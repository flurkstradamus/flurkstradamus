import json
import os
import hashlib
from datetime import datetime

STORAGE_FILE = "storage.json"

def hash_password(password: str) -> str:
    """Hashes a password with SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def load_storage():
    """Loads all data structures from storage.json with sensible defaults."""
    default_users = {
        "flurk": {
            "username": "flurk",
            "email": "flurk@flurkstradamus.com",
            "display_name": "Flurk",
            "password_hash": hash_password("flurk123"),
            "is_admin": True,
            "is_banned": False,
            "created_at": "2026-10-26",
            "last_login": "2026-10-26 12:00 PM ET",
            "favorite_team": "NFL",
            "bio": "Lead strategist and model developer.",
            "avatar_url": "",
            "is_public": True,
            "share_feed": True,
            "searches": [],
            "reset_token": None,
            "session_token": None
        }
    }

    if not os.path.exists(STORAGE_FILE):
        return [], [], default_users, [], {}

    try:
        with open(STORAGE_FILE, "r") as f:
            data = json.load(f)
            saved_bets = data.get("saved_bets", [])
            chat_messages = data.get("chat_messages", [])
            user_accounts = data.get("user_accounts", default_users)
            banned_emails = data.get("banned_emails", [])
            game_snapshots = data.get("game_snapshots", {})
            return saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots
    except Exception:
        return [], [], default_users, [], {}

def save_all_storage(saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots):
    """Saves state back to storage.json."""
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
    if not matchup:
        return None

    # Check for direct abbreviation matches: "AWAY @ HOME"
    parts = matchup.split("@")
    if len(parts) == 2:
        a_abbr = parts[0].strip().upper()
        h_abbr = parts[1].strip().upper()
        for g in games_data:
            if g.get("away_short", "").upper() == a_abbr and g.get("home_short", "").upper() == h_abbr:
                return g

    # Fuzzy check by team names
    for g in games_data:
        h_team = g.get("home_team", "").lower()
        a_team = g.get("away_team", "").lower()
        if (h_team in matchup.lower() or g.get("home_short", "").lower() in matchup.lower()) and \
           (a_team in matchup.lower() or g.get("away_short", "").lower() in matchup.lower()):
            return g

    return None

def auto_resolve_bets(saved_bets, games_data, chat_messages=None, game_snapshots=None):
    """
    Grades completed games without ever overwriting custom entered risk or payout amounts.
    """
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
                # STRICTLY PRESERVE ENTERED PAYOUT
                if not bet.get("payout_dollars") or float(bet.get("payout_dollars", 0)) <= 0:
                    bet["payout_dollars"] = float(bet.get("payout", bet.get("risk_dollars", 10.0) * 1.91))
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
                # STRICTLY PRESERVE ENTERED PAYOUT
                if not bet.get("payout_dollars") or float(bet.get("payout_dollars", 0)) <= 0:
                    bet["payout_dollars"] = float(bet.get("payout", bet.get("risk_dollars", 10.0) * 1.91))
                updated = True
            elif won is False:
                bet["status"] = "Lost"
                updated = True

    if updated:
        save_all_storage(
            saved_bets, 
            chat_messages if chat_messages is not None else [], 
            {}, 
            [], 
            game_snapshots if game_snapshots is not None else {}
        )

    return updated
