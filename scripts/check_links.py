import json
import os

with open(os.path.join('jsons', 'top_10s_linked.json')) as f:
	js_data = json.load(f)

songs = []
for song in js_data:
	if not 'link' in song:
		if [ song['title'], song['artist'] ] not in songs:
			print('{1} - {0}'.format(song['title'], song['artist']))
			songs.append([ song['title'], song['artist'] ])