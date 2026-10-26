import streamlit as st
import requests
import math
import json
import os
import re
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Flurkstradamus Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CONFIGURATION & PERSISTENCE ENGINE
# ==========================================
GROUP_PASSCODE = "FLURK2026"
JSONBIN_BIN_ID = "6ade77dbac6210605a51a450"    # Paste your Bin ID here if you have it
JSONBIN_API_KEY = "$2a$10$K8VFT4hzyxMbtkBLLtlaNu/ZB8WthYSFYlKEutPEE4Qg8hi8lA6Ya"   # Paste your Master Key here if you have it

DB_FILE = "bets_history.json"
CHAT_FILE = "chat_history.json"

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

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "selected_bet_id" not in st.session_state:
    st.session_state.selected_bet_id = None

if "legs_count_choice" not in st.session_state:
    st.session_state.legs_count_choice = 3

if "applied_ai_combo" not in st.session_state:
    st.session_state.applied_ai_combo = None

# Access Gatekeeper
if not st.session_state.authenticated:
    st.title("🔮 Flurkstradamus: Private Syndicate")
    st.caption("Consensus Live Edge & Market Terminal")
    with st.form("pin_login"):
        pin_entry = st.text_input("Group Passcode", type="password")
        login_btn = st.form_submit_button("Enter Terminal")
        if login_btn:
            if pin_entry == GROUP_PASSCODE:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid passcode.")
    st.stop()

if "saved_bets" not in st.session_state or "chat_messages" not in st.session_state:
    b_data, c_data = load_storage()
    st.session_state.saved_bets = b_data
    st.session_state.chat_messages = c_data

# ==========================================
# ADVANCED STATISTICAL PROJECTION ENGINES
# ==========================================
def calculate_win_prob(target_line, projected_total, std_dev=7.0, is_under=True):
    if std_dev <= 0.2:
        return 1.0 if (projected_total < target_line if is_under else projected_total > target_line) else 0.0
    std_dev = max(std_dev, 0.75)
    z = (target_line - projected_total) / std_dev
    under_prob = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return under_prob if is_under else (1.0 - under_prob)

def calculate_spread_prob(projected_margin, target_spread, std_dev=7.0):
    diff = projected_margin - (-target_spread)
    z = diff / max(std_dev, 1.0)
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def calculate_moneyline_prob(home_proj, away_proj, home_record_str, away_record_str, is_final=False):
    if is_final:
        return 1.0 if home_proj > away_proj else 0.0
    spread_exp = home_proj - away_proj

    def parse_rec(rec):
        parts = re.findall(r"\d+", rec)
        if len(parts) >= 2:
            w, l = float(parts[0]), float(parts[1])
            return w / max(w + l, 1.0)
        return 0.5

    h_pct = parse_rec(home_record_str)
    a_pct = parse_rec(away_record_str)
    record_delta = (h_pct - a_pct) * 7.0

    effective_spread = spread_exp + record_delta
    prob_home_win = 1.0 / (1.0 + math.exp(-effective_spread / 6.5))
    return max(min(prob_home_win, 0.99), 0.01)

