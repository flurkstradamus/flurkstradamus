import streamlit as st
import requests
import re
from datetime import datetime, timedelta

# Import modular engines
from config import GROUP_PASSCODE, DEFAULT_LOGO, OFFICIAL_ABBR_MAP
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob
from database import load_storage, save_all_storage, find_game_for_bet, auto_resolve_bets, hash_password

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

    /* REMOVE GAP BETWEEN SIDEBAR BUTTONS */
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

    /* BALANCED, HIGH-VISIBILITY RECOMMENDATION ROW */
    .rec-single-line-card {
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background-color: rgba(255, 255, 255, 0.02);
        padding: 8px 14px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: nowrap;
        white-space: nowrap;
        line-height: 1.3;
        transition: background-color 0.15s ease-in-out, border-color 0.15s ease-in-out;
    }
    .rec-single-line-card:hover {
        background-color: rgba(255, 255, 255, 0.04);
        border-color: rgba(34, 197, 94, 0.35);
    }
    .rec-left-wrap {
        display: flex;
        align-items: center;
        gap: 9px;
    }
    .rec-right-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* EDIT LINK BUTTON */
    .edit-link-btn div[data-testid="stButton"] button {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        min-height: unset !important;
        height: auto !important;
        color: #38bdf8 !important;
        font-size: 0.80rem !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        text-decoration: underline !important;
    }
    .edit-link-btn div[data-testid="stButton"] button:hover {
        color: #0284c7 !important;
    }

    .clean-subtext {
        font-size: 0.85rem !important;
        color: rgba(255, 255, 255, 0.75) !important;
        margin-top: 2px !important;
        display: block !important;
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
if "passcode_authenticated" not in st.session_state:
    st.session_state.passcode_authenticated = False
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "selected_bet_id" not in st.session_state:
    st.session_state.selected_bet_id = None
if "combo_active_legs" not in st.session_state:
    st.session_state.combo_active_legs = []
if "ai_recommended_combo" not in st.session_state:
    st.session_state.ai_recommended_combo = None
if "active_nav_page" not in st.session_state:
    st.session_state.active_nav_page = "Single Game Engine"
if "editing_ai_combo" not in st.session_state:
    st.session_state.editing_ai_combo = False
if "combo_version" not in st.session_state:
    st.session_state.combo_version = 0

# Single Game State Keys
if "single_selected_idx" not in st.session_state:
    st.session_state.single_selected_idx = 0
if "single_applied_pick" not in st.session_state:
    st.session_state.single_applied_pick = None
if "single_form_version" not in st.session_state:
    st.session_state.single_form_version = 0

# Load Database
b_data, c_data, u_data = load_storage()
if "saved_bets" not in st.session_state:
    st.session_state.saved_bets = b_data
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = c_data
if "user_accounts" not in st.session_state:
    st.session_state.user_accounts = u_data

# ==========================================
# STAGE 1: GROUP PASSCODE GATEKEEPER
# ==========================================
if not st.session_state.passcode_authenticated:
    st.title("🔮 Flurkstradamus")
    st.caption("Private Edge & Consensus Terminal")
    with st.container(border=True):
        st.markdown("### 🔑 Private Beta Access")
        st.write("Please enter the community invite passcode to proceed:")
        with st.form("pin_login"):
            pin_entry = st.text_input("Group Passcode", type="password", placeholder="Enter passcode...")
            login_btn = st.form_submit_button("Access Terminal", use_container_width=True)
            if login_btn:
                if pin_entry == GROUP_PASSCODE:
                    st.session_state.passcode_authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid group passcode.")
    st.stop()

# ==========================================
# STAGE 2: USER LOGIN & REGISTRATION
# ==========================================
if st.session_state.logged_in_user is None:
    st.title("🔮 Flurkstradamus")
    st.caption("Sign in or create your betting handle to save slips, track P&L, and join the leaderboard.")
    
    tab_login, tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])
    
    with tab_login:
        with st.form("user_login_form"):
            uname = st.text_input("Username", placeholder="e.g. jsmith").strip().lower()
            pword = st.text_input("Password", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Sign In to Flurkstradamus", use_container_width=True)
            
            if submit_login:
                user_record = st.session_state.user_accounts.get(uname)
                if user_record and user_record.get("password_hash") == hash_password(pword):
                    st.session_state.logged_in_user = user_record
                    st.success(f"Welcome back, {user_record.get('display_name', uname)}!")
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")
                    
    with tab_signup:
        with st.form("user_signup_form"):
            new_uname = st.text_input("Choose Username (Login ID)", placeholder="e.g. sharpshooter").strip().lower()
            new_dname = st.text_input("Display Name / Bettor Handle", placeholder="e.g. Sharp Shooter")
            new_pword = st.text_input("Choose Password", type="password", placeholder="••••••••")
            new_pword_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••")
            fav_team = st.text_input("Favorite Team (Optional)", placeholder="e.g. Philadelphia Eagles")
            submit_signup = st.form_submit_button("Create My Account", use_container_width=True)
            
            if submit_signup:
                if not new_uname or not new_pword or not new_dname:
                    st.error("Username, display name, and password are required.")
                elif len(new_uname) < 3:
                    st.error("Username must be at least 3 characters.")
                elif new_pword != new_pword_confirm:
                    st.error("Passwords do not match.")
                elif new_uname in st.session_state.user_accounts:
                    st.error("This username is already taken. Please pick another.")
                else:
                    new_user = {
                        "username": new_uname,
                        "display_name": new_dname.strip(),
                        "password_hash": hash_password(new_pword),
                        "is_admin": False,
                        "created_at": datetime.now().strftime("%Y-%m-%d"),
                        "favorite_team": fav_team.strip() if fav_team else "NFL"
                    }
                    st.session_state.user_accounts[new_uname] = new_user
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts)
                    st.session_state.logged_in_user = new_user
                    st.success("Account created successfully!")
                    st.rerun()
    st.stop()

