global MODEL, WEIGHTS, WEIGHT_COLS, cs_data, odds, pp_data, pp_projs, team_mapper, player_mapper, player_hltv_df, team_hltv_df, player_hit_rates

import gspread
import os
import xgboost
import joblib
import warnings
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time
from utils import prizepicks_lines, database_connection_and_cursor, database_table
warnings.filterwarnings("ignore")

def print_developer_info():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 50)
    print("     🚀 DEVELOPED BY: KAZI")
    print("     📌 LINKEDIN: LINKEDIN.COM/IN/KAZISHAHRIA")
    print("     📌 FIVERR: FIVERR.COM/KAZIRSHAHRIA")
    print("=" * 50 + "\n")
print_developer_info()

MODEL = joblib.load(os.path.join(os.getcwd(), "xgr_model_v3.joblib"))
WEIGHTS = np.array([0.25, 0.20, 0.15, 0.125, 0.115, 0.10, 0.05, 0.01])
WEIGHT_COLS = ["kills", "headshots", "assists", "deaths", "kast", "adr", "rating"]

# GCP Auth
CLIENT = gspread.service_account(filename=os.path.join(os.getcwd(), "credentials.json"))
WORKBOOK = CLIENT.open("Phase 2 Project - Nano")
WORKBOOK1 = WORKBOOK.get_worksheet(0)
WORKBOOK2 = WORKBOOK.get_worksheet(1)
WORKBOOK3 = WORKBOOK.get_worksheet(2)
WORKBOOK4 = WORKBOOK.get_worksheet(3)
print(f"[STATUS]: IMPORTED DEPENDENCIES")

def total_maps(cs_data, map_df, map_three):
    stats = ["kills", "headshots", "assists", "deaths", "kast", "adr", "rating"]
    if map_three:
        for stat_column in stats:
            idx = cs_data.columns.get_indexer([stat_column])[0]
            stat_value = map_df[f"{stat_column}_map_1"] + map_df[f"{stat_column}_map_2"] + map_df[f"{stat_column}_map_3"]
            if stat_column in ["kast", "k_d_diff", "adr", "fk_diff", "rating"]:
                map_df.insert(loc=idx, column=stat_column, value=stat_value/3)
            else:
                map_df.insert(loc=idx, column=stat_column, value=stat_value)
        drop_cols = [f"{stat_column}_map_1" for stat_column in stats] + [f"{stat_column}_map_2" for stat_column in stats] + [f"{stat_column}_map_3" for stat_column in stats]
        map_df.drop(columns=drop_cols, inplace=True)
        map_df["map_number"] = "MAPS 1-3"
        return map_df
    else:
        for stat_column in stats:
            idx = cs_data.columns.get_indexer([stat_column])[0]
            stat_value = map_df[f"{stat_column}_map_1"] + map_df[f"{stat_column}_map_2"]
            if stat_column in ["kast", "adr", "rating"]:
                map_df.insert(loc=idx, column=stat_column, value=stat_value/2)
            else:
                map_df.insert(loc=idx, column=stat_column, value=stat_value)
        drop_cols = [f"{stat_column}_map_1" for stat_column in stats] + [f"{stat_column}_map_2" for stat_column in stats]
        map_df.drop(columns=drop_cols, inplace=True)
        map_df["map_number"] = "MAPS 1-2"
        return map_df

def database_table(table_name):
    connection, cursor = database_connection_and_cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    data_fetched = cursor.fetchall()
    columns = [col_name[0] for col_name in cursor.description]
    data_df = pd.DataFrame(data_fetched, columns=columns).infer_objects()
    connection.close()
    return data_df