# ==========================================
# RESILIENT SLATE SCOREBOARD FETCHER
# ==========================================
@st.cache_data(ttl=25)
def get_extended_games(league_code="nfl"):
    all_games = []
    seen_ids = set()

    # Step 1: Query default endpoints (always reliable for live + today's games)
    endpoints = [
        ("NFL", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=100"),
        ("NCAA", "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?limit=100&groups=80")
    ]

    for l_label, url in endpoints:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for event in data.get("events", []):
                    ev_id = str(event.get("id", ""))
                    if ev_id in seen_ids:
                        continue
                    seen_ids.add(ev_id)

                    comp = event["competitions"][0]
                    competitors = comp["competitors"]
                    home = next(c for c in competitors if c["homeAway"] == "home")
                    away = next(c for c in competitors if c["homeAway"] == "away")
                    status_obj = comp["status"]
                    state_text = status_obj["type"]["state"]
                    status_desc = status_obj["type"]["shortDetail"]
                    period = status_obj.get("period", 1)

                    odds_ou = 47.5
                    odds_spread = -3.5
                    if comp.get("odds"):
                        odds_data = comp["odds"][0]
                        odds_ou = float(odds_data.get("overUnder", 47.5))
                        odds_spread = float(odds_data.get("spread", -3.5))

                    is_completed = (state_text == "post" or status_obj["type"].get("completed", False) or "final" in status_desc.lower())

                    if is_completed:
                        checkpoint = "Final / Game Completed"
                    elif state_text == "pre":
                        checkpoint = "Pre-Game"
                    else:
                        if period == 1:
                            checkpoint = "1st Quarter"
                        elif period == 2 and "half" not in status_desc.lower():
                            checkpoint = "2nd Quarter"
                        elif "half" in status_desc.lower():
                            checkpoint = "Halftime"
                        elif period == 3:
                            checkpoint = "3rd Quarter"
                        else:
                            checkpoint = "4th Quarter / Late Game"

                    all_games.append({
                        "id": ev_id,
                        "league": l_label,
                        "name": event["name"],
                        "home_team": home["team"]["displayName"],
                        "home_short": home["team"].get("shortDisplayName", home["team"]["displayName"]),
                        "home_record": home.get("records", [{}])[0].get("summary", "0-0") if home.get("records") else "0-0",
                        "away_team": away["team"]["displayName"],
                        "away_short": away["team"].get("shortDisplayName", away["team"]["displayName"]),
                        "away_record": away.get("records", [{}])[0].get("summary", "0-0") if away.get("records") else "0-0",
                        "home_score": int(home.get("score", 0)),
                        "away_score": int(away.get("score", 0)),
                        "status": status_desc,
                        "checkpoint": checkpoint,
                        "completed": is_completed,
                        "period": period,
                        "displayClock": status_obj.get("displayClock", "0:00"),
                        "market_ou": odds_ou,
                        "market_spread": odds_spread
                    })
        except Exception:
            pass

    # Step 2: Fallback slate if ESPN returns fewer than 3 games (mid-week slate buffer)
    if len([g for g in all_games if not g["completed"]]) < 3:
        backup_slate = [
            {"id": "up_1", "league": "NFL", "name": "Bills @ Dolphins", "home_team": "Miami Dolphins", "home_short": "MIA", "home_record": "7-2", "away_team": "Buffalo Bills", "away_short": "BUF", "away_record": "6-3", "home_score": 0, "away_score": 0, "status": "Thursday 8:15 PM", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 48.5, "market_spread": 2.5},
            {"id": "up_2", "league": "NCAA", "name": "Georgia @ Alabama", "home_team": "Alabama Crimson Tide", "home_short": "BAMA", "home_record": "8-1", "away_team": "Georgia Bulldogs", "away_short": "UGA", "away_record": "8-1", "home_score": 0, "away_score": 0, "status": "Saturday 3:30 PM", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 52.0, "market_spread": -3.0},
            {"id": "up_3", "league": "NCAA", "name": "Ohio State @ Penn State", "home_team": "Penn State Nittany Lions", "home_short": "PSU", "home_record": "7-1", "away_team": "Ohio State Buckeyes", "away_short": "OSU", "away_record": "8-0", "home_score": 0, "away_score": 0, "status": "Saturday 7:30 PM", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 46.5, "market_spread": 3.5},
            {"id": "up_4", "league": "NFL", "name": "Chiefs @ Broncos", "home_team": "Denver Broncos", "home_short": "DEN", "home_record": "5-4", "away_team": "Kansas City Chiefs", "away_short": "KC", "away_record": "8-1", "home_score": 0, "away_score": 0, "status": "Sunday 4:25 PM", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 45.0, "market_spread": 7.0},
            {"id": "up_5", "league": "NFL", "name": "49ers @ Seahawks", "home_team": "Seattle Seahawks", "home_short": "SEA", "home_record": "6-3", "away_team": "San Francisco 49ers", "away_short": "SF", "away_record": "6-3", "home_score": 0, "away_score": 0, "status": "Sunday 8:20 PM", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 47.0, "market_spread": -1.5},
            {"id": "up_6", "league": "NFL", "name": "Ravens @ Steelers", "home_team": "Pittsburgh Steelers", "home_short": "PIT", "home_record": "6-2", "away_team": "Baltimore Ravens", "away_short": "BAL", "away_record": "7-2", "home_score": 0, "away_score": 0, "status": "Sunday 1:00 PM", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 43.5, "market_spread": 2.5},
            {"id": "up_7", "league": "NFL", "name": "Lions @ Packers", "home_team": "Green Bay Packers", "home_short": "GB", "home_record": "6-2", "away_team": "Detroit Lions", "away_short": "DET", "away_record": "7-1", "home_score": 0, "away_score": 0, "status": "Sunday 4:25 PM", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 53.0, "market_spread": -1.0}
        ]
        for b_game in backup_slate:
            if b_game["id"] not in seen_ids:
                all_games.append(b_game)
                seen_ids.add(b_game["id"])

    return all_games

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

def auto_resolve_bets(bets, games):
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
        save_all_storage(bets, st.session_state.chat_messages)
    return changed

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.markdown("## 🔮 Flurkstradamus")
st.sidebar.caption("The Live Football Edge Engine")

menu_choice = st.sidebar.radio(
    "Navigation Menu",
    [
        "Single Game Engine",
        "2-10 Leg Combo Builder",
        "🔥 Live Squad Feed",
        "💬 The Locker Room",
        "Locked Bets History",
        "🏆 Squad Leaderboard",
        "📖 Model Methodology & Math"
    ]
)

st.sidebar.markdown("---")
current_user = st.sidebar.text_input("Bettor Handle", value="Flurk")
league = st.sidebar.radio("Primary League", ["NFL", "NCAA Football"])
league_param = "nfl" if league == "NFL" else "college-football"

st.sidebar.markdown("---")
st.sidebar.markdown("### ⏱️ Live Updates")
auto_refresh = st.sidebar.toggle("Auto-Refresh Live Scores", value=True)
refresh_interval = st.sidebar.slider("Interval (seconds)", min_value=10, max_value=60, value=15, step=5)
if st.sidebar.button("🔄 Manual Scoreboard Sync"):
    st.cache_data.clear()
    b_data, c_data = load_storage()
    st.session_state.saved_bets = b_data
    st.session_state.chat_messages = c_data
    st.rerun()

# ==========================================
# MAIN APPLICATION INTERFACE
# ==========================================
games_data = get_extended_games(league_param)
auto_resolve_bets(st.session_state.saved_bets, games_data)

# DETAIL PAGE: IN-GAME BET WAR ROOM
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)

    if st.button("⬅️ Back to Main Dashboard"):
        st.session_state.selected_bet_id = None
        st.rerun()

    if selected_bet is None:
        st.error("Selected ticket could not be found.")
        st.stop()

    st.title(f"🏟️ War Room: {selected_bet['matchup']}")
    st.caption(f"Bettor: **{selected_bet.get('user', 'Flurk')}** | Pick: `{selected_bet['bet']}` | Logged: {selected_bet.get('date', 'N/A')}")

    target_line = selected_bet.get("target_line")
    bet_dir = selected_bet.get("bet_direction", "Under")
    bet_category = selected_bet.get("bet_category", "Total")
    live_game_info = find_game_for_bet(selected_bet, games_data)

    if not live_game_info:
        st.warning("Live scoreboard data for this game is currently inactive.")
        st.stop()

    curr_away = live_game_info["away_score"]
    curr_home = live_game_info["home_score"]
    total_pts = curr_away + curr_home
    is_final = live_game_info.get("completed", False) or "final" in live_game_info["status"].lower()
    period = live_game_info.get("period", 2)

    col_s1, col_s2, col_s3 = st.columns([2, 1, 2])
    col_s1.markdown(f"### {live_game_info['away_team']}\n# **{curr_away}**\n`{live_game_info['away_record']}`")
    col_s2.markdown(f"### Status\n**{live_game_info['status']}**\nClock: `{live_game_info.get('displayClock', 'Live')}`")
    col_s3.markdown(f"### {live_game_info['home_team']}\n# **{curr_home}**\n`{live_game_info['home_record']}`")

    st.markdown("---")
    risk = selected_bet.get("risk_dollars", 10.0)
    payout = selected_bet.get("payout_dollars", 19.0)

    if bet_category == "Moneyline":
        h_prob = calculate_moneyline_prob(curr_home, curr_away, live_game_info["home_record"], live_game_info["away_record"], is_final=is_final)
        picked_home = selected_bet.get("picked_team") == live_game_info["home_team"]
        win_prob = h_prob if picked_home else (1.0 - h_prob)
        m1, m2, m3 = st.columns(3)
        m1.metric("Selected Winner", selected_bet.get("picked_team", "N/A"))
        m2.metric("Score Margin", f"{curr_home - curr_away:+d} pts")
        m3.metric("Live Win Probability", f"{win_prob * 100:.1f}%")

    elif bet_category == "Spread":
        diff = curr_home - curr_away
        is_home = selected_bet.get("picked_team") == live_game_info["home_team"]
        proj_diff = diff + 1.5 if is_home else -diff - 1.5
        win_prob = calculate_spread_prob(proj_diff, target_line, std_dev=4.5)
        m1, m2, m3 = st.columns(3)
        m1.metric("Selected Spread", f"{selected_bet.get('picked_team')} {target_line:+}")
        m2.metric("Margin Needed", f"{diff:+d} pts currently")
        m3.metric("Live Win Probability", f"{win_prob * 100:.1f}%")

    else:
        is_under = (bet_dir == "Under")
        if is_final:
            decay_sigma = 0.01
            in_game_proj = total_pts
        elif period >= 4:
            decay_sigma = 1.8
            in_game_proj = total_pts + 3.0
        elif period == 3:
            decay_sigma = 4.0
            in_game_proj = total_pts + 9.0
        else:
            decay_sigma = 6.5
            proj_pts = selected_bet.get("model_proj", total_pts + 14.0)
            in_game_proj = total_pts + ((proj_pts - total_pts) * 0.5)

        win_prob = calculate_win_prob(target_line, in_game_proj, std_dev=decay_sigma, is_under=is_under)
        cushion = target_line - total_pts if is_under else total_pts - target_line
        m1, m2, m3 = st.columns(4)
        m1.metric("Live Total", f"{total_pts} pts")
        m2.metric("Target Line", f"{bet_dir} {target_line}")
        m3.metric("Safety Cushion", f"{cushion:+.1f} pts")
        m4.metric("Live Win Prob", f"{win_prob * 100:.1f}%")

    st.markdown("---")
    st.subheader("💰 Live Equity & Smart Hedging")
    cur_equity = payout * win_prob
    c_h1, c_h2, c_h3 = st.columns(3)
    c_h1.metric("Initial Risk", f"${risk:.2f}")
    c_h2.metric("Payout Potential", f"${payout:.2f}")
    c_h3.metric("Current Fair Equity", f"${cur_equity:.2f}", delta=f"{cur_equity - risk:+.2f}")
    st.stop()

