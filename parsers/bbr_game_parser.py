import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import time
import re
from datetime import datetime
import random


BASE_URL = "https://www.basketball-reference.com"


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]


REQUEST_DELAY = 7
BOX_SCORE_DELAY = 4
INITIAL_BACKOFF_DELAY = 10
MAX_RETRIES = 5

session = requests.Session()
session.headers.update({"User-Agent": random.choice(USER_AGENTS)})


def get_soup(url, is_box_score=False):
    """Fetches and parses HTML from a URL, handling commented-out tables and retries."""
    print(f"Fetching URL: {url}")
    current_base_delay = BOX_SCORE_DELAY if is_box_score else REQUEST_DELAY

    for attempt in range(MAX_RETRIES):
        try:

            if attempt > 0:
                pass
            else:
                time.sleep(current_base_delay)

            response = session.get(url, timeout=30)
            response.raise_for_status()

            text_to_parse = response.text
            if (
                is_box_score
                or "div_schedule" in text_to_parse
                or "box-" in text_to_parse
                or "line_score" in text_to_parse
                or "four_factors" in text_to_parse
            ):
                text_to_parse = re.sub(r"<!--|-->", "", text_to_parse)

            soup = BeautifulSoup(text_to_parse, "lxml")
            return soup

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after_header = e.response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        wait_time = int(retry_after_header)
                    except ValueError:

                        try:
                            retry_date = datetime.strptime(
                                retry_after_header, "%a, %d %b %Y %H:%M:%S GMT"
                            )
                            wait_time = (retry_date - datetime.utcnow()).total_seconds()
                            wait_time = max(0, wait_time)
                        except ValueError:
                            wait_time = INITIAL_BACKOFF_DELAY * (2**attempt)
                else:
                    wait_time = INITIAL_BACKOFF_DELAY * (2**attempt)

                print(
                    f"    HTTP 429: Too Many Requests. Waiting {wait_time:.2f}s. Retrying (Attempt {attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(wait_time)

                session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
                continue
            else:
                print(f"    HTTP Error for {url}: {e}")
                return None

        except requests.exceptions.RequestException as e:
            wait_time = INITIAL_BACKOFF_DELAY * (2**attempt)
            print(
                f"    Request Exception for {url}: {e}. Waiting {wait_time}s. Retrying (Attempt {attempt + 1}/{MAX_RETRIES})..."
            )
            time.sleep(wait_time)
            continue

    print(f"Failed to fetch {url} after {MAX_RETRIES} retries.")
    return None


def parse_team_abbr_from_link(link_tag):
    if link_tag and link_tag.has_attr("href"):
        match = re.search(r"/teams/([A-Z]{3})/\d{4}\.html", link_tag["href"])
        if match:
            return match.group(1)
    return None


def parse_game_id_from_box_score_link(link_tag):
    if link_tag and link_tag.has_attr("href"):
        match = re.search(r"/boxscores/(\d{8}0[A-Z]{3})\.html", link_tag["href"])
        if match:
            return match.group(1)
    return None


def safe_int_convert(value):
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return value


def safe_float_convert(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return value


def parse_schedule_page(schedule_soup, season_end_year):
    games_data = []
    schedule_table = schedule_soup.find("table", id="schedule")
    if not schedule_table:
        print(f"Could not find schedule table for {season_end_year}")
        return pd.DataFrame()

    for row in schedule_table.find("tbody").find_all("tr"):
        if row.find("th", class_="thead"):
            continue

        date_th = row.find("th", {"data-stat": "date_game"})
        start_time_td = row.find("td", {"data-stat": "game_start_time"})
        visitor_team_td = row.find("td", {"data-stat": "visitor_team_name"})
        visitor_pts_td = row.find("td", {"data-stat": "visitor_pts"})
        home_team_td = row.find("td", {"data-stat": "home_team_name"})
        home_pts_td = row.find("td", {"data-stat": "home_pts"})
        box_score_td = row.find("td", {"data-stat": "box_score_text"})
        overtimes_td = row.find("td", {"data-stat": "overtimes"})
        attendance_td = row.find("td", {"data-stat": "attendance"})
        log_td = row.find("td", {"data-stat": "game_duration"})
        arena_td = row.find("td", {"data-stat": "arena_name"})

        if not all([date_th, visitor_team_td, home_team_td, box_score_td]):
            continue

        game_date_str = date_th.get_text(strip=True)
        try:
            game_date = datetime.strptime(game_date_str, "%a, %b %d, %Y").strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            game_date = game_date_str

        visitor_team_link = visitor_team_td.find("a")
        home_team_link = home_team_td.find("a")
        box_score_link_tag = box_score_td.find("a")

        game_id = None
        if box_score_link_tag:
            game_id = parse_game_id_from_box_score_link(box_score_link_tag)
        if not game_id and date_th.has_attr("csk"):
            game_id_match = re.match(r"(\d{8}0[A-Z]{3})", date_th["csk"])
            if game_id_match:
                game_id = game_id_match.group(1)
        if not game_id:
            home_team_abbr_for_id = parse_team_abbr_from_link(home_team_link)
            if (
                home_team_abbr_for_id
                and isinstance(game_date, str)
                and re.match(r"\d{4}-\d{2}-\d{2}", game_date)
            ):
                game_id = game_date.replace("-", "") + "0" + home_team_abbr_for_id
            else:
                print(f"    Could not determine Game_ID for {game_date_str}")
                continue

        home_pts = safe_int_convert(
            home_pts_td.get_text(strip=True) if home_pts_td else None
        )
        visitor_pts = safe_int_convert(
            visitor_pts_td.get_text(strip=True) if visitor_pts_td else None
        )
        home_win = (
            1
            if isinstance(home_pts, int)
            and isinstance(visitor_pts, int)
            and home_pts > visitor_pts
            else 0
        )
        point_diff = (
            (home_pts - visitor_pts)
            if isinstance(home_pts, int) and isinstance(visitor_pts, int)
            else None
        )

        game_info = {
            "Game_ID": game_id,
            "Date": game_date,
            "Start_Time_ET": (
                start_time_td.get_text(strip=True) if start_time_td else None
            ),
            "Visitor_Team_Name": (
                visitor_team_td.get_text(strip=True) if visitor_team_td else None
            ),
            "Visitor_Team_ID": parse_team_abbr_from_link(visitor_team_link),
            "Visitor_PTS": visitor_pts,
            "Home_Team_Name": (
                home_team_td.get_text(strip=True) if home_team_td else None
            ),
            "Home_Team_ID": parse_team_abbr_from_link(home_team_link),
            "Home_PTS": home_pts,
            "Box_Score_Link": (
                box_score_link_tag["href"] if box_score_link_tag else None
            ),
            "Arena": arena_td.get_text(strip=True) if arena_td else None,
            "Attendance": safe_int_convert(
                attendance_td.get_text(strip=True) if attendance_td else None
            ),
            "Notes": (
                overtimes_td.get_text(strip=True)
                if overtimes_td and overtimes_td.get_text(strip=True)
                else None
            ),
            "Season_End_Year": season_end_year,
            "Home_Win": home_win,
            "Point_Differential": point_diff,
            "Game_Duration": log_td.get_text(strip=True) if log_td else None,
        }
        games_data.append(game_info)
    return pd.DataFrame(games_data)


def parse_individual_box_score(
    box_score_soup, game_id, season_end_year, home_team_id, visitor_team_id
):
    print(f"    Parsing box score for Game ID: {game_id}")
    line_score_data, four_factors_data, player_basic_data, player_advanced_data = (
        [],
        [],
        [],
        [],
    )
    game_meta = {"Game_ID": game_id, "Season_End_Year": season_end_year}

    line_score_table = box_score_soup.find("table", id="line_score")
    if line_score_table and line_score_table.find("tbody"):
        for row in line_score_table.find("tbody").find_all("tr"):
            cells = row.find_all(["th", "td"])
            team_abbr_tag = cells[0].find("a")
            team_abbr = (
                parse_team_abbr_from_link(team_abbr_tag)
                if team_abbr_tag
                else cells[0].get_text(strip=True)
            )
            line_score_data.append(
                {
                    "Game_ID": game_id,
                    "Team_ID": team_abbr,
                    "Q1": safe_int_convert(cells[1].get_text(strip=True)),
                    "Q2": safe_int_convert(cells[2].get_text(strip=True)),
                    "Q3": safe_int_convert(cells[3].get_text(strip=True)),
                    "Q4": safe_int_convert(cells[4].get_text(strip=True)),
                    "Final_PTS": safe_int_convert(cells[5].get_text(strip=True)),
                }
            )
    line_score_df = pd.DataFrame(line_score_data)

    four_factors_table = box_score_soup.find("table", id="four_factors")
    if four_factors_table and four_factors_table.find("tbody"):
        for row in four_factors_table.find("tbody").find_all("tr"):
            cells = row.find_all(["th", "td"])
            team_abbr_tag = cells[0].find("a")
            team_abbr = (
                parse_team_abbr_from_link(team_abbr_tag)
                if team_abbr_tag
                else cells[0].get_text(strip=True)
            )
            four_factors_data.append(
                {
                    "Game_ID": game_id,
                    "Team_ID": team_abbr,
                    "Pace": safe_float_convert(cells[1].get_text(strip=True)),
                    "eFG_Pct": safe_float_convert(cells[2].get_text(strip=True)),
                    "TOV_Pct": safe_float_convert(cells[3].get_text(strip=True)),
                    "ORB_Pct": safe_float_convert(cells[4].get_text(strip=True)),
                    "FT_per_FGA": safe_float_convert(cells[5].get_text(strip=True)),
                    "ORtg": safe_float_convert(cells[6].get_text(strip=True)),
                }
            )
    four_factors_df = pd.DataFrame(four_factors_data)

    team_ids_in_game = [
        visitor_team_id,
        home_team_id,
    ]

    for team_abbr_current in team_ids_in_game:
        if not team_abbr_current:
            continue

        for table_type in ["basic", "advanced"]:
            table_id_suffix = f"box-{team_abbr_current}-game-{table_type}"
            player_table_soup = box_score_soup.find("table", id=table_id_suffix)
            if not player_table_soup or not player_table_soup.find("thead"):
                print(
                    f"      Could not find player {table_type} table: {table_id_suffix}"
                )
                continue

            header_tags = (
                player_table_soup.find("thead").find_all("tr")[-1].find_all("th")
            )

            headers = [
                th.get("data-stat") or th.get_text(strip=True) for th in header_tags
            ]

            cleaned_headers = []
            for h in headers:
                if h == "player":
                    cleaned_headers.append("Player_Name_Full")
                elif h == "mp":
                    cleaned_headers.append("MP")
                else:
                    cleaned_headers.append(h.replace("%", "_Pct").replace("/", "_per_"))

            tbody = player_table_soup.find("tbody")
            if tbody:
                for player_row in tbody.find_all("tr"):
                    if (
                        player_row.find("th", class_="over_header")
                        or player_row.has_attr("class")
                        and "thead" in player_row["class"]
                    ):
                        continue

                    p_cells = player_row.find_all(["th", "td"])
                    if not p_cells:
                        continue

                    player_data = {
                        "Game_ID": game_id,
                        "Team_ID": team_abbr_current,
                        "Opponent_Team_ID": (
                            visitor_team_id
                            if team_abbr_current == home_team_id
                            else home_team_id
                        ),
                    }

                    player_name_cell = p_cells[0]
                    player_name_tag = player_name_cell.find("a")
                    if player_name_tag:
                        player_data["Player_Name_Full"] = player_name_tag.get_text(
                            strip=True
                        )
                        player_id_match = re.search(
                            r"/players/[a-z]/([a-z0-9]+)\.html", player_name_tag["href"]
                        )
                        if player_id_match:
                            player_data["Player_ID"] = player_id_match.group(1)
                    else:
                        player_data["Player_Name_Full"] = player_name_cell.get_text(
                            strip=True
                        )

                    is_dnp = False
                    if len(p_cells) > 1:
                        mp_or_dnp_text = p_cells[1].get_text(strip=True)
                        dnp_reasons = [
                            "Did Not Play",
                            "Not With Team",
                            "Player Suspended",
                            "Did Not Dress",
                        ]
                        if any(reason in mp_or_dnp_text for reason in dnp_reasons):
                            is_dnp = True
                            player_data["Played_Status"] = mp_or_dnp_text
                            player_data["MP"] = "0:00"

                    if is_dnp:

                        for header_name in cleaned_headers[1:]:
                            if header_name not in player_data:
                                player_data[header_name] = None
                    else:
                        player_data["Played_Status"] = "Played"

                        for h_idx, header_name in enumerate(cleaned_headers):

                            cell_idx = h_idx
                            if cell_idx < len(p_cells):
                                stat_val = p_cells[cell_idx].get_text(strip=True)
                                if header_name == "Player_Name_Full":
                                    continue

                                if header_name in [
                                    "ORtg",
                                    "DRtg",
                                    "GmSc",
                                    "Plus_Minus",
                                ] or header_name in [
                                    "FG",
                                    "FGA",
                                    "3P",
                                    "3PA",
                                    "FT",
                                    "FTA",
                                    "ORB",
                                    "DRB",
                                    "TRB",
                                    "AST",
                                    "STL",
                                    "BLK",
                                    "TOV",
                                    "PF",
                                    "PTS",
                                ]:
                                    player_data[header_name] = safe_int_convert(
                                        stat_val
                                    )
                                elif header_name.endswith("_Pct") or header_name in [
                                    "TS_Pct",
                                    "eFG_Pct",
                                    "3PAr",
                                    "FTr",
                                    "ORB_Pct",
                                    "DRB_Pct",
                                    "TRB_Pct",
                                    "AST_Pct",
                                    "STL_Pct",
                                    "BLK_Pct",
                                    "TOV_Pct",
                                    "USG_Pct",
                                    "BPM",
                                ]:
                                    player_data[header_name] = safe_float_convert(
                                        stat_val
                                    )
                                else:
                                    player_data[header_name] = stat_val
                            else:
                                player_data[header_name] = None

                    if table_type == "basic":
                        player_basic_data.append(player_data)
                    elif table_type == "advanced":
                        player_advanced_data.append(player_data)

    player_basic_df = pd.DataFrame(player_basic_data)
    player_advanced_df = pd.DataFrame(player_advanced_data)

    inactive_div = box_score_soup.find("div", string=re.compile("Inactive:"))
    if inactive_div:
        game_meta["Inactives_Text"] = inactive_div.get_text(strip=True)

    officials_div = box_score_soup.find("div", string=re.compile("Officials:"))
    if officials_div:
        game_meta["Officials_Text"] = (
            officials_div.get_text(strip=True).replace("Officials:", "").strip()
        )

    time_of_game_div = box_score_soup.find("div", string=re.compile("Time of Game:"))
    if time_of_game_div:
        game_meta["Time_Of_Game_Str"] = (
            time_of_game_div.get_text(strip=True).replace("Time of Game:", "").strip()
        )

    return (
        line_score_df,
        four_factors_df,
        player_basic_df,
        player_advanced_df,
        game_meta,
    )


def main():
    start_year = 2024
    end_year = 2024

    all_games_schedule_list = []
    all_line_scores_list = []
    all_four_factors_list = []
    all_player_basic_list = []
    all_player_advanced_list = []
    all_game_meta_list = []

    for year_int in range(start_year, end_year + 1):
        print(f"\nProcessing Season Ending: {year_int}")
        main_schedule_url = f"{BASE_URL}/leagues/NBA_{year_int}_games.html"
        main_soup = get_soup(main_schedule_url)
        if not main_soup:
            continue

        month_links = []
        filter_div = main_soup.find("div", class_="filter")
        if filter_div:
            for a_tag in filter_div.find_all("a", href=True):
                month_links.append(BASE_URL + a_tag["href"])
        if not month_links:
            month_links.append(main_schedule_url)
        month_links = sorted(list(set(month_links)))

        for month_url in month_links:
            print(f"  Processing month URL: {month_url}")
            monthly_soup = get_soup(month_url)
            if not monthly_soup:
                continue

            schedule_table_to_parse = None
            comment = monthly_soup.find(
                string=lambda text: isinstance(text, Comment)
                and '<table class="suppress_glossary sortable stats_table now_sortable" id="schedule"'
                in text
            )
            if comment:
                schedule_table_to_parse = BeautifulSoup(comment, "lxml")
            else:
                schedule_table_to_parse = monthly_soup

            if schedule_table_to_parse:
                monthly_schedule_df = parse_schedule_page(
                    schedule_table_to_parse, year_int
                )
                if not monthly_schedule_df.empty:
                    all_games_schedule_list.append(monthly_schedule_df)
                    for idx, game_row in monthly_schedule_df.iterrows():
                        if (
                            pd.isna(game_row["Box_Score_Link"])
                            or not game_row["Box_Score_Link"]
                        ):
                            print(
                                f"    Skipping game, no box score link: {game_row['Date']} {game_row.get('Visitor_Team_Name','Vis')} vs {game_row.get('Home_Team_Name','Home')}"
                            )
                            continue

                        box_score_url = BASE_URL + game_row["Box_Score_Link"]
                        box_soup = get_soup(box_score_url, is_box_score=True)
                        if box_soup:
                            ls_df, ff_df, pb_df, pa_df, g_meta = (
                                parse_individual_box_score(
                                    box_soup,
                                    game_row["Game_ID"],
                                    year_int,
                                    game_row["Home_Team_ID"],
                                    game_row["Visitor_Team_ID"],
                                )
                            )
                            if not ls_df.empty:
                                all_line_scores_list.append(ls_df)
                            if not ff_df.empty:
                                all_four_factors_list.append(ff_df)
                            if not pb_df.empty:
                                all_player_basic_list.append(pb_df)
                            if not pa_df.empty:
                                all_player_advanced_list.append(pa_df)
                            if g_meta:
                                all_game_meta_list.append(g_meta)
            else:
                print(f"  No schedule table structure found on {month_url}")

    if all_games_schedule_list:
        pd.concat(all_games_schedule_list, ignore_index=True).to_csv(
            "games_schedule.csv", index=False
        )
        print("Saved games_schedule.csv")
    if all_line_scores_list:
        pd.concat(all_line_scores_list, ignore_index=True).to_csv(
            "game_line_scores.csv", index=False
        )
        print("Saved game_line_scores.csv")
    if all_four_factors_list:
        pd.concat(all_four_factors_list, ignore_index=True).to_csv(
            "game_four_factors.csv", index=False
        )
        print("Saved game_four_factors.csv")
    if all_player_basic_list:
        pd.concat(all_player_basic_list, ignore_index=True).to_csv(
            "game_player_basic_stats.csv", index=False
        )
        print("Saved game_player_basic_stats.csv")
    if all_player_advanced_list:
        pd.concat(all_player_advanced_list, ignore_index=True).to_csv(
            "game_player_advanced_stats.csv", index=False
        )
        print("Saved game_player_advanced_stats.csv")
    if all_game_meta_list:
        pd.DataFrame(all_game_meta_list).to_csv("game_meta_info.csv", index=False)
        print("Saved game_meta_info.csv")

    print("Full schedule and box score parsing complete.")


if __name__ == "__main__":
    main()
