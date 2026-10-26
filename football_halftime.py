import streamlit as st
import requests
import re
import random
import string
from datetime import datetime, timedelta

# Import modular engines
from config import DEFAULT_LOGO, OFFICIAL_ABBR_MAP
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob
from database import load_storage, save_all_storage, find_game_for_bet, auto_resolve_bets, hash_password

st.set_page_config(
    page_title="Flurkstradamus Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Responsive Desktop + Mobile styling & STRICT LEFT ALIGNMENT FOR NAVIGATION
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

def get_current_et_time():
    """Returns true Eastern Time (ET) regardless of host server timezone."""
    utc_now = datetime.utcnow()
    et_now = utc_now - timedelta(hours=4)
    return et_now

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
if "editing_msg_id" not in st.session_state:
    st.session_state.editing_msg_id = None

# Single Game State Keys
if "single_selected_idx" not in st.session_state:
    st.session_state.single_selected_idx = 0
if "single_applied_pick" not in st.session_state:
    st.session_state.single_applied_pick = None
if "single_form_version" not in st.session_state:
    st.session_state.single_form_version = 0

# Load Database
b_data, c_data, u_data, banned_emails_data = load_storage()
if "saved_bets" not in st.session_state:
    st.session_state.saved_bets = b_data
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = c_data
if "user_accounts" not in st.session_state:
    st.session_state.user_accounts = u_data
if "banned_emails" not in st.session_state:
    st.session_state.banned_emails = banned_emails_data

# ==========================================
# USER LOGIN, SIGNUP & FORGOT PASSWORD (DIRECT ACCESS)
# ==========================================
if st.session_state.logged_in_user is None:
    st.title("🔮 Flurkstradamus")
    st.caption("Sign in, create an account, or recover your password.")
    
    tab_login, tab_signup, tab_forgot = st.tabs(["🔐 Sign In", "📝 Create Account", "🔑 Forgot Password"])
    
    with tab_login:
        with st.form("user_login_form"):
            uname = st.text_input("Username or Email", placeholder="e.g. sharpbettor or email@domain.com").strip().lower()
            pword = st.text_input("Password", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Sign In to Flurkstradamus", use_container_width=True)
            
            if submit_login:
                matched_user = None
                for u_k, u_v in st.session_state.user_accounts.items():
                    if u_k.lower() == uname or u_v.get("email", "").lower() == uname:
                        matched_user = u_v
                        break

                if matched_user:
                    if matched_user.get("is_banned", False):
                        st.error("This account has been banned by the administrator.")
                    elif matched_user.get("password_hash") == hash_password(pword):
                        st.session_state.logged_in_user = matched_user
                        st.success(f"Welcome back, {matched_user.get('display_name')}!")
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                else:
                    st.error("Account not found.")
                    
    with tab_signup:
        with st.form("user_signup_form"):
            new_uname = st.text_input("Choose Username (Login ID)", placeholder="e.g. gridiron_guru").strip().lower()
            new_email = st.text_input("Email Address (For Account Recovery)", placeholder="e.g. bettor@example.com").strip().lower()
            new_dname = st.text_input("Display Name / Bettor Handle", placeholder="e.g. Gridiron Guru")
            new_pword = st.text_input("Choose Password", type="password", placeholder="••••••••")
            new_pword_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••")
            fav_team = st.text_input("Favorite Team (Optional)", placeholder="e.g. Philadelphia Eagles")
            submit_signup = st.form_submit_button("Create My Account", use_container_width=True)
            
            if submit_signup:
                if not new_uname or not new_email or not new_pword or not new_dname:
                    st.error("Username, email, display name, and password are all required.")
                elif "@" not in new_email or "." not in new_email:
                    st.error("Please provide a valid email address.")
                elif new_email in st.session_state.banned_emails:
                    st.error("This email address has been banned from registering.")
                elif len(new_uname) < 3:
                    st.error("Username must be at least 3 characters.")
                elif new_pword != new_pword_confirm:
                    st.error("Passwords do not match.")
                elif new_uname in st.session_state.user_accounts:
                    st.error("This username is already taken. Please choose another.")
                elif any(u.get("email", "").lower() == new_email for u in st.session_state.user_accounts.values()):
                    st.error("An account with this email address already exists.")
                else:
                    new_user = {
                        "username": new_uname,
                        "email": new_email,
                        "display_name": new_dname.strip(),
                        "password_hash": hash_password(new_pword),
                        "is_admin": False,
                        "is_banned": False,
                        "created_at": get_current_et_time().strftime("%Y-%m-%d"),
                        "favorite_team": fav_team.strip() if fav_team else "NFL",
                        "reset_token": None
                    }
                    st.session_state.user_accounts[new_uname] = new_user
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                    st.session_state.logged_in_user = new_user
                    st.success("Account created successfully!")
                    st.rerun()

    with tab_forgot:
        st.markdown("#### 🔑 Password Recovery")
        st.write("Enter your registered email address to generate an on-screen password reset authorization code.")
        
        with st.form("request_reset_form"):
            recover_email = st.text_input("Registered Email Address", placeholder="e.g. user@example.com").strip().lower()
            send_code_btn = st.form_submit_button("Request Reset Code", use_container_width=True)
            
            if send_code_btn:
                target_user = None
                for u in st.session_state.user_accounts.values():
                    if u.get("email", "").lower() == recover_email:
                        target_user = u
                        break
                        
                if target_user:
                    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    target_user["reset_token"] = token
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                    st.success(f"✅ Recovery Code Generated: **`{token}`** (Enter this code below to set your new password)")
                else:
                    st.error("No account found with that email address.")

        with st.form("complete_reset_form"):
            st.markdown("##### Complete Password Change")
            c_email = st.text_input("Confirm Your Email", placeholder="user@example.com").strip().lower()
            code_input = st.text_input("6-Character Reset Code", placeholder="e.g. AB12CD").strip().upper()
            new_pass1 = st.text_input("New Password", type="password", placeholder="••••••••")
            new_pass2 = st.text_input("Confirm New Password", type="password", placeholder="••••••••")
            submit_new_pass = st.form_submit_button("Update Password", use_container_width=True)
            
            if submit_new_pass:
                target_user = None
                for u in st.session_state.user_accounts.values():
                    if u.get("email", "").lower() == c_email:
                        target_user = u
                        break
                        
                if not target_user:
                    st.error("User not found.")
                elif not target_user.get("reset_token") or target_user.get("reset_token") != code_input:
                    st.error("Invalid or expired reset code.")
                elif new_pass1 != new_pass2:
                    st.error("New passwords do not match.")
                elif len(new_pass1) < 4:
                    st.error("Password must be at least 4 characters.")
                else:
                    target_user["password_hash"] = hash_password(new_pass1)
                    target_user["reset_token"] = None
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                    st.success("🎉 Password updated successfully! Please switch to the 'Sign In' tab.")

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
# ESPN SCOREBOARD DATA (WITH DYNAMIC FILTER & BACKUP SLATE)
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
            if selected_league == "All Games" or b_game["league"] == selected_league or (selected_league == "NCAA Football" and b_game["league"] == "NCAA"):
                if b_game["id"] not in seen_ids:
                    all_games.append(b_game)
                    seen_ids.add(b_game["id"])

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
    b_data, c_data, u_data, b_e_data = load_storage()
    st.session_state.saved_bets = b_data
    st.session_state.chat_messages = c_data
    st.session_state.user_accounts = u_data
    st.session_state.banned_emails = b_e_data
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

# 2. ENHANCED ADMIN USER CONTROL
elif menu_choice == "🛡️ Admin User Control" and is_user_admin:
    st.subheader("🛡️ Commissioner Admin Console & User Control")
    st.caption("Inspect user accounts, audit locked bets, ban bad actors, and reset credentials.")
    
    users = st.session_state.user_accounts
    banned_emails = st.session_state.banned_emails

    m1, m2, m3 = st.columns(3)
    m1.metric("Registered Users", len(users))
    m2.metric("Total Bets Locked In", len(st.session_state.saved_bets))
    m3.metric("Banned Email Blacklist", len(banned_emails))

    with st.expander("🚫 Manage Banned Email Blacklist", expanded=False):
        b_col1, b_col2 = st.columns([3, 1])
        with b_col1:
            email_to_ban = st.text_input("Add Email to Blacklist", placeholder="e.g. spammer@domain.com").strip().lower()
        with b_col2:
            if st.button("Add to Blacklist", use_container_width=True):
                if email_to_ban and email_to_ban not in banned_emails:
                    banned_emails.append(email_to_ban)
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, banned_emails)
                    st.success(f"Blacklisted {email_to_ban}")
                    st.rerun()
        if banned_emails:
            st.write("Active Blacklist:")
            for b_e in banned_emails:
                st.code(b_e)

    st.markdown("---")
    st.markdown("### 👥 Member Directory")

    for u_key, u_info in list(users.items()):
        is_u_banned = u_info.get("is_banned", False)
        is_u_adm = u_info.get("is_admin", False)
        u_email = u_info.get("email", "No email provided")
        u_display = u_info.get("display_name", u_key)

        u_bets = [b for b in st.session_state.saved_bets if b.get("user", "").strip().lower() == u_key.lower() or b.get("user", "").strip().lower() == u_display.lower()]

        with st.container(border=True):
            r1, r2 = st.columns([6, 4])
            with r1:
                badge = "👑 Admin" if is_u_adm else ("🚫 BANNED" if is_u_banned else "👤 Active Member")
                st.markdown(f"#### **{u_display}** (`@{u_key}`) &nbsp; <span style='font-size:0.8rem; background-color:rgba(255,255,255,0.08); padding:2px 8px; border-radius:4px;'>{badge}</span>", unsafe_allow_html=True)
                st.caption(f"📧 **Email:** `{u_email}` | 🏈 **Fav Team:** `{u_info.get('favorite_team', 'NFL')}` | 🗓️ **Joined:** `{u_info.get('created_at', 'N/A')}`")
            with r2:
                st.metric("Total Bets Placed", len(u_bets))

            with st.expander(f"🔍 View {u_display}'s Locked Tickets ({len(u_bets)})"):
                if not u_bets:
                    st.info("No tickets placed yet.")
                else:
                    for ub in u_bets:
                        st.markdown(f"• **{ub.get('date')}** — `{ub.get('matchup')}`: **{ub.get('bet')}** | Risk: ${ub.get('risk_dollars', 10):.2f} | Status: `{ub.get('status')}`")

            if u_key != "flurk":
                c_act1, c_act2, c_act3 = st.columns(3)
                with c_act1:
                    ban_label = "✅ Unban User" if is_u_banned else "🚫 Ban User"
                    if st.button(ban_label, key=f"ban_toggle_{u_key}", use_container_width=True):
                        u_info["is_banned"] = not is_u_banned
                        if u_info["is_banned"] and u_email not in banned_emails and "@" in u_email:
                            banned_emails.append(u_email)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, banned_emails)
                        st.rerun()

                with c_act2:
                    with st.popover("🔑 Reset Password"):
                        new_p_input = st.text_input("New Password", type="password", key=f"adm_p_{u_key}")
                        if st.button("Set New Password", key=f"adm_p_btn_{u_key}"):
                            if len(new_p_input) >= 4:
                                u_info["password_hash"] = hash_password(new_p_input)
                                save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, banned_emails)
                                st.success("Password updated!")
                            else:
                                st.error("Must be at least 4 chars.")

                with c_act3:
                    if st.button("🗑️ Delete Account", key=f"del_user_{u_key}", use_container_width=True):
                        users.pop(u_key)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, banned_emails)
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
    st.caption("Squad banter, threaded replies, reactions, and editable posts.")

    with st.form("send_msg_form", clear_on_submit=True):
        user_msg = st.text_input("Send a message", placeholder="Talk trash, call your shot, or share your angle...")
        send_btn = st.form_submit_button("Post Message", use_container_width=True)
        if send_btn and user_msg.strip():
            et_now = get_current_et_time()
            new_msg = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "time": et_now.strftime("%I:%M %p ET"),
                "text": user_msg.strip(),
                "reactions": {},
                "replies": []
            }
            st.session_state.chat_messages.insert(0, new_msg)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
            st.rerun()

    for m_idx, m in enumerate(list(st.session_state.chat_messages[:40])):
        m_id = m.get("id", str(m_idx))
        if "reactions" not in m:
            m["reactions"] = {}
        if "replies" not in m:
            m["replies"] = []

        is_author = (m.get("user", "").strip().lower() == current_user.strip().lower() or is_user_admin)

        with st.container(border=True):
            top_col1, top_col2 = st.columns([7, 3])
            with top_col1:
                st.markdown(f"**{m.get('user')}** &nbsp; <span style='opacity:0.55;font-size:0.8rem;'>{m.get('time')}</span>", unsafe_allow_html=True)
            with top_col2:
                if is_author:
                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("✏️ Edit", key=f"edit_trig_{m_id}", use_container_width=True):
                            st.session_state.editing_msg_id = m_id if st.session_state.editing_msg_id != m_id else None
                            st.rerun()
                    with btn_c2:
                        if st.button("🗑️ Del", key=f"del_msg_{m_id}", use_container_width=True):
                            st.session_state.chat_messages.pop(m_idx)
                            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                            st.rerun()

            if st.session_state.editing_msg_id == m_id:
                with st.form(f"inline_edit_form_{m_id}"):
                    edited_text = st.text_input("Edit message", value=m.get("text", ""))
                    e_btn1, e_btn2 = st.columns(2)
                    save_edit = e_btn1.form_submit_button("Save Changes")
                    cancel_edit = e_btn2.form_submit_button("Cancel")

                    if save_edit and edited_text.strip():
                        m["text"] = edited_text.strip()
                        if "edited" not in m.get("time", ""):
                            m["time"] = f"{m.get('time')} (edited)"
                        st.session_state.editing_msg_id = None
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                        st.rerun()
                    elif cancel_edit:
                        st.session_state.editing_msg_id = None
                        st.rerun()
            else:
                st.write(m.get("text"))

            if m["reactions"]:
                rx_badges = [f"{emoji} {count}" for emoji, count in m["reactions"].items() if count > 0]
                if rx_badges:
                    st.markdown(" ".join([f"<span style='background-color:rgba(255,255,255,0.08);padding:2px 8px;border-radius:12px;font-size:0.8rem;margin-right:4px;'>{b}</span>" for b in rx_badges]), unsafe_allow_html=True)

            col_rx, col_rep_btn = st.columns([6, 4], vertical_alignment="center")
            with col_rx:
                rx_cols = st.columns(5)
                emojis = ["🔥", "💀", "💰", "🏈", "🧢"]
                for e_idx, emoji in enumerate(emojis):
                    if rx_cols[e_idx].button(emoji, key=f"rx_{m_id}_{emoji}"):
                        m["reactions"][emoji] = m["reactions"].get(emoji, 0) + 1
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                        st.rerun()

            with st.expander(f"💬 Replies ({len(m['replies'])})", expanded=False):
                for rep in m["replies"]:
                    st.markdown(f"""
                    <div style="border-left: 2px solid rgba(255,255,255,0.2); padding-left: 8px; margin-bottom: 6px;">
                        <strong style="font-size:0.85rem;">{rep.get('user')}</strong> <span style="opacity:0.5;font-size:0.75rem;">({rep.get('time')})</span><br>
                        <span style="font-size:0.9rem;">{rep.get('text')}</span>
                    </div>
                    """, unsafe_allow_html=True)

                with st.form(f"reply_form_{m_id}", clear_on_submit=True):
                    rep_input = st.text_input("Reply to message", placeholder="Your reply...", key=f"rep_in_{m_id}")
                    post_rep = st.form_submit_button("Post Reply")
                    if post_rep and rep_input.strip():
                        et_now = get_current_et_time()
                        m["replies"].append({
                            "user": current_user.strip(),
                            "time": et_now.strftime("%I:%M %p ET"),
                            "text": rep_input.strip()
                        })
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                        st.rerun()

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

