import json
import os
import re

with open(os.path.join('jsons', 'all_songs.json')) as f:
	js_data = json.load(f)

with open(os.path.join('jsons', 'top-10s.json')) as f:
	t10_data = json.load(f)

t10_data_linked = []

for song in t10_data:
	for data in js_data:
		t10_song_title = str(song['title']).lower().replace('the ', '')
		match = re.search(r"[^a-zA-Z0-9\s]", t10_song_title)
		if match:
			t10_song_title = t10_song_title[:match.start()]
		if t10_song_title.find(' ') > -1:
			t10_song_title = t10_song_title[:t10_song_title.find(' ')]

		t10_song_artist = str(song['artist']).lower().replace('the ', '')
		match = re.search(r"[^a-zA-Z0-9\s]", t10_song_artist)
		if match:
			t10_song_artist = t10_song_artist[:match.start()]
		if t10_song_artist.find(' ') > -1:
			t10_song_artist = t10_song_artist[:t10_song_artist.find(' ')]

		data_song_title = str(data['title']).lower()
		data_song_artist = str(data['artist']).lower()

		#if 'stay' == t10_song_title:
			#print(f'{1} {2} {3} {4}', t10_song_title, data_song_title, t10_song_artist, data_song_artist)

		if t10_song_title in data_song_title and t10_song_artist in data_song_artist:
			song['link'] = data['preview']
	t10_data_linked.append(song)
	if 'link' in song:
		print(str(song['date']) + ': ' + str(song['title']) + ' link added.')
	else:
		print('ERROR: link not found for ' + str(song['title']) + '.')

with open(os.path.join('jsons', 'top_10s_linked.json'), 'w') as f:
	json.dump(t10_data_linked, f)