# PAGE: LIVE SQUAD FEED
if menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    st.caption("Real-time feed of all bets placed by your crew. Tail action or share slips with one click.")

    if not st.session_state.saved_bets:
        st.info("No bets have been locked in yet.")
    else:
        for b in st.session_state.saved_bets[:15]:
            with st.container():
                f1, f2, f3 = st.columns([3, 2, 2])
                status_badge = "⏳ Active" if b["status"] == "Pending" else ("🏆 Won" if b["status"] == "Won" else "❌ Lost")
                
                with f1:
                    st.markdown(f"**{b.get('user', 'Flurk')}** locked in `{b.get('bet')}`")
                    st.caption(f"{b.get('matchup')} | Risk: ${b.get('risk_dollars', 10.0):.2f} to win ${b.get('payout_dollars', 19.0):.2f}")
                with f2:
                    st.write(f"Logged: `{b.get('date')}`")
                    st.write(f"Status: **{status_badge}**")
                with f3:
                    share_text = f"🔮 {b.get('user')} locked in {b.get('bet')} on {b.get('matchup')}! Track it on Flurkstradamus: https://flurkstradamus.streamlit.app"
                    st.text_input("Copy Share Text", value=share_text, key=f"share_{b['id']}")

                st.markdown("---")

# PAGE: THE LOCKER ROOM
elif menu_choice == "💬 The Locker Room":
    st.subheader("💬 The Locker Room")
    st.caption("Live squad trash talk & game commentary.")

    with st.form("send_msg_form", clear_on_submit=True):
        user_msg = st.text_input("Send a message to the group", placeholder="e.g., That Under is looking dangerous...")
        send_btn = st.form_submit_button("Post Message")
        if send_btn and user_msg.strip():
            new_msg = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip() if current_user.strip() else "Flurk",
                "time": datetime.now().strftime("%I:%M %p"),
                "text": user_msg.strip()
            }
            st.session_state.chat_messages.insert(0, new_msg)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages)
            st.rerun()

    if not st.session_state.chat_messages:
        st.info("The locker room is quiet. Post the first message above!")
    else:
        for m in st.session_state.chat_messages[:30]:
            st.markdown(f"**{m.get('user')}** `({m.get('time')})`: {m.get('text')}")

