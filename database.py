import json
import os
import shutil
import hashlib
import smtplib
import base64
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import streamlit as st

STORAGE_FILE = "storage.json"
BACKUP_FILE = "storage_backup.json"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_admin_credentials():
    try:
        cfg = st.secrets["admin"]
        return {
            "username": cfg["username"],
            "password": cfg["password"],
            "email": cfg.get("email", "admin@domain.com")
        }
    except Exception:
        return {
            "username": "admin",
            "password": "adminpassword",
            "email": "admin@domain.com"
        }

def send_verification_email(recipient_email: str, code: str) -> tuple[bool, str]:
    try:
        if "smtp" not in st.secrets:
            return False, "SMTP configuration not configured in Streamlit Secrets."
        smtp_cfg = st.secrets["smtp"]
    except Exception as e:
        return False, f"Failed reading SMTP secrets: {e}"

    server_host = smtp_cfg.get("server", "smtp.gmail.com")
    port = int(smtp_cfg.get("port", 587))
    username = smtp_cfg.get("username", "").strip()
    password = smtp_cfg.get("password", "").strip().replace(" ", "")
    sender_email = smtp_cfg.get("sender_email", username).strip()

    if not username or not password:
        return False, "SMTP username or password missing."

    msg = MIMEMultipart()
    msg["From"] = f"Flurkstradamus <{sender_email}>"
    msg["To"] = recipient_email
    msg["Subject"] = "Your Flurkstradamus Verification Code"
    msg.attach(MIMEText(f"Welcome to Flurkstradamus!\n\nYour 6-digit confirmation code is: {code}\n", "plain"))

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(server_host, port, timeout=10)
        else:
            server = smtplib.SMTP(server_host, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        return True, "Activation email sent successfully."
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Please configure a 16-character App Password."
    except Exception as e:
        return False, f"SMTP error: {str(e)}"

# Remote Cloud GitHub Sync Helpers
def fetch_remote_storage_from_github():
    try:
        gh_cfg = st.secrets.get("github")
        if not gh_cfg or not gh_cfg.get("token") or not gh_cfg.get("repo"):
            return None
        token = str(gh_cfg["token"]).strip().strip('"').strip("'")
        repo = str(gh_cfg["repo"]).strip().strip('"').strip("'")
        branch = str(gh_cfg.get("branch", "main")).strip()
        url = f"https://api.github.com/repos/{repo}/contents/{STORAGE_FILE}?ref={branch}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = requests.get(url, headers=headers, timeout=6.0)
        if res.status_code == 200:
            content_b64 = res.json().get("content", "")
            data_str = base64.b64decode(content_b64).decode("utf-8")
            return json.loads(data_str)
        elif res.status_code == 404:
            # File not found remotely yet
            return None
    except Exception as e:
        print(f"GitHub fetch error: {e}")
    return None

def push_storage_to_github(payload_dict):
    try:
        gh_cfg = st.secrets.get("github")
        if not gh_cfg or not gh_cfg.get("token") or not gh_cfg.get("repo"):
            return False
        token = str(gh_cfg["token"]).strip().strip('"').strip("'")
        repo = str(gh_cfg["repo"]).strip().strip('"').strip("'")
        branch = str(gh_cfg.get("branch", "main")).strip()
        url = f"https://api.github.com/repos/{repo}/contents/{STORAGE_FILE}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        sha = None
        get_res = requests.get(f"{url}?ref={branch}", headers=headers, timeout=6.0)
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")

        json_bytes = json.dumps(payload_dict, indent=2).encode("utf-8")
        encoded_content = base64.b64encode(json_bytes).decode("utf-8")

        body = {
            "message": "Persist Flurkstradamus storage state [skip ci]",
            "content": encoded_content,
            "branch": branch
        }
        if sha:
            body["sha"] = sha

        put_res = requests.put(url, headers=headers, json=body, timeout=8.0)
        if put_res.status_code not in [200, 201]:
            print(f"GitHub Sync Failed: HTTP {put_res.status_code} - {put_res.text[:150]}")
            return False
        return True
    except Exception as e:
        print(f"GitHub push error: {e}")
        return False

def load_storage():
    admin_cred = get_admin_credentials()
    admin_key = admin_cred["username"].lower()
    
    # 1. Fetch remote data from GitHub first
    remote_data = fetch_remote_storage_from_github()
    if remote_data:
        try:
            with open(STORAGE_FILE, "w") as f:
                json.dump(remote_data, f, indent=2)
        except Exception:
            pass
        data = remote_data
    else:
        target_path = STORAGE_FILE if os.path.exists(STORAGE_FILE) else (BACKUP_FILE if os.path.exists(BACKUP_FILE) else None)
        if not target_path:
            return [], [], {}, [], {}, []
        try:
            with open(target_path, "r") as f:
                data = json.load(f)
        except Exception:
            return [], [], {}, [], {}, []

    try:
        saved_bets = data.get("saved_bets", [])
        chat_messages = data.get("chat_messages", [])
        user_accounts = data.get("user_accounts", {})
        banned_emails = data.get("banned_emails", [])
        game_snapshots = data.get("game_snapshots", {})
        support_tickets = data.get("support_tickets", [])

        admin_user = user_accounts.get(admin_key, {
            "username": admin_cred["username"],
            "email": admin_cred["email"],
            "display_name": admin_cred["username"],
            "created_at": "2026-10-28",
            "favorite_team": "Multi-Sport",
            "bio": "Lead administrator.",
            "avatar_url": "",
            "is_public": True,
            "share_feed": True,
            "searches": [],
            "reset_token": None,
            "session_token": None
        })
        admin_user["is_admin"] = True
        admin_user["is_banned"] = False
        admin_user["is_verified"] = True
        admin_user["password_hash"] = hash_password(admin_cred["password"])
        user_accounts[admin_key] = admin_user

        for b in saved_bets:
            if "locked_profit" not in b:
                p = float(b.get("payout_dollars", b.get("payout", 0.0)))
                r = float(b.get("risk_dollars", 0.0))
                b["locked_profit"] = p - r

        return saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots, support_tickets
    except Exception:
        return [], [], {}, [], {}, []

def save_all_storage(saved_bets, chat_messages, user_accounts, banned_emails, game_snapshots, support_tickets=None):
    disk_bets, disk_chat, disk_users, disk_banned, disk_snaps, disk_tickets = [], [], {}, [], {}, []
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, "r") as f:
                d = json.load(f)
                disk_bets = d.get("saved_bets", [])
                disk_chat = d.get("chat_messages", [])
                disk_users = d.get("user_accounts", {})
                disk_banned = d.get("banned_emails", [])
                disk_snaps = d.get("game_snapshots", {})
                disk_tickets = d.get("support_tickets", [])
            shutil.copyfile(STORAGE_FILE, BACKUP_FILE)
        except Exception:
            pass

    payload = {
        "saved_bets": saved_bets if saved_bets else disk_bets,
        "chat_messages": chat_messages if chat_messages else disk_chat,
        "user_accounts": user_accounts if user_accounts else disk_users,
        "banned_emails": banned_emails if banned_emails else disk_banned,
        "game_snapshots": game_snapshots if game_snapshots else disk_snaps,
        "support_tickets": support_tickets if support_tickets is not None else disk_tickets
    }

    # 1. Local disk write
    try:
        temp_file = STORAGE_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(temp_file, STORAGE_FILE)
    except Exception as e:
        print(f"Local save error: {e}")

    # 2. Remote GitHub write (persistent across rebuilds)
    push_storage_to_github(payload)

