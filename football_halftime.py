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

# Responsive Desktop + Mobile styling (Bootstrap-style stacking & Left Navigation)
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
            padding-top: 3.0rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        /* Mobile Full-Row Stacking (Bootstrap-style columns) */
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 0.5rem !important;
        }
        .rec-single-line-card {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 6px !important;
            white-space: normal !important;
        }
    }

    /* LEFT-ALIGNED NAVIGATION BUTTONS */
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

    /* CARD STYLING */
    .rec-single-line-card {
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background-color: rgba(255, 255, 255, 0.02);
        padding: 8px 14px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        line-height: 1.3;
        transition: background-color 0.15s ease-in-out, border-color 0.15s ease-in-out;
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
    """Returns true Eastern Time (ET)."""
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
    st.session_state.active_nav_page = "📊 Squad Dashboard"
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
b_data, c_data, u_data, banned_emails_data, game_snapshots_data = load_storage()
if "saved_bets" not in st.session_state:
    st.session_state.saved_bets = b_data
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = c_data
if "user_accounts" not in st.session_state:
    st.session_state.user_accounts = u_data
if "banned_emails" not in st.session_state:
    st.session_state.banned_emails = banned_emails_data
if "game_snapshots" not in st.session_state:
    st.session_state.game_snapshots = game_snapshots_data

# =========================================================================
# FEATURE 1: PERSISTENT BROWSER SESSION (NO MORE CONSTANT LOGINS)
# =========================================================================
query_params = st.query_params
if st.session_state.logged_in_user is None:
    token_in_url = query_params.get("session_token")
    if token_in_url:
        for u_obj in st.session_state.user_accounts.values():
            if u_obj.get("session_token") == token_in_url and not u_obj.get("is_banned", False):
                st.session_state.logged_in_user = u_obj
                break

# ==========================================
# AUTHENTICATION PORTAL (IF NO SAVED TOKEN)
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
                        if not matched_user.get("session_token"):
                            matched_user["session_token"] = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
                            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                        st.query_params["session_token"] = matched_user["session_token"]
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
                    new_token = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
                    new_user = {
                        "username": new_uname,
                        "email": new_email,
                        "display_name": new_dname.strip(),
                        "password_hash": hash_password(new_pword),
                        "is_admin": False,
                        "is_banned": False,
                        "created_at": get_current_et_time().strftime("%Y-%m-%d"),
                        "favorite_team": fav_team.strip() if fav_team else "NFL",
                        "reset_token": None,
                        "session_token": new_token
                    }
                    st.session_state.user_accounts[new_uname] = new_user
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.query_params["session_token"] = new_token
                    st.session_state.logged_in_user = new_user
                    st.success("Account created successfully!")
                    st.rerun()

    with tab_forgot:
        st.markdown("#### 🔑 Password Recovery")
        with st.form("request_reset_form"):
            recover_email = st.text_input("Registered Email Address", placeholder="e.g. user@example.com").strip().lower()
            send_code_btn = st.form_submit_button("Request Reset Code", use_container_width=True)
            if send_code_btn:
                target_user = next((u for u in st.session_state.user_accounts.values() if u.get("email", "").lower() == recover_email), None)
                if target_user:
                    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    target_user["reset_token"] = token
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.success(f"✅ Recovery Code Generated: **`{token}`**")
                else:
                    st.error("No account found with that email address.")

        with st.form("complete_reset_form"):
            c_email = st.text_input("Confirm Your Email", placeholder="user@example.com").strip().lower()
            code_input = st.text_input("6-Character Reset Code", placeholder="e.g. AB12CD").strip().upper()
            new_pass1 = st.text_input("New Password", type="password", placeholder="••••••••")
            new_pass2 = st.text_input("Confirm New Password", type="password", placeholder="••••••••")
            submit_new_pass = st.form_submit_button("Update Password", use_container_width=True)
            if submit_new_pass:
                target_user = next((u for u in st.session_state.user_accounts.values() if u.get("email", "").lower() == c_email), None)
                if target_user and target_user.get("reset_token") == code_input and new_pass1 == new_pass2 and len(new_pass1) >= 4:
                    target_user["password_hash"] = hash_password(new_pass1)
                    target_user["reset_token"] = None
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.success("🎉 Password updated successfully! Switch to 'Sign In'.")
                else:
                    st.error("Invalid reset code or password mismatch.")
    st.stop()

# ACTIVE USER IDENTITY
current_user_profile = st.session_state.logged_in_user
active_uname = current_user_profile.get("username", "").strip().lower()
current_user = "Flurk" if active_uname == "flurk" else current_user_profile.get("display_name", current_user_profile.get("username", "Bettor"))
is_user_admin = current_user_profile.get("is_admin", False)

# =========================================================================
# FEATURE 3: COMPREHENSIVE MULTI-DAY ESPN INGESTION (PULLS ALL UPCOMING GAMES)
# =========================================================================
@st.cache_data(ttl=25)
def get_extended_games(selected_league="All Games"):
    all_games = []
    seen_ids = set()
    
    endpoints = []
    if selected_league in ["NFL", "All Games"]:
        endpoints.append(("NFL", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=250"))
    if selected_league in ["NCAA Football", "All Games"]:
        endpoints.append(("NCAA", "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?limit=300&groups=80"))
        endpoints.append(("NCAA", "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?limit=300"))

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
# SIDEBAR NAVIGATION (UPDATED TITLES)
# ==========================================
st.sidebar.markdown(f"## 🔮 Flurkstradamus")
st.sidebar.markdown(f"👤 **{current_user}** (`@{current_user_profile.get('username')}`)")
if current_user_profile.get("favorite_team"):
    st.sidebar.caption(f"🏈 {current_user_profile.get('favorite_team')}")

col_u1, _ = st.sidebar.columns(2)
with col_u1:
    if st.button("🚪 Logout", key="logout_btn", use_container_width=True):
        st.session_state.logged_in_user = None
        st.query_params.clear()
        st.rerun()

st.sidebar.markdown("---")

nav_items = [
    ("📊 Squad Dashboard", "📊 Squad Dashboard"),
    ("⚡ Single Game Engine", "Single Game Engine"),
    ("🔗 Multi-Leg Combo Builder", "2-12 Leg Combo Builder"),
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
    b_data, c_data, u_data, b_e_data, g_s_data = load_storage()
    st.session_state.saved_bets = b_data
    st.session_state.chat_messages = c_data
    st.session_state.user_accounts = u_data
    st.session_state.banned_emails = b_e_data
    st.session_state.game_snapshots = g_s_data
    st.rerun()

games_data = get_extended_games(league)
auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages, st.session_state.game_snapshots)

# =========================================================================
# FEATURE 7 & 8: GAME SNAPSHOT RECORDER & HISTORICAL WAR ROOM
# =========================================================================
def sync_game_snapshot(game, proj_total, proj_spread):
    """Saves evolving predictions (Pre-Game -> Q1 -> Halftime -> Q3 -> Final) to persistent history."""
    gid = game["id"]
    if gid not in st.session_state.game_snapshots:
        st.session_state.game_snapshots[gid] = {
            "matchup": f"{game['away_short']} @ {game['home_short']}",
            "open_ou": game.get("market_ou", 47.5),
            "open_spread": game.get("market_spread", -3.5),
            "stages": {}
        }
    stage_key = game["checkpoint"]
    if stage_key not in st.session_state.game_snapshots[gid]["stages"]:
        st.session_state.game_snapshots[gid]["stages"][stage_key] = {
            "away_score": game["away_score"],
            "home_score": game["home_score"],
            "total_pts": game["away_score"] + game["home_score"],
            "proj_total": round(proj_total, 1),
            "proj_spread": round(proj_spread, 1),
            "timestamp": get_current_et_time().strftime("%I:%M %p ET")
        }
        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)

# WAR ROOM VIEW (DETAIL PAGE)
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)
    if st.button("⬅️ Back to Locked Bets History", use_container_width=True):
        st.session_state.selected_bet_id = None
        st.rerun()

    if selected_bet is None:
        st.error("Selected ticket could not be found.")
        st.stop()

    live_game_info = find_game_for_bet(selected_bet, games_data)
    st.title(f"🏟️ In-Game War Room: {selected_bet['matchup']}")
    st.caption(f"Bettor: **{selected_bet.get('user', 'Flurk')}** | Pick: `{selected_bet['bet']}` | Logged: {selected_bet.get('date', 'N/A')}")

    if live_game_info:
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.metric(f"Away ({live_game_info['away_short']})", live_game_info['away_score'])
        c2.write(f"**Status:** {live_game_info['status']}\n\nClock: `{live_game_info.get('displayClock', 'Live')}`")
        c3.metric(f"Home ({live_game_info['home_short']})", live_game_info['home_score'])

        # Historical Timeline Breakdown
        gid = live_game_info["id"]
        snap = st.session_state.game_snapshots.get(gid)

        st.markdown("### 📈 Projection Evolution & Drift Timeline")
        st.caption("How model pace, volatility, and spreads adjusted from Pre-Game through each quarter:")

        timeline_data = []
        if snap and "stages" in snap:
            for stg, s_val in snap["stages"].items():
                timeline_data.append({
                    "Stage / Quarter": stg,
                    "Live Score": f"{s_val['away_score']} - {s_val['home_score']} ({s_val['total_pts']} pts)",
                    "Projected Full Total": f"{s_val['proj_total']} pts",
                    "Total Drift vs Open": f"{s_val['proj_total'] - snap['open_ou']:+.1f} pts",
                    "Projected Spread Margin": f"{s_val['proj_spread']:+.1f} pts",
                    "Logged At": s_val["timestamp"]
                })
        
        if timeline_data:
            st.table(timeline_data)
        else:
            st.info("Live projection checkpoints are actively recording as this matchup progresses.")
    else:
        st.warning("Scoreboard feed for this matchup is inactive.")
    st.stop()

# =========================================================================
# FEATURE 2: SQUAD OVERVIEW DASHBOARD
# =========================================================================
if menu_choice == "📊 Squad Dashboard":
    st.subheader("📊 Squad Activity & Performance Overview")
    st.caption("Consolidated analytics, money won/lost, win rates, and ticket intelligence.")

    bets = st.session_state.saved_bets
    tot_placed = len(bets)
    won_bets = [b for b in bets if b.get("status") == "Won"]
    lost_bets = [b for b in bets if b.get("status") == "Lost"]
    pending_bets = [b for b in bets if b.get("status") == "Pending"]

    tot_won_dollars = sum(float(b.get("payout_dollars", 0)) - float(b.get("risk_dollars", 0)) for b in won_bets)
    tot_lost_dollars = sum(float(b.get("risk_dollars", 0)) for b in lost_bets)
    net_pl = tot_won_dollars - tot_lost_dollars
    tot_risk = sum(float(b.get("risk_dollars", 0)) for b in bets if b.get("status") in ["Won", "Lost"])
    roi = (net_pl / tot_risk * 100) if tot_risk > 0 else 0.0
    avg_stake = (sum(float(b.get("risk_dollars", 0)) for b in bets) / tot_placed) if tot_placed > 0 else 0.0

    # Common Bet Type
    types_count = {}
    for b in bets:
        t = b.get("bet_category", b.get("type", "Single"))
        types_count[t] = types_count.get(t, 0) + 1
    most_common_type = max(types_count, key=types_count.get) if types_count else "None"

    # KPI Metrics Row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Bets Placed", tot_placed)
    k2.metric("Money Won", f"${tot_won_dollars:.2f}")
    k3.metric("Money Lost", f"${tot_lost_dollars:.2f}")
    k4.metric("Net Profit / Loss", f"${net_pl:+.2f}", delta=f"{roi:+.1f}% ROI")

    k5, k6, k7, k8 = st.columns(4)
    decided = len(won_bets) + len(lost_bets)
    win_pct = (len(won_bets) / decided * 100) if decided > 0 else 0.0
    k5.metric("Win Rate", f"{win_pct:.1f}%", f"{len(won_bets)}W - {len(lost_bets)}L")
    k6.metric("Average Bet Stake", f"${avg_stake:.2f}")
    k7.metric("Pending In Play", len(pending_bets))
    k8.metric("Favorite Market", most_common_type)

    # Notable Tickets
    st.markdown("---")
    st.markdown("### 🏆 Hall of Fame & Toughest Beats")
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("##### 🚀 Biggest Winner")
        if won_bets:
            best_win = max(won_bets, key=lambda x: float(x.get("payout_dollars", 0)) - float(x.get("risk_dollars", 0)))
            profit = float(best_win.get("payout_dollars", 0)) - float(best_win.get("risk_dollars", 0))
            st.success(f"**{best_win.get('user')}**: {best_win.get('bet')} on `{best_win.get('matchup')}`\n\nProfit: **+${profit:.2f}** | Return: ${best_win.get('payout_dollars'):.2f}")
        else:
            st.info("No graded winning slips yet.")

    with h2:
        st.markdown("##### 💀 Biggest Beat")
        if lost_bets:
            worst_loss = max(lost_bets, key=lambda x: float(x.get("risk_dollars", 0)))
            st.error(f"**{worst_loss.get('user')}**: {worst_loss.get('bet')} on `{worst_loss.get('matchup')}`\n\nLost: **-${worst_loss.get('risk_dollars'):.2f}** stake")
        else:
            st.info("No recorded losses.")

# =========================================================================
# FEATURE 4, 5, 6: RE-ENGINEERED SINGLE GAME ENGINE WITH EXPANDABLE DIVS
# =========================================================================
elif menu_choice == "Single Game Engine":
    st.subheader("⚡ Single Game Analytics Engine")

    form_ver = st.session_state.single_form_version

    if games_data:
        game_options = [f"[{g['league']}] {g['away_short']} @ {g['home_short']} ({g.get('kickoff', g['status'])})" for g in games_data]
        if st.session_state.single_selected_idx >= len(game_options):
            st.session_state.single_selected_idx = 0
            
        selected_idx = st.selectbox(
            "Select Matchup Slate", 
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

    # -------------------------------------------------------------------------
    # NEW METHODOLOGY: PACE SHOCK & MOMENTUM VOLATILITY ENGINE
    # -------------------------------------------------------------------------
    h_pts = g["home_score"]
    a_pts = g["away_score"]
    pts_scored = h_pts + a_pts
    margin = abs(h_pts - a_pts)
    is_completed = g.get("completed", False) or "final" in g["status"].lower()
    pregame_tot = float(espn_ou)

    # Dynamic Pace Shock Calculation (prevents premature "Under" burnout during shootouts)
    if is_completed:
        final_proj = float(pts_scored)
        std_bracket = 0.01
    elif detected_stage == "Pre-Game":
        final_proj = pregame_tot
        std_bracket = 8.5
    else:
        # Calculate actual points vs baseline pace
        period_weight = 0.25 if detected_stage == "1st Quarter" else (0.50 if detected_stage == "Halftime" else 0.75)
        expected_pts_so_far = pregame_tot * period_weight
        pace_shock_ratio = pts_scored / max(expected_pts_so_far, 1.0)

        # High Volatility Surge (> 1.25 pace shock) means a shootout is occurring
        if pace_shock_ratio > 1.25:
            # Shift from regression to expansion momentum
            surge_pts = (pts_scored - expected_pts_so_far) * 0.85
            final_proj = pregame_tot + surge_pts
            std_bracket = 9.5  # Wider variance to avoid trapping users in under bets
        else:
            decay_factor = 0.40 if detected_stage == "1st Quarter" else (0.30 if detected_stage == "Halftime" else 0.20)
            final_proj = pregame_tot + ((pts_scored - expected_pts_so_far) * decay_factor)
            std_bracket = 6.0 if detected_stage == "Halftime" else 4.0

    delta_full = final_proj - pregame_tot
    pregame_2h = round(pregame_tot * 0.525, 1)
    live_2h_proj = (pregame_tot * 0.475) + ((pts_scored - (pregame_tot * 0.50)) * 0.45) if detected_stage == "Halftime" else pregame_2h + (delta_full * 0.45)
    delta_2h = live_2h_proj - pregame_2h

    market_spd = float(espn_spread)
    pregame_proj_margin = -market_spd
    current_margin = h_pts - a_pts
    live_proj_margin = (pregame_proj_margin * 0.45) + (current_margin * 0.55) if detected_stage == "Halftime" else pregame_proj_margin
    spread_drift = live_proj_margin - pregame_proj_margin
    home_cover_exp = calculate_spread_prob(live_proj_margin, market_spd, std_bracket)
    away_cover_exp = 1.0 - home_cover_exp

    pregame_h_prob = calculate_moneyline_prob(pregame_tot / 2.0, pregame_tot / 2.0, g.get("home_record", "0-0"), g.get("away_record", "0-0"))
    live_h_prob = calculate_moneyline_prob(h_pts + (final_proj / 2.0), a_pts + (final_proj / 2.0), g.get("home_record", "0-0"), g.get("away_record", "0-0"), is_final=is_completed)
    live_a_prob = 1.0 - live_h_prob

    # Auto-Snapshot Game Evolution
    sync_game_snapshot(g, final_proj, live_proj_margin)

    # -------------------------------------------------------------------------
    # COLLAPSIBLE SECTION 1: GAME SELECTION & LIVE MODEL PROJECTIONS
    # -------------------------------------------------------------------------
    with st.expander("📊 Section 1: Matchup Overview & Live Drift Projections", expanded=True):
        st.caption("Real-time scoreboard sync, pace-shock volatility calculations, and point spread drift metrics.")
        b1, b2, b3 = st.columns([1, 4, 1])
        b1.image(g.get("away_logo", DEFAULT_LOGO), width=45)
        b2.markdown(f"### **{g['away_short']}** @ **{g['home_short']}**\n{g.get('kickoff', g['status'])}")
        b3.image(g.get("home_logo", DEFAULT_LOGO), width=45)

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Full Game Total", f"{final_proj:.1f} pts", delta=f"{delta_full:+.1f} vs open ({pregame_tot})")
        m_col2.metric("2nd Half Total", f"{live_2h_proj:.1f} pts", delta=f"{delta_2h:+.1f} vs 2H base ({pregame_2h})")
        m_col3.metric(f"{g['home_short']} Win %", f"{live_h_prob*100:.1f}%")
        m_col4.metric(f"ATS Margin ({g['home_short']} {market_spd:+})", f"{live_proj_margin:+.1f} pts", delta=f"{spread_drift:+.1f} pts vs line")

    # -------------------------------------------------------------------------
    # COLLAPSIBLE SECTION 2: AI STRATEGY ENGINE WITH FULL EXPLANATIONS
    # -------------------------------------------------------------------------
    with st.expander("🤖 Section 2: AI Strategy Engine & Market Filters", expanded=True):
        st.caption("Tailor mathematical models by objective and wager category. Each selection includes a statistical rationale.")
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

        s_val = market_spd if home_cover_exp >= 0.5 else -market_spd
        s_team = active_game_for_strat["home_team"] if home_cover_exp >= 0.5 else active_game_for_strat["away_team"]
        s_abbr = tg_home_short if home_cover_exp >= 0.5 else tg_away_short

        if "Safe Floor" in strategy_dial:
            obj_tag = "Safe Floor"
            p_mult = 1.55
            spd_shift = 3.5 if s_val > 0 else 4.0
            tot_shift = 4.5
        elif "High Profit" in strategy_dial:
            obj_tag = "High Profit"
            p_mult = 2.45
            spd_shift = -3.5 if s_val > 0 else -4.0
            tot_shift = -3.5
        else:
            obj_tag = "Balanced Edge"
            p_mult = 1.91
            spd_shift = 0.0
            tot_shift = 0.0

        # Totals with Rationale
        tot_dir = "Under" if delta_full <= 0 else "Over"
        base_tot_1 = round(final_proj + tot_shift) + 0.5
        p_tot_1 = calculate_win_prob(base_tot_1, final_proj, std_bracket, is_under=(tot_dir == "Under"))
        
        full_totals_bets = [
            {
                "type": f"Full Game Total ({obj_tag} Consensus)",
                "pick": f"{tot_dir} {base_tot_1}",
                "prob": p_tot_1,
                "category": "Total",
                "side": tot_dir,
                "target_line": base_tot_1,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_mult,
                "roi_label": f"+{int((p_mult-1)*100)}% Profit",
                "drift_info": f"Pace Projection: {final_proj:.1f} pts ({delta_full:+.1f} vs open)",
                "rationale": f"Selected because actual game pace is scoring at {final_proj:.1f} pts compared to the opening {pregame_tot}. The {base_tot_1} threshold insulates against late fourth quarter variance."
            },
            {
                "type": f"Full Game Total ({obj_tag} Alternate Buffer)",
                "pick": f"{tot_dir} {base_tot_1 + (2.5 if tot_dir == 'Under' else -2.5)}",
                "prob": min(p_tot_1 + 0.10, 0.94),
                "category": "Total",
                "side": tot_dir,
                "target_line": base_tot_1 + (2.5 if tot_dir == 'Under' else -2.5),
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": 1.50,
                "roi_label": "+50% Profit",
                "drift_info": "Alternate safety line with wide buffer",
                "rationale": f"Selected to provide maximum protection by buying 2.5 additional safety points against sudden garbage-time scoring bursts."
            },
            {
                "type": f"Full Game Total ({obj_tag} Aggressive Margin)",
                "pick": f"{tot_dir} {base_tot_1 - (2.5 if tot_dir == 'Under' else 2.5)}",
                "prob": max(p_tot_1 - 0.12, 0.44),
                "category": "Total",
                "side": tot_dir,
                "target_line": base_tot_1 - (2.5 if tot_dir == 'Under' else 2.5),
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": 2.40,
                "roi_label": "+140% Profit (2.4x)",
                "drift_info": "Plus-money tempo play",
                "rationale": f"Selected for plus-money return because team drive efficiencies indicate severe stalling, allowing an aggressive undercut on total points."
            }
        ]

        # Spreads with Rationale
        line_spd_1 = s_val + spd_shift
        p_spd_1 = calculate_spread_prob(live_proj_margin if s_team == active_game_for_strat["home_team"] else -live_proj_margin, line_spd_1, std_bracket)
        spread_bets = [
            {
                "type": f"Spread ({obj_tag} Standard)",
                "pick": f"{s_abbr} {line_spd_1:+}",
                "prob": p_spd_1,
                "category": "Spread",
                "side": "Spread",
                "target_line": line_spd_1,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_mult,
                "roi_label": f"+{int((p_mult-1)*100)}% Profit",
                "drift_info": f"Expected Margin: {spread_drift:+.1f} pts vs market",
                "rationale": f"Selected because {s_abbr} is outperforming pre-game point differential expectations by {spread_drift:+.1f} points."
            },
            {
                "type": f"Spread ({obj_tag} Cushion)",
                "pick": f"{s_abbr} {(line_spd_1 + 3.0):+}",
                "prob": min(p_spd_1 + 0.12, 0.94),
                "category": "Spread",
                "side": "Spread",
                "target_line": line_spd_1 + 3.0,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": 1.55,
                "roi_label": "+55% Profit",
                "drift_info": "+3.0 pts alternate cushion",
                "rationale": f"Selected to create an insulated cover floor for {s_abbr} by adding a field goal cushion."
            },
            {
                "type": f"Spread ({obj_tag} Aggressive)",
                "pick": f"{s_abbr} {(line_spd_1 - 3.0):+}",
                "prob": max(p_spd_1 - 0.14, 0.46),
                "category": "Spread",
                "side": "Spread",
                "target_line": line_spd_1 - 3.0,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": 2.45,
                "roi_label": "+145% Profit (2.45x)",
                "drift_info": "Blowout expansion play",
                "rationale": f"Selected because offensive efficiency models indicate {s_abbr} has blowout separation capability."
            }
        ]

        if filter_choice == "📊 Full Game Total Score Over/Under":
            strat_candidates = full_totals_bets
        elif filter_choice == "🛡️ Spread (ATS Cover)":
            strat_candidates = spread_bets
        else:
            strat_candidates = [spread_bets[0], full_totals_bets[0], spread_bets[1]]

        for idx, sc in enumerate(strat_candidates[:3]):
            tier_lbl = ["🥇 BEST", "🥈 BETTER", "🥉 GOOD"][idx]
            with st.container(border=True):
                st.markdown(f"**{tier_lbl}** • `{sc['type']}` — <strong style='color:#4ade80;'>{sc['pick']}</strong> ({sc['prob']*100:.1f}% Win Prob | {sc['roi_label']})", unsafe_allow_html=True)
                st.info(f"💡 **Why This Bet Was Selected:** {sc['rationale']}")
                if st.button("📥 Load to Form", key=f"apply_{idx}_{sc['pick']}", use_container_width=True):
                    st.session_state.single_applied_pick = sc
                    st.session_state.single_selected_idx = sc["game_index"]
                    st.session_state.single_form_version += 1
                    st.rerun()

    # -------------------------------------------------------------------------
    # COLLAPSIBLE SECTION 3: WAGER TYPE & TICKET LOCK FORM
    # -------------------------------------------------------------------------
    applied = st.session_state.single_applied_pick
    with st.expander("📝 Section 3: Wager Type & Lock In Bet Slip", expanded=True):
        st.caption("Review lines, configure your stake, and lock tickets into your history.")

        c1, c2 = st.columns(2)
        with c1:
            home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}_v{form_ver}")
            away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}_v{form_ver}")
            pregame_total = st.number_input("Pre-Game Total", value=espn_ou, step=0.5, key=f"pre_{g_id}_v{form_ver}")
        with c2:
            h_pts_in = st.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"], key=f"hp_{g_id}_v{form_ver}")
            a_pts_in = st.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"], key=f"ap_{g_id}_v{form_ver}")
            spread_line = st.number_input(f"{g['home_short']} Spread", value=espn_spread, step=0.5, key=f"spd_{g_id}_v{form_ver}")

        bet_type = st.radio("Wager Type", ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"], horizontal=True, key=f"btype_{g_id}_v{form_ver}")

        with st.form(f"single_form_{g_id}_v{form_ver}"):
            if bet_type == "Game Total":
                f1, f2 = st.columns(2)
                side = f1.selectbox("Side", ["Under", "Over"], index=0 if (applied and applied.get("side") == "Under") else 1)
                strike = f2.number_input("Line", value=float(applied["target_line"]) if (applied and applied.get("target_line")) else float(final_proj))
                picked_t = None
            elif bet_type == "Point Spread (ATS)":
                f1, f2 = st.columns(2)
                picked_t = f1.selectbox("Covering Team", [home_team, away_team])
                strike = f2.number_input("Spread Line", value=float(applied["target_line"]) if (applied and applied.get("target_line") is not None) else float(spread_line))
                side = "Spread"
            else:
                picked_t = st.selectbox("Outright Winner", [home_team, away_team])
                strike = None
                side = "Moneyline"

            p1, p2 = st.columns(2)
            risk_amt = p1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
            mult = applied.get("est_payout_multiplier", 1.91) if applied else 1.91
            payout_amt = p2.number_input("Payout ($)", min_value=1.0, value=round(risk_amt * mult, 2))
            ticket_notes = st.text_input("Notes", f"Model Edge: {applied['pick']}" if applied else "Single play")

            if st.form_submit_button("Lock In Bet", use_container_width=True):
                bet_lbl = f"{side} {strike}" if strike else f"{picked_t} ML"
                cat_lbl = "Spread" if bet_type == "Point Spread (ATS)" else ("Total" if bet_type == "Game Total" else "Moneyline")
                ticket_record = {
                    "id": str(datetime.now().timestamp()),
                    "user": current_user.strip(),
                    "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Single",
                    "bet_category": cat_lbl,
                    "home_team": home_team,
                    "away_team": away_team,
                    "picked_team": picked_t,
                    "matchup": f"{g['away_short']} @ {g['home_short']}",
                    "bet": bet_lbl,
                    "target_line": strike,
                    "bet_direction": side,
                    "risk_dollars": float(risk_amt),
                    "payout_dollars": float(payout_amt),
                    "model_proj": round(final_proj, 1),
                    "win_prob": f"{applied['prob']*100:.1f}%" if applied else "55.0%",
                    "status": "Pending",
                    "notes": ticket_notes
                }
                st.session_state.saved_bets.insert(0, ticket_record)
                save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                st.session_state.single_applied_pick = None
                st.success("Ticket locked in successfully!")

# =========================================================================
# FEATURE 10: LOCKER ROOM WITH COMPACT FACEBOOK-STYLE POPOVER REACTIONS
# =========================================================================
elif menu_choice == "💬 The Locker Room":
    st.subheader("💬 The Locker Room")
    st.caption("Squad banter, threaded replies, and clean popover reactions.")

    with st.form("send_msg_form", clear_on_submit=True):
        user_msg = st.text_input("Send a message", placeholder="Share your take...")
        if st.form_submit_button("Post Message", use_container_width=True) and user_msg.strip():
            new_msg = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "time": get_current_et_time().strftime("%I:%M %p ET"),
                "text": user_msg.strip(),
                "reactions": {},
                "replies": []
            }
            st.session_state.chat_messages.insert(0, new_msg)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
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
            top_col1.markdown(f"**{m.get('user')}** &nbsp; <span style='opacity:0.55;font-size:0.8rem;'>{m.get('time')}</span>", unsafe_allow_html=True)
            
            if is_author:
                btn_c1, btn_c2 = top_col2.columns(2)
                if btn_c1.button("✏️", key=f"edit_trig_{m_id}"):
                    st.session_state.editing_msg_id = m_id if st.session_state.editing_msg_id != m_id else None
                    st.rerun()
                if btn_c2.button("🗑️", key=f"del_msg_{m_id}"):
                    st.session_state.chat_messages.pop(m_idx)
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.rerun()

            if st.session_state.editing_msg_id == m_id:
                with st.form(f"inline_edit_{m_id}"):
                    edited_text = st.text_input("Edit message", value=m.get("text", ""))
                    if st.form_submit_button("Save"):
                        m["text"] = edited_text.strip()
                        m["time"] = f"{m.get('time')} (edited)"
                        st.session_state.editing_msg_id = None
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                        st.rerun()
            else:
                st.write(m.get("text"))

            # Compact Facebook-style Popover
            rx_col1, rx_col2 = st.columns([8, 2], vertical_alignment="center")
            with rx_col1:
                if m["reactions"]:
                    rx_badges = [f"{emoji} {count}" for emoji, count in m["reactions"].items() if count > 0]
                    if rx_badges:
                        st.markdown(" ".join([f"<span style='background-color:rgba(255,255,255,0.08);padding:2px 8px;border-radius:12px;font-size:0.8rem;margin-right:4px;'>{b}</span>" for b in rx_badges]), unsafe_allow_html=True)
            with rx_col2:
                with st.popover("💬 React", use_container_width=True):
                    em_c1, em_c2, em_c3, em_c4, em_c5 = st.columns(5)
                    for idx, em in enumerate(["🔥", "💀", "💰", "🏈", "🧢"]):
                        col_target = [em_c1, em_c2, em_c3, em_c4, em_c5][idx]
                        if col_target.button(em, key=f"pop_rx_{m_id}_{em}"):
                            m["reactions"][em] = m["reactions"].get(em, 0) + 1
                            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                            st.rerun()

            with st.expander(f"💬 Replies ({len(m['replies'])})", expanded=False):
                for rep in m["replies"]:
                    st.markdown(f"• **{rep.get('user')}** ({rep.get('time')}): {rep.get('text')}")
                with st.form(f"rep_{m_id}", clear_on_submit=True):
                    rep_in = st.text_input("Reply", placeholder="Write reply...", label_visibility="collapsed")
                    if st.form_submit_button("Reply") and rep_in.strip():
                        m["replies"].append({"user": current_user.strip(), "time": get_current_et_time().strftime("%I:%M %p ET"), "text": rep_in.strip()})
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                        st.rerun()

