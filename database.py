import json
import os

SNAPSHOT_FILE = "game_snapshots.json"

def load_game_snapshots():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def record_quarterly_snapshot(game_id, league, state, home_team, away_team, h_score, a_score, period, pre_proj_total, pre_proj_spread):
    """
    Logs pre-game and post-quarter progression (Pre, Q1, Half, Q3, Final)
    to build empirical self-learning regression datasets.
    """
    snapshots = load_game_snapshots()
    entry = {
        "game_id": str(game_id),
        "league": league,
        "state": state,
        "period": period,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": h_score,
        "away_score": a_score,
        "current_total": h_score + a_score,
        "pre_proj_total": pre_proj_total,
        "pre_proj_spread": pre_proj_spread,
        "timestamp": str(os.path.getmtime(SNAPSHOT_FILE)) if os.path.exists(SNAPSHOT_FILE) else ""
    }
    
    # Update existing game state or append new
    updated = False
    for idx, s in enumerate(snapshots):
        if s.get("game_id") == str(game_id) and s.get("period") == period:
            snapshots[idx] = entry
            updated = True
            break
    if not updated:
        snapshots.append(entry)

    try:
        with open(SNAPSHOT_FILE, "w") as f:
            json.dump(snapshots, f, indent=2)
    except Exception:
        pass

def calculate_pace_drift_factor(period, current_total, pre_game_total):
    """
    Calculates pacing drift from quarter progression.
    Returns expected terminal total adjustment factor.
    """
    if period == 0 or current_total == 0:
        return pre_game_total
    
    # Regression weight increases as game matures
    quarter_weights = {1: 0.35, 2: 0.60, 3: 0.85, 4: 1.0}
    w = quarter_weights.get(period, 0.50)
    
    extrapolated = (current_total / max(1, period)) * 4.0
    return round((extrapolated * w) + (pre_game_total * (1.0 - w)), 1)