def fix_cs_data(cs_data):
    # Convert To Float Values
    cs_data[["kast", "adr", "rating"]] = cs_data[["kast", "adr", "rating"]].astype("float")
    cs_data["date"] = pd.to_datetime(cs_data["date"])

    cs_data = cs_data.iloc[:, :].query("(map != 'Best of 3') and (map != 'Best of 2') and (map != 'All') and (map != 'Cache')").dropna().reset_index(drop=True)

    cs_data.drop(columns=["k_d_diff", "fk_diff", "event", "map", "team", "opponent", "player_name", "team_score", "opponent_score"], inplace=True)

    cs_data = cs_data.groupby(by=["match_url"]).filter(lambda group: set(group["map_number"]).issubset({1, 2, 3}))

    cs_data.reset_index(drop=True, inplace=True)

    map_1 = cs_data[cs_data["map_number"] == 1]
    map_2 = cs_data[cs_data["map_number"] == 2]
    map_3 = cs_data[cs_data["map_number"] == 3]

    target_cols = ["match_url", "player_url", "kills", "headshots", "assists", "deaths", "kast", "adr", "rating"]

    map_1_2= pd.merge(
        left=map_1,
        right=map_2[target_cols],
        suffixes = ("_map_1", "_map_2"),
        on=["match_url", "player_url"],
    )

    map_1_2_3 = map_1_2.merge(
        right=map_3[target_cols],
        on=["match_url", "player_url"],
    ).rename(columns={"kills": "kills_map_3", "headshots": "headshots_map_3", "assists": "assists_map_3", 
                    "deaths": "deaths_map_3", "kast": "kast_map_3", "adr": "adr_map_3", "rating": "rating_map_3"})

    map_1_2 = total_maps(cs_data=cs_data, map_df=map_1_2, map_three=False)
    map_1_2_3 = total_maps(cs_data=cs_data, map_df=map_1_2_3, map_three=True)

    map_1["map_number"] = "MAPS 1"
    map_3["map_number"] = "MAPS 3"

    cs_data = pd.concat(
        [
            map_1,
            map_3,
            map_1_2,
            map_1_2_3
        ],
        ignore_index=True
    )
    return cs_data

def prev_stats(player_url, map_number, kills_or_headshots, days: int):
    player_data = cs_data[
        (cs_data["player_url"] == player_url) &
        (cs_data["map_number"] == map_number)
    ]
    player_stat_array = player_data[kills_or_headshots].tail(days).to_numpy()
    
    return  np.flip(player_stat_array), round(player_stat_array[:10].mean(), 3), round(player_stat_array.mean(), 3)

def prev_avg_stats(player_url, map_number, days):
    query_date = (datetime.today() - timedelta(days=days)).date()

    player_data = cs_data[
        (cs_data["player_url"] == player_url) &
        (cs_data["map_number"] == map_number) &
        (cs_data["date"].dt.date >= query_date)
    ][["kills", "deaths", "headshots", "rating"]]

    # Data to return
    kd = (player_data["kills"]/player_data["deaths"]).mean().__round__(2)
    hs = ((player_data["headshots"]/player_data["kills"]).mean()*100).__round__(0)
    rating = (player_data["rating"]).mean().__round__(2)
    return kd, hs, rating

