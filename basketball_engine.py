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

@st.cache_data(ttl=600)
def get_live_nba_roster(team_id_or_abbr):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{str(team_id_or_abbr).lower()}/roster"
    players = []
    try:
        r = requests.get(url, timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            for athlete in data.get("athletes", []):
                items = athlete.get("items", []) if "items" in athlete else [athlete]
                for p in items:
                    pos = p.get("position", {}).get("abbreviation", "G")
                    name = p.get("displayName") or p.get("fullName")
                    if pos in ["PG", "SG", "SF", "PF", "C", "G", "F"] and name:
                        pts_line = 24.5 if pos in ["PG", "SG"] else (19.5 if pos in ["SF", "PF"] else 14.5)
                        players.append((name, pos, pts_line))
    except Exception:
        pass

    if not players:
        return [("Lead Guard", "PG", 23.5), ("Lead Wing", "SF", 20.5), ("Starting Big", "C", 14.5)]
    return players[:8]

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
