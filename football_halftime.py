import streamlit as st
import requests
import re
import random
import string
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# Import modular engines
from config import DEFAULT_LOGO, OFFICIAL_ABBR_MAP
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob
from database import load_storage, save_all_storage, find_game_for_bet, auto_resolve_bets, hash_password

st.set_page_config(
    page_title="Flurkstradamus Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Responsive Desktop + Mobile styling & Bootstrap-style full row stacking
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
        input, select, textarea {
            font-size: 16px !important;
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

# CLIENT-SIDE SCRIPTS: AUTO-CLOSE SIDEBAR ON MOBILE & DISMISS KEYBOARD
components.html("""
<script>
    function setupMobileBehaviors() {
        const doc = window.parent.document;
        if (!doc) return;

        if (window.parent.innerWidth <= 768) {
            const active = doc.activeElement;
            if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) {
                active.blur();
            }
        }

        const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
        if (sidebar) {
            const navButtons = sidebar.querySelectorAll('button');
            navButtons.forEach(btn => {
                if (!btn.dataset.mobileCloseAttached) {
                    btn.dataset.mobileCloseAttached = "true";
                    btn.addEventListener('click', () => {
                        if (window.parent.innerWidth <= 768) {
                            setTimeout(() => {
                                const closeBtn = doc.querySelector('[data-testid="stSidebarCollapseButton"]') 
                                              || doc.querySelector('button[kind="header"]')
                                              || doc.querySelector('[data-testid="stSidebar"] button');
                                if (closeBtn) closeBtn.click();
                            }, 100);
                        }
                    });
                }
            });
        }
    }
    setTimeout(setupMobileBehaviors, 300);
    setTimeout(setupMobileBehaviors, 800);
</script>
""", height=0)

STAR_TD_PLAYERS = {
    "PHI": [("Saquon Barkley", "RB"), ("A.J. Brown", "WR"), ("Jalen Hurts", "QB")],
    "DAL": [("CeeDee Lamb", "WR"), ("Rico Dowdle", "RB"), ("Jake Ferguson", "TE")],
    "KC": [("Travis Kelce", "TE"), ("Isiah Pacheco", "RB"), ("Xavier Worthy", "WR")],
    "BAL": [("Derrick Henry", "RB"), ("Lamar Jackson", "QB"), ("Zay Flowers", "WR")],
    "BUF": [("Josh Allen", "QB"), ("James Cook", "RB"), ("Khalil Shakir", "WR")],
    "MIA": [("De'Von Achane", "RB"), ("Tyreek Hill", "WR"), ("Jaylen Waddle", "WR")],
    "SF": [("Christian McCaffrey", "RB"), ("George Kittle", "TE"), ("Deebo Samuel", "WR")],
    "DET": [("Jahmyr Gibbs", "RB"), ("David Montgomery", "RB"), ("Amon-Ra St. Brown", "WR")],
    "GB": [("Josh Jacobs", "RB"), ("Jayden Reed", "WR"), ("Tucker Kraft", "TE")],
    "MIN": [("Justin Jefferson", "WR"), ("Aaron Jones", "RB"), ("Jordan Addison", "WR")],
    "CIN": [("Ja'Marr Chase", "WR"), ("Chase Brown", "RB"), ("Tee Higgins", "WR")],
    "HOU": [("Joe Mixon", "RB"), ("Nico Collins", "WR"), ("Stefon Diggs", "WR")],
    "ALA": [("Jalen Milroe", "QB"), ("Jam Miller", "RB"), ("Ryan Williams", "WR")],
    "UGA": [("Trevor Etienne", "RB"), ("Dillon Bell", "WR"), ("Dominic Lovett", "WR")],
    "OSU": [("Quinshon Judkins", "RB"), ("TreVeyon Henderson", "RB"), ("Jeremiah Smith", "WR")],
    "PSU": [("Nicholas Singleton", "RB"), ("Kaytron Allen", "RB"), ("Tyler Warren", "TE")],
    "TEX": [("Quinn Ewers", "QB"), ("Jaydon Blue", "RB"), ("Isaiah Bond", "WR")],
    "ORE": [("Jordan James", "RB"), ("Tez Johnson", "WR"), ("Dillon Gabriel", "QB")]
}

def get_star_scorers_for_team(abbr, team_name):
    clean_a = abbr.upper()
    if clean_a in STAR_TD_PLAYERS:
        return STAR_TD_PLAYERS[clean_a]
    for key, players in STAR_TD_PLAYERS.items():
        if key in clean_a or key in team_name.upper():
            return players
    return [("Lead Starting RB", "RB"), ("Primary WR1", "WR"), ("Red Zone TE", "TE")]

def get_current_et_time():
    utc_now = datetime.utcnow()
    return utc_now - timedelta(hours=4)

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

def round_half_point(val):
    return round(float(val) * 2.0) / 2.0

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
    st.session_state.active_nav_page = "📊 My Dashboard"
if "editing_ai_combo" not in st.session_state:
    st.session_state.editing_ai_combo = False
if "combo_version" not in st.session_state:
    st.session_state.combo_version = 0
if "editing_msg_id" not in st.session_state:
    st.session_state.editing_msg_id = None
if "scroll_to_form" not in st.session_state:
    st.session_state.scroll_to_form = False

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

# Persistent browser session
query_params = st.query_params
if st.session_state.logged_in_user is None:
    token_in_url = query_params.get("session_token")
    if token_in_url:
        for u_obj in st.session_state.user_accounts.values():
            if u_obj.get("session_token") == token_in_url and not u_obj.get("is_banned", False):
                st.session_state.logged_in_user = u_obj
                break

# Authentication Portal
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
                        matched_user["last_login"] = get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET")
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
            new_email = st.text_input("Email Address", placeholder="e.g. bettor@example.com").strip().lower()
            new_dname = st.text_input("Display Name", placeholder="e.g. Gridiron Guru")
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
                    st.error("This email address has been banned.")
                elif len(new_uname) < 3:
                    st.error("Username must be at least 3 characters.")
                elif new_pword != new_pword_confirm:
                    st.error("Passwords do not match.")
                elif new_uname in st.session_state.user_accounts:
                    st.error("This username is taken.")
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
                        "last_login": get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET"),
                        "favorite_team": fav_team.strip() if fav_team else "NFL",
                        "bio": "Football strategist and value seeker.",
                        "avatar_url": "",
                        "is_public": True,
                        "share_feed": True,
                        "searches": [],
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
            recover_email = st.text_input("Registered Email Address", placeholder="user@example.com").strip().lower()
            if st.form_submit_button("Request Reset Code", use_container_width=True):
                target_user = next((u for u in st.session_state.user_accounts.values() if u.get("email", "").lower() == recover_email), None)
                if target_user:
                    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    target_user["reset_token"] = token
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.success(f"✅ Recovery Code Generated: **`{token}`**")
                else:
                    st.error("No account found with that email address.")

        with st.form("complete_reset_form"):
            c_email = st.text_input("Confirm Your Email").strip().lower()
            code_input = st.text_input("6-Character Reset Code").strip().upper()
            new_pass1 = st.text_input("New Password", type="password")
            new_pass2 = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                target_user = next((u for u in st.session_state.user_accounts.values() if u.get("email", "").lower() == c_email), None)
                if target_user and target_user.get("reset_token") == code_input and new_pass1 == new_pass2 and len(new_pass1) >= 4:
                    target_user["password_hash"] = hash_password(new_pass1)
                    target_user["reset_token"] = None
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.success("🎉 Password updated! Please sign in.")
                else:
                    st.error("Invalid reset code or password mismatch.")
    st.stop()

# Active User Context
current_user_profile = st.session_state.logged_in_user
active_uname = current_user_profile.get("username", "").strip().lower()
current_user = "Flurk" if active_uname == "flurk" else current_user_profile.get("display_name", current_user_profile.get("username", "Bettor"))
is_user_admin = current_user_profile.get("is_admin", False)

current_user_profile["last_active"] = get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET")

# MULTI-DAY ESPN INGESTION (UPCOMING, LIVE & PAST MATCHUPS)
@st.cache_data(ttl=30)
def get_extended_games(selected_league="All Games"):
    all_games = []
    seen_ids = set()
    
    base_dates = [""]
    now_et = get_current_et_time()
    for d_offset in range(0, 14):
        f_dt = now_et + timedelta(days=d_offset)
        base_dates.append(f_dt.strftime("%Y%m%d"))
    for p_offset in range(1, 4):
        p_dt = now_et - timedelta(days=p_offset)
        base_dates.append(p_dt.strftime("%Y%m%d"))

    for d_param in base_dates:
        d_query = f"?dates={d_param}" if d_param else ""
        d_query_college = f"?dates={d_param}&groups=80" if d_param else "?groups=80"

        endpoints = []
        if selected_league in ["NFL", "All Games"]:
            endpoints.append(("NFL", f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard{d_query}"))
        if selected_league in ["NCAA Football", "All Games"]:
            endpoints.append(("NCAA", f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard{d_query_college}"))

        for l_label, url in endpoints:
            try:
                r = requests.get(url, timeout=4)
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

                        raw_date = event.get("date", "")
                        kickoff_formatted = format_espn_kickoff(raw_date, status_desc)
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
                            "raw_date": raw_date,
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

def sync_game_snapshot(game, proj_total, proj_spread):
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

# Sidebar UI
st.sidebar.markdown(f"## 🔮 Flurkstradamus")
st.sidebar.markdown(f"👤 **{current_user}** (`@{current_user_profile.get('username')}`)")
if current_user_profile.get("favorite_team"):
    st.sidebar.caption(f"🏈 {current_user_profile.get('favorite_team')}")

col_u1, _ = st.sidebar.columns(2)
with col_u1:
    if st.button("🚪 Logout", key="logout_btn", use_container_width=True, help="End your session and clear saved tokens."):
        st.session_state.logged_in_user = None
        st.query_params.clear()
        st.rerun()

st.sidebar.markdown("---")

nav_items = [
    ("📊 My Dashboard", "📊 My Dashboard"),
    ("⚡ Single Game Engine", "⚡ Single Game Engine"),
    ("🔗 Multi-Leg Combo Builder", "🔗 Multi-Leg Combo Builder"),
    ("📜 Locked Bets History", "📜 Locked Bets History"),
    ("🏆 Leaderboard", "🏆 Leaderboard"),
    ("🔥 Live Squad Feed", "🔥 Live Squad Feed"),
    ("💬 The Locker Room", "💬 The Locker Room"),
    ("💡 How It Works", "💡 How It Works"),
    ("📖 Model Methodology & Math", "📖 Model Methodology & Math"),
    ("⚙️ Account Settings", "⚙️ Account Settings")
]

if is_user_admin:
    nav_items.append(("🛡️ Admin", "🛡️ Admin"))

for label, page_key in nav_items:
    is_active = (st.session_state.active_nav_page == page_key and st.session_state.selected_bet_id is None)
    btn_type = "primary" if is_active else "secondary"
    if st.sidebar.button(label, key=f"nav_{page_key}", type=btn_type, use_container_width=True):
        st.session_state.selected_bet_id = None
        st.session_state.active_nav_page = page_key
        st.rerun()

menu_choice = st.session_state.active_nav_page

st.sidebar.markdown("---")
league = st.sidebar.radio("Primary League", ["NFL", "NCAA Football", "All Games"], help="Filter scoreboard feeds between Pro, College, or all games combined.")
auto_refresh = st.sidebar.toggle("Auto-Refresh Live Scores", value=True, help="Sync live ESPN scoreboards every 15 seconds.")
refresh_interval = st.sidebar.slider("Interval (seconds)", 10, 60, 15, 5)
if st.sidebar.button("🔄 Manual Scoreboard Sync", use_container_width=True, help="Force refresh live lines and scores immediately."):
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

# WAR ROOM ROUTE
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)
    
    if st.button("⬅️ Back to Locked Bets History", use_container_width=True):
        st.session_state.selected_bet_id = None
        st.rerun()

    if selected_bet is None:
        st.error("Selected ticket could not be found.")
        st.stop()

    is_combo = (selected_bet.get("bet_category") == "Combo" or "Leg" in selected_bet.get("type", ""))
    st.title(f"🏟️ War Room: {selected_bet.get('matchup', 'Football Ticket')}")
    st.caption(f"Bettor: **{selected_bet.get('user', 'Flurk')}** | Pick: `{selected_bet['bet']}` | Logged: {selected_bet.get('date', 'N/A')} | Status: `{selected_bet.get('status')}`")

    wm1, wm2, wm3, wm4 = st.columns(4)
    r_val = float(selected_bet.get('risk_dollars', 10.0))
    p_val = float(selected_bet.get('payout_dollars', 19.0))
    wm1.metric("Risk", f"${r_val:.2f}")
    wm2.metric("Payout", f"${p_val:.2f}")
    wm3.metric("Profit Potential", f"+${p_val - r_val:.2f}")
    wm4.metric("Live Ticket Status", selected_bet.get("status", "Pending"))

    if is_combo:
        st.markdown("### 📋 Multi-Leg Parlay Breakdown (All Teams & Logos)")
        st.caption("Game-by-game live scoreboard tracking, team logos, and quarter projection evolution:")
        legs = selected_bet.get("parsed_legs", [])
        
        if not legs:
            st.info("Parsed leg data not stored for older tickets.")
        else:
            for l_idx, leg in enumerate(legs):
                leg_matchup = leg.get("matchup", "")
                m_g = find_game_for_bet({"matchup": leg_matchup}, games_data)
                
                with st.container(border=True):
                    if m_g:
                        col_lg1, col_lg2 = st.columns([7, 3])
                        with col_lg1:
                            st.markdown(f"""
                            <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                                <span style="background-color:#38bdf8; color:#000; font-weight:800; font-size:0.75rem; padding:2px 7px; border-radius:4px;">LEG {l_idx+1}</span>
                                <img src="{m_g['away_logo']}" width="26" height="26" style="border-radius:50%;">
                                <strong style="font-size:1.0rem;">{m_g['away_short']}</strong> @
                                <img src="{m_g['home_logo']}" width="26" height="26" style="border-radius:50%;">
                                <strong style="font-size:1.0rem;">{m_g['home_short']}</strong>
                                <span style="opacity:0.6; font-size:0.85rem;">({m_g.get('kickoff', m_g['status'])})</span>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_lg2:
                            st.markdown(f"<div style='text-align:right;'><strong style='color:#4ade80;'>{leg.get('side', '')} {leg.get('line', '')} {leg.get('picked_team', '')}</strong></div>", unsafe_allow_html=True)

                        lc1, lc2, lc3 = st.columns([2, 1, 2])
                        lc1.metric(f"Away ({m_g['away_short']})", m_g['away_score'])
                        lc2.write(f"**Status:** {m_g['status']}\n\nClock: `{m_g.get('displayClock', 'Live')}`")
                        lc3.metric(f"Home ({m_g['home_short']})", m_g['home_score'])
                        
                        gid = m_g["id"]
                        snap = st.session_state.game_snapshots.get(gid)
                        if snap and "stages" in snap:
                            st.markdown("##### 📈 Projection Evolution (Initial vs In-Game Shifts)")
                            t_rows = []
                            for stg, s_val in snap["stages"].items():
                                t_rows.append({
                                    "Stage": stg,
                                    "Score": f"{s_val['away_score']} - {s_val['home_score']}",
                                    "Projected Total": f"{s_val['proj_total']} pts",
                                    "Total Shift": f"{s_val['proj_total'] - snap['open_ou']:+.1f} pts",
                                    "Projected Spread Margin": f"{s_val['proj_spread']:+.1f} pts"
                                })
                            st.table(t_rows)
                    else:
                        st.markdown(f"#### Leg {l_idx+1}: **{leg_matchup}**")
                        st.write(f"**Pick:** `{leg.get('side', '')} {leg.get('line', '')} {leg.get('picked_team', '')}` ({leg.get('type')})")
                        st.caption("Scoreboard feed for this leg is scheduled or inactive.")

                    st.markdown("##### 💡 Strategic Insights & What to Watch:")
                    st.write(f"• **Why Suggested:** High compound equity model selected `{leg.get('side', '')} {leg.get('line', '')}` based on opening defensive pace ratings.")
                    st.write("• **What to Watch For:** Monitor third-quarter turnover margins and clock-bleed drives. If point pacing stalls, hedge opportunity opens up on live totals.")

    else:
        live_game_info = find_game_for_bet(selected_bet, games_data)
        if live_game_info:
            with st.container(border=True):
                col_s1, col_s2, col_s3 = st.columns([2, 1, 2])
                with col_s1:
                    st.image(live_game_info["away_logo"], width=45)
                    st.markdown(f"**{live_game_info['away_short']}**\n# **{live_game_info['away_score']}**")
                with col_s2:
                    st.caption(f"{live_game_info.get('kickoff', live_game_info['status'])}")
                    st.caption(f"Clock: `{live_game_info.get('displayClock', 'Live')}`")
                with col_s3:
                    st.image(live_game_info["home_logo"], width=45)
                    st.markdown(f"**{live_game_info['home_short']}**\n# **{live_game_info['home_score']}**")

            gid = live_game_info["id"]
            snap = st.session_state.game_snapshots.get(gid)

            st.markdown("### 📈 Projection Evolution & Drift Timeline")
            st.caption("Machine-learning trajectory: how projections adapted as quarter scores evolved:")

            timeline_data = []
            if snap and "stages" in snap:
                for stg, s_val in snap["stages"].items():
                    timeline_data.append({
                        "Stage / Period": stg,
                        "Live Score": f"{s_val['away_score']} - {s_val['home_score']} ({s_val['total_pts']} pts)",
                        "Projected Full Total": f"{s_val['proj_total']} pts",
                        "Total Drift vs Open": f"{s_val['proj_total'] - snap['open_ou']:+.1f} pts",
                        "Projected Spread Margin": f"{s_val['proj_spread']:+.1f} pts",
                        "Logged At": s_val["timestamp"]
                    })
            
            if timeline_data:
                st.table(timeline_data)
            else:
                st.info("Live checkpoints will record as the matchup transitions between Pre-Game, Q1, Halftime, and Q3.")

            st.markdown("### 💡 Game Script Intelligence:")
            st.write(f"• **Model Rationale:** Ticket locked with initial probability expectation of **{selected_bet.get('win_prob', 'N/A')}**.")
            st.write("• **Live Tactical Edge:** Watch for hurry-up packages and red zone turnover variance.")
        else:
            st.warning("Live scoreboard feed for this matchup is currently inactive.")
    st.stop()

# =========================================================================
# 1. MY DASHBOARD
# =========================================================================
if menu_choice == "📊 My Dashboard":
    st.subheader(f"📊 {current_user}'s Personal Betting Dashboard")
    st.caption("Personal portfolio overview: money won, money lost, ROI, and performance breakdown.")

    curr_user_clean = current_user.strip().lower()
    my_bets = [b for b in st.session_state.saved_bets if b.get("user", "").strip().lower() == curr_user_clean or (curr_user_clean == "flurk" and b.get("user", "").strip().lower() in ["flurk", "admin"])]
    tot_placed = len(my_bets)

    if tot_placed == 0:
        with st.container(border=True):
            st.markdown("### 👋 Welcome to Flurkstradamus! Let's Lock In Your First Edge")
            st.write(
                "You haven't locked in any bet slips yet. Flurkstradamus continuously tracks live line drift and models scoring pace to identify mispriced sportsbook lines. "
                "Follow these simple steps to get started:"
            )
            st.markdown("""
            1. **Navigate to the Single Game Engine or Combo Builder**:
               * Use the **Single Game Engine** for point spreads, totals, moneylines, and player anytime touchdowns.
               * Use the **Multi-Leg Combo Builder** if you want to compound true win probabilities on a multi-team parlay.
            2. **Select a Matchup or Let the System Pick**:
               * Select your game from the dropdown or toggle **Scan Full Slate for Highest Discrepancy**.
            3. **Choose Your Strategy Objective**:
               * Slide the model dial to **🛡️ Safe Floor** (insulating cushion with high win rates), **⚖️ Balanced Edge** (+EV sweet spot), or **🚀 High Profit** (max multiplier upside).
            4. **Load & Lock In**:
               * Click **'📥 Load to Form'** on any recommended card. It scrolls down and immediately populates the slip for you!
               * Review your stake and click **Lock In Bet Slip** to save it to your history and leaderboard standing!
            """)

            ob_c1, ob_c2 = st.columns(2)
            with ob_c1:
                if st.button("⚡ Go to Single Game Engine", use_container_width=True):
                    st.session_state.active_nav_page = "⚡ Single Game Engine"
                    st.rerun()
            with ob_c2:
                if st.button("🔗 Go to Multi-Leg Combo Builder", use_container_width=True):
                    st.session_state.active_nav_page = "🔗 Multi-Leg Combo Builder"
                    st.rerun()

    won_bets = [b for b in my_bets if b.get("status") == "Won"]
    lost_bets = [b for b in my_bets if b.get("status") == "Lost"]
    pending_bets = [b for b in my_bets if b.get("status") == "Pending"]

    tot_won_dollars = sum(float(b.get("payout_dollars", 0)) - float(b.get("risk_dollars", 0)) for b in won_bets)
    tot_lost_dollars = sum(float(b.get("risk_dollars", 0)) for b in lost_bets)
    net_pl = tot_won_dollars - tot_lost_dollars
    tot_risk = sum(float(b.get("risk_dollars", 0)) for b in my_bets if b.get("status") in ["Won", "Lost"])
    roi = (net_pl / tot_risk * 100) if tot_risk > 0 else 0.0
    avg_stake = (sum(float(b.get("risk_dollars", 0)) for b in my_bets) / tot_placed) if tot_placed > 0 else 0.0

    types_count = {}
    for b in my_bets:
        t = b.get("bet_category", b.get("type", "Single"))
        types_count[t] = types_count.get(t, 0) + 1
    most_common_type = max(types_count, key=types_count.get) if types_count else "None"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("My Bets Placed", tot_placed, help="Total tickets placed under your profile.")
    k2.metric("Money Won", f"${tot_won_dollars:.2f}", help="Total net profit from settled winning slips.")
    k3.metric("Money Lost", f"${tot_lost_dollars:.2f}", help="Total stake lost on settled losing slips.")
    k4.metric("Net Profit / Loss", f"${net_pl:+.2f}", delta=f"{roi:+.1f}% ROI", help="Net dollars won/lost and overall return on investment percentage.")

    k5, k6, k7, k8 = st.columns(4)
    decided = len(won_bets) + len(lost_bets)
    win_pct = (len(won_bets) / decided * 100) if decided > 0 else 0.0
    k5.metric("Win Rate", f"{win_pct:.1f}%", f"{len(won_bets)}W - {len(lost_bets)}L")
    k6.metric("Average Stake", f"${avg_stake:.2f}")
    k7.metric("Pending In Play", len(pending_bets))
    k8.metric("Favorite Market", most_common_type)

    st.markdown("---")
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("##### 🚀 Top Winner")
        if won_bets:
            best_win = max(won_bets, key=lambda x: float(x.get("payout_dollars", 0)) - float(x.get("risk_dollars", 0)))
            profit = float(best_win.get("payout_dollars", 0)) - float(best_win.get("risk_dollars", 0))
            st.success(f"{best_win.get('bet')} on `{best_win.get('matchup')}`\n\nProfit: **+${profit:.2f}** | Return: ${best_win.get('payout_dollars'):.2f}")
        else:
            st.info("No graded winning slips yet.")
    with h2:
        st.markdown("##### 💀 Toughest Beat")
        if lost_bets:
            worst_loss = max(lost_bets, key=lambda x: float(x.get("risk_dollars", 0)))
            st.error(f"{worst_loss.get('bet')} on `{worst_loss.get('matchup')}`\n\nStake Lost: **-${worst_loss.get('risk_dollars'):.2f}**")
        else:
            st.info("No recorded losses.")

# =========================================================================
# 2. SINGLE GAME ENGINE
# =========================================================================
elif menu_choice == "⚡ Single Game Engine":
    st.subheader("⚡ Single Game Analytics Engine")

    form_ver = st.session_state.single_form_version

    f_col1, f_col2 = st.columns([1, 2])
    with f_col1:
        timing_view = st.selectbox(
            "Game Status Filter",
            ["⏳ Upcoming Games", "⚡ Live Games", "📜 Past / Completed Games", "🌐 All Matchups"],
            help="Filter between upcoming future games, live active games, or past completed games."
        )
    with f_col2:
        search_query = st.text_input("🔍 Search Matchup or Team", placeholder="e.g. Eagles, Dallas, Ohio State...", help="Search any team name, city, or matchup.")
        if search_query.strip():
            if "searches" not in current_user_profile:
                current_user_profile["searches"] = []
            if search_query.strip() not in current_user_profile["searches"]:
                current_user_profile["searches"].append(search_query.strip())
                save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)

    pool = games_data
    if timing_view == "⏳ Upcoming Games":
        pool = [g for g in pool if not g.get("completed", False) and g.get("checkpoint") == "Pre-Game"]
    elif timing_view == "⚡ Live Games":
        pool = [g for g in pool if not g.get("completed", False) and g.get("checkpoint") != "Pre-Game"]
    elif timing_view == "📜 Past / Completed Games":
        pool = [g for g in pool if g.get("completed", False)]

    if search_query.strip():
        q = search_query.strip().lower()
        pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g["home_short"].lower() or q in g["away_short"].lower()]

    if pool:
        game_options = [f"[{g['kickoff']}] [{g['league']}] {g['away_short']} @ {g['home_short']}" for g in pool]
        if st.session_state.single_selected_idx >= len(game_options):
            st.session_state.single_selected_idx = 0
            
        selected_idx = st.selectbox(
            "Select Matchup", 
            range(len(game_options)), 
            index=st.session_state.single_selected_idx, 
            format_func=lambda x: game_options[x],
            key=f"single_matchup_dropdown_v{form_ver}",
            help="Choose the specific matchup you want to model and analyze."
        )
        st.session_state.single_selected_idx = selected_idx
        
        g = pool[selected_idx]
        g_id = g.get("id", str(selected_idx))
        detected_stage = g["checkpoint"]
        espn_ou = round_half_point(g["market_ou"])
        espn_spread = round_half_point(g["market_spread"])
    else:
        st.info("No matchups found matching your status filter or search query. Switch to '⏳ Upcoming Games' or '🌐 All Matchups'.")
        st.stop()

    h_pts = g["home_score"]
    a_pts = g["away_score"]
    pts_scored = h_pts + a_pts
    is_completed = g.get("completed", False) or "final" in g["status"].lower()
    pregame_tot = float(espn_ou)

    if is_completed:
        final_proj = float(pts_scored)
        std_bracket = 0.01
    elif detected_stage == "Pre-Game":
        final_proj = pregame_tot
        std_bracket = 8.5
    else:
        period_weight = 0.25 if detected_stage == "1st Quarter" else (0.50 if detected_stage == "Halftime" else 0.75)
        expected_pts_so_far = pregame_tot * period_weight
        pace_shock_ratio = pts_scored / max(expected_pts_so_far, 1.0)

        if pace_shock_ratio > 1.25:
            surge_pts = (pts_scored - expected_pts_so_far) * 0.85
            final_proj = pregame_tot + surge_pts
            std_bracket = 9.5
        else:
            decay_factor = 0.40 if detected_stage == "1st Quarter" else (0.30 if detected_stage == "Halftime" else 0.20)
            final_proj = pregame_tot + ((pts_scored - expected_pts_so_far) * decay_factor)
            std_bracket = 6.0 if detected_stage == "Halftime" else 4.0

    final_proj = round_half_point(final_proj)
    delta_full = final_proj - pregame_tot
    pregame_2h = round_half_point(pregame_tot * 0.525)
    live_2h_proj = round_half_point((pregame_tot * 0.475) + ((pts_scored - (pregame_tot * 0.50)) * 0.45) if detected_stage == "Halftime" else pregame_2h + (delta_full * 0.45))
    delta_2h = live_2h_proj - pregame_2h

    market_spd = float(espn_spread)
    pregame_proj_margin = -market_spd
    current_margin = h_pts - a_pts
    live_proj_margin = round_half_point((pregame_proj_margin * 0.45) + (current_margin * 0.55) if detected_stage == "Halftime" else pregame_proj_margin)
    spread_drift = live_proj_margin - pregame_proj_margin
    home_cover_exp = calculate_spread_prob(live_proj_margin, market_spd, std_bracket)
    away_cover_exp = 1.0 - home_cover_exp

    live_h_prob = calculate_moneyline_prob(h_pts + (final_proj / 2.0), a_pts + (final_proj / 2.0), g.get("home_record", "0-0"), g.get("away_record", "0-0"), is_final=is_completed)
    live_a_prob = 1.0 - live_h_prob

    sync_game_snapshot(g, final_proj, live_proj_margin)

    # ACCORDION 1
    with st.expander("📊 Section 1: Matchup Overview & Live Drift Projections", expanded=True):
        st.markdown(
            "> **What this section does:** Compares opening sportsbook lines against in-game scoring volume to calculate live line drift, "
            "second-half pace projections, and effective ATS margin deviations."
        )
        b1, b2, b3 = st.columns([1, 4, 1])
        b1.image(g.get("away_logo", DEFAULT_LOGO), width=45)
        b2.markdown(f"### **{g['away_short']}** @ **{g['home_short']}**\n{g['kickoff']}")
        b3.image(g.get("home_logo", DEFAULT_LOGO), width=45)

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Full Game Total", f"{final_proj:.1f} pts", delta=f"{delta_full:+.1f} vs open ({pregame_tot:.1f})", help="Pace-shock full game projection.")
        m_col2.metric("2nd Half Total", f"{live_2h_proj:.1f} pts", delta=f"{delta_2h:+.1f} vs 2H base ({pregame_2h:.1f})", help="Expected scoring volume in the second half.")
        m_col3.metric(f"{g['home_short']} Win %", f"{live_h_prob*100:.1f}%", help="Logistic straight-up win expectancy.")
        m_col4.metric(f"ATS Margin ({g['home_short']} {market_spd:+.1f})", f"{live_proj_margin:+.1f} pts", delta=f"{spread_drift:+.1f} pts vs line", help="Expected point spread margin differential.")

    # ACCORDION 2: AI STRATEGY ENGINE WITH MATCHUP & TEAM DETAILS
    with st.expander("🤖 Section 2: AI Strategy Engine & Market Filters", expanded=True):
        st.markdown(
            "> **What this section does:** Evaluates betting opportunities across Totals, Spreads, Moneylines, and **Player Anytime Touchdown Scorers**. "
            "Adjusting the Model Objective dynamically changes line thresholds, payouts, and win probabilities."
        )
        col_scope, col_type_filter = st.columns(2)
        scope_choice = col_scope.selectbox(
            "Target Slate", 
            ["🎯 Focus on Selected Game Above", "⚡ Scan Full Slate for Highest Discrepancy"],
            help="Analyze the currently selected matchup or scan across all active games."
        )
        filter_choice = col_type_filter.selectbox(
            "Type of Bet", 
            [
                "⚡ Let the System Pick (All Markets Combined)", 
                "📊 Full Game Total Score Over/Under", 
                "⏱️ 2nd Half Total Points", 
                "🛡️ Spread (ATS Cover)",
                "🏆 Team Win/Loser (Moneyline)", 
                "🏈 Player Anytime Touchdown Scorer"
            ],
            help="Choose the specific wagering market you wish to generate recommendations for."
        )
        
        strategy_dial = st.select_slider(
            "Model Objective", 
            options=[
                "🛡️ Safe Floor (High Win %, Low Drawdown)", 
                "⚖️ Balanced Edge (+EV Sweet Spot)", 
                "🚀 High Profit (Max Multiplier & Value Underdogs)"
            ], 
            value="⚖️ Balanced Edge (+EV Sweet Spot)",
            help="Slide to adjust safety margin: Safe Floor buys points for high win probability, while High Profit seeks plus-money returns."
        )

        active_game_for_strat = g
        strat_game_index = pool.index(active_game_for_strat)
        if "Scan Full Slate" in scope_choice and pool:
            live_pool = [gm for gm in pool if not gm.get("completed", False)]
            if live_pool:
                active_game_for_strat = max(live_pool, key=lambda x: abs((x["home_score"] + x["away_score"] + (x.get("market_ou", 47.5)*0.475)) - x.get("market_ou", 47.5)))
                strat_game_index = pool.index(active_game_for_strat)

        tg_away_logo = active_game_for_strat.get("away_logo", DEFAULT_LOGO)
        tg_home_logo = active_game_for_strat.get("home_logo", DEFAULT_LOGO)
        tg_away_short = active_game_for_strat.get("away_short", "AWAY")
        tg_home_short = active_game_for_strat.get("home_short", "HOME")
        tg_date_str = active_game_for_strat.get("kickoff", "Scheduled Game")
        tg_league_str = active_game_for_strat.get("league", "NFL")

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

        # Totals
        tot_dir = "Under" if delta_full <= 0 else "Over"
        base_tot_1 = round_half_point(final_proj + tot_shift)
        p_tot_1 = calculate_win_prob(base_tot_1, final_proj, std_bracket, is_under=(tot_dir == "Under"))
        full_totals_bets = [
            {
                "type": f"Full Game Total ({obj_tag} Consensus)",
                "pick": f"{tot_dir} {base_tot_1:.1f}",
                "prob": p_tot_1,
                "category": "Total",
                "side": tot_dir,
                "target_line": base_tot_1,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_mult,
                "roi_label": f"+{int((p_mult-1)*100)}% Profit",
                "drift_info": f"Pace Projection: {final_proj:.1f} pts ({delta_full:+.1f} vs open)",
                "rationale": f"Selected because in-game scoring volume indicates {final_proj:.1f} total points vs opening line of {pregame_tot:.1f}."
            },
            {
                "type": f"Full Game Total ({obj_tag} Alternate Buffer)",
                "pick": f"{tot_dir} {round_half_point(base_tot_1 + (2.5 if tot_dir == 'Under' else -2.5)):.1f}",
                "prob": min(p_tot_1 + 0.10, 0.94),
                "category": "Total",
                "side": tot_dir,
                "target_line": round_half_point(base_tot_1 + (2.5 if tot_dir == 'Under' else -2.5)),
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": 1.50,
                "roi_label": "+50% Profit",
                "drift_info": "Alternate safety line buffer",
                "rationale": "Selected to insulate against sudden late fourth-quarter garbage time touchdowns by expanding the line."
            },
            {
                "type": f"Full Game Total ({obj_tag} Aggressive Margin)",
                "pick": f"{tot_dir} {round_half_point(base_tot_1 - (2.5 if tot_dir == 'Under' else 2.5)):.1f}",
                "prob": max(p_tot_1 - 0.12, 0.44),
                "category": "Total",
                "side": tot_dir,
                "target_line": round_half_point(base_tot_1 - (2.5 if tot_dir == 'Under' else 2.5)),
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": 2.40,
                "roi_label": "+140% Profit (2.4x)",
                "drift_info": "Plus-money pace undercut",
                "rationale": "Selected for maximum profit multiplier where team drive efficiency models show severe stalling."
            }
        ]

        # Spreads
        line_spd_1 = round_half_point(s_val + spd_shift)
        p_spd_1 = calculate_spread_prob(live_proj_margin if s_team == active_game_for_strat["home_team"] else -live_proj_margin, line_spd_1, std_bracket)
        spread_bets = [
            {
                "type": f"Spread ({obj_tag} Standard)",
                "pick": f"{s_abbr} {line_spd_1:+.1f}",
                "prob": p_spd_1,
                "category": "Spread",
                "side": "Spread",
                "target_line": line_spd_1,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_mult,
                "roi_label": f"+{int((p_mult-1)*100)}% Profit",
                "drift_info": f"Expected Margin: {spread_drift:+.1f} pts vs market",
                "rationale": f"Selected because {s_abbr} is outperforming point differential expectations."
            },
            {
                "type": f"Spread ({obj_tag} Cushion)",
                "pick": f"{s_abbr} {round_half_point(line_spd_1 + 3.0):+.1f}",
                "prob": min(p_spd_1 + 0.12, 0.94),
                "category": "Spread",
                "side": "Spread",
                "target_line": round_half_point(line_spd_1 + 3.0),
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": 1.55,
                "roi_label": "+55% Profit",
                "drift_info": "+3.0 pts bought buffer",
                "rationale": f"Selected to provide an insulated cover floor for {s_abbr} by adding extra cushion."
            },
            {
                "type": f"Spread ({obj_tag} Aggressive)",
                "pick": f"{s_abbr} {round_half_point(line_spd_1 - 3.0):+.1f}",
                "prob": max(p_spd_1 - 0.14, 0.46),
                "category": "Spread",
                "side": "Spread",
                "target_line": round_half_point(line_spd_1 - 3.0),
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": 2.45,
                "roi_label": "+145% Profit (2.45x)",
                "drift_info": "Blowout expansion play",
                "rationale": f"Selected for plus-money return where talent and yardage advantages indicate blowout separation."
            }
        ]

        # Touchdown Props with Real Player Names
        home_scorers = get_star_scorers_for_team(tg_home_short, active_game_for_strat["home_team"])
        away_scorers = get_star_scorers_for_team(tg_away_short, active_game_for_strat["away_team"])

        p1_name, p1_pos = home_scorers[0]
        p2_name, p2_pos = away_scorers[0]
        p3_name, p3_pos = home_scorers[1] if len(home_scorers) > 1 else ("Primary Target", "WR")

        td_candidates = [
            {
                "player": f"{p1_name} ({p1_pos} - {tg_home_short})",
                "p_td": 0.58 if "Safe Floor" in strategy_dial else 0.52,
                "mult": 1.85,
                "label": "+85% Profit (-115)",
                "reason": f"{p1_name} commands {tg_home_short}'s goal-line share inside the 5-yard line with unmatched red-zone touch volume."
            },
            {
                "player": f"{p2_name} ({p2_pos} - {tg_away_short})",
                "p_td": 0.45 if "Safe Floor" in strategy_dial else 0.41,
                "mult": 2.25,
                "label": "+125% Profit (+125)",
                "reason": f"{p2_name} is {tg_away_short}'s premier red-zone option facing an opponent allowing frequent goal-to-go opportunities."
            },
            {
                "player": f"{p3_name} ({p3_pos} - {tg_home_short})",
                "p_td": 0.36 if "Safe Floor" in strategy_dial else 0.33,
                "mult": 3.10,
                "label": "+210% Profit (+210)",
                "reason": f"{p3_name} serves as the primary situational target on play-action passing concepts in high-scoring scripts."
            }
        ]

        touchdown_bets = [
            {
                "type": f"Anytime Touchdown ({obj_tag})",
                "pick": f"{c['player']} Any Time TD",
                "prob": c["p_td"],
                "category": "Anytime TD",
                "side": "TD",
                "target_line": 1.0,
                "picked_team": c["player"],
                "game_index": strat_game_index,
                "est_payout_multiplier": c["mult"],
                "roi_label": c["label"],
                "drift_info": "Red-zone touch volume & defensive matchup efficiency",
                "rationale": c["reason"]
            }
            for c in td_candidates
        ]

        if filter_choice == "📊 Full Game Total Score Over/Under":
            strat_candidates = full_totals_bets
        elif filter_choice == "🛡️ Spread (ATS Cover)":
            strat_candidates = spread_bets
        elif filter_choice == "🏈 Player Anytime Touchdown Scorer":
            strat_candidates = touchdown_bets
        else:
            strat_candidates = [spread_bets[0], full_totals_bets[0], touchdown_bets[0]]

        # RENDER SUGGESTED BETS WITH FULL MATCHUP, LOGOS & KICKOFF DATE/TIME
        for idx, sc in enumerate(strat_candidates[:3]):
            tier_lbl = ["🥇 BEST", "🥈 BETTER", "🥉 GOOD"][idx]
            with st.container(border=True):
                # Header Marquee with Logos, Kickoff Time & League
                st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 6px; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 800; font-size: 0.90rem;">{tier_lbl}</span>
                        <span style="opacity: 0.4;">•</span>
                        <code style="font-size: 0.80rem;">{sc['type']}</code>
                    </div>
                    <div style="display: flex; align-items: center; gap: 7px;">
                        <span style="background-color: rgba(255,255,255,0.08); padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">[{tg_league_str}]</span>
                        <img src="{tg_away_logo}" width="22" height="22" style="border-radius: 50%;">
                        <strong style="font-size: 0.90rem;">{tg_away_short}</strong>
                        <span style="opacity: 0.4; font-size: 0.8rem;">@</span>
                        <img src="{tg_home_logo}" width="22" height="22" style="border-radius: 50%;">
                        <strong style="font-size: 0.90rem;">{tg_home_short}</strong>
                        <span style="opacity: 0.65; font-size: 0.78rem; margin-left: 4px;">🗓️ {tg_date_str}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Bet Pick, Multiplier & Probability
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

                st.info(f"💡 **Why This Bet Was Selected:** {sc['rationale']}")
                if st.button("📥 Load to Form", key=f"apply_{idx}_{sc['pick']}", use_container_width=True, help="Load this exact pick, line, and odds directly into your slip below and scroll to form."):
                    st.session_state.single_applied_pick = sc
                    st.session_state.single_selected_idx = sc["game_index"]
                    st.session_state.single_form_version += 1
                    st.session_state.scroll_to_form = True
                    st.rerun()

    # Anchor point for smooth auto-scrolling
    st.markdown("<div id='bet-slip-anchor'></div>", unsafe_allow_html=True)

    if st.session_state.scroll_to_form:
        st.session_state.scroll_to_form = False
        components.html("""
            <script>
                setTimeout(function() {
                    const el = window.parent.document.getElementById('bet-slip-anchor');
                    if (el) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }, 300);
            </script>
        """, height=0)

    # ACCORDION 3: SLIP BUILDER WITH 0.5 STEP INCREMENTS
    applied = st.session_state.single_applied_pick
    with st.expander("📝 Section 3: Wager Type & Lock In Bet Slip", expanded=True):
        st.markdown(
            "> **What this section does:** Review matchup parameters, customize risk and payout, and persist the slip to your account history."
        )

        c1, c2 = st.columns(2)
        with c1:
            home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}_v{form_ver}")
            away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}_v{form_ver}")
            pregame_total = st.number_input("Pre-Game Baseline Total", value=float(espn_ou), step=0.5, format="%.1f", key=f"pre_{g_id}_v{form_ver}", help="Opening sportsbook consensus total.")
        with c2:
            h_pts_in = st.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"], key=f"hp_{g_id}_v{form_ver}")
            a_pts_in = st.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"], key=f"ap_{g_id}_v{form_ver}")
            spread_line = st.number_input(f"{g['home_short']} Spread", value=float(espn_spread), step=0.5, format="%.1f", key=f"spd_{g_id}_v{form_ver}", help="Opening consensus point spread line.")

        default_wtype = 0
        if applied:
            if applied["category"] == "Spread": default_wtype = 1
            elif applied["category"] == "Moneyline": default_wtype = 2
            elif applied["category"] == "Anytime TD": default_wtype = 3

        bet_type = st.radio(
            "Wager Type", 
            ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Player Anytime Touchdown Scorer"], 
            index=default_wtype,
            horizontal=True, 
            key=f"btype_{g_id}_v{form_ver}",
            help="Choose the market type for this ticket."
        )

        with st.form(f"single_form_{g_id}_v{form_ver}"):
            if bet_type == "Game Total":
                f1, f2 = st.columns(2)
                side = f1.selectbox("Side", ["Under", "Over"], index=0 if (applied and applied.get("side") == "Under") else 1)
                default_strike = round_half_point(applied["target_line"]) if (applied and applied.get("target_line")) else round_half_point(final_proj)
                strike = f2.number_input("Target Line (pts)", value=float(default_strike), step=0.5, format="%.1f")
                picked_t = None
            elif bet_type == "Point Spread (ATS)":
                f1, f2 = st.columns(2)
                picked_t = f1.selectbox("Covering Team", [home_team, away_team])
                default_spread = round_half_point(applied["target_line"]) if (applied and applied.get("target_line") is not None) else round_half_point(spread_line)
                strike = f2.number_input("Spread Line", value=float(default_spread), step=0.5, format="%.1f")
                side = "Spread"
            elif bet_type == "Straight Up Winner (Moneyline)":
                picked_t = st.selectbox("Outright Winner", [home_team, away_team])
                strike = None
                side = "Moneyline"
            else:
                default_p = applied["picked_team"] if (applied and applied.get("picked_team")) else f"{p1_name} ({p1_pos} - {g['home_short']})"
                picked_t = st.text_input("Player to Score TD", value=default_p, help="Enter exact player name.")
                strike = 1.0
                side = "Anytime TD"

            p1, p2 = st.columns(2)
            risk_amt = p1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0, help="Dollar amount staked.")
            mult = applied.get("est_payout_multiplier", 1.91) if applied else 1.91
            payout_amt = p2.number_input("Payout ($)", min_value=1.0, value=round(risk_amt * mult, 2), help="Total payout returned if ticket wins.")
            
            if applied:
                default_notes = f"Model Edge: {applied['pick']} | {applied.get('drift_info', '')}"
            else:
                default_notes = f"Model Proj: {final_proj:.1f} pts ({delta_full:+.1f} vs {pregame_tot:.1f} open) | Live ATS Margin: {live_proj_margin:+.1f} pts"

            ticket_notes = st.text_input("Notes", default_notes, help="Statistical audit trail and reasoning for this bet.")

            if st.form_submit_button("Lock In Bet Slip", use_container_width=True):
                if bet_type == "Player Anytime Touchdown Scorer":
                    bet_lbl = f"{picked_t} Any Time TD"
                    cat_lbl = "Anytime TD"
                else:
                    bet_lbl = f"{side} {strike:.1f}" if strike else f"{picked_t} ML"
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
                st.success("Ticket locked into your account history!")

# =========================================================================
# 3. MULTI-LEG COMBO BUILDER
# =========================================================================
elif menu_choice == "🔗 Multi-Leg Combo Builder":
    st.subheader("🔗 Multi-Leg Combo Builder (Up to 12 Legs)")
    st.caption("Automated cross-slate parlay scanner, compound probability calculator, and slip builder.")

    c_fcol1, c_fcol2 = st.columns([1, 2])
    with c_fcol1:
        c_timing_view = c_fcol1.selectbox(
            "Game Status Filter (Combo)",
            ["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"],
            help="Filter games for your parlay legs."
        )
    with c_fcol2:
        c_search = c_fcol2.text_input("🔍 Search Game Slate", placeholder="e.g. Chiefs, Lions, Ravens...", help="Search teams to include in parlay legs.")

    c_pool = games_data
    if c_timing_view == "⏳ Upcoming Games":
        c_pool = [g for g in c_pool if not g.get("completed", False) and g.get("checkpoint") == "Pre-Game"]
    elif c_timing_view == "⚡ Live Games":
        c_pool = [g for g in c_pool if not g.get("completed", False) and g.get("checkpoint") != "Pre-Game"]

    if c_search.strip():
        cq = c_search.strip().lower()
        c_pool = [g for g in c_pool if cq in g["home_team"].lower() or cq in g["away_team"].lower() or cq in g["home_short"].lower() or cq in g["away_short"].lower()]

    if not c_pool:
        st.info("No games match the selected status or search filter. Switch back to '⏳ Upcoming Games' or '🌐 All Matchups'.")
        st.stop()

    game_choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in c_pool]

    if st.session_state.combo_active_legs and c_pool:
        for leg in st.session_state.combo_active_legs:
            if leg.get("matchup_idx", 0) >= len(c_pool):
                leg["matchup_idx"] = 0

    if not st.session_state.combo_active_legs and c_pool:
        init_count = min(3, len(c_pool))
        st.session_state.combo_active_legs = []
        for j in range(init_count):
            g_item = c_pool[j]
            st.session_state.combo_active_legs.append({
                "matchup_idx": j,
                "type": "Game Total",
                "side": "Under",
                "line": round_half_point(g_item.get("market_ou", 47.5)),
                "picked_team": g_item["home_team"]
            })

    with st.expander("🤖 Flurkstradamus AI Combo Recommender & Strategy Scanner", expanded=True):
        st.markdown(
            "> **What this scanner does:** Automatically scans the entire slate to find compound edges across totals, spreads, and moneylines matching your target leg count."
        )
        col_strat1, col_strat2 = st.columns(2)
        strategy_mode = col_strat1.selectbox(
            "Strategy Objective",
            [
                "🎯 Maximum Win Probability (Safest Floor)",
                "🔥 High Expected Value (+EV Total Edge)",
                "🏆 Straight-Up Moneyline Dominance",
                "🛡️ Defensive Under Lock (Pace Slump)"
            ],
            help="Select your compound strategy objective."
        )

        active_candidate_games = [gm for gm in c_pool if not gm.get("completed", False)]
        if not active_candidate_games:
            active_candidate_games = c_pool
        max_possible_legs = min(12, max(2, len(active_candidate_games)))

        suggest_legs_count = col_strat2.number_input(
            "Target Legs (Up to 12)",
            min_value=2,
            max_value=max_possible_legs,
            value=min(max(len(st.session_state.combo_active_legs), 3), max_possible_legs),
            help="Choose how many legs to include in the parlay."
        )
        generate_clicked = st.button("⚡ Scan & Recommend Across Slates", use_container_width=True, help="Run AI scan to select the best combination of picks.")

        if generate_clicked and c_pool:
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
                else:
                    proj_tot = c_tot_pts + 8.0
                    sigma = 4.0

                h_prob = calculate_moneyline_prob(c_h_pts + 14, c_a_pts + 14, c_h_rec, c_a_rec, is_final=False)

                if "Maximum Win Probability" in strategy_mode:
                    cushion_line = round_half_point(proj_tot + (sigma * 1.5))
                    p = calculate_win_prob(cushion_line, proj_tot, sigma, is_under=True)
                    candidate_legs.append({
                        "leg_id": f"tot_{g_c['id']}_under_{cushion_line}",
                        "matchup_idx": c_pool.index(g_c),
                        "type": "Game Total",
                        "side": "Under",
                        "line": cushion_line,
                        "picked_team": c_h,
                        "prob": p,
                        "desc": f"Under {cushion_line:.1f}",
                        "detail": f"Proj: {proj_tot:.1f} pts",
                        "score_metric": p
                    })
                elif "High Expected Value" in strategy_mode:
                    edge = abs(proj_tot - c_ou)
                    is_u = proj_tot < c_ou
                    tgt_line = round_half_point(c_ou)
                    p = calculate_win_prob(tgt_line, proj_tot, sigma, is_under=is_u)
                    candidate_legs.append({
                        "leg_id": f"ev_{g_c['id']}_{'u' if is_u else 'o'}_{tgt_line}",
                        "matchup_idx": c_pool.index(g_c),
                        "type": "Game Total",
                        "side": "Under" if is_u else "Over",
                        "line": tgt_line,
                        "picked_team": c_h,
                        "prob": p,
                        "desc": f"{'Under' if is_u else 'Over'} {tgt_line:.1f}",
                        "detail": f"Edge: {edge:.1f} pts",
                        "score_metric": edge * p
                    })
                else:
                    ml_fav = c_h if h_prob >= 0.5 else c_a
                    fav_abbr = c_h_abbr if h_prob >= 0.5 else c_a_abbr
                    ml_p = max(h_prob, 1.0 - h_prob)
                    candidate_legs.append({
                        "leg_id": f"ml_{g_c['id']}_{ml_fav}",
                        "matchup_idx": c_pool.index(g_c),
                        "type": "Straight Up Winner",
                        "side": "Under",
                        "line": round_half_point(c_ou),
                        "picked_team": ml_fav,
                        "prob": ml_p,
                        "desc": f"{fav_abbr} ML",
                        "detail": f"{ml_p*100:.1f}%",
                        "score_metric": ml_p
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

        if st.session_state.ai_recommended_combo and c_pool:
            valid_legs = [l for l in st.session_state.ai_recommended_combo if 0 <= l.get("matchup_idx", -1) < len(c_pool)]
            st.session_state.ai_recommended_combo = valid_legs

        if st.session_state.ai_recommended_combo:
            num_legs_rec = len(st.session_state.ai_recommended_combo)
            comp_p = 1.0
            for l_item in st.session_state.ai_recommended_combo:
                comp_p *= l_item["prob"]

            t_col1, t_col2 = st.columns([8.5, 1.5], vertical_alignment="center")
            t_col1.markdown(f"#### 🎯 Recommended Ticket ({num_legs_rec} Legs):")
            toggle_label = "Done" if st.session_state.editing_ai_combo else "Edit Legs"
            if t_col2.button(toggle_label, key="toggle_edit_ai", help="Open menu to drop specific legs."):
                st.session_state.editing_ai_combo = not st.session_state.editing_ai_combo
                st.rerun()

            if st.session_state.editing_ai_combo:
                with st.container(border=True):
                    leg_options = [
                        f"Leg {k+1}: {item['desc']} ({c_pool[min(item['matchup_idx'], len(c_pool)-1)]['away_short']}@{c_pool[min(item['matchup_idx'], len(c_pool)-1)]['home_short']})"
                        for k, item in enumerate(st.session_state.ai_recommended_combo)
                    ]
                    selected_leg_idx = st.radio("Select a leg to remove:", range(len(leg_options)), format_func=lambda x: leg_options[x])
                    r_c1, r_c2 = st.columns([2, 1])
                    if r_c1.button("🗑️ Remove Selected Leg", use_container_width=True):
                        st.session_state.ai_recommended_combo.pop(selected_leg_idx)
                        st.rerun()
                    if r_c2.button("Done", use_container_width=True):
                        st.session_state.editing_ai_combo = False
                        st.rerun()

            for idx_ai, l_ai in enumerate(st.session_state.ai_recommended_combo):
                m_idx = min(max(l_ai.get("matchup_idx", 0), 0), len(c_pool) - 1)
                g_match = c_pool[m_idx]
                detail_str = l_ai.get("detail", "")

                st.markdown(f"""
                <div class="rec-single-line-card">
                    <div>
                        <span style="background-color: #22c55e; color: #000; font-weight: 800; font-size: 0.75rem; padding: 2px 7px; border-radius: 4px;">
                            LEG {idx_ai+1}
                        </span>
                        <img src="{g_match['away_logo']}" width="20" height="20" style="border-radius: 50%;">
                        <strong>{g_match['away_short']}</strong> @
                        <img src="{g_match['home_logo']}" width="20" height="20" style="border-radius: 50%;">
                        <strong>{g_match['home_short']}</strong>
                    </div>
                    <div>
                        <strong style="color: #4ade80;">{l_ai['desc']}</strong> ({detail_str}) — 
                        <span style="background-color: rgba(255, 255, 255, 0.08); padding: 2px 8px; border-radius: 4px; font-size: 0.80rem; font-weight: 600;">
                            {l_ai['prob']*100:.1f}%
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            m_rec1, m_rec2 = st.columns([2, 1], vertical_alignment="center")
            m_rec1.metric("Compound Recommended Win Expectancy", f"{comp_p * 100:.1f}%", delta=f"{len(st.session_state.ai_recommended_combo)} Legs")
            if m_rec2.button("📥 Apply Picks into Ticket Slip", use_container_width=True, help="Load recommended picks directly into the combo slip below."):
                st.session_state.combo_version += 1
                st.session_state.combo_active_legs = [
                    {
                        "matchup_idx": min(l_item["matchup_idx"], len(c_pool)-1),
                        "type": l_item["type"],
                        "side": l_item.get("side", "Under"),
                        "line": round_half_point(l_item.get("line", 47.5)),
                        "picked_team": l_item.get("picked_team", c_pool[min(l_item["matchup_idx"], len(c_pool)-1)]["home_team"])
                    }
                    for l_item in st.session_state.ai_recommended_combo
                ]
                st.rerun()

    ver = st.session_state.combo_version
    ctrl_c1, ctrl_c2 = st.columns([3, 1], vertical_alignment="center")
    ctrl_c1.markdown(f"#### Active Ticket Slip ({len(st.session_state.combo_active_legs)} Legs)")
    if ctrl_c2.button("➕ Add Leg", use_container_width=True, disabled=(len(st.session_state.combo_active_legs) >= 12 or not c_pool)):
        next_idx = min(len(st.session_state.combo_active_legs), len(c_pool) - 1)
        g_next = c_pool[next_idx]
        st.session_state.combo_active_legs.append({
            "matchup_idx": next_idx,
            "type": "Game Total",
            "side": "Under",
            "line": round_half_point(g_next.get("market_ou", 47.5)),
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
            leg_g = c_pool[sel_matchup]

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
                strike = col_c.number_input("Line (pts)", value=float(round_half_point(leg_data.get("line", leg_g.get("market_ou", 44.5)))), step=0.5, format="%.1f", key=f"lstrike_{i}_v{ver}")
                leg_data["side"] = side
                leg_data["line"] = strike
                leg_prob = calculate_win_prob(strike, 42.0, 7.0, is_under=(side == "Under"))
                leg_desc = f"{leg_g['away_short']} @ {leg_g['home_short']}: {side} {strike:.1f}"
            else:
                col_b, col_c = st.columns(2)
                teams_opt = [leg_g["home_team"], leg_g["away_team"]]
                prev_pick = leg_data.get("picked_team", leg_g["home_team"])
                pick_idx = teams_opt.index(prev_pick) if prev_pick in teams_opt else 0
                winner = col_b.selectbox("Pick Winner", teams_opt, index=pick_idx, format_func=lambda x: f"{clean_abbr(x, '')} ({x})", key=f"lwinner_{i}_v{ver}")
                leg_data["picked_team"] = winner
                win_abbr = clean_abbr(winner, "")
                h_prob = calculate_moneyline_prob(leg_g["home_score"] + 14, leg_g["away_score"] + 14, leg_g["home_record"], leg_g["away_record"])
                leg_prob = h_prob if winner == leg_g["home_team"] else (1.0 - h_prob)
                leg_desc = f"{leg_g['away_short']} @ {leg_g['home_short']}: {win_abbr} ML"
                col_c.metric("Model Win %", f"{leg_prob * 100:.1f}%")

            compound_prob *= leg_prob
            combo_legs.append({"desc": leg_desc, "prob": leg_prob})

    st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        c_r1, c_r2 = st.columns(2)
        c_risk = c_r1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        c_payout = c_r2.number_input("Payout ($)", min_value=1.0, value=50.0, step=10.0)
        if st.form_submit_button(f"Lock In {len(combo_legs)}-Leg Ticket", use_container_width=True):
            parsed_legs = []
            for item in st.session_state.combo_active_legs:
                s_idx = min(item["matchup_idx"], len(c_pool) - 1)
                mg = c_pool[s_idx]
                parsed_legs.append({
                    "matchup": f"{mg['away_short']} @ {mg['home_short']}",
                    "type": item["type"],
                    "side": item.get("side", ""),
                    "line": round_half_point(item.get("line", 0.0)),
                    "picked_team": item.get("picked_team", "")
                })

            combo_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                "type": f"{len(combo_legs)}-Leg Combo",
                "bet_category": "Combo",
                "matchup": " | ".join([cl["desc"] for cl in combo_legs]),
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
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
            st.success(f"{len(combo_legs)}-Leg combo ticket locked in!")

# =========================================================================
# 4. LOCKED BETS HISTORY
# =========================================================================
elif menu_choice == "📜 Locked Bets History":
    st.subheader(f"📜 {current_user}'s Locked Bets")
    st.caption("Click any card to enter the live game War Room with score updates and projection timelines.")

    curr_user_clean = current_user.strip().lower()
    col_filter1, col_filter2 = st.columns([3, 1])
    with col_filter2:
        show_all_history = st.toggle("Show All Squad Bets", value=False)
        
    my_tickets = st.session_state.saved_bets if show_all_history else [
        b for b in st.session_state.saved_bets 
        if b.get("user", "").strip().lower() == curr_user_clean 
        or (curr_user_clean == "flurk" and b.get("user", "").strip().lower() in ["flurk", "admin"])
    ]

    with col_filter1:
        st.write(f"Showing **{len(my_tickets)}** ticket(s).")
        if st.button("⚡ Grade Finals", use_container_width=True):
            if auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages, st.session_state.game_snapshots):
                st.success("Updated tickets!")
                st.rerun()

    if not my_tickets:
        st.info("No tickets recorded yet.")
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

# =========================================================================
# 5. LEADERBOARD
# =========================================================================
elif menu_choice == "🏆 Leaderboard":
    st.subheader("🏆 Leaderboard")
    st.caption("Consensus standings, return on investment, betting volume, and live member status.")

    user_stats = {}
    for b in st.session_state.saved_bets:
        u_raw = b.get("user", "Flurk").strip().lower()
        if u_raw not in user_stats:
            user_stats[u_raw] = {
                "name": b.get("user"),
                "total_bets": 0,
                "won": 0,
                "lost": 0,
                "pending": 0,
                "net": 0.0,
                "total_staked": 0.0,
                "types": {}
            }
        
        user_stats[u_raw]["total_bets"] += 1
        r, p = float(b.get("risk_dollars", 0)), float(b.get("payout_dollars", 0))
        cat = b.get("bet_category", b.get("type", "Single"))
        user_stats[u_raw]["types"][cat] = user_stats[u_raw]["types"].get(cat, 0) + 1

        if b.get("status") == "Won":
            user_stats[u_raw]["won"] += 1
            user_stats[u_raw]["net"] += (p - r)
            user_stats[u_raw]["total_staked"] += r
        elif b.get("status") == "Lost":
            user_stats[u_raw]["lost"] += 1
            user_stats[u_raw]["net"] -= r
            user_stats[u_raw]["total_staked"] += r
        else:
            user_stats[u_raw]["pending"] += 1

    board = []
    for u_key, stat in user_stats.items():
        acc = st.session_state.user_accounts.get(u_key, {})
        if not acc.get("is_public", True):
            continue

        last_act = acc.get("last_active", "")
        is_online = ("ET" in last_act)
        fav_market = max(stat["types"], key=stat["types"].get) if stat["types"] else "Single"
        decided = stat["won"] + stat["lost"]
        win_rate = (stat["won"] / decided * 100) if decided > 0 else 0.0
        roi_val = (stat["net"] / stat["total_staked"] * 100) if stat["total_staked"] > 0 else 0.0

        board.append({
            "name": stat["name"],
            "online": "🟢 Online" if is_online else "⚪ Offline",
            "total_bets": stat["total_bets"],
            "won": stat["won"],
            "lost": stat["lost"],
            "pending": stat["pending"],
            "win_rate": f"{win_rate:.1f}%",
            "roi": f"{roi_val:+.1f}%",
            "favorite": fav_market,
            "net": stat["net"]
        })

    board.sort(key=lambda x: x["net"], reverse=True)

    if not board:
        st.info("No recorded tickets on the public leaderboard.")
    else:
        for idx, u in enumerate(board):
            medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"#{idx+1}"))
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 4, 2])
                c1.markdown(f"### {medal} **{u['name']}** &nbsp; <span style='font-size:0.8rem;'>{u['online']}</span>", unsafe_allow_html=True)
                c1.caption(f"Favorite Wager Type: **{u['favorite']}**")
                
                c2.write(f"📊 **{u['won']}W - {u['lost']}L** ({u['win_rate']} Win Rate) | **{u['total_bets']}** Total Bets ({u['pending']} Pending)")
                c2.write(f"Return ROI: **{u['roi']}**")

                color = "#4ade80" if u['net'] >= 0 else "#f87171"
                c3.markdown(f"<div style='text-align:right;'><span style='color:{color};font-size:1.4rem;font-weight:700;'>${u['net']:+.2f}</span></div>", unsafe_allow_html=True)

# =========================================================================
# 6. LIVE SQUAD FEED
# =========================================================================
elif menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    st.caption("Live stream of tickets placed across the squad.")
    for b in st.session_state.saved_bets[:25]:
        with st.container(border=True):
            st.write(f"**{b.get('user')}**: {b.get('bet')} on `{b.get('matchup')}` — Risk: ${b.get('risk_dollars')} | Return: ${b.get('payout_dollars')} ({b.get('status')})")

# =========================================================================
# 7. THE LOCKER ROOM
# =========================================================================
elif menu_choice == "💬 The Locker Room":
    st.subheader("💬 The Locker Room")
    st.caption("Squad banter with compact reactions and threaded replies.")

    with st.form("send_msg_form", clear_on_submit=True):
        user_msg = st.text_input("Send a message", placeholder="Share your thoughts...")
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
        if "reactions" not in m: m["reactions"] = {}
        if "replies" not in m: m["replies"] = []
        is_author = (m.get("user", "").strip().lower() == current_user.strip().lower() or is_user_admin)

        with st.container(border=True):
            top_col1, top_col2 = st.columns([8, 2])
            top_col1.markdown(f"**{m.get('user')}** &nbsp; <span style='opacity:0.55;font-size:0.8rem;'>{m.get('time')}</span>", unsafe_allow_html=True)
            if is_author and top_col2.button("🗑️", key=f"del_{m_id}"):
                st.session_state.chat_messages.pop(m_idx)
                save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                st.rerun()

            st.write(m.get("text"))

            col_rx, col_pop = st.columns([8, 2], vertical_alignment="center")
            if m["reactions"]:
                rx_badges = [f"{em} {ct}" for em, ct in m["reactions"].items() if ct > 0]
                col_rx.markdown(" ".join([f"<span style='background-color:rgba(255,255,255,0.08);padding:2px 8px;border-radius:12px;font-size:0.8rem;'>{b}</span>" for b in rx_badges]), unsafe_allow_html=True)
            
            with col_pop.popover("💬 React"):
                for em in ["🔥", "💀", "💰", "🏈", "🧢"]:
                    if st.button(em, key=f"rx_{m_id}_{em}"):
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

# =========================================================================
# 8. HOW IT WORKS
# =========================================================================
elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: The User Manual")
    st.markdown("""
    * **📊 My Dashboard**: Review personal performance, money won, money lost, ROI, and top winners. If you have no bets placed, follow the quick start onboarding steps!
    * **⚡ Single Game Engine**: Filter games by upcoming, live, or past. Review real-time model projections, anytime touchdown props, and custom AI bet rationales with full team logo headers and dates.
    * **🔗 Multi-Leg Combo Builder**: Scan slates for optimal multi-leg parlay opportunities with compound true win probabilities.
    * **🏟️ In-Game War Room**: Click any single or multi-leg combo ticket in Locked Bets History to evaluate live score updates, all team logos, and quarter-by-quarter projection drift.
    * **⚙️ Account Settings**: Personalize your profile, bio, avatar, and privacy settings.
    """)

# =========================================================================
# 9. MODEL METHODOLOGY & MATH
# =========================================================================
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Flurkstradamus Machine Learning & Mathematical Architecture")
    st.markdown("""
    ### Why Flurkstradamus Outperforms Traditional Sportsbooks
    Traditional sportsbooks rely on static pre-game lines and flat halving models (dividing full game lines by 2 for halftime). 
    Flurkstradamus utilizes a **Self-Learning Bayesian In-Game Regression Engine** designed to avoid getting trapped in volatile blowouts or sudden shootouts.
    """)

    with st.container(border=True):
        st.markdown("#### 1. In-Game Machine Learning & Quarter-by-Quarter Feedback Loop")
        st.write(
            "Every game's trajectory is continuously preserved across 5 discrete states in `storage.json`: "
            "**Pre-Game $\to$ Q1 $\to$ Halftime $\to$ Q3 $\to$ Final**."
        )
        st.markdown("""
        * **Tracking Projections vs. Reality:** The model logs its pre-game expected scoring pace against actual quarter-by-quarter scoring.
        * **Pace-Shock Anomaly Detection:** If an early quarter exceeds baseline scoring pace by over 25% (e.g. a shootout), the model expands variance ($\sigma$) dynamically rather than forcing an artificial regression toward opening pregame numbers.
        * **Feedback Learning:** As historical games finalize, the system aggregates the variance delta between pre-game predictions and final scores to train team-specific tempo modifiers for future slates.
        """)

    with st.container(border=True):
        st.markdown("#### 2. Statistical Formulas & Normal CDF Modeling")
        st.write("Over/Under win expectancies use the continuous cumulative normal distribution function:")
        st.latex(r"Z = \frac{\text{Line} - \mu_{\text{in-game}}}{\sigma_{\text{decay}}}")
        st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")
        st.write("Point spread ATS win expectancies utilize effective team efficiency margins passed through a logistic sigmoid function:")
        st.latex(r"\text{Spread}_{\text{eff}} = (\text{Home Proj} - \text{Away Proj}) + \left[(\text{Home Win \%} - \text{Away Win \%}) \times 7.0\right]")
        st.latex(r"P(\text{Home Cover}) = \frac{1}{1 + e^{-\frac{\text{Spread}_{\text{eff}}}{6.5}}}")

    with st.container(border=True):
        st.markdown("#### 3. Anytime Touchdown Prop Architecture")
        st.write(
            "Touchdown probabilities model goal-line share ($< 5$ yards), red-zone target volume, team implied totals, and opponent red-zone defensive efficiency."
        )
        st.latex(r"P(\text{TD}) = 1 - e^{-\left(\lambda_{\text{Team TD}} \times \text{Player Share} \times \text{Defensive Matchup Modifier}\right)}")

# =========================================================================
# 10. ACCOUNT SETTINGS (BOTTOM OF USER NAVIGATION)
# =========================================================================
elif menu_choice == "⚙️ Account Settings":
    st.subheader("⚙️ Account Settings & Profile Management")
    st.caption("Customize your display name, profile details, privacy preferences, and security.")

    with st.form("account_settings_form"):
        st.markdown("### 👤 Profile Details")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            new_display = st.text_input("Display Name (Public Bettor Handle)", value=current_user_profile.get("display_name", ""))
            new_email = st.text_input("Email Address", value=current_user_profile.get("email", ""))
            new_team = st.text_input("Favorite Team", value=current_user_profile.get("favorite_team", "NFL"))
        with col_p2:
            new_avatar = st.text_input("Profile Avatar URL", value=current_user_profile.get("avatar_url", ""), placeholder="https://example.com/avatar.png")
            new_bio = st.text_area("Short Bio", value=current_user_profile.get("bio", "Football strategist and value seeker."))

        st.markdown("### 🔒 Privacy Settings")
        pr1, pr2 = st.columns(2)
        with pr1:
            pub_lead = st.toggle("Show My Profile on Public Leaderboard", value=current_user_profile.get("is_public", True), help="Toggle whether other bettors can see your P&L ranking.")
        with pr2:
            share_fd = st.toggle("Publish My Slips to Live Squad Feed", value=current_user_profile.get("share_feed", True), help="Allow your locked bets to broadcast to the community.")

        st.markdown("### 🔑 Security & Password Change")
        sc1, sc2 = st.columns(2)
        with sc1:
            p_change1 = st.text_input("New Password (Leave blank to keep current)", type="password", placeholder="••••••••")
        with sc2:
            p_change2 = st.text_input("Confirm New Password", type="password", placeholder="••••••••")

        if st.form_submit_button("Save Account Settings", use_container_width=True):
            if new_display.strip():
                current_user_profile["display_name"] = new_display.strip()
            if new_email.strip() and "@" in new_email:
                current_user_profile["email"] = new_email.strip()
            current_user_profile["favorite_team"] = new_team.strip()
            current_user_profile["avatar_url"] = new_avatar.strip()
            current_user_profile["bio"] = new_bio.strip()
            current_user_profile["is_public"] = pub_lead
            current_user_profile["share_feed"] = share_fd

            if p_change1:
                if p_change1 == p_change2 and len(p_change1) >= 4:
                    current_user_profile["password_hash"] = hash_password(p_change1)
                    st.success("Password updated!")
                else:
                    st.error("Passwords must match and be at least 4 characters.")

            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
            st.success("✅ Account settings successfully updated!")
            st.rerun()

# =========================================================================
# 11. ADMIN CONSOLE
# =========================================================================
elif menu_choice == "🛡️ Admin" and is_user_admin:
    st.subheader("🛡️ Commissioner Admin Console")
    st.caption("Inspect user activity, audit bet tickets, review search logs, and manage accounts.")

    users = st.session_state.user_accounts
    st.write(f"Total Registered Users: **{len(users)}**")

    user_list = list(users.keys())
    selected_u = st.selectbox(
        "Select User to Inspect Activity & Dossier",
        options=user_list,
        format_func=lambda x: f"{users[x].get('display_name')} (@{x})"
    )

    if selected_u:
        u_info = users[selected_u]
        st.markdown("---")
        with st.container(border=True):
            st.markdown(f"### 👤 User Dossier: **{u_info.get('display_name')}** (`@{selected_u}`)")
            
            c_a1, c_a2, c_a3 = st.columns(3)
            c_a1.write(f"📧 **Email:** `{u_info.get('email', 'N/A')}`\n\n🏈 **Fav Team:** `{u_info.get('favorite_team', 'NFL')}`")
            c_a2.write(f"🗓️ **Joined:** `{u_info.get('created_at', 'N/A')}`\n\n⏱️ **Last Login:** `{u_info.get('last_login', 'N/A')}`")
            c_a3.write(f"Status: **{'🚫 BANNED' if u_info.get('is_banned') else '✅ Active'}**\n\nRole: **{'👑 Admin' if u_info.get('is_admin') else '👤 Member'}**")

            searches = u_info.get("searches", [])
            st.markdown("##### 🔍 Recent Matchup & Team Searches:")
            if searches:
                st.write(", ".join([f"`{s}`" for s in searches[-15:]]))
            else:
                st.caption("No search queries logged.")

            u_clean = selected_u.lower()
            u_bets = [b for b in st.session_state.saved_bets if b.get("user", "").strip().lower() == u_clean or b.get("user", "").strip().lower() == u_info.get("display_name", "").strip().lower()]
            
            st.markdown(f"##### 📊 Betting Portfolio ({len(u_bets)} Tickets Locked In):")
            u_won = [b for b in u_bets if b.get("status") == "Won"]
            u_lost = [b for b in u_bets if b.get("status") == "Lost"]
            u_profit = sum(float(b.get("payout_dollars", 0)) - float(b.get("risk_dollars", 0)) for b in u_won) - sum(float(b.get("risk_dollars", 0)) for b in u_lost)
            
            p_col1, p_col2, p_col3 = st.columns(3)
            p_col1.metric("Tickets Placed", len(u_bets))
            p_col2.metric("Record", f"{len(u_won)}W - {len(u_lost)}L")
            p_col3.metric("Net P&L", f"${u_profit:+.2f}")

            with st.expander(f"📜 View All Tickets Placed by {u_info.get('display_name')}"):
                if not u_bets:
                    st.info("No tickets locked in yet.")
                else:
                    for ub in u_bets:
                        st.markdown(f"• **{ub.get('date')}** — `{ub.get('matchup')}`: **{ub.get('bet')}** | Stake: ${ub.get('risk_dollars', 10):.2f} | Status: `{ub.get('status')}`")

            if selected_u != "flurk":
                st.markdown("##### ⚙️ Administrative Actions:")
                act1, act2 = st.columns(2)
                with act1:
                    ban_label = "✅ Unban Account" if u_info.get("is_banned") else "🚫 Ban Account"
                    if st.button(ban_label, key=f"ban_btn_{selected_u}"):
                        u_info["is_banned"] = not u_info.get("is_banned", False)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots)
                        st.rerun()
                with act2:
                    if st.button("🗑️ Delete User Permanently", key=f"del_user_btn_{selected_u}"):
                        users.pop(selected_u)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots)
                        st.rerun()
