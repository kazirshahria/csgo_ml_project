"""Build a scraper to extract HLTV data"""
import requests
import selenium
import time, json, string
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime
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

def detailedStats(urls: list):
    statlinks = []
    driver = make_driver()
    counter = 0
    for url in tqdm(urls):
        driver.get(url)
        try:
            detailedStats = driver.find_element(By.LINK_TEXT, "Detailed stats").get_attribute("href")
            statlinks.append(detailedStats)
        except NoSuchElementException:
            pass
        counter += 1
        if counter == 100:
            driver.quit()
            counter = 0
            driver = make_driver()
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

def hltvplayerData(driver: selenium):
    """Scrape all players"""
    players_data = []
    for letter in list(string.ascii_uppercase) + ["numbers"]:
        url = f"https://www.hltv.org/players/{letter}"
        while True:
            driver.get(url)
            players = driver.find_elements(By.CSS_SELECTOR, "a[class='standard-box players-archive-box a-reset text-ellipsis']")
            for player in players:
                playerUrl = player.get_attribute("href")
                gameName = player.find_element(By.CSS_SELECTOR, "div[class='players-archive-nickname text-ellipsis']").text.strip()
                realName = player.find_element(By.CSS_SELECTOR, "div[class='players-archive-name text-ellipsis']").text.strip()
                country = player.find_element(By.CSS_SELECTOR, "div[class='players-archive-country']").text.strip()
                players_data.append(
                    {
                        "Gamer Name": gameName,
                        "Real Name": realName,
                        "Country": country,
                        "URL": playerUrl
                    }
                )
            try:
                nextPage = driver.find_element(By.LINK_TEXT, "Next").get_attribute("href")
                url = nextPage
                print("Next Page.")
            except NoSuchElementException:
                print("No More Pages.")
                break
    df = pd.DataFrame(players_data)
    df.to_csv("Players.csv", encoding="utf-8-sig")

def hltvplayerStats(driver: selenium, url: str):
    driver.get(url)
    time.sleep(1.0)

    # Extract event and date info from the match info box
    gameInfo = driver.find_element(By.CSS_SELECTOR, "div[class='match-info-box']")
    event = gameInfo.find_element(By.CSS_SELECTOR, "a[class='block text-ellipsis']").text.strip()
    date = gameInfo.find_element(By.CSS_SELECTOR, "span[data-time-format='yyyy-MM-dd HH:mm']").text.strip()

    # Get the map URLs for the match (if available)
    individualMaps = [link.get_attribute("href") for link in driver.find_elements(By.CSS_SELECTOR, "a[class='col stats-match-map standard-box a-reset inactive']")]

    players_data = []  # This will store all player data

    def process_map(mapName, statTables, map_num):
        # Iterate over both teams (team 0 and team 1)
        for t, o in [(0, 1), (1, 0)]:
            teammates = [row.find_element(By.CSS_SELECTOR, "td.st-player a").text for row in statTables[t].find_elements(By.CSS_SELECTOR, "tbody tr")]
            opponents = [row.find_element(By.CSS_SELECTOR, "td.st-player a").text for row in statTables[o].find_elements(By.CSS_SELECTOR, "tbody tr")]

            # Team name
            team_name = statTables[t].find_element(By.CSS_SELECTOR, ".st-teamname.text-ellipsis").text

            # Get both teams and their scores
            gameInfo = driver.find_element(By.CSS_SELECTOR, "div[class='match-info-box']")
            left_team_name = gameInfo.find_element(By.CSS_SELECTOR, "div.team-left a").text.strip()
            left_team_score = int(gameInfo.find_element(By.CSS_SELECTOR, "div.team-left div.bold").text.strip())
            right_team_score = int(gameInfo.find_element(By.CSS_SELECTOR, "div.team-right div.bold").text.strip())

            # Process each player in the team's stats table
            for row in statTables[t].find_elements(By.CSS_SELECTOR, "tbody tr"):
                # Assign the correct scores based on team name
                if team_name == left_team_name:
                    team_score = left_team_score
                    opp_score = right_team_score
                else:
                    team_score = right_team_score
                    opp_score = left_team_score

                player = {
                    "Event": event,
                    "Date": date,
                    "Map": mapName,
                    "Map Number": map_num,
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
                    "Team Score": team_score,
                    "Opponent Score": opp_score
                }

                # Append teammates (excluding the player himself/herself)
                idx = 0
                for teammate in teammates:
                    if teammate != player['Name']:
                        player[f"Teammate {idx + 1}"] = teammate
                        idx += 1

                # Append opponents
                for idx, opponent in enumerate(opponents):
                    player[f"Opponent {idx + 1}"] = opponent

                # Add player data to the list
                players_data.append(player)

    # Process case for single map (no individual maps)
    if len(individualMaps) == 0:
        mapName = gameInfo.text.split("Map")[1].strip().split("\n")[0]
        statTables = driver.find_elements(By.CSS_SELECTOR, "table[class='stats-table totalstats ']")
        process_map(mapName, statTables, "Single Map")
    # Process case for multiple maps
    else:
        for map_num, map_url in enumerate(individualMaps):
            driver.get(map_url)
            time.sleep(1.0)
            # Get the map name and the stat tables
            mapInfo = driver.find_element(By.CSS_SELECTOR, "a[class='col stats-match-map standard-box a-reset']")
            mapName = mapInfo.find_element(By.CSS_SELECTOR, "div[class='stats-match-map-result-mapname dynamic-map-name-full']").text.strip()
            statTables = driver.find_elements(By.CSS_SELECTOR, "table[class='stats-table totalstats ']")
            process_map(mapName, statTables, map_num+1)
    return players_data