# ACTIVE USER IDENTITY
current_user_profile = st.session_state.logged_in_user
current_user = current_user_profile.get("display_name", current_user_profile.get("username", "Flurk"))
is_user_admin = current_user_profile.get("is_admin", False)

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
# SIDEBAR NAVIGATION & USER PROFILE
# ==========================================
st.sidebar.markdown(f"## 🔮 Flurkstradamus")
st.sidebar.markdown(f"👤 **{current_user}** (`@{current_user_profile.get('username')}`)")
if current_user_profile.get("favorite_team"):
    st.sidebar.caption(f"🏈 {current_user_profile.get('favorite_team')}")

col_u1, col_u2 = st.sidebar.columns(2)
with col_u1:
    if st.button("🚪 Logout", key="logout_btn", use_container_width=True):
        st.session_state.logged_in_user = None
        st.rerun()

st.sidebar.markdown("---")

nav_items = [
    ("⚡ Single Game Engine", "Single Game Engine"),
    ("🔗 2-12 Leg Combo Builder", "2-12 Leg Combo Builder"),
    ("🔥 Live Squad Feed", "🔥 Live Squad Feed"),
    ("💬 The Locker Room", "💬 The Locker Room"),
    ("🏆 Squad Leaderboard", "🏆 Squad Leaderboard"),
    ("📜 Locked Bets History", "Locked Bets History"),
    ("💡 How It Works", "💡 How It Works"),
    ("📖 Model Methodology & Math", "📖 Model Methodology & Math")
]

# Admin Area Entry
if is_user_admin:
    nav_items.append(("🛡️ Admin User Control", "🛡️ Admin User Control"))

for label, page_key in nav_items:
    is_active = (st.session_state.active_nav_page == page_key)
    btn_type = "primary" if is_active else "secondary"
    if st.sidebar.button(label, key=f"nav_{page_key}", type=btn_type, use_container_width=True):
        st.session_state.active_nav_page = page_key
        st.rerun()

menu_choice = st.session_state.active_nav_page

