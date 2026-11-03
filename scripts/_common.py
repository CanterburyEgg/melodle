"""Shared constants, normalization helpers, and atomic JSON I/O for Melodle scripts."""

from __future__ import annotations

import functools
import html
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONS_DIR = REPO_ROOT / "jsons"
DATA_DIR = JSONS_DIR / "data"

GITIGNORED_PLAYLISTS = {"bailey-bops.json", "boy-bops.json"}

# Official 5-artist exclusion list (lead, co-lead, or featured):
# Diddy / P. Diddy / Puff Daddy / Sean Combs, R. Kelly, Gary Glitter, Morgan Wallen, Jason Aldean
BANNED_ARTIST_RE = re.compile(
    r"\b("
    r"diddy|p\.?\s*diddy|puff\s+daddy|puffy|sean\s+(?:[a-z]+\s+)?combs|dirty\s+money"
    r"|r(?:\.\s*|\s+)kelly|robert\s+kelly"
    r"|gary\s+glitter"
    r"|morgan\s+wallen"
    r"|jason\s+aldean"
    r")\b",
    re.IGNORECASE,
)

BANNED_TITLE_RE = re.compile(
    r"\b("
    r"diddy|p\.?\s*diddy|puff\s+daddy|sean\s+(?:[a-z]+\s+)?combs"
    r"|r(?:\.\s*|\s+)kelly|robert\s+kelly"
    r"|gary\s+glitter"
    r"|morgan\s+wallen"
    r"|jason\s+aldean"
    r")\b",
    re.IGNORECASE,
)

# Titles/artists containing "diddy" or "puffy" unrelated to Sean Combs
SAFE_TITLE_SUBSTRINGS = ("do wah diddy", "diddy wah diddy", "bo diddley")
SAFE_ARTIST_SUBSTRINGS = ("puffy amiyumi",)

# Known tracks where featured artist was stripped from playlist display strings
BANNED_TRACK_IDS = {
    "5IZXB5IKAD2qlvTPJYDCFB",  # Post Malone feat. Morgan Wallen - I Had Some Help
    "7221xIgOnuakPdLqT0F3nP",  # Post Malone feat. Morgan Wallen - I Had Some Help (single)
    "2k431Ect1b8BW0oTvHEU5R",  # Method Man & Mary J. Blige - Puff Daddy Mix
    "0UTzRsBvDAghWekcjjJ721",  # Method Man & Mary J. Blige - Puff Daddy Mix Instrumental
}

# Protected group/stage names that contain commas, '&', 'and', or 'x'
PROTECTED_ARTISTS = (
    "earth, wind & fire",
    "tyler, the creator",
    "crosby, stills, nash & young",
    "crosby, stills & nash",
    "blood, sweat & tears",
    "emerson, lake & palmer",
    "peter, paul and mary",
    "10,000 maniacs",
    "lil nas x",
    "chloe x halle",
    "kc and the sunshine band",
    "kc & the sunshine band",
    "kool & the gang",
    "kool and the gang",
    "simon & garfunkel",
    "simon and garfunkel",
    "hall & oates",
    "daryl hall & john oates",
    "daryl hall and john oates",
    "brooks & dunn",
    "dan + shay",
    "macklemore & ryan lewis",
    "tegan and sara",
    "florence + the machine",
    "florence and the machine",
    "hootie & the blowfish",
    "huey lewis & the news",
    "huey lewis and the news",
    "tom petty and the heartbreakers",
    "tom petty & the heartbreakers",
    "prince and the revolution",
    "bob seger & the silver bullet band",
    "bruce springsteen & the e street band",
    "joan jett & the blackhearts",
    "joan jett and the blackhearts",
    "martha and the vandellas",
    "martha & the vandellas",
    "sly & the family stone",
    "sly and the family stone",
    "gladys knight & the pips",
    "gladys knight and the pips",
    "smokey robinson & the miracles",
    "diana ross & the supremes",
    "captain & tennille",
    "sonny & cher",
    "peaches & herbs",
    "sam & dave",
    "england dan & john ford coley",
    "seals & crofts",
    "loggins & messina",
    "bell biv devoe",
    "salt-n-pepa",
    "heavy d & the boyz",
    "dj jazzy jeff & the fresh prince",
    "marky mark and the funky bunch",
    "c+c music factory",
)

SPOTIFY_URI_RE = re.compile(r"^spotify:track:([A-Za-z0-9]{22})$")
SPOTIFY_URL_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z-]+/)?track/([A-Za-z0-9]{22})")
PREVIEW_URL_RE = re.compile(r"^https://p\.scdn\.co/mp3-preview/[0-9a-f]{40}(?:\?[A-Za-z0-9_=&-]+)?$")
IMAGE_URL_RE = re.compile(r"^https://(?:i\.scdn\.co|image-cdn-[a-z0-9-]+\.spotifycdn\.com)/image/([A-Za-z0-9]+)$")


