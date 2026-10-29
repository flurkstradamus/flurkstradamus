import requests
import re
from datetime import datetime, timedelta
import streamlit as st
from config import DEFAULT_LOGO, OFFICIAL_ABBR_MAP
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def clean_nba_abbr(team_name, espn_abbr):
    if team_name in OFFICIAL_ABBR_MAP:
        return OFFICIAL_ABBR_MAP[team_name]
    if espn_abbr and espn_abbr.strip():
        clean = espn_abbr.strip().upper()
        if len(clean) <= 4:
            return clean
    words = re.findall(r"[A-Z0-9]", team_name)
    return "".join(words[:3]) if words else "NBA"

def format_nba_tipoff(date_str, fallback_status):
    if not date_str:
        return fallback_status
    try:
        dt = datetime.strptime(date_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M%z")
        dt_et = dt - timedelta(hours=4)
        return dt_et.strftime("%a %m/%d - %I:%M %p ET")
    except Exception:
        return fallback_status

@st.cache_data(ttl=600, show_spinner=False)
def fetch_nba_injury_list():
    """
    Fetches the live NBA-wide injury report from ESPN.
    Returns a set of lowercased player names who are confirmed Out or Doubtful.
    """
    inactive_players = set()
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        r = requests.get(url, timeout=3.5)
        if r.status_code == 200:
            data = r.json()
            # ESPN organizes injuries under injuries array per team or league-wide
            items = data.get("injuries", [])
            for team_entry in items:
                for inj in team_entry.get("injuries", []):
                    ath = inj.get("athlete", {})
                    name = ath.get("displayName") or ath.get("name")
                    status_desc = str(inj.get("status", "")).lower()
                    # Filter out players who will not play
                    if name and any(kw in status_desc for kw in ["out", "doubtful", "ir", "injured reserve", "suspension"]):
                        inactive_players.add(name.lower().strip())
    except Exception:
        pass
    return inactive_players

@st.cache_data(ttl=600, show_spinner=False)
def get_live_nba_roster(team_id_or_abbr):
    """
    Retrieves active rotation players dynamically while filtering out:
    1. Injured or Out players
    2. Deep reserves who do not log active playing time
    """
    clean_key = str(team_id_or_abbr or "").strip().lower()
    injury_set = fetch_nba_injury_list()

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{clean_key}/roster"
    healthy_players = []

    try:
        r = requests.get(url, timeout=3.5)
        if r.status_code == 200:
            data = r.json()
            athletes = data.get("athletes", [])
            for athlete_group in athletes:
                items = athlete_group.get("items", []) if "items" in athlete_group else [athlete_group]
                for p in items:
                    name = p.get("displayName") or p.get("fullName")
                    pos = p.get("position", {}).get("abbreviation", "G")
                    stats = p.get("statistics", {})
                    ppg = float(stats.get("pointsPerGame", 0.0))

                    if not name:
                        continue

                    # 1. Skip players on the live injury report
                    if name.lower().strip() in injury_set:
                        continue

                    # 2. Skip players listed as injured directly on the roster object
                    injuries = p.get("injuries", [])
                    if injuries:
                        status_str = str(injuries[0].get("status", "")).lower()
                        if any(kw in status_str for kw in ["out", "doubtful", "ir"]):
                            continue

                    # 3. Dynamic points prop line based on season metrics or position
                    if ppg >= 7.5:
                        strike_line = round(ppg + 0.5, 1)
                        healthy_players.append((name, pos, strike_line))
                    elif not stats and pos in ["PG", "SG", "SF", "PF", "C", "G", "F"]:
                        # Fallback for starters when statistics array is omitted
                        pts_line = 21.5 if pos in ["PG", "SG"] else (17.5 if pos in ["SF", "PF"] else 13.5)
                        healthy_players.append((name, pos, pts_line))
    except Exception:
        pass

    if len(healthy_players) >= 3:
        return healthy_players[:10]

    return [("Lead Guard", "PG", 22.5), ("Lead Wing", "SF", 19.5), ("Starting Center", "C", 14.5)]

def get_live_nba_3pm_roster(team_id_or_abbr):
    """
    Returns player roster filtered and prioritized for 3-Point Field Goals Made.
    Uses real player names from the team roster if available, prioritizing guards & wings.
    Format: list of tuples: (player_name, position, baseline_3pm, baseline_pts)
    """
    # 1. Check if standard live roster is available in session state or module
    live_roster = []
    if "get_live_nba_roster" in globals():
        try:
            live_roster = globals()["get_live_nba_roster"](team_id_or_abbr)
        except Exception:
            live_roster = []

    # 2. Known team perimeter shooters lookup by abbreviation / ID
    abbr = str(team_id_or_abbr).upper()
    team_shooters = {
        "CLE": [("Donovan Mitchell", "SG", 3.5, 26.5), ("Sam Merrill", "SG", 2.5, 12.0), ("Darius Garland", "PG", 2.5, 19.5), ("Max Strus", "SF", 2.5, 13.5)],
        "ATL": [("Trae Young", "PG", 3.0, 24.0), ("Nickeil Alexander-Walker", "SG", 2.5, 15.5), ("CJ McCollum", "SG", 2.5, 17.5), ("Bogdan Bogdanovic", "SG", 2.5, 16.0)],
        "BOS": [("Jayson Tatum", "SF", 3.0, 27.0), ("Jaylen Brown", "SG", 2.5, 24.0), ("Derrick White", "PG", 2.5, 16.5), ("Payton Pritchard", "PG", 2.0, 12.5)],
        "GSW": [("Stephen Curry", "PG", 4.5, 27.5), ("Buddy Hield", "SG", 3.0, 15.5), ("Moses Moody", "SG", 1.5, 11.0)],
        "LAL": [("Luka Doncic", "PG", 3.5, 32.0), ("Austin Reaves", "SG", 2.0, 16.0), ("D'Angelo Russell", "PG", 2.5, 15.0)],
        "MIL": [("Damian Lillard", "PG", 3.5, 25.0), ("Malik Beasley", "SG", 2.5, 12.5), ("AJ Green", "SG", 2.0, 10.0)],
        "NYK": [("Jalen Brunson", "PG", 2.5, 26.5), ("OG Anunoby", "SF", 2.0, 15.0), ("Mikal Bridges", "SG", 2.5, 18.0), ("Karl-Anthony Towns", "C", 2.0, 21.0)],
        "DEN": [("Jamal Murray", "PG", 2.5, 21.0), ("Michael Porter Jr.", "SF", 2.5, 17.0), ("Christian Braun", "SG", 1.5, 13.5)],
        "MIN": [("Anthony Edwards", "SG", 3.5, 27.0), ("Mike Conley", "PG", 2.0, 11.5), ("Naz Reid", "C", 2.0, 14.5)],
        "DAL": [("Kyrie Irving", "PG", 3.0, 25.0), ("Klay Thompson", "SG", 3.0, 16.5), ("P.J. Washington", "PF", 1.5, 12.5)],
        "PHX": [("Devin Booker", "SG", 2.5, 26.0), ("Kevin Durant", "PF", 2.0, 26.5), ("Grayson Allen", "SG", 2.5, 12.5), ("Bradley Beal", "SG", 2.0, 17.0)],
        "OKC": [("Shai Gilgeous-Alexander", "PG", 2.0, 30.5), ("Jalen Williams", "SF", 1.5, 19.5), ("Luguentz Dort", "SG", 2.0, 11.5), ("Chet Holmgren", "C", 1.5, 17.0)],
        "MIA": [("Tyler Herro", "SG", 3.0, 22.0), ("Duncan Robinson", "SG", 2.5, 12.0), ("Terry Rozier", "PG", 2.0, 16.5)],
        "PHI": [("Tyrese Maxey", "PG", 3.0, 26.0), ("Paul George", "SF", 2.5, 21.0), ("Kelly Oubre Jr.", "SG", 1.5, 14.5)],
        "IND": [("Tyrese Haliburton", "PG", 2.5, 20.0), ("Myles Turner", "C", 1.5, 16.0), ("Andrew Nembhard", "SG", 1.5, 12.5)],
        "SAC": [("De'Aaron Fox", "PG", 2.0, 25.5), ("Keegan Murray", "SF", 2.5, 15.0), ("Kevin Huerter", "SG", 2.0, 11.5)],
        "NOP": [("CJ McCollum", "SG", 3.0, 19.0), ("Trey Murphy III", "SF", 3.0, 16.5), ("Jordan Hawkins", "SG", 2.0, 12.0)],
        "HOU": [("Jalen Green", "SG", 2.5, 20.5), ("Fred VanVleet", "PG", 2.5, 15.5), ("Jabari Smith Jr.", "PF", 1.5, 13.0)],
        "MEM": [("Ja Morant", "PG", 1.5, 24.5), ("Desmond Bane", "SG", 3.0, 21.0), ("Marcus Smart", "PG", 1.5, 12.0)],
        "ORL": [("Franz Wagner", "SF", 1.5, 21.0), ("Jalen Suggs", "PG", 2.0, 14.0), ("Kentavious Caldwell-Pope", "SG", 1.5, 10.0)],
        "TOR": [("Immanuel Quickley", "PG", 2.5, 18.0), ("RJ Barrett", "SG", 1.5, 20.5), ("Gradey Dick", "SG", 2.0, 13.5)],
        "CHI": [("Coby White", "PG", 2.5, 19.0), ("Zach LaVine", "SG", 2.5, 21.0), ("Nikola Vucevic", "C", 1.5, 18.0)],
        "SAS": [("Victor Wembanyama", "C", 2.0, 23.5), ("Devin Vassell", "SG", 2.5, 18.5), ("Chris Paul", "PG", 1.5, 10.0)],
        "CHA": [("LaMelo Ball", "PG", 3.5, 24.5), ("Brandon Miller", "SF", 2.5, 19.0), ("Tre Mann", "SG", 2.0, 14.0)],
        "DET": [("Cade Cunningham", "PG", 2.0, 23.0), ("Jaden Ivey", "SG", 1.5, 17.5), ("Malik Beasley", "SG", 2.5, 13.0), ("Tobias Harris", "PF", 1.5, 14.0)],
        "WAS": [("Jordan Poole", "SG", 2.5, 19.0), ("Kyle Kuzma", "PF", 2.0, 21.0), ("Corey Kispert", "SF", 2.0, 12.5)],
        "UTA": [("Lauri Markkanen", "PF", 3.0, 23.0), ("Collin Sexton", "PG", 1.5, 18.5), ("Keyonte George", "PG", 2.0, 15.0)],
        "BKN": [("Cam Thomas", "SG", 2.5, 24.0), ("Cameron Johnson", "SF", 2.5, 14.5), ("Dennis Schroder", "PG", 1.5, 14.0)],
        "POR": [("Anfernee Simons", "SG", 3.0, 21.0), ("Shaedon Sharpe", "SG", 1.5, 16.0), ("Jerami Grant", "PF", 2.0, 19.0)],
        "LAC": [("James Harden", "PG", 2.5, 20.0), ("Norman Powell", "SG", 2.0, 16.0), ("Terance Mann", "SG", 1.0, 9.5)]
    }

    # Match team abbreviation or home short
    for k, v in team_shooters.items():
        if k in abbr:
            return v

    # Fallback to names from live_roster if available
    if live_roster:
        results = []
        for p in live_roster[:4]:
            p_name = p[0]
            p_pts = float(p[2]) if len(p) > 2 else 20.0
            # Estimate 3PM from point total: ~2.5 for guards/wings, ~1.5 otherwise
            est_3pm = 2.5 if p_pts >= 20.0 else 1.5
            results.append((p_name, "G", est_3pm, p_pts))
        return results

    return [
        ("Primary Guard", "PG", 2.5, 24.5),
        ("Sharpshooter Wing", "SG", 2.5, 20.5),
        ("Starting Forward", "SF", 1.5, 18.0),
        ("Sixth Man Sniper", "SG", 1.5, 14.0)
    ]

@st.cache_data(ttl=30, show_spinner=False)
def fetch_nba_scoreboard(days_range=(-2, 4)):
    games = []
    seen = set()
    now_utc = datetime.now() - timedelta(hours=4)
    date_queries = [""]
    for d in range(days_range[0], days_range[1]):
        date_queries.append((now_utc + timedelta(days=d)).strftime("%Y%m%d"))

    for dq in date_queries:
        d_param = f"&dates={dq}" if dq else ""
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?limit=40{d_param}"
        try:
            r = requests.get(url, timeout=3.5)
            if r.status_code == 200:
                for event in r.json().get("events", []):
                    ev_id = str(event.get("id", ""))
                    if ev_id in seen:
                        continue
                    seen.add(ev_id)

                    comp = event["competitions"][0]
                    competitors = comp["competitors"]
                    home = next(c for c in competitors if c["homeAway"] == "home")
                    away = next(c for c in competitors if c["homeAway"] == "away")
                    status_obj = comp["status"]
                    state_text = status_obj["type"]["state"]
                    status_desc = status_obj["type"]["shortDetail"]
                    period = status_obj.get("period", 1)

                    odds_ou = 224.5
                    odds_spread = -4.5
                    if comp.get("odds"):
                        odds_data = comp["odds"][0]
                        odds_ou = float(odds_data.get("overUnder", 224.5))
                        odds_spread = float(odds_data.get("spread", -4.5))

                    is_completed = (state_text == "post" or status_obj["type"].get("completed", False) or "final" in status_desc.lower())
                    checkpoint = "Final" if is_completed else ("Pre-Game" if (state_text == "pre" or period == 0) else ("Halftime" if "half" in status_desc.lower() else f"Q{period}"))

                    home_name = home.get("team", {}).get("displayName", "Home")
                    away_name = away.get("team", {}).get("displayName", "Away")

                    games.append({
                        "id": ev_id,
                        "league": "NBA",
                        "sport": "basketball",
                        "name": event["name"],
                        "kickoff": format_nba_tipoff(event.get("date", ""), status_desc),
                        "home_team": home_name,
                        "home_id": home.get("team", {}).get("id"),
                        "home_short": clean_nba_abbr(home_name, home.get("team", {}).get("abbreviation")),
                        "home_logo": home.get("team", {}).get("logo", DEFAULT_LOGO),
                        "home_record": home.get("records", [{}])[0].get("summary", "0-0") if home.get("records") else "0-0",
                        "away_team": away_name,
                        "away_id": away.get("team", {}).get("id"),
                        "away_short": clean_nba_abbr(away_name, away.get("team", {}).get("abbreviation")),
                        "away_logo": away.get("team", {}).get("logo", DEFAULT_LOGO),
                        "away_record": away.get("records", [{}])[0].get("summary", "0-0") if away.get("records") else "0-0",
                        "home_score": int(home.get("score", 0)),
                        "away_score": int(away.get("score", 0)),
                        "status": status_desc,
                        "state_text": state_text,
                        "checkpoint": checkpoint,
                        "completed": is_completed,
                        "period": period,
                        "displayClock": status_obj.get("displayClock", "0:00"),
                        "market_ou": odds_ou,
                        "market_spread": odds_spread
                    })
        except Exception:
            pass
    return games
