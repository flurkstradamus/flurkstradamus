import requests
import re
from datetime import datetime, timedelta
import streamlit as st
from config import DEFAULT_LOGO, OFFICIAL_ABBR_MAP
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def clean_abbr(team_name, espn_abbr):
    if team_name in OFFICIAL_ABBR_MAP:
        return OFFICIAL_ABBR_MAP[team_name]
    if espn_abbr and espn_abbr.strip():
        clean = espn_abbr.strip().upper()
        if len(clean) <= 5:
            return clean
    words = re.findall(r"[A-Z0-9]", team_name)
    return "".join(words[:4]) if words else "TEAM"

def format_football_kickoff(date_str, fallback_status):
    if not date_str:
        return fallback_status
    try:
        dt = datetime.strptime(date_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M%z")
        dt_et = dt - timedelta(hours=4)
        return dt_et.strftime("%a %m/%d - %I:%M %p ET")
    except Exception:
        return fallback_status

def round_half_point(val):
    try:
        return round(float(val) * 2.0) / 2.0
    except (ValueError, TypeError):
        return 47.5

@st.cache_data(ttl=600)
def get_live_football_roster(team_id_or_abbr, league="NFL"):
    sport_path = "college-football" if "NCAA" in str(league).upper() else "nfl"
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/{sport_path}/teams/{str(team_id_or_abbr).lower()}/roster"
    players = []
    try:
        r = requests.get(url, timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            for athlete in data.get("athletes", []):
                items = athlete.get("items", []) if "items" in athlete else [athlete]
                for p in items:
                    pos = p.get("position", {}).get("abbreviation", "")
                    name = p.get("displayName") or p.get("fullName")
                    if pos in ["QB", "RB", "WR", "TE"] and name:
                        players.append((name, pos))
    except Exception:
        pass

    if not players:
        return [("Lead Running Back", "RB"), ("Top Wideout", "WR"), ("Starting Tight End", "TE")]
    order = {"RB": 0, "WR": 1, "TE": 2, "QB": 3}
    players.sort(key=lambda x: order.get(x[1], 4))
    return players[:6]

def fetch_football_scoreboard(league_filter="NFL", days_range=(-2, 6)):
    games = []
    seen = set()
    now_utc = datetime.now() - timedelta(hours=4)
    date_queries = [""]
    for d in range(days_range[0], days_range[1]):
        date_queries.append((now_utc + timedelta(days=d)).strftime("%Y%m%d"))

    endpoints = []
    for dq in date_queries:
        d_param = f"&dates={dq}" if dq else ""
        if league_filter in ["NFL", "All Games"]:
            endpoints.append(("NFL", f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=50{d_param}"))
        if league_filter in ["NCAA Football", "All Games"]:
            endpoints.append(("NCAA", f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?limit=50&groups=80{d_param}"))

    for l_label, url in endpoints:
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

                    odds_ou = 47.5
                    odds_spread = -3.5
                    if comp.get("odds"):
                        odds_data = comp["odds"][0]
                        odds_ou = float(odds_data.get("overUnder", 47.5))
                        odds_spread = float(odds_data.get("spread", -3.5))

                    is_completed = (state_text == "post" or status_obj["type"].get("completed", False) or "final" in status_desc.lower())
                    checkpoint = "Final" if is_completed else ("Pre-Game" if (state_text == "pre" or period == 0) else ("Halftime" if "half" in status_desc.lower() else f"Q{period}"))

                    home_name = home.get("team", {}).get("displayName", "Home")
                    away_name = away.get("team", {}).get("displayName", "Away")

                    games.append({
                        "id": ev_id,
                        "league": l_label,
                        "sport": "football",
                        "name": event["name"],
                        "kickoff": format_football_kickoff(event.get("date", ""), status_desc),
                        "home_team": home_name,
                        "home_id": home.get("team", {}).get("id"),
                        "home_short": clean_abbr(home_name, home.get("team", {}).get("abbreviation")),
                        "home_logo": home.get("team", {}).get("logo", DEFAULT_LOGO),
                        "home_record": home.get("records", [{}])[0].get("summary", "0-0") if home.get("records") else "0-0",
                        "away_team": away_name,
                        "away_id": away.get("team", {}).get("id"),
                        "away_short": clean_abbr(away_name, away.get("team", {}).get("abbreviation")),
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
