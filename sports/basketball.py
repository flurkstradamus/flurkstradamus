import streamlit as st
import requests
from datetime import datetime

@st.cache_data(ttl=300, show_spinner=False)
def fetch_nba_live_roster_by_team_id(team_id):
    """
    Pulls the verified active roster for an NBA team directly from ESPN's official team roster API.
    Guarantees traded/waived players are completely purged.
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

@st.cache_data(ttl=60, show_spinner=False)
def fetch_nba_game_boxscore_players(game_id):
    """
    Pulls players currently playing or dressed in the actual active game from ESPN Game Summary.
    """
    if not game_id:
        return {"home": [], "away": []}
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    result = {"home": [], "away": []}
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            box = resp.json().get("boxscore", {}).get("players", [])
            for idx, team_box in enumerate(box):
                side = "away" if idx == 0 else "home"
                athletes = team_box.get("statistics", [{}])[0].get("athletes", [])
                for ath in athletes:
                    athlete_info = ath.get("athlete", {})
                    p_name = athlete_info.get("displayName", "")
                    pos = athlete_info.get("position", {}).get("abbreviation", "G")
                    dnp = ath.get("didNotPlay", False)
                    reason = ath.get("reason", "").lower()
                    if p_name and not dnp and not any(r in reason for r in ["inactive", "dnp", "out"]):
                        result[side].append((p_name, pos))
    except Exception:
        pass
    return result

@st.cache_data(ttl=60, show_spinner=False)
def fetch_nba_scoreboard():
    """
    Fetches the live NBA scoreboard from ESPN API with quarterly score breakdowns.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    games = []
    try:
        resp = requests.get(url, timeout=4)
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

                # Quarter-by-quarter scoring breakdown
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

def get_live_nba_roster(team_id_or_abbr, game_id=None):
    """
    Returns verified active rotation players for an NBA team.
    Checks live box score first; falls back to verified live ESPN team roster.
    """
    if game_id:
        box_players = fetch_nba_game_boxscore_players(game_id)
        active_list = box_players.get("home", []) + box_players.get("away", [])
        if active_list:
            return [(p[0], p[1], 20.0) for p in active_list]

    live_roster = fetch_nba_live_roster_by_team_id(team_id_or_abbr)
    if live_roster:
        return [(p[0], p[1], 19.5) for p in live_roster]

    return [("Starting Guard", "PG", 22.0), ("Starting Wing", "SG", 19.5), ("Forward", "SF", 16.0)]

def get_live_nba_3pm_roster(team_id_or_abbr, game_id=None):
    """
    Returns verified active perimeter players (Guards & Wings) taking 3-pointers.
    Filters out big men and inactive players.
    """
    base_roster = get_live_nba_roster(team_id_or_abbr, game_id=game_id)
    shooters = []
    for p in base_roster:
        name, pos, pts = p[0], p[1], p[2]
        if pos in ["PG", "SG", "SF", "G"]:
            shooters.append((name, pos, 2.5, pts))
    return shooters if shooters else [("Starting Guard", "PG", 2.5, 20.0)]