def make_predictions(team_id, player_id, opponent_team, map_type):
    model_inputs = {
    "wma_kills": None, "wma_headshots": None, "wma_assists": None, "wma_deaths": None, "wma_kast": None, "wma_adr": None,
    "wma_rating": None, "maps_1": 0, "maps_1_2": 0, "maps_1_3": 0, "maps_3": 0, "player_team_enc": None, "opponent_team_enc": None, "player_enc": None
    }
    TEAM_ID = int(team_id)
    PLAYER_ID = int(player_id)
    OPP_TEAM = opponent_team
    MAP_TYPE = map_type.replace("MAPS", "MAP").replace("MAP", "MAPS")

    if ("(Combo)" in map_type) | ("First" in map_type) | ("AWP" in map_type):
        return 0

    kills_or_headshots = MAP_TYPE.split()[-1].lower()
    
    map_number = " ".join(MAP_TYPE.split()[:2])
    map_number_formatted = map_number.lower().replace(" ", "_").replace("-", "_")

    team_url = team_hltv_df.loc[TEAM_ID]["hltv_url"]
    opp_url = team_hltv_df[team_hltv_df["player_team"] == OPP_TEAM]
    # If opponent cannot be found
    if len(opp_url) == 0:
        print(f"[ML MODEL ERROR]: OPPONENT NOT FOUND ({opponent_team})")
        return 0
    
    opp_url = opp_url["hltv_url"].iloc[0]
    player_url = player_hltv_df.loc[PLAYER_ID]["hltv_url"]

    # ID ERRORS
    try:
        player_team_id = team_mapper.get((team_url, map_number))
    except TypeError:
        print(f"[TEAM ID ERROR]: {TEAM_ID}")
        return 0
    try:
        opp_team_id = team_mapper.get((opp_url, map_number))
    except TypeError:
        print(f"[OPPONENT NAME ERROR]: {OPP_TEAM}")
        return 0
    
    try:
        player_id = player_mapper.get((player_url, map_number))
    except TypeError:
        print(f"[PLAYER ID ERROR]: {PLAYER_ID}")
        return 0

    model_inputs["player_team_enc"] = player_team_id
    model_inputs["opponent_team_enc"] = opp_team_id
    model_inputs["player_enc"] = player_id
    model_inputs[map_number_formatted] = 1

    player_data_df = cs_data[
    (cs_data["map_number"] == map_number) &
    (cs_data["player_url"] == player_url)
    ]
    if len(player_data_df) < 8:
        print(f"[ML MODEL ERROR]: NOT ENOUGH DATA ({player_url} | {map_number})")
        return 0

    dot_product = player_data_df[WEIGHT_COLS].tail(8).apply(lambda group: np.dot(WEIGHTS[::-1], group), raw=True)
    kills, headshots, assists, deaths, kast, adr, rating = dot_product
    model_inputs["wma_kills"] = kills
    model_inputs["wma_headshots"] = headshots
    model_inputs["wma_assists"] = assists
    model_inputs["wma_deaths"] = deaths
    model_inputs["wma_kast"] = kast
    model_inputs["wma_adr"] = adr
    model_inputs["wma_rating"] = rating

    x = [np.array(list(model_inputs.values()))]
    prediction = MODEL.predict(x)[0]
    if kills_or_headshots == "headshots":
        return round(prediction[1], 3)
    else:
        return round(prediction[0], 3)

def backtracking(game_date, player_id, team_id, opponent_team, map_type):
    model_inputs = {
    "wma_kills": None, "wma_headshots": None, "wma_assists": None, "wma_deaths": None, "wma_kast": None, "wma_adr": None,
    "wma_rating": None, "maps_1": 0, "maps_1_2": 0, "maps_1_3": 0, "maps_3": 0, "player_team_enc": None, "opponent_team_enc": None, "player_enc": None
    }
    TEAM_ID = int(team_id)
    PLAYER_ID = int(player_id)
    OPP_TEAM = opponent_team
    MAP_TYPE = map_type

    if ("(Combo)" in map_type) | ("First" in map_type) | ("AWP" in map_type):
        return 0

    kills_or_headshots = MAP_TYPE.split()[-1].lower()
    
    map_number = " ".join(MAP_TYPE.split()[:2])
    map_number_formatted = map_number.lower().replace(" ", "_").replace("-", "_")

    team_url = team_hltv_df.loc[TEAM_ID]["hltv_url"]
    opp_url = team_hltv_df[team_hltv_df["player_team"] == OPP_TEAM]
    # If opponent cannot be found
    if len(opp_url) == 0:
        print(f"[ML MODEL ERROR]: OPPONENT NOT FOUND ({opponent_team})")
        return 0
    
    opp_url = opp_url["hltv_url"].iloc[0]
    player_url = player_hltv_df.loc[PLAYER_ID]["hltv_url"]

    # ID ERRORS
    try:
        player_team_id = team_mapper.get((team_url, map_number))
    except TypeError:
        print(f"[TEAM ID ERROR]: {TEAM_ID}")
        return 0
    try:
        opp_team_id = team_mapper.get((opp_url, map_number))
    except TypeError:
        print(f"[OPPONENT NAME ERROR]: {OPP_TEAM}")
        return 0
    
    try:
        player_id = player_mapper.get((player_url, map_number))
    except TypeError:
        print(f"[PLAYER ID ERROR]: {PLAYER_ID}")
        return 0

    model_inputs["player_team_enc"] = player_team_id
    model_inputs["opponent_team_enc"] = opp_team_id
    model_inputs["player_enc"] = player_id
    model_inputs[map_number_formatted] = 1

    player_data_df = cs_data[
    (cs_data["map_number"] == map_number) &
    (cs_data["player_url"] == player_url) &
    (cs_data["date"].dt.date < game_date.date()) &
    (cs_data["map_number"] == map_number)
    ]

    actual = cs_data[
    (cs_data["date"].dt.date == game_date.date()) &
    (cs_data["player_url"] == player_url) &
    (cs_data["opponent_url"] == opp_url) &
    (cs_data["map_number"] == map_number)
    ]

    if len(actual) != 1:
        print(f"[DATAFRAME ERROR]: CANNOT FIND ACTUAL RESULT ({player_url} | {opp_url} | {map_number} | {game_date.date()})")
        return 0, 0
    
    if len(player_data_df) < 8:
        print(f"[DATAFRAME ERROR]: NOT ENOUGH DATA ({player_url} | {map_number})")
        return 0, 0

    dot_product = player_data_df[WEIGHT_COLS].tail(8).apply(lambda group: np.dot(WEIGHTS[::-1], group), raw=True)
    kills, headshots, assists, deaths, kast, adr, rating = dot_product
    model_inputs["wma_kills"] = kills
    model_inputs["wma_headshots"] = headshots
    model_inputs["wma_assists"] = assists
    model_inputs["wma_deaths"] = deaths
    model_inputs["wma_kast"] = kast
    model_inputs["wma_adr"] = adr
    model_inputs["wma_rating"] = rating

    x = [np.array(list(model_inputs.values()))]
    prediction = MODEL.predict(x)[0]

    if kills_or_headshots == "headshots":
        return prediction[1], actual.iloc[0][kills_or_headshots]
    else:
        return prediction[0], actual.iloc[0][kills_or_headshots]