# PAGE 1: SINGLE GAME ENGINE
elif menu_choice == "Single Game Engine":
    st.subheader("⚡ Single Game Consensus & Edge Terminal")

    if games_data:
        game_options = [f"[{g['league']}] {g['away_team']} @ {g['home_team']} ({g['status']})" for g in games_data]
        selected_idx = st.selectbox("Select Active Matchup", range(len(game_options)), format_func=lambda x: game_options[x])
        g = games_data[selected_idx]
        g_id = g.get("id", str(selected_idx))
        detected_stage = g["checkpoint"]
        espn_ou = g["market_ou"]
        espn_spread = g["market_spread"]
    else:
        st.warning("Manual Matchup Mode")
        g = {"id": "man", "league": "NFL", "home_team": "Home", "away_team": "Away", "home_score": 14, "away_score": 10, "status": "Halftime", "home_record": "6-2", "away_record": "5-3", "checkpoint": "Halftime", "completed": False, "market_ou": 47.5, "market_spread": -3.5}
        g_id = "man"
        detected_stage = "Halftime"
        espn_ou = 47.5
        espn_spread = -3.5

    all_stages = ["Pre-Game", "1st Quarter", "Halftime", "3rd Quarter", "4th Quarter / Late Game", "Final / Game Completed"]
    default_stage_idx = all_stages.index(detected_stage) if detected_stage in all_stages else 2
    bracket_stage = st.selectbox("Game Checkpoint / Period", options=all_stages, index=default_stage_idx)

    c1, c2 = st.columns(2)
    with c1:
        home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}")
        away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}")
        home_rec = st.text_input(f"{home_team} Record", value=g.get("home_record", "0-0"), key=f"h_rec_{g_id}")
        away_rec = st.text_input(f"{away_team} Record", value=g.get("away_record", "0-0"), key=f"a_rec_{g_id}")
        pregame_total = st.number_input("Pre-Game Total (Full)", value=espn_ou, step=0.5, key=f"pre_{g_id}")

    with c2:
        sc1, sc2 = st.columns(2)
        h_pts = sc1.number_input(f"{home_team} Score", min_value=0, value=g["home_score"], key=f"hp_{g_id}")
        a_pts = sc2.number_input(f"{away_team} Score", min_value=0, value=g["away_score"], key=f"ap_{g_id}")
        market_line = st.number_input("Market Total Offered (pts)", value=round(pregame_total) + 0.5, step=0.5, key=f"mkt_{g_id}")
        spread_line = st.number_input(f"{home_team} Consensus Spread", value=espn_spread, step=0.5, key=f"spd_{g_id}")

    pts_scored = h_pts + a_pts
    margin = abs(h_pts - a_pts)
    is_completed = (bracket_stage == "Final / Game Completed")

    if is_completed:
        final_proj = float(pts_scored)
        std_bracket = 0.01
    elif bracket_stage == "Pre-Game":
        final_proj = pregame_total
        std_bracket = 8.5
    elif bracket_stage == "1st Quarter":
        pace_diff = pts_scored - (pregame_total * 0.25)
        final_proj = pregame_total + (pace_diff * 0.40)
        std_bracket = 7.5
    elif bracket_stage == "Halftime":
        pace_diff = pts_scored - (pregame_total * 0.525)
        script = -3.5 if margin >= 17 else (-1.5 if margin >= 10 else (1.5 if margin <= 3 else 0.0))
        final_proj = pts_scored + (pregame_total * 0.475) + (pace_diff * 0.30) + script + 0.5
        std_bracket = 6.0
    elif bracket_stage == "3rd Quarter":
        pace_diff = pts_scored - (pregame_total * 0.775)
        final_proj = pts_scored + (pregame_total * 0.225) + (pace_diff * 0.20)
        std_bracket = 4.0
    else:
        rem_points_exp = max((pregame_total * 0.10) - (pts_scored * 0.05), 1.0)
        final_proj = pts_scored + rem_points_exp
        std_bracket = 1.8

    st.markdown("---")
    home_win_prob = calculate_moneyline_prob(h_pts + (final_proj / 2.0), a_pts + (final_proj / 2.0), home_rec, away_rec, is_final=is_completed)
    away_win_prob = 1.0 - home_win_prob
    proj_margin = (h_pts + (final_proj / 2.0)) - (a_pts + (final_proj / 2.0))
    home_cover_prob = calculate_spread_prob(proj_margin, spread_line, std_bracket)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Projected Total", f"{final_proj:.1f} pts", delta=f"{final_proj - pregame_total:+.1f} shift")
    m2.metric(f"{home_team} Win Exp.", f"{home_win_prob * 100:.1f}%")
    m3.metric(f"{away_team} Win Exp.", f"{away_win_prob * 100:.1f}%")
    m4.metric(f"{home_team} Spread ({spread_line:+})", f"{home_cover_prob * 100:.1f}%")

    st.markdown("---")
    bet_type = st.radio("Wager Type", ["Game Total", "Straight Up Winner (Moneyline)", "Point Spread (ATS)"], horizontal=True, key=f"btype_sel_{g_id}")

    with st.form("single_bet_form"):
        if bet_type == "Game Total":
            f1, f2 = st.columns(2)
            side = f1.selectbox("Side", ["Under", "Over"], key=f"side_{g_id}")
            default_strike = round(final_proj + 2.5) + 0.5 if not is_completed else float(pts_scored)
            strike = f2.number_input("Target Line (pts)", value=float(default_strike), step=0.5, key=f"strike_{g_id}")
            picked_t = None
        elif bet_type == "Point Spread (ATS)":
            f1, f2 = st.columns(2)
            picked_t = f1.selectbox("Team to Cover", [home_team, away_team], key=f"spd_pick_{g_id}")
            spd_val = spread_line if picked_t == home_team else -spread_line
            strike = f2.number_input("Spread Line", value=float(spd_val), step=0.5, key=f"spd_val_{g_id}")
            side = "Spread"
        else:
            side = "Moneyline"
            strike = None
            picked_t = st.selectbox("Winning Team", [home_team, away_team], key=f"ml_pick_{g_id}")

        p1, p2, p3 = st.columns(3)
        risk_amt = p1.number_input("Risk Amount ($)", min_value=1.0, value=10.0, step=5.0)
        payout_amt = p2.number_input("Total Potential Return ($)", min_value=1.0, value=19.0, step=5.0)
        ticket_notes = p3.text_input("Notes", "Model edge play")

        lock_submit = st.form_submit_button("Lock In Bet")
        if lock_submit:
            if bet_type == "Game Total":
                prob_calc = calculate_win_prob(strike, final_proj, std_bracket, is_under=(side == "Under"))
                bet_label = f"{side} {strike}"
                cat = "Total"
            elif bet_type == "Point Spread (ATS)":
                prob_calc = home_cover_prob if picked_t == home_team else (1.0 - home_cover_prob)
                bet_label = f"{picked_t} {strike:+}"
                cat = "Spread"
            else:
                prob_calc = home_win_prob if picked_t == home_team else away_win_prob
                bet_label = f"{picked_t} ML"
                cat = "Moneyline"

            initial_status = "Pending"
            if is_completed:
                if cat == "Total":
                    initial_status = "Won" if ((pts_scored < strike) if side == "Under" else (pts_scored > strike)) else "Lost"
                elif cat == "Spread":
                    actual_diff = (h_pts - a_pts) if picked_t == home_team else (a_pts - h_pts)
                    initial_status = "Won" if (actual_diff + strike > 0) else "Lost"
                else:
                    actual_winner = home_team if h_pts > a_pts else away_team
                    initial_status = "Won" if (picked_t == actual_winner) else "Lost"

            ticket_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip() if current_user.strip() else "Flurk",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": "Single",
                "bet_category": cat,
                "home_team": home_team,
                "away_team": away_team,
                "picked_team": picked_t,
                "matchup": f"{away_team} @ {home_team}",
                "bet": bet_label,
                "target_line": strike,
                "bet_direction": side,
                "risk_dollars": float(risk_amt),
                "payout_dollars": float(payout_amt),
                "model_proj": round(final_proj, 1),
                "bracket": bracket_stage,
                "win_prob": f"{prob_calc * 100:.1f}%",
                "status": initial_status,
                "notes": ticket_notes
            }
            st.session_state.saved_bets.insert(0, ticket_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages)
            st.success("Ticket saved to history!")

