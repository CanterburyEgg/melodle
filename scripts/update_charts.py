#!/usr/bin/env python3
"""Unified Billboard Hot 100, Timeline, and Decade Playlist updater for Melodle.

Features:
- Enforces the 5-artist exclusion list (Diddy/Puff Daddy, R. Kelly, Gary Glitter,
  Morgan Wallen, Jason Aldean — lead & featured) with #11+ chart promotion.
- Enforces 100% playable charts (--cull-unplayable): if a charting track has no
  30s Spotify preview, promotes the next playable #11+ track from that week.
- Resolves Spotify track URIs, 30s p.scdn.co previews, and 300x300 i.scdn.co
  album art via local caches + Spotify Web API + Spotify track embeds, saving
  progress continuously to a resumable checkpoint file.
- Atomically updates chart_dates.json, top_10s.json, top_10s_linked.json,
  top_10s_data.json (Timeline), billboard-no-1s.json, and decade playlists.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import (  # noqa: E402
    DATA_DIR,
    GITIGNORED_PLAYLISTS,
    JSONS_DIR,
    REPO_ROOT,
    atomic_write_json,
    clean_image_url,
    clean_preview_url,
    clean_text,
    extract_primary_artist,
    is_banned_entry,
    normalize_artist_token,
    normalize_match_key,
    normalize_spotify_uri,
    normalize_title_token,
    read_json,
    strip_accents,
)

DEFAULT_BILLBOARD_URL = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/all.json"
DEFAULT_CHECKPOINT_PATH = REPO_ROOT / ".cache" / "spotify_checkpoint.json"
DEFAULT_LEGACY_CACHE_PATH = REPO_ROOT / ".cache" / "legacy_spotify_cache.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

UNCENSOR_TITLES = {
    "f**kin problems": "Fuckin' Problems",
    "i don't f**k with you": "I Don't Fuck With You",
    "work b**ch!": "Work Bitch",
    "b**** better have my money": "Bitch Better Have My Money",
    "apes**t": "APESHIT",
}

UNCENSOR_PATTERNS = (
    (re.compile(r"\bf\*{2,}k(?:in'?|ing)?\b", re.I), lambda m: "fuckin'" if "in" in m.group(0).lower() else "fuck"),
    (re.compile(r"\bs\*{2,}t\b", re.I), lambda _: "shit"),
    (re.compile(r"\bb\*{2,}(?:ch|h)\b", re.I), lambda _: "bitch"),
    (re.compile(r"\ba\*{2}\b", re.I), lambda _: "ass"),
    (re.compile(r"\bd\*{2}n\b", re.I), lambda _: "damn"),
    (re.compile(r"\bh\*ll\b", re.I), lambda _: "hell"),
    (re.compile(r"\bn\*{2,}(?:as|az|a)\b", re.I), lambda _: "niggas"),
)

HOLIDAY_TITLE_RE = re.compile(
    r"\b("
    r"christmas|xmas|santa\s+claus|santa\s+baby|santa\s+tell\s+me"
    r"|jingle\s+bell|sleigh\s+ride|feliz\s+navidad|rudolph"
    r"|winter\s+wonderland|holly\s+jolly|silent\s+night|deck\s+the\s+halls"
    r"|little\s+saint\s+nick|underneath\s+the\s+tree|mistletoe"
    r"|let\s+it\s+snow|it's\s+the\s+most\s+wonderful\s+time"
    r")\b",
    re.IGNORECASE,
)

ARTIST_TYPO_FIXES = {
    "Barry DeVorzon and Perry Botikin Jr.": "Barry DeVorzon and Perry Botkin, Jr.",
    'The 4 Seasons Featuring the "Sound of Frankie Valli': 'The 4 Seasons Featuring the "Sound of Frankie Valli"',
}


def uncensor_title(title: str) -> str:
    low = title.lower()
    if low in UNCENSOR_TITLES:
        return UNCENSOR_TITLES[low]
    out = title
    for pat, repl in UNCENSOR_PATTERNS:
        out = pat.sub(repl, out)
    return out


class QuotaExceededError(RuntimeError):
    """Raised when Spotify Web API returns a long 24h Retry-After window."""


class SpotifyResolver:
    """Resolves (title, artist) -> {uri, preview, picture, year, sp_title, sp_artist}."""

    def __init__(
        self,
        *,
        creds: dict[str, str] | None,
        checkpoint_path: Path | None,
        extra_cache_path: Path | None,
        rps: float = 3.0,
        offline: bool = False,
    ) -> None:
        self.creds = creds
        self.checkpoint_path = checkpoint_path
        self.min_interval = 1.0 / max(0.5, rps)
        self.offline = offline
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._last_api_call: float = 0.0

        self.exact_cache: dict[str, dict[str, Any]] = {}
        self.fuzzy_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.dirty_count: int = 0

        self._load_existing_repo_caches(extra_cache_path)
        if checkpoint_path and checkpoint_path.exists():
            cp = read_json(checkpoint_path)
            if isinstance(cp, dict):
                for k, v in cp.items():
                    if not isinstance(v, dict):
                        continue
                    existing = self.exact_cache.get(k)
                    # Never let a cached no_preview clobber a known valid preview from repo files
                    if v.get("no_preview") and existing and existing.get("preview"):
                        continue
                    if existing and existing.get("preview") and not v.get("preview"):
                        merged = {**existing, **{kk: vv for kk, vv in v.items() if vv}}
                        self.exact_cache[k] = merged
                    else:
                        self.exact_cache[k] = v
                    cur = self.exact_cache[k]
                    if cur.get("preview"):
                        parts = k.split("|||", 1)
                        if len(parts) == 2:
                            self.fuzzy_cache.setdefault(normalize_match_key(parts[0], parts[1]), cur)

    def _register_known(
        self,
        title: str,
        artist: str,
        *,
        uri: str = "",
        preview: str = "",
        picture: str = "",
        year: str = "",
        allow_fuzzy: bool = True,
    ) -> None:
        t = clean_text(title)
        a = ARTIST_TYPO_FIXES.get(clean_text(artist), clean_text(artist))
        if not t or not a or is_banned_entry(t, a, uri):
            return
        prev = clean_preview_url(preview)
        pic = clean_image_url(picture)
        norm_uri = normalize_spotify_uri(uri)
        if not prev and not norm_uri:
            return

        key = f"{t}|||{a}"
        existing = self.exact_cache.get(key, {})
        merged = {
            "uri": norm_uri or existing.get("uri", ""),
            "preview": prev or existing.get("preview", ""),
            "picture": pic or existing.get("picture", ""),
            "year": year or existing.get("year", ""),
            "sp_title": existing.get("sp_title") or t,
            "sp_artist": existing.get("sp_artist") or a,
        }
        self.exact_cache[key] = merged
        if allow_fuzzy and merged["preview"]:
            fk = normalize_match_key(t, a)
            if fk not in self.fuzzy_cache or (merged["uri"] and not self.fuzzy_cache[fk].get("uri")):
                self.fuzzy_cache[fk] = merged

    def _load_existing_repo_caches(self, extra_cache_path: Path | None) -> None:
        for seed_path in (DEFAULT_LEGACY_CACHE_PATH, extra_cache_path):
            if seed_path and seed_path.exists():
                for row in read_json(seed_path):
                    self._register_known(
                        row.get("title", ""),
                        row.get("artist", ""),
                        uri=row.get("id", "") or row.get("trackLink", ""),
                        preview=row.get("preview", ""),
                        picture=row.get("picture", ""),
                    )

        for p in sorted(JSONS_DIR.glob("*.json")):
            if p.name in GITIGNORED_PLAYLISTS:
                continue
            try:
                rows = read_json(p)
            except Exception:
                continue
            if isinstance(rows, list):
                is_startup = p.name == "startup-playlist.json"
                for row in rows:
                    if isinstance(row, dict):
                        self._register_known(
                            row.get("title", ""),
                            row.get("artist", ""),
                            uri=row.get("trackLink", ""),
                            preview=row.get("preview", ""),
                            allow_fuzzy=not is_startup,
                        )

        td_path = DATA_DIR / "top_10s_data.json"
        if td_path.exists():
            for row in read_json(td_path):
                self._register_known(
                    row.get("title", ""),
                    row.get("artist", ""),
                    preview=row.get("link", ""),
                    picture=row.get("picture", ""),
                    year=str(row.get("year", "")),
                )

        tl_path = DATA_DIR / "top_10s_linked.json"
        if tl_path.exists():
            for row in read_json(tl_path):
                if row.get("link"):
                    self._register_known(
                        row.get("title", ""),
                        row.get("artist", ""),
                        preview=row.get("link", ""),
                    )

    def _mark_dirty(self) -> None:
        self.dirty_count += 1
        if self.dirty_count >= 25:
            self.save_checkpoint()

    def save_checkpoint(self) -> None:
        if self.checkpoint_path and self.dirty_count > 0:
            atomic_write_json(self.checkpoint_path, self.exact_cache, indent=2)
            self.dirty_count = 0

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token
        if not self.creds or not self.creds.get("client_id") or not self.creds.get("client_secret"):
            raise RuntimeError(
                "Spotify API credentials required for network lookups "
                "(set SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET or pass --creds-file)."
            )
        raw = f"{self.creds['client_id']}:{self.creds['client_secret']}".encode("utf-8")
        b64 = base64.b64encode(raw).decode("ascii")
        body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=body,
            headers={
                "Authorization": f"Basic {b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self._token = payload["access_token"]
        self._token_expiry = now + int(payload.get("expires_in", 3600))
        return self._token

    def _pace(self) -> None:
        elapsed = time.time() - self._last_api_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_api_call = time.time()

    def fetch_embed(self, track_id: str) -> dict[str, Any] | None:
        """Fetch public Spotify track embed. Returns None on network/transient error, or dict on HTTP 200."""
        url = f"https://open.spotify.com/embed/track/{track_id}"
        for attempt in range(3):
            self._pace()
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    page = resp.read().decode("utf-8")
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.DOTALL)
                if not m:
                    return None
                entity = (
                    json.loads(m.group(1))
                    .get("props", {})
                    .get("pageProps", {})
                    .get("state", {})
                    .get("data", {})
                    .get("entity", {})
                )
                title = clean_text(entity.get("title") or entity.get("name") or "")
                artists = ", ".join(clean_text(a.get("name", "")) for a in entity.get("artists", []) if a.get("name"))
                if is_banned_entry(title, artists, track_id):
                    return {"banned": True}
                preview = clean_preview_url((entity.get("audioPreview") or {}).get("url", ""))
                imgs = (entity.get("visualIdentity") or {}).get("image") or []
                pic = ""
                for im in imgs:
                    u = im.get("url", "")
                    if "00001e02" in u:
                        pic = clean_image_url(u)
                        break
                if not pic and imgs:
                    pic = clean_image_url(imgs[0].get("url", ""))
                rel = str((entity.get("releaseDate") or {}).get("isoString", "") or "")
                yr = rel[:4] if re.match(r"^\d{4}", rel) else ""
                return {
                    "uri": f"spotify:track:{track_id}",
                    "preview": preview,
                    "picture": pic,
                    "year": yr,
                    "sp_title": title,
                    "sp_artist": artists,
                }
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return {"preview": "", "not_found": True}
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                return None
            except Exception:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None
        return None

    def _search_spotify_candidates(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        for _ in range(3):
            token = self._get_token()
            self._pace()
            params = urllib.parse.urlencode({"q": query, "type": "track", "market": "US", "limit": limit})
            req = urllib.request.Request(
                f"https://api.spotify.com/v1/search?{params}",
                headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data.get("tracks", {}).get("items", [])
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    raw_ra = exc.headers.get("Retry-After", "5")
                    try:
                        retry_after = int(float(raw_ra))
                    except ValueError:
                        retry_after = 60
                    if retry_after > 45:
                        self.save_checkpoint()
                        raise QuotaExceededError(
                            f"Spotify Search API rate-limited (Retry-After={retry_after}s). Checkpoint saved."
                        ) from exc
                    time.sleep(retry_after + 1)
                    continue
                if exc.code == 401:
                    self._token = None
                    continue
                raise
        return []

    @staticmethod
    def _titles_match(target_title: str, cand_name: str) -> tuple[bool, bool]:
        """Return (exact_match, prefix_match) between target_title and cand_name."""
        t_norm = normalize_title_token(target_title)
        ct_norm = normalize_title_token(cand_name)
        if not t_norm or not ct_norm:
            return False, False
        if t_norm == ct_norm:
            return True, False
        # Wildcard match if target still contains censoring '*'
        if "*" in target_title:
            wc = re.sub(r"[^a-z0-9*]+", "", strip_accents(target_title).lower())
            pat = "^" + re.sub(r"\*+", "[a-z0-9]+", wc) + "$"
            if re.match(pat, ct_norm):
                return True, False
        # Word-boundary prefix match only when both normalized titles are >= 5 chars
        # and Taylor's Version / Remix parity matches
        for special in ("taylorsversion", "remix"):
            if (special in t_norm) != (special in ct_norm):
                return False, False
        if len(t_norm) >= 5 and len(ct_norm) >= 5:
            t_words = re.findall(r"\w+", strip_accents(target_title).lower())
            c_words = re.findall(r"\w+", strip_accents(cand_name).lower())
            if t_words and c_words and (c_words[: len(t_words)] == t_words or t_words[: len(c_words)] == c_words):
                return False, True
        return False, False

    @staticmethod
    def _score_candidate(
        item: dict[str, Any],
        target_title: str,
        raw_target_title: str,
        target_artist: str,
        chart_year: int,
    ) -> int:
        cand_name = clean_text(item.get("name", ""))
        cand_artist_list = [clean_text(a.get("name", "")) for a in item.get("artists", []) if a.get("name")]
        cand_artists = ", ".join(cand_artist_list)

        exact_t, prefix_t = SpotifyResolver._titles_match(target_title, cand_name)
        if not exact_t and not prefix_t:
            exact_t, prefix_t = SpotifyResolver._titles_match(raw_target_title, cand_name)
        if not exact_t and not prefix_t:
            return -1000

        # Primary target artist MUST match at least one candidate artist (no substring inside 'billyjoel' / 'blackcrowes')
        primary_norm = extract_primary_artist(target_artist)
        cand_norms = [normalize_artist_token(a) for a in cand_artist_list]
        cand_joined_norm = normalize_artist_token(cand_artists)

        primary_matched = False
        if primary_norm in cand_norms or primary_norm == cand_joined_norm:
            primary_matched = True
        elif len(primary_norm) >= 6 and any(cn.startswith(primary_norm) or primary_norm.startswith(cn) for cn in cand_norms if len(cn) >= 5):
            primary_matched = True
        if not primary_matched:
            return -1000

        # If exact title + primary artist match a banned featured artist on Spotify, return special -99999 sentinel
        if is_banned_entry(cand_name, cand_artists, item.get("id", "")):
            return -99999 if exact_t else -9999

        low_blob = f"{cand_name} {cand_artists} {item.get('album', {}).get('name', '')}".lower()
        if any(bad in low_blob for bad in ("karaoke", "tribute", "originally performed", "in the style of", "8-bit")):
            return -9999
        if "taylor's version" in low_blob and "taylor's version" not in raw_target_title.lower() and chart_year < 2021:
            return -500

        score = 100 if exact_t else 55
        score += 80

        # Secondary / featured artist bonus when target credits a collaborator
        if any(k in target_artist.lower() for k in ("feat", "&", "with")):
            secondary = re.split(r"\s+(?:featuring|feat\.?|with|&)\s+", target_artist.lower(), maxsplit=1)
            if len(secondary) > 1:
                sec_tok = normalize_artist_token(secondary[1].split(",")[0])
                if sec_tok and any(sec_tok == cn for cn in cand_norms):
                    score += 35

        for tag in ("live", "instrumental", "acoustic", "commentary"):
            if tag in cand_name.lower() and tag not in raw_target_title.lower():
                score -= 60

        album = item.get("album", {})
        rel = str(album.get("release_date", ""))
        if re.match(r"^\d{4}", rel):
            rel_yr = int(rel[:4])
            diff = abs(rel_yr - chart_year)
            if diff <= 1:
                score += 25
            elif diff <= 3:
                score += 10
        if album.get("album_type") == "album":
            score += 8
        score += int(item.get("popularity", 0)) // 5
        return score

    @staticmethod
    def _clamp_year(yr_raw: Any, chart_year: int) -> str:
        s = str(yr_raw or "").strip()
        if re.fullmatch(r"\d{4}", s):
            yi = int(s)
            if 1950 <= yi <= chart_year:
                return s
        return str(chart_year)

    def resolve(
        self,
        title: str,
        artist: str,
        chart_year: int,
        *,
        need_uri: bool = False,
        need_picture: bool = False,
    ) -> dict[str, Any] | None:
        t = clean_text(title)
        a = ARTIST_TYPO_FIXES.get(clean_text(artist), clean_text(artist))
        exact_key = f"{t}|||{a}"

        cached = self.exact_cache.get(exact_key)
        if cached is not None:
            if cached.get("banned") or cached.get("no_preview"):
                return cached if cached.get("banned") else None
            if need_uri and cached.get("no_uri"):
                return None
            if need_picture and cached.get("no_picture") and not cached.get("picture"):
                return cached
            has_req_uri = (not need_uri) or bool(cached.get("uri"))
            has_req_pic = (not need_picture) or bool(cached.get("picture"))
            if cached.get("preview") and has_req_uri and has_req_pic:
                return cached

            # Fast path: if URI is already known (e.g. from startup-playlist or 2020s.json), fetch embed directly!
            if cached.get("uri") and not self.offline and (not cached.get("preview") or (need_picture and not cached.get("picture"))):
                tid = cached["uri"].split(":")[-1]
                emb = self.fetch_embed(tid)
                if emb and emb.get("banned"):
                    self.exact_cache[exact_key] = {"banned": True}
                    self._mark_dirty()
                    return {"banned": True}
                if emb:
                    merged_prev = emb.get("preview") or cached.get("preview", "")
                    merged_pic = emb.get("picture") or cached.get("picture", "")
                    if merged_prev:
                        updated = {
                            **cached,
                            "preview": merged_prev,
                            "picture": merged_pic,
                            "year": self._clamp_year(emb.get("year") or cached.get("year"), chart_year),
                            "no_picture": not bool(merged_pic),
                        }
                        self.exact_cache[exact_key] = updated
                        self.fuzzy_cache.setdefault(normalize_match_key(t, a), updated)
                        self._mark_dirty()
                        if (not need_uri or updated.get("uri")) and (not need_picture or updated.get("picture")):
                            return updated
                        return updated

        is_collab_variant = bool(re.search(r"\b(feat|featuring|with|remix)\b|&", a, re.I))
        if not is_collab_variant and "taylor's version" not in t.lower() and "remix" not in t.lower():
            f_hit = self.fuzzy_cache.get(normalize_match_key(t, a))
            if f_hit and "taylor's version" not in f_hit.get("sp_title", "").lower():
                has_req_uri = (not need_uri) or bool(f_hit.get("uri"))
                has_req_pic = (not need_picture) or bool(f_hit.get("picture"))
                if f_hit.get("preview") and has_req_uri and has_req_pic:
                    return f_hit

        if self.offline:
            return cached if (cached and cached.get("preview") and not need_uri) else None

        search_title = uncensor_title(re.sub(r'\s*\(from\s+"[^"]+"\)', "", t, flags=re.I).strip())
        q_title = search_title.replace('"', "")
        primary_artist = re.split(r"\s+(?:Featuring|Feat\.?|Ft\.?|With|Duet With|X)\s+", a, maxsplit=1, flags=re.I)[0]
        primary_artist = primary_artist.replace("Ke$ha", "Kesha").replace("P!nk", "Pink").replace('"', "")

        queries = [
            f'track:"{q_title}" artist:"{primary_artist}"',
            f"{q_title} {re.sub(r'\\b(Featuring|Feat\\.?|With)\\b', ' ', a, flags=re.I)}",
        ]
        seen_ids: set[str] = set()
        scored: list[tuple[int, dict[str, Any]]] = []

        for q in queries:
            for item in self._search_spotify_candidates(q):
                tid = item.get("id")
                if not tid or tid in seen_ids:
                    continue
                seen_ids.add(tid)
                sc = self._score_candidate(item, search_title, t, a, chart_year)
                if sc == -99999:
                    self.exact_cache[exact_key] = {"banned": True}
                    self._mark_dirty()
                    return {"banned": True}
                if sc > 0:
                    scored.append((sc, item))
            if any(sc >= 180 for sc, _ in scored):
                break

        scored.sort(key=lambda pair: pair[0], reverse=True)
        had_transient_embed_err = False
        existing_prev = (cached or {}).get("preview", "")

        for _, item in scored[:4]:
            tid = item["id"]
            emb = self.fetch_embed(tid)
            if emb is None:
                had_transient_embed_err = True
                continue
            if emb.get("banned"):
                self.exact_cache[exact_key] = {"banned": True}
                self._mark_dirty()
                return {"banned": True}
            final_prev = emb.get("preview") or existing_prev
            if final_prev:
                alb = item.get("album", {})
                imgs = alb.get("images", [])
                pic = (
                    emb.get("picture")
                    or clean_image_url(imgs[1]["url"] if len(imgs) > 1 else (imgs[0]["url"] if imgs else ""))
                    or (cached or {}).get("picture", "")
                )
                rel = str(alb.get("release_date", ""))
                yr = self._clamp_year(rel[:4] if re.match(r"^\d{4}", rel) else emb.get("year"), chart_year)
                sp_artists = ", ".join(x.get("name", "") for x in item.get("artists", []))
                record = {
                    "uri": f"spotify:track:{tid}",
                    "preview": final_prev,
                    "picture": pic,
                    "year": yr,
                    "sp_title": clean_text(item.get("name") or t),
                    "sp_artist": clean_text(sp_artists or a),
                }
                self.exact_cache[exact_key] = record
                self.fuzzy_cache.setdefault(normalize_match_key(t, a), record)
                self._mark_dirty()
                return record

        # Never clobber an existing valid preview with no_preview, and never cache transient network errors!
        if cached and cached.get("preview"):
            updated = dict(cached)
            if need_uri:
                updated["no_uri"] = True
            if need_picture and not updated.get("picture"):
                updated["no_picture"] = True
            self.exact_cache[exact_key] = updated
            self._mark_dirty()
            return None if need_uri else updated

        if not had_transient_embed_err:
            self.exact_cache[exact_key] = {"no_preview": True}
            self._mark_dirty()
        return None


def load_billboard_feed(source: str) -> list[dict[str, Any]]:
    p = Path(source)
    if p.exists():
        raw = read_json(p)
    else:
        req = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    if isinstance(raw, dict) and "data" in raw:
        return raw["data"]
    if isinstance(raw, list):
        return raw
    raise ValueError("Unexpected Billboard feed structure")


def load_credentials(creds_file: str | None) -> dict[str, str] | None:
    if creds_file:
        p = Path(creds_file)
        if p.exists():
            return read_json(p)
    cid = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    csec = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if cid and csec:
        return {"client_id": cid, "client_secret": csec}
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update Melodle Billboard charts, Timeline, and decade playlists.")
    parser.add_argument(
        "--billboard-source",
        default=DEFAULT_BILLBOARD_URL,
        help="Path or URL to mhollingshead/billboard-hot-100 all.json.",
    )
    parser.add_argument("--creds-file", help="Path to JSON with Spotify client_id and client_secret.")
    parser.add_argument(
        "--checkpoint",
        default=str(DEFAULT_CHECKPOINT_PATH),
        help="Resumable lookup cache path.",
    )
    parser.add_argument("--extra-cache", help="Optional seed lookup cache JSON.")
    parser.add_argument("--rps", type=float, default=3.0, help="Max Spotify API/embed requests/sec (default: 3.0).")
    parser.add_argument(
        "--cull-unplayable",
        action="store_true",
        help="Cull any Top 10 song with no playable Spotify preview and promote #11+ (#R4 Option B).",
    )
    parser.add_argument(
        "--sync-decades",
        nargs="*",
        default=[],
        help="Decade playlist(s) to expand/sync up to --decade-max-rank (e.g. 2000s 2020s).",
    )
    parser.add_argument("--decade-max-rank", type=int, default=20, help="Max Billboard peak rank for --sync-decades.")
    parser.add_argument("--sync-no1s", action="store_true", help="Sync new #1 hits into jsons/billboard-no-1s.json.")
    parser.add_argument("--offline", action="store_true", help="Use local caches only without network calls.")
    parser.add_argument("--dry-run", action="store_true", help="Compute updates without writing to jsons/.")
    args = parser.parse_args(argv)

    if args.offline and args.cull_unplayable and not args.dry_run:
        print("[ERROR] --offline cannot be combined with --cull-unplayable unless --dry-run is set.", file=sys.stderr)
        return 1

    raw_charts = load_billboard_feed(args.billboard_source)
    existing_dates_list = read_json(DATA_DIR / "chart_dates.json").get("dates", [])
    existing_dates = set(existing_dates_list)
    existing_linked = read_json(DATA_DIR / "top_10s_linked.json")
    existing_by_week: dict[str, list[dict[str, Any]]] = {}
    for row in existing_linked:
        existing_by_week.setdefault(row["date"], []).append(row)

    # Deduplicate charts by normalized date & compute earliest Hot 100 year for every song
    charts_by_date: dict[str, dict[str, Any]] = {}
    first_chart_year: dict[tuple[str, str], int] = {}
    for ch in raw_charts:
        d = ch["date"]
        if d == "1976-07-03" and "1976-07-04" in existing_by_week:
            d = "1976-07-04"
        charts_by_date[d] = {**ch, "date": d}
        yr = int(d[:4])
        for entry in ch.get("data", []):
            t = clean_text(entry.get("song", ""))
            a = ARTIST_TYPO_FIXES.get(clean_text(entry.get("artist", "")), clean_text(entry.get("artist", "")))
            mk = normalize_match_key(t, a)
            if mk not in first_chart_year or yr < first_chart_year[mk]:
                first_chart_year[mk] = yr

    missing_existing = existing_dates - set(charts_by_date.keys())
    if missing_existing:
        print(
            f"[WARN] Carrying forward {len(missing_existing)} existing date(s) absent from feed.",
            file=sys.stderr,
        )
        for d in missing_existing:
            charts_by_date[d] = {"date": d, "data": []}

    charts = [charts_by_date[d] for d in sorted(charts_by_date.keys())]

    resolver = SpotifyResolver(
        creds=load_credentials(args.creds_file),
        checkpoint_path=Path(args.checkpoint) if args.checkpoint else None,
        extra_cache_path=Path(args.extra_cache) if args.extra_cache else None,
        rps=args.rps,
        offline=args.offline,
    )

    new_dates: list[str] = []
    out_top10: list[dict[str, Any]] = []
    out_linked: list[dict[str, Any]] = []
    earliest_active_chart_song: dict[tuple[str, str], tuple[int, str, str, str]] = {}

    weeks_added = 0
    weeks_rebuilt = 0

    try:
        for chart in charts:
            date_str = chart["date"]
            chart_year = int(date_str[:4])
            new_dates.append(date_str)

            prev_rows = existing_by_week.get(date_str)
            resolved_prev: list[dict[str, Any]] | None = None

            # Always attempt to fill missing links on existing weeks BEFORE deciding to rebuild (#S10)
            if prev_rows is not None:
                resolved_prev = []
                for r in sorted(prev_rows, key=lambda x: int(x["rank"])):
                    t = clean_text(r["title"])
                    a = ARTIST_TYPO_FIXES.get(clean_text(r["artist"]), clean_text(r["artist"]))
                    lnk = r.get("link", "")
                    if not lnk:
                        hit = resolver.resolve(t, a, chart_year)
                        if hit and not hit.get("banned") and hit.get("preview"):
                            lnk = hit["preview"]
                    resolved_prev.append({"date": date_str, "rank": int(r["rank"]), "title": t, "artist": a, "link": lnk})

            needs_rebuild = resolved_prev is None or (
                args.cull_unplayable
                and bool(chart.get("data"))
                and any(not r.get("link") or is_banned_entry(r["title"], r["artist"]) for r in resolved_prev)
            )

            if not needs_rebuild and resolved_prev is not None:
                for row in resolved_prev:
                    out_top10.append(
                        {"date": row["date"], "rank": row["rank"], "title": row["title"], "artist": row["artist"]}
                    )
                    out_linked.append(row)
                    sk = (row["title"].lower(), row["artist"].lower())
                    if row["link"] and (sk not in earliest_active_chart_song or chart_year < earliest_active_chart_song[sk][0]):
                        earliest_active_chart_song[sk] = (chart_year, row["title"], row["artist"], row["link"])
                continue

            if date_str not in existing_dates:
                weeks_added += 1
            else:
                weeks_rebuilt += 1

            entries = sorted(chart.get("data", []), key=lambda e: int(e["this_week"]))
            chosen: list[dict[str, Any]] = []
            seen_songs: set[tuple[str, str]] = set()
            seen_previews: set[str] = set()
            had_promotion = False

            for entry in entries:
                if len(chosen) >= 10:
                    break
                t = clean_text(entry.get("song", ""))
                a = ARTIST_TYPO_FIXES.get(clean_text(entry.get("artist", "")), clean_text(entry.get("artist", "")))
                if is_banned_entry(t, a):
                    had_promotion = True
                    continue
                sk = (t.lower(), a.lower())
                if sk in seen_songs:
                    had_promotion = True
                    continue

                hit = resolver.resolve(t, a, chart_year)
                if hit and hit.get("banned"):
                    had_promotion = True
                    continue
                prev_url = (hit or {}).get("preview", "")
                if args.cull_unplayable and not prev_url:
                    had_promotion = True
                    continue
                if prev_url and prev_url in seen_previews:
                    had_promotion = True
                    continue

                seen_songs.add(sk)
                if prev_url:
                    seen_previews.add(prev_url)
                orig_rank = int(entry["this_week"])
                rank = (len(chosen) + 1) if (had_promotion or orig_rank > 10) else orig_rank
                chosen.append({"date": date_str, "rank": rank, "title": t, "artist": a, "link": prev_url})

                if prev_url and (sk not in earliest_active_chart_song or chart_year < earliest_active_chart_song[sk][0]):
                    earliest_active_chart_song[sk] = (chart_year, t, a, prev_url)

            if len(chosen) != 10 and not args.dry_run:
                raise RuntimeError(f"Week {date_str} resolved only {len(chosen)}/10 songs; aborting write.")

            for row in chosen:
                out_top10.append(
                    {"date": row["date"], "rank": row["rank"], "title": row["title"], "artist": row["artist"]}
                )
                out_linked.append(row)

        # Sync Timeline top_10s_data.json (repairing incomplete skeletons & fetching missing pictures!)
        raw_tdata = read_json(DATA_DIR / "top_10s_data.json")
        tdata_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        tdata_order: list[tuple[str, str]] = []
        for r in raw_tdata:
            t = clean_text(r["title"])
            a = ARTIST_TYPO_FIXES.get(clean_text(r["artist"]), clean_text(r["artist"]))
            if is_banned_entry(t, a):
                continue
            sk = (t.lower(), a.lower())
            if sk not in tdata_by_key:
                tdata_order.append(sk)
            tdata_by_key[sk] = {
                "title": t,
                "artist": a,
                "link": clean_preview_url(r.get("link", "")) or r.get("link", ""),
                "year": str(r.get("year", "")),
                "picture": clean_image_url(r.get("picture", "")) or r.get("picture", ""),
            }

        added_td = 0
        repaired_td = 0
        for sk, (chart_yr, t, a, lnk) in sorted(earliest_active_chart_song.items(), key=lambda kv: (kv[1][0], kv[0][0])):
            existing_td = tdata_by_key.get(sk)
            if existing_td and existing_td.get("link") and existing_td.get("picture"):
                continue
            hit = resolver.resolve(t, a, chart_yr, need_picture=True)
            if not hit or hit.get("banned"):
                continue
            pic = hit.get("picture", "")
            prev_final = hit.get("preview") or lnk
            if not prev_final or not pic:
                continue
            yr_str = resolver._clamp_year(
                existing_td.get("year") if existing_td else hit.get("year"),
                chart_yr,
            )
            new_row = {
                "title": t,
                "artist": a,
                "link": prev_final,
                "year": yr_str,
                "picture": pic,
            }
            if existing_td is None:
                tdata_order.append(sk)
                added_td += 1
            else:
                repaired_td += 1
            tdata_by_key[sk] = new_row

        tdata: list[dict[str, Any]] = []
        for sk in tdata_order:
            row = tdata_by_key[sk]
            if args.cull_unplayable and (not row.get("link") or not row.get("picture")):
                continue
            tdata.append(row)

        # Optional decade playlist expansion / sync (#S1 holiday & catalog recurrence filter)
        christmas_path = JSONS_DIR / "christmas.json"
        christmas_rows = read_json(christmas_path) if christmas_path.exists() else []
        christmas_uris = {r["trackLink"] for r in christmas_rows if r.get("trackLink")}
        christmas_keys = {normalize_match_key(r["title"], r["artist"]) for r in christmas_rows}

        decade_updates: dict[Path, list[dict[str, Any]]] = {}
        for dec in args.sync_decades:
            m = re.fullmatch(r"(\d{4})s", dec.strip())
            if not m:
                print(f"[WARN] Invalid decade label {dec!r}, expected e.g. '2000s' or '2020s'", file=sys.stderr)
                continue
            start_yr = int(m.group(1))
            dec_path = JSONS_DIR / f"{start_yr}s.json"
            dec_entries: list[dict[str, Any]] = read_json(dec_path) if dec_path.exists() else []
            seen_uris = {e["trackLink"] for e in dec_entries if e.get("trackLink")}
            seen_previews = {clean_preview_url(e.get("preview", "")) for e in dec_entries if e.get("preview")}
            seen_keys = {normalize_match_key(e["title"], e["artist"]) for e in dec_entries}

            peaks: dict[tuple[str, str], tuple[int, str, str, int]] = {}
            for chart in charts:
                yr = int(chart["date"][:4])
                if not (start_yr <= yr <= start_yr + 9):
                    continue
                for e in chart.get("data", []):
                    rk = int(e["this_week"])
                    if rk > args.decade_max_rank:
                        continue
                    t = clean_text(e.get("song", ""))
                    a = ARTIST_TYPO_FIXES.get(clean_text(e.get("artist", "")), clean_text(e.get("artist", "")))
                    if is_banned_entry(t, a) or HOLIDAY_TITLE_RE.search(t):
                        continue
                    mk = normalize_match_key(t, a)
                    if mk in seen_keys or mk in christmas_keys:
                        continue
                    # Exclude pre-decade catalog re-entries (allow late Dec -> Jan crossovers via start_yr - 1)
                    if first_chart_year.get(mk, yr) < start_yr - 1:
                        continue
                    if mk not in peaks or rk < peaks[mk][0]:
                        peaks[mk] = (rk, t, a, yr)

            added_dec = 0
            for mk, (_, t, a, yr) in sorted(peaks.items(), key=lambda kv: (kv[1][3], kv[1][0], kv[1][1])):
                if mk in seen_keys:
                    continue
                hit = resolver.resolve(t, a, yr, need_uri=True)
                if not hit or hit.get("banned") or not hit.get("uri") or not hit.get("preview"):
                    continue
                if hit["uri"] in seen_uris or hit["uri"] in christmas_uris:
                    continue
                prev_clean = clean_preview_url(hit["preview"])
                if prev_clean and prev_clean in seen_previews:
                    continue
                if hit.get("year") and re.fullmatch(r"\d{4}", str(hit["year"])) and int(hit["year"]) < start_yr - 1:
                    continue
                sp_t = hit.get("sp_title") or t
                if HOLIDAY_TITLE_RE.search(sp_t):
                    continue
                seen_uris.add(hit["uri"])
                if prev_clean:
                    seen_previews.add(prev_clean)
                seen_keys.add(mk)
                seen_keys.add(normalize_match_key(sp_t, hit.get("sp_artist") or a))
                dec_entries.append({
                    "title": sp_t,
                    "artist": hit.get("sp_artist") or a,
                    "trackLink": hit["uri"],
                    "preview": hit["preview"],
                })
                added_dec += 1
            decade_updates[dec_path] = dec_entries
            print(f"[DECADE] {dec_path.name}: +{added_dec} tracks -> {len(dec_entries)} total")

        # Optional billboard-no-1s.json sync
        no1_entries: list[dict[str, Any]] | None = None
        if args.sync_no1s:
            no1_path = JSONS_DIR / "billboard-no-1s.json"
            no1_entries = read_json(no1_path)
            seen_no1_uris = {e["trackLink"] for e in no1_entries}
            seen_no1_previews = {clean_preview_url(e.get("preview", "")) for e in no1_entries if e.get("preview")}
            seen_no1_keys = {normalize_match_key(e["title"], e["artist"]) for e in no1_entries}
            added_no1 = 0
            for chart in charts:
                yr = int(chart["date"][:4])
                for e in chart.get("data", []):
                    if int(e["this_week"]) != 1:
                        continue
                    t = clean_text(e.get("song", ""))
                    a = ARTIST_TYPO_FIXES.get(clean_text(e.get("artist", "")), clean_text(e.get("artist", "")))
                    if is_banned_entry(t, a):
                        continue
                    mk = normalize_match_key(t, a)
                    if mk in seen_no1_keys:
                        continue
                    hit = resolver.resolve(t, a, yr, need_uri=True)
                    if not hit or hit.get("banned") or not hit.get("uri") or not hit.get("preview"):
                        continue
                    prev_clean = clean_preview_url(hit["preview"])
                    if hit["uri"] in seen_no1_uris or (prev_clean and prev_clean in seen_no1_previews):
                        continue
                    seen_no1_uris.add(hit["uri"])
                    if prev_clean:
                        seen_no1_previews.add(prev_clean)
                    seen_no1_keys.add(mk)
                    no1_entries.append({
                        "title": hit.get("sp_title") or t,
                        "artist": hit.get("sp_artist") or a,
                        "trackLink": hit["uri"],
                        "preview": hit["preview"],
                    })
                    added_no1 += 1
            print(f"[NO-1S] billboard-no-1s.json: +{added_no1} tracks -> {len(no1_entries)} total")

    finally:
        resolver.save_checkpoint()

    unlinked_count = sum(1 for r in out_linked if not r.get("link"))
    print(
        f"[SUMMARY] weeks={len(new_dates)} (+{weeks_added} new, {weeks_rebuilt} rebuilt), "
        f"rows={len(out_linked)}, unlinked={unlinked_count}, "
        f"timeline={len(tdata)} (+{added_td} new, {repaired_td} repaired)"
    )

    if not args.dry_run:
        atomic_write_json(DATA_DIR / "chart_dates.json", {"dates": new_dates})
        atomic_write_json(DATA_DIR / "top_10s.json", out_top10)
        atomic_write_json(DATA_DIR / "top_10s_linked.json", out_linked)
        atomic_write_json(DATA_DIR / "top_10s_data.json", tdata)
        for dec_path, dec_entries in decade_updates.items():
            atomic_write_json(dec_path, dec_entries)
        if no1_entries is not None:
            atomic_write_json(JSONS_DIR / "billboard-no-1s.json", no1_entries)
        print("[WRITE] All canonical Melodle data files updated atomically.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
