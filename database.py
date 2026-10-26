import os
import json
import requests
from config import JSONBIN_BIN_ID, JSONBIN_API_KEY, DB_FILE, CHAT_FILE

def fetch_cloud_data():
    if JSONBIN_BIN_ID and JSONBIN_API_KEY:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
        headers = {"X-Master-Key": JSONBIN_API_KEY}
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                record = r.json().get("record", {})
                return record.get("bets", []), record.get("messages", [])
        except Exception:
            pass
    return None, None

def push_cloud_data(bets, messages):
    if JSONBIN_BIN_ID and JSONBIN_API_KEY:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
        headers = {
            "Content-Type": "application/json",
            "X-Master-Key": JSONBIN_API_KEY
        }
        try:
            r = requests.put(url, json={"bets": bets, "messages": messages}, headers=headers, timeout=5)
            return r.status_code == 200
        except Exception:
            pass
    return False

def load_storage():
    cloud_bets, cloud_chat = fetch_cloud_data()
    local_bets = []
    local_chat = []
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                local_bets = json.load(f)
        except Exception:
            local_bets = []
            
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, "r") as f:
                local_chat = json.load(f)
        except Exception:
            local_chat = []

    merged_bets = {b["id"]: b for b in (local_bets + (cloud_bets or []))}
    bets_list = list(merged_bets.values())
    bets_list.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    
    chat_list = cloud_chat if cloud_chat is not None else local_chat
    return bets_list, chat_list

def save_all_storage(bets, messages):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(bets, f, indent=4)
        with open(CHAT_FILE, "w") as f:
            json.dump(messages, f, indent=4)
    except Exception:
        pass
    push_cloud_data(bets, messages)

def find_game_for_bet(bet, games):
    m_text = bet.get("matchup", "").lower()
    h_team = bet.get("home_team", "").lower()
    a_team = bet.get("away_team", "").lower()
    for g_item in games:
        g_h = g_item["home_team"].lower()
        g_a = g_item["away_team"].lower()
        g_h_short = g_item["home_short"].lower()
        g_a_short = g_item["away_short"].lower()
        if (h_team and h_team in g_h) or (a_team and a_team in g_a):
            return g_item
        if (g_h in m_text or g_h_short in m_text) and (g_a in m_text or g_a_short in m_text):
            return g_item
        if g_h in m_text or g_a in m_text:
            return g_item
    return None

def auto_resolve_bets(bets, games, chat_messages):
    changed = False
    for b in bets:
        if b.get("status") == "Pending":
            b_cat = b.get("bet_category", "Total")
            if b_cat != "Combo":
                match_game = find_game_for_bet(b, games)
                if match_game and (match_game.get("completed", False) or "final" in match_game["status"].lower()):
                    tot = match_game["away_score"] + match_game["home_score"]
                    h_score = match_game["home_score"]
                    a_score = match_game["away_score"]
                    
                    if b_cat == "Total" and b.get("target_line") is not None:
                        is_und = (b.get("bet_direction", "Under") == "Under")
                        b["status"] = "Won" if ((tot < b["target_line"]) if is_und else (tot > b["target_line"])) else "Lost"
                        changed = True
                    elif b_cat == "Moneyline" and b.get("picked_team"):
                        actual_winner = match_game["home_team"] if h_score > a_score else match_game["away_team"]
                        b["status"] = "Won" if (b["picked_team"] == actual_winner) else "Lost"
                        changed = True
                    elif b_cat == "Spread" and b.get("target_line") is not None:
                        team_picked = b.get("picked_team", match_game["home_team"])
                        line = b["target_line"]
                        diff = (h_score - a_score) if team_picked == match_game["home_team"] else (a_score - h_score)
                        b["status"] = "Won" if (diff + line > 0) else "Lost"
                        changed = True

            elif b_cat == "Combo" and b.get("parsed_legs"):
                all_done = True
                any_lost = False
                for leg in b["parsed_legs"]:
                    m_g = find_game_for_bet({"matchup": leg["matchup"]}, games)
                    if m_g and (m_g.get("completed", False) or "final" in m_g["status"].lower()):
                        t_pts = m_g["away_score"] + m_g["home_score"]
                        if leg["type"] == "Total":
                            is_u = leg["side"] == "Under"
                            if not ((t_pts < leg["line"]) if is_u else (t_pts > leg["line"])):
                                any_lost = True
                        elif leg["type"] == "Moneyline":
                            act_win = m_g["home_team"] if m_g["home_score"] > m_g["away_score"] else m_g["away_team"]
                            if leg["picked_team"] != act_win:
                                any_lost = True
                    else:
                        all_done = False
                
                if any_lost:
                    b["status"] = "Lost"
                    changed = True
                elif all_done:
                    b["status"] = "Won"
                    changed = True

    if changed:
        save_all_storage(bets, chat_messages)
    return changed