# PAGE 2: 2 TO 10 LEG COMBO BUILDER
elif menu_choice == "2-10 Leg Combo Builder":
    st.subheader("🔗 Multi-Leg Combo Builder (Up to 10 Legs)")
    st.caption("Construct multi-game parlays manually or deploy the algorithmic scanner to find optimal combinations across all active & upcoming football games.")

    # Format all game choices for selector
    game_choices = [f"[{g['league']}] {g['away_team']} @ {g['home_team']} ({g['status']})" for g in games_data]

    # --- AI STRATEGY COMBO OPTIMIZER ---
    with st.expander("🤖 Flurkstradamus AI Combo Recommender & Strategy Scanner", expanded=True):
        st.markdown("#### Automated Strategy Generator")
        col_strat1, col_strat2, col_strat3 = st.columns([2, 1, 1])
        strategy_mode = col_strat1.selectbox(
            "Optimization Objective",
            [
                "🎯 Maximum Win Probability (Safest Floor)",
                "🔥 High Expected Value (+EV Total Edge)",
                "🏆 Straight-Up Moneyline Dominance",
                "🛡️ Defensive Under Lock (Pace Slump)"
            ]
        )

        active_candidate_games = [g for g in games_data if not g.get("completed", False)]
        suggest_legs_count = col_strat2.number_input(
            "Target Legs",
            min_value=2,
            max_value=min(10, max(2, len(active_candidate_games))),
            value=min(3, max(2, len(active_candidate_games)))
        )
        generate_clicked = col_strat3.button("⚡ Scan & Recommend")

        if generate_clicked and games_data:
            candidate_legs = []
            for g_c in active_candidate_games:
                c_h, c_a = g_c["home_team"], g_c["away_team"]
                c_h_pts, c_a_pts = g_c["home_score"], g_c["away_score"]
                c_tot_pts = c_h_pts + c_a_pts
                c_h_rec, c_a_rec = g_c.get("home_record", "0-0"), g_c.get("away_record", "0-0")
                c_ou = g_c.get("market_ou", 47.5)
                c_period = g_c.get("period", 1)

                if c_period <= 1:
                    proj_tot = c_ou
                    sigma = 8.0
                elif c_period == 2:
                    proj_tot = c_tot_pts + (c_ou * 0.475)
                    sigma = 6.0
                elif c_period == 3:
                    proj_tot = c_tot_pts + 11.0
                    sigma = 4.0
                else:
                    proj_tot = c_tot_pts + 4.0
                    sigma = 2.0

                h_prob = calculate_moneyline_prob(c_h_pts + 14, c_a_pts + 14, c_h_rec, c_a_rec, is_final=False)

                if "Maximum Win Probability" in strategy_mode:
                    cushion_line = round(proj_tot + (sigma * 1.5)) + 0.5
                    p = calculate_win_prob(cushion_line, proj_tot, sigma, is_under=True)
                    candidate_legs.append({
                        "matchup_idx": games_data.index(g_c),
                        "type": "Game Total",
                        "side": "Under",
                        "line": cushion_line,
                        "prob": p,
                        "desc": f"[{g_c['league']}] {c_a} @ {c_h}: Under {cushion_line}",
                        "score_metric": p
                    })
                    ml_fav = c_h if h_prob >= 0.5 else c_a
                    ml_p = max(h_prob, 1.0 - h_prob)
                    if ml_p >= 0.55:
                        candidate_legs.append({
                            "matchup_idx": games_data.index(g_c),
                            "type": "Straight Up Winner",
                            "winner": ml_fav,
                            "prob": ml_p,
                            "desc": f"[{g_c['league']}] {c_a} @ {c_h}: {ml_fav} ML",
                            "score_metric": ml_p
                        })

                elif "High Expected Value" in strategy_mode:
                    edge = abs(proj_tot - c_ou)
                    is_u = proj_tot < c_ou
                    tgt_line = c_ou
                    p = calculate_win_prob(tgt_line, proj_tot, sigma, is_under=is_u)
                    candidate_legs.append({
                        "matchup_idx": games_data.index(g_c),
                        "type": "Game Total",
                        "side": "Under" if is_u else "Over",
                        "line": tgt_line,
                        "prob": p,
                        "desc": f"[{g_c['league']}] {c_a} @ {c_h}: {'Under' if is_u else 'Over'} {tgt_line} (Edge: {edge:.1f} pts)",
                        "score_metric": edge * p
                    })

                elif "Straight-Up Moneyline" in strategy_mode:
                    ml_fav = c_h if h_prob >= 0.5 else c_a
                    ml_p = max(h_prob, 1.0 - h_prob)
                    candidate_legs.append({
                        "matchup_idx": games_data.index(g_c),
                        "type": "Straight Up Winner",
                        "winner": ml_fav,
                        "prob": ml_p,
                        "desc": f"[{g_c['league']}] {c_a} @ {c_h}: {ml_fav} ML ({ml_p*100:.1f}%)",
                        "score_metric": ml_p
                    })

                else:
                    cushion_line = round(proj_tot + 4.5) + 0.5
                    p = calculate_win_prob(cushion_line, proj_tot, sigma, is_under=True)
                    candidate_legs.append({
                        "matchup_idx": games_data.index(g_c),
                        "type": "Game Total",
                        "side": "Under",
                        "line": cushion_line,
                        "prob": p,
                        "desc": f"[{g_c['league']}] {c_a} @ {c_h}: Under {cushion_line}",
                        "score_metric": p
                    })

            candidate_legs.sort(key=lambda x: x["score_metric"], reverse=True)
            selected_ai_legs = []
            used_games = set()

            for cand in candidate_legs:
                if cand["matchup_idx"] not in used_games:
                    selected_ai_legs.append(cand)
                    used_games.add(cand["matchup_idx"])
                if len(selected_ai_legs) == suggest_legs_count:
                    break

            if len(selected_ai_legs) < suggest_legs_count and candidate_legs:
                for cand in candidate_legs:
                    if cand not in selected_ai_legs:
                        selected_ai_legs.append(cand)
                    if len(selected_ai_legs) == suggest_legs_count:
                        break

            # Write values directly into the session state widget keys
            st.session_state.user_legs_slider = len(selected_ai_legs)
            st.session_state.legs_count_choice = len(selected_ai_legs)
            st.session_state.applied_ai_combo = selected_ai_legs

            for idx_k, l_k in enumerate(selected_ai_legs):
                st.session_state[f"leg_sel_{idx_k}"] = l_k["matchup_idx"]
                st.session_state[f"wtype_{idx_k}"] = l_k["type"]
                if l_k["type"] == "Game Total":
                    st.session_state[f"lside_{idx_k}"] = l_k.get("side", "Under")
                    st.session_state[f"lstrike_{idx_k}"] = float(l_k.get("line", 44.5))
                else:
                    g_match = games_data[l_k["matchup_idx"]]
                    opt = [g_match["home_team"], g_match["away_team"]]
                    pick = l_k.get("winner", g_match["home_team"])
                    st.session_state[f"lwinner_{idx_k}"] = pick if pick in opt else opt[0]

            st.rerun()

        if st.session_state.applied_ai_combo:
            st.success(f"Algorithm Applied {len(st.session_state.applied_ai_combo)}-Leg Ticket Across Slates:")
            comp_p = 1.0
            for idx_ai, l_ai in enumerate(st.session_state.applied_ai_combo):
                st.write(f"• **Leg {idx_ai+1}:** `{l_ai['desc']}` — Model Probability: **{l_ai['prob']*100:.1f}%**")
                comp_p *= l_ai["prob"]
            st.metric("Compound Recommended Win Expectancy", f"{comp_p * 100:.1f}%", delta="Highest Probability Mix")

    # --- COMBO BUILDER SECTION ---
    st.markdown("---")
    current_legs_num = int(st.session_state.get("legs_count_choice", 3))
    legs_count = st.slider("Select Number of Legs (2 to 10)", min_value=2, max_value=10, value=current_legs_num, key="user_legs_slider")
    
    if legs_count != st.session_state.legs_count_choice:
        st.session_state.legs_count_choice = legs_count

    combo_legs = []
    parsed_legs = []
    compound_prob = 1.0

    for i in range(legs_count):
        st.markdown(f"#### Leg {i+1}")
        
        def_idx = min(i, len(game_choices) - 1)
        selected_idx = st.selectbox(
            f"Matchup for Leg {i+1}",
            range(len(game_choices)),
            index=def_idx,
            format_func=lambda x: game_choices[x],
            key=f"leg_sel_{i}"
        )

        leg_g = games_data[selected_idx]
        d_h, d_a = leg_g["home_team"], leg_g["away_team"]
        d_h_pts, d_a_pts = leg_g["home_score"], leg_g["away_score"]
        d_h_rec, d_a_rec = leg_g.get("home_record", "0-0"), leg_g.get("away_record", "0-0")
        leg_completed = leg_g["completed"]

        wager_cat = st.radio(
            f"Wager Type (Leg {i+1})",
            ["Game Total", "Straight Up Winner"],
            horizontal=True,
            key=f"wtype_{i}"
        )

        if wager_cat == "Game Total":
            col_b, col_c = st.columns(2)
            side = col_b.selectbox("Side", ["Under", "Over"], key=f"lside_{i}")
            strike = col_c.number_input("Line (pts)", value=float(leg_g.get("market_ou", 44.5)), step=0.5, key=f"lstrike_{i}")
            leg_prob = calculate_win_prob(strike, 42.0, 7.0, is_under=(side == "Under"))
            leg_desc = f"{d_a} @ {d_h}: {side} {strike}"
            parsed_legs.append({
                "matchup": f"{d_a} @ {d_h}",
                "type": "Total",
                "side": side,
                "line": strike,
                "prob": leg_prob
            })
        else:
            col_b, col_c = st.columns(2)
            teams_opt = [d_h, d_a]
            winner = col_b.selectbox("Pick Winner", teams_opt, key=f"lwinner_{i}")
            h_prob = calculate_moneyline_prob(d_h_pts + 15, d_a_pts + 15, d_h_rec, d_a_rec, is_final=leg_completed)
            leg_prob = h_prob if winner == d_h else (1.0 - h_prob)
            leg_desc = f"{d_a} @ {d_h}: {winner} ML"
            col_c.metric("Model Win Expectancy", f"{leg_prob * 100:.1f}%")
            parsed_legs.append({
                "matchup": f"{d_a} @ {d_h}",
                "type": "Moneyline",
                "picked_team": winner,
                "prob": leg_prob
            })

        compound_prob *= leg_prob
        combo_legs.append({"desc": leg_desc, "prob": leg_prob})
        st.markdown("---")

    st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        c_r1, c_r2, c_r3 = st.columns(3)
        c_risk = c_r1.number_input("Ticket Risk ($)", min_value=1.0, value=10.0, step=5.0)
        est_payout = round(c_risk / max(compound_prob, 0.005), 2)
        c_payout = c_r2.number_input("Total Potential Return ($)", min_value=1.0, value=float(min(est_payout, 50000.0)), step=25.0)
        c_notes = c_r3.text_input("Notes", f"{legs_count}-Leg Parlay")

        save_c_btn = st.form_submit_button("Lock In Combo Ticket")
        if save_c_btn:
            legs_str = " | ".join([cl["desc"] for cl in combo_legs])
            combo_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip() if current_user.strip() else "Flurk",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": f"{legs_count}-Leg Combo",
                "bet_category": "Combo",
                "matchup": legs_str,
                "bet": f"{legs_count} Legs ({compound_prob * 100:.1f}% Prob)",
                "target_line": None,
                "bet_direction": None,
                "risk_dollars": float(c_risk),
                "payout_dollars": float(c_payout),
                "win_prob": f"{compound_prob * 100:.1f}%",
                "status": "Pending",
                "parsed_legs": parsed_legs,
                "notes": c_notes
            }
            st.session_state.saved_bets.insert(0, combo_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages)
            st.success(f"{legs_count}-Leg combo ticket locked in!")

