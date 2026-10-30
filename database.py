import json
import os
from datetime import datetime

SNAPSHOT_FILE = "game_snapshots.json"

def load_game_snapshots():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_game_snapshots(snapshots):
    try:
        with open(SNAPSHOT_FILE, "w") as f:
            json.dump(snapshots, f, indent=2)
        return True
    except Exception:
        return False

def record_full_game_progression(game_obj, active_roster_away=None, active_roster_home=None):
    """
    Records and updates the current-year game telemetry lifecycle across checkpoints:
    'pre', 'q1', 'half', 'q3', and 'final'.
    """
    snapshots = load_game_snapshots()
    g_id = str(game_obj.get("id"))
    league = str(game_obj.get("league", "NFL")).upper()

    # Find existing game record or create new
    game_entry = next((s for s in snapshots if s.get("game_id") == g_id), None)
    
    period = game_obj.get("period", 0)
    state = game_obj.get("state_text", "pre")
    is_completed = game_obj.get("completed", False)
    
    # Determine checkpoint key
    if is_completed or state == "post":
        checkpoint = "final"
    elif period == 1:
        checkpoint = "q1"
    elif period == 2:
        checkpoint = "half"
    elif period == 3:
        checkpoint = "q3"
    elif period >= 4:
        checkpoint = "q4"
    else:
        checkpoint = "pre"

    h_score = int(game_obj.get("home_score", 0))
    a_score = int(game_obj.get("away_score", 0))
    current_total = h_score + a_score
    pre_total = float(game_obj.get("market_ou", 46.5 if league == "NFL" else 224.5))
    pre_spread = float(game_obj.get("market_spread", -3.5))

    # Pace drift calculation
    from database import calculate_pace_drift_factor
    projected_total = calculate_pace_drift_factor(period, current_total, pre_total) if period > 0 else pre_total

    if not game_entry:
        game_entry = {
            "game_id": g_id,
            "league": league,
            "date": game_obj.get("kickoff", "Scheduled"),
            "away_team": game_obj.get("away_team"),
            "home_team": game_obj.get("home_team"),
            "away_short": game_obj.get("away_short"),
            "home_short": game_obj.get("home_short"),
            "away_logo": game_obj.get("away_logo"),
            "home_logo": game_obj.get("home_logo"),
            "confirmed_players_away": active_roster_away or [],
            "confirmed_players_home": active_roster_home or [],
            "checkpoints": {}
        }
        snapshots.insert(0, game_entry)

    # Update active rosters if supplied
    if active_roster_away:
        game_entry["confirmed_players_away"] = active_roster_away
    if active_roster_home:
        game_entry["confirmed_players_home"] = active_roster_home

    # Record data snapshot for this checkpoint
    game_entry["checkpoints"][checkpoint] = {
        "period": period,
        "clock": game_obj.get("clock", ""),
        "away_score": a_score,
        "home_score": h_score,
        "score_total": current_total,
        "projected_total": projected_total,
        "projected_spread": pre_spread,
        "projected_winner": game_entry["home_team"] if pre_spread < 0 else game_entry["away_team"],
        "recorded_at": datetime.now().isoformat()
    }

    # Final summary attributes
    game_entry["final_score_away"] = a_score
    game_entry["final_score_home"] = h_score
    game_entry["status"] = "Completed" if is_completed else f"In Progress (Q{period})" if period > 0 else "Scheduled"

    save_game_snapshots(snapshots)