def hr_x(player_url, last_x):
    # Filter data for the given player and sort by game_date
    player_hr = pp_projs[pp_projs["hltv_player_url"] == player_url].sort_values("game_date")

    # If no data is available for the player, return None
    if player_hr.empty:
        return (None, None)

    # If "AT" (All-Time) is selected
    if last_x == "AT":
        hr_correct = (player_hr["outcome"] == "Cash").sum()
        hr_string = f'{hr_correct}/{len(player_hr)}'
        return (hr_string, hr_correct / len(player_hr) if len(player_hr) > 0 else 0)

    # If last_x is within the available game history
    elif last_x <= len(player_hr):
        hr_perct = player_hr.tail(last_x)  # Get last `last_x` games
        hr_correct = (hr_perct["outcome"] == "Cash").sum()  # Count "Cash" in the subset
        hr_string = f'{hr_correct}/{last_x}'  # Use last_x as denominator
        return (hr_string, hr_correct / last_x if last_x > 0 else 0)

    # If last_x is greater than available games, return None
    return (None, None)

def update_google_sheets():
    lines = prizepicks_lines()
    lines_updated = []
    projections_hr_list = []
    backtracking_list = []

    if lines:
        for line in lines:
            pp_team_1 = line["Team"]
            pp_team_2 = line["Opp"]
            pp_date = pd.to_datetime(line["Game Date"]).date()
            pp_team_1_norm = pp_team_1
            pp_team_2_norm = pp_team_2

            # Filter odds for relevant dates
            odds_sub = odds[odds["date"] <= pp_date]

            # Mrelevant teams
            odds_result = odds_sub[
                ((odds_sub["team1"] == pp_team_1_norm) & (odds_sub["team2"] == pp_team_2_norm)) |
                ((odds_sub["team1"] == pp_team_2_norm) & (odds_sub["team2"] == pp_team_1_norm))
            ]

            # Assign odds if matches found
            if not odds_result.empty:
                if ((odds_result["team1"] == pp_team_1_norm) & (odds_result["team2"] == pp_team_2_norm)).any():
                    line["Odd"] = odds_result.loc[
                        (odds_result["team1"] == pp_team_1_norm) & (odds_result["team2"] == pp_team_2_norm),
                        "team1_odd"
                    ].iloc[0]
                elif ((odds_result["team1"] == pp_team_2_norm) & (odds_result["team2"] == pp_team_1_norm)).any():
                    line["Odd"] = odds_result.loc[
                        (odds_result["team1"] == pp_team_2_norm) & (odds_result["team2"] == pp_team_1_norm),
                        "team2_odd"
                    ].iloc[0]
            else:
                line["Odd"] = None

            lines_updated.append(line)
    else:
        print("[STATUS]: PRIZEPICKS HAS NO NEW LINES")
        return []

    print(f"[STATUS]: MAKING PROJECTIONS FOR {len(lines_updated)} PRIZEPICKS LINES")

    for line in lines_updated:
        projections_setup = {
        "ID": line["ID"], "Player": line["Name"], "Team": line["Team"], "Opponent": line["Opp"], "Type": None,
        "M1": None, "M2": None, "M3": None, "M4": None, "M5": None,
        "M6": None, "M7": None, "M8": None, "M9": None, "M10": None,
        "M11": None, "M12": None, "M13": None, "M14": None, "M15": None,
        "PP Line": line["Line Score"], "L10 Avg": None, "L15 Avg": None, "Projection": None,
        "Diff +/-": 0, "O/U": None, "Odds": line["Odd"], "Extras": None,
        "O HR %": None, "U HR %": None, "1/mo K/D": None, "1/mo HS%": None,
        "1/mo Rating": None, "3/mo K/D": None, "3/mo HS%": None, "3/mo Rating": None
        }

        backtrack_setup = {
            "Player": line["Name"], "L7 HR": None, "L7 HR %": None, "L14 HR": None,
            "L14 HR %": None, "L30 HR": None, "L30 HR %": None, "Extras": None,
            "O HR %": None, "U HR %": None, "AT HR": None, "AT HR %": None
        }

        map_type = line["Type"].replace("MAPS", "MAP").replace("MAP", "MAPS")
        
        if not("(Combo)" in map_type) | ("First" in map_type) | ("AWP" in map_type):
            player_id = int(line["Player ID"])
            team_id = int(line["Team ID"])
            opp_team = line["Opp"]

            kills_or_headshots = map_type.split()[-1].lower()
            
            map_number = " ".join(map_type.split()[:2])
            opp_url = team_hltv_df[team_hltv_df["player_team"] == opp_team]
            
            # If opponent cannot be found
            if len(opp_url) == 0:
                continue
            
            opp_url = opp_url["hltv_url"].iloc[0]
            player_url = player_hltv_df.loc[player_id]["hltv_url"]

            stat_array, ten_game_avg, overall_avg = prev_stats(player_url=player_url, map_number=map_number, kills_or_headshots=kills_or_headshots, days=15)
            projections_setup["Type"] = map_type.replace("MAPS ", "M").replace("Headshots", "Hs")
            for i, stat in enumerate(stat_array, start=1):
                projections_setup[f"M{i}"] = stat
                
            # Model projections
            try:
                proj_num = make_predictions(team_id=team_id, player_id=player_id, opponent_team=opp_team, map_type=map_type)
                if proj_num != 0:            
                    projections_setup["Projection"] = proj_num
                    projections_setup["Diff +/-"] = projections_setup["Projection"] - projections_setup["PP Line"]
                    projections_setup["O/U"] = "Under" if projections_setup["Diff +/-"] < 0 else "Over"

                projections_setup["L10 Avg"] = ten_game_avg
                projections_setup["L15 Avg"] = overall_avg
            except:
                print(f"NO PREDICTION: ", player_url, team_id, player_id, opp_team, map_type)

            # Hit Rate
            try:
                over_hr = player_hit_rates.loc[player_url, "Over", "Cash"]
            except KeyError:
                over_hr =  None
                pass
            projections_setup["O HR %"] = over_hr

            try:
                under_hr = player_hit_rates.loc[player_url, "Under", "Cash"]
            except KeyError:
                under_hr = None
                pass
            projections_setup["U HR %"] = under_hr

            kd_mo_1, hs_mo_1, rating_mo_1 = prev_avg_stats(player_url=player_url, map_number=map_number, days=30)
            kd_mo_3, hs_mo_3, rating_mo_3 = prev_avg_stats(player_url=player_url, map_number=map_number, days=90)
            projections_setup["1/mo K/D"] = kd_mo_1
            projections_setup["1/mo HS%"] = hs_mo_1
            projections_setup["1/mo Rating"] = rating_mo_1
            projections_setup["3/mo K/D"] = kd_mo_3
            projections_setup["3/mo HS%"] = hs_mo_3
            projections_setup["3/mo Rating"] = rating_mo_3
            projections_hr_list.append(projections_setup)
            
            # Backtracking
            backtrack_setup["L7 HR"], backtrack_setup["L7 HR %"] = hr_x(player_url, 7)
            backtrack_setup["L14 HR"], backtrack_setup["L14 HR %"] = hr_x(player_url, 14)
            backtrack_setup["L30 HR"], backtrack_setup["L30 HR %"] = hr_x(player_url, 30)
            backtrack_setup["O HR %"] = over_hr
            backtrack_setup["U HR %"] = under_hr
            backtrack_setup["AT HR"], backtrack_setup["AT HR %"] = hr_x(player_url, "AT")
            backtracking_list.append(backtrack_setup)
    print(f"[STATUS]: SUCCESSFULLY MADE {len(projections_hr_list)} PROJECTIONS")
    return projections_hr_list, backtracking_list