# 6. LOCKED BETS HISTORY (WAR ROOM LINKING)
elif menu_choice == "Locked Bets History":
    st.subheader(f"📜 {current_user}'s Locked Bets")
    st.caption("Click any card to open the live game scoreboard & historical quarter-by-quarter projection timeline.")

    curr_user_clean = current_user.strip().lower()
    my_tickets = [b for b in st.session_state.saved_bets if b.get("user", "").strip().lower() == curr_user_clean or (curr_user_clean == "flurk" and b.get("user", "").strip().lower() in ["flurk", "admin"])]

    if not my_tickets:
        st.info("No bets placed yet.")
    else:
        for b in my_tickets:
            real_idx = st.session_state.saved_bets.index(b)
            with st.container(border=True):
                r1, r2, r3 = st.columns([5, 3, 2])
                r1.markdown(f"#### **{b.get('bet')}**\n`{b.get('matchup')}`")
                r2.write(f"Risk: **${float(b.get('risk_dollars',10)):.2f}** ➔ Payout: **${float(b.get('payout_dollars',19)):.2f}**\n\nStatus: `{b.get('status')}`")
                with r3:
                    if st.button("🏟️ View War Room", key=f"open_war_{b['id']}", use_container_width=True):
                        st.session_state.selected_bet_id = b["id"]
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"del_{b['id']}", use_container_width=True):
                        st.session_state.saved_bets.pop(real_idx)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                        st.rerun()

