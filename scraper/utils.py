"""Build a scraper to extract HLTV data"""

import selenium
import time, json
from tqdm import tqdm
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException

def make_driver():
    options = Options()
    options.add_argument("--headless")
    driver = Firefox(options=options)
    return driver

def exportJson(data: list, year: int):
    data_to_export = {
        str(year): data
    }
    with open(f"{year}.json", "w") as jsonFile:
        json.dump(data_to_export, jsonFile, indent=4)

    print(f"Json file {year} exported.")

def hltvmatchIDs(driver: selenium, url: str):
    """
    Scrape the match IDs from a page.
    """
    ids = []
    while True:
        driver.get(url)
        time.sleep(2.5)
        matchids = driver.find_element(By.CSS_SELECTOR, "div[class='results-all']").find_elements(By.CSS_SELECTOR, "div[class='result-con']")
        for match in matchids:
            href = match.find_element(By.CSS_SELECTOR, "a[class='a-reset']").get_attribute("href")
            ids.append(href.strip())
        try:
            next_page = driver.find_element(By.CSS_SELECTOR, "a[class='pagination-next ']")
            url = next_page.get_attribute("href")
            print(url)
        except NoSuchElementException:
            return ids

def mapExtract(tags: selenium):
    """Extracts the maps removed and picked"""
    # Loop through tags
    mapInformation = {}
    pick_n = 1
    remove_n = 1
    for tag in tags:
        splits = tag.text.replace(".", "").split(" ")
        pick = splits[2]
        action = f"{splits[1]} - {splits[-1]}"
        if pick == "removed":
            mapInformation[f"Map {remove_n} Removed"] = action
            remove_n += 1
        if pick == "picked":
            mapInformation[f"Map {pick_n} Picked"] = action
            pick_n += 1
        if "was" in splits:
            mapInformation["Map Left Over"] = splits[1]
    return mapInformation

def deatiledStats(urls: list):
    statlinks = []
    for url in tqdm(urls):
        driver = make_driver()
        driver.get(url)
        # time.sleep(1.0)
        try:
            detailedStats = driver.find_element(By.LINK_TEXT, "Detailed stats").get_attribute("href")
            statlinks.append(detailedStats)
        except NoSuchElementException:
            pass
        driver.quit()
    return statlinks

def hltvmatchDetails(driver: selenium, matches: list):
    """Scrape info on past matches"""
    matchInfos = []
    for match in tqdm(matches):
        matchDict = {}
        driver.get(match)
        time.sleep(1.5)
        team1 = driver.find_element(By.CSS_SELECTOR, "div[class='team1-gradient']")
        team2 = driver.find_element(By.CSS_SELECTOR, "div[class='team2-gradient']")
        eventDetails = driver.find_element(By.CSS_SELECTOR, "div[class='timeAndEvent']")

        team1Name = team1.find_element(By.CSS_SELECTOR, "div[class='teamName']").text.strip()
        team2Name = team2.find_element(By.CSS_SELECTOR, "div[class='teamName']").text.strip()

        try:
            team1Score = team1.find_element(By.CSS_SELECTOR, "div[class='won']").text.strip()
            team2Score = team2.find_element(By.CSS_SELECTOR, "div[class='lost']").text.strip()
        except NoSuchElementException:
            team1Score = team1.find_element(By.CSS_SELECTOR, "div[class='lost']").text.strip()
            team2Score = team2.find_element(By.CSS_SELECTOR, "div[class='won']").text.strip()

        eventTime, date, event, status = eventDetails.find_element(By.CLASS_NAME, "time").text.strip(),\
                                    eventDetails.find_element(By.CLASS_NAME, "date").text.strip(),\
                                    eventDetails.find_element(By.CSS_SELECTOR, ".event.text-ellipsis").text.strip(),\
                                    eventDetails.find_element(By.CLASS_NAME, "countdown").text.strip().title(),
        detailedStats = driver.find_element(By.LINK_TEXT, "Detailed stats").get_attribute("href")
        mapsBox = driver.find_element(By.CSS_SELECTOR, "div[class='padding']")
        mapTags = mapsBox.find_elements(By.TAG_NAME, "div")
        matchDict["Team 1"] = team1Name
        matchDict["Team 2"] = team2Name
        matchDict["Team 1 Score"] = team1Score
        matchDict["Team 2 Score"] = team2Score
        matchDict["Date"] = date
        matchDict["Time"] = eventTime
        matchDict["Event"] = event
        matchDict["Status"] = status
        matchDict["Detailed Statistics"] = detailedStats
        matchInfos.append(matchDict)
    return matchInfos

