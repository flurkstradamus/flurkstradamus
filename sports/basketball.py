import streamlit as st
import requests
from datetime import datetime

# =========================================================================
# 1. VERIFIED NBA ROTATIONAL STARTERS & PERIMETER SHOOTERS
# =========================================================================
ESTABLISHED_ROTATION_SHOOTERS = {
    # Washington Wizards (ESPN Team ID: 27)
    "WSH": [
        ("Jordan Poole", "SG", 2.5, 21.5),
        ("Bub Carrington", "PG", 1.5, 12.5),
        ("Corey Kispert", "SF", 2.0, 13.0),
        ("Kyle Kuzma", "PF", 1.5, 18.5),
        ("Bilal Coulibaly", "SG", 1.5, 14.5),
        ("Alex Sarr", "C", 1.0, 13.5),
    ],
    # Charlotte Hornets (ESPN Team ID: 30)
    "CHA": [
        ("LaMelo Ball", "PG", 3.5, 25.5),
        ("Brandon Miller", "SF", 2.5, 19.5),
        ("Miles Bridges", "PF", 1.5, 17.5),
        ("Tre Mann", "SG", 2.0, 15.5),
        ("Grant Williams", "PF", 1.5, 10.5),
        ("Seth Curry", "SG", 1.5, 8.5),
    ],
    # Boston Celtics (ESPN Team ID: 2)
    "BOS": [
        ("Jayson Tatum", "SF", 3.5, 28.5),
        ("Jaylen Brown", "SG", 2.5, 24.5),
        ("Derrick White", "PG", 2.5, 16.5),
        ("Jrue Holiday", "PG", 1.5, 13.5),
        ("Payton Pritchard", "PG", 2.5, 14.5),
    ],
    # New York Knicks (ESPN Team ID: 18)
    "NYK": [
        ("Jalen Brunson", "PG", 2.5, 27.5),
        ("Mikal Bridges", "SG", 2.5, 18.5),
        ("Karl-Anthony Towns", "C", 2.0, 22.5),
        ("OG Anunoby", "SF", 1.5, 15.5),
        ("Josh Hart", "SG", 1.5, 12.5),
    ],
    # Los Angeles Lakers (ESPN Team ID: 13)
    "LAL": [
        ("Anthony Davis", "C", 0.5, 27.5),
        ("LeBron James", "SF", 2.0, 23.5),
        ("Austin Reaves", "SG", 2.0, 17.5),
        ("D'Angelo Russell", "PG", 2.5, 15.5),
        ("Rui Hachimura", "PF", 1.5, 14.5),
    ],
    # Golden State Warriors (ESPN Team ID: 9)
    "GSW": [
        ("Stephen Curry", "PG", 4.5, 27.5),
        ("Buddy Hield", "SG", 3.0, 16.5),
        ("Jonathan Kuminga", "SF", 1.0, 16.5),
        ("Andrew Wiggins", "SF", 1.5, 15.5),
        ("Brandin Podziemski", "SG", 1.5, 11.5),
    ],
    # Phoenix Suns (ESPN Team ID: 21)
    "PHX": [
        ("Kevin Durant", "PF", 2.0, 26.5),
        ("Devin Booker", "SG", 2.5, 25.5),
        ("Bradley Beal", "SG", 1.5, 17.5),
        ("Tyus Jones", "PG", 1.5, 11.5),
        ("Grayson Allen", "SG", 2.0, 11.5),
    ],
    # Dallas Mavericks (ESPN Team ID: 6)
    "DAL": [
        ("Luka Doncic", "PG", 3.5, 30.5),
        ("Kyrie Irving", "SG", 2.5, 24.5),
        ("Klay Thompson", "SG", 2.5, 15.5),
        ("P.J. Washington", "PF", 1.5, 12.5),
    ],
    # Denver Nuggets (ESPN Team ID: 7)
    "DEN": [
        ("Nikola Jokic", "C", 1.5, 26.5),
        ("Jamal Murray", "PG", 2.5, 21.5),
        ("Michael Porter Jr.", "SF", 2.5, 18.5),
        ("Christian Braun", "SG", 1.5, 14.5),
        ("Russell Westbrook", "PG", 1.0, 12.5),
    ],
    # Milwaukee Bucks (ESPN Team ID: 15)
    "MIL": [
        ("Giannis Antetokounmpo", "PF", 0.5, 31.5),
        ("Damian Lillard", "PG", 3.5, 25.5),
        ("Brook Lopez", "C", 1.5, 12.5),
        ("Bobby Portis", "PF", 1.5, 13.5),
        ("Gary Trent Jr.", "SG", 2.0, 11.5),
    ],
    # Philadelphia 76ers (ESPN Team ID: 20)
    "PHI": [
        ("Tyrese Maxey", "PG", 3.0, 27.5),
        ("Paul George", "SF", 2.5, 21.5),
        ("Joel Embiid", "C", 1.0, 28.5),
        ("Kelly Oubre Jr.", "SF", 1.5, 14.5),
    ],
    # Cleveland Cavaliers (ESPN Team ID: 5)
    "CLE": [
        ("Donovan Mitchell", "SG", 3.0, 26.5),
        ("Darius Garland", "PG", 2.5, 20.5),
        ("Evan Mobley", "PF", 0.5, 18.5),
        ("Caris LeVert", "SG", 1.5, 12.5),
    ],
    # Minnesota Timberwolves (ESPN Team ID: 16)
    "MIN": [
        ("Anthony Edwards", "SG", 3.5, 27.5),
        ("Julius Randle", "PF", 1.5, 21.5),
        ("Naz Reid", "C", 2.0, 15.5),
        ("Jaden McDaniels", "SF", 1.5, 11.5),
        ("Mike Conley", "PG", 1.5, 10.5),
    ],
    # Oklahoma City Thunder (ESPN Team ID: 25)
    "OKC": [
        ("Shai Gilgeous-Alexander", "PG", 2.0, 29.5),
        ("Jalen Williams", "SF", 1.5, 20.5),
        ("Chet Holmgren", "C", 1.5, 18.5),
        ("Luguentz Dort", "SG", 1.5, 11.5),
        ("Isaiah Joe", "SG", 2.0, 10.5),
    ],
}

