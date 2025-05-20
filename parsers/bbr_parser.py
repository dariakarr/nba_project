import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE_URL = "https://www.basketball-reference.com/leagues/NBA_{}_totals.html"


def fetch_html_with_retries(url, retries=3, delay=5):
    """Fetches HTML content from a URL with retries and a timeout."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            return response.content
        except requests.exceptions.Timeout:
            logging.warning(
                f"Timeout occurred for {url} (attempt {i+1}/{retries}). Retrying in {delay}s..."
            )
            time.sleep(delay)
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error for {url} (attempt {i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                logging.error(f"Failed to fetch {url} after {retries} retries.")
                return None
    return None


def parse_player_totals_for_year(html_content, year_season_ends):
    """Parses player total stats from HTML content for a given season."""
    soup = BeautifulSoup(html_content, "html.parser")

    table = soup.find("table", id="totals_stats")
    if not table:
        table_div = soup.find("div", id="div_totals_stats")
        if table_div:
            table = table_div.find("table", id="totals_stats")

    if not table:
        logging.warning(
            f"Stats table 'totals_stats' not found for year {year_season_ends}."
        )
        return []

    parsed_rows = []

    tbody = table.find("tbody")
    if not tbody:
        logging.warning(f"No tbody found in table for year {year_season_ends}")
        return []

    for row in tbody.find_all("tr"):
        if row.has_attr("class") and "thead" in row["class"]:
            continue

        player_entry = {"season_end_year": year_season_ends}
        is_player_row_candidate = False

        for cell in row.find_all(["th", "td"]):
            stat_name = cell.get("data-stat")
            if stat_name:
                text_value = cell.get_text(strip=True)
                player_entry[stat_name] = text_value

                if stat_name == "name_display":
                    is_player_row_candidate = True
                    player_link = cell.find("a")
                    if player_link and player_link.has_attr("href"):
                        href_parts = player_link["href"].split("/")
                        if len(href_parts) > 0:

                            player_entry["player_id"] = href_parts[-1].replace(
                                ".html", ""
                            )

                    if cell.has_attr("data-append-csv"):
                        player_entry["player_id_csv"] = cell["data-append-csv"]

        if is_player_row_candidate and player_entry.get("name_display"):
            if "ranker" not in player_entry:
                player_entry["ranker"] = None
            parsed_rows.append(player_entry)

    return parsed_rows


def clean_and_convert_data(df):
    """Cleans and converts DataFrame columns to appropriate types."""
    if df.empty:
        return df

    rename_map = {
        "season_end_year": "SeasonEndYear",
        "ranker": "Rk",
        "name_display": "Player",
        "player_id": "PlayerID",
        "player_id_csv": "PlayerID_CSV",
        "age": "Age",
        "team_name_abbr": "Tm",
        "pos": "Pos",
        "games": "G",
        "games_started": "GS",
        "mp": "MP",
        "fg": "FG",
        "fga": "FGA",
        "fg_pct": "FG%",
        "fg3": "3P",
        "fg3a": "3PA",
        "fg3_pct": "3P%",
        "fg2": "2P",
        "fg2a": "2PA",
        "fg2_pct": "2P%",
        "efg_pct": "eFG%",
        "ft": "FT",
        "fta": "FTA",
        "ft_pct": "FT%",
        "orb": "ORB",
        "drb": "DRB",
        "trb": "TRB",
        "ast": "AST",
        "stl": "STL",
        "blk": "BLK",
        "tov": "TOV",
        "pf": "PF",
        "pts": "PTS",
        "tpl_dbl": "Trp-Dbl",
        "awards": "Awards",
    }

    cols_to_use = [col for col in rename_map.keys() if col in df.columns]
    df = df[cols_to_use].copy()
    df.rename(columns=rename_map, inplace=True)

    if "Rk" in df.columns:
        df["Rk"] = pd.to_numeric(df["Rk"], errors="coerce").astype("Int64")

    int_cols = [
        "Age",
        "G",
        "GS",
        "MP",
        "FG",
        "FGA",
        "3P",
        "3PA",
        "2P",
        "2PA",
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
    ]
    if "Trp-Dbl" in df.columns:

        df["Trp-Dbl"] = pd.to_numeric(
            df["Trp-Dbl"].replace("", "0"), errors="coerce"
        ).astype("Int64")

    for col in int_cols:
        if col in df.columns:

            df[col] = pd.to_numeric(df[col].replace("", None), errors="coerce").astype(
                "Int64"
            )

    float_cols = ["FG%", "3P%", "2P%", "eFG%", "FT%"]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].replace("", None), errors="coerce")

    str_cols = ["Player", "PlayerID", "PlayerID_CSV", "Tm", "Pos", "Awards"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("")

    return df


def get_nba_player_totals_all_years(start_year_url, end_year_url):
    """
    Fetches, parses, and combines NBA player total stats for a range of seasons.
    Years refer to the year the season ends (e.g., 2020 for 2019-20 season).
    """
    all_data_collected = []

    for year in range(start_year_url, end_year_url + 1):
        url = BASE_URL.format(year)

        season_label = f"{year-1}-{str(year)[-2:]}"
        logging.info(f"Fetching data for {season_label} season from {url}...")

        html_content = fetch_html_with_retries(url)

        if html_content:
            season_data = parse_player_totals_for_year(html_content, year)
            if season_data:
                all_data_collected.extend(season_data)
                logging.info(
                    f"Successfully parsed {len(season_data)} entries for {season_label} season."
                )
            else:
                logging.warning(f"No data parsed for {season_label} season.")
        else:
            logging.warning(f"Failed to fetch HTML for {season_label} season.")

        sleep_duration = 5
        logging.info(f"Waiting for {sleep_duration} seconds before next request...")
        time.sleep(sleep_duration)

    if not all_data_collected:
        logging.error(
            "No data was collected from any year. Returning an empty DataFrame."
        )
        return pd.DataFrame()

    final_df = pd.DataFrame(all_data_collected)

    final_df = clean_and_convert_data(final_df)

    return final_df


if __name__ == "__main__":

    START_YEAR_URL = 2000
    END_YEAR_URL = 2024

    logging.info(
        f"Starting data collection for NBA seasons ending {START_YEAR_URL} to {END_YEAR_URL}."
    )

    nba_player_stats_df = get_nba_player_totals_all_years(START_YEAR_URL, END_YEAR_URL)

    if not nba_player_stats_df.empty:
        logging.info(f"\n--- Data collection complete ---")
        logging.info(
            f"Collected data for {nba_player_stats_df['SeasonEndYear'].nunique()} seasons, total {len(nba_player_stats_df)} entries."
        )
        logging.info(
            f"\nFirst 5 rows of the combined DataFrame:\n{nba_player_stats_df.head()}"
        )
        logging.info(
            f"\nLast 5 rows of the combined DataFrame:\n{nba_player_stats_df.tail()}"
        )
        logging.info(f"\nDataFrame Info:\n")
        nba_player_stats_df.info()

        output_filename = f"nba_player_totals_{START_YEAR_URL}-{END_YEAR_URL}.csv"
        try:
            nba_player_stats_df.to_csv(output_filename, index=False)
            logging.info(f"Data successfully saved to {output_filename}")
        except Exception as e:
            logging.error(f"Error saving DataFrame to CSV: {e}")
    else:
        logging.info("No data was fetched or parsed. The final DataFrame is empty.")
