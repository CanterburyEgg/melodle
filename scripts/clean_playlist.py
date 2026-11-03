#!/usr/bin/env python3
"""Normalize, deduplicate, filter, and pretty-format Melodle playlist JSON files.

Replaces the legacy `jsons/filter.py` and `jsons/prettify.py` helpers.

Examples:
    python3 scripts/clean_playlist.py --all            # Dry-run check across all tracked playlists
    python3 scripts/clean_playlist.py --all --write    # Clean & format all tracked playlists in place
    python3 scripts/clean_playlist.py my_export.json --write
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import (  # noqa: E402
    GITIGNORED_PLAYLISTS,
    JSONS_DIR,
    PREVIEW_URL_RE,
    atomic_write_json,
    clean_preview_url,
    clean_text,
    is_banned_entry,
    normalize_spotify_uri,
    read_json,
    strip_accents,
)


def resolve_playlist_path(arg: str) -> Path:
    p = Path(arg)
    if p.exists():
        return p.resolve()
    candidate = JSONS_DIR / (arg if arg.endswith(".json") else f"{arg}.json")
    if candidate.exists():
        return candidate.resolve()
    return p


def discover_tracked_playlists() -> list[Path]:
    paths: list[Path] = []
    for p in sorted(JSONS_DIR.glob("*.json")):
        if p.name in GITIGNORED_PLAYLISTS:
            continue
        paths.append(p)
    return paths


def clean_playlist_entries(
    entries: list[dict[str, Any]],
    *,
    is_startup: bool,
    allow_no_preview: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = {
        "input": len(entries),
        "kept": 0,
        "unplayable": 0,
        "banned": 0,
        "duplicates": 0,
    }
    require_preview = not (is_startup or allow_no_preview)
    seen_uris: set[str] = set()
    seen_previews: set[str] = set()
    seen_names: set[tuple[str, str]] = set()
    cleaned: list[dict[str, Any]] = []

    for raw in entries:
        if not isinstance(raw, dict):
            stats["unplayable"] += 1
            continue

        title = clean_text(raw.get("title", ""))
        artist = clean_text(raw.get("artist", ""))
        uri = normalize_spotify_uri(raw.get("trackLink", "") or raw.get("id", ""))

        preview_raw = str(raw.get("preview") or "").strip().replace("\\/", "/")
        preview_base = clean_preview_url(preview_raw)
        preview_out = preview_raw if (preview_base and PREVIEW_URL_RE.match(preview_raw)) else preview_base

        if not title or not artist or not uri:
            stats["unplayable"] += 1
            continue
        if require_preview and not preview_base:
            stats["unplayable"] += 1
            continue

        if is_banned_entry(title, artist, uri):
            stats["banned"] += 1
            continue

        name_key = (
            strip_accents(title).lower(),
            strip_accents(artist).lower(),
        )
        if uri in seen_uris or name_key in seen_names or (not is_startup and preview_base and preview_base in seen_previews):
            stats["duplicates"] += 1
            continue

        seen_uris.add(uri)
        seen_names.add(name_key)
        if not is_startup and preview_base:
            seen_previews.add(preview_base)

        if is_startup:
            cleaned.append({
                "title": title,
                "artist": artist,
                "trackLink": uri,
            })
        else:
            cleaned.append({
                "title": title,
                "artist": artist,
                "trackLink": uri,
                "preview": preview_out,
            })

    stats["kept"] = len(cleaned)
    return cleaned, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean, deduplicate, and format Melodle playlist JSONs.")
    parser.add_argument("files", nargs="*", help="Playlist JSON path(s) or name(s) in jsons/.")
    parser.add_argument("--all", action="store_true", help="Process all tracked playlists in jsons/*.json.")
    parser.add_argument("--write", action="store_true", help="Write cleaned/formatted JSON back to disk.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any playlist would change when cleaned.",
    )
    parser.add_argument(
        "--allow-no-preview",
        action="store_true",
        help="Allow custom playlist entries without a 30s MP3 preview (emits preview: '').",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    if args.all:
        targets.extend(discover_tracked_playlists())
    for f in args.files:
        targets.append(resolve_playlist_path(f))

    if not targets:
        parser.print_help()
        return 1

    exit_code = 0
    for path in targets:
        if not path.exists():
            print(f"[ERROR] File not found: {path}", file=sys.stderr)
            exit_code = 1
            continue
        try:
            data = read_json(path)
        except (ValueError, UnicodeDecodeError) as exc:
            print(f"[ERROR] Invalid JSON/UTF-8 in {path.name}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        # Support Soundiiz object exports {"name": "...", "tracks": [...]}
        unwrapped_dict = False
        if isinstance(data, dict) and isinstance(data.get("tracks"), list):
            data = data["tracks"]
            unwrapped_dict = True

        if not isinstance(data, list):
            print(f"[ERROR] Expected JSON array in {path.name}, got {type(data).__name__}", file=sys.stderr)
            exit_code = 1
            continue

        is_startup = path.name == "startup-playlist.json"
        cleaned, stats = clean_playlist_entries(
            data,
            is_startup=is_startup,
            allow_no_preview=args.allow_no_preview,
        )
        changed = unwrapped_dict or (cleaned != data)

        status = "CHANGED" if changed else "OK"
        print(
            f"[{status}] {path.name}: {stats['kept']}/{stats['input']} kept "
            f"(dupes={stats['duplicates']}, banned={stats['banned']}, unplayable={stats['unplayable']})"
        )
        if args.write:
            atomic_write_json(path, cleaned)
        elif args.check and changed:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