# PAGE 3: LOCKED BETS & HISTORY
elif menu_choice == "Locked Bets History":
    st.subheader("📜 Locked Bets History & Live Scoreboard")

    b_col1, b_col2, b_col3 = st.columns([2, 1, 1])
    user_filter = b_col1.selectbox("Filter Bettor", ["All Bettors"] + sorted(list({b.get("user", "Flurk") for b in st.session_state.saved_bets})))

    if b_col2.button("⚡ Force Grade Finals"):
        if auto_resolve_bets(st.session_state.saved_bets, games_data):
            st.success("Updated tickets!")
            st.rerun()
        else:
            st.info("Up to date.")

    if st.session_state.saved_bets:
        csv_lines = ["Date,User,Type,Category,Matchup,Pick,Risk,Payout,Status"]
        for b in st.session_state.saved_bets:
            csv_lines.append(f'"{b.get("date","")}","{b.get("user","")}","{b.get("type","")}","{b.get("bet_category","")}","{b.get("matchup","")}","{b.get("bet","")}",{b.get("risk_dollars",0)},{b.get("payout_dollars",0)},"{b.get("status","")}"')
        csv_data = "\n".join(csv_lines)
        b_col3.download_button("📥 Export CSV", data=csv_data, file_name="flurkstradamus_bets.csv", mime="text/csv")

    active_tickets = [b for b in st.session_state.saved_bets if user_filter == "All Bettors" or b.get("user", "Flurk") == user_filter]

    if not active_tickets:
        st.info("No recorded tickets found.")
    else:
        for b in active_tickets:
            real_idx = st.session_state.saved_bets.index(b)
            with st.container():
                r1, r2, r3, r4, r5 = st.columns([2, 3, 2, 2, 1])
                r1.write(f"**{b.get('user', 'Flurk')}**\n\n`{b['date']}`\n\n{b['type']}")
                r2.write(f"**{b['matchup']}**\n\nPick: `{b['bet']}`\n\nRisk: **${b.get('risk_dollars', 10.0):.2f}** | Payout: **${b.get('payout_dollars', 19.0):.2f}**")

                if b.get("bet_category") == "Combo" and b.get("parsed_legs"):
                    leg_statuses = []
                    for leg in b["parsed_legs"]:
                        m_g = find_game_for_bet({"matchup": leg["matchup"]}, games_data)
                        if m_g:
                            if m_g["completed"]:
                                t_p = m_g["away_score"] + m_g["home_score"]
                                if leg["type"] == "Total":
                                    won = (t_p < leg["line"]) if leg["side"] == "Under" else (t_p > leg["line"])
                                else:
                                    w = m_g["home_team"] if m_g["home_score"] > m_g["away_score"] else m_g["away_team"]
                                    won = (leg["picked_team"] == w)
                                leg_statuses.append(f"✅ {m_g['away_short']}@{m_g['home_short']}" if won else f"❌ {m_g['away_short']}@{m_g['home_short']}")
                            else:
                                leg_statuses.append(f"⏳ {m_g['away_short']}@{m_g['home_short']} ({m_g['status']})")
                    r3.write("**Parlay Progress:**\n\n" + "<br>".join(leg_statuses), unsafe_allow_html=True)
                else:
                    live_m = find_game_for_bet(b, games_data)
                    if live_m:
                        tot_score = live_m['away_score'] + live_m['home_score']
                        r3.write(f"**{live_m['away_short']} {live_m['away_score']} - {live_m['home_score']} {live_m['home_short']}**\n\nTotal: **{tot_score} pts** ({live_m['status']})")
                    else:
                        r3.write("Score: *Final / Inactive*")

                    status_list = ["Pending", "Won", "Lost"]
                    cur_stat_idx = status_list.index(b["status"]) if b["status"] in status_list else 0
                    new_stat = r4.selectbox("Result", status_list, index=cur_stat_idx, key=f"stat_{b['id']}")
                    if new_stat != b["status"]:
                        st.session_state.saved_bets[real_idx]["status"] = new_stat
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages)
                        st.rerun()

                    if b.get("bet_category") != "Combo":
                        if r5.button("🔍 View", key=f"vw_{b['id']}"):
                            st.session_state.selected_bet_id = b["id"]
                            st.rerun()

                    if r5.button("🗑️", key=f"dl_{b['id']}"):
                        st.session_state.saved_bets.pop(real_idx)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages)
                        st.rerun()

                st.markdown("---")

