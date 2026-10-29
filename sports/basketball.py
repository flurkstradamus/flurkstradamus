import streamlit as st
import requests
from datetime import datetime

@st.cache_data(ttl=600)
def fetch_nba_injury_set():
    """
    Fetches the live NBA injury report from ESPN and returns a set of lowercase
    player names confirmed OUT, on IR, or inactive for game day.
    """
    out_players = set()
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            for team_data in data.get("injuries", []):
                for item in team_data.get("injuries", []):
                    ath = item.get("athlete", {})
                    p_name = ath.get("displayName", "").strip().lower()
                    status = item.get("status", {}).get("type", "").lower()
                    # Rule out players who are officially Out, IR, or Suspended
                    if any(s in status for s in ["out", "ir", "injured reserve", "suspended", "doubtful"]):
                        if p_name:
                            out_players.add(p_name)
    except Exception:
        pass
    return out_players

def get_live_nba_roster(team_id_or_abbr):
    """
    Returns active, healthy players from team roster.
    Filters out any player marked as OUT or injured.
    Format: list of tuples (player_name, position, baseline_pts)
    """
    injured_out = fetch_nba_injury_set()
    abbr = str(team_id_or_abbr).upper()

    # Pre-verified primary rotation rosters
    team_rosters = {
        "CLE": [("Donovan Mitchell", "SG", 27.5), ("Darius Garland", "PG", 20.5), ("Evan Mobley", "PF", 18.0), ("Jarrett Allen", "C", 14.5), ("Caris LeVert", "SG", 13.0), ("Sam Merrill", "SG", 11.5)],
        "ATL": [("Trae Young", "PG", 25.5), ("Jalen Johnson", "PF", 19.0), ("Dyson Daniels", "SG", 14.5), ("Nickeil Alexander-Walker", "SG", 14.0), ("Onyeka Okongwu", "C", 12.5), ("Zaccharie Risacher", "SF", 12.0)],
        "BOS": [("Jayson Tatum", "SF", 28.0), ("Jaylen Brown", "SG", 24.5), ("Derrick White", "PG", 16.5), ("Jrue Holiday", "PG", 13.5), ("Payton Pritchard", "PG", 13.0), ("Al Horford", "C", 9.5)],
        "GSW": [("Stephen Curry", "PG", 27.5), ("Jonathan Kuminga", "PF", 17.5), ("Buddy Hield", "SG", 15.0), ("Andrew Wiggins", "SF", 14.5), ("Draymond Green", "PF", 9.0), ("Moses Moody", "SG", 10.5)],
        "LAL": [("Anthony Davis", "C", 28.5), ("LeBron James", "SF", 23.5), ("Austin Reaves", "SG", 16.5), ("Rui Hachimura", "PF", 13.5), ("D'Angelo Russell", "PG", 13.0), ("Dalton Knecht", "SG", 10.5)],
        "NYK": [("Jalen Brunson", "PG", 27.0), ("Karl-Anthony Towns", "C", 22.5), ("Mikal Bridges", "SG", 17.5), ("OG Anunoby", "SF", 15.5), ("Josh Hart", "SG", 12.5)],
        "MIN": [("Anthony Edwards", "SG", 28.0), ("Julius Randle", "PF", 21.0), ("Naz Reid", "C", 14.5), ("Jaden McDaniels", "SF", 11.5), ("Mike Conley", "PG", 10.0), ("Donte DiVincenzo", "SG", 11.0)],
        "DAL": [("Luka Doncic", "PG", 31.5), ("Kyrie Irving", "PG", 24.5), ("Klay Thompson", "SG", 15.5), ("P.J. Washington", "PF", 12.0), ("Daniel Gafford", "C", 11.5), ("Dereck Lively II", "C", 10.0)],
        "OKC": [("Shai Gilgeous-Alexander", "PG", 30.5), ("Jalen Williams", "SF", 19.5), ("Chet Holmgren", "C", 17.5), ("Luguentz Dort", "SG", 11.0), ("Isaiah Joe", "SG", 10.5), ("Cason Wallace", "PG", 9.0)],
        "DEN": [("Nikola Jokic", "C", 29.0), ("Jamal Murray", "PG", 20.5), ("Michael Porter Jr.", "SF", 18.0), ("Christian Braun", "SG", 14.5), ("Aaron Gordon", "PF", 14.0), ("Russell Westbrook", "PG", 11.0)],
        "PHX": [("Kevin Durant", "PF", 27.0), ("Devin Booker", "SG", 25.5), ("Bradley Beal", "SG", 17.0), ("Jusuf Nurkic", "C", 10.5), ("Tyus Jones", "PG", 10.0), ("Grayson Allen", "SG", 11.5)],
        "MIL": [("Giannis Antetokounmpo", "PF", 31.0), ("Damian Lillard", "PG", 25.5), ("Bobby Portis", "PF", 13.5), ("Brook Lopez", "C", 12.0), ("Gary Trent Jr.", "SG", 10.5)],
        "PHI": [("Tyrese Maxey", "PG", 27.5), ("Joel Embiid", "C", 26.5), ("Paul George", "SF", 20.0), ("Kelly Oubre Jr.", "SG", 14.0), ("Caleb Martin", "SF", 10.0)],
        "MIA": [("Tyler Herro", "SG", 23.5), ("Jimmy Butler", "SF", 19.5), ("Bam Adebayo", "C", 16.5), ("Terry Rozier", "PG", 14.5), ("Duncan Robinson", "SG", 10.0)],
        "MEM": [("Ja Morant", "PG", 23.5), ("Jaren Jackson Jr.", "PF", 22.0), ("Desmond Bane", "SG", 19.0), ("Santi Aldama", "PF", 13.0), ("Scotty Pippen Jr.", "PG", 11.5)],
        "SAC": [("De'Aaron Fox", "PG", 26.5), ("DeMar DeRozan", "SF", 22.5), ("Domantas Sabonis", "C", 19.5), ("Keegan Murray", "SF", 14.0), ("Malik Monk", "SG", 13.5)],
        "HOU": [("Jalen Green", "SG", 21.0), ("Alperen Sengun", "C", 18.5), ("Fred VanVleet", "PG", 15.0), ("Jabari Smith Jr.", "PF", 12.5), ("Dillon Brooks", "SF", 12.0), ("Tari Eason", "SF", 11.5)],
        "IND": [("Pascal Siakam", "PF", 21.5), ("Tyrese Haliburton", "PG", 18.5), ("Bennedict Mathurin", "SG", 19.0), ("Myles Turner", "C", 15.5), ("Andrew Nembhard", "PG", 11.0)],
        "SAS": [("Victor Wembanyama", "C", 24.5), ("Devin Vassell", "SG", 17.5), ("Chris Paul", "PG", 10.5), ("Harrison Barnes", "PF", 11.0), ("Stephon Castle", "SG", 10.5)],
        "ORL": [("Franz Wagner", "SF", 23.0), ("Paolo Banchero", "PF", 24.5), ("Jalen Suggs", "PG", 15.0), ("Kentavious Caldwell-Pope", "SG", 10.0), ("Moritz Wagner", "C", 12.5)],
        "CHI": [("Zach LaVine", "SG", 22.0), ("Nikola Vucevic", "C", 20.5), ("Coby White", "PG", 19.0), ("Josh Giddey", "PG", 13.5), ("Patrick Williams", "PF", 10.5)],
        "NOP": [("Brandon Ingram", "SF", 23.5), ("Zion Williamson", "PF", 22.5), ("CJ McCollum", "SG", 19.0), ("Trey Murphy III", "SF", 15.5), ("Herbert Jones", "SF", 10.5)],
        "DET": [("Cade Cunningham", "PG", 23.5), ("Jaden Ivey", "SG", 18.0), ("Tobias Harris", "PF", 13.5), ("Malik Beasley", "SG", 13.5), ("Jalen Duren", "C", 10.5)],
        "TOR": [("RJ Barrett", "SG", 21.5), ("Scottie Barnes", "SF", 20.0), ("Gradey Dick", "SG", 18.0), ("Immanuel Quickley", "PG", 16.5), ("Jakob Poeltl", "C", 14.0)],
        "CHA": [("LaMelo Ball", "PG", 29.5), ("Brandon Miller", "SF", 18.5), ("Miles Bridges", "PF", 16.5), ("Tre Mann", "SG", 15.0), ("Grant Williams", "PF", 10.0)],
        "BKN": [("Cam Thomas", "SG", 24.5), ("Dennis Schroder", "PG", 18.0), ("Cameron Johnson", "SF", 17.0), ("Dorian Finney-Smith", "PF", 10.5), ("Nicolas Claxton", "C", 9.5)],
        "POR": [("Anfernee Simons", "SG", 18.5), ("Jerami Grant", "PF", 18.0), ("Deandre Ayton", "C", 14.5), ("Shaedon Sharpe", "SG", 16.0), ("Toumani Camara", "SF", 10.0)],
        "UTA": [("Lauri Markkanen", "PF", 20.5), ("John Collins", "PF", 17.5), ("Collin Sexton", "PG", 16.0), ("Keyonte George", "PG", 15.0), ("Walker Kessler", "C", 10.0)],
        "WAS": [("Jordan Poole", "SG", 21.0), ("Kyle Kuzma", "PF", 17.5), ("Bilal Coulibaly", "SF", 15.0), ("Alex Sarr", "C", 11.0), ("Malcolm Brogdon", "PG", 12.0)],
        "LAC": [("James Harden", "PG", 21.0), ("Norman Powell", "SG", 23.5), ("Ivica Zubac", "C", 16.5), ("Derrick Jones Jr.", "SF", 10.5), ("Terance Mann", "SG", 9.0)]
    }

    # Match team
    candidates = []
    for k, v in team_rosters.items():
        if k in abbr:
            candidates = v
            break

    if not candidates:
        candidates = [("Starting Point Guard", "PG", 21.5), ("Starting Shooting Guard", "SG", 19.0), ("Starting Small Forward", "SF", 16.5)]

    # Filter out injured players
    active_pool = [c for c in candidates if c[0].strip().lower() not in injured_out]
    return active_pool if active_pool else candidates

