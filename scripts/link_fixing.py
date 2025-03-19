import json
import os
import re

with open(os.path.join('jsons', 'top_10s_data.json')) as f:
	link_data = json.load(f)

with open(os.path.join('jsons', 'all_songs.json')) as f:
	song_data = json.load(f)

link_dump = ''

'''
for song in song_data:
	link_dump += song['preview'] + '\n'

with open(os.path.join('jsons', 'link_dump.txt'), 'w') as f:
	f.write(link_dump)
'''

for link in link_data:
	# fixes for individual artists
	if ("Taylor's Version" in str(link['title'])):
		link_dump += link['link'] + '\n'
		continue

	if ("Drift Away" == link['title']):
		link_dump += link['link'] + '\n'
		continue

	if ("I Need A Girl" in str(link['title'])):
		link_dump += link['link'] + '\n'
		continue

	# end fixes for individual artists

	for song in song_data:
		link_title = str(link['title'])[:str(link['title']).index(' (')] if ' (' in str(link['title']) else str(link['title'])
		song_title = str(song['title'])[:str(song['title']).index(' (')] if ' (' in str(song['title']) else str(song['title'])

		link_artist = str(link['artist'])[:str(link['artist']).index(',')] if ',' in str(link['artist']) else str(link['artist'])
		song_artist = str(song['artist'])[:str(song['artist']).index(',')] if ',' in str(song['artist']) else str(song['artist'])
		
		link_artist = link_artist.replace('.', '')
		song_artist = song_artist.replace('.', '')

		# fixes for individual artists
		link_artist.replace('Ricky', 'Rick')
		song_artist.replace('Ricky', 'Rick')

		if ("Taylor's Version" in str(song['title'])):
			continue

		if ("Drift Away" == song['title']):
			continue

		if ("I Need A Girl" in str(song['title'])):
			continue

		# end fixes for individual artists

		if link['title'] == '(God Must Have Spent) A Little More Time On You' and song['title'] == '(God Must Have Spent) A Little More Time On You':
			print('{0} {1} {2} {3}'.format(link['title'].lower(), song['title'].lower(), link_artist.lower(), song_artist.lower()))

		if str(link_title).lower() == str(song_title).lower() and (link_artist.lower() in song['artist'].lower().replace('.','') or song_artist.lower() in link['artist'].lower().replace('.','')):
			link['link'] = song['preview']
			break
	link_dump += link['link'] + '\n'

with open(os.path.join('jsons', 'top_10s_data.json'), 'w') as f:
	json.dump(link_data, f, indent = 4)

with open(os.path.join('jsons', 'link_dump.txt'), 'w') as f:
	f.write(link_dump)
