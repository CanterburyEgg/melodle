import json
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

for file in sorted(os.listdir(script_dir)):
    filepath = os.path.join(script_dir, file)
    if not os.path.isfile(filepath) or not file.lower().endswith(".json"):
        continue
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            file_json = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Skipping invalid JSON {file}: {exc}")
        continue
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(file_json, f, indent=4, ensure_ascii=False)
