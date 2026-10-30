import json
import os
import hashlib
from datetime import datetime

STORAGE_FILE = "storage.json"
SNAPSHOT_FILE = "game_snapshots.json"

# =========================================================================
# 1. CORE STORAGE LOAD & SAVE
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

def load_storage():
    """
    Primary storage loader called directly by app.py line 9.
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

# Backwards compatibility alias
load_all_storage = load_storage

def save_all_storage(saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots, support_tickets):
    """Persists all session state variables back into storage.json."""
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
# 2. BET RESOLUTION ENGINE
# =========================================================================

def find_game_for_bet(bet, games_data):
    """Matches a locked bet slip against live or completed scoreboard data."""
    if not games_data:
        return None

    matchup_str = str(bet.get("matchup", "")).lower()
    bet_str = str(bet.get("bet", "")).lower()
    picked_t = str(bet.get("picked_team", "")).lower()

    for gm in games_data:
        h_name = str(gm.get("home_team", "")).lower()
        a_name = str(gm.get("away_team", "")).lower()
        h_sh = str(gm.get("home_short", "")).lower()
        a_sh = str(gm.get("away_short", "")).lower()

        if (h_sh in matchup_str and a_sh in matchup_str) or \
           (h_name in matchup_str and a_name in matchup_str) or \
           (h_sh in bet_str and a_sh in bet_str) or \
           (picked_t and (picked_t in h_name or picked_t in a_name or picked_t in h_sh or picked_t in a_sh)):
            return gm

    return None

def auto_resolve_bet(bet, game_data):
    """Auto-evaluates pending bets against final game results."""
    if not game_data or not game_data.get("completed", False):
        return "Pending"

    h_score = int(game_data.get("home_score", 0))
    a_score = int(game_data.get("away_score", 0))
    total_score = h_score + a_score

    bet_type = str(bet.get("bet_category", bet.get("type", ""))).lower()
    direction = str(bet.get("bet_direction", "")).lower()
    line = bet.get("target_line")
    picked_team = str(bet.get("picked_team", "")).lower()

    # Totals
    if "total" in bet_type or "over" in direction or "under" in direction:
        if line is not None:
            fl_line = float(line)
            if total_score > fl_line:
                return "Won" if "over" in direction else "Lost"
            elif total_score < fl_line:
                return "Won" if "under" in direction else "Lost"
            else:
                return "Push"

    # Moneylines
    if "moneyline" in bet_type or "straight up" in bet_type or direction == "moneyline":
        h_name = str(game_data.get("home_team", "")).lower()
        h_sh = str(game_data.get("home_short", "")).lower()
        winning_team = "home" if h_score > a_score else ("away" if a_score > h_score else "tie")

        if winning_team == "tie":
            return "Push"

        is_picked_home = (picked_team in h_name or picked_team in h_sh)
        if (is_picked_home and winning_team == "home") or (not is_picked_home and winning_team == "away"):
            return "Won"
        return "Lost"

    # Spread
    if "spread" in bet_type or direction == "spread":
        if line is not None:
            fl_line = float(line)
            h_name = str(game_data.get("home_team", "")).lower()
            h_sh = str(game_data.get("home_short", "")).lower()
            is_picked_home = (picked_team in h_name or picked_team in h_sh)

            spread_margin = (h_score - a_score) if is_picked_home else (a_score - h_score)
            adjusted_margin = spread_margin + fl_line

            if adjusted_margin > 0:
                return "Won"
            elif adjusted_margin < 0:
                return "Lost"
            else:
                return "Push"

    return "Pending"

# =========================================================================
# 3. AUTHENTICATION & SECURITY
# =========================================================================

def hash_password(password: str) -> str:
    """Hashes passwords using SHA-256."""
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()

def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verifies plain password against hash."""
    return stored_password_hash == hash_password(provided_password)

def get_admin_credentials():
    """Returns administrator username and password hash."""
    admin_user = os.environ.get("FLURK_ADMIN_USER", "flurk")
    admin_pass = os.environ.get("FLURK_ADMIN_PASS", "flurkstradamus2026")
    return admin_user, hash_password(admin_pass)

def send_verification_email(recipient_email, verification_code):
    """
    Stub for email verification that safely returns True
    so the app never crashes on missing SMTP credentials.
    """
    return True

# =========================================================================
# 4. GAME SNAPSHOTS & PACING DRIFT
# =========================================================================

def load_game_snapshots():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def record_quarterly_snapshot(game_id, league, state, home_team, away_team, h_score, a_score, period, pre_proj_total, pre_proj_spread):
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
    if period == 0 or current_total == 0:
        return float(pre_game_total)

    quarter_weights = {1: 0.35, 2: 0.60, 3: 0.85, 4: 1.0}
    w = quarter_weights.get(period, 0.50)

    extrapolated = (float(current_total) / max(1.0, float(period))) * 4.0
    drift_result = (extrapolated * w) + (float(pre_game_total) * (1.0 - w))
    return round(drift_result, 1)