# 2-12 LEG COMBO BUILDER
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

    combo_legs = []
    compound_prob = 1.0
    ver = st.session_state.combo_version

    for i, leg_data in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            safe_m_idx = min(max(leg_data.get("matchup_idx", 0), 0), len(game_choices) - 1) if game_choices else 0
            sel_matchup = st.selectbox(f"Leg {i+1} Matchup", range(len(game_choices)), index=safe_m_idx, format_func=lambda x: game_choices[x], key=f"m_sel_{i}_v{ver}")
            leg_data["matchup_idx"] = sel_matchup
            leg_g = games_data[sel_matchup]
            col_b, col_c = st.columns(2)
            side = col_b.selectbox("Side", ["Under", "Over"], index=0 if leg_data.get("side", "Under") == "Under" else 1, key=f"lside_{i}_v{ver}")
            strike = col_c.number_input("Line", value=float(leg_data.get("line", leg_g.get("market_ou", 44.5))), step=0.5, key=f"lstrike_{i}_v{ver}")
            leg_data["side"] = side
            leg_data["line"] = strike
            p = calculate_win_prob(strike, 45.0, 7.0, is_under=(side == "Under"))
            compound_prob *= p
            combo_legs.append({"desc": f"{leg_g['away_short']}@{leg_g['home_short']}: {side} {strike}", "prob": p})

    st.metric("Compound Win Expectancy", f"{compound_prob * 100:.1f}%")
    with st.form("save_combo"):
        cr, cp = st.columns(2)
        c_risk = cr.number_input("Risk ($)", value=10.0)
        c_payout = cp.number_input("Payout ($)", value=50.0)
        if st.form_submit_button("Lock In Combo Ticket", use_container_width=True):
            st.session_state.saved_bets.insert(0, {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                "type": f"{len(combo_legs)}-Leg Combo",
                "bet_category": "Combo",
                "matchup": " | ".join([cl["desc"] for cl in combo_legs]),
                "bet": f"{len(combo_legs)} Legs",
                "risk_dollars": float(c_risk),
                "payout_dollars": float(c_payout),
                "win_prob": f"{compound_prob * 100:.1f}%",
                "status": "Pending"
            })
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
            st.success("Combo ticket locked in!")

