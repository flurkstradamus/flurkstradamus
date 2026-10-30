import requests
from datetime import datetime

def sync_season_historical_games(league="NFL", season_year=2026):
    """
    Pulls completed games and box score line scores directly from ESPN
    for the current season to populate the Learning Lab.
    """
    snapshots = load_game_snapshots()
    existing_ids = {s.get("game_id") for s in snapshots}
    
    league_code = "football/nfl" if league.upper() == "NFL" else "basketball/nba"
    
    # ESPN allows querying recent scoreboard dates or past weeks
    # For NBA: Queries recent days; For NFL: Queries past regular season weeks
    new_games_added = 0

    if league.upper() == "NFL":
        # Check weeks 1 through 18
        for wk in range(1, 19):
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype=2&week={wk}"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    events = resp.json().get("events", [])
                    for ev in events:
                        g_id = str(ev.get("id"))
                        status_obj = ev.get("status", {})
                        is_completed = status_obj.get("type", {}).get("completed", False)
                        
                        # Only ingest completed past games or update existing ones
                        if not is_completed:
                            continue

                        comp = ev.get("competitions", [{}])[0]
                        competitors = comp.get("competitors", [])
                        
                        home_t, away_t = {}, {}
                        for c in competitors:
                            if c.get("homeAway") == "home":
                                home_t = c
                            else:
                                away_t = c

                        h_name = home_t.get("team", {}).get("displayName", "Home")
                        a_name = away_t.get("team", {}).get("displayName", "Away")
                        h_short = home_t.get("team", {}).get("abbreviation", "HOME")
                        a_short = away_t.get("team", {}).get("abbreviation", "AWAY")
                        h_logo = home_t.get("team", {}).get("logo", "")
                        a_logo = away_t.get("team", {}).get("logo", "")

                        try:
                            h_score = int(home_t.get("score", 0))
                            a_score = int(away_t.get("score", 0))
                        except (ValueError, TypeError):
                            h_score, a_score = 0, 0

                        h_lines = [int(p.get("value", 0)) for p in home_t.get("linescores", [])]
                        a_lines = [int(p.get("value", 0)) for p in away_t.get("linescores", [])]

                        # Check odds if available
                        odds = comp.get("odds", [{}])[0] if comp.get("odds") else {}
                        market_ou = 46.5
                        market_spread = -3.5
                        if "overUnder" in odds:
                            try: market_ou = float(odds["overUnder"])
                            except: pass

                        # Build checkpoints from line scores
                        q1_tot = (h_lines[0] if len(h_lines) > 0 else 0) + (a_lines[0] if len(a_lines) > 0 else 0)
                        q2_tot = q1_tot + (h_lines[1] if len(h_lines) > 1 else 0) + (a_lines[1] if len(a_lines) > 1 else 0)
                        q3_tot = q2_tot + (h_lines[2] if len(h_lines) > 2 else 0) + (a_lines[2] if len(a_lines) > 2 else 0)
                        final_tot = h_score + a_score

                        checkpoints = {
                            "pre": {
                                "period": 0, "away_score": 0, "home_score": 0, "score_total": 0,
                                "projected_total": market_ou, "projected_spread": market_spread,
                                "projected_winner": h_name if market_spread < 0 else a_name
                            },
                            "q1": {
                                "period": 1, "away_score": a_lines[0] if a_lines else 0, "home_score": h_lines[0] if h_lines else 0,
                                "score_total": q1_tot, "projected_total": round((q1_tot * 4.0 * 0.35) + (market_ou * 0.65), 1),
                                "projected_winner": h_name if market_spread < 0 else a_name
                            },
                            "half": {
                                "period": 2, "away_score": sum(a_lines[:2]), "home_score": sum(h_lines[:2]),
                                "score_total": q2_tot, "projected_total": round((q2_tot * 2.0 * 0.60) + (market_ou * 0.40), 1),
                                "projected_winner": h_name if market_spread < 0 else a_name
                            },
                            "q3": {
                                "period": 3, "away_score": sum(a_lines[:3]), "home_score": sum(h_lines[:3]),
                                "score_total": q3_tot, "projected_total": round(((q3_tot / 3.0) * 4.0 * 0.85) + (market_ou * 0.15), 1),
                                "projected_winner": h_name if market_spread < 0 else a_name
                            },
                            "final": {
                                "period": 4, "away_score": a_score, "home_score": h_score,
                                "score_total": final_tot, "projected_total": float(final_tot),
                                "projected_winner": h_name if h_score > a_score else a_name
                            }
                        }

                        # Pull active roster athletes from box score if available
                        confirmed_a = []
                        confirmed_h = []
                        for ply in away_t.get("leaders", []):
                            for l_ath in ply.get("leaders", []):
                                confirmed_a.append((l_ath.get("athlete", {}).get("displayName", ""), ply.get("name", "ATH")))
                        for ply in home_t.get("leaders", []):
                            for l_ath in ply.get("leaders", []):
                                confirmed_h.append((l_ath.get("athlete", {}).get("displayName", ""), ply.get("name", "ATH")))

                        game_entry = {
                            "game_id": g_id,
                            "league": "NFL",
                            "date": ev.get("date", f"Week {wk}"),
                            "away_team": a_name,
                            "home_team": h_name,
                            "away_short": a_short,
                            "home_short": h_short,
                            "away_logo": a_logo,
                            "home_logo": h_logo,
                            "final_score_away": a_score,
                            "final_score_home": h_score,
                            "status": "Completed",
                            "confirmed_players_away": confirmed_a,
                            "confirmed_players_home": confirmed_h,
                            "checkpoints": checkpoints
                        }

                        # If already in snapshots, update it; otherwise append
                        found_idx = next((i for i, s in enumerate(snapshots) if s.get("game_id") == g_id), None)
                        if found_idx is not None:
                            snapshots[found_idx] = game_entry
                        else:
                            snapshots.append(game_entry)
                            new_games_added += 1
            except Exception:
                continue

    save_game_snapshots(snapshots)
    return new_games_added
