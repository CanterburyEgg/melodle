import json
import os

with open(os.path.join('jsons', 'missing_links.json')) as f:
	js_data = json.load(f)

songs_pruned = []
for song in js_data:
	songs_pruned.append({
			'title': song['title'],
			'artist': song['artist'],
			'preview': song['preview']
		})

with open(os.path.join('jsons', 'missing_links_pruned.json'), 'w') as f:
	json.dump(songs_pruned, f)