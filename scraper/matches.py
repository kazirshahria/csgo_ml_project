from utils import *
import json

file = open("./matches/all_matches.json")

urls = json.load(file)

for year in range(2023, 2025):
    stats = deatiledStats(urls=urls[str(year)])
    exportJson(stats, year)
