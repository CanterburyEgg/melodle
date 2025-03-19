import json
import sys

def merge_jsons(j1, j2, destination, anchors):
	with open(j1, encoding='utf8') as f:
		json1 = json.load(f)

	with open(j2, encoding='utf8') as f:
		json2 = json.load(f)

	for entry1 in json1:
		for entry2 in json2:
			match = True
			for anchor in anchors:
				if entry1[anchor] != entry2[anchor]:
					match = False
					break
			if match:
				for key in entry2:
					if key not in anchors:
						entry1[key] = entry2[key] # merge json2 into json1
				break

	with open(destination, 'w', encoding='utf8') as f:
		json.dump(json1, f, indent = 4, ensure_ascii = False)

if __name__ == "__main__":
	# usage: python3 merg_jsons.py <json1> <json2> <json_destination> [<anchor1> <anchor2> ...]
	if len(sys.argv) < 5:
		print("Missing arguments. Usage: python3 merg_jsons.py <json1> <json2> <json_destination> [<anchor1> <anchor2> ...]")
	else:
		json1 = sys.argv[1]
		json2 = sys.argv[2]
		json_dest = sys.argv[3]

		anchors = []
		for arg in sys.argv[4:]:
			anchors.append(arg)

		merge_jsons(json1, json2, json_dest, anchors)