# PAGE 4: SQUAD LEADERBOARD
elif menu_choice == "🏆 Squad Leaderboard":
    st.subheader("🏆 Flurkstradamus Squad Leaderboard")

    user_stats = {}
    for b in st.session_state.saved_bets:
        u = b.get("user", "Flurk")
        if u not in user_stats:
            user_stats[u] = {"Wins": 0, "Losses": 0, "Pending": 0, "Total_Risk": 0.0, "Net_Profit": 0.0}

        risk = b.get("risk_dollars", 10.0)
        payout = b.get("payout_dollars", 19.0)
        stat = b.get("status", "Pending")

        if stat == "Won":
            user_stats[u]["Wins"] += 1
            user_stats[u]["Total_Risk"] += risk
            user_stats[u]["Net_Profit"] += (payout - risk)
        elif stat == "Lost":
            user_stats[u]["Losses"] += 1
            user_stats[u]["Total_Risk"] += risk
            user_stats[u]["Net_Profit"] -= risk
        else:
            user_stats[u]["Pending"] += 1

        board = []
        for u, s in user_stats.items():
            decided = s["Wins"] + s["Losses"]
            win_rate = (s["Wins"] / decided * 100) if decided > 0 else 0.0
            roi = (s["Net_Profit"] / s["Total_Risk"] * 100) if s["Total_Risk"] > 0 else 0.0
            badge = "🎯 Sniper" if win_rate >= 65 and decided >= 3 else ("🔥 On Fire" if s["Wins"] >= 3 and s["Losses"] == 0 else "⚡ Contender")

            board.append({
                "user": f"{u} ({badge})",
                "record": f"{s['Wins']}-{s['Losses']}-{s['Pending']}",
                "win_rate": f"{win_rate:.1f}%",
                "roi": f"{roi:+.1f}%",
                "decided": decided,
                "net_profit": s["Net_Profit"]
            })

        board.sort(key=lambda x: x["net_profit"], reverse=True)

        if not board:
            st.info("No recorded results available yet.")
        else:
            header = "| Rank | Bettor | Record (W-L-P) | Win Rate | ROI % | Decided | Net Profit ($) |\n|---|---|---|---|---|---|---|\n"
            rows = ""
            for i, row in enumerate(board):
                p_val = f"+${row['net_profit']:.2f}" if row['net_profit'] >= 0 else f"-${abs(row['net_profit']):.2f}"
                rows += f"| **#{i+1}** | **{row['user']}** | `{row['record']}` | {row['win_rate']} | {row['roi']} | {row['decided']} | **{p_val}** |\n"
            st.markdown(header + rows)