def hltvplayerData(driver: selenium, url: str):
    """Scrape all players"""
    while True:
        driver.get(url)
        time.sleep(1.5)
        players = driver.find_elements(By.CSS_SELECTOR, "a[class='standard-box players-archive-box a-reset text-ellipsis']")
        for player in players:
            playerUrl = player.get_attribute("href")
            gameName = player.find_element(By.CSS_SELECTOR, "div[class='players-archive-nickname text-ellipsis']").text.strip()
            realName = player.find_element(By.CSS_SELECTOR, "div[class='players-archive-name text-ellipsis']").text.strip()
            country = player.find_element(By.CSS_SELECTOR, "div[class='players-archive-country']").text.strip()
            print(playerUrl, gameName, realName, country)
        try:
            nextPage = driver.find_element(By.LINK_TEXT, "Next").get_attribute("href")
            url = nextPage
            print("Next Page.")
        except NoSuchElementException:
            print("No More Pages.")
            break

def hltvplayerStats(driver: selenium, url: str):
    driver.get(url)
    time.sleep(1.5)

    # Extract event and date info from the match info box
    gameInfo = driver.find_element(By.CSS_SELECTOR, "div[class='match-info-box']")
    event = gameInfo.find_element(By.CSS_SELECTOR, "a[class='block text-ellipsis']").text.strip()
    date = gameInfo.find_element(By.CSS_SELECTOR, "span[data-time-format='yyyy-MM-dd HH:mm']").text.strip()

    # Get the map URLs for the match (if available)
    individualMaps = [link.get_attribute("href") for link in driver.find_elements(By.CSS_SELECTOR, "a[class='col stats-match-map standard-box a-reset inactive']")]

    players_data = []  # This will store all player data

    def process_map(mapName, statTables):
        # Iterate over both teams (team 0 and team 1)
        for t, o in [(0, 1), (1, 0)]:
            teammates = [row.find_element(By.CSS_SELECTOR, "td.st-player a").text for row in statTables[t].find_elements(By.CSS_SELECTOR, "tbody tr")]
            opponents = [row.find_element(By.CSS_SELECTOR, "td.st-player a").text for row in statTables[o].find_elements(By.CSS_SELECTOR, "tbody tr")]

            # Team name
            team_name = statTables[t].find_element(By.CSS_SELECTOR, ".st-teamname.text-ellipsis").text

            # Process each player in the team's stats table
            for row in statTables[t].find_elements(By.CSS_SELECTOR, "tbody tr"):
                player = {
                    "Event": event,
                    "Date": date,
                    "Map": mapName,
                    "Team": team_name,
                    "Name": row.find_element(By.CSS_SELECTOR, "td.st-player a").text,
                    "Kills": row.find_element(By.CSS_SELECTOR, "td.st-kills").text.split(' ')[0],
                    "Headshots": row.find_element(By.CSS_SELECTOR, "td.st-kills span.gtSmartphone-only").text.strip('()'),
                    "Assists": row.find_elements(By.TAG_NAME, "td")[2].text.split(' ')[0],
                    "Deaths": row.find_elements(By.TAG_NAME, "td")[3].text,
                    "Kast": row.find_elements(By.TAG_NAME, "td")[4].text,
                    "K-D Diff": row.find_elements(By.TAG_NAME, "td")[5].text,
                    "ADR": row.find_elements(By.TAG_NAME, "td")[6].text,
                    "FK Diff": row.find_elements(By.TAG_NAME, "td")[7].text,
                    "Rating": row.find_elements(By.TAG_NAME, "td")[8].text,
                }

                # Append teammates (excluding the player himself/herself)
                for idx, teammate in enumerate(teammates):
                    if teammate != player['Name']:
                        player[f"Teammate {idx + 1}"] = teammate

                # Append opponents
                for idx, opponent in enumerate(opponents):
                    player[f"Opponent {idx + 1}"] = opponent

                # Add player data to the list
                players_data.append(player)

    # Process case for single map (no individual maps)
    if len(individualMaps) == 0:
        mapName = gameInfo.text.split("Map")[1].strip().split("\n")[0]
        statTables = driver.find_elements(By.CSS_SELECTOR, "table[class='stats-table totalstats ']")
        process_map(mapName, statTables)
    # Process case for multiple maps
    else:
        for map_url in individualMaps:
            driver.get(map_url)
            time.sleep(1.5)
            # Get the map name and the stat tables
            mapInfo = driver.find_element(By.CSS_SELECTOR, "a[class='col stats-match-map standard-box a-reset']")
            mapName = mapInfo.find_element(By.CSS_SELECTOR, "div[class='stats-match-map-result-mapname dynamic-map-name-full']").text.strip()
            statTables = driver.find_elements(By.CSS_SELECTOR, "table[class='stats-table totalstats ']")
            process_map(mapName, statTables)
    return players_data