st.sidebar.markdown("---")
league = st.sidebar.radio("Primary League", ["NFL", "NCAA Football"])
league_param = "nfl" if league == "NFL" else "college-football"

st.sidebar.markdown("---")
st.sidebar.markdown("### ⏱️ Live Updates")
auto_refresh = st.sidebar.toggle("Auto-Refresh Live Scores", value=True)
refresh_interval = st.sidebar.slider("Interval (seconds)", min_value=10, max_value=60, value=15, step=5)
if st.sidebar.button("🔄 Manual Scoreboard Sync", use_container_width=True):
    st.cache_data.clear()
    b_data, c_data, u_data = load_storage()
    st.session_state.saved_bets = b_data
    st.session_state.chat_messages = c_data
    st.session_state.user_accounts = u_data
    st.rerun()

# Grade pending bets
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

# PAGE: ADMIN USER CONTROL
if menu_choice == "🛡️ Admin User Control" and is_user_admin:
    st.subheader("🛡️ Admin Console & User Management")
    st.caption("Manage registered beta testers, toggle admin rights, and reset passwords.")
    
    users = st.session_state.user_accounts
    st.write(f"Total Registered Users: **{len(users)}**")
    
    for u_key, u_info in list(users.items()):
        with st.container(border=True):
            a_col1, a_col2, a_col3 = st.columns([3, 3, 2])
            with a_col1:
                st.markdown(f"**{u_info.get('display_name')}** (`@{u_key}`)")
                st.caption(f"Joined: {u_info.get('created_at', 'N/A')} | Fav Team: {u_info.get('favorite_team', 'None')}")
            with a_col2:
                is_adm = u_info.get("is_admin", False)
                status_txt = "👑 Administrator" if is_adm else "👤 Member"
                st.markdown(f"**Role:** `{status_txt}`")
            with a_col3:
                if u_key != "admin" and u_key != current_user_profile.get("username"):
                    if st.button("🗑️ Delete", key=f"del_u_{u_key}", use_container_width=True):
                        users.pop(u_key)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users)
                        st.rerun()

