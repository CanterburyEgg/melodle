import json
import os
import sys

if len(sys.argv) < 2:
    print("Usage: python3 jsons/filter.py <playlist.json> [--write]")
    sys.exit(1)

script_dir = os.path.dirname(os.path.abspath(__file__))
name = sys.argv[1]
write_changes = "--write" in sys.argv[2:]
filepath = name if os.path.isabs(name) or os.path.exists(name) else os.path.join(script_dir, name)

with open(filepath, "r", encoding="utf-8-sig") as f:
    file_json = json.load(f)

seen_uris = set()
seen_names = set()
cleaned = []

for entry in file_json:
    uri = entry.get("trackLink", "")
    name_key = (str(entry.get("title", "")).strip().lower(), str(entry.get("artist", "")).strip().lower())
    if (uri and uri in seen_uris) or name_key in seen_names:
        print("Duplicate:", entry)
        continue
    if uri:
        seen_uris.add(uri)
    seen_names.add(name_key)
    cleaned.append(entry)

print(f"Unique tracks: {len(cleaned)} of {len(file_json)}")
if write_changes and len(cleaned) != len(file_json):
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cleaned, f, indent=4, ensure_ascii=False)
    print(f"Wrote deduplicated playlist to {filepath}")