def hltvTop(driver: selenium, query: str):
    # Years
    years = list(range(2020, 2025))
    # Scrape urls
    for year in years:
        url = f"https://www.hltv.org/stats/{query}?startDate={year}-01-01&endDate={year}-12-31"
        driver.get(url)
        if query == "teams":
            class_name = 'teamCol-teams-overview'
        else:
            class_name = 'playerCol '
        players = driver.find_elements(By.CSS_SELECTOR, f"td[class='{class_name}']")
        players_lis = []
        for player in players:
            players_lis.append(player.text.strip())
        # Export the data
        exportJson(players_lis, year)
    driver.close()

def prizepicks():
    # Make a query to the cod url
    pp_cod_url = "https://partner-api.prizepicks.com/projections?league_id=265"
    res = requests.get(pp_cod_url).json()
    # Append to the player list
    player_names_lis = []
    # Get the player names
    for player in res["included"]:
        if player["type"]=="new_player":
            name = player["attributes"]["display_name"].strip()
            if name not in player_names_lis:
                player_names_lis.append(name)
    return player_names_lis

def project_player(player_name_inp: str):
    # The map matcher to handle the filter
    maps_mapper = {
        "Dust2": "de_dust2",
        "Nuke": "de_nuke",
        "Ancient": "de_ancient",
        "Inferno": "de_inferno",
        "Mirage": "de_mirage",
        "Anubis": "de_anubis",
        "Vertigo": "de_vertigo"
    }
    # Create the driver to scrape the required information for the model
    driver = make_driver()
    driver_2 = make_driver()
    # Open the excel file with the player names
    players_df = pd.read_csv("Players.csv").to_dict(orient="records")
    model_lis = []
    # Model features
    model = {
        'April': 0, 'August': 0, 'December': 0, 'February': 0, 'January': 0,
        'July': 0, 'June': 0, 'March': 0, 'May': 0, 'November': 0,
        'October': 0, 'September': 0, 'Ancient': 0, 'Anubis': 0, 'Dust2': 0, 'Inferno': 0,
        'Mirage': 0, 'Nuke': 0, 'Vertigo': 0, 'Team': "", 'Opponent Team': "",
        'Name': "", 'Teammate 1': "", 'Teammate 2': "", 'Teammate 3': "",
        'Teammate 4': "", 'Opponent 1': "", 'Opponent 2': "",
        'Opponent 3': "", 'Opponent 4': "", 'Opponent 5': "",
        'Kills': 0, 'Headshots': 0, 'Assists': 0,
        'Deaths': 0, 'Kast': 0, 'K-D Diff': 0, 'ADR': 0,
        'FK Diff': 0, 'Rating': 0
    }
    for player_df in players_df:
        if player_df["Gamer Name"]==player_name_inp:
            # Find the next games and then use Selenium to make a query to get the data
            match_box = player_df["URL"] + "#tab-matchesBox"
            driver.get(match_box)
            nextGame_url = driver.find_element(By.CSS_SELECTOR, "a[class='matchpage-button']").get_attribute("href")
            # Player team
            player_team = driver.find_element(By.CSS_SELECTOR, "div[class='playerInfoRow playerTeam']").find_element(By.CSS_SELECTOR, "span[itemprop='text']").text
            # Date
            game_date = driver.find_element(By.CSS_SELECTOR, "td[class='date-cell']").text
            game_date = datetime.strptime(game_date, '%d/%m/%Y')
            # Month
            month = game_date.strftime('%B')
            model[month] = 1
            # Year
            # year = game_date.strftime('%Y')
            # model[year] = 1
            # Query the next game and scrape info for the ML model
            driver.get(nextGame_url)
            # Lineups
            lineups = driver.find_element(By.CSS_SELECTOR, "div[class='lineups']")
            team_lineups = lineups.find_elements(By.CSS_SELECTOR, "div[class='lineup standard-box']")
            # Iterate through both team objects
            for team_lineup in team_lineups:
                i = 1
                team = team_lineup.find_element(By.CSS_SELECTOR, "div[class='flex-align-center']").text
                players = team_lineup.find_elements(By.CSS_SELECTOR, "td[class='player']")
                # Teammates
                if team == player_team:
                    # First add the player and team
                    model["Team"] = team
                    model["Name"] = player_name_inp
                    for team_player in players:
                        teammate = team_player.text
                        if teammate != player_name_inp:
                            model[f"Teammate {i}"] = teammate
                            i += 1
                # Opponents
                else:
                    model["Opponent Team"] = team
                    for opp_player in players:
                        opp_mate = opp_player.text
                        model[f"Opponent {i}"] = opp_mate
                        i += 1
            # Get the WMA on a map
            weights = np.array([0.25, 0.20, 0.15, 0.125, 0.115, 0.10, 0.05, 0.01])
            # Window size
            window_size = 8
            player_url_split = player_df["URL"].split("/")
            # Create the URL to scrape stats from the games a player played
            matches_url = "https://www.hltv.org/stats/players/matches/" + player_url_split[-2] + "/" + player_url_split[-1]
            # Loop through all the maps and get the stats
            for map_key in tqdm(maps_mapper.keys()):
                model[map_key] = 1
                wma_map = {
                    "Kills": [],
                    "Headshots": [],
                    "Assists": [],
                    "Deaths": [],
                    "Kast": [],
                    "K-D Diff": [],
                    "ADR": [],
                    "FK Diff": [],
                    "Rating": []
                }
                match_history_url = matches_url + f"?maps={maps_mapper[map_key]}"
                # Get all the match history links
                driver.get(match_history_url)
                time.sleep(1)
                # Save up to the window size
                tr_tags = driver.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
                # If there aren't 8 games then go onto the next map
                if len(tr_tags) < window_size:
                    continue
                # Get the stats to calculate the WMA
                for tag in tr_tags[:window_size]:
                    # Find the map link
                    map_link = tag.find_element(By.TAG_NAME, "a").get_attribute("href")
                    driver_2.get(map_link)
                    statTables = driver_2.find_elements(By.CSS_SELECTOR, "table[class='stats-table totalstats ']")
                    # Find the stat table
                    for row in statTables:
                        # Get all the players
                        team_players = row.find_elements(By.CSS_SELECTOR, "tbody tr")
                        for player in team_players:
                            name = player.find_element(By.CSS_SELECTOR, "td.st-player a").text
                            if name == player_name_inp:
                                wma_map["Kills"].append(float(player.find_element(By.CSS_SELECTOR, "td.st-kills").text.split(' ')[0])),
                                wma_map["Headshots"].append(float(player.find_element(By.CSS_SELECTOR, "td.st-kills span.gtSmartphone-only").text.strip('()')))
                                wma_map["Assists"].append(float(player.find_elements(By.TAG_NAME, "td")[2].text.split(' ')[0]))
                                wma_map["Deaths"].append(float(player.find_elements(By.TAG_NAME, "td")[3].text))
                                wma_map["Kast"].append(float(player.find_elements(By.TAG_NAME, "td")[4].text.replace("%", "")))
                                wma_map["K-D Diff"].append(float(player.find_elements(By.TAG_NAME, "td")[5].text))
                                wma_map["ADR"].append(float(player.find_elements(By.TAG_NAME, "td")[6].text.replace("-", "")))
                                wma_map["FK Diff"].append(float(player.find_elements(By.TAG_NAME, "td")[7].text))
                                wma_map["Rating"].append(float(player.find_elements(By.TAG_NAME, "td")[8].text))
                                break
                # Apply the weights to the list
                for wma_key in wma_map.keys():
                    model[wma_key] = np.dot(wma_map[wma_key], weights)
                model_lis.append(model.copy())
                model[map_key] = 0
    return pd.DataFrame(model_lis)