def clean_text(val: Any) -> str:
    """Unescape HTML entities, normalize Unicode dashes/whitespace, and return str."""
    s = html.unescape(str(val if val is not None else ""))
    s = s.replace("\u00a0", " ").replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", s).strip()


def is_banned_entry(title: str, artist: str, track_link: str = "") -> bool:
    """Return True if a song matches the 5-artist exclusion list by artist, title, or track ID."""
    uri = normalize_spotify_uri(track_link) if track_link else ""
    if uri:
        tid = uri.split(":")[-1]
        if tid in BANNED_TRACK_IDS:
            return True
    al = (artist or "").lower()
    if BANNED_ARTIST_RE.search(artist or "") and not any(safe in al for safe in SAFE_ARTIST_SUBSTRINGS):
        return True
    tl = (title or "").lower()
    if BANNED_TITLE_RE.search(title or "") and not any(safe in tl for safe in SAFE_TITLE_SUBSTRINGS):
        return True
    return False


def normalize_spotify_uri(raw: str) -> str:
    """Convert any Spotify track URL or URI into canonical 'spotify:track:<22-char-id>', or ''."""
    if not raw:
        return ""
    s = str(raw).strip().replace("\\/", "/")
    m = SPOTIFY_URI_RE.match(s)
    if m:
        return f"spotify:track:{m.group(1)}"
    m = SPOTIFY_URL_RE.search(s)
    if m:
        return f"spotify:track:{m.group(1)}"
    if re.fullmatch(r"[A-Za-z0-9]{22}", s):
        return f"spotify:track:{s}"
    return ""


def clean_preview_url(raw: str) -> str:
    """Normalize a Spotify 30s MP3 preview URL (stripping optional ?cid=... query), or ''."""
    if not raw:
        return ""
    s = str(raw).strip().replace("\\/", "/")
    if not PREVIEW_URL_RE.match(s):
        return ""
    return s.split("?")[0]


def clean_image_url(raw: str) -> str:
    """Normalize any Spotify CDN cover URL to canonical 'https://i.scdn.co/image/<id>'."""
    if not raw:
        return ""
    s = str(raw).strip().replace("\\/", "/").split("?")[0]
    m = IMAGE_URL_RE.match(s)
    if m:
        return f"https://i.scdn.co/image/{m.group(1)}"
    return ""


def strip_accents(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    without = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", without)


def _alnum_unicode(s: str) -> str:
    return "".join(ch for ch in s if ch.isalnum())


def normalize_artist_token(artist: str) -> str:
    """Normalize a single artist name while preserving Unicode letters/digits."""
    a = strip_accents(clean_text(artist)).lower()
    a = a.replace("$", "s").replace("p!nk", "pink")
    a = re.sub(r"^the\s+", "", a)
    return _alnum_unicode(a)


def extract_primary_artist(artist: str) -> str:
    """Extract normalized primary artist token without breaking protected band/stage names."""
    a = strip_accents(clean_text(artist)).lower()
    a = a.replace("$", "s").replace("p!nk", "pink")
    # Strip explicit featuring/duet suffixes first
    a_lead = re.split(r"\s+(?:featuring|feat\.?|ft\.?|duet with)\s+", a, maxsplit=1)[0].strip()
    for prot in PROTECTED_ARTISTS:
        if a_lead == prot or a_lead.startswith(prot + ",") or a_lead.startswith(prot + " "):
            return _alnum_unicode(re.sub(r"^the\s+", "", prot))
    a_primary = re.split(r"\s+(?:with|and|&|\+)\s+|,\s*", a_lead, maxsplit=1)[0]
    a_primary = re.sub(r"^the\s+", "", a_primary)
    return _alnum_unicode(a_primary)


def normalize_title_token(title: str) -> str:
    """Normalize a song title, stripping only audio-mastering tags (preserving Taylor's Version / Remix)."""
    t = strip_accents(clean_text(title)).lower()
    # Strip pure mastering/soundtrack parentheticals, NEVER Taylor's Version / 10 Minute Version / Remix
    t = re.sub(
        r"\s*[\(\[][^)\]]*(?:remaster(?:ed)?|mono|stereo|radio edit|single edit|album version|single version|lp version|from\s+\")[^)\]]*[\)\]]",
        "",
        t,
    )
    t = re.sub(
        r"\s+-\s+(?:\d{4}\s+)?(?:remaster(?:ed)?|mono|stereo|radio edit|single edit|album version|single version|lp version).*$",
        "",
        t,
    )
    return _alnum_unicode(t)


@functools.lru_cache(maxsize=65536)
def normalize_match_key(title: str, artist: str) -> tuple[str, str]:
    """Normalized (title, primary_artist) key for deduplication and fuzzy cache lookups."""
    return normalize_title_token(title), extract_primary_artist(artist)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def atomic_write_json(path: Path, data: Any, indent: int = 4) -> None:
    """Atomically write pretty-printed UTF-8 JSON preserving file permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = (path.stat().st_mode & 0o777) if path.exists() else 0o644
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
