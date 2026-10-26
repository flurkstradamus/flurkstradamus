import json
import os
import hashlib

DATA_FILE = "storage.json"

def hash_password(password: str) -> str:
    """Hash password with SHA-256 and a fixed salt."""
    salt = "flurkstradamus_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def load_storage():
    """Load bets, chat messages, and user accounts from storage.json."""
    default_users = {
        "flurk": {
            "username": "flurk",
            "display_name": "Flurk",
            "password_hash": hash_password("Loofus1993"),
            "is_admin": True,
            "created_at": "2026-10-26",
            "favorite_team": "NFL"
        }
    }
    
    if not os.path.exists(DATA_FILE):
        return [], [], default_users
        
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            bets = data.get("bets", [])
            chat = data.get("chat", [])
            users = data.get("users", {})
            
            # Ensure flurk admin is always present and active
            if "flurk" not in users or users["flurk"].get("password_hash") != hash_password("Loofus1993"):
                users["flurk"] = default_users["flurk"]
                
            return bets, chat, users
    except Exception:
        return [], [], default_users

def save_all_storage(bets, chat, users=None):
    """Persist all bets, chat messages, and user accounts."""
    if users is None:
        _, _, users = load_storage()
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "bets": bets, 
                "chat": chat,
                "users": users
            }, f, indent=2)
    except Exception:
        pass

def find_game_for_bet(bet, games_data):
    """Helper to locate live game scoreboard info matching a ticket."""
    if not games_data:
        return None
    matchup_str = bet.get("matchup", "")
    for g in games_data:
        away = g.get("away_short", "")
        home = g.get("home_short", "")
        if f"{away} @ {home}" in matchup_str or f"{away} vs {home}" in matchup_str:
            return g
    return None

def auto_resolve_bets(saved_bets, games_data, chat_messages):
    """Automatically grades completed tickets."""
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
        save_all_storage(saved_bets, chat_messages)
    return updated
