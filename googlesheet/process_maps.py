import os
import time
import boto3
import pandas as pd
import mysql.connector
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# Connect to the AWS database with all of the HLTV stats
def database_connection_and_cursor(database: str) -> tuple:
    """
    Gains connection to the database and cursor

    Params:
        database (str): Name of the database

    Return:
        connection: Database connection
        cursor: Database cursor
    """
    # Database connection parameters
    host = "csdb.cpweiko20fua.us-east-2.rds.amazonaws.com"
    port = 3306
    user = "admin"
    password = "csgodatabase"

    # Connect to the database
    connection = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        connection_timeout=800
    )

    # Create a cursor
    cursor = connection.cursor()
    return connection, cursor

def total_maps_statistics(df: pd.DataFrame, df2: pd.DataFrame, three_maps: bool=False) -> pd.DataFrame:
    """
    Totals up the statistics on the dataframe and returns a new dataframe

    Params:
        df (pd.DataFrame): The dataframe
        three_maps (bool): If it is three maps

    Returns:
        df (pd.DataFrame): New dataframe
    """
    df = df.copy()
    # Total up the numbers
    stat_columns = ["Kills", "Headshots", "Assists", "Deaths", "Kast", "ADR", "Rating"]
    # If statistics of three maps should be sum
    if three_maps:
        for stat_column in stat_columns:
            idx = df2.columns.get_indexer([stat_column])[0]
            if stat_column in ["Kast", "ADR", "Rating"]:
                df.insert(loc=idx, column=stat_column, value=(df[f"{stat_column} Map 1"] + df[f"{stat_column} Map 2"] + df[f"{stat_column} Map 3"])/3)
            else:
                df.insert(loc=idx, column=stat_column, value=df[f"{stat_column} Map 1"] + df[f"{stat_column} Map 2"] + df[f"{stat_column} Map 3"])
        drop_cols = [f"{stat_column} Map 1" for stat_column in stat_columns] + [f"{stat_column} Map 2" for stat_column in stat_columns] + [f"{stat_column} Map 3" for stat_column in stat_columns]
        df.drop(columns=drop_cols, inplace=True)
        df["Map Number"] = "MAPS 1-3"
        return df
    # Only two maps
    else:
        for stat_column in stat_columns:
            idx = df2.columns.get_indexer([stat_column])[0]
            if stat_column in ["Kast", "ADR", "Rating"]:
                df.insert(loc=idx, column=stat_column, value=(df[f"{stat_column} Map 1"] + df[f"{stat_column} Map 2"])/2)
            else:
                df.insert(loc=idx, column=stat_column, value=df[f"{stat_column} Map 1"] + df[f"{stat_column} Map 2"])
        drop_cols = [f"{stat_column} Map 1" for stat_column in stat_columns] + [f"{stat_column} Map 2" for stat_column in stat_columns]
        df.drop(columns=drop_cols, inplace=True)
        df["Map Number"] = "MAPS 1-2"
        return df