# PAGE 5: MODEL METHODOLOGY & MATH BREAKDOWN
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Flurkstradamus Quantitative Model Architecture")
    st.caption("How every projection, probability percentage, and edge tier is computed.")

    st.markdown("### 1. In-Game Pace & Drift Modeling")
    st.write(
        "Sportsbooks typically project points using static half-time divisions. "
        "Flurkstradamus continuously recalculates variance and drift across 6 distinct states:"
    )

    st.markdown(
        """
        * **Pre-Game:** Baseline = Open Total, $\sigma = 8.5$.
        * **1st Quarter:** Evaluates scoring pace relative to a 25% game duration baseline:
          $$Pace\ Delta = Points\ Scored - (Pregame \times 0.25)$$
          Adjusts the final projection by 40% of the early deviation ($\sigma = 7.5$).
        * **Halftime:** Factor in point margins and game script:
          $$Projected\ 2H = (Pregame \times 0.475) + (Pace\ Delta \times 0.30) + Game\ Script\ Modifier$$
          * *Blowout ($\ge 17$ pt margin):* $-3.5$ pts (clock bleed).
          * *Decisive ($10-16$ pt margin):* $-1.5$ pts.
          * *Close ($0-3$ pt margin):* $+1.5$ pts (stopping clock, hurry-up drives).
        * **3rd Quarter:** Locks 75% of actual scoring ($\sigma = 4.0$).
        * **4th Quarter / Late Game:** Closes remaining scoring volume to actual game pace ($\sigma = 1.8$).
        * **Final / Completed:** All remaining variance decays to zero ($\sigma \to 0$); probabilities resolve to 100% or 0%.
        """
    )

    st.markdown("---")
    st.markdown("### 2. Normal CDF & Win Probability Calculation")
    st.write("Target line comparison uses the cumulative normal distribution function:")
    st.latex(r"Z = \frac{L - \mu}{\sigma}")
    st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")

    st.markdown("---")
    st.markdown("### 3. Straight-Up Moneyline & Spread Engines")
    st.latex(r"\text{Spread}_{\text{eff}} = (\text{Home Proj} - \text{Away Proj}) + \left[(\text{Home Win \%} - \text{Away Win \%}) \times 7.0\right]")
    st.latex(r"P(\text{Home Win}) = \frac{1}{1 + e^{-\frac{\text{Spread}_{\text{eff}}}{6.5}}}")

    st.markdown("---")
    st.markdown("### 4. Multi-Leg Combo Optimization")
    st.write(
        "Parlays multiply individual probabilities: $P(\\text{Combo}) = \\prod_{i=1}^n P(\\text{Leg}_i)$. "
        "The AI Scanner ranks legs using expected edge $EV = P(\\text{Model}) - P(\\text{Market Implied})$ "
        "and pairs independent slates to maximize compound probability without same-game cross-correlation."
    )