# Mapping numeric ESPN Team IDs and alternative names to abbreviations
TEAM_ID_MAP = {
    "27": "WSH", "WAS": "WSH", "WIZARDS": "WSH", "WASHINGTON": "WSH",
    "30": "CHA", "HORNETS": "CHA", "CHARLOTTE": "CHA",
    "2": "BOS", "CELTICS": "BOS", "BOSTON": "BOS",
    "18": "NYK", "KNICKS": "NYK", "NEW YORK": "NYK",
    "13": "LAL", "LAKERS": "LAL",
    "9": "GSW", "WARRIORS": "GSW", "GOLDEN STATE": "GSW",
    "21": "PHX", "SUNS": "PHX", "PHOENIX": "PHX",
    "6": "DAL", "MAVERICKS": "DAL", "DALLAS": "DAL",
    "7": "DEN", "NUGGETS": "DEN", "DENVER": "DEN",
    "15": "MIL", "BUCKS": "MIL", "MILWAUKEE": "MIL",
    "20": "PHI", "76ERS": "PHI", "SIXERS": "PHI", "PHILADELPHIA": "PHI",
    "5": "CLE", "CAVALIERS": "CLE", "CAVS": "CLE", "CLEVELAND": "CLE",
    "16": "MIN", "TIMBERWOLVES": "MIN", "MINNESOTA": "MIN",
    "25": "OKC", "THUNDER": "OKC", "OKLAHOMA CITY": "OKC",
}

# Blacklist known Two-Way / G-League players that do not have prop markets on sportsbooks/Robinhood
NON_MARKET_PLAYERS = {
    "reece beekman", "trevor keels", "chris livingston", 
    "steve settle iii", "keshawn murphy", "jared butler",
    "tristan vukcevic", "anthony gill", "colin castleton",
    "leaky black", "amari bailey", "marquese chriss"
}

def resolve_team_key(team_id_or_abbr):
    """Normalizes team ID numbers or names into standard abbreviations."""
    raw = str(team_id_or_abbr).upper().strip()
    if raw in TEAM_ID_MAP:
        return TEAM_ID_MAP[raw]
    for k, v in TEAM_ID_MAP.items():
        if k in raw:
            return v
    for k in ESTABLISHED_ROTATION_SHOOTERS.keys():
        if k in raw:
            return k
    return raw

