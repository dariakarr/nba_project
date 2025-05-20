import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from io import StringIO


INPUT_CSV_PATH = "nba_team_standings_2000-2024.csv"
BASE_URL = "https://www.basketball-reference.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_DELAY = 2


def get_soup(url):
    """Fetches and parses HTML from a URL."""
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        response.raise_for_status()
        commented_html = re.sub(r"<!--|-->", "", response.text)
        soup = BeautifulSoup(commented_html, "lxml")
        return soup
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def clean_salary(salary_str):
    """Removes $ and commas, converts to int."""
    if salary_str is None or salary_str == "":
        return None
    return int(salary_str.replace("$", "").replace(",", ""))


def parse_table_to_dataframe(table_soup, table_id, team_id, season_end_year):
    """Parses a BeautifulSoup table object into a pandas DataFrame."""
    if not table_soup:
        print(f"Table with id '{table_id}' not found for {team_id} {season_end_year}.")
        return pd.DataFrame()

    headers_from_html_th_tags = []
    header_row_thead = table_soup.find("thead")
    if header_row_thead:

        header_tr_list = header_row_thead.find_all("tr")
        if header_tr_list:
            headers_from_html_th_tags = header_tr_list[-1].find_all("th")

    if not headers_from_html_th_tags:
        first_row = table_soup.find("tr")
        if first_row:
            headers_from_html_th_tags = first_row.find_all(["th", "td"])

    if not headers_from_html_th_tags:
        print(
            f"Could not find any header th tags for table {table_id} for {team_id} {season_end_year}"
        )
        return pd.DataFrame()

    cleaned_headers = []
    for i, th_tag in enumerate(headers_from_html_th_tags):
        h_text = th_tag.get_text(strip=True)
        data_stat = th_tag.get("data-stat")
        col_name = h_text

        if table_id == "salaries2":
            if data_stat == "ranker":
                col_name = "Rk_Sal"
            elif data_stat == "player":
                col_name = "Player_In_Salary_Table"
            elif data_stat == "salary":
                col_name = "Salary_Value"
            elif not h_text and not data_stat:
                col_name = f"column_{i}"
            elif not h_text and data_stat:
                col_name = data_stat
        else:
            if h_text == "%" and cleaned_headers and cleaned_headers[-1].endswith("3P"):
                cleaned_headers[-1] = cleaned_headers[-1] + "_Pct"
                continue
            elif (
                h_text == "%" and cleaned_headers and cleaned_headers[-1].endswith("FG")
            ):
                cleaned_headers[-1] = cleaned_headers[-1] + "_Pct"
                continue
            elif (
                h_text == "%" and cleaned_headers and cleaned_headers[-1].endswith("FT")
            ):
                cleaned_headers[-1] = cleaned_headers[-1] + "_Pct"
                continue
            elif (
                h_text == "%" and cleaned_headers and cleaned_headers[-1].endswith("2P")
            ):
                cleaned_headers[-1] = cleaned_headers[-1] + "_Pct"
                continue
            elif (
                h_text == "%"
                and cleaned_headers
                and cleaned_headers[-1].endswith("eFG")
            ):
                cleaned_headers[-1] = cleaned_headers[-1] + "_Pct"
                continue
            elif h_text == "Birth":
                col_name = "Country_Birth"
            elif h_text == "No." and table_id == "roster":
                col_name = "Jersey_No"
            elif h_text == "Player" and table_id == "roster":
                col_name = "Player_Name_Roster"
            elif h_text == "Player" and (
                table_id == "per_game_stats" or table_id == "totals_stats"
            ):
                col_name = "Player_Name_Stats"
            elif h_text == "Arena" and table_id == "team_misc":
                col_name = "Arena_Name"
            elif (
                h_text == "FT/FGA"
                and cleaned_headers
                and cleaned_headers[-1] == "ORB_Pct"
            ):
                col_name = "FT_per_FGA_Off"
            elif (
                h_text == "FT/FGA"
                and cleaned_headers
                and cleaned_headers[-1] == "DRB_Pct"
            ):
                col_name = "FT_per_FGA_Def"
            elif (
                h_text == "eFG%" and cleaned_headers and cleaned_headers[-1] == "_3PAr"
            ):
                col_name = "eFG_Pct_Off"
            elif (
                h_text == "eFG%"
                and cleaned_headers
                and cleaned_headers[-1] == "FT_per_FGA_Off"
            ):
                col_name = "eFG_Pct_Def"
            elif (
                h_text == "TOV%"
                and cleaned_headers
                and cleaned_headers[-1] == "eFG_Pct_Off"
            ):
                col_name = "TOV_Pct_Off"
            elif (
                h_text == "TOV%"
                and cleaned_headers
                and cleaned_headers[-1] == "eFG_Pct_Def"
            ):
                col_name = "TOV_Pct_Def"
            elif not h_text.strip():
                if data_stat:
                    col_name = data_stat
                else:
                    col_name = f"column_{i}"
            else:
                col_name = (
                    col_name.replace("%", "_Pct")
                    .replace("/", "_per_")
                    .replace(".", "")
                    .replace("-", "_")
                    .replace(" ", "_")
                )

        cleaned_headers.append(col_name)

    rows_data = []
    tbody = table_soup.find("tbody")
    if not tbody:
        print(f"No tbody found for table {table_id} for {team_id} {season_end_year}")
        return pd.DataFrame()

    for row_soup in tbody.find_all("tr"):
        if row_soup.find("th", class_="over_header") or row_soup.find(
            "td", class_="over_header"
        ):
            continue
        if row_soup.has_attr("class") and "thead" in row_soup["class"]:
            continue

        cells = row_soup.find_all(["th", "td"])
        row_dict = {}

        player_id_val = None
        player_name_val = None

        if table_id in ["roster", "per_game_stats", "totals_stats", "salaries2"]:
            player_cell_tag = None
            if table_id == "salaries2":
                if len(cells) > 1:
                    player_cell_tag = cells[1]
            else:
                player_cell_tag = row_soup.find("td", {"data-stat": "player"})

            if player_cell_tag:
                player_name_val = player_cell_tag.get_text(strip=True)
                player_link_tag = player_cell_tag.find("a")
                if player_link_tag and player_link_tag.get("href"):
                    player_id_match = re.search(
                        r"/players/[a-z]/([a-z0-9]+)\.html", player_link_tag["href"]
                    )
                    if player_id_match:
                        player_id_val = player_id_match.group(1)

            if player_id_val:
                row_dict["Player_ID"] = player_id_val
            if player_name_val:
                row_dict["Player_Name_Full"] = player_name_val

        for i, cell in enumerate(cells):
            header_name = (
                cleaned_headers[i]
                if i < len(cleaned_headers)
                else f"column_{i}_fallback"
            )
            cell_text = cell.get_text(strip=True)

            if cell_text == "":
                row_dict[header_name] = None
            elif header_name == "Salary_Value" and table_id == "salaries2":
                row_dict[header_name] = clean_salary(cell_text)
            elif header_name == "Jersey_No" and table_id == "roster":
                row_dict[header_name] = cell_text
            else:
                try:
                    if "." in cell_text:
                        row_dict[header_name] = float(cell_text)
                    else:
                        row_dict[header_name] = int(cell_text)
                except ValueError:
                    row_dict[header_name] = cell_text

        if table_id == "team_and_opponent":
            first_col_val = cells[0].get_text(strip=True)
            if "Lg Rank" in first_col_val or "Year/Year" in first_col_val:
                continue
            elif "Team/G" in first_col_val:
                row_dict["Stat_Type"] = "Team_Per_Game"
            elif "Opponent/G" in first_col_val:
                row_dict["Stat_Type"] = "Opponent_Per_Game"
            elif "Team" == first_col_val:
                row_dict["Stat_Type"] = "Team_Totals"
            elif "Opponent" == first_col_val:
                row_dict["Stat_Type"] = "Opponent_Totals"
            else:
                continue

        if (
            table_id == "per_game_stats" or table_id == "totals_stats"
        ) and row_dict.get("Player_Name_Stats") == "Team Totals":
            continue
        if table_id == "salaries2" and (not player_name_val or player_name_val == ""):
            continue
        if table_id == "team_misc" and row_dict.get(cleaned_headers[0]) != "Team":
            continue

        if row_dict:
            rows_data.append(row_dict)

    df = pd.DataFrame(rows_data)
    df["Tm_ID"] = team_id
    df["Season_End_Year"] = int(season_end_year)
    return df


