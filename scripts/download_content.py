import json
import os
import requests

with open(os.path.join('jsons', 'data', 'top_10s_data.json')) as f:
	data = json.load(f)

for song in data:
	name = (str(song['title']) + ' - ' + str(song['artist'])).replace('/', '+')

	if 'picture' in song.keys() and not os.path.isfile(os.path.join('data', 'audio', name + '.mp3')):
		audio = requests.get(song['link'])
		with open(os.path.join('data', 'audio', name + '.mp3'), 'wb') as f:
			f.write(audio.content)

		image = requests.get(song['picture'])
		with open(os.path.join('data', 'img', name + '.jpg'), 'wb') as f:
			f.write(image.content)

		print(name + ' content written.')