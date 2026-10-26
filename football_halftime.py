import streamlit as st
import requests
import re
from datetime import datetime, timedelta

# Import modular engines
from config import GROUP_PASSCODE, DEFAULT_LOGO, OFFICIAL_ABBR_MAP
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob
from database import load_storage, save_all_storage, find_game_for_bet, auto_resolve_bets

st.set_page_config(
    page_title="Flurkstradamus Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Responsive Desktop + Mobile styling & Zero-gap alignment
st.markdown("""
<style>
    @media (min-width: 768px) {
        .block-container {
            padding-top: 4.5rem !important;
            padding-bottom: 3rem !important;
            padding-left: 2.5rem !important;
            padding-right: 2.5rem !important;
            max-width: 1200px !important;
        }
    }
    @media (max-width: 767px) {
        .block-container {
            padding-top: 3.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
    }

    /* FIX 1: REMOVE GAP BETWEEN SIDEBAR BUTTONS */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.2rem !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        text-align: left !important;
        justify-content: flex-start !important;
        display: flex !important;
        align-items: center !important;
        padding-left: 12px !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
        min-height: 2.0rem !important;
        height: 2.0rem !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button * {
        text-align: left !important;
        justify-content: flex-start !important;
    }

    /* FIX 2: TIGHT, EVEN PADDING IN RECOMMENDATION ROWS */
    div.rec-card-container div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        background-color: rgba(255, 255, 255, 0.02) !important;
        padding: 4px 10px !important;
        margin-top: 2px !important;
        margin-bottom: 2px !important;
        min-height: unset !important;
        height: auto !important;
        transition: all 0.2s ease-in-out;
    }
    div.rec-card-container div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border-color: rgba(34, 197, 94, 0.4) !important;
    }
    div.rec-card-container div[data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 0 !important;
        margin: 0 !important;
        gap: 0 !important;
    }
    div.rec-card-container div[data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
        font-size: 0.85rem !important;
    }
    div.rec-card-container div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
        gap: 0.25rem !important;
    }

    /* FIX 3: SMALL, FLUSH ✕ BUTTON MATCHING TEXT HEIGHT */
    div.rec-card-container div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stButton"] {
        opacity: 0;
        transition: opacity 0.2s ease-in-out;
        margin: 0 !important;
        padding: 0 !important;
        height: 1.25rem !important;
        min-height: 1.25rem !important;
    }
    div.rec-card-container div[data-testid="stVerticalBlockBorderWrapper"]:hover div[data-testid="stButton"] {
        opacity: 1 !important;
    }
    div.rec-card-container div[data-testid="stButton"] button {
        float: right !important;
        padding: 0px !important;
        min-height: 1.25rem !important;
        height: 1.25rem !important;
        width: 1.25rem !important;
        font-size: 0.65rem !important;
        line-height: 1.25rem !important;
        border: 1px solid rgba(239, 68, 68, 0.4) !important;
        color: #ef4444 !important;
        background-color: rgba(239, 68, 68, 0.08) !important;
        margin: 0 !important;
        border-radius: 4px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div.rec-card-container div[data-testid="stButton"] button p {
        font-size: 0.65rem !important;
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    div.rec-card-container div[data-testid="stButton"] button:hover {
        background-color: rgba(239, 68, 68, 0.25) !important;
        border-color: #ef4444 !important;
    }

    .rec-item-row {
        display: flex;
        align-items: center;
        gap: 7px;
        flex-wrap: wrap;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

def clean_abbr(team_name, espn_abbr):
    if team_name in OFFICIAL_ABBR_MAP:
        return OFFICIAL_ABBR_MAP[team_name]
    if espn_abbr and espn_abbr.strip():
        clean = espn_abbr.strip().upper()
        if len(clean) <= 5:
            return clean
    words = re.findall(r"[A-Z0-9]", team_name)
    return "".join(words[:4]) if words else "TEAM"

def format_espn_kickoff(date_str, fallback_status):
    if not date_str:
        return fallback_status
    try:
        dt = datetime.strptime(date_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M%z")
        dt_et = dt - timedelta(hours=4)
        return dt_et.strftime("%a %m/%d - %I:%M %p ET")
    except Exception:
        return fallback_status

# Session Initializations
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "selected_bet_id" not in st.session_state:
    st.session_state.selected_bet_id = None
if "combo_active_legs" not in st.session_state:
    st.session_state.combo_active_legs = []
if "ai_recommended_combo" not in st.session_state:
    st.session_state.ai_recommended_combo = None
if "active_nav_page" not in st.session_state:
    st.session_state.active_nav_page = "2-12 Leg Combo Builder"

# Access Gatekeeper
if not st.session_state.authenticated:
    st.title("🔮 Flurkstradamus")
    st.caption("Private Edge & Consensus Terminal")
    with st.form("pin_login"):
        pin_entry = st.text_input("Group Passcode", type="password")
        login_btn = st.form_submit_button("Enter Terminal", use_container_width=True)
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

# ESPN Multi-League Ingestion
@st.cache_data(ttl=25)
def get_extended_games(league_code="nfl"):
    all_games = []
    seen_ids = set()
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

                    kickoff_formatted = format_espn_kickoff(event.get("date", ""), status_desc)
                    home_team_obj = home.get("team", {})
                    away_team_obj = away.get("team", {})
                    
                    home_name = home_team_obj.get("displayName", "Home")
                    away_name = away_team_obj.get("displayName", "Away")

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
                        checkpoint = "Halftime" if "half" in status_desc.lower() else (f"{period}st Quarter" if period == 1 else f"{period}th Quarter")

                    all_games.append({
                        "id": ev_id,
                        "league": l_label,
                        "name": event["name"],
                        "kickoff": kickoff_formatted,
                        "home_team": home_name,
                        "home_short": clean_abbr(home_name, home_team_obj.get("abbreviation")),
                        "home_logo": home_team_obj.get("logo", DEFAULT_LOGO),
                        "home_record": home.get("records", [{}])[0].get("summary", "0-0") if home.get("records") else "0-0",
                        "away_team": away_name,
                        "away_short": clean_abbr(away_name, away_team_obj.get("abbreviation")),
                        "away_logo": away_team_obj.get("logo", DEFAULT_LOGO),
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

    if len([g for g in all_games if not g["completed"]]) < 3:
        backup_slate = [
            {"id": "up_1", "league": "NFL", "name": "Bills @ Dolphins", "kickoff": "Thu 10/29 - 8:15 PM ET", "home_team": "Miami Dolphins", "home_short": "MIA", "home_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png", "home_record": "7-2", "away_team": "Buffalo Bills", "away_short": "BUF", "away_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png", "away_record": "6-3", "home_score": 0, "away_score": 0, "status": "Thu 8:15 PM ET", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 48.5, "market_spread": 2.5},
            {"id": "up_2", "league": "NCAA", "name": "Georgia @ Alabama", "kickoff": "Sat 10/31 - 3:30 PM ET", "home_team": "Alabama Crimson Tide", "home_short": "ALA", "home_logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/333.png", "home_record": "8-1", "away_team": "Georgia Bulldogs", "away_short": "UGA", "away_logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/61.png", "away_record": "8-1", "home_score": 0, "away_score": 0, "status": "Sat 3:30 PM ET", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 52.0, "market_spread": -3.0},
            {"id": "up_3", "league": "NCAA", "name": "Ohio State @ Penn State", "kickoff": "Sat 10/31 - 7:30 PM ET", "home_team": "Penn State Nittany Lions", "home_short": "PSU", "home_logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/213.png", "home_record": "7-1", "away_team": "Ohio State Buckeyes", "away_short": "OSU", "away_logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/194.png", "away_record": "8-0", "home_score": 0, "away_score": 0, "status": "Sat 7:30 PM ET", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 46.5, "market_spread": 3.5},
            {"id": "up_4", "league": "NFL", "name": "Chiefs @ Broncos", "kickoff": "Sun 11/01 - 4:25 PM ET", "home_team": "Denver Broncos", "home_short": "DEN", "home_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png", "home_record": "5-4", "away_team": "Kansas City Chiefs", "away_short": "KC", "away_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png", "away_record": "8-1", "home_score": 0, "away_score": 0, "status": "Sun 4:25 PM ET", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 45.0, "market_spread": 7.0},
            {"id": "up_5", "league": "NFL", "name": "49ers @ Seahawks", "kickoff": "Sun 11/01 - 8:20 PM ET", "home_team": "Seattle Seahawks", "home_short": "SEA", "home_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png", "home_record": "6-3", "away_team": "San Francisco 49ers", "away_short": "SF", "away_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png", "away_record": "6-3", "home_score": 0, "away_score": 0, "status": "Sun 8:20 PM ET", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 47.0, "market_spread": -1.5},
            {"id": "up_6", "league": "NFL", "name": "Ravens @ Steelers", "kickoff": "Sun 11/01 - 1:00 PM ET", "home_team": "Pittsburgh Steelers", "home_short": "PIT", "home_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png", "home_record": "6-2", "away_team": "Baltimore Ravens", "away_short": "BAL", "away_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png", "away_record": "7-2", "home_score": 0, "away_score": 0, "status": "Sun 1:00 PM ET", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 43.5, "market_spread": 2.5},
            {"id": "up_7", "league": "NFL", "name": "Lions @ Packers", "kickoff": "Sun 11/01 - 4:25 PM ET", "home_team": "Green Bay Packers", "home_short": "GB", "home_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png", "home_record": "6-2", "away_team": "Detroit Lions", "away_short": "DET", "away_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png", "away_record": "7-1", "home_score": 0, "away_score": 0, "status": "Sun 4:25 PM ET", "checkpoint": "Pre-Game", "completed": False, "period": 1, "displayClock": "Pre", "market_ou": 53.0, "market_spread": -1.0}
        ]
        for b_game in backup_slate:
            if b_game["id"] not in seen_ids:
                all_games.append(b_game)
                seen_ids.add(b_game["id"])

    return all_games

# ==========================================
# SIDEBAR NAVIGATION (LEFT-ALIGNED, LOW-MARGIN BUTTONS)
# ==========================================
st.sidebar.markdown("## 🔮 Flurkstradamus")
st.sidebar.caption("The Live Football Edge Engine")

st.sidebar.markdown("<p style='font-size:0.75rem; font-weight:700; color:#94a3b8; margin-bottom:4px; letter-spacing:0.5px;'>NAVIGATION</p>", unsafe_allow_html=True)

nav_items = [
    ("⚡ Single Game Engine", "Single Game Engine"),
    ("🔗 2-12 Leg Combo Builder", "2-12 Leg Combo Builder"),
    ("🔥 Live Squad Feed", "🔥 Live Squad Feed"),
    ("💬 The Locker Room", "💬 The Locker Room"),
    ("📜 Locked Bets History", "Locked Bets History"),
    ("🏆 Squad Leaderboard", "🏆 Squad Leaderboard"),
    ("📖 Model Methodology & Math", "📖 Model Methodology & Math")
]

for label, page_key in nav_items:
    is_active = (st.session_state.active_nav_page == page_key)
    btn_type = "primary" if is_active else "secondary"
    if st.sidebar.button(label, key=f"nav_{page_key}", type=btn_type, use_container_width=True):
        st.session_state.active_nav_page = page_key
        st.rerun()

menu_choice = st.session_state.active_nav_page

st.sidebar.markdown("---")
current_user = st.sidebar.text_input("Bettor Handle", value="Flurk")
league = st.sidebar.radio("Primary League", ["NFL", "NCAA Football"])
league_param = "nfl" if league == "NFL" else "college-football"

st.sidebar.markdown("---")
st.sidebar.markdown("### ⏱️ Live Updates")
auto_refresh = st.sidebar.toggle("Auto-Refresh Live Scores", value=True)
refresh_interval = st.sidebar.slider("Interval (seconds)", min_value=10, max_value=60, value=15, step=5)
if st.sidebar.button("🔄 Manual Scoreboard Sync", use_container_width=True):
    st.cache_data.clear()
    b_data, c_data = load_storage()
    st.session_state.saved_bets = b_data
    st.session_state.chat_messages = c_data
    st.rerun()

# ==========================================
# MAIN APPLICATION INTERFACE
# ==========================================
games_data = get_extended_games(league_param)
auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages)

# DETAIL PAGE: IN-GAME BET WAR ROOM
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)

    if st.button("⬅️ Back to Main Dashboard", use_container_width=True):
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

    with st.container(border=True):
        col_s1, col_s2, col_s3 = st.columns([2, 1, 2])
        with col_s1:
            st.image(live_game_info["away_logo"], width=45)
            st.markdown(f"**{live_game_info['away_short']}**\n# **{curr_away}**")
        with col_s2:
            st.caption(f"{live_game_info.get('kickoff', live_game_info['status'])}")
            st.caption(f"Clock: `{live_game_info.get('displayClock', 'Live')}`")
        with col_s3:
            st.image(live_game_info["home_logo"], width=45)
            st.markdown(f"**{live_game_info['home_short']}**\n# **{curr_home}**")

    risk = selected_bet.get("risk_dollars", 10.0)
    payout = selected_bet.get("payout_dollars", 19.0)

    if bet_category == "Moneyline":
        h_prob = calculate_moneyline_prob(curr_home, curr_away, live_game_info["home_record"], live_game_info["away_record"], is_final=is_final)
        picked_home = selected_bet.get("picked_team") == live_game_info["home_team"]
        win_prob = h_prob if picked_home else (1.0 - h_prob)
        m1, m2 = st.columns(2)
        m1.metric("Selected Winner", selected_bet.get("picked_team", "N/A"))
        m2.metric("Live Win Prob", f"{win_prob * 100:.1f}%")

    elif bet_category == "Spread":
        diff = curr_home - curr_away
        is_home = selected_bet.get("picked_team") == live_game_info["home_team"]
        proj_diff = diff + 1.5 if is_home else -diff - 1.5
        win_prob = calculate_spread_prob(proj_diff, target_line, std_dev=4.5)
        m1, m2 = st.columns(2)
        m1.metric("Spread Pick", f"{selected_bet.get('picked_team')} {target_line:+}")
        m2.metric("Live Win Prob", f"{win_prob * 100:.1f}%")

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
        m1, m2 = st.columns(2)
        m1.metric("Live Total", f"{total_pts} pts")
        m2.metric("Safety Cushion", f"{cushion:+.1f} pts")

    with st.container(border=True):
        st.subheader("💰 Live Equity & Smart Cashout")
        cur_equity = payout * win_prob
        c_h1, c_h2, c_h3 = st.columns(3)
        c_h1.metric("Risk", f"${risk:.2f}")
        c_h2.metric("Payout", f"${payout:.2f}")
        c_h3.metric("Fair Value", f"${cur_equity:.2f}", delta=f"{cur_equity - risk:+.2f}")
    st.stop()

# PAGE: LIVE SQUAD FEED
if menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    st.caption("Real-time feed of all bets placed across the squad.")

    if not st.session_state.saved_bets:
        st.info("No bets have been locked in yet.")
    else:
        for b in st.session_state.saved_bets[:15]:
            with st.container(border=True):
                status_badge = "⏳ Active" if b["status"] == "Pending" else ("🏆 Won" if b["status"] == "Won" else "❌ Lost")
                st.markdown(f"**{b.get('user', 'Flurk')}** locked `{b.get('bet')}`")
                st.caption(f"{b.get('matchup')} | Risk: ${b.get('risk_dollars', 10.0):.2f} ➜ Win: ${b.get('payout_dollars', 19.0):.2f} ({status_badge})")
                share_text = f"🔮 {b.get('user')} locked in {b.get('bet')} on {b.get('matchup')}! Track it on Flurkstradamus: https://flurkstradamus.streamlit.app"
                st.text_input("Share Text", value=share_text, key=f"share_{b['id']}")

# PAGE: THE LOCKER ROOM
elif menu_choice == "💬 The Locker Room":
    st.subheader("💬 The Locker Room")
    st.caption("Squad banter & game commentary.")

    with st.form("send_msg_form", clear_on_submit=True):
        user_msg = st.text_input("Send a message", placeholder="Trash talk here...")
        send_btn = st.form_submit_button("Post Message", use_container_width=True)
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

    for m in st.session_state.chat_messages[:30]:
        with st.container(border=True):
            st.markdown(f"**{m.get('user')}** <span style='opacity:0.6;font-size:0.8rem;'>({m.get('time')})</span>", unsafe_allow_html=True)
            st.write(m.get('text'))

# PAGE 1: SINGLE GAME ENGINE
elif menu_choice == "Single Game Engine":
    st.subheader("⚡ Single Game Engine")

    if games_data:
        game_options = [f"[{g['league']}] {g['away_short']} @ {g['home_short']} ({g.get('kickoff', g['status'])})" for g in games_data]
        selected_idx = st.selectbox("Select Matchup", range(len(game_options)), format_func=lambda x: game_options[x])
        g = games_data[selected_idx]
        g_id = g.get("id", str(selected_idx))
        detected_stage = g["checkpoint"]
        espn_ou = g["market_ou"]
        espn_spread = g["market_spread"]
    else:
        st.warning("Manual Matchup Mode")
        g = {"id": "man", "league": "NFL", "home_team": "Home", "home_short": "HOME", "home_logo": DEFAULT_LOGO, "away_team": "Away", "away_short": "AWAY", "away_logo": DEFAULT_LOGO, "home_score": 14, "away_score": 10, "status": "Halftime", "kickoff": "Live", "home_record": "6-2", "away_record": "5-3", "checkpoint": "Halftime", "completed": False, "market_ou": 47.5, "market_spread": -3.5}
        g_id = "man"
        detected_stage = "Halftime"
        espn_ou = 47.5
        espn_spread = -3.5

    with st.container(border=True):
        b1, b2, b3 = st.columns([1, 4, 1])
        b1.image(g.get("away_logo", DEFAULT_LOGO), width=45)
        b2.markdown(f"### **{g['away_short']}** @ **{g['home_short']}**\n{g.get('kickoff', g['status'])}")
        b3.image(g.get("home_logo", DEFAULT_LOGO), width=45)

    all_stages = ["Pre-Game", "1st Quarter", "Halftime", "3rd Quarter", "4th Quarter / Late Game", "Final / Game Completed"]
    default_stage_idx = all_stages.index(detected_stage) if detected_stage in all_stages else 2
    bracket_stage = st.selectbox("Game Checkpoint / Period", options=all_stages, index=default_stage_idx)

    c1, c2 = st.columns(2)
    with c1:
        home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}")
        away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}")
        home_rec = st.text_input(f"{g['home_short']} Record", value=g.get("home_record", "0-0"), key=f"h_rec_{g_id}")
        away_rec = st.text_input(f"{g['away_short']} Record", value=g.get("away_record", "0-0"), key=f"a_rec_{g_id}")
        pregame_total = st.number_input("Pre-Game Baseline Total", value=espn_ou, step=0.5, key=f"pre_{g_id}")

    with c2:
        sc1, sc2 = st.columns(2)
        h_pts = sc1.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"], key=f"hp_{g_id}")
        a_pts = sc2.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"], key=f"ap_{g_id}")
        market_line = st.number_input("Market Total Offered", value=round(pregame_total) + 0.5, step=0.5, key=f"mkt_{g_id}")
        spread_line = st.number_input(f"{g['home_short']} Spread", value=espn_spread, step=0.5, key=f"spd_{g_id}")

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

    home_win_prob = calculate_moneyline_prob(h_pts + (final_proj / 2.0), a_pts + (final_proj / 2.0), home_rec, away_rec, is_final=is_completed)
    away_win_prob = 1.0 - home_win_prob
    proj_margin = (h_pts + (final_proj / 2.0)) - (a_pts + (final_proj / 2.0))
    home_cover_prob = calculate_spread_prob(proj_margin, spread_line, std_bracket)

    with st.container(border=True):
        m1, m2 = st.columns(2)
        m1.metric("Projected Total", f"{final_proj:.1f} pts")
        m2.metric(f"{g['home_short']} Win Exp.", f"{home_win_prob * 100:.1f}%")

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
            picked_t = f1.selectbox("Team to Cover", [home_team, away_team], format_func=lambda x: f"{g['home_short']} ({home_team})" if x == home_team else f"{g['away_short']} ({away_team})", key=f"spd_pick_{g_id}")
            spd_val = spread_line if picked_t == home_team else -spread_line
            strike = f2.number_input("Spread Line", value=float(spd_val), step=0.5, key=f"spd_val_{g_id}")
            side = "Spread"
        else:
            side = "Moneyline"
            strike = None
            picked_t = st.selectbox("Winning Team", [home_team, away_team], format_func=lambda x: f"{g['home_short']} ({home_team})" if x == home_team else f"{g['away_short']} ({away_team})", key=f"ml_pick_{g_id}")

        p1, p2 = st.columns(2)
        risk_amt = p1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        payout_amt = p2.number_input("Payout ($)", min_value=1.0, value=19.0, step=5.0)
        ticket_notes = st.text_input("Notes", "Model play")

        lock_submit = st.form_submit_button("Lock In Bet", use_container_width=True)
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
                "matchup": f"{g['away_short']} @ {g['home_short']}",
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

# PAGE 2: 2 TO 12 LEG COMBO BUILDER
elif menu_choice == "2-12 Leg Combo Builder":
    st.subheader("🔗 Multi-Leg Combo Builder (Up to 12 Legs)")
    game_choices = [f"[{g['league']}] {g['away_short']} @ {g['home_short']} ({g.get('kickoff', g['status'])})" for g in games_data]

    if not st.session_state.combo_active_legs:
        init_count = min(3, len(games_data))
        st.session_state.combo_active_legs = []
        for j in range(init_count):
            g_item = games_data[j]
            st.session_state.combo_active_legs.append({
                "matchup_idx": j,
                "type": "Game Total",
                "side": "Under",
                "line": float(g_item.get("market_ou", 47.5)),
                "picked_team": g_item["home_team"]
            })

    # AI Strategy Scanner Accordion
    with st.expander("🤖 Flurkstradamus AI Combo Recommender & Strategy Scanner", expanded=True):
        st.markdown("#### Automated Strategy Generator")
        col_strat1, col_strat2 = st.columns(2)
        strategy_mode = col_strat1.selectbox(
            "Strategy Objective",
            [
                "🎯 Maximum Win Probability (Safest Floor)",
                "🔥 High Expected Value (+EV Total Edge)",
                "🏆 Straight-Up Moneyline Dominance",
                "🛡️ Defensive Under Lock (Pace Slump)"
            ]
        )

        active_candidate_games = [g for g in games_data if not g.get("completed", False)]
        max_possible_legs = min(12, max(2, len(active_candidate_games)))

        suggest_legs_count = col_strat2.number_input(
            "Target Legs (Up to 12)",
            min_value=2,
            max_value=max_possible_legs,
            value=min(max(len(st.session_state.combo_active_legs), 3), max_possible_legs)
        )
        generate_clicked = st.button("⚡ Scan & Recommend Across Slates", use_container_width=True)

        if generate_clicked and games_data:
            candidate_legs = []
            for g_c in active_candidate_games:
                c_h, c_a = g_c["home_team"], g_c["away_team"]
                c_h_abbr, c_a_abbr = g_c["home_short"], g_c["away_short"]
                c_kickoff = g_c.get("kickoff", g_c["status"])
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
                        "leg_id": f"tot_{g_c['id']}_under_{cushion_line}",
                        "matchup_idx": games_data.index(g_c),
                        "type": "Game Total",
                        "side": "Under",
                        "line": cushion_line,
                        "picked_team": c_h,
                        "prob": p,
                        "desc": f"Under {cushion_line}",
                        "detail": f"Proj: {proj_tot:.1f} pts",
                        "score_metric": p
                    })
                    ml_fav = c_h if h_prob >= 0.5 else c_a
                    fav_abbr = c_h_abbr if h_prob >= 0.5 else c_a_abbr
                    ml_p = max(h_prob, 1.0 - h_prob)
                    if ml_p >= 0.55:
                        candidate_legs.append({
                            "leg_id": f"ml_{g_c['id']}_{ml_fav}",
                            "matchup_idx": games_data.index(g_c),
                            "type": "Straight Up Winner",
                            "side": "Under",
                            "line": cushion_line,
                            "picked_team": ml_fav,
                            "prob": ml_p,
                            "desc": f"{fav_abbr} ML",
                            "detail": f"{ml_p*100:.1f}%",
                            "score_metric": ml_p
                        })

                elif "High Expected Value" in strategy_mode:
                    edge = abs(proj_tot - c_ou)
                    is_u = proj_tot < c_ou
                    tgt_line = c_ou
                    p = calculate_win_prob(tgt_line, proj_tot, sigma, is_under=is_u)
                    candidate_legs.append({
                        "leg_id": f"ev_{g_c['id']}_{'u' if is_u else 'o'}_{tgt_line}",
                        "matchup_idx": games_data.index(g_c),
                        "type": "Game Total",
                        "side": "Under" if is_u else "Over",
                        "line": tgt_line,
                        "picked_team": c_h,
                        "prob": p,
                        "desc": f"{'Under' if is_u else 'Over'} {tgt_line}",
                        "detail": f"Edge: {edge:.1f} pts",
                        "score_metric": edge * p
                    })

                elif "Straight-Up Moneyline" in strategy_mode:
                    ml_fav = c_h if h_prob >= 0.5 else c_a
                    fav_abbr = c_h_abbr if h_prob >= 0.5 else c_a_abbr
                    ml_p = max(h_prob, 1.0 - h_prob)
                    candidate_legs.append({
                        "leg_id": f"ml_{g_c['id']}_{ml_fav}",
                        "matchup_idx": games_data.index(g_c),
                        "type": "Straight Up Winner",
                        "side": "Under",
                        "line": c_ou,
                        "picked_team": ml_fav,
                        "prob": ml_p,
                        "desc": f"{fav_abbr} ML",
                        "detail": f"{ml_p*100:.1f}%",
                        "score_metric": ml_p
                    })

                else:
                    cushion_line = round(proj_tot + 4.5) + 0.5
                    p = calculate_win_prob(cushion_line, proj_tot, sigma, is_under=True)
                    candidate_legs.append({
                        "leg_id": f"def_{g_c['id']}_under_{cushion_line}",
                        "matchup_idx": games_data.index(g_c),
                        "type": "Game Total",
                        "side": "Under",
                        "line": cushion_line,
                        "picked_team": c_h,
                        "prob": p,
                        "desc": f"Under {cushion_line}",
                        "detail": f"Proj: {proj_tot:.1f} pts",
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

            st.session_state.ai_recommended_combo = selected_ai_legs

        # INTEGRATED ULTRA-COMPACT CARDS (CLEAN ROW, EQUALIZED PADDING)
        if st.session_state.ai_recommended_combo:
            num_legs_rec = len(st.session_state.ai_recommended_combo)
            comp_p = 1.0
            for l_item in st.session_state.ai_recommended_combo:
                comp_p *= l_item["prob"]

            st.markdown(f"#### 🎯 Recommended Ticket ({num_legs_rec} Legs):")

            # Dedicated container class for zero-gap targeting
            st.markdown('<div class="rec-card-container">', unsafe_allow_html=True)
            for idx_ai, l_ai in enumerate(list(st.session_state.ai_recommended_combo)):
                g_match = games_data[l_ai["matchup_idx"]]
                leg_key = l_ai.get("leg_id", f"leg_{idx_ai}_{l_ai['matchup_idx']}")
                detail_str = l_ai.get("detail", "")

                with st.container(border=True):
                    c_left, c_mid, c_btn = st.columns([5.6, 4.0, 0.4], vertical_alignment="center")
                    
                    with c_left:
                        st.markdown(f"""
                        <div class="rec-item-row">
                            <span style="background-color: #22c55e; color: #000; font-weight: 800; font-size: 0.70rem; padding: 1px 6px; border-radius: 4px;">
                                LEG {idx_ai+1}
                            </span>
                            <img src="{g_match['away_logo']}" width="18" height="18" style="border-radius: 50%;">
                            <strong>{g_match['away_short']}</strong>
                            <span style="opacity: 0.4;">@</span>
                            <img src="{g_match['home_logo']}" width="18" height="18" style="border-radius: 50%;">
                            <strong>{g_match['home_short']}</strong>
                            <span style="opacity: 0.55; font-size: 0.75rem;">({g_match.get('kickoff', g_match['status'])})</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with c_mid:
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; justify-content: flex-end; gap: 6px; flex-wrap: wrap; margin: 0; padding: 0;">
                            <strong style="color: #4ade80; font-size: 0.88rem;">{l_ai['desc']}</strong>
                            <span style="opacity: 0.6; font-size: 0.75rem;">({detail_str})</span>
                            <span style="background-color: rgba(255, 255, 255, 0.08); padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">
                                {l_ai['prob']*100:.1f}%
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with c_btn:
                        if st.button("✕", key=f"btn_remove_{leg_key}", help=f"Remove Leg {idx_ai+1}"):
                            st.session_state.ai_recommended_combo = [item for item in st.session_state.ai_recommended_combo if item.get("leg_id") != l_ai.get("leg_id")]
                            st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

            m_rec1, m_rec2 = st.columns([2, 1], vertical_alignment="center")
            m_rec1.metric("Compound Recommended Win Expectancy", f"{comp_p * 100:.1f}%", delta=f"{len(st.session_state.ai_recommended_combo)} Legs Total")

            if m_rec2.button("📥 Apply Recommended Picks into Combo Builder", use_container_width=True):
                st.session_state.combo_active_legs = [
                    {
                        "matchup_idx": l_item["matchup_idx"],
                        "type": l_item["type"],
                        "side": l_item.get("side", "Under"),
                        "line": float(l_item.get("line", 47.5)),
                        "picked_team": l_item.get("picked_team", games_data[l_item["matchup_idx"]]["home_team"])
                    }
                    for l_item in st.session_state.ai_recommended_combo
                ]
                st.rerun()

    # SLIP BUILDER CONTROLS
    ctrl_c1, ctrl_c2 = st.columns([3, 1], vertical_alignment="center")
    with ctrl_c1:
        st.markdown(f"#### Active Slip ({len(st.session_state.combo_active_legs)} Legs)")
    with ctrl_c2:
        if st.button("➕ Add Leg", use_container_width=True, disabled=(len(st.session_state.combo_active_legs) >= 12)):
            next_idx = min(len(st.session_state.combo_active_legs), len(games_data) - 1)
            g_next = games_data[next_idx]
            st.session_state.combo_active_legs.append({
                "matchup_idx": next_idx,
                "type": "Game Total",
                "side": "Under",
                "line": float(g_next.get("market_ou", 47.5)),
                "picked_team": g_next["home_team"]
            })
            st.rerun()

    combo_legs = []
    parsed_legs = []
    compound_prob = 1.0

    # RENDER ACTIVE LEGS WITH OFFICIAL TEAM LOGOS IN THE FORM
    for i, leg_data in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            sel_matchup = st.selectbox(
                f"Leg {i+1} Matchup",
                range(len(game_choices)),
                index=min(leg_data["matchup_idx"], len(game_choices) - 1),
                format_func=lambda x: game_choices[x],
                key=f"m_sel_{i}"
            )
            leg_data["matchup_idx"] = sel_matchup

            leg_g = games_data[leg_data["matchup_idx"]]
            d_h, d_a = leg_g["home_team"], leg_g["away_team"]
            d_h_abbr, d_a_abbr = leg_g["home_short"], leg_g["away_short"]
            d_kickoff = leg_g.get("kickoff", leg_g["status"])
            d_h_pts, d_a_pts = leg_g["home_score"], leg_g["away_score"]
            d_h_rec, d_a_rec = leg_g.get("home_record", "0-0"), leg_g.get("away_record", "0-0")
            leg_completed = leg_g["completed"]

            # Visual Matchup Header with Official Logos in the Form
            st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; background-color: rgba(255, 255, 255, 0.04); border-radius: 6px; padding: 6px 10px; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <img src="{leg_g.get('away_logo', DEFAULT_LOGO)}" width="28" height="28" style="border-radius: 50%;">
                    <div>
                        <strong style="font-size: 0.95rem;">{d_a_abbr}</strong>
                        <span style="opacity: 0.6; font-size: 0.75rem; margin-left: 2px;">({d_a_rec})</span>
                    </div>
                    <span style="opacity: 0.4; margin: 0 2px;">@</span>
                    <img src="{leg_g.get('home_logo', DEFAULT_LOGO)}" width="28" height="28" style="border-radius: 50%;">
                    <div>
                        <strong style="font-size: 0.95rem;">{d_h_abbr}</strong>
                        <span style="opacity: 0.6; font-size: 0.75rem; margin-left: 2px;">({d_h_rec})</span>
                    </div>
                </div>
                <div style="opacity: 0.75; font-size: 0.8rem; font-weight: 600;">
                    🗓️ {d_kickoff}
                </div>
            </div>
            """, unsafe_allow_html=True)

            wager_cat = st.radio(
                f"Wager Type (Leg {i+1})",
                ["Game Total", "Straight Up Winner"],
                horizontal=True,
                index=0 if leg_data["type"] == "Game Total" else 1,
                key=f"wtype_{i}"
            )
            leg_data["type"] = wager_cat

            if wager_cat == "Game Total":
                col_b, col_c = st.columns(2)
                side = col_b.selectbox("Side", ["Under", "Over"], index=0 if leg_data.get("side", "Under") == "Under" else 1, key=f"lside_{i}")
                strike = col_c.number_input("Line (pts)", value=float(leg_data.get("line", leg_g.get("market_ou", 44.5))), step=0.5, key=f"lstrike_{i}")
                leg_data["side"] = side
                leg_data["line"] = strike

                leg_prob = calculate_win_prob(strike, 42.0, 7.0, is_under=(side == "Under"))
                leg_desc = f"{d_a_abbr} @ {d_h_abbr}: {side} {strike}"
                parsed_legs.append({
                    "matchup": f"{d_a_abbr} @ {d_h_abbr}",
                    "type": "Total",
                    "side": side,
                    "line": strike,
                    "prob": leg_prob
                })
            else:
                col_b, col_c = st.columns(2)
                teams_opt = [d_h, d_a]
                prev_pick = leg_data.get("picked_team", d_h)
                pick_idx = teams_opt.index(prev_pick) if prev_pick in teams_opt else 0

                winner = col_b.selectbox(
                    "Pick Winner",
                    teams_opt,
                    index=pick_idx,
                    format_func=lambda x: f"{d_h_abbr} ({d_h})" if x == d_h else f"{d_a_abbr} ({d_a})",
                    key=f"lwinner_{i}"
                )
                leg_data["picked_team"] = winner

                win_abbr = d_h_abbr if winner == d_h else d_a_abbr
                h_prob = calculate_moneyline_prob(d_h_pts + 15, d_a_pts + 15, d_h_rec, d_a_rec, is_final=leg_completed)
                leg_prob = h_prob if winner == d_h else (1.0 - h_prob)
                leg_desc = f"{d_a_abbr} @ {d_h_abbr}: {win_abbr} ML"
                col_c.metric("Model Win %", f"{leg_prob * 100:.1f}%")
                parsed_legs.append({
                    "matchup": f"{d_a_abbr} @ {d_h_abbr}",
                    "type": "Moneyline",
                    "picked_team": winner,
                    "prob": leg_prob
                })

            compound_prob *= leg_prob
            combo_legs.append({"desc": leg_desc, "prob": leg_prob})

    active_leg_count = len(st.session_state.combo_active_legs)
    with st.container(border=True):
        st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        c_r1, c_r2 = st.columns(2)
        c_risk = c_r1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        est_payout = round(c_risk / max(compound_prob, 0.005), 2)
        c_payout = c_r2.number_input("Payout ($)", min_value=1.0, value=float(min(est_payout, 50000.0)), step=25.0)
        c_notes = st.text_input("Notes", f"{active_leg_count}-Leg Parlay")

        save_c_btn = st.form_submit_button(f"Lock In {active_leg_count}-Leg Ticket", use_container_width=True)
        if save_c_btn:
            legs_str = " | ".join([cl["desc"] for cl in combo_legs])
            combo_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip() if current_user.strip() else "Flurk",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": f"{active_leg_count}-Leg Combo",
                "bet_category": "Combo",
                "matchup": legs_str,
                "bet": f"{active_leg_count} Legs ({compound_prob * 100:.1f}% Prob)",
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
            st.success(f"{active_leg_count}-Leg combo ticket locked in!")

# PAGE 3: LOCKED BETS & HISTORY
elif menu_choice == "Locked Bets History":
    st.subheader(f"📜 {current_user}'s Locked Bets")
    st.caption("Your personalized active slips, scores, and settled tickets.")

    curr_user_clean = current_user.strip().lower() if current_user.strip() else "flurk"
    my_tickets = [b for b in st.session_state.saved_bets if b.get("user", "Flurk").strip().lower() == curr_user_clean]

    h_top1, h_top2 = st.columns([3, 1])
    with h_top1:
        st.write(f"Showing **{len(my_tickets)}** ticket(s) placed by **{current_user}**.")
    with h_top2:
        if st.button("⚡ Grade Finals", use_container_width=True):
            if auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages):
                st.success("Updated tickets!")
                st.rerun()

    if not my_tickets:
        st.info(f"You don't have any locked bets yet under handle '{current_user}'. Lock in a pick in the Single Game or Combo Engine!")
    else:
        for b in my_tickets:
            real_idx = st.session_state.saved_bets.index(b)
            status_val = b.get("status", "Pending")

            if status_val == "Won":
                card_style = "border: 1.5px solid #22c55e; background-color: rgba(34, 197, 94, 0.05);"
                badge_html = "<span style='background-color:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>🏆 WON</span>"
            elif status_val == "Lost":
                card_style = "border: 1.5px solid #ef4444; background-color: rgba(239, 68, 68, 0.05);"
                badge_html = "<span style='background-color:#ef4444;color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>❌ LOST</span>"
            else:
                card_style = "border: 1.5px solid #eab308; background-color: rgba(234, 179, 8, 0.05);"
                badge_html = "<span style='background-color:#eab308;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>⏳ IN PLAY</span>"

            live_m = find_game_for_bet(b, games_data)
            away_logo = live_m.get("away_logo", DEFAULT_LOGO) if live_m else DEFAULT_LOGO
            home_logo = live_m.get("home_logo", DEFAULT_LOGO) if live_m else DEFAULT_LOGO
            
            if live_m:
                a_short = live_m.get("away_short", "AWAY")
                h_short = live_m.get("home_short", "HOME")
                a_score = live_m.get("away_score", 0)
                h_score = live_m.get("home_score", 0)
                tot_pts = a_score + h_score
                is_fin = live_m.get("completed", False) or "final" in live_m["status"].lower()
                status_prefix = "Final Score" if is_fin else "Live Score"
                score_str = f"**{status_prefix}:** {a_score} vs {h_score} ({tot_pts} total)"
                game_title = f"{a_short} vs {h_short}"
            else:
                game_title = b.get("matchup", "Football Matchup")
                score_str = "Score: *Pre-Game / Scheduled*"

            st.markdown(f"""
            <div style="{card_style} border-radius: 12px; padding: 12px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <img src="{away_logo}" width="26" height="26" style="border-radius: 50%;">
                        <strong style="font-size: 1.05rem;">{game_title}</strong>
                        <img src="{home_logo}" width="26" height="26" style="border-radius: 50%;">
                    </div>
                    <div>{badge_html}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.container():
                c_row1, c_row2, c_row3, c_row4 = st.columns([3, 3, 2, 1])
                with c_row1:
                    st.write(score_str)
                    st.caption(f"🗓️ Logged: `{b.get('date', 'N/A')}`")
                with c_row2:
                    st.write(f"**Pick:** `{b.get('bet')}`")
                    st.caption(f"Risk: **${b.get('risk_dollars', 10.0):.2f}** ➜ Return: **${b.get('payout_dollars', 19.0):.2f}**")
                with c_row3:
                    if b.get("bet_category") == "Combo" and b.get("parsed_legs"):
                        leg_statuses = []
                        for leg in b["parsed_legs"]:
                            m_g = find_game_for_bet({"matchup": leg["matchup"]}, games_data)
                            if m_g and m_g["completed"]:
                                t_p = m_g["away_score"] + m_g["home_score"]
                                won = (t_p < leg["line"]) if leg["type"] == "Total" and leg["side"] == "Under" else (t_p > leg["line"] if leg["type"] == "Total" else leg["picked_team"] == (m_g["home_team"] if m_g["home_score"] > m_g["away_score"] else m_g["away_team"]))
                                leg_statuses.append(f"✅ {m_g['away_short']}" if won else f"❌ {m_g['away_short']}")
                            elif m_g:
                                leg_statuses.append(f"⏳ {m_g['away_short']}")
                        st.write(" • ".join(leg_statuses))
                    else:
                        st.caption(f"Type: {b.get('type', 'Single')}")
                with c_row4:
                    if st.button("🗑️", key=f"del_slip_{b['id']}", help="Delete this ticket", use_container_width=True):
                        st.session_state.saved_bets.pop(real_idx)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages)
                        st.rerun()

            st.markdown("<hr style='margin: 8px 0 16px 0; opacity: 0.15;'>", unsafe_allow_html=True)

# PAGE 4: SQUAD LEADERBOARD
elif menu_choice == "🏆 Squad Leaderboard":
    st.subheader("🏆 Squad Leaderboard")
    st.caption("Consensus standings and betting performance.")

    user_stats = {}
    for b in st.session_state.saved_bets:
        u_raw = b.get("user", "Flurk")
        u_clean = u_raw.strip() if u_raw.strip() else "Flurk"
        u_key = u_clean.lower()
        if u_key not in user_stats:
            user_stats[u_key] = {
                "display_name": u_clean,
                "Wins": 0,
                "Losses": 0,
                "Pending": 0,
                "Total_Risk": 0.0,
                "Net_Profit": 0.0
            }

        risk = float(b.get("risk_dollars", 10.0))
        payout = float(b.get("payout_dollars", 19.0))
        stat = b.get("status", "Pending")

        if stat == "Won":
            user_stats[u_key]["Wins"] += 1
            user_stats[u_key]["Total_Risk"] += risk
            user_stats[u_key]["Net_Profit"] += (payout - risk)
        elif stat == "Lost":
            user_stats[u_key]["Losses"] += 1
            user_stats[u_key]["Total_Risk"] += risk
            user_stats[u_key]["Net_Profit"] -= risk
        else:
            user_stats[u_key]["Pending"] += 1

    board = []
    for u_k, s in user_stats.items():
        decided = s["Wins"] + s["Losses"]
        win_rate = (s["Wins"] / decided * 100) if decided > 0 else 0.0
        roi = (s["Net_Profit"] / s["Total_Risk"] * 100) if s["Total_Risk"] > 0 else 0.0
        badge = "🎯 Sniper" if win_rate >= 65 and decided >= 3 else ("🔥 On Fire" if s["Wins"] >= 3 and s["Losses"] == 0 else ("⚡ Contender" if decided > 0 else "🌱 Rookie"))

        board.append({
            "name": s["display_name"],
            "badge": badge,
            "wins": s["Wins"],
            "losses": s["Losses"],
            "pending": s["Pending"],
            "win_rate": win_rate,
            "roi": roi,
            "decided": decided,
            "net_profit": s["Net_Profit"]
        })

    board.sort(key=lambda x: x["net_profit"], reverse=True)

    if not board:
        st.info("No bets recorded yet to rank.")
    else:
        top_c1, top_c2 = st.columns(2)
        top_c1.metric("Total Bettors", f"{len(board)}")
        tot_profit = sum(x['net_profit'] for x in board)
        top_c2.metric("Squad Net P&L", f"${tot_profit:+.2f}", delta=f"{'+' if tot_profit>=0 else ''}{tot_profit:.2f}")

        for rank_idx, bettor in enumerate(board):
            medal = "🥇" if rank_idx == 0 else ("🥈" if rank_idx == 1 else ("🥉" if rank_idx == 2 else f"#{rank_idx+1}"))
            with st.container(border=True):
                r_c1, r_c2 = st.columns([3, 2])
                with r_c1:
                    st.markdown(f"### {medal} **{bettor['name']}**")
                    st.caption(f"{bettor['badge']} • {bettor['wins']}W - {bettor['losses']}L - {bettor['pending']}P")
                with r_c2:
                    p_color = "#4ade80" if bettor['net_profit'] >= 0 else "#f87171"
                    p_text = f"+${bettor['net_profit']:.2f}" if bettor['net_profit'] >= 0 else f"-${abs(bettor['net_profit']):.2f}"
                    st.markdown(f"<div style='text-align:right;'><span style='color:{p_color};font-size:1.4rem;font-weight:700;'>{p_text}</span></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align:right;opacity:0.6;font-size:0.85rem;'>ROI: {bettor['roi']:+.1f}%</div>", unsafe_allow_html=True)

                s1, s2, s3 = st.columns(3)
                s1.metric("Win Rate", f"{bettor['win_rate']:.1f}%")
                s2.metric("Decided", f"{bettor['decided']}")
                s3.metric("Pending", f"{bettor['pending']}")

# PAGE 5: MODEL METHODOLOGY & MATH BREAKDOWN
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Model Architecture & Math")
    st.caption("How edge, variance, and straight-up win rates are calculated.")

    with st.container(border=True):
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
            * **4th Quarter / Late Game:** Closes remaining scoring volume to actual game pace hazards ($\sigma = 1.8$).
            * **Final / Completed:** All remaining variance decays to zero ($\sigma \to 0$); probabilities resolve to 100% or 0%.
            """
        )

    with st.container(border=True):
        st.markdown("### 2. Normal CDF & Win Probability Calculation")
        st.write("Target line comparison uses the cumulative normal distribution function:")
        st.latex(r"Z = \frac{L - \mu}{\sigma}")
        st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")

    with st.container(border=True):
        st.markdown("### 3. Straight-Up Moneyline & Spread Engines")
        st.latex(r"\text{Spread}_{\text{eff}} = (\text{Home Proj} - \text{Away Proj}) + \left[(\text{Home Win \%} - \text{Away Win \%}) \times 7.0\right]")
        st.latex(r"P(\text{Home Win}) = \frac{1}{1 + e^{-\frac{\text{Spread}_{\text{eff}}}{6.5}}}")
