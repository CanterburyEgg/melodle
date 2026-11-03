#!/usr/bin/env python3
"""Fast, zero-network pre-push validator for Melodle's datasets and HTML/JS apps.

Usage:
    python3 scripts/audit_repo.py
    python3 scripts/audit_repo.py --strict-previews
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import (  # noqa: E402
    DATA_DIR,
    GITIGNORED_PLAYLISTS,
    IMAGE_URL_RE,
    JSONS_DIR,
    PREVIEW_URL_RE,
    REPO_ROOT,
    SPOTIFY_URI_RE,
    clean_preview_url,
    is_banned_entry,
)

HTML_FILES = ("index.html", "quiz.html", "billboard.html", "timeline.html")
EXPECTED_DATA_FILES = {"chart_dates.json", "top_10s.json", "top_10s_linked.json", "top_10s_data.json"}
HTML_ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_file_formatting(path: Path, errors: list[str], *, check_entities: bool = True) -> str:
    rel = path.relative_to(REPO_ROOT)
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"{rel}: contains UTF-8 BOM")
    if b"\r" in raw:
        errors.append(f"{rel}: expected LF line endings, found CR")
    if not raw.endswith(b"\n"):
        errors.append(f"{rel}: missing trailing newline")
    text = raw.decode("utf-8")
    if check_entities and HTML_ENTITY_RE.search(text):
        errors.append(f"{rel}: contains unescaped HTML entity ({HTML_ENTITY_RE.search(text).group(0)})")
    return text


def audit_playlists(errors: list[str]) -> int:
    ntj_path = JSONS_DIR / "names-to-jsons.txt"
    ntj_text = check_file_formatting(ntj_path, errors)
    ntj_ids: list[str] = []
    seen_ntj_ids: set[str] = set()

    for line in ntj_text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3 or any(p != p.strip() or not p for p in parts):
            errors.append(f"names-to-jsons.txt: malformed or unstripped line {line!r}")
            continue
        pid = parts[0]
        if pid in seen_ntj_ids:
            errors.append(f"names-to-jsons.txt: duplicate playlist ID {pid!r}")
        seen_ntj_ids.add(pid)
        ntj_ids.append(pid)
        if f"{pid}.json" in GITIGNORED_PLAYLISTS:
            errors.append(f"names-to-jsons.txt: references gitignored playlist {pid}.json (would 404 in prod)")
        if not (JSONS_DIR / f"{pid}.json").exists():
            errors.append(f"names-to-jsons.txt: missing playlist file jsons/{pid}.json")

    if not (JSONS_DIR / "startup-playlist.json").exists():
        errors.append("jsons/startup-playlist.json: missing default playlist required by index.html")

    expected_tracked = {f"{pid}.json" for pid in ntj_ids} | {"startup-playlist.json"}
    actual_tracked = {p.name for p in JSONS_DIR.glob("*.json") if p.name not in GITIGNORED_PLAYLISTS}
    unregistered = actual_tracked - expected_tracked
    if unregistered:
        errors.append(f"jsons/: unregistered JSON file(s) not in names-to-jsons.txt: {sorted(unregistered)}")

    count = 0
    for p in sorted(JSONS_DIR.glob("*.json")):
        if p.name in GITIGNORED_PLAYLISTS:
            continue
        count += 1
        text = check_file_formatting(p, errors)
        entries = json.loads(text)
        is_startup = p.name == "startup-playlist.json"
        expected_keys = {"title", "artist", "trackLink"} if is_startup else {"title", "artist", "trackLink", "preview"}

        seen_uris: set[str] = set()
        seen_previews: set[str] = set()
        seen_names: set[tuple[str, str]] = set()
        for idx, e in enumerate(entries):
            if set(e.keys()) != expected_keys:
                errors.append(f"jsons/{p.name}[{idx}]: keys {set(e.keys())} != {expected_keys}")
                continue
            title, artist, uri = e["title"], e["artist"], e["trackLink"]
            if not isinstance(title, str) or not isinstance(artist, str) or not title or not artist:
                errors.append(f"jsons/{p.name}[{idx}]: invalid title/artist")
            if not SPOTIFY_URI_RE.match(str(uri)):
                errors.append(f"jsons/{p.name}[{idx}]: invalid trackLink {uri!r}")
            if not is_startup:
                prev_str = str(e.get("preview", ""))
                if not PREVIEW_URL_RE.match(prev_str):
                    errors.append(f"jsons/{p.name}[{idx}]: invalid preview {prev_str!r}")
                else:
                    prev_base = clean_preview_url(prev_str)
                    if prev_base in seen_previews:
                        errors.append(f"jsons/{p.name}[{idx}]: duplicate preview audio {prev_base}")
                    seen_previews.add(prev_base)
            if is_banned_entry(title, artist, uri):
                errors.append(f"jsons/{p.name}[{idx}]: banned artist entry {title!r} — {artist!r}")
            if uri in seen_uris:
                errors.append(f"jsons/{p.name}[{idx}]: duplicate URI {uri}")
            seen_uris.add(uri)
            nk = (title.strip().lower(), artist.strip().lower())
            if nk in seen_names:
                errors.append(f"jsons/{p.name}[{idx}]: duplicate song {title!r} — {artist!r}")
            seen_names.add(nk)
    return count


def audit_billboard_and_timeline(errors: list[str], *, strict_previews: bool) -> dict[str, int]:
    actual_data_files = {p.name for p in DATA_DIR.iterdir() if p.is_file() and not p.name.startswith(".")}
    extra = actual_data_files - EXPECTED_DATA_FILES
    missing = EXPECTED_DATA_FILES - actual_data_files
    if extra:
        errors.append(f"jsons/data/: unexpected intermediate/backup files present: {sorted(extra)}")
    if missing:
        errors.append(f"jsons/data/: missing canonical files: {sorted(missing)}")
        return {}

    texts = {fn: check_file_formatting(DATA_DIR / fn, errors) for fn in sorted(EXPECTED_DATA_FILES)}

    dates_obj = json.loads(texts["chart_dates.json"])
    dates = dates_obj.get("dates", [])
    if dates != sorted(set(dates)) or any(not ISO_DATE_RE.match(str(d)) for d in dates):
        errors.append("chart_dates.json: dates are not strictly sorted unique YYYY-MM-DD strings")

    top10 = json.loads(texts["top_10s.json"])
    linked = json.loads(texts["top_10s_linked.json"])
    tdata = json.loads(texts["top_10s_data.json"])

    if len(top10) != len(dates) * 10:
        errors.append(f"top_10s.json: expected {len(dates) * 10} rows, got {len(top10)}")
    if len(linked) != len(dates) * 10:
        errors.append(f"top_10s_linked.json: expected {len(dates) * 10} rows, got {len(linked)}")

    for idx, r in enumerate(top10):
        if set(r.keys()) != {"date", "rank", "title", "artist"}:
            errors.append(f"top_10s.json[{idx}]: unexpected keys {set(r.keys())}")
            break

    t10_tuples = [(r["date"], r["rank"], r["title"], r["artist"]) for r in top10]
    lnk_tuples = [(r["date"], r["rank"], r["title"], r["artist"]) for r in linked]
    if t10_tuples != lnk_tuples:
        errors.append("top_10s.json and top_10s_linked.json row tuples/ordering do not match 1:1")

    by_week: dict[str, list[dict]] = {}
    empty_links = 0
    for idx, r in enumerate(linked):
        if set(r.keys()) != {"date", "rank", "title", "artist", "link"}:
            errors.append(f"top_10s_linked.json[{idx}]: unexpected keys {set(r.keys())}")
            break
        if not r["title"] or not r["artist"]:
            errors.append(f"top_10s_linked.json[{idx}]: empty title/artist")
        by_week.setdefault(r["date"], []).append(r)
        if is_banned_entry(r["title"], r["artist"]):
            errors.append(f"top_10s_linked.json[{idx}]: banned entry {r['title']!r} — {r['artist']!r}")
        lnk = r.get("link", "")
        if not lnk:
            empty_links += 1
            if strict_previews:
                errors.append(f"top_10s_linked.json[{idx}] ({r['date']} #{r['rank']}): empty preview link")
        elif not PREVIEW_URL_RE.match(lnk):
            errors.append(f"top_10s_linked.json[{idx}]: malformed preview link {lnk!r}")

    if set(by_week.keys()) != set(dates):
        orphan = set(by_week.keys()) - set(dates)
        if orphan:
            errors.append(f"top_10s_linked.json: orphan chart dates absent from chart_dates.json: {sorted(orphan)[:5]}")

    for d in dates:
        rows = by_week.get(d, [])
        if len(rows) != 10:
            errors.append(f"top_10s_linked.json ({d}): expected 10 rows, got {len(rows)}")
            continue
        ranks = [r["rank"] for r in rows]
        if ranks != sorted(ranks) or any(not (1 <= rk <= 10) for rk in ranks):
            errors.append(f"top_10s_linked.json ({d}): unsorted or out-of-range ranks {ranks}")
        seen_songs = set()
        seen_links = set()
        for r in rows:
            sk = (r["title"].lower(), r["artist"].lower())
            if sk in seen_songs:
                errors.append(f"top_10s_linked.json ({d}): duplicate song {sk}")
            seen_songs.add(sk)
            if r.get("link"):
                base_lnk = clean_preview_url(r["link"])
                if base_lnk in seen_links:
                    errors.append(f"top_10s_linked.json ({d}): duplicate audio link {base_lnk}")
                seen_links.add(base_lnk)

    max_valid_year = datetime.now().year + 1
    seen_td = set()
    incomplete_td = 0
    for idx, r in enumerate(tdata):
        t, a, yr = r.get("title", ""), r.get("artist", ""), r.get("year", "")
        if not isinstance(t, str) or not isinstance(a, str) or not t or not a:
            errors.append(f"top_10s_data.json[{idx}]: empty or non-string title/artist")
        if not isinstance(yr, str) or not re.fullmatch(r"\d{4}", yr) or not (1950 <= int(yr) <= max_valid_year):
            errors.append(f"top_10s_data.json[{idx}]: invalid 4-digit year {yr!r}")
        if is_banned_entry(t, a):
            errors.append(f"top_10s_data.json[{idx}]: banned entry {t!r} — {a!r}")
        lnk = r.get("link", "")
        pic = r.get("picture", "")
        if not lnk or not pic:
            incomplete_td += 1
            if strict_previews:
                errors.append(f"top_10s_data.json[{idx}] ({t!r}): missing link or picture")
        if lnk and not PREVIEW_URL_RE.match(lnk):
            errors.append(f"top_10s_data.json[{idx}]: malformed link {lnk!r}")
        if pic and not IMAGE_URL_RE.match(pic.split("?")[0]):
            errors.append(f"top_10s_data.json[{idx}]: malformed picture {pic!r}")
        key = (t.lower(), a.lower())
        if key in seen_td:
            errors.append(f"top_10s_data.json[{idx}]: duplicate Timeline entry {key}")
        seen_td.add(key)

    return {
        "weeks": len(dates),
        "chart_rows": len(linked),
        "empty_links": empty_links,
        "timeline_songs": len(tdata),
        "incomplete_timeline": incomplete_td,
    }


def audit_html_files(errors: list[str]) -> None:
    osascript_bin = shutil.which("osascript")
    for name in HTML_FILES:
        path = REPO_ROOT / name
        raw = path.read_bytes()
        if b"\r\n" not in raw or b"\r" in raw.replace(b"\r\n", b"") or b"\n" in raw.replace(b"\r\n", b""):
            errors.append(f"{name}: inconsistent line endings (expected strict CRLF)")
        text = raw.decode("utf-8")
        if not text.lstrip().lower().startswith("<!doctype html>"):
            errors.append(f"{name}: missing <!DOCTYPE html>")
        if osascript_bin:
            scripts = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", text, re.DOTALL)
            for idx, script_body in enumerate(scripts):
                res = subprocess.run(
                    [osascript_bin, "-l", "JavaScript", "-e", f"new Function({json.dumps(script_body)});"],
                    capture_output=True,
                    text=True,
                )
                if res.returncode != 0:
                    errors.append(f"{name} <script>[{idx}] JS syntax error: {res.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate all Melodle JSON datasets and HTML/JS files.")
    parser.add_argument(
        "--strict-previews",
        action="store_true",
        help="Fail if any row in top_10s_linked.json or top_10s_data.json lacks a preview/picture.",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []
    playlist_count = audit_playlists(errors)
    summary = audit_billboard_and_timeline(errors, strict_previews=args.strict_previews)
    audit_html_files(errors)

    if errors:
        print(f"AUDIT FAILED ({len(errors)} issue(s)):", file=sys.stderr)
        for err in errors[:50]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more.", file=sys.stderr)
        return 1

    print(
        f"AUDIT PASSED: {playlist_count} playlists, {summary.get('weeks', 0)} Billboard weeks "
        f"({summary.get('chart_rows', 0)} rows, {summary.get('empty_links', 0)} unlinked), "
        f"{summary.get('timeline_songs', 0)} Timeline songs ({summary.get('incomplete_timeline', 0)} skeleton), "
        f"and {len(HTML_FILES)} HTML apps clean."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
