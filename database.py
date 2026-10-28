import json
import os
import hashlib
from datetime import datetime
import streamlit as st

STORAGE_FILE = "storage.json"

def hash_password(password: str) -> str:
    """Hashes a password with SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_admin_credentials():
    """Retrieves admin credentials securely from Streamlit Secrets."""
    try:
        cfg = st.secrets["admin"]
        return {
            "username": cfg["username"],
            "password": cfg["password"],
            "email": cfg.get("email", "admin@domain.com")
        }
    except Exception:
        # Generic fallback if secrets are not configured yet
        return {
            "username": "admin",
            "password": "adminpassword",
            "email": "admin@domain.com"
        }

def get_default_users():
    cred = get_admin_credentials()
    u_key = cred["username"].lower()
    return {
        u_key: {
            "username": cred["username"],
            "email": cred["email"],
            "display_name": cred["username"],
            "password_hash": hash_password(cred["password"]),
            "is_admin": True,
            "is_banned": False,
            "created_at": "2026-10-26",
            "last_login": "2026-10-26 12:00 PM ET",
            "favorite_team": "NFL",
            "bio": "Lead strategist and administrator.",
            "avatar_url": "",
            "is_public": True,
            "share_feed": True,
            "searches": [],
            "reset_token": None,
            "session_token": None
        }
    }

def load_storage():
    """Safely loads data from storage.json and syncs the secure admin account."""
    default_users = get_default_users()
    admin_cred = get_admin_credentials()
    admin_key = admin_cred["username"].lower()

    if not os.path.exists(STORAGE_FILE):
        return [], [], default_users, [], {}

    try:
        with open(STORAGE_FILE, "r") as f:
            data = json.load(f)
            saved_bets = data.get("saved_bets", [])
            chat_messages = data.get("chat_messages", [])
            user_accounts = data.get("user_accounts", {})

            # Ensure the designated admin account matches secrets
            admin_user = user_accounts.get(admin_key, {
                "username": admin_cred["username"],
                "email": admin_cred["email"],
                "display_name": admin_cred["username"],
                "created_at": "2026-10-26",
                "favorite_team": "NFL",
                "bio": "Lead strategist and administrator.",
                "avatar_url": "",
                "is_public": True,
                "share_feed": True,
                "searches": [],
                "reset_token": None,
                "session_token": None
            })
            
            admin_user["is_admin"] = True
            admin_user["is_banned"] = False
            admin_user["password_hash"] = hash_password(admin_cred["password"])
            admin_user["email"] = admin_cred["email"]
            user_accounts[admin_key] = admin_user

            banned_emails = data.get("banned_emails", [])
            game_snapshots = data.get("game_snapshots", {})
            return saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots
    except Exception as e:
        print(f"Error loading storage: {e}")
        return [], [], default_users, [], {}

def save_all_storage(saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots):
    """Saves state back to storage.json safely."""
    if not user_accounts:
        user_accounts = get_default_users()

    payload = {
        "saved_bets": saved_bets,
        "chat_messages": chat_messages,
        "user_accounts": user_accounts,
        "banned_emails": banned_emails,
        "game_snapshots": game_snapshots
    }
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        print(f"Error saving storage: {e}")

def find_game_for_bet(bet, games_data):
    """Matches a bet ticket to an active or past ESPN game object."""
    matchup = bet.get("matchup", "")
    if not matchup or not games_data:
        return None

    parts = matchup.split("@")
    if len(parts) == 2:
        a_abbr = parts[0].strip().upper()
        h_abbr = parts[1].strip().upper()
        for g in games_data:
            if g.get("away_short", "").upper() == a_abbr and g.get("home_short", "").upper() == h_abbr:
                return g

    for g in games_data:
        h_team = g.get("home_team", "").lower()
        a_team = g.get("away_team", "").lower()
        if (h_team in matchup.lower() or g.get("home_short", "").lower() in matchup.lower()) and \
           (a_team in matchup.lower() or g.get("away_short", "").lower() in matchup.lower()):
            return g

    return None

def auto_resolve_bets(saved_bets, games_data, chat_messages=None, game_snapshots=None):
    """Grades completed games without modifying entered payout or risk amounts."""
    if not saved_bets or not games_data:
        return False

    updated = False

    for bet in saved_bets:
        if bet.get("status") != "Pending":
            continue

        is_combo = (bet.get("bet_category") == "Combo" or "Leg" in bet.get("type", ""))

        if is_combo:
            legs = bet.get("parsed_legs", [])
            if not legs:
                continue

            all_legs_final = True
            any_leg_lost = False

            for leg in legs:
                leg_game = find_game_for_bet({"matchup": leg.get("matchup", "")}, games_data)
                if not leg_game:
                    all_legs_final = False
                    continue

                is_completed = leg_game.get("completed", False) or "final" in str(leg_game.get("status", "")).lower()
                if not is_completed:
                    all_legs_final = False
                    continue

                h_score = leg_game.get("home_score", 0)
                a_score = leg_game.get("away_score", 0)
                tot_score = h_score + a_score

                l_type = leg.get("type", "")
                l_side = leg.get("side", "")
                l_line = leg.get("line")

                if l_type == "Game Total" and l_line is not None:
                    if l_side == "Under" and tot_score > float(l_line):
                        any_leg_lost = True
                    elif l_side == "Over" and tot_score < float(l_line):
                        any_leg_lost = True
                elif l_type in ["Straight Up Winner", "Moneyline"]:
                    picked = leg.get("picked_team", "")
                    if picked == leg_game.get("home_team") and h_score < a_score:
                        any_leg_lost = True
                    elif picked == leg_game.get("away_team") and a_score < h_score:
                        any_leg_lost = True

            if any_leg_lost:
                bet["status"] = "Lost"
                updated = True
            elif all_legs_final and not any_leg_lost:
                bet["status"] = "Won"
                updated = True

        else:
            game = find_game_for_bet(bet, games_data)
            if not game:
                continue

            is_completed = game.get("completed", False) or "final" in str(game.get("status", "")).lower()
            if not is_completed:
                continue

            h_score = game.get("home_score", 0)
            a_score = game.get("away_score", 0)
            tot_score = h_score + a_score
            cat = bet.get("bet_category", "")
            t_line = bet.get("target_line")
            b_side = bet.get("bet_direction", "")

            won = None

            if cat in ["Total", "2H Total"] and t_line is not None:
                t_val = float(t_line)
                if b_side == "Under":
                    won = (tot_score < t_val)
                elif b_side == "Over":
                    won = (tot_score > t_val)
            elif cat == "Spread" and t_line is not None:
                spread_val = float(t_line)
                if bet.get("picked_team") == game.get("home_team"):
                    won = ((h_score - a_score) + spread_val) > 0
                else:
                    won = ((a_score - h_score) + spread_val) > 0
            elif cat == "Moneyline":
                if bet.get("picked_team") == game.get("home_team"):
                    won = (h_score > a_score)
                else:
                    won = (a_score > h_score)

            if won is True:
                bet["status"] = "Won"
                updated = True
            elif won is False:
                bet["status"] = "Lost"
                updated = True

    if updated:
        try:
            with open(STORAGE_FILE, "r") as f:
                cur = json.load(f)
                users = cur.get("user_accounts", get_default_users())
                banned = cur.get("banned_emails", [])
        except:
            users = get_default_users()
            banned = []
            
        save_all_storage(
            saved_bets, 
            chat_messages if chat_messages is not None else [], 
            users, 
            banned, 
            game_snapshots if game_snapshots is not None else {}
        )

    return updated
