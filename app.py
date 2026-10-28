import streamlit as st
import random
import string
from datetime import datetime, timezone, timedelta

# Import modules
from config import DEFAULT_LOGO
from database import (
    load_storage, save_all_storage, find_game_for_bet, auto_resolve_bets,
    hash_password, get_admin_credentials, send_verification_email
)
from sports import fetch_football_scoreboard, fetch_nba_scoreboard
from views.dashboard import render_dashboard
from views.single_game import render_single_game
from views.combo_builder import render_combo_builder
from views.history import render_history
from views.leaderboard import render_leaderboard, render_squad_feed
from views.settings import render_settings, render_support
from views.guides import render_how_it_works, render_math, render_about
from views.admin import render_admin

st.set_page_config(
    page_title="Flurkstradamus: Sports Betting Analytics & Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# GA4 Component Injection
def inject_google_analytics():
    ga_id = st.secrets.get("GA_MEASUREMENT_ID")
    if not ga_id: return
    import streamlit.components.v1 as components
    components.html(f"""
    <script>
        (function() {{
            const win = window.parent; const doc = win.document;
            if (!doc.getElementById('ga-gtag-script')) {{
                const script = doc.createElement('script'); script.id = 'ga-gtag-script';
                script.async = true; script.src = 'https://www.googletagmanager.com/gtag/js?id={ga_id}';
                doc.head.appendChild(script);
                win.dataLayer = win.dataLayer || [];
                function gtag() {{ win.dataLayer.push(arguments); }}
                gtag('js', new Date()); gtag('config', '{ga_id}');
            }}
        }})();
    </script>
    """, height=0)

inject_google_analytics()

# CSS Layout & Left Alignment
st.markdown("""
<style>
    @media (min-width: 768px) {
        .block-container { padding-top: 4.5rem !important; padding-bottom: 3rem !important; padding-left: 2.5rem !important; padding-right: 2.5rem !important; max-width: 1200px !important; }
        .dashboard-header-desktop { display: block !important; }
        .dashboard-header-mobile { display: none !important; }
    }
    @media (max-width: 767px) {
        .block-container { padding-top: 2.2rem !important; padding-bottom: 2rem !important; padding-left: 0.6rem !important; padding-right: 0.6rem !important; }
        .dashboard-header-desktop { display: none !important; }
        .dashboard-header-mobile { display: block !important; font-size: 1.45rem !important; font-weight: 700 !important; margin-bottom: 0.3rem !important; }
    }
    a.header-anchor, a[data-testid="stHeaderAnchor"] { display: none !important; }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.25rem !important; }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        text-align: left !important; justify-content: flex-start !important; display: flex !important;
        align-items: center !important; padding-left: 14px !important; min-height: 2.2rem !important;
        font-weight: 600 !important; border-radius: 6px !important; width: 100% !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button p {
        text-align: left !important; justify-content: flex-start !important; width: 100% !important; margin: 0 !important;
    }
    .rec-card-box { border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.12); background: rgba(255, 255, 255, 0.025); padding: 12px; margin-bottom: 12px; }
    .rec-header-row { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 6px; margin-bottom: 8px; }
    .rec-pick-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
    .badge-roi { background-color: #22c55e; color: #000; font-weight: 800; font-size: 0.75rem; padding: 2px 7px; border-radius: 4px; }
    .badge-prob { background-color: rgba(255, 255, 255, 0.08); padding: 2px 7px; border-radius: 4px; font-weight: 700; font-size: 0.78rem; }
</style>
""", unsafe_allow_html=True)

def get_current_et_time():
    return datetime.now(timezone.utc) - timedelta(hours=4)

def calculate_live_bet_prob(bet_obj, live_m):
    if not live_m: return bet_obj.get("win_prob", "50.0%")
    stat_val = bet_obj.get("status", "Pending")
    is_fin = live_m.get("completed", False) or "final" in live_m.get("status", "").lower()
    if is_fin: return "100.0%" if stat_val == "Won" else "0.0%"
    return bet_obj.get("win_prob", "52.0%")

def get_numeric_prob(bet_obj, games_data):
    live_m = find_game_for_bet(bet_obj, games_data)
    p_str = calculate_live_bet_prob(bet_obj, live_m)
    try: return max(0.001, min(0.999, float(str(p_str).replace("%", "").strip()) / 100.0))
    except: return 0.50

def render_ticket_card(b, real_idx, games_data, can_delete=False):
    status_val = b.get("status", "Pending")
    badge_html = "<span style='background-color:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;'>🏆 WON</span>" if status_val == "Won" else \
                 ("<span style='background-color:#ef4444;color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;'>❌ LOST</span>" if status_val == "Lost" else \
                 "<span style='background-color:rgba(255,255,255,0.12);color:#94a3b8;padding:2px 8px;border-radius:12px;font-weight:700;'>⏳ PENDING</span>")

    with st.container(border=True):
        st.markdown(f"**Ticket #{real_idx+1}** | Status: {badge_html} | **{b.get('bet')}**", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([3.5, 3.5, 2.0, 1.2])
        r = float(b.get("risk_dollars", 10.0))
        p = float(b.get("payout_dollars", b.get("payout", 19.0)))
        c1.write(f"Matchup: `{b.get('matchup', 'Game')}`\n\n🗓️ `{b.get('date', 'N/A')}`")
        c2.write(f"Risk: **${r:.2f}** ➔ Return: **${p:.2f}**\n\nProfit: **+${b.get('locked_profit', p-r):.2f}**")
        c3.caption(f"Type: {b.get('bet_category', 'Single')}")
        if c4.button("🏟️ War Room", key=f"wr_{b.get('id', real_idx)}_{real_idx}", use_container_width=True):
            st.session_state.selected_bet_id = b["id"]
            st.rerun()
        if can_delete and c4.button("🗑️", key=f"del_{b.get('id', real_idx)}_{real_idx}", use_container_width=True):
            st.session_state.saved_bets.pop(real_idx)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.rerun()

# State initialization
if "logged_in_user" not in st.session_state: st.session_state.logged_in_user = None
if "selected_bet_id" not in st.session_state: st.session_state.selected_bet_id = None
if "combo_active_legs" not in st.session_state: st.session_state.combo_active_legs = []
if "active_nav_page" not in st.session_state: st.session_state.active_nav_page = "📊 My Dashboard"
if "single_selected_idx" not in st.session_state: st.session_state.single_selected_idx = 0
if "single_applied_pick" not in st.session_state: st.session_state.single_applied_pick = None
if "single_form_version" not in st.session_state: st.session_state.single_form_version = 0
if "pending_verify_user" not in st.session_state: st.session_state.pending_verify_user = None

b_data, c_data, u_data, banned_data, snap_data, tkt_data = load_storage()
if "saved_bets" not in st.session_state: st.session_state.saved_bets = b_data
if "chat_messages" not in st.session_state: st.session_state.chat_messages = c_data
if "user_accounts" not in st.session_state: st.session_state.user_accounts = u_data
if "banned_emails" not in st.session_state: st.session_state.banned_emails = banned_data
if "game_snapshots" not in st.session_state: st.session_state.game_snapshots = snap_data
if "support_tickets" not in st.session_state: st.session_state.support_tickets = tkt_data

# URL token check
token_in_url = st.query_params.get("auth_token") or st.query_params.get("session_token")
if st.session_state.logged_in_user is None and token_in_url:
    for u_obj in st.session_state.user_accounts.values():
        if u_obj.get("session_token") == token_in_url and not u_obj.get("is_banned", False) and u_obj.get("is_verified", True):
            st.session_state.logged_in_user = u_obj
            break

# Authentication
if st.session_state.logged_in_user is None:
    st.title("🔮 Flurkstradamus")
    st.caption("Algorithmic sports betting intelligence, in-game pace modeling, and automated bankroll tracking.")
    t_login, t_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])
    with t_login:
        with st.form("login_form"):
            u_in = st.text_input("Username or Email").strip().lower()
            p_in = st.text_input("Password", type="password")
            rem = st.checkbox("Remember me", value=True)
            if st.form_submit_button("Sign In", use_container_width=True):
                admin_cred = get_admin_credentials()
                if u_in in [admin_cred["username"].lower(), admin_cred["email"].lower()] and p_in == admin_cred["password"]:
                    admin_k = admin_cred["username"].lower()
                    admin_p = st.session_state.user_accounts.get(admin_k, {"username": admin_cred["username"], "is_admin": True, "is_verified": True})
                    admin_p["session_token"] = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    st.session_state.user_accounts[admin_k] = admin_p
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    if rem: st.query_params["auth_token"] = admin_p["session_token"]
                    st.session_state.logged_in_user = admin_p
                    st.rerun()

                matched = next((u for u in st.session_state.user_accounts.values() if u.get("username", "").lower() == u_in or u.get("email", "").lower() == u_in), None)
                if matched and matched.get("password_hash") == hash_password(p_in) and not matched.get("is_banned"):
                    matched["session_token"] = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    if rem: st.query_params["auth_token"] = matched["session_token"]
                    st.session_state.logged_in_user = matched
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    with t_signup:
        with st.form("signup_form"):
            nu = st.text_input("Username").strip().lower()
            ne = st.text_input("Email").strip().lower()
            np1 = st.text_input("Password", type="password")
            np2 = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Sign Up", use_container_width=True):
                if nu and ne and np1 == np2 and len(np1) >= 4:
                    new_u = {
                        "username": nu, "email": ne, "display_name": nu,
                        "password_hash": hash_password(np1), "is_admin": False, "is_banned": False,
                        "is_verified": True, "created_at": get_current_et_time().strftime("%Y-%m-%d"),
                        "session_token": ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    }
                    st.session_state.user_accounts[nu] = new_u
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    st.session_state.logged_in_user = new_u
                    st.rerun()
                else:
                    st.error("Please fill all fields and match passwords.")
    st.stop()