def find_game_for_bet(bet, games_data):
    matchup = bet.get("matchup", "")
    if not matchup or not games_data:
        return None

    notes_str = str(bet.get("notes", "")).upper()
    pool = games_data
    if "[NFL]" in notes_str or "NFL" in notes_str:
        pool = [g for g in games_data if g.get("league") == "NFL"] or games_data
    elif "[NBA]" in notes_str or "NBA" in notes_str:
        pool = [g for g in games_data if g.get("league") == "NBA"] or games_data
    elif "[NCAA" in notes_str or "NCAA" in notes_str:
        pool = [g for g in games_data if g.get("league") == "NCAA"] or games_data

    parts = matchup.split("@")
    if len(parts) == 2:
        a_abbr = parts[0].strip().upper()
        h_abbr = parts[1].strip().upper()
        for g in pool:
            if g.get("away_short", "").upper() == a_abbr and g.get("home_short", "").upper() == h_abbr:
                return g

    for g in pool:
        h_team = g.get("home_team", "").lower()
        a_team = g.get("away_team", "").lower()
        h_short = g.get("home_short", "").lower()
        a_short = g.get("away_short", "").lower()
        if (h_team in matchup.lower() or h_short in matchup.lower()) and \
           (a_team in matchup.lower() or a_short in matchup.lower()):
            return g

    for g in pool:
        h_team = g.get("home_team", "").lower()
        a_team = g.get("away_team", "").lower()
        if h_team in matchup.lower() or a_team in matchup.lower():
            return g

    return None