def main():
    try:
        standings_df = pd.read_csv(INPUT_CSV_PATH)
    except FileNotFoundError:
        print(f"Error: Input CSV file '{INPUT_CSV_PATH}' not found.")
        return

    all_rosters = []
    all_team_opponent_stats = []
    all_team_misc_stats = []
    all_player_per_game = []
    all_player_totals = []
    all_salaries = []

    for index, row in standings_df.iterrows():
        team_abbr = row["Tm_ID"]
        year = int(row["SeasonEndYear"])
        print(f"Fetching data for {team_abbr} - Season {year}...")

        team_url = f"{BASE_URL}/teams/{team_abbr}/{year}.html"
        soup = get_soup(team_url)

        if not soup:
            print(f"Skipping {team_abbr} for {year} due to fetch error.")
            time.sleep(REQUEST_DELAY)
            continue

        roster_table_soup = soup.find("table", id="roster")
        roster_df = parse_table_to_dataframe(
            roster_table_soup, "roster", team_abbr, year
        )
        if not roster_df.empty:
            all_rosters.append(roster_df)

        team_opp_table_soup = soup.find("table", id="team_and_opponent")
        team_opp_df = parse_table_to_dataframe(
            team_opp_table_soup, "team_and_opponent", team_abbr, year
        )
        if not team_opp_df.empty:
            all_team_opponent_stats.append(team_opp_df)

        team_misc_table_soup = soup.find("table", id="team_misc")
        team_misc_df = parse_table_to_dataframe(
            team_misc_table_soup, "team_misc", team_abbr, year
        )
        if not team_misc_df.empty:
            all_team_misc_stats.append(team_misc_df)

        player_pg_table_soup = soup.find("table", id="per_game_stats")
        player_pg_df = parse_table_to_dataframe(
            player_pg_table_soup, "per_game_stats", team_abbr, year
        )
        if not player_pg_df.empty:
            all_player_per_game.append(player_pg_df)

        player_totals_table_soup = soup.find("table", id="totals_stats")
        player_totals_df = parse_table_to_dataframe(
            player_totals_table_soup, "totals_stats", team_abbr, year
        )
        if not player_totals_df.empty:
            all_player_totals.append(player_totals_df)

        salaries_table_soup = soup.find("table", id="salaries2")
        salaries_df = parse_table_to_dataframe(
            salaries_table_soup, "salaries2", team_abbr, year
        )
        if not salaries_df.empty:
            all_salaries.append(salaries_df)

        time.sleep(REQUEST_DELAY)

    if all_rosters:
        final_rosters_df = pd.concat(all_rosters, ignore_index=True)
        final_rosters_df.to_csv("parsed_team_rosters.csv", index=False)
        print("Saved parsed_team_rosters.csv")
    if all_team_opponent_stats:
        final_team_opponent_df = pd.concat(all_team_opponent_stats, ignore_index=True)
        final_team_opponent_df.to_csv("parsed_team_opponent_stats.csv", index=False)
        print("Saved parsed_team_opponent_stats.csv")
    if all_team_misc_stats:
        final_team_misc_df = pd.concat(all_team_misc_stats, ignore_index=True)
        final_team_misc_df.to_csv("parsed_team_misc_stats.csv", index=False)
        print("Saved parsed_team_misc_stats.csv")
    if all_player_per_game:
        final_player_pg_df = pd.concat(all_player_per_game, ignore_index=True)
        final_player_pg_df.to_csv("parsed_player_per_game_stats.csv", index=False)
        print("Saved parsed_player_per_game_stats.csv")
    if all_player_totals:
        final_player_totals_df = pd.concat(all_player_totals, ignore_index=True)
        final_player_totals_df.to_csv("parsed_player_totals_stats.csv", index=False)
        print("Saved parsed_player_totals_stats.csv")
    if all_salaries:
        final_salaries_df = pd.concat(all_salaries, ignore_index=True)
        final_salaries_df.to_csv("parsed_team_salaries.csv", index=False)
        print("Saved parsed_team_salaries.csv")

    print("Parsing complete.")


if __name__ == "__main__":
    main()