# PAGE: LIVE SQUAD FEED
elif menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    st.caption("Real-time feed of all bets placed across the squad.")

    if not st.session_state.saved_bets:
        st.info("No bets have been locked in yet.")
    else:
        for b in st.session_state.saved_bets[:25]:
            status_val = b.get("status", "Pending")
            live_m = find_game_for_bet(b, games_data)
            away_logo = live_m.get("away_logo", DEFAULT_LOGO) if live_m else DEFAULT_LOGO
            home_logo = live_m.get("home_logo", DEFAULT_LOGO) if live_m else DEFAULT_LOGO

            game_has_started = False
            if live_m:
                chk = live_m.get("checkpoint", "")
                stt = live_m.get("status", "").lower()
                game_has_started = ("pre" not in chk.lower()) and ("pm" not in stt and "am" not in stt)

            if status_val == "Won":
                card_style = "border: 1.5px solid #22c55e; background-color: rgba(34, 197, 94, 0.05);"
                badge_html = "<span style='background-color:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>🏆 WON</span>"
            elif status_val == "Lost":
                card_style = "border: 1.5px solid #ef4444; background-color: rgba(239, 68, 68, 0.05);"
                badge_html = "<span style='background-color:#ef4444;color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>❌ LOST</span>"
            else:
                if game_has_started:
                    card_style = "border: 1.5px solid #eab308; background-color: rgba(234, 179, 8, 0.05);"
                    badge_html = "<span style='background-color:#eab308;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>⚡ IN PLAY</span>"
                else:
                    card_style = "border: 1.5px solid rgba(255, 255, 255, 0.2); background-color: rgba(255, 255, 255, 0.03);"
                    badge_html = "<span style='background-color:rgba(255, 255, 255, 0.12);color:#94a3b8;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>⏳ PENDING</span>"

            if live_m:
                a_short = live_m.get("away_short", "AWAY")
                h_short = live_m.get("home_short", "HOME")
                a_score = live_m.get("away_score", 0)
                h_score = live_m.get("home_score", 0)
                tot_pts = a_score + h_score
                is_fin = live_m.get("completed", False) or "final" in live_m["status"].lower()
                status_prefix = "Final Score" if is_fin else ("Live Score" if game_has_started else "Scheduled Kickoff")
                if game_has_started or is_fin:
                    score_str = f"**{status_prefix}:** {a_score} vs {h_score} ({tot_pts} total)"
                else:
                    score_str = f"🗓️ {live_m.get('kickoff', live_m.get('status', 'Pre-Game'))}"
                game_title = f"{a_short} vs {h_short}"
            else:
                game_title = b.get("matchup", "Football Matchup")
                score_str = "Score: *Pre-Game / Scheduled*"

            bettor_tag = b.get('user', 'Flurk')
            st.markdown(f"""
            <div style="{card_style} border-radius: 12px; padding: 12px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <img src="{away_logo}" width="26" height="26" style="border-radius: 50%;">
                        <strong style="font-size: 1.05rem;">{game_title}</strong>
                        <img src="{home_logo}" width="26" height="26" style="border-radius: 50%;">
                        <span style="opacity: 0.6; font-size: 0.85rem; margin-left: 6px;">by <strong>{bettor_tag}</strong></span>
                    </div>
                    <div>{badge_html}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.container():
                c_f1, c_f2, c_f3 = st.columns([3, 4, 3])
                with c_f1:
                    st.write(score_str)
                    st.caption(f"🗓️ Logged: `{b.get('date', 'N/A')}`")
                with c_f2:
                    st.write(f"**Pick:** `{b.get('bet')}`")
                    r_val = float(b.get('risk_dollars', 10.0))
                    p_val = float(b.get('payout_dollars', 19.0))
                    roi_pct = ((p_val - r_val) / max(r_val, 0.01)) * 100
                    st.markdown(f"<span class='clean-subtext'>Risk: ${r_val:.2f} | Return: ${p_val:.2f} (+{roi_pct:.1f}%)</span>", unsafe_allow_html=True)
                with c_f3:
                    cat_label = b.get("bet_category", b.get("type", "Single"))
                    st.write(f"**Type:** `{cat_label}`")
                    share_text = f"🔮 {bettor_tag} locked in {b.get('bet')} on {b.get('matchup')}! Track it on Flurkstradamus: https://flurkstradamus.streamlit.app"
                    with st.expander("🔗 Share Pick"):
                        st.text_input("Copy Link", value=share_text, key=f"feed_share_{b['id']}")

            st.markdown("<hr style='margin: 6px 0 14px 0; opacity: 0.15;'>", unsafe_allow_html=True)

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
                "user": current_user.strip(),
                "time": datetime.now().strftime("%I:%M %p"),
                "text": user_msg.strip()
            }
            st.session_state.chat_messages.insert(0, new_msg)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts)
            st.rerun()

    for m in st.session_state.chat_messages[:30]:
        with st.container(border=True):
            st.markdown(f"**{m.get('user')}** <span style='opacity:0.6;font-size:0.8rem;'>({m.get('time')})</span>", unsafe_allow_html=True)
            st.write(m.get('text'))

# PAGE: SQUAD LEADERBOARD
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

# PAGE: LOCKED BETS HISTORY
elif menu_choice == "Locked Bets History":
    st.subheader(f"📜 {current_user}'s Locked Bets")
    st.caption("Your personalized active slips, scores, and settled tickets.")

    curr_user_clean = current_user.strip().lower()
    my_tickets = [b for b in st.session_state.saved_bets if b.get("user", "").strip().lower() == curr_user_clean]

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

            live_m = find_game_for_bet(b, games_data)
            away_logo = live_m.get("away_logo", DEFAULT_LOGO) if live_m else DEFAULT_LOGO
            home_logo = live_m.get("home_logo", DEFAULT_LOGO) if live_m else DEFAULT_LOGO
            
            game_has_started = False
            if live_m:
                chk = live_m.get("checkpoint", "")
                stt = live_m.get("status", "").lower()
                game_has_started = ("pre" not in chk.lower()) and ("pm" not in stt and "am" not in stt)

            if status_val == "Won":
                card_style = "border: 1.5px solid #22c55e; background-color: rgba(34, 197, 94, 0.05);"
                badge_html = "<span style='background-color:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>🏆 WON</span>"
            elif status_val == "Lost":
                card_style = "border: 1.5px solid #ef4444; background-color: rgba(239, 68, 68, 0.05);"
                badge_html = "<span style='background-color:#ef4444;color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>❌ LOST</span>"
            else:
                if game_has_started:
                    card_style = "border: 1.5px solid #eab308; background-color: rgba(234, 179, 8, 0.05);"
                    badge_html = "<span style='background-color:#eab308;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>⚡ IN PLAY</span>"
                else:
                    card_style = "border: 1.5px solid rgba(255, 255, 255, 0.2); background-color: rgba(255, 255, 255, 0.03);"
                    badge_html = "<span style='background-color:rgba(255, 255, 255, 0.12);color:#94a3b8;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>⏳ PENDING</span>"
            
            if live_m:
                a_short = live_m.get("away_short", "AWAY")
                h_short = live_m.get("home_short", "HOME")
                a_score = live_m.get("away_score", 0)
                h_score = live_m.get("home_score", 0)
                tot_pts = a_score + h_score
                is_fin = live_m.get("completed", False) or "final" in live_m["status"].lower()
                status_prefix = "Final Score" if is_fin else ("Live Score" if game_has_started else "Scheduled Kickoff")
                if game_has_started or is_fin:
                    score_str = f"**{status_prefix}:** {a_score} vs {h_score} ({tot_pts} total)"
                else:
                    score_str = f"🗓️ {live_m.get('kickoff', live_m.get('status', 'Pre-Game'))}"
                game_title = f"{a_short} vs {h_short}"
            else:
                game_title = b.get("matchup", "Football Matchup")
                score_str = "Score: *Pre-Game / Scheduled*"

            st.markdown(f"""
            <div style="{card_style} border-radius: 12px; padding: 12px; margin-bottom: 8px;">
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
                    r_val = float(b.get('risk_dollars', 10.0))
                    p_val = float(b.get('payout_dollars', 19.0))
                    roi_pct = ((p_val - r_val) / max(r_val, 0.01)) * 100
                    st.markdown(f"<span class='clean-subtext'>Risk: ${r_val:.2f} | Return: ${p_val:.2f} (+{roi_pct:.1f}%)</span>", unsafe_allow_html=True)
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
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts)
                        st.rerun()

            st.markdown("<hr style='margin: 8px 0 16px 0; opacity: 0.15;'>", unsafe_allow_html=True)

