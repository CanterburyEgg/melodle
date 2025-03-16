import json
import os

with open(os.path.join('jsons', 'links_pruned.json')) as f:
	js_data = json.load(f)

for song in js_data:
	print(song['title'] + '\t' + song['artist'] + '\t' + song['preview'])