# Active Context
curr_user = st.session_state.logged_in_user
active_uname = curr_user.get("username", "bettor").lower()
is_admin = curr_user.get("is_admin", False)

st.sidebar.markdown(f"## 🔮 Flurkstradamus")
if st.sidebar.button(f"👤 {curr_user.get('display_name', active_uname)} (@{active_uname})", key="sidebar_user_profile_link"):
    st.session_state.selected_bet_id = None
    st.session_state.active_nav_page = "⚙️ Account Settings"
    st.rerun()

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in_user = None
    st.query_params.clear()
    st.rerun()

st.sidebar.markdown("---")
league_choice = st.sidebar.radio("Primary League", ["NBA", "NFL", "NCAA Football", "All Games"])
st.sidebar.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

if league_choice == "NBA":
    games_data = fetch_nba_scoreboard()
elif league_choice in ["NFL", "NCAA Football"]:
    games_data = fetch_football_scoreboard(league_choice)
else:
    games_data = fetch_nba_scoreboard() + fetch_football_scoreboard("All Games")

auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages, st.session_state.game_snapshots, st.session_state.support_tickets)

nav_list = [
    "📊 My Dashboard", "⚡ Single Game Engine", "🔗 Multi-Leg Combo Builder",
    "📜 Locked Bets History", "🏆 Leaderboard", "🔥 Live Squad Feed",
    "💡 How It Works", "📖 Model Methodology & Math", "⚙️ Account Settings",
    "📩 Feedback & Support", "ℹ️ About Flurkstradamus"
]
if is_admin: nav_list.append("🛡️ Admin")

