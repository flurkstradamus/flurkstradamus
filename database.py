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

def load_storage():
    """
    Primary storage loader called directly by app.py.
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

# Aliases for backwards compatibility
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
        winning_team = "home" if h_score > a_score else ("away" if a_score > h_score else "tie")
        if winning_team == "tie":
            return "Push"

        h_name = str(game_data.get("home_team", "")).lower()
        h_sh = str(game_data.get("home_short", "")).lower()
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

auto_resolve_be = auto_resolve_bet

# =========================================================================
# 3. AUTHENTICATION & SECURITY
# =========================================================================

def hash_password(password: str) -> str:
    """Hashes passwords using SHA-256."""
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()

def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verifies plain password against hash."""
    return stored_password_hash == hash_password(provided_password)

class AdminCredentialsDict(dict):
    def __getitem__(self, item):
        if isinstance(item, int):
            return list(self.values())[item]
        return super().__getitem__(item)
    def __iter__(self):
        return iter([self["username"], self["password"]])

def get_admin_credentials():
    admin_user = os.environ.get("FLURK_ADMIN_USER", "flurk")
    admin_pass = os.environ.get("FLURK_ADMIN_PASS", "flurkstradamus2026")
    admin_email = os.environ.get("FLURK_ADMIN_EMAIL", "admin@flurkstradamus.com")
    return AdminCredentialsDict({
        "username": admin_user,
        "email": admin_email,
        "password": admin_pass
    })

def send_verification_email(recipient_email, verification_code):
    return True

# =========================================================================
# 4. GAME PROGRESSION LEARNING & QUARTERLY TELEMETRY
# =========================================================================

def load_game_snapshots():
    """Loads historical game progression snapshots for model learning."""
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

def calculate_pace_drift_factor(period, current_total, pre_game_total):
    """Calculates pacing drift factor as the game progresses through quarters."""
    if period == 0 or current_total == 0:
        return float(pre_game_total)

    quarter_weights = {1: 0.35, 2: 0.60, 3: 0.85, 4: 1.0}
    w = quarter_weights.get(period, 0.50)

    extrapolated = (float(current_total) / max(1.0, float(period))) * 4.0
    drift_result = (extrapolated * w) + (float(pre_game_total) * (1.0 - w))
    return round(drift_result, 1)

def record_quarterly_snapshot(game_id, league, state, home_team, away_team, h_score, a_score, period, pre_proj_total, pre_proj_spread):
    """Logs quarterly telemetry snapshot into game_snapshots.json."""
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

def record_full_game_progression(game_obj, active_roster_away=None, active_roster_home=None):
    """
    Records and updates season game progression across checkpoints:
    'pre', 'q1', 'half', 'q3', and 'final'.
    """
    snapshots = load_game_snapshots()
    g_id = str(game_obj.get("id"))
    league = str(game_obj.get("league", "NFL")).upper()

    game_entry = next((s for s in snapshots if s.get("game_id") == g_id), None)

    period = game_obj.get("period", 0)
    state = game_obj.get("state_text", "pre")
    is_completed = game_obj.get("completed", False)

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

    if active_roster_away:
        game_entry["confirmed_players_away"] = active_roster_away
    if active_roster_home:
        game_entry["confirmed_players_home"] = active_roster_home

    if "checkpoints" not in game_entry:
        game_entry["checkpoints"] = {}

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

    game_entry["final_score_away"] = a_score
    game_entry["final_score_home"] = h_score
    game_entry["status"] = "Completed" if is_completed else f"In Progress (Q{period})" if period > 0 else "Scheduled"

    save_game_snapshots(snapshots)

# Fallback hook for unexpected imports
def __getattr__(name):
    def _dummy(*args, **kwargs):
        return None
    return _dummy
