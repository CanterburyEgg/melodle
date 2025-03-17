import wikipedia
import requests
from bs4 import BeautifulSoup as bs4
import os
import json

def get_release_date_from_infobox(page_title):
	url = f"https://en.wikipedia.org/wiki/{page_title}"
	response = requests.get(url)
	response.raise_for_status()

	soup = bs4(response.content, 'html.parser')
	infobox = soup.find('table', {'class': 'infobox'})

	release_date = None

	if infobox:
		for row in infobox.find_all('tr'):
			header = row.find('th')
			cells = row.find_all('td')
			if header and cells and 'elease' in header.get_text(strip=True): # Release / released / release date ...
				release_date = cells[0].get_text(strip=True)

	return release_date

if __name__ == '__main__':
	with open(os.path.join('jsons','song_names_artists.json')) as f:
		song_data = json.load(f)

	for song in song_data['songs']:
		try:
			sr = wikipedia.search(song, results=5)

			while True:
				for x in range(0, len(sr)):
					title = sr[x]
					release_date = get_release_date_from_infobox(title)
					if release_date is not None:
						break
				break

			print('{0}: {1}'.format(song, release_date))
		except:
			continue