import json
import os
import hashlib
from datetime import datetime

STORAGE_FILE = "storage.json"
SNAPSHOT_FILE = "game_snapshots.json"

# =========================================================================
# 1. CORE DATABASE INITIALIZATION & FILE PERSISTENCE
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
# 2. USER AUTHENTICATION & SECURITY HELPERS
# =========================================================================

def hash_password(password: str) -> str:
    """Hashes passwords using SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verifies a plain password against stored hash."""
    return stored_password_hash == hash_password(provided_password)

def load_user_accounts():
    _, _, u, _, _, _ = load_all_storage()
    return u

def save_user_accounts(user_accounts):
    sb, c, _, b, s, t = load_all_storage()
    return save_all_storage(sb, c, user_accounts, b, s, t)

def load_banned_emails():
    _, _, _, b, _, _ = load_all_storage()
    return b

def save_banned_emails(banned_emails):
    sb, c, u, _, s, t = load_all_storage()
    return save_all_storage(sb, c, u, banned_emails, s, t)


# =========================================================================
# 3. INDIVIDUAL GETTERS & CONVENIENCE HELPERS
# =========================================================================

def load_saved_bets():
    sb, _, _, _, _, _ = load_all_storage()
    return sb

def save_saved_bets(saved_bets):
    _, c, u, b, s, t = load_all_storage()
    return save_all_storage(saved_bets, c, u, b, s, t)

def load_chat_messages():
    _, c, _, _, _, _ = load_all_storage()
    return c

def save_chat_messages(chat_messages):
    sb, _, u, b, s, t = load_all_storage()
    return save_all_storage(sb, chat_messages, u, b, s, t)

def load_support_tickets():
    _, _, _, _, _, t = load_all_storage()
    return t

def save_support_tickets(support_tickets):
    sb, c, u, b, s, _ = load_all_storage()
    return save_all_storage(sb, c, u, b, s, support_tickets)


# =========================================================================
# 4. QUARTERLY MATCHUP SNAPSHOTS & PACING DRIFT
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

def save_game_snapshots(game_snapshots):
    try:
        with open(SNAPSHOT_FILE, "w") as f:
            json.dump(game_snapshots, f, indent=2)
        return True
    except Exception:
        return False

def record_quarterly_snapshot(game_id, league, state, home_team, away_team, h_score, a_score, period, pre_proj_total, pre_proj_spread):
    """Logs pre-game and quarter-by-quarter telemetry (Q1, Halftime, Q3, Final)."""
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

    save_game_snapshots(snapshots)

def calculate_pace_drift_factor(period, current_total, pre_game_total):
    """Calculates reactive pacing adjustments as the game matures through quarters."""
    if period == 0 or current_total == 0:
        return float(pre_game_total)

    quarter_weights = {1: 0.35, 2: 0.60, 3: 0.85, 4: 1.0}
    w = quarter_weights.get(period, 0.50)

    extrapolated = (float(current_total) / max(1.0, float(period))) * 4.0
    drift_result = (extrapolated * w) + (float(pre_game_total) * (1.0 - w))
    return round(drift_result, 1)
