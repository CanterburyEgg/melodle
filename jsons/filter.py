import json
import os
import sys

script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)

name = sys.argv[1]
filepath = os.path.join(script_dir, name)

with open(filepath, encoding='utf-8-sig') as f:
	file_json = json.load(f)

used = []
for entry in file_json:
	if (entry['title'] + entry['artist']) in used:
		print(entry)
	else:
		used.append(entry['title'] + entry['artist'])

print(len(used))
#with open(filepath, 'w', encoding='utf-8-sig') as f:
#	json.dump(file_json, f, indent=4)