def auto_resolve_bets(saved_bets, games_data, chat_messages=None, game_snapshots=None, support_tickets=None):
    if not saved_bets or not games_data:
        return False
    updated = False

    for bet in saved_bets:
        if bet.get("status") != "Pending":
            continue

        is_combo = (bet.get("bet_category") == "Combo" or "Leg" in bet.get("type", ""))
        if is_combo:
            legs = bet.get("parsed_legs", [])
            all_final = True
            any_lost = False
            for leg in legs:
                lg_game = find_game_for_bet({"matchup": leg.get("matchup", "")}, games_data)
                if not lg_game or not lg_game.get("completed", False):
                    all_final = False
                    continue
                h_sc = lg_game.get("home_score", 0)
                a_sc = lg_game.get("away_score", 0)
                tot_sc = h_sc + a_sc
                if leg.get("type") == "Game Total" and leg.get("line") is not None:
                    if leg.get("side") == "Under" and tot_sc > float(leg.get("line")):
                        any_lost = True
                    elif leg.get("side") == "Over" and tot_sc < float(leg.get("line")):
                        any_lost = True
                elif leg.get("type") in ["Straight Up Winner", "Moneyline"]:
                    picked = leg.get("picked_team", "")
                    if picked == lg_game.get("home_team") and h_sc < a_sc:
                        any_lost = True
                    elif picked == lg_game.get("away_team") and a_sc < h_sc:
                        any_lost = True

            if any_lost:
                bet["status"] = "Lost"
                updated = True
            elif all_final and not any_lost:
                bet["status"] = "Won"
                updated = True
        else:
            game = find_game_for_bet(bet, games_data)
            if not game or not game.get("completed", False):
                continue

            h_sc = game.get("home_score", 0)
            a_sc = game.get("away_score", 0)
            tot_sc = h_sc + a_sc
            cat = bet.get("bet_category", "")
            t_line = bet.get("target_line")
            b_side = bet.get("bet_direction", "")

            won = None
            if "Total" in cat and t_line is not None:
                won = (tot_sc < float(t_line)) if b_side == "Under" else (tot_sc > float(t_line))
            elif "Spread" in cat and t_line is not None:
                diff = (h_sc - a_sc) if bet.get("picked_team") == game.get("home_team") else (a_sc - h_sc)
                won = (diff + float(t_line)) > 0
            elif "Moneyline" in cat:
                won = (h_sc > a_sc) if bet.get("picked_team") == game.get("home_team") else (a_sc > h_sc)

            if won is True:
                bet["status"] = "Won"
                updated = True
            elif won is False:
                bet["status"] = "Lost"
                updated = True

    if updated:
        save_all_storage(saved_bets, chat_messages or [], {}, [], game_snapshots or {}, support_tickets)
    return updated