# PAGE: HOW IT WORKS
elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: The Flurkstradamus User Guide")
    st.caption("Mastering the Edge Engine, Combo Builder, and Squad Tracker.")

    with st.container(border=True):
        st.markdown("### ⚡ 1. Single Game Engine & AI Strategy Builder")
        st.write(
            "The **Single Game Engine** connects live to ESPN scoreboard endpoints to track "
            "every game from pregame opening through the final whistle."
        )
        st.markdown("""
        * **Live Line Drift Tracking:** Compares opening sportsbook lines against real-time scoring to compute live **Full Game Totals**, **2nd Half Totals**, and **Spread ATS Margins**.
        * **The Risk vs. Return Dial:** Adjust the slider to set your model objective:
          * **🛡️ Safe Floor:** Isolates insulated lines with 80%+ win probabilities.
          * **⚖️ Balanced Edge:** Finds the sweet spot (+EV) paying 1:1 or better with 60–70% win probabilities.
          * **🚀 High Profit:** Discovers high-multiplier lines (+140 to +250) and mispriced live underdogs.
        * **One-Click Loading:** Press **'📥 Load to Form'** on any Good, Better, or Best card to immediately sync the matchup, set the lines, and populate your slip below.
        """)

    with st.container(border=True):
        st.markdown("### 🔗 2. 2–12 Leg Combo Builder")
        st.write(
            "Designed for parlay architects. Build customized tickets or let the system analyze the entire slate for compound edge."
        )
        st.markdown("""
        * **Automated Strategy Generator:** Pick an objective (*Max Win Probability*, *High EV*, *Moneyline Dominance*, or *Defensive Under*) and set your target leg count.
        * **Interactive Leg Removal:** Click **Edit** beside the recommended ticket header to expose the radio selector drawer and drop any leg you don't like.
        * **Compound Probability Modeling:** As you add or remove picks, the engine compounds true win probabilities across every leg in real time.
        """)

    with st.container(border=True):
        st.markdown("### 📜 3. Locked Bets History & Live Squad Feed")
        st.write("Keep all your tickets in one place and share plays with the squad.")
        st.markdown("""
        * **Smart Status Badges:** Slips automatically track game progress (`⏳ PENDING`, `⚡ IN PLAY`, `🏆 WON`, `❌ LOST`).
        * **Clean USD Metrics:** Displays risk and return metrics alongside net profit ROI percentages.
        * **In-Game War Room:** Click on active single bets to enter the War Room and track live equity and smart cashout fair values.
        """)

    with st.container(border=True):
        st.markdown("### 🏆 4. Squad Leaderboard & The Locker Room")
        st.markdown("""
        * **Leaderboard Standings:** Automatically tracks wins, losses, win rates, and total net profit ($) for every bettor in your crew.
        * **Badges:** Earn badges like `🎯 Sniper` or `🔥 On Fire` based on consistency and profit margins.
        * **The Locker Room:** Real-time squad chat feed for game chatter, alerts, and banter.
        """)

