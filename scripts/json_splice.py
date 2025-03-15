import json
import os

decades = [ '1960', '1970', '1980', '1990', '2000', '2010', '2020' ]
all_songs = []

for decade in decades:
	with open(os.path.join('jsons', decade + 's.json')) as f:
		js_data = json.load(f)
		all_songs += js_data

with open(os.path.join('jsons', 'all_songs.json'), 'w') as f:
	json.dump(all_songs, f)