# 6. LOCKED BETS HISTORY (LIVE SCORES, LIVE PROBABILITY & MULTI-TEAM COMBOS)
elif menu_choice == "Locked Bets History":
    st.subheader(f"📜 {current_user}'s Locked Bets")
    st.caption("Active slips, live scoreboard updates, current win probabilities, and settled tickets.")

    curr_user_clean = current_user.strip().lower()
    
    col_filter1, col_filter2 = st.columns([3, 1])
    with col_filter2:
        show_all_history = st.toggle("Show All Squad Bets", value=False)
        
    if show_all_history:
        my_tickets = st.session_state.saved_bets
    else:
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
            is_combo = (b.get("bet_category") == "Combo" or "Leg" in b.get("type", ""))

            live_win_prob_str = b.get("win_prob", "50.0%")
            live_m = find_game_for_bet(b, games_data)

            game_has_started = False
            if live_m and not is_combo:
                chk = live_m.get("checkpoint", "")
                stt = live_m.get("status", "").lower()
                game_has_started = ("pre" not in chk.lower()) and ("pm" not in stt and "am" not in stt)
                is_fin = live_m.get("completed", False) or "final" in live_m["status"].lower()

                if is_fin:
                    live_win_prob_str = "100.0%" if status_val == "Won" else "0.0%"
                elif game_has_started:
                    curr_tot = live_m["away_score"] + live_m["home_score"]
                    t_line = b.get("target_line")
                    b_side = b.get("bet_direction", "Under")
                    b_cat = b.get("bet_category", "Total")

                    if b_cat in ["Total", "2H Total"] and t_line:
                        decay_sigma = 4.0 if live_m.get("period", 1) >= 3 else 6.5
                        p_live = calculate_win_prob(t_line, curr_tot + 14.0, decay_sigma, is_under=(b_side == "Under"))
                        live_win_prob_str = f"{p_live * 100:.1f}%"
                    elif b_cat == "Moneyline":
                        h_prob = calculate_moneyline_prob(live_m["home_score"] + 14, live_m["away_score"] + 14, live_m.get("home_record", "0-0"), live_m.get("away_record", "0-0"))
                        live_p = h_prob if b.get("picked_team") == live_m["home_team"] else (1.0 - h_prob)
                        live_win_prob_str = f"{live_p * 100:.1f}%"
                    elif b_cat == "Spread" and t_line:
                        diff = live_m["home_score"] - live_m["away_score"]
                        proj_diff = diff if b.get("picked_team") == live_m["home_team"] else -diff
                        sp_prob = calculate_spread_prob(proj_diff, t_line, std_dev=5.0)
                        live_win_prob_str = f"{sp_prob * 100:.1f}%"

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

            if is_combo:
                legs = b.get("parsed_legs", [])
                leg_count = len(legs) if legs else "Multi"
                title_html = f"🔗 <strong>{leg_count}-Leg Parlay Ticket</strong> &nbsp; <span style='opacity:0.6;font-size:0.85rem;'>by <strong>{b.get('user', 'Flurk')}</strong></span>"
            else:
                if live_m:
                    a_s = live_m.get("away_short", "AWAY")
                    h_s = live_m.get("home_short", "HOME")
                    a_pts = live_m.get("away_score", 0)
                    h_pts = live_m.get("home_score", 0)
                    clock = live_m.get("displayClock", "")
                    status_text = live_m.get("status", "")
                    score_badge = f"<span style='background-color:rgba(255,255,255,0.08);padding:3px 8px;border-radius:6px;font-weight:700;font-size:0.85rem;'>{a_s} {a_pts} - {h_pts} {h_s} ({clock or status_text})</span>"
                    title_html = f"""
                    <div style="display:flex; align-items:center; gap:8px;">
                        <img src="{live_m.get('away_logo', DEFAULT_LOGO)}" width="24" height="24" style="border-radius:50%;">
                        <strong>{a_s}</strong> <span style='opacity:0.4;'>@</span>
                        <img src="{live_m.get('home_logo', DEFAULT_LOGO)}" width="24" height="24" style="border-radius:50%;">
                        <strong>{h_s}</strong>
                        {score_badge}
                        <span style='opacity:0.6; font-size:0.82rem;'>by <strong>{b.get('user', 'Flurk')}</strong></span>
                    </div>
                    """
                else:
                    title_html = f"🏈 <strong>{b.get('matchup', 'Matchup')}</strong> &nbsp; <span style='opacity:0.6;font-size:0.85rem;'>by <strong>{b.get('user', 'Flurk')}</strong></span>"

            st.markdown(f"""
            <div style="{card_style} border-radius: 12px; padding: 12px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>{title_html}</div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="background-color:rgba(56,189,248,0.15); color:#38bdf8; font-weight:700; padding:2px 8px; border-radius:6px; font-size:0.75rem;">
                            🎲 Live Win Prob: {live_win_prob_str}
                        </span>
                        {badge_html}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.container():
                c_row1, c_row2, c_row3, c_row4 = st.columns([3.5, 3.5, 2.0, 1.0])
                
                with c_row1:
                    if is_combo:
                        st.write(f"**Multi-Game Parlay:** `{b.get('bet')}`")
                    else:
                        st.write(f"**Pick:** `{b.get('bet')}`")
                    st.caption(f"🗓️ Logged: `{b.get('date', 'N/A')}`")

                with c_row2:
                    r_val = float(b.get('risk_dollars', 10.0))
                    p_val = float(b.get('payout_dollars', 19.0))
                    roi_pct = ((p_val - r_val) / max(r_val, 0.01)) * 100
                    st.write(f"**Risk:** ${r_val:.2f} ➔ **Return:** ${p_val:.2f}")
                    st.markdown(f"<span class='clean-subtext' style='color:#4ade80;'>Potential Profit: +${p_val - r_val:.2f} (+{roi_pct:.1f}%)</span>", unsafe_allow_html=True)

                with c_row3:
                    cat_label = b.get("bet_category", b.get("type", "Single"))
                    st.caption(f"Type: **{cat_label}**")
                    if b.get("notes"):
                        st.caption(f"Notes: *{b.get('notes')}*")

                with c_row4:
                    if st.button("🗑️", key=f"del_slip_{b['id']}", help="Delete this ticket", use_container_width=True):
                        st.session_state.saved_bets.pop(real_idx)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
                        st.rerun()

                if is_combo:
                    with st.expander("📋 View All Teams, Live Scores & Leg Breakdown", expanded=True):
                        parsed = b.get("parsed_legs", [])
                        if parsed:
                            for leg_idx, leg in enumerate(parsed):
                                m_g = find_game_for_bet({"matchup": leg["matchup"]}, games_data)
                                if m_g:
                                    a_sh = m_g.get("away_short", "AWAY")
                                    h_sh = m_g.get("home_short", "HOME")
                                    a_sc = m_g.get("away_score", 0)
                                    h_sc = m_g.get("home_score", 0)
                                    t_sc = a_sc + h_sc
                                    fin = m_g.get("completed", False) or "final" in m_g.get("status", "").lower()
                                    is_started = ("pre" not in m_g.get("checkpoint", "").lower()) and ("pm" not in m_g.get("status", "").lower() and "am" not in m_g.get("status", "").lower())

                                    if fin:
                                        if leg.get("type") == "Total":
                                            won = (t_sc < leg["line"]) if leg.get("side") == "Under" else (t_sc > leg["line"])
                                        else:
                                            winner_team = m_g["home_team"] if h_sc > a_sc else m_g["away_team"]
                                            won = (leg.get("picked_team") == winner_team)
                                        leg_badge = "✅ WON" if won else "❌ LOST"
                                    elif is_started:
                                        leg_badge = f"⚡ LIVE ({a_sc} - {h_sc})"
                                    else:
                                        leg_badge = f"⏳ {m_g.get('kickoff', m_g.get('status', 'Pre-Game'))}"

                                    st.markdown(f"""
                                    <div style="display:flex; justify-content:space-between; align-items:center; background-color:rgba(255,255,255,0.03); padding:6px 10px; border-radius:6px; margin-bottom:4px;">
                                        <div style="display:flex; align-items:center; gap:8px;">
                                            <span style="font-size:0.8rem; opacity:0.5;">Leg {leg_idx+1}:</span>
                                            <img src="{m_g.get('away_logo', DEFAULT_LOGO)}" width="20" height="20" style="border-radius:50%;">
                                            <strong>{a_sh}</strong> @
                                            <img src="{m_g.get('home_logo', DEFAULT_LOGO)}" width="20" height="20" style="border-radius:50%;">
                                            <strong>{h_sh}</strong>
                                            <span style="opacity:0.4;">|</span>
                                            <strong style="color:#38bdf8;">{leg.get('side', '')} {leg.get('line', '')} {leg.get('picked_team', '')}</strong>
                                        </div>
                                        <div>
                                            <span style="font-weight:700; font-size:0.80rem;">{leg_badge}</span>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.write(f"Matchups: `{b.get('matchup')}`")

            st.markdown("<hr style='margin: 8px 0 16px 0; opacity: 0.15;'>", unsafe_allow_html=True)

# 7. HOW IT WORKS
elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: The Flurkstradamus User Guide")
    st.caption("Mastering the Edge Engine, Combo Builder, and Squad Tracker.")

    with st.container(border=True):
        st.markdown("### ⚡ 1. Single Game Engine & AI Strategy Builder")
        st.write("The Single Game Engine connects live to ESPN scoreboard endpoints to track games in real-time.")
        st.markdown("""
        * **Live Line Drift Tracking:** Compares opening sportsbook lines against real-time scoring to compute live totals, 2H totals, and ATS margins.
        * **The Risk vs. Return Dial:** Adjust the slider to set your model objective from Safe Floor up to High Profit. Lines and Win Probabilities recalibrate dynamically.
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
        * **Live Scores & Probabilities:** Live scoreboard statuses and updated win probabilities track automatically on the Locked Bets page.
        * **Leaderboard Standings:** Ranks bettors by total net profit and win rate.
        """)

# 8. MODEL METHODOLOGY & MATH BREAKDOWN
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

    if st.session_state.combo_active_legs and games_data:
        for leg in st.session_state.combo_active_legs:
            if leg.get("matchup_idx", 0) >= len(games_data):
                leg["matchup_idx"] = 0

    if not st.session_state.combo_active_legs and games_data:
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

        active_candidate_games = [gm for gm in games_data if not gm.get("completed", False)]
        if not active_candidate_games:
            active_candidate_games = games_data
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

            st.session_state.ai_recommended_combo = selected_ai_legs
            st.session_state.editing_ai_combo = False

        if st.session_state.ai_recommended_combo and games_data:
            valid_legs = [l for l in st.session_state.ai_recommended_combo if 0 <= l.get("matchup_idx", -1) < len(games_data)]
            st.session_state.ai_recommended_combo = valid_legs

        if st.session_state.ai_recommended_combo:
            num_legs_rec = len(st.session_state.ai_recommended_combo)
            comp_p = 1.0
            for l_item in st.session_state.ai_recommended_combo:
                comp_p *= l_item["prob"]

            t_col1, t_col2 = st.columns([8.5, 1.5], vertical_alignment="center")
            with t_col1:
                st.markdown(f"#### 🎯 Recommended Ticket ({num_legs_rec} Legs):")
            with t_col2:
                st.markdown('<div class="edit-link-btn">', unsafe_allow_html=True)
                toggle_label = "Done" if st.session_state.editing_ai_combo else "Edit"
                if st.button(toggle_label, key="toggle_edit_ai"):
                    st.session_state.editing_ai_combo = not st.session_state.editing_ai_combo
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            if st.session_state.editing_ai_combo:
                with st.container(border=True):
                    leg_options = [
                        f"Leg {k+1}: {item['desc']} ({games_data[min(item['matchup_idx'], len(games_data)-1)]['away_short']}@{games_data[min(item['matchup_idx'], len(games_data)-1)]['home_short']})"
                        for k, item in enumerate(st.session_state.ai_recommended_combo)
                    ]
                    selected_leg_idx = st.radio(
                        "Select a leg to remove:",
                        options=range(len(leg_options)),
                        format_func=lambda x: leg_options[x],
                        label_visibility="collapsed"
                    )
                    r_c1, r_c2 = st.columns([2, 1], vertical_alignment="center")
                    with r_c1:
                        if st.button("🗑️ Remove Selected Leg", use_container_width=True):
                            st.session_state.ai_recommended_combo.pop(selected_leg_idx)
                            if not st.session_state.ai_recommended_combo:
                                st.session_state.editing_ai_combo = False
                            st.rerun()
                    with r_c2:
                        if st.button("Done Editing", use_container_width=True):
                            st.session_state.editing_ai_combo = False
                            st.rerun()

            for idx_ai, l_ai in enumerate(st.session_state.ai_recommended_combo):
                m_idx = min(max(l_ai.get("matchup_idx", 0), 0), len(games_data) - 1)
                g_match = games_data[m_idx]
                detail_str = l_ai.get("detail", "")

                st.markdown(f"""
                <div class="rec-single-line-card">
                    <div class="rec-left-wrap">
                        <span style="background-color: #22c55e; color: #000; font-weight: 800; font-size: 0.75rem; padding: 2px 7px; border-radius: 4px;">
                            LEG {idx_ai+1}
                        </span>
                        <img src="{g_match['away_logo']}" width="22" height="22" style="border-radius: 50%;">
                        <strong style="font-size: 0.92rem;">{g_match['away_short']}</strong>
                        <span style="opacity: 0.4; font-size: 0.90rem;">@</span>
                        <img src="{g_match['home_logo']}" width="22" height="22" style="border-radius: 50%;">
                        <strong style="font-size: 0.92rem;">{g_match['home_short']}</strong>
                        <span style="opacity: 0.55; font-size: 0.80rem;">({g_match.get('kickoff', g_match['status'])})</span>
                    </div>
                    <div class="rec-right-wrap">
                        <strong style="color: #4ade80; font-size: 0.92rem;">{l_ai['desc']}</strong>
                        <span style="opacity: 0.6; font-size: 0.80rem;">({detail_str})</span>
                        <span style="background-color: rgba(255, 255, 255, 0.08); padding: 2px 8px; border-radius: 4px; font-size: 0.80rem; font-weight: 600;">
                            {l_ai['prob']*100:.1f}%
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            m_rec1, m_rec2 = st.columns([2, 1], vertical_alignment="center")
            m_rec1.metric("Compound Recommended Win Expectancy", f"{comp_p * 100:.1f}%", delta=f"{len(st.session_state.ai_recommended_combo)} Legs Total")

            if m_rec2.button("📥 Apply Recommended Picks into Combo Builder", use_container_width=True):
                st.session_state.combo_version += 1
                st.session_state.combo_active_legs = [
                    {
                        "matchup_idx": min(l_item["matchup_idx"], len(games_data)-1),
                        "type": l_item["type"],
                        "side": l_item.get("side", "Under"),
                        "line": float(l_item.get("line", 47.5)),
                        "picked_team": l_item.get("picked_team", games_data[min(l_item["matchup_idx"], len(games_data)-1)]["home_team"])
                    }
                    for l_item in st.session_state.ai_recommended_combo
                ]
                st.rerun()

    # SLIP BUILDER CONTROLS
    ver = st.session_state.combo_version
    ctrl_c1, ctrl_c2 = st.columns([3, 1], vertical_alignment="center")
    with ctrl_c1:
        st.markdown(f"#### Active Slip ({len(st.session_state.combo_active_legs)} Legs)")
    with ctrl_c2:
        if st.button("➕ Add Leg", use_container_width=True, disabled=(len(st.session_state.combo_active_legs) >= 12 or not games_data)):
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
    compound_prob = 1.0

    for i, leg_data in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            safe_m_idx = min(max(leg_data.get("matchup_idx", 0), 0), len(game_choices) - 1) if game_choices else 0
            sel_matchup = st.selectbox(
                f"Leg {i+1} Matchup",
                range(len(game_choices)),
                index=safe_m_idx,
                format_func=lambda x: game_choices[x],
                key=f"m_sel_{i}_v{ver}"
            )
            leg_data["matchup_idx"] = sel_matchup

            leg_g = games_data[sel_matchup]
            d_h, d_a = leg_g["home_team"], leg_g["away_team"]
            d_h_abbr, d_a_abbr = leg_g["home_short"], leg_g["away_short"]
            d_kickoff = leg_g.get("kickoff", leg_g["status"])
            d_h_pts, d_a_pts = leg_g["home_score"], leg_g["away_score"]
            d_h_rec, d_a_rec = leg_g.get("home_record", "0-0"), leg_g.get("away_record", "0-0")
            leg_completed = leg_g["completed"]

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
                key=f"wtype_{i}_v{ver}"
            )
            leg_data["type"] = wager_cat

            if wager_cat == "Game Total":
                col_b, col_c = st.columns(2)
                side = col_b.selectbox("Side", ["Under", "Over"], index=0 if leg_data.get("side", "Under") == "Under" else 1, key=f"lside_{i}_v{ver}")
                strike = col_c.number_input("Line (pts)", value=float(leg_data.get("line", leg_g.get("market_ou", 44.5))), step=0.5, key=f"lstrike_{i}_v{ver}")
                leg_data["side"] = side
                leg_data["line"] = strike

                leg_prob = calculate_win_prob(strike, 42.0, 7.0, is_under=(side == "Under"))
                leg_desc = f"{d_a_abbr} @ {d_h_abbr}: {side} {strike}"
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
                    key=f"lwinner_{i}_v{ver}"
                )
                leg_data["picked_team"] = winner

                win_abbr = d_h_abbr if winner == d_h else d_a_abbr
                h_prob = calculate_moneyline_prob(d_h_pts + 15, d_a_pts + 15, d_h_rec, d_a_rec, is_final=leg_completed)
                leg_prob = h_prob if winner == d_h else (1.0 - h_prob)
                leg_desc = f"{d_a_abbr} @ {d_h_abbr}: {win_abbr} ML"
                col_c.metric("Model Win %", f"{leg_prob * 100:.1f}%")

            compound_prob *= leg_prob
            combo_legs.append({"desc": leg_desc, "prob": leg_prob})

    with st.container(border=True):
        st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        c_r1, c_r2 = st.columns(2)
        c_risk = c_r1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        c_payout = c_r2.number_input("Payout ($)", min_value=1.0, value=50.0, step=10.0)
        save_c_btn = st.form_submit_button(f"Lock In {len(combo_legs)}-Leg Ticket", use_container_width=True)
        if save_c_btn:
            legs_str = " | ".join([cl["desc"] for cl in combo_legs])
            
            parsed_legs = []
            for item in st.session_state.combo_active_legs:
                s_idx = min(item["matchup_idx"], len(games_data) - 1)
                mg = games_data[s_idx]
                parsed_legs.append({
                    "matchup": f"{mg['away_short']} @ {mg['home_short']}",
                    "type": item["type"],
                    "side": item.get("side", ""),
                    "line": item.get("line", ""),
                    "picked_team": item.get("picked_team", "")
                })

            combo_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                "type": f"{len(combo_legs)}-Leg Combo",
                "bet_category": "Combo",
                "matchup": legs_str,
                "bet": f"{len(combo_legs)} Legs ({compound_prob * 100:.1f}% Prob)",
                "target_line": None,
                "bet_direction": None,
                "risk_dollars": float(c_risk),
                "payout_dollars": float(c_payout),
                "win_prob": f"{compound_prob * 100:.1f}%",
                "status": "Pending",
                "parsed_legs": parsed_legs,
                "notes": f"{len(combo_legs)}-Leg Parlay"
            }
            st.session_state.saved_bets.insert(0, combo_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
            st.success(f"{len(combo_legs)}-Leg combo ticket locked in!")

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

    # =========================================================================
    # TIERED STRATEGY ENGINE WITH FULL FILTER & OBJECTIVE RECALIBRATION
    # =========================================================================
    with st.expander("🤖 AI Strategy Engine (Adjustable Risk vs. Return Scale)", expanded=True):
        col_scope, col_type_filter = st.columns(2)
        scope_choice = col_scope.selectbox("Target Slate", ["🎯 Focus on Selected Game Above", "⚡ Scan Full Slate for Highest Discrepancy"])
        filter_choice = col_type_filter.selectbox("Type of Bet", [
            "⚡ Let the System Pick (All Markets Combined)", 
            "📊 Full Game Total Score Over/Under", 
            "⏱️ 2nd Half Total Points", 
            "🏆 Team Win/Loser (Moneyline)", 
            "🛡️ Spread (ATS Cover)"
        ])
        
        strategy_dial = st.select_slider(
            "Model Objective", 
            options=[
                "🛡️ Safe Floor (High Win %, Low Drawdown)", 
                "⚖️ Balanced Edge (+EV Sweet Spot)", 
                "🚀 High Profit (Max Multiplier & Value Underdogs)"
            ], 
            value="⚖️ Balanced Edge (+EV Sweet Spot)"
        )

        active_game_for_strat = g
        strat_game_index = st.session_state.single_selected_idx
        if "Scan Full Slate" in scope_choice and games_data:
            live_pool = [gm for gm in games_data if not gm.get("completed", False)]
            if live_pool:
                active_game_for_strat = max(live_pool, key=lambda x: abs((x["home_score"] + x["away_score"] + (x.get("market_ou", 47.5)*0.475)) - x.get("market_ou", 47.5)))
                strat_game_index = games_data.index(active_game_for_strat)

        tg_away_logo = active_game_for_strat.get("away_logo", DEFAULT_LOGO)
        tg_home_logo = active_game_for_strat.get("home_logo", DEFAULT_LOGO)
        tg_away_short = active_game_for_strat.get("away_short", "AWAY")
        tg_home_short = active_game_for_strat.get("home_short", "HOME")
        tg_date_str = active_game_for_strat.get("kickoff", active_game_for_strat.get("status", "Pre-Game"))

        # Baseline spread metrics
        s_val = market_spd if home_cover_exp >= 0.5 else -market_spd
        s_team = active_game_for_strat["home_team"] if home_cover_exp >= 0.5 else active_game_for_strat["away_team"]
        s_abbr = tg_home_short if home_cover_exp >= 0.5 else tg_away_short

        # Dynamic Calibration Factors based on Model Objective dial
        if "Safe Floor" in strategy_dial:
            obj_tag = "Safe Floor"
            p_multiplier_spread = 1.55
            p_multiplier_total = 1.55
            p_multiplier_2h = 1.55
            spd_shift = 3.5 if s_val > 0 else 4.0
            tot_shift = 4.5
            second_shift = 3.5
        elif "High Profit" in strategy_dial:
            obj_tag = "High Profit"
            p_multiplier_spread = 2.45
            p_multiplier_total = 2.40
            p_multiplier_2h = 2.45
            spd_shift = -3.5 if s_val > 0 else -4.0
            tot_shift = -3.5
            second_shift = -3.5
        else: # Balanced Edge (+EV)
            obj_tag = "Balanced Edge"
            p_multiplier_spread = 1.91
            p_multiplier_total = 1.91
            p_multiplier_2h = 1.91
            spd_shift = 0.0
            tot_shift = 0.0
            second_shift = 0.0

        # SPREAD RECALIBRATION
        line_spd_1 = s_val + spd_shift
        p_spd_1 = calculate_spread_prob(live_proj_margin if s_team == active_game_for_strat["home_team"] else -live_proj_margin, line_spd_1, std_bracket)
        line_spd_2 = s_val + (spd_shift + 1.5)
        p_spd_2 = calculate_spread_prob(live_proj_margin if s_team == active_game_for_strat["home_team"] else -live_proj_margin, line_spd_2, std_bracket)
        line_spd_3 = s_val + (spd_shift - 1.5)
        p_spd_3 = calculate_spread_prob(live_proj_margin if s_team == active_game_for_strat["home_team"] else -live_proj_margin, line_spd_3, std_bracket)

        spread_bets = [
            {
                "type": f"Spread ({obj_tag} Consensus)",
                "pick": f"{s_abbr} {line_spd_1:+}",
                "prob": p_spd_1,
                "category": "Spread",
                "side": "Spread",
                "target_line": line_spd_1,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_multiplier_spread,
                "roi_label": f"+{int((p_multiplier_spread-1)*100)}% Profit",
                "drift_info": f"Expected Margin: {spread_drift:+.1f} pts vs line",
                "rationale": f"Calibrated for {obj_tag} expectancy."
            },
            {
                "type": f"Spread ({obj_tag} Alternate Buffer)",
                "pick": f"{s_abbr} {line_spd_2:+}",
                "prob": p_spd_2,
                "category": "Spread",
                "side": "Spread",
                "target_line": line_spd_2,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": round(max(p_multiplier_spread - 0.20, 1.40), 2),
                "roi_label": f"+{int((max(p_multiplier_spread - 0.20, 1.40)-1)*100)}% Profit",
                "drift_info": "Additional buffer bought on alternate spread",
                "rationale": f"High protection cushion on {s_abbr}."
            },
            {
                "type": f"Spread ({obj_tag} Aggressive Target)",
                "pick": f"{s_abbr} {line_spd_3:+}",
                "prob": p_spd_3,
                "category": "Spread",
                "side": "Spread",
                "target_line": line_spd_3,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": round(p_multiplier_spread + 0.35, 2),
                "roi_label": f"+{int(((p_multiplier_spread + 0.35)-1)*100)}% Profit",
                "drift_info": "Accelerated cover target",
                "rationale": f"Enhanced payout margin play on {s_abbr}."
            }
        ]

        # FULL GAME TOTAL RECALIBRATION
        tot_dir = "Under" if delta_full <= 0 else "Over"
        base_tot_1 = round(final_proj + tot_shift) + 0.5
        p_tot_1 = calculate_win_prob(base_tot_1, final_proj, std_bracket, is_under=(tot_dir == "Under"))
        base_tot_2 = base_tot_1 + 2.5
        p_tot_2 = calculate_win_prob(base_tot_2, final_proj, std_bracket, is_under=(tot_dir == "Under"))
        base_tot_3 = base_tot_1 - 2.5
        p_tot_3 = calculate_win_prob(base_tot_3, final_proj, std_bracket, is_under=(tot_dir == "Under"))

        full_totals_bets = [
            {
                "type": f"Full Game Total ({obj_tag} {tot_dir})",
                "pick": f"{tot_dir} {base_tot_1}",
                "prob": p_tot_1,
                "category": "Total",
                "side": tot_dir,
                "target_line": base_tot_1,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_multiplier_total,
                "roi_label": f"+{int((p_multiplier_total-1)*100)}% Profit",
                "drift_info": f"Model Proj: {final_proj:.1f} pts ({delta_full:+.1f} pace shift)",
                "rationale": f"Recalibrated for {obj_tag} pacing."
            },
            {
                "type": f"Full Game Total ({obj_tag} Alternate Line)",
                "pick": f"{tot_dir} {base_tot_2}",
                "prob": p_tot_2,
                "category": "Total",
                "side": tot_dir,
                "target_line": base_tot_2,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": round(max(p_multiplier_total - 0.20, 1.40), 2) if tot_dir == "Under" else round(p_multiplier_total + 0.35, 2),
                "roi_label": f"+{int((max(p_multiplier_total - 0.20, 1.40)-1)*100)}% Profit",
                "drift_info": "Alternate total boundary threshold",
                "rationale": f"Targeting adjusted probability cushion."
            },
            {
                "type": f"Full Game Total ({obj_tag} Aggressive Threshold)",
                "pick": f"{tot_dir} {base_tot_3}",
                "prob": p_tot_3,
                "category": "Total",
                "side": tot_dir,
                "target_line": base_tot_3,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": round(p_multiplier_total + 0.35, 2) if tot_dir == "Under" else round(max(p_multiplier_total - 0.20, 1.40), 2),
                "roi_label": f"+{int(((p_multiplier_total + 0.35)-1)*100)}% Profit",
                "drift_info": "Max multiplier volume threshold",
                "rationale": "High value undercut on scoring volatility."
            }
        ]

        # 2ND HALF TOTAL RECALIBRATION
        line_2h_1 = round(live_2h_proj + second_shift) + 0.5
        p_2h_1 = calculate_win_prob(line_2h_1, live_2h_proj, 5.0, is_under=True)
        line_2h_2 = line_2h_1 + 2.0
        p_2h_2 = calculate_win_prob(line_2h_2, live_2h_proj, 5.0, is_under=True)
        line_2h_3 = line_2h_1 - 2.0
        p_2h_3 = calculate_win_prob(line_2h_3, live_2h_proj, 5.0, is_under=True)

        second_half_bets = [
            {
                "type": f"2nd Half Total ({obj_tag} Consensus)",
                "pick": f"2H Under {line_2h_1}",
                "prob": p_2h_1,
                "category": "2H Total",
                "side": "Under",
                "target_line": line_2h_1,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_multiplier_2h,
                "roi_label": f"+{int((p_multiplier_2h-1)*100)}% Profit",
                "drift_info": f"2H Proj: {live_2h_proj:.1f} pts ({delta_2h:+.1f} shift)",
                "rationale": f"Calculated 2H regression for {obj_tag}."
            },
            {
                "type": f"2nd Half Total ({obj_tag} Cushion)",
                "pick": f"2H Under {line_2h_2}",
                "prob": p_2h_2,
                "category": "2H Total",
                "side": "Under",
                "target_line": line_2h_2,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": round(max(p_multiplier_2h - 0.20, 1.40), 2),
                "roi_label": f"+{int((max(p_multiplier_2h - 0.20, 1.40)-1)*100)}% Profit",
                "drift_info": "+2.0 pts additional safety cushion",
                "rationale": "High win expectancy with expanded 2H buffer."
            },
            {
                "type": f"2nd Half Total ({obj_tag} Aggressive)",
                "pick": f"2H Under {line_2h_3}",
                "prob": p_2h_3,
                "category": "2H Total",
                "side": "Under",
                "target_line": line_2h_3,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": round(p_multiplier_2h + 0.35, 2),
                "roi_label": f"+{int(((p_multiplier_2h + 0.35)-1)*100)}% Profit",
                "drift_info": "Aggressive clock bleed undercut",
                "rationale": "Plus-money return on fast running clocks."
            }
        ]

        # MONEYLINE RECALIBRATION
        fav_team = active_game_for_strat["home_team"] if live_h_prob >= 0.5 else active_game_for_strat["away_team"]
        fav_abbr = tg_home_short if live_h_prob >= 0.5 else tg_away_short
        dog_team = active_game_for_strat["away_team"] if live_h_prob >= 0.5 else active_game_for_strat["home_team"]
        dog_abbr = tg_away_short if live_h_prob >= 0.5 else tg_home_short

        if "Safe Floor" in strategy_dial:
            ml_p_main = max(live_h_prob, live_a_prob)
            ml_p_sub = min(ml_p_main + 0.08, 0.95)
            ml_p_alt = min(ml_p_main + 0.04, 0.92)
            ml_mult = 1.45
            ml_pick_primary = f"{fav_abbr} ML"
            ml_team_primary = fav_team
        elif "High Profit" in strategy_dial:
            ml_p_main = min(live_h_prob, live_a_prob)
            ml_p_sub = max(ml_p_main - 0.05, 0.38)
            ml_p_alt = min(ml_p_main + 0.04, 0.49)
            ml_mult = 2.65
            ml_pick_primary = f"{dog_abbr} ML"
            ml_team_primary = dog_team
        else:
            ml_p_main = max(live_h_prob, live_a_prob)
            ml_p_sub = min(live_h_prob, live_a_prob)
            ml_p_alt = max(live_h_prob, live_a_prob)
            ml_mult = 1.74
            ml_pick_primary = f"{fav_abbr} ML"
            ml_team_primary = fav_team

        moneyline_bets = [
            {
                "type": f"Moneyline ({obj_tag} Selection)",
                "pick": ml_pick_primary,
                "prob": ml_p_main,
                "category": "Moneyline",
                "side": "Moneyline",
                "target_line": None,
                "picked_team": ml_team_primary,
                "game_index": strat_game_index,
                "est_payout_multiplier": ml_mult,
                "roi_label": f"+{int((ml_mult-1)*100)}% Profit",
                "drift_info": f"Model Win Expectancy: {ml_p_main*100:.1f}%",
                "rationale": f"Optimized outright straight-up play for {obj_tag}."
            },
            {
                "type": f"Moneyline ({obj_tag} High Value Alternate)",
                "pick": f"{fav_abbr} ML",
                "prob": ml_p_alt,
                "category": "Moneyline",
                "side": "Moneyline",
                "target_line": None,
                "picked_team": fav_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": 1.62,
                "roi_label": "+62% Profit",
                "drift_info": f"Favored Win Probability: {ml_p_alt*100:.1f}%",
                "rationale": f"High consistency winner on {fav_abbr} without laying point spreads."
            },
            {
                "type": f"Moneyline ({obj_tag} Value Underdog)",
                "pick": f"{dog_abbr} ML",
                "prob": ml_p_sub,
                "category": "Moneyline",
                "side": "Moneyline",
                "target_line": None,
                "picked_team": dog_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": 2.50,
                "roi_label": "+150% Profit (2.5x)",
                "drift_info": f"Upset Win Probability: {ml_p_sub*100:.1f}%",
                "rationale": f"High return position on {dog_abbr} in close game scripts."
            }
        ]

        # Route matching candidates strictly to selected Type of Bet
        if filter_choice == "📊 Full Game Total Score Over/Under":
            strat_candidates = full_totals_bets
        elif filter_choice == "⏱️ 2nd Half Total Points":
            strat_candidates = second_half_bets
        elif filter_choice == "🏆 Team Win/Loser (Moneyline)":
            strat_candidates = moneyline_bets
        elif filter_choice == "🛡️ Spread (ATS Cover)":
            strat_candidates = spread_bets
        else:
            # Combined / Let the System Pick: Best from each category
            strat_candidates = [spread_bets[0], full_totals_bets[0], second_half_bets[0], moneyline_bets[0]]

        # Tier sorting ensures that Top Card has the absolute strongest matching score
        if "Safe Floor" in strategy_dial:
            strat_candidates.sort(key=lambda x: x["prob"], reverse=True)
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
        <div style="display: flex; align-items: center; justify-content: space-between; background-color: rgba(255, 255, 255, 0.04); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px; border: 1px solid rgba(255, 255, 255, 0.1);">
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
            
            # Save the true calibrated probability directly on the ticket
            ticket_prob_str = f"{applied['prob']*100:.1f}%" if applied and "prob" in applied else f"{home_cover_exp*100:.1f}%"

            ticket_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
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
                "win_prob": ticket_prob_str,
                "status": "Pending",
                "notes": ticket_notes
            }
            st.session_state.saved_bets.insert(0, ticket_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails)
            st.session_state.single_applied_pick = None
            st.success("Ticket saved to history!")
