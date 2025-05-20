import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE_URL = "https://www.basketball-reference.com/leagues/NBA_{}_standings.html"


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


def parse_team_data_from_row(row, year_season_ends, conference, current_division):
    """Helper function to parse a single team row from a standings table."""
    team_entry = {
        "SeasonEndYear": year_season_ends,
        "Conference": conference,
        "Division": current_division,
    }

    th_team_name = row.find("th", {"data-stat": "team_name"})
    if th_team_name:
        team_name_full = th_team_name.get_text(strip=True)
        team_entry["Team"] = team_name_full.replace("*", "").strip()
        team_entry["Playoffs"] = "*" if "*" in team_name_full else ""

        team_link = th_team_name.find("a")
        if team_link and team_link.has_attr("href"):
            href_parts = team_link["href"].split("/")
            if len(href_parts) > 2:
                team_entry["Tm_ID"] = href_parts[2]
    else:
        return None

    cells = row.find_all("td")

    for cell in cells:
        stat_name = cell.get("data-stat")
        if stat_name:
            team_entry[stat_name] = cell.get_text(strip=True)

    if "Team" in team_entry:
        return team_entry
    return None


def parse_standings_for_year(html_content, year_season_ends):
    """
    Parses team standings from HTML content for a given season.
    Handles both conference-based and division-based table structures.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    all_teams_data = []

    table_e_conf = soup.find("table", id="confs_standings_E")
    table_w_conf = soup.find("table", id="confs_standings_W")

    if table_e_conf and table_w_conf:
        logging.info(f"Found conference-based standings tables for {year_season_ends}.")

        tbody_e = table_e_conf.find("tbody")
        if tbody_e:
            for row in tbody_e.find_all("tr"):
                if "thead" in row.get("class", []):
                    continue
                team_data = parse_team_data_from_row(
                    row, year_season_ends, "East", None
                )
                if team_data:
                    all_teams_data.append(team_data)

        tbody_w = table_w_conf.find("tbody")
        if tbody_w:
            for row in tbody_w.find_all("tr"):
                if "thead" in row.get("class", []):
                    continue
                team_data = parse_team_data_from_row(
                    row, year_season_ends, "West", None
                )
                if team_data:
                    all_teams_data.append(team_data)
    else:

        logging.info(
            f"Conference tables not found, trying division-based standings tables for {year_season_ends}."
        )
        table_e_div = soup.find("table", id="divs_standings_E")
        table_w_div = soup.find("table", id="divs_standings_W")

        current_division = None
        if table_e_div:
            tbody_e = table_e_div.find("tbody")
            if tbody_e:
                for row in tbody_e.find_all("tr"):
                    if "thead" in row.get("class", []):
                        current_division = row.get_text(strip=True)
                        continue
                    if current_division:
                        team_data = parse_team_data_from_row(
                            row, year_season_ends, "East", current_division
                        )
                        if team_data:
                            all_teams_data.append(team_data)
            else:
                logging.warning(
                    f"No tbody found in Eastern Division table for year {year_season_ends}"
                )
        else:
            logging.warning(
                f"Eastern Division standings table 'divs_standings_E' not found for {year_season_ends}."
            )

        current_division = None
        if table_w_div:
            tbody_w = table_w_div.find("tbody")
            if tbody_w:
                for row in tbody_w.find_all("tr"):
                    if "thead" in row.get("class", []):
                        current_division = row.get_text(strip=True)
                        continue
                    if current_division:
                        team_data = parse_team_data_from_row(
                            row, year_season_ends, "West", current_division
                        )
                        if team_data:
                            all_teams_data.append(team_data)
            else:
                logging.warning(
                    f"No tbody found in Western Division table for year {year_season_ends}"
                )
        else:
            logging.warning(
                f"Western Division standings table 'divs_standings_W' not found for {year_season_ends}."
            )

    if not all_teams_data and not (table_e_conf or table_e_div):
        logging.error(
            f"No standings tables (neither conference nor division) could be found for year {year_season_ends}."
        )

    return all_teams_data


def clean_team_standings_data(df):
    """Cleans and converts team standings DataFrame columns."""
    if df.empty:
        return df

    rename_map = {
        "wins": "W",
        "losses": "L",
        "win_loss_pct": "W/L%",
        "gb": "GB",
        "pts_per_g": "PS/G",
        "opp_pts_per_g": "PA/G",
        "srs": "SRS",
    }

    cols_to_rename = {k: v for k, v in rename_map.items() if k in df.columns}
    df.rename(columns=cols_to_rename, inplace=True)

    if "W" in df.columns:
        df["W"] = pd.to_numeric(df["W"], errors="coerce").astype("Int64")
    if "L" in df.columns:
        df["L"] = pd.to_numeric(df["L"], errors="coerce").astype("Int64")

    float_cols = ["W/L%", "PS/G", "PA/G", "SRS"]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "GB" in df.columns:
        df["GB"] = (
            df["GB"].replace({"—": "0", "—": 0, "-": "0", None: "0"}).astype(float)
        )

    if "Division" not in df.columns:
        df["Division"] = None

    return df


def get_nba_team_standings_all_years(start_year_url, end_year_url):
    """
    Fetches, parses, and combines NBA team standings for a range of seasons.
    """
    all_standings_data = []
    for year in range(start_year_url, end_year_url + 1):
        url = BASE_URL.format(year)
        season_label = f"{year-1}-{str(year)[-2:]}"
        logging.info(f"Fetching team standings for {season_label} season from {url}...")

        html_content = fetch_html_with_retries(url)

        if html_content:
            season_standings = parse_standings_for_year(html_content, year)
            if season_standings:
                all_standings_data.extend(season_standings)
                logging.info(
                    f"Successfully parsed {len(season_standings)} team entries for {season_label} season."
                )
            else:
                logging.warning(
                    f"No team standings data parsed for {season_label} season."
                )
        else:
            logging.warning(
                f"Failed to fetch HTML for team standings for {season_label} season."
            )

        sleep_duration = 5
        logging.info(f"Waiting for {sleep_duration} seconds before next request...")
        time.sleep(sleep_duration)

    if not all_standings_data:
        logging.error(
            "No team standings data was collected from any year. Returning an empty DataFrame."
        )
        return pd.DataFrame()

    final_df = pd.DataFrame(all_standings_data)
    final_df = clean_team_standings_data(final_df)

    ordered_cols = [
        "SeasonEndYear",
        "Conference",
        "Division",
        "Team",
        "Tm_ID",
        "Playoffs",
        "W",
        "L",
        "W/L%",
        "GB",
        "PS/G",
        "PA/G",
        "SRS",
    ]
    existing_ordered_cols = [col for col in ordered_cols if col in final_df.columns]
    final_df = final_df[existing_ordered_cols]

    return final_df


if __name__ == "__main__":
    START_YEAR_URL = 2000
    END_YEAR_URL = 2024

    logging.info(
        f"Starting team standings data collection for NBA seasons ending {START_YEAR_URL} to {END_YEAR_URL}."
    )

    nba_team_standings_df = get_nba_team_standings_all_years(
        START_YEAR_URL, END_YEAR_URL
    )

    if not nba_team_standings_df.empty:
        logging.info(f"\n--- Team Standings Data Collection Complete ---")
        logging.info(
            f"Collected team standings for {nba_team_standings_df['SeasonEndYear'].nunique()} seasons, total {len(nba_team_standings_df)} team entries."
        )
        logging.info(
            f"\nFirst 5 rows of the combined DataFrame:\n{nba_team_standings_df.head()}"
        )
        logging.info(
            f"\nLast 5 rows of the combined DataFrame:\n{nba_team_standings_df.tail()}"
        )
        logging.info(f"\nDataFrame Info:\n")
        nba_team_standings_df.info()

        output_filename = f"nba_team_standings_{START_YEAR_URL}-{END_YEAR_URL}.csv"
        try:
            nba_team_standings_df.to_csv(output_filename, index=False)
            logging.info(f"Team standings data successfully saved to {output_filename}")
        except Exception as e:
            logging.error(f"Error saving team standings DataFrame to CSV: {e}")
    else:
        logging.info(
            "No team standings data was fetched or parsed. The final DataFrame is empty."
        )
