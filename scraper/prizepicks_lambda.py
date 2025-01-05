import json
import os
import requests
import json
from datetime import datetime
import mysql.connector

def database_connection_and_cursor(database: str=None) -> tuple:
    """
    Gains connection to the database and cursor

    Params:
        database (str): Name of the database

    Return:
        connection: Database connection
        cursor: Database cursor
    """
    # Connect to the database
    connection = mysql.connector.connect(
        host=os.environ["HOST"],
        user=os.environ["USER"],
        password=os.environ["PASSWORD"],
        database=os.environ["DATABASE"],
        port=3306,
        connection_timeout=800
    )
    # Create a cursor
    cursor = connection.cursor()
    return connection, cursor

def insert_prizepicks_lines_into_database(connection, cursor, data):
    # SQL insert query
    insert_query = """
    INSERT IGNORE INTO prizepicks_lines (id, game_date, game_time, stat_type, player_name, player_team, opp, line_score)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """
    # Insert the records into the database
    cursor.executemany(insert_query, data)
    # Commit the changes into the database
    connection.commit()
    print(f"{cursor.rowcount} rows inserted successfully into 'prizepicks_lines' table.")

def prizepicks_lines(league_id: str="265", insert_into_db: bool=False) -> list:
    """
    Returns the Prizepicks lines for any league

    Params:
        league_id (str): The id for querying a league

    Return:
        data_lis (list): A list of Prizepicks lines
    """
    url = f"https://partner-api.prizepicks.com/projections?league_id={league_id}"
    res = requests.get(url).json()
    # Append to the player list
    player_maps = {}
    # Get the player names
    for player in res["included"]:
        if player["type"]=="new_player":
            id = player["id"]
            name = player["attributes"]["display_name"].strip()
            team = player["attributes"]["team"].strip()
            if id not in player_maps.keys():
                player_maps[id] = {
                    "Name": name,
                    "Team": team
                }
    all_lines = []
    all_lines_db = []
    lines = res["data"]
    for line in lines:
        line_id = line["id"]
        opp = line["attributes"]["description"].replace("MAPS", "MAP").replace("MAP", "MAPS").split("MAPS")[0]
        date = datetime.fromisoformat(line["attributes"]["start_time"])
        player_id = line["relationships"]["new_player"]["data"]["id"]
        line_score = line["attributes"]["line_score"]
        stat_type = line["attributes"]["stat_type"]
        player_info = player_maps[player_id]
        name = player_info["Name"]
        team = player_info["Team"]
        data = {
            "ID": line_id,
            "Game Date": date.date(),
            "Game Time": date.time(),
            "Type": stat_type.replace("MAP 3", "MAPS 3"),
            "Name": name.strip(),
            "Team": team.strip(),
            "Opp": opp.strip(),
            "Line Score": line_score
        }
        all_lines.append(data)
        all_lines_db.append(tuple(data.values()))
    if insert_into_db:
        connection, cursor = database_connection_and_cursor("CSGO")
        insert_prizepicks_lines_into_database(connection, cursor, all_lines_db)
    return all_lines

def lambda_handler():
    # TODO implement
    response = prizepicks_lines(insert_into_db=True)
    if response == True:
        return {
            'statusCode': 200,
            'body': json.dumps('Scraped lines from Prizepicks and updated the database!')
        }

