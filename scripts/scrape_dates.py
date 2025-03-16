import json
import os

with open(os.path.join('jsons', 'top_10s_linked.json')) as f:
	js_data = json.load(f)

chart_dates = []
for song in js_data:
	if song['date'] not in chart_dates:
		chart_dates.append(song['date'])

with open(os.path.join('jsons', 'chart_dates.json'), 'w') as f:
	json.dump({ 'dates': chart_dates }, f)