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

# Responsive styling & STRICT LEFT-ALIGNMENT FOR SIDEBAR BUTTONS
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

    /* FORCED LEFT ALIGNMENT FOR NAVIGATION BUTTONS */
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
        padding-left: 14px !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
        min-height: 2.1rem !important;
        height: 2.1rem !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button p {
        text-align: left !important;
        justify-content: flex-start !important;
        width: 100% !important;
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button * {
        text-align: left !important;
        justify-content: flex-start !important;
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
            uname = st.text_input("Username", placeholder="e.g. sharpbettor").strip().lower()
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
            new_uname = st.text_input("Choose Username (Login ID)", placeholder="e.g. gridiron_guru").strip().lower()
            new_dname = st.text_input("Display Name / Bettor Handle", placeholder="e.g. Gridiron Guru")
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
active_uname = current_user_profile.get("username", "").strip().lower()

if active_uname == "flurk":
    current_user = "Flurk"
else:
    current_user = current_user_profile.get("display_name", current_user_profile.get("username", "Bettor"))

is_user_admin = current_user_profile.get("is_admin", False)

# ==========================================
# ESPN SCOREBOARD DATA (WITH DYNAMIC FILTER)
# ==========================================
@st.cache_data(ttl=25)
def get_extended_games(selected_league="All Games"):
    all_games = []
    seen_ids = set()
    
    endpoints = []
    if selected_league in ["NFL", "All Games"]:
        endpoints.append(("NFL", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=100"))
    if selected_league in ["NCAA Football", "All Games"]:
        endpoints.append(("NCAA", "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?limit=100&groups=80"))

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

    return all_games

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.markdown(f"## 🔮 Flurkstradamus")
st.sidebar.markdown(f"👤 **{current_user}** (`@{current_user_profile.get('username')}`)")
if current_user_profile.get("favorite_team"):
    st.sidebar.caption(f"🏈 {current_user_profile.get('favorite_team')}")

col_u1, _ = st.sidebar.columns(2)
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
league = st.sidebar.radio("Primary League", ["NFL", "NCAA Football", "All Games"])

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

games_data = get_extended_games(league)
auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages)

# ==========================================
# PAGE ROUTING
# ==========================================

# 1. WAR ROOM DETAIL
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
    live_game_info = find_game_for_bet(selected_bet, games_data)

    if not live_game_info:
        st.warning("Live scoreboard data for this game is currently inactive.")
        st.stop()

    curr_away = live_game_info["away_score"]
    curr_home = live_game_info["home_score"]
    total_pts = curr_away + curr_home

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
    st.stop()

# 2. ADMIN USER CONTROL
elif menu_choice == "🛡️ Admin User Control" and is_user_admin:
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
                if u_key != "flurk" and u_key != current_user_profile.get("username"):
                    if st.button("🗑️ Delete", key=f"del_u_{u_key}", use_container_width=True):
                        users.pop(u_key)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users)
                        st.rerun()

# 3. LIVE SQUAD FEED
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

# 4. THE LOCKER ROOM
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

# 5. SQUAD LEADERBOARD
elif menu_choice == "🏆 Squad Leaderboard":
    st.subheader("🏆 Squad Leaderboard")
    st.caption("Consensus standings and betting performance.")

    user_stats = {}
    for b in st.session_state.saved_bets:
        u_raw = b.get("user", "Flurk")
        u_clean = u_raw.strip() if u_raw.strip() else "Flurk"
        u_key = u_clean.lower()
        display_name = "Flurk" if u_key == "flurk" else u_clean

        if u_key not in user_stats:
            user_stats[u_key] = {
                "display_name": display_name,
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

# 6. LOCKED BETS HISTORY (ROBUST SEARCH & RESTORATION)
elif menu_choice == "Locked Bets History":
    st.subheader(f"📜 {current_user}'s Locked Bets")
    st.caption("Your personalized active slips, scores, and settled tickets.")

    curr_user_clean = current_user.strip().lower()
    
    col_filter1, col_filter2 = st.columns([3, 1])
    with col_filter2:
        show_all_history = st.toggle("Show All Squad Bets", value=False)
        
    if show_all_history:
        my_tickets = st.session_state.saved_bets
    else:
        # Match case-insensitively across Flurk, flurk, admin, and current handle
        my_tickets = [
            b for b in st.session_state.saved_bets 
            if b.get("user", "").strip().lower() == curr_user_clean 
            or (curr_user_clean == "flurk" and b.get("user", "").strip().lower() in ["flurk", "admin"])
        ]

    with col_filter1:
        st.write(f"Showing **{len(my_tickets)}** ticket(s) (Total in database: **{len(st.session_state.saved_bets)}**).")
        if st.button("⚡ Grade Finals", use_container_width=True):
            if auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages):
                st.success("Updated tickets!")
                st.rerun()

    if not my_tickets:
        st.info(f"You don't have any locked bets yet under handle '{current_user}'. (Tip: Toggle 'Show All Squad Bets' above if your bets were saved under another name).")
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
                        <span style="opacity: 0.6; font-size: 0.85rem; margin-left: 6px;">by <strong>{b.get('user', 'Flurk')}</strong></span>
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
                    cat_label = b.get("bet_category", b.get("type", "Single"))
                    st.caption(f"Type: {cat_label}")
                with c_row4:
                    if st.button("🗑️", key=f"del_slip_{b['id']}", help="Delete this ticket", use_container_width=True):
                        st.session_state.saved_bets.pop(real_idx)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts)
                        st.rerun()

# 7. HOW IT WORKS
elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: The Flurkstradamus User Guide")
    st.caption("Mastering the Edge Engine, Combo Builder, and Squad Tracker.")

    with st.container(border=True):
        st.markdown("### ⚡ 1. Single Game Engine & AI Strategy Builder")
        st.write("The Single Game Engine connects live to ESPN scoreboard endpoints to track games in real-time.")
        st.markdown("""
        * **Live Line Drift Tracking:** Compares opening sportsbook lines against real-time scoring to compute live totals, 2H totals, and ATS margins.
        * **The Risk vs. Return Dial:** Adjust the slider to set your model objective from Safe Floor up to High Profit.
        * **One-Click Loading:** Press '📥 Load to Form' on any card to immediately populate your slip.
        """)

    with st.container(border=True):
        st.markdown("### 🔗 2. 2–12 Leg Combo Builder")
        st.markdown("""
        * **Automated Strategy Generator:** Pick an objective and set your target leg count to compound true win probabilities.
        * **Interactive Leg Removal:** Click Edit beside the recommended ticket header to remove individual legs.
        """)

    with st.container(border=True):
        st.markdown("### 📜 3. Locked Bets History & Squad Leaderboard")
        st.markdown("""
        * **Smart Status Badges:** Tracks PENDING, IN PLAY, WON, and LOST statuses automatically.
        * **Leaderboard Standings:** Ranks bettors by total net profit and win rate.
        """)

# 8. MODEL METHODOLOGY & MATH BREAKDOWN (COMPLETE RESTORATION)
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Model Architecture & Math Breakdown")
    st.caption("Detailed statistical formulations governing in-game drift, variance decay, and logistic win probabilities.")

    with st.container(border=True):
        st.markdown("### 1. In-Game Pace & Drift Modeling")
        st.write(
            "Sportsbooks project points using static half-time splits. "
            "Flurkstradamus continuously recalculates true variance and script deviations across 6 distinct states:"
        )
        st.markdown("""
        * **Pre-Game:** Baseline = Open Total, Standard Deviation $\sigma = 8.5$.
        * **1st Quarter:** Evaluates scoring pace relative to a 25% game duration baseline:
          $$Pace\\ Delta = Points\\ Scored - (Pregame \\times 0.25)$$
          Adjusts the final projection by 40% of the early deviation ($\sigma = 7.5$).
        * **Halftime:** Incorporates point margin and second-half game script adjustments:
          $$Projected\\ 2H = (Pregame \\times 0.475) + (Pace\\ Delta \\times 0.30) + Game\\ Script\\ Modifier$$
          * *Blowout ($\ge 17$ pt margin):* $-3.5$ pts (clock bleed, run-heavy drives).
          * *Decisive ($10-16$ pt margin):* $-1.5$ pts.
          * *Close ($0-3$ pt margin):* $+1.5$ pts (hurry-up offense, stop-the-clock scenarios).
        * **3rd Quarter:** Locks 75% of actual scoring ($\sigma = 4.0$).
        * **4th Quarter / Late Game:** Closes remaining scoring volume to actual game pace hazards ($\sigma = 1.8$).
        * **Final / Completed:** All remaining variance decays to zero ($\sigma \\to 0$).
        """)

    with st.container(border=True):
        st.markdown("### 2. Normal CDF & Win Probability Calculation")
        st.write("Target line evaluation utilizes the cumulative normal distribution function:")
        st.latex(r"Z = \frac{L - \mu}{\sigma}")
        st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")
        st.latex(r"P(\text{Over}) = 1.0 - P(\text{Under})")

    with st.container(border=True):
        st.markdown("### 3. Straight-Up Moneyline & Spread Engines")
        st.write("Calculates team efficiency differentials transformed through a logistic sigmoid function:")
        st.latex(r"\text{Spread}_{\text{eff}} = (\text{Home Proj} - \text{Away Proj}) + \left[(\text{Home Win \%} - \text{Away Win \%}) \times 7.0\right]")
        st.latex(r"P(\text{Home Win}) = \frac{1}{1 + e^{-\frac{\text{Spread}_{\text{eff}}}{6.5}}}")

# 9. 2-12 LEG COMBO BUILDER
elif menu_choice == "2-12 Leg Combo Builder":
    st.subheader("🔗 Multi-Leg Combo Builder (Up to 12 Legs)")
    game_choices = [f"[{gm['league']}] {gm['away_short']} @ {gm['home_short']} ({gm.get('kickoff', gm['status'])})" for gm in games_data]

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

    combo_legs = []
    compound_prob = 1.0

    ver = st.session_state.combo_version
    for i, leg_data in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            sel_matchup = st.selectbox(
                f"Leg {i+1} Matchup",
                range(len(game_choices)),
                index=min(leg_data["matchup_idx"], len(game_choices) - 1),
                format_func=lambda x: game_choices[x],
                key=f"m_sel_{i}_v{ver}"
            )
            leg_data["matchup_idx"] = sel_matchup
            leg_g = games_data[leg_data["matchup_idx"]]
            d_h, d_a = leg_g["home_team"], leg_g["away_team"]
            d_h_abbr, d_a_abbr = leg_g["home_short"], leg_g["away_short"]

            col_b, col_c = st.columns(2)
            side = col_b.selectbox("Side", ["Under", "Over"], index=0 if leg_data.get("side", "Under") == "Under" else 1, key=f"lside_{i}_v{ver}")
            strike = col_c.number_input("Line (pts)", value=float(leg_data.get("line", leg_g.get("market_ou", 44.5))), step=0.5, key=f"lstrike_{i}_v{ver}")
            leg_data["side"] = side
            leg_data["line"] = strike

            leg_prob = calculate_win_prob(strike, 42.0, 7.0, is_under=(side == "Under"))
            leg_desc = f"{d_a_abbr} @ {d_h_abbr}: {side} {strike}"
            compound_prob *= leg_prob
            combo_legs.append({"desc": leg_desc, "prob": leg_prob})

    with st.container(border=True):
        st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        c_r1, c_r2 = st.columns(2)
        c_risk = c_r1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        c_payout = c_r2.number_input("Payout ($)", min_value=1.0, value=50.0, step=10.0)
        save_c_btn = st.form_submit_button("Lock In Ticket", use_container_width=True)
        if save_c_btn:
            legs_str = " | ".join([cl["desc"] for cl in combo_legs])
            combo_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": f"{len(combo_legs)}-Leg Combo",
                "bet_category": "Combo",
                "matchup": legs_str,
                "bet": f"{len(combo_legs)} Legs",
                "target_line": None,
                "bet_direction": None,
                "risk_dollars": float(c_risk),
                "payout_dollars": float(c_payout),
                "win_prob": f"{compound_prob * 100:.1f}%",
                "status": "Pending",
                "notes": "Combo Play"
            }
            st.session_state.saved_bets.insert(0, combo_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts)
            st.success("Combo ticket locked in!")