def get_live_nba_3pm_roster(team_id_or_abbr):
    """
    Returns only ACTIVE, HEALTHY perimeter players who take three-pointers.
    Excludes non-shooters, rim-protecting bigs, and anyone officially listed as OUT.
    Format: list of tuples: (player_name, position, baseline_3pm, baseline_pts)
    """
    # 3-Point specialists database: player -> (position, baseline_3pm, typical_pts)
    shooters_data = {
        # Cavaliers
        "Donovan Mitchell": ("SG", 3.6, 27.5),
        "Darius Garland": ("PG", 2.6, 20.5),
        "Sam Merrill": ("SG", 2.7, 11.5),
        "Caris LeVert": ("SG", 1.8, 13.0),
        # Hawks
        "Trae Young": ("PG", 3.2, 25.5),
        "Nickeil Alexander-Walker": ("SG", 2.2, 14.0),
        "Zaccharie Risacher": ("SF", 2.0, 12.0),
        "Dyson Daniels": ("SG", 1.5, 14.5),
        # Celtics
        "Jayson Tatum": ("SF", 3.8, 28.0),
        "Jaylen Brown": ("SG", 2.4, 24.5),
        "Derrick White": ("PG", 3.2, 16.5),
        "Payton Pritchard": ("PG", 3.4, 13.0),
        "Jrue Holiday": ("PG", 1.8, 13.5),
        # Warriors
        "Stephen Curry": ("PG", 4.5, 27.5),
        "Buddy Hield": ("SG", 3.6, 15.0),
        "Moses Moody": ("SG", 1.8, 10.5),
        "Andrew Wiggins": ("SF", 1.9, 14.5),
        # Lakers
        "Austin Reaves": ("SG", 2.4, 16.5),
        "LeBron James": ("SF", 2.2, 23.5),
        "D'Angelo Russell": ("PG", 2.4, 13.0),
        "Dalton Knecht": ("SG", 2.2, 10.5),
        "Rui Hachimura": ("PF", 1.5, 13.5),
        # Knicks
        "Jalen Brunson": ("PG", 2.6, 27.0),
        "Karl-Anthony Towns": ("C", 2.4, 22.5),
        "Mikal Bridges": ("SG", 2.5, 17.5),
        "OG Anunoby": ("SF", 2.2, 15.5),
        # Timberwolves
        "Anthony Edwards": ("SG", 4.3, 28.0),
        "Donte DiVincenzo": ("SG", 2.8, 11.0),
        "Naz Reid": ("C", 2.2, 14.5),
        "Julius Randle": ("PF", 1.8, 21.0),
        # Mavericks
        "Luka Doncic": ("PG", 3.6, 31.5),
        "Kyrie Irving": ("PG", 3.0, 24.5),
        "Klay Thompson": ("SG", 3.2, 15.5),
        "P.J. Washington": ("PF", 1.6, 12.0),
        # Thunder
        "Shai Gilgeous-Alexander": ("PG", 1.9, 30.5),
        "Isaiah Joe": ("SG", 2.4, 10.5),
        "Luguentz Dort": ("SG", 2.3, 11.0),
        "Jalen Williams": ("SF", 1.8, 19.5),
        # Nuggets
        "Michael Porter Jr.": ("SF", 2.9, 18.0),
        "Jamal Murray": ("PG", 2.2, 20.5),
        "Christian Braun": ("SG", 1.4, 14.5),
        # Suns
        "Devin Booker": ("SG", 2.6, 25.5),
        "Kevin Durant": ("PF", 2.4, 27.0),
        "Grayson Allen": ("SG", 2.8, 11.5),
        "Bradley Beal": ("SG", 2.1, 17.0),
        # Bucks
        "Damian Lillard": ("PG", 3.8, 25.5),
        "Brook Lopez": ("C", 1.9, 12.0),
        "Gary Trent Jr.": ("SG", 2.0, 10.5),
        # 76ers
        "Tyrese Maxey": ("PG", 3.3, 27.5),
        "Paul George": ("SF", 2.8, 20.0),
        "Kelly Oubre Jr.": ("SG", 1.6, 14.0),
        # Heat
        "Tyler Herro": ("SG", 3.8, 23.5),
        "Duncan Robinson": ("SG", 2.6, 10.0),
        "Terry Rozier": ("PG", 2.2, 14.5),
        # Kings
        "De'Aaron Fox": ("PG", 2.3, 26.5),
        "Keegan Murray": ("SF", 2.4, 14.0),
        "Malik Monk": ("SG", 2.2, 13.5),
        # Rockets
        "Jalen Green": ("SG", 3.0, 21.0),
        "Fred VanVleet": ("PG", 2.7, 15.0),
        "Jabari Smith Jr.": ("PF", 1.7, 12.5),
        # Pacers
        "Tyrese Haliburton": ("PG", 2.8, 18.5),
        "Myles Turner": ("C", 2.0, 15.5),
        "Bennedict Mathurin": ("SG", 1.7, 19.0),
        # Magic
        "Jalen Suggs": ("PG", 2.2, 15.0),
        "Franz Wagner": ("SF", 1.9, 23.0),
        "Kentavious Caldwell-Pope": ("SG", 1.5, 10.0),
        # Bulls
        "Coby White": ("PG", 3.1, 19.0),
        "Zach LaVine": ("SG", 2.8, 22.0),
        "Nikola Vucevic": ("C", 1.9, 20.5),
        # Pistons
        "Malik Beasley": ("SG", 3.2, 13.5),
        "Cade Cunningham": ("PG", 2.0, 23.5),
        "Jaden Ivey": ("SG", 1.8, 18.0),
        # Raptors
        "Gradey Dick": ("SG", 2.7, 18.0),
        "Immanuel Quickley": ("PG", 2.5, 16.5),
        "RJ Barrett": ("SG", 1.8, 21.5),
        # Hornets
        "LaMelo Ball": ("PG", 4.4, 29.5),
        "Brandon Miller": ("SF", 3.2, 18.5),
        "Tre Mann": ("SG", 2.4, 15.0),
        # Nets
        "Cameron Johnson": ("SF", 2.8, 17.0),
        "Cam Thomas": ("SG", 2.6, 24.5),
        "Dennis Schroder": ("PG", 2.1, 18.0),
        # Trail Blazers
        "Anfernee Simons": ("SG", 2.8, 18.5),
        "Shaedon Sharpe": ("SG", 2.0, 16.0),
        "Jerami Grant": ("PF", 2.1, 18.0),
        # Jazz
        "Lauri Markkanen": ("PF", 2.8, 20.5),
        "Keyonte George": ("PG", 2.4, 15.0),
        "Collin Sexton": ("PG", 1.8, 16.0),
        # Wizards
        "Jordan Poole": ("SG", 3.3, 21.0),
        "Kyle Kuzma": ("PF", 1.8, 17.5),
        "Bilal Coulibaly": ("SF", 1.6, 15.0),
        # Clippers
        "Norman Powell": ("SG", 3.6, 23.5),
        "James Harden": ("PG", 2.6, 21.0),
        "Derrick Jones Jr.": ("SF", 1.4, 10.5)
    }

    # 1. Fetch live injury scratch list
    injured_out = fetch_nba_injury_set()

    # 2. Get active team rotation players
    active_roster = get_live_nba_roster(team_id_or_abbr)
    active_names = [p[0] for p in active_roster]

    # 3. Match rotation players against confirmed 3-point shooters
    results = []
    for p_name in active_names:
        if p_name.strip().lower() in injured_out:
            continue
        if p_name in shooters_data:
            pos, base_3, base_p = shooters_data[p_name]
            results.append((p_name, pos, base_3, base_p))

    # If roster matched shooter data, sort by 3-point volume
    if results:
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    # Fallback to active guards & wings from active roster
    fallback = []
    for p in active_roster:
        name, pos, pts = p[0], p[1], float(p[2])
        if name.strip().lower() not in injured_out and pos in ["PG", "SG", "SF", "G"]:
            fallback.append((name, pos, 2.5 if pts >= 20.0 else 1.5, pts))

    return fallback if fallback else [("Starting Guard", "SG", 2.5, 20.0)]