def main_program():
    connection, cursor = database_connection_and_cursor("CSGO")
    print(f"[{datetime.now()}] Connected to database.")
    cursor.execute(
        """SELECT * FROM hltv_stats"""
    )
    cs_data = cursor.fetchall()

    cols = [
        'ID', 'Event', 'Date', 'Map', 'Map Number', 'Team', 'Name',
        'Kills', 'Headshots', 'Assists', 'Deaths', 'Kast', 'K-D Diff',
        'ADR', 'FK Diff', 'Rating', 'Team Score', 'Opponent Score',
        'Teammate 1', 'Teammate 2', 'Teammate 3', 'Teammate 4', 'Opponent 1',
        'Opponent 2', 'Opponent 3', 'Opponent 4', 'Opponent 5', 'Teammate 5',
        'Opponent 6', 'Opponent 7', 'Teammate 6'
    ]
    cs_data = pd.DataFrame(cs_data, columns=cols)
    print(f"[{datetime.now()}] Imported the data to a dataframe.")

    # Convert object statistic columns to float values
    cs_data["Kast"] = cs_data["Kast"].astype("float")
    cs_data["ADR"] = cs_data["ADR"].astype("float")
    cs_data["Rating"] = cs_data["Rating"].astype("float")

    # Unique teams and players
    team_df = cs_data[["Date", "Name", "Team"]].drop_duplicates()
    team_df.reset_index(drop=True, inplace=True)

    # Concat the data
    cs_data = \
    cs_data.merge(
        right=team_df.add_prefix("Opponent "),
        left_on=["Date", "Opponent 1"],
        right_on=["Opponent Date", "Opponent Name"],
        how="left",
    ).drop(columns=["Opponent Date", "Opponent Name"])

    # Opponents
    opponents = cs_data.pop("Opponent Team")

    # Append back to the dataframe
    cs_data.insert(5, "Opponent Team", opponents)

    cs_stats = cs_data.iloc[:, :].query("(Map!='Best of 3') and (Map!='Best of 2') and (Map!= 'All')").reset_index(drop=True)

    # Drop the columns
    cs_stats_f = cs_stats.drop(columns=["ID", "K-D Diff", "FK Diff", "Team Score", "Opponent Score"])

    # Filter the dataset to only MAPS 1, 2, and 3
    cs_stats_f = cs_stats_f.groupby(by=["Event", "Date", "Team", "Opponent Team"]).filter(lambda group: set(group["Map Number"]).issubset({"1", "2", "3"}))
    cs_stats_f.reset_index(drop=True, inplace=True)
        
    # Seperate the Maps to make it easier merge
    map_1 = cs_stats_f[cs_stats_f["Map Number"] == "1"]
    map_2 = cs_stats_f[cs_stats_f["Map Number"] == "2"]
    map_3 = cs_stats_f[cs_stats_f["Map Number"] == "3"]

    # Merge the dataframes to calculate for Maps 1-2
    map_1_and_2 = pd.merge(
        left=map_1,
        right=map_2[
            ["Event", "Date", "Name", "Team", "Opponent Team", "Kills", "Headshots", "Assists", "Deaths", "Kast", "ADR", "Rating"]
            ],
        suffixes = (" Map 1", " Map 2"),
        on=["Event", "Date", "Name", "Team", "Opponent Team"],
    )

    # Merge the dataframe to calculate for Maps 1-3
    map_1_and_2_and_3 = map_1_and_2.merge(
        right=map_3[
            ["Event", "Date", "Name", "Team", "Opponent Team", "Kills", "Headshots", "Assists", "Deaths", "Kast", "ADR", "Rating"]
        ],
        on=["Event", "Date", "Name", "Team", "Opponent Team"],
    ).rename(columns={
        "Kills": "Kills Map 3",
        "Headshots": "Headshots Map 3",
        "Assists": "Assists Map 3",
        "Deaths": "Deaths Map 3",
        "Kast": "Kast Map 3",
        "ADR": "ADR Map 3",
        "Rating": "Rating Map 3"
        })

    # Apply the function
    map_1_and_2 = total_maps_statistics(df=map_1_and_2, df2=cs_stats_f)
    map_1_and_2_and_3 = total_maps_statistics(df=map_1_and_2_and_3, df2=cs_stats_f, three_maps=True)

    # Change the Map Number column
    map_1["Map Number"] = "MAPS 1"
    map_3["Map Number"] = "MAPS 3"

    # Exclude Map 2
    cs_maps_and_stats = pd.concat([map_1, map_3, map_1_and_2, map_1_and_2_and_3], ignore_index=True)
    print(f"[{datetime.now()}] Processed the maps.")

    client = boto3.client(
        service_name = "s3",
        region_name = "us-east-2",
        aws_access_key_id = os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]
    )
    print(f"[{datetime.now()}] Connected to S3 bucket and uploading the data.")
    client.put_object(Bucket="csgobucket1", Key="cs_data_processed.csv", Body=cs_maps_and_stats.to_csv())
    print(f"[{datetime.now()}] Uploaded the data to the S3 bucket.")
    connection.close()

# Schedule the program to run every 2 hours
if __name__ == "__main__":
    while True:
        print(f"[{datetime.now()}] Starting main program...")
        main_program()

        # Countdown to the next run
        print(f"[{datetime.now()}] Waiting 2 hours until the next run...")
        next_run = 2 * 60 * 60  # 2 hours in seconds
        while next_run > 0:
            hours, remainder = divmod(next_run, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"Next run in: {int(hours)}h {int(minutes)}m {int(seconds)}s", end="\r")
            time.sleep(1)
            next_run -= 1