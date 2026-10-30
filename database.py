import json
import os
from datetime import datetime

STORAGE_FILE = "storage.json"
SNAPSHOT_FILE = "game_snapshots.json"

# =========================================================================
# CORE APP STORAGE (BETS, USERS, CHATS, TICKETS, SNAPSHOTS)
# =========================================================================

def init_db():
    """Initializes local storage files if they do not exist."""
    if not os.path.exists(STORAGE_FILE):
        default_data = {
            "saved_bets": [],
            "chat_messages": [],
            "user_accounts": {},
            "banned_emails": [],
            "game_snapshots": [],
            "support_tickets": []
        }
        try:
            with open(STORAGE_FILE, "w") as f:
                json.dump(default_data, f, indent=2)
        except Exception:
            pass

    if not os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "w") as f:
                json.dump([], f, indent=2)
        except Exception:
            pass

def load_all_storage():
    """
    Loads all saved data for app.py session state initialization.
    Returns: (saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots, support_tickets)
    """
    init_db()
    try:
        with open(STORAGE_FILE, "r") as f:
            data = json.load(f)
            return (
                data.get("saved_bets", []),
                data.get("chat_messages", []),
                data.get("user_accounts", {}),
                data.get("banned_emails", []),
                data.get("game_snapshots", []),
                data.get("support_tickets", [])
            )
    except Exception:
        return ([], [], {}, [], [], [])

def save_all_storage(saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots, support_tickets):
    """
    Persists all current session state variables back into storage.json.
    """
    data = {
        "saved_bets": saved_bets,
        "chat_messages": chat_messages,
        "user_accounts": user_accounts,
        "banned_emails": banned_emails,
        "game_snapshots": game_snapshots,
        "support_tickets": support_tickets
    }
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

# =========================================================================
# QUARTERLY MATCHUP SNAPSHOTS & SELF-LEARNING PACING DRIFT
# =========================================================================

def load_game_snapshots():
    """Loads historical game progression snapshots for regression learning."""
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def record_quarterly_snapshot(game_id, league, state, home_team, away_team, h_score, a_score, period, pre_proj_total, pre_proj_spread):
    """
    Logs pre-game and quarter-by-quarter telemetry (Q1, Halftime, Q3, Final).
    Used by War Room and Single Game Analytics to track in-game pacing changes.
    """
    snapshots = load_game_snapshots()
    entry = {
        "game_id": str(game_id),
        "league": league,
        "state": state,
        "period": period,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": int(h_score),
        "away_score": int(a_score),
        "current_total": int(h_score) + int(a_score),
        "pre_proj_total": float(pre_proj_total),
        "pre_proj_spread": float(pre_proj_spread),
        "updated_at": datetime.now().isoformat()
    }

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
    Calculates reactive pacing adjustments as the game matures through quarters.
    Weighting ramps up from Q1 through Q4 to provide sharp terminal estimates.
    """
    if period == 0 or current_total == 0:
        return float(pre_game_total)

    quarter_weights = {1: 0.35, 2: 0.60, 3: 0.85, 4: 1.0}
    w = quarter_weights.get(period, 0.50)

    extrapolated = (float(current_total) / max(1.0, float(period))) * 4.0
    drift_result = (extrapolated * w) + (float(pre_game_total) * (1.0 - w))
    return round(drift_result, 1)
