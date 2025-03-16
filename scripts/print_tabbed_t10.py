import json
import os

with open(os.path.join('jsons', 'top_10s_linked.json')) as f:
	js_data = json.load(f)

song_links = []
for song in js_data:
	song_link = { 'title': song['title'],
				  'artist': song['artist'],
				  'link': song['link'] if 'link' in song else ''
				}
	if song_link not in song_links:
		song_links.append(song_link)

with open(os.path.join('jsons', 'top_10s_links.json'), 'w') as f:
	json.dump(song_links, f)