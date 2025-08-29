import json
import os

script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)

for file in os.listdir(script_dir):
	filepath = os.path.join(script_dir, file)
	filetype = filepath[filepath.rfind('.') + 1:]
	if filetype == 'json':
		with open(filepath, encoding='utf-8-sig') as f:
			file_json = json.load(f)
		with open(filepath, 'w', encoding='utf-8-sig') as f:
			json.dump(file_json, f, indent=4)