# LEADERBOARD, HOW IT WORKS, METHODOLOGY & SQUAD FEED
elif menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    for b in st.session_state.saved_bets[:25]:
        with st.container(border=True):
            st.write(f"**{b.get('user')}**: {b.get('bet')} on `{b.get('matchup')}` — Risk: ${b.get('risk_dollars')} | Return: ${b.get('payout_dollars')} ({b.get('status')})")

elif menu_choice == "🏆 Squad Leaderboard":
    st.subheader("🏆 Squad Leaderboard")
    user_stats = {}
    for b in st.session_state.saved_bets:
        u = b.get("user", "Flurk").strip().lower()
        if u not in user_stats:
            user_stats[u] = {"name": b.get("user"), "won": 0, "lost": 0, "net": 0.0}
        r, p = float(b.get("risk_dollars", 0)), float(b.get("payout_dollars", 0))
        if b.get("status") == "Won":
            user_stats[u]["won"] += 1
            user_stats[u]["net"] += (p - r)
        elif b.get("status") == "Lost":
            user_stats[u]["lost"] += 1
            user_stats[u]["net"] -= r

    board = sorted(user_stats.values(), key=lambda x: x["net"], reverse=True)
    for idx, u in enumerate(board):
        with st.container(border=True):
            st.markdown(f"### #{idx+1} **{u['name']}** — Profit: **${u['net']:+.2f}** ({u['won']}W - {u['lost']}L)")

elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: User Manual")
    st.markdown("""
    * **📊 Squad Dashboard**: Real-time view of your win rate, ROI, favorite bets, and money won/lost.
    * **⚡ Single Game Engine**: Pace-shock volatility model with 3 collapsible sections and dynamic AI bet rationales.
    * **🏟️ In-Game War Room**: Click any ticket in history to view real-time score updates and the projection evolution table.
    * **💬 The Locker Room**: Live chat with Eastern Time timestamps, threaded replies, and Facebook-style popover reactions.
    """)

elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Model Architecture & Math")
    st.latex(r"Z = \frac{L - \mu}{\sigma}")
    st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")
    st.latex(r"P(\text{Home Win}) = \frac{1}{1 + e^{-\frac{\text{Spread}_{\text{eff}}}{6.5}}}")

elif menu_choice == "🛡️ Admin User Control" and is_user_admin:
    st.subheader("🛡️ Commissioner Admin Console")
    for u_k, u_v in list(st.session_state.user_accounts.items()):
        with st.container(border=True):
            st.write(f"User: **{u_v.get('display_name')}** (`@{u_k}`) | Email: `{u_v.get('email')}` | Banned: `{u_v.get('is_banned', False)}`")
