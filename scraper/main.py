from utils import *
import pandas as pd

gameurl = "https://www.hltv.org/matches/2375857/incontrol-vs-detonate-cct-season-2-north-america-series-3"
matchstats = "https://www.hltv.org/stats/matches/mapstatsid/97751/paradox-vs-ground-zero"
driver = make_driver()

# for year in range(2020, 2025):
#     matchurl = f"https://www.hltv.org/results?offset=0&startDate={year}-01-01&endDate={year}-12-31"
#     ids = hltvmatchIDs(driver, matchurl)
#     exportJson(ids, year)


# hltvplayerData(driver, playerurl)

# data = hltvplayerStats(driver, matchstats)
# print(data)
# df = pd.DataFrame(data)
# df.to_csv("data.csv", index=False)