for page in nav_list:
    btn_type = "primary" if (st.session_state.active_nav_page == page and st.session_state.selected_bet_id is None) else "secondary"
    if st.sidebar.button(page, key=f"nav_{page}", type=btn_type, use_container_width=True):
        st.session_state.selected_bet_id = None
        st.session_state.active_nav_page = page
        st.rerun()

menu_choice = st.session_state.active_nav_page

# War Room Routing
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)
    if st.button("⬅️ Back to Tickets", use_container_width=True) or not selected_bet:
        st.session_state.selected_bet_id = None
        st.rerun()
    live_g = find_game_for_bet(selected_bet, games_data)
    st.title(f"🏟️ War Room: {selected_bet.get('matchup')}")
    st.write(f"**Pick:** `{selected_bet.get('bet')}` | Status: `{selected_bet.get('status')}`")
    if live_g:
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.metric(live_g['away_short'], live_g['away_score'])
        c2.metric("Clock", live_g.get('displayClock', live_g['status']))
        c3.metric(live_g['home_short'], live_g['home_score'])
    st.stop()

# Page Routing
if menu_choice == "📊 My Dashboard":
    render_dashboard(curr_user, active_uname, games_data, get_numeric_prob)
elif menu_choice == "⚡ Single Game Engine":
    render_single_game(curr_user, active_uname, games_data, get_current_et_time)
elif menu_choice == "🔗 Multi-Leg Combo Builder":
    render_combo_builder(curr_user, active_uname, games_data, get_current_et_time)
elif menu_choice == "📜 Locked Bets History":
    render_history(curr_user, active_uname, is_admin, games_data, render_ticket_card)
elif menu_choice == "🏆 Leaderboard":
    render_leaderboard()
elif menu_choice == "🔥 Live Squad Feed":
    render_squad_feed(games_data, render_ticket_card)
elif menu_choice == "💡 How It Works":
    render_how_it_works()
elif menu_choice == "📖 Model Methodology & Math":
    render_math()
elif menu_choice == "⚙️ Account Settings":
    render_settings(curr_user, active_uname)
elif menu_choice == "📩 Feedback & Support":
    render_support(curr_user, active_uname, is_admin, get_current_et_time)
elif menu_choice == "ℹ️ About Flurkstradamus":
    render_about()
elif menu_choice == "🛡️ Admin" and is_admin:
    render_admin()
