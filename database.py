import json
import os
import hashlib

DATA_FILE = "storage.json"

def hash_password(password: str) -> str:
    """Hash password with SHA-256 and a fixed salt."""
    salt = "flurkstradamus_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def load_storage():
    """Load bets, chat messages, user accounts, banned emails, and historical projections."""
    default_users = {
        "flurk": {
            "username": "flurk",
            "display_name": "Flurk",
            "email": "flurk@flurkstradamus.com",
            "password_hash": hash_password("Loofus1993"),
            "is_admin": True,
            "is_banned": False,
            "created_at": "2026-10-26",
            "favorite_team": "NFL",
            "reset_token": None,
            "session_token": "flurk_persistent_token_999"
        }
    }
    
    if not os.path.exists(DATA_FILE):
        return [], [], default_users, [], {}
        
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            bets = data.get("bets", [])
            chat = data.get("chat", [])
            users = data.get("users", {})
            banned_emails = data.get("banned_emails", [])
            game_snapshots = data.get("game_snapshots", {})
            
            # Ensure admin account exists with proper session token
            if "flurk" not in users or users["flurk"].get("password_hash") != hash_password("Loofus1993"):
                users["flurk"] = default_users["flurk"]
            else:
                if "session_token" not in users["flurk"]:
                    users["flurk"]["session_token"] = "flurk_persistent_token_999"

            return bets, chat, users, banned_emails, game_snapshots
    except Exception:
        return [], [], default_users, [], {}

def save_all_storage(bets, chat, users=None, banned_emails=None, game_snapshots=None):
    """Persist all bets, chat messages, user accounts, blacklist, and projection snapshots."""
    if users is None or banned_emails is None or game_snapshots is None:
        _, _, u, b_e, g_s = load_storage()
        if users is None:
            users = u
        if banned_emails is None:
            banned_emails = b_e
        if game_snapshots is None:
            game_snapshots = g_s
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "bets": bets, 
                "chat": chat,
                "users": users,
                "banned_emails": banned_emails,
                "game_snapshots": game_snapshots
            }, f, indent=2)
    except Exception:
        pass

def find_game_for_bet(bet, games_data):
    """Locate live game scoreboard data matching a ticket."""
    if not games_data:
        return None
    matchup_str = bet.get("matchup", "")
    for g in games_data:
        away = g.get("away_short", "")
        home = g.get("home_short", "")
        if f"{away} @ {home}" in matchup_str or f"{away} vs {home}" in matchup_str or (away in matchup_str and home in matchup_str):
            return g
    return None

def auto_resolve_bets(saved_bets, games_data, chat_messages, game_snapshots=None):
    """Automatically grades completed tickets and preserves final snapshot."""
    updated = False
    for b in saved_bets:
        if b.get("status") == "Pending":
            game = find_game_for_bet(b, games_data)
            if game and game.get("completed", False):
                h_score = game.get("home_score", 0)
                a_score = game.get("away_score", 0)
                tot = h_score + a_score
                cat = b.get("bet_category", "Total")
                target = b.get("target_line")
                side = b.get("bet_direction", "Under")
                
                if cat in ["Total", "2H Total"] and target is not None:
                    if side == "Under":
                        b["status"] = "Won" if tot < target else "Lost"
                    else:
                        b["status"] = "Won" if tot > target else "Lost"
                    updated = True
                elif cat == "Spread" and target is not None:
                    diff = (h_score - a_score) if b.get("picked_team") == game.get("home_team") else (a_score - h_score)
                    b["status"] = "Won" if (diff + target > 0) else "Lost"
                    updated = True
                elif cat == "Moneyline":
                    winner = game.get("home_team") if h_score > a_score else game.get("away_team")
                    b["status"] = "Won" if b.get("picked_team") == winner else "Lost"
                    updated = True
                    
    if updated:
        save_all_storage(saved_bets, chat_messages, game_snapshots=game_snapshots)
    return updated