# PAGE: MODEL METHODOLOGY & MATH BREAKDOWN
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Model Architecture & Math")
    st.caption("How edge, variance, and straight-up win rates are calculated.")

    with st.container(border=True):
        st.markdown("### 1. In-Game Pace & Drift Modeling")
        st.write("Sportsbooks typically project points using static half-time divisions. Flurkstradamus continuously recalculates variance and drift across 6 distinct states:")
        st.markdown("""
        * **Pre-Game:** Baseline = Open Total, $\sigma = 8.5$.
        * **1st Quarter:** Evaluates scoring pace relative to a 25% game duration baseline:
          $$Pace\\ Delta = Points\\ Scored - (Pregame \\times 0.25)$$
          Adjusts the final projection by 40% of the early deviation ($\sigma = 7.5$).
        * **Halftime:** Factor in point margins and game script:
          $$Projected\\ 2H = (Pregame \\times 0.475) + (Pace\\ Delta \\times 0.30) + Game\\ Script\\ Modifier$$
          * *Blowout ($\ge 17$ pt margin):* $-3.5$ pts (clock bleed).
          * *Decisive ($10-16$ pt margin):* $-1.5$ pts.
          * *Close ($0-3$ pt margin):* $+1.5$ pts (stopping clock, hurry-up drives).
        * **3rd Quarter:** Locks 75% of actual scoring ($\sigma = 4.0$).
        * **4th Quarter / Late Game:** Closes remaining scoring volume to actual game pace hazards ($\sigma = 1.8$).
        * **Final / Completed:** All remaining variance decays to zero ($\sigma \\to 0$).
        """)

    with st.container(border=True):
        st.markdown("### 2. Normal CDF & Win Probability Calculation")
        st.latex(r"Z = \frac{L - \mu}{\sigma}")
        st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")

    with st.container(border=True):
        st.markdown("### 3. Straight-Up Moneyline & Spread Engines")
        st.latex(r"\text{Spread}_{\text{eff}} = (\text{Home Proj} - \text{Away Proj}) + \left[(\text{Home Win \%} - \text{Away Win \%}) \times 7.0\right]")
        st.latex(r"P(\text{Home Win}) = \frac{1}{1 + e^{-\frac{\text{Spread}_{\text{eff}}}{6.5}}}")

