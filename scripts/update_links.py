import json
import os
import re

with open(os.path.join('jsons', 'top_10s_links.json')) as f:
	links = json.load(f)

with open(os.path.join('jsons', 'top_10s.json')) as f:
	t10_songs = json.load(f)

t10_data_linked = []

for song in t10_songs:
	song_data = song
	song_data['link'] = ''
	for song_linked in links:
		if song['title'] == song_linked['title'] and song['artist'] == song_linked['artist']:
			song_data['link'] = song_linked['link']
			t10_data_linked.append(song_data)
			break
	t10_data_linked.append(song_data)

with open(os.path.join('jsons', 'top_10s_linked.json'), 'w') as f:
	json.dump(t10_data_linked, f, indent = 4)