# =========================================================================
# 2. ESPN DATA SCRAPERS & INJURY FILTERS
# =========================================================================

@st.cache_data(ttl=600, show_spinner=False)
def fetch_nba_injury_set():
    """
    Fetches the live NBA injury report from ESPN.
    Returns a set of lowercase player names confirmed OUT or on IR.
    """
    out_players = set()
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            for team_data in data.get("injuries", []):
                for item in team_data.get("injuries", []):
                    ath = item.get("athlete", {})
                    p_name = ath.get("displayName", "").strip().lower()
                    status = item.get("status", {}).get("type", "").lower()
                    if any(s in status for s in ["out", "ir", "injured reserve", "suspended", "doubtful"]):
                        if p_name:
                            out_players.add(p_name)
    except Exception:
        pass
    return out_players

@st.cache_data(ttl=60, show_spinner=False)
def fetch_nba_scoreboard():
    """
    Fetches the live NBA scoreboard from ESPN API with quarterly linescores.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    games = []
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            events = resp.json().get("events", [])
            for ev in events:
                comp = ev.get("competitions", [{}])[0]
                status_obj = ev.get("status", {})
                competitors = comp.get("competitors", [])

                home_team, away_team = {}, {}
                for c in competitors:
                    if c.get("homeAway") == "home":
                        home_team = c
                    else:
                        away_team = c

                h_name = home_team.get("team", {}).get("displayName", "Home Team")
                a_name = away_team.get("team", {}).get("displayName", "Away Team")
                h_short = home_team.get("team", {}).get("abbreviation", "HOME")
                a_short = away_team.get("team", {}).get("abbreviation", "AWAY")
                h_logo = home_team.get("team", {}).get("logo", "")
                a_logo = away_team.get("team", {}).get("logo", "")

                try:
                    h_score = int(home_team.get("score", 0))
                    a_score = int(away_team.get("score", 0))
                except (ValueError, TypeError):
                    h_score, a_score = 0, 0

                h_lines = [int(p.get("value", 0)) for p in home_team.get("linescores", [])]
                a_lines = [int(p.get("value", 0)) for p in away_team.get("linescores", [])]

                state_text = status_obj.get("type", {}).get("state", "pre")
                completed = status_obj.get("type", {}).get("completed", False)
                period = status_obj.get("period", 0)
                clock = status_obj.get("displayClock", "")

                odds = comp.get("odds", [{}])[0] if comp.get("odds") else {}
                market_spread = -3.5
                market_ou = 224.5

                if "overUnder" in odds:
                    try:
                        market_ou = float(odds["overUnder"])
                    except (ValueError, TypeError):
                        pass

                details_spd = odds.get("details", "")
                if details_spd and ("-" in details_spd or "+" in details_spd):
                    try:
                        parts = details_spd.split()
                        market_spread = float(parts[-1])
                    except Exception:
                        pass

                raw_date = ev.get("date", "")
                kickoff_str = "Scheduled"
                if raw_date:
                    try:
                        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        kickoff_str = dt.strftime("%a %m/%d - %I:%M %p ET")
                    except Exception:
                        kickoff_str = "Upcoming"

                games.append({
                    "id": str(ev.get("id")),
                    "league": "NBA",
                    "home_id": home_team.get("id", h_short),
                    "away_id": away_team.get("id", a_short),
                    "home_team": h_name,
                    "away_team": a_name,
                    "home_short": h_short,
                    "away_short": a_short,
                    "home_logo": h_logo,
                    "away_logo": a_logo,
                    "home_score": h_score,
                    "away_score": a_score,
                    "home_linescores": h_lines,
                    "away_linescores": a_lines,
                    "home_record": home_team.get("records", [{}])[0].get("summary", "0-0") if home_team.get("records") else "0-0",
                    "away_record": away_team.get("records", [{}])[0].get("summary", "0-0") if away_team.get("records") else "0-0",
                    "market_ou": market_ou,
                    "market_spread": market_spread,
                    "state_text": state_text,
                    "completed": completed,
                    "period": period,
                    "clock": clock,
                    "kickoff": kickoff_str
                })
    except Exception:
        pass
    return games

@st.cache_data(ttl=300, show_spinner=False)
def fetch_nba_live_roster_by_team_id(team_id):
    """
    Pulls the active roster from ESPN's official team endpoint and filters
    out two-way contracts, non-roster invites, and injured players.
    """
    if not team_id or str(team_id) in ["None", "HOME", "AWAY"]:
        return []
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
    roster = []
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            athletes = resp.json().get("athletes", [])
            for a in athletes:
                name = a.get("displayName", "")
                pos = a.get("position", {}).get("abbreviation", "G")
                
                # Check for two-way or inactive contract designations
                contract_type = str(a.get("contract", {}).get("salary", "")).lower()
                status_desc = str(a.get("status", {}).get("type", "")).lower()
                is_two_way = ("two-way" in status_desc) or ("g league" in status_desc) or ("two-way" in contract_type)

                if is_two_way or name.strip().lower() in NON_MARKET_PLAYERS:
                    continue

                injured = a.get("injuries", [])
                is_out = False
                for inj in injured:
                    status = inj.get("status", "").lower()
                    if any(s in status for s in ["out", "ir", "doubtful", "suspended"]):
                        is_out = True
                        break

                if name and not is_out:
                    roster.append((name, pos))
    except Exception:
        pass
    return roster

# =========================================================================
# 3. ROSTER RESOLUTION FUNCTIONS
# =========================================================================

def get_live_nba_roster(team_id_or_abbr, game_id=None):
    """
    Returns verified active rotation players for an NBA team.
    Prioritizes known rotation starters; falls back to filtered active ESPN roster.
    """
    team_key = resolve_team_key(team_id_or_abbr)
    injury_set = fetch_nba_injury_set()

    # 1. Match against known team rotation tables
    if team_key in ESTABLISHED_ROTATION_SHOOTERS:
        valid = [
            (p[0], p[1], p[3])
            for p in ESTABLISHED_ROTATION_SHOOTERS[team_key]
            if p[0].strip().lower() not in injury_set and p[0].strip().lower() not in NON_MARKET_PLAYERS
        ]
        if valid:
            return valid

    # 2. Dynamic scrape fallback with strict injury and status filtering
    dynamic_roster = fetch_nba_live_roster_by_team_id(team_id_or_abbr)
    if dynamic_roster:
        valid = []
        for p in dynamic_roster:
            p_name, pos = p[0], p[1]
            if p_name.strip().lower() not in injury_set and p_name.strip().lower() not in NON_MARKET_PLAYERS:
                valid.append((p_name, pos, 17.5))
        if valid:
            return valid

    return [
        ("Jordan Poole", "SG", 21.5),
        ("Kyle Kuzma", "PF", 18.5),
        ("LaMelo Ball", "PG", 25.5)
    ]

def get_live_nba_3pm_roster(team_id_or_abbr, game_id=None):
    """
    Returns verified perimeter rotation players (Guards & Wings) with active 3PM volume.
    Excludes deep reserves and two-way players who don't have prop markets.
    """
    team_key = resolve_team_key(team_id_or_abbr)
    injury_set = fetch_nba_injury_set()

    # 1. Match against known rotation perimeter shooters
    if team_key in ESTABLISHED_ROTATION_SHOOTERS:
        healthy_shooters = [
            (p[0], p[1], p[2], p[3])
            for p in ESTABLISHED_ROTATION_SHOOTERS[team_key]
            if p[0].strip().lower() not in injury_set 
            and p[0].strip().lower() not in NON_MARKET_PLAYERS 
            and p[1] in ["PG", "SG", "SF", "G", "F"]
        ]
        if healthy_shooters:
            return healthy_shooters

    # 2. Dynamic fallback
    base_roster = get_live_nba_roster(team_id_or_abbr, game_id=game_id)
    shooters = []
    for p in base_roster:
        name, pos, pts = p[0], p[1], p[2]
        if pos in ["PG", "SG", "SF", "G"] and name.strip().lower() not in NON_MARKET_PLAYERS:
            shooters.append((name, pos, 2.5, pts))
            
    return shooters if shooters else [
        ("Jordan Poole", "SG", 2.5, 21.5),
        ("Bub Carrington", "PG", 1.5, 12.5)
    ]