# PAGE: SINGLE GAME ENGINE VIEW & FORM
if menu_choice == "Single Game Engine":
    # ----------------------------------------------------
    # SINGLE GAME INPUT FORM & MODEL CALCULATIONS
    # With Team Logos & Visual Pick Badge Directly Inside
    # ----------------------------------------------------
    all_stages = ["Pre-Game", "1st Quarter", "Halftime", "3rd Quarter", "4th Quarter / Late Game", "Final / Game Completed"]
    default_stage_idx = all_stages.index(detected_stage) if detected_stage in all_stages else 2
    bracket_stage = st.selectbox("Game Checkpoint / Period", options=all_stages, index=default_stage_idx, key=f"stage_sel_{g_id}_v{form_ver}")

    c1, c2 = st.columns(2)
    with c1:
        home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}_v{form_ver}")
        away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}_v{form_ver}")
        home_rec = st.text_input(f"{g['home_short']} Record", value=g.get("home_record", "0-0"), key=f"h_rec_{g_id}_v{form_ver}")
        away_rec = st.text_input(f"{g['away_short']} Record", value=g.get("away_record", "0-0"), key=f"a_rec_{g_id}_v{form_ver}")
        pregame_total = st.number_input("Pre-Game Baseline Total", value=espn_ou, step=0.5, key=f"pre_{g_id}_v{form_ver}")

    with c2:
        sc1, sc2 = st.columns(2)
        h_pts_in = sc1.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"], key=f"hp_{g_id}_v{form_ver}")
        a_pts_in = sc2.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"], key=f"ap_{g_id}_v{form_ver}")
        market_line = st.number_input("Market Total Offered", value=round(pregame_total) + 0.5, step=0.5, key=f"mkt_{g_id}_v{form_ver}")
        spread_line = st.number_input(f"{g['home_short']} Spread", value=espn_spread, step=0.5, key=f"spd_{g_id}_v{form_ver}")

    default_wtype_idx = 0
    if applied:
        if applied["category"] == "Moneyline":
            default_wtype_idx = 1
        elif applied["category"] == "Spread":
            default_wtype_idx = 2
        elif applied["category"] == "2H Total":
            default_wtype_idx = 3
        elif applied["category"] == "Total":
            default_wtype_idx = 0

    bet_type = st.radio(
        "Wager Type", 
        ["Game Total", "Straight Up Winner (Moneyline)", "Point Spread (ATS)", "2nd Half Total"], 
        index=default_wtype_idx,
        horizontal=True, 
        key=f"btype_sel_{g_id}_v{form_ver}"
    )

    with st.form(f"single_bet_form_v{form_ver}"):
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; background-color: rgba(255, 255, 255, 0.04); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px; border: 1px solid rgba(255, 255, 255, 0.1);">
            <div style="display: flex; align-items: center; gap: 8px;">
                <img src="{g.get('away_logo', DEFAULT_LOGO)}" width="30" height="30" style="border-radius: 50%;">
                <div>
                    <strong style="font-size: 1.0rem;">{g['away_short']}</strong>
                    <span style="opacity: 0.6; font-size: 0.75rem; margin-left: 2px;">({g.get('away_record', '0-0')})</span>
                </div>
                <span style="opacity: 0.4; margin: 0 4px; font-weight: 700;">@</span>
                <img src="{g.get('home_logo', DEFAULT_LOGO)}" width="30" height="30" style="border-radius: 50%;">
                <div>
                    <strong style="font-size: 1.0rem;">{g['home_short']}</strong>
                    <span style="opacity: 0.6; font-size: 0.75rem; margin-left: 2px;">({g.get('home_record', '0-0')})</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="opacity: 0.85; font-size: 0.80rem; font-weight: 600;">🗓️ {g.get('kickoff', g.get('status', 'Pre-Game'))}</div>
                <div style="opacity: 0.55; font-size: 0.75rem;">Selected Slip: <strong>{g['away_short']} @ {g['home_short']}</strong></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if bet_type in ["Game Total", "2nd Half Total"]:
            f1, f2 = st.columns(2)
            default_side_idx = 0
            if applied and applied.get("side"):
                default_side_idx = 0 if applied["side"] == "Under" else 1
            side = f1.selectbox("Side", ["Under", "Over"], index=default_side_idx, key=f"side_{g_id}_v{form_ver}")
            
            calc_default = live_2h_proj if bet_type == "2nd Half Total" else final_proj
            calc_strike = applied["target_line"] if (applied and applied.get("target_line")) else (round(calc_default + 2.5) + 0.5 if not is_completed else float(pts_scored))
            strike = f2.number_input("Target Line (pts)", value=float(calc_strike), step=0.5, key=f"strike_{g_id}_v{form_ver}")
            picked_t = None
        elif bet_type == "Point Spread (ATS)":
            f1, f2 = st.columns(2)
            default_spd_team_idx = 0
            if applied and applied.get("picked_team"):
                default_spd_team_idx = 0 if applied["picked_team"] == home_team else 1
            picked_t = f1.selectbox("Team to Cover", [home_team, away_team], index=default_spd_team_idx, format_func=lambda x: f"{g['home_short']} ({home_team})" if x == home_team else f"{g['away_short']} ({away_team})", key=f"spd_pick_{g_id}_v{form_ver}")
            
            if applied and applied.get("target_line") is not None:
                default_spd_val = float(applied["target_line"])
            else:
                default_spd_val = float(spread_line if picked_t == home_team else -spread_line)
            strike = f2.number_input("Spread Line", value=default_spd_val, step=0.5, key=f"spd_val_{g_id}_v{form_ver}")
            side = "Spread"
        else:
            side = "Moneyline"
            strike = None
            default_team_idx = 0
            if applied and applied.get("picked_team"):
                default_team_idx = 0 if applied["picked_team"] == home_team else 1
            picked_t = st.selectbox("Winning Team", [home_team, away_team], index=default_team_idx, format_func=lambda x: f"{g['home_short']} ({home_team})" if x == home_team else f"{g['away_short']} ({away_team})", key=f"ml_pick_{g_id}_v{form_ver}")

        p1, p2 = st.columns(2)
        risk_amt = p1.number_input("Risk ($)", min_value=1.0, value=5.0, step=5.0, key=f"risk_{g_id}_v{form_ver}")
        
        suggested_multiplier = applied.get("est_payout_multiplier", 1.91) if applied else 1.91
        calculated_payout = round(risk_amt * suggested_multiplier, 2)
        payout_amt = p2.number_input("Payout ($)", min_value=1.0, value=calculated_payout, step=1.0, key=f"payout_{g_id}_v{form_ver}")
        
        default_notes = f"AI Tier Edge: {applied['pick']} ({applied.get('roi_label', '')})" if applied else "Model play"
        ticket_notes = st.text_input("Notes", default_notes, key=f"notes_{g_id}_v{form_ver}")

        lock_submit = st.form_submit_button("Lock In Bet", use_container_width=True)
        if lock_submit:
            if bet_type in ["Game Total", "2nd Half Total"]:
                ref_proj = live_2h_proj if bet_type == "2nd Half Total" else final_proj
                ref_sig = 5.0 if bet_type == "2nd Half Total" else std_bracket
                prob_calc = calculate_win_prob(strike, ref_proj, ref_sig, is_under=(side == "Under"))
                bet_label = f"{side} {strike}" if bet_type == "Game Total" else f"2H {side} {strike}"
                cat = "2H Total" if bet_type == "2nd Half Total" else "Total"
            elif bet_type == "Point Spread (ATS)":
                prob_calc = home_cover_exp if picked_t == home_team else away_cover_exp
                bet_label = f"{picked_t} {strike:+}"
                cat = "Spread"
            else:
                prob_calc = home_win_prob if picked_t == home_team else away_win_prob
                bet_label = f"{picked_t} ML"
                cat = "Moneyline"

            initial_status = "Pending"
            ticket_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
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
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts)
            st.session_state.single_applied_pick = None
            st.success("Ticket saved to history!")
