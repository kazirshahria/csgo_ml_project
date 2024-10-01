from utils import *
import pandas as pd
import json

# Import URLs
file = open("./player_stats/all_stats.json")
data = json.load(file)
driver = make_driver()

count = 0
for year in ["2023", "2024"]:
    scraped_lis = []
    urls = data[year]
    for url in tqdm(urls):
        try:
            scraped_data = hltvplayerStats(driver, url)
        except:
            driver.close()
            driver = make_driver()
            continue
        scraped_lis.extend(scraped_data)
        count += 4
        # Avoid Memory Leak
        if 100 <= count:
            driver.quit()
            driver = make_driver()
            count = 0
    # Export the data
    df = pd.DataFrame(scraped_lis)
    df.to_csv(f"{str(year)}.csv", encoding="utf-8-sig")