# 10. SINGLE GAME ENGINE
elif menu_choice == "Single Game Engine":
    st.subheader("⚡ Single Game Engine")

    form_ver = st.session_state.single_form_version

    if games_data:
        game_options = [f"[{g['league']}] {g['away_short']} @ {g['home_short']} ({g.get('kickoff', g['status'])})" for g in games_data]
        if st.session_state.single_selected_idx >= len(game_options):
            st.session_state.single_selected_idx = 0
            
        selected_idx = st.selectbox(
            "Select Matchup", 
            range(len(game_options)), 
            index=st.session_state.single_selected_idx, 
            format_func=lambda x: game_options[x],
            key=f"single_matchup_dropdown_v{form_ver}"
        )
        st.session_state.single_selected_idx = selected_idx
        
        g = games_data[selected_idx]
        g_id = g.get("id", str(selected_idx))
        detected_stage = g["checkpoint"]
        espn_ou = g["market_ou"]
        espn_spread = g["market_spread"]
    else:
        st.warning(f"No games currently active for {league}.")
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

    h_pts = g["home_score"]
    a_pts = g["away_score"]
    pts_scored = h_pts + a_pts
    margin = abs(h_pts - a_pts)
    is_completed = g.get("completed", False) or "final" in g["status"].lower()

    pregame_tot = float(espn_ou)
    if is_completed:
        final_proj = float(pts_scored)
        std_bracket = 0.01
    elif detected_stage == "Pre-Game":
        final_proj = pregame_tot
        std_bracket = 8.5
    elif detected_stage == "1st Quarter":
        pace_diff = pts_scored - (pregame_tot * 0.25)
        final_proj = pregame_tot + (pace_diff * 0.40)
        std_bracket = 7.5
    elif detected_stage == "Halftime":
        pace_diff = pts_scored - (pregame_tot * 0.525)
        script = -3.5 if margin >= 17 else (-1.5 if margin >= 10 else (1.5 if margin <= 3 else 0.0))
        final_proj = pts_scored + (pregame_tot * 0.475) + (pace_diff * 0.30) + script + 0.5
        std_bracket = 6.0
    elif detected_stage == "3rd Quarter":
        pace_diff = pts_scored - (pregame_tot * 0.775)
        final_proj = pts_scored + (pregame_tot * 0.225) + (pace_diff * 0.20)
        std_bracket = 4.0
    else:
        rem_points_exp = max((pregame_tot * 0.10) - (pts_scored * 0.05), 1.0)
        final_proj = pts_scored + rem_points_exp
        std_bracket = 1.8

    delta_full = final_proj - pregame_tot
    pregame_2h = round(pregame_tot * 0.525, 1)
    live_2h_proj = (pregame_tot * 0.475) + ((pts_scored - (pregame_tot * 0.525)) * 0.30) + 0.5 if detected_stage == "Halftime" else pregame_2h + (delta_full * 0.45)
    delta_2h = live_2h_proj - pregame_2h

    pregame_h_prob = calculate_moneyline_prob(pregame_tot / 2.0, pregame_tot / 2.0, g.get("home_record", "0-0"), g.get("away_record", "0-0"))
    live_h_prob = calculate_moneyline_prob(h_pts + (final_proj / 2.0), a_pts + (final_proj / 2.0), g.get("home_record", "0-0"), g.get("away_record", "0-0"), is_final=is_completed)
    live_a_prob = 1.0 - live_h_prob
    ml_swing = (live_h_prob - pregame_h_prob) * 100

    market_spd = float(espn_spread)
    pregame_proj_margin = -market_spd
    current_margin = h_pts - a_pts
    live_proj_margin = (pregame_proj_margin * 0.45) + (current_margin * 0.55) if detected_stage == "Halftime" else pregame_proj_margin
    spread_drift = live_proj_margin - pregame_proj_margin
    home_cover_exp = calculate_spread_prob(live_proj_margin, market_spd, std_bracket)
    away_cover_exp = 1.0 - home_cover_exp

    with st.container(border=True):
        st.markdown("#### 📊 Live Model Drift & Projections")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Full Game Total", f"{final_proj:.1f} pts", delta=f"{delta_full:+.1f} vs open ({pregame_tot})")
        m_col2.metric("2nd Half Total", f"{live_2h_proj:.1f} pts", delta=f"{delta_2h:+.1f} vs 2H base ({pregame_2h})")
        m_col3.metric(f"{g['home_short']} Win %", f"{live_h_prob*100:.1f}%", delta=f"{ml_swing:+.1f}% momentum")
        m_col4.metric(f"ATS Margin ({g['home_short']} {market_spd:+})", f"{live_proj_margin:+.1f} pts", delta=f"{spread_drift:+.1f} pts vs line")

    # TIERED STRATEGY ENGINE
    with st.expander("🤖 AI Strategy Engine (Adjustable Risk vs. Return Scale)", expanded=True):
        col_scope, col_type_filter = st.columns(2)
        scope_choice = col_scope.selectbox("Target Slate", ["🎯 Focus on Selected Game Above", "⚡ Scan Full Slate for Highest Discrepancy"])
        filter_choice = col_type_filter.selectbox("Type of Bet", ["⚡ Let the System Pick (All Markets Combined)", "📊 Full Game Total Score Over/Under", "⏱️ 2nd Half Total Points", "🏆 Team Win/Loser (Moneyline)", "🛡️ Spread (ATS Cover)"])
        
        strategy_dial = st.select_slider("Model Objective", options=["🛡️ Safe Floor (High Win %, Low Drawdown)", "⚖️ Balanced Edge (+EV Sweet Spot)", "🚀 High Profit (Max Multiplier & Value Underdogs)"], value="⚖️ Balanced Edge (+EV Sweet Spot)")

        active_game_for_strat = g
        strat_game_index = st.session_state.single_selected_idx
        if "Scan Full Slate" in scope_choice and games_data:
            live_pool = [gm for gm in games_data if not gm.get("completed", False)]
            if live_pool:
                active_game_for_strat = max(live_pool, key=lambda x: abs((x["home_score"] + x["away_score"] + (x.get("market_ou", 47.5)*0.475)) - x.get("market_ou", 47.5)))
                strat_game_index = games_data.index(active_game_for_strat)

        strat_candidates = []
        tg_away_logo = active_game_for_strat.get("away_logo", DEFAULT_LOGO)
        tg_home_logo = active_game_for_strat.get("home_logo", DEFAULT_LOGO)
        tg_away_short = active_game_for_strat.get("away_short", "AWAY")
        tg_home_short = active_game_for_strat.get("home_short", "HOME")
        tg_date_str = active_game_for_strat.get("kickoff", active_game_for_strat.get("status", "Pre-Game"))

        s_val = market_spd if home_cover_exp >= 0.5 else -market_spd
        s_team = active_game_for_strat["home_team"] if home_cover_exp >= 0.5 else active_game_for_strat["away_team"]
        s_abbr = tg_home_short if home_cover_exp >= 0.5 else tg_away_short
        s_p = home_cover_exp if home_cover_exp >= 0.5 else away_cover_exp

        strat_candidates.append({
            "type": "Spread (Consensus Line)",
            "pick": f"{s_abbr} {s_val:+}",
            "prob": s_p,
            "category": "Spread",
            "side": "Spread",
            "target_line": s_val,
            "picked_team": s_team,
            "game_index": strat_game_index,
            "est_payout_multiplier": 1.91,
            "roi_label": "+91% Profit",
            "drift_info": f"Expected Margin: {spread_drift:+.1f} pts vs line",
            "rationale": f"High value spread cover on {s_abbr} paying standard 1:1 odds."
        })

        line_base_2h = round(live_2h_proj) + 0.5
        p_base_2h = calculate_win_prob(line_base_2h, live_2h_proj, 5.0, is_under=True)
        strat_candidates.append({
            "type": "2nd Half Total (Model Consensus)",
            "pick": f"2H Under {line_base_2h}",
            "prob": p_base_2h,
            "category": "2H Total",
            "side": "Under",
            "target_line": line_base_2h,
            "picked_team": None,
            "game_index": strat_game_index,
            "est_payout_multiplier": 1.91,
            "roi_label": "+91% Profit",
            "drift_info": f"2H Proj: {live_2h_proj:.1f} pts",
            "rationale": "Direct statistical regression model projection for second half volume."
        })

        fav_team = active_game_for_strat["home_team"] if live_h_prob >= 0.5 else active_game_for_strat["away_team"]
        fav_abbr = tg_home_short if live_h_prob >= 0.5 else tg_away_short
        fav_prob = max(live_h_prob, live_a_prob)
        strat_candidates.append({
            "type": "Moneyline (Model Favorite)",
            "pick": f"{fav_abbr} ML",
            "prob": fav_prob,
            "category": "Moneyline",
            "side": "Moneyline",
            "target_line": None,
            "picked_team": fav_team,
            "game_index": strat_game_index,
            "est_payout_multiplier": 1.74,
            "roi_label": "+74% Profit",
            "drift_info": f"Win Probability: {fav_prob*100:.1f}%",
            "rationale": f"{fav_abbr} holds controlling efficiency dominance."
        })

        if "Safe Floor" in strategy_dial:
            strat_candidates.sort(key=lambda x: (x["prob"] * 0.85) + ((x["est_payout_multiplier"] / 3.0) * 0.15), reverse=True)
            tier_names = ["🥇 BEST (Highest Win Rate)", "🥈 BETTER (Strong Floor)", "🥉 GOOD (Reliable Safety)"]
        elif "High Profit" in strategy_dial:
            strat_candidates.sort(key=lambda x: (x["prob"] * 0.20) + ((x["est_payout_multiplier"] / 3.0) * 0.80), reverse=True)
            tier_names = ["🥇 BEST (Max Multiplier Edge)", "🥈 BETTER (High Upside)", "🥉 GOOD (Balanced Return)"]
        else:
            strat_candidates.sort(key=lambda x: (x["prob"] * x["est_payout_multiplier"]), reverse=True)
            tier_names = ["🥇 BEST (Optimal +EV Balance)", "🥈 BETTER (Strong Risk/Reward)", "🥉 GOOD (Solid Fundamental Play)"]

        for idx, (tier_label, sc) in enumerate(zip(tier_names, strat_candidates[:3])):
            with st.container(border=True):
                st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 5px; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 7px;">
                        <span style="font-weight: 800; font-size: 0.88rem;">{tier_label}</span>
                        <span style="opacity: 0.4;">•</span>
                        <code style="font-size: 0.80rem;">{sc['type']}</code>
                    </div>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <img src="{tg_away_logo}" width="20" height="20" style="border-radius: 50%;">
                        <strong style="font-size: 0.85rem;">{tg_away_short}</strong>
                        <span style="opacity: 0.4; font-size: 0.8rem;">@</span>
                        <img src="{tg_home_logo}" width="20" height="20" style="border-radius: 50%;">
                        <strong style="font-size: 0.85rem;">{tg_home_short}</strong>
                        <span style="opacity: 0.55; font-size: 0.75rem; margin-left: 4px;">({tg_date_str})</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                r_c1, r_c2 = st.columns([7.5, 2.5], vertical_alignment="center")
                with r_c1:
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                        <strong style='color:#4ade80; font-size:1.15rem;'>{sc['pick']}</strong>
                        <span style='background-color:#22c55e; color:#000; font-weight:800; font-size:0.75rem; padding:2px 8px; border-radius:4px;'>
                            {sc['roi_label']}
                        </span>
                        <span style='background-color:rgba(255,255,255,0.08); padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.80rem;'>
                            {sc['prob']*100:.1f}% Win Prob
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"{sc['drift_info']} • {sc['rationale']}")
                with r_c2:
                    if st.button("📥 Load to Form", key=f"apply_tier_{idx}_{sc['pick']}", use_container_width=True):
                        st.session_state.single_applied_pick = sc
                        st.session_state.single_selected_idx = sc["game_index"]
                        st.session_state.single_form_version += 1
                        st.rerun()

    # FORM TO LOCK BETS
    applied = st.session_state.single_applied_pick
    all_stages = ["Pre-Game", "1st Quarter", "Halftime", "3rd Quarter", "4th Quarter / Late Game", "Final / Game Completed"]
    default_stage_idx = all_stages.index(detected_stage) if detected_stage in all_stages else 2
    bracket_stage = st.selectbox("Game Period", options=all_stages, index=default_stage_idx, key=f"stage_sel_{g_id}_v{form_ver}")

    c1, c2 = st.columns(2)
    with c1:
        home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}_v{form_ver}")
        away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}_v{form_ver}")
        pregame_total = st.number_input("Pre-Game Total", value=espn_ou, step=0.5, key=f"pre_{g_id}_v{form_ver}")

    with c2:
        h_pts_in = st.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"], key=f"hp_{g_id}_v{form_ver}")
        a_pts_in = st.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"], key=f"ap_{g_id}_v{form_ver}")
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

    bet_type = st.radio("Wager Type", ["Game Total", "Straight Up Winner (Moneyline)", "Point Spread (ATS)", "2nd Half Total"], index=default_wtype_idx, horizontal=True, key=f"btype_sel_{g_id}_v{form_ver}")

    with st.form(f"single_bet_form_v{form_ver}"):
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; background-color: rgba(255, 255, 255, 0.04); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <img src="{g.get('away_logo', DEFAULT_LOGO)}" width="28" height="28" style="border-radius: 50%;">
                <strong>{g['away_short']}</strong> @
                <img src="{g.get('home_logo', DEFAULT_LOGO)}" width="28" height="28" style="border-radius: 50%;">
                <strong>{g['home_short']}</strong>
            </div>
            <div style="opacity: 0.6; font-size: 0.8rem;">🗓️ {g.get('kickoff', g.get('status', 'Pre-Game'))}</div>
        </div>
        """, unsafe_allow_html=True)

        if bet_type in ["Game Total", "2nd Half Total"]:
            f1, f2 = st.columns(2)
            side = f1.selectbox("Side", ["Under", "Over"], index=0 if (applied and applied.get("side") == "Under") else 1, key=f"side_{g_id}_v{form_ver}")
            strike = f2.number_input("Target Line (pts)", value=float(applied["target_line"]) if (applied and applied.get("target_line")) else float(final_proj), step=0.5, key=f"strike_{g_id}_v{form_ver}")
            picked_t = None
        elif bet_type == "Point Spread (ATS)":
            f1, f2 = st.columns(2)
            picked_t = f1.selectbox("Team to Cover", [home_team, away_team], index=0 if (applied and applied.get("picked_team") == home_team) else 1, key=f"spd_pick_{g_id}_v{form_ver}")
            strike = f2.number_input("Spread Line", value=float(applied["target_line"]) if (applied and applied.get("target_line") is not None) else float(spread_line), step=0.5, key=f"spd_val_{g_id}_v{form_ver}")
            side = "Spread"
        else:
            picked_t = st.selectbox("Winning Team", [home_team, away_team], index=0 if (applied and applied.get("picked_team") == home_team) else 1, key=f"ml_pick_{g_id}_v{form_ver}")
            strike = None
            side = "Moneyline"

        p1, p2 = st.columns(2)
        risk_amt = p1.number_input("Risk ($)", min_value=1.0, value=5.0, step=5.0, key=f"risk_{g_id}_v{form_ver}")
        suggested_multiplier = applied.get("est_payout_multiplier", 1.91) if applied else 1.91
        payout_amt = p2.number_input("Payout ($)", min_value=1.0, value=round(risk_amt * suggested_multiplier, 2), step=1.0, key=f"payout_{g_id}_v{form_ver}")
        ticket_notes = st.text_input("Notes", f"Model Edge: {applied['pick']}" if applied else "Model Play", key=f"notes_{g_id}_v{form_ver}")

        lock_submit = st.form_submit_button("Lock In Bet", use_container_width=True)
        if lock_submit:
            bet_label = f"{side} {strike}" if strike else f"{picked_t} ML"
            cat = "2H Total" if bet_type == "2nd Half Total" else ("Spread" if bet_type == "Point Spread (ATS)" else ("Moneyline" if bet_type == "Straight Up Winner (Moneyline)" else "Total"))
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
                "win_prob": f"{home_cover_exp*100:.1f}%",
                "status": "Pending",
                "notes": ticket_notes
            }
            st.session_state.saved_bets.insert(0, ticket_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts)
            st.session_state.single_applied_pick = None
            st.success("Ticket saved to history!")