def update_projections():
    insert_rows = []
    # Logic to find projections not made
    pp_lines_not_predicted = pp_data[
                            (pp_data["game_date"].dt.date >= max(pp_projs["game_date"])) & 
                            (pp_data["game_date"].dt.date < datetime.today().date()) &
                            ~(pp_data["id"].isin(pp_projs["id"]))
                            ].dropna().reset_index(drop=True)
    print(f"[STATUS]: PROJECTING FOR {len(pp_lines_not_predicted)} PRIZEPICKS LINES")
    values = pp_lines_not_predicted.apply(lambda row: backtracking(row["game_date"], row["player_id"], row["team_id"], row["opp"], row["stat_type"]), axis=1)
    pp_lines_not_predicted[["predict", "actual"]] = values.apply(pd.Series)
    pp_projs_to_insert = pp_lines_not_predicted[pp_lines_not_predicted["predict"] != 0].reset_index(drop=True)
    pp_projs_to_insert["game_date"] = pp_projs_to_insert["game_date"].dt.date
    for row in pp_projs_to_insert.to_numpy():
        insert_rows.append(tuple(row))
    if 0 < len(insert_rows):
        conn, cur = database_connection_and_cursor()
        insert_query = """
        INSERT IGNORE INTO prizepicks_projections (
            id, game_date, stat_type, player_name, player_team, opp, 
            line_score, player_id, team_id, predict, actual
        ) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        cur.executemany(insert_query, insert_rows)
        conn.commit()
        print(f"[STATUS]: INSERTED {len(insert_rows)} NEW PROJECTIONS")
    else:
        print(f"[STATUS]: 0 PROJECTIONS TO INSERT INTO DB")

def update_last_updated():
    # Get the current date and time
    current_datetime = datetime.now()
    formatted_time = current_datetime.strftime("%I:%M %p")

    # Specify the middle cell
    middle_cell_1 = "A3"
    middle_cell_2 = "A4"

    # Update the cell with the date and time
    try:
        WORKBOOK4.update(middle_cell_1, [[f"{current_datetime.date()}"]])
        WORKBOOK4.update(middle_cell_2, [[f"{formatted_time}"]])
        print(f"[STATUS]: UPDATED ON {current_datetime.date()}")
    except Exception as e:
        print(f"An error occurred while updating the middle cell: {e}")

if __name__ == "__main__":
    while True:
        # Fetch the tables
        odds = database_table("bovado_odds")
        pp_data = database_table("prizepicks_lines")
        cs_data = database_table("hltv_cs")

        # Fetch encoders
        teams_encoded_df = database_table("teams_encoded").set_index(["hltv_url", "map_number"])
        team_mapper = teams_encoded_df.to_dict()["std"]
        players_encoded_df = database_table("players_encoded").set_index(["hltv_url", "map_number"])
        player_mapper = players_encoded_df.to_dict()["std"]

        # Fetch mappers
        player_hltv_df = database_table("player_map")
        player_hltv_df.dropna(inplace=True)
        player_hltv_df["player_id"] = player_hltv_df["player_id"].astype("int")
        player_hltv_df.set_index("player_id", inplace=True)

        team_hltv_df = database_table("team_map")
        team_hltv_df.dropna(inplace=True)
        team_hltv_df["team_id"] = team_hltv_df["team_id"].astype("int")
        team_hltv_df.set_index("team_id", inplace=True)

        pp_data.drop(columns="game_time", inplace=True)
        pp_data["game_date"] = pd.to_datetime(pp_data["game_date"])
        odds["date"] = pd.to_datetime(odds["date"]).dt.date
        odds.dropna(inplace=True)

        # Backtracking
        pp_projs = database_table("prizepicks_projections")
        model_predicted_series = np.where(
        (pp_projs["line_score"] < pp_projs["predict"]),
        "Over",
        "Under"   
        )

        outcome_series = np.where(
            ((pp_projs["predict"] > pp_projs["line_score"]) & (pp_projs["actual"] > pp_projs["line_score"])) |
            ((pp_projs["predict"] < pp_projs["line_score"]) & (pp_projs["actual"] < pp_projs["line_score"])),
            "Cash",
            "Chalk"
        )

        pp_projs["model_predicted"] = model_predicted_series
        pp_projs["outcome"] = outcome_series

        pp_projs["hltv_player_url"] = pp_projs["player_id"].map(lambda id: player_hltv_df.loc[int(id)]["hltv_url"])
        player_hit_rates = pp_projs.groupby(["hltv_player_url", "model_predicted"]).apply(lambda group: group["outcome"].value_counts(normalize=True))
        
        print(f"[STATUS]: FETCHED DATA FROM DATABASE")
        
        cs_data = fix_cs_data(cs_data)
        projections_list, backtracking_list = update_google_sheets()

        if 0 < len(projections_list):
            print(f"[STATUS]: UPDATING GOOGLE SHEETS 1-3")
            # Manipulate the dataframes
            projections_df = pd.DataFrame(projections_list)
            projections_df["Team"] = projections_df["Team"].str.upper()
            projections_df["Opponent"] = projections_df["Opponent"].str.upper()
            projections_df = projections_df.sort_values(by=["Team", "Player", "Type", "Diff +/-"], ascending=[True, True, False, False])
            projections_df["Projection"] = projections_df["Projection"].round(3)
            projections_df = projections_df.drop_duplicates(subset="ID").drop(columns="ID")
            projections_df  = projections_df.replace(np.nan, "")
            projections_df2 = projections_df.sort_values("Diff +/-", ascending=False)
            
            # Backtracking
            hr_df = pd.DataFrame(backtracking_list).sort_values(by="AT HR %", ascending=False).drop_duplicates()
            hr_df.dropna(subset="AT HR %", inplace=True)
            hr_df.replace(np.nan, "", inplace=True)
                
            # Worksheets
            worksheet_data1 = [projections_df.columns.values.tolist()] + projections_df.values.tolist()
            worksheet_data2 = [projections_df.columns.values.tolist()] + projections_df2.values.tolist()
            worksheet_data3 = [hr_df.columns.values.tolist()] + hr_df.values.tolist()
            WORKBOOK1.clear()
            WORKBOOK1.update(worksheet_data1, value_input_option="USER_ENTERED")
            WORKBOOK2.clear()
            WORKBOOK2.update(worksheet_data2, value_input_option="USER_ENTERED")
            WORKBOOK3.clear()
            WORKBOOK3.update(worksheet_data3, value_input_option="USER_ENTERED")
            print(f"[STATUS]: GOOGLE SHEETS SUCCESSFULLY UPDATED")
        update_projections()
        update_last_updated()
        print(f"[STATUS]: SLEEPING FOR 5 MINS...\n")
        time.sleep(60*5)