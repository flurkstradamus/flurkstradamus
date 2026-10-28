import streamlit as st
import requests
import re
import random
import string
from datetime import datetime, timezone, timedelta
import streamlit.components.v1 as components

# Modular engines
try:
    from config import DEFAULT_LOGO
    from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob
    from database import (
        load_storage, save_all_storage, find_game_for_bet, auto_resolve_bets,
        hash_password, get_admin_credentials, send_verification_email
    )
    from football_engine import fetch_football_scoreboard, get_live_football_roster
    from basketball_engine import fetch_nba_scoreboard, get_live_nba_roster
except Exception as import_err:
    st.error(f"Error loading system engines: {import_err}")
    st.stop()

st.set_page_config(
    page_title="Flurkstradamus: Sports Betting Analytics & Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# GA4 Component Injection
def inject_google_analytics():
    ga_id = st.secrets.get("GA_MEASUREMENT_ID")
    if not ga_id:
        return
    ga_snippet = f"""
    <script>
        (function() {{
            const win = window.parent;
            const doc = win.document;
            if (!doc.getElementById('ga-gtag-script')) {{
                const script = doc.createElement('script');
                script.id = 'ga-gtag-script';
                script.async = true;
                script.src = 'https://www.googletagmanager.com/gtag/js?id={ga_id}';
                doc.head.appendChild(script);

                win.dataLayer = win.dataLayer || [];
                function gtag() {{ win.dataLayer.push(arguments); }}
                gtag('js', new Date());
                gtag('config', '{ga_id}', {{
                    'page_title': doc.title,
                    'page_location': win.location.href
                }});
            }}
        }})();
    </script>
    """
    components.html(ga_snippet, height=0)

inject_google_analytics()

# Global styling
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
        .dashboard-header-desktop { display: block !important; }
        .dashboard-header-mobile { display: none !important; }
    }
    @media (max-width: 767px) {
        .block-container {
            padding-top: 2.2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        .dashboard-header-desktop { display: none !important; }
        .dashboard-header-mobile {
            display: block !important;
            font-size: 1.45rem !important;
            font-weight: 700 !important;
            margin-bottom: 0.3rem !important;
        }
    }
    a.header-anchor, a[data-testid="stHeaderAnchor"] { display: none !important; }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.2rem !important; }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        text-align: left !important;
        justify-content: flex-start !important;
        display: flex !important;
        align-items: center !important;
        padding-left: 14px !important;
        min-height: 2.1rem !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

def get_current_et_time():
    utc_now = datetime.now(timezone.utc)
    return utc_now - timedelta(hours=4)

def round_half_point(val):
    try:
        return round(float(val) * 2.0) / 2.0
    except (ValueError, TypeError):
        return 47.5

def calculate_live_bet_prob(bet_obj, live_m):
    if not live_m:
        return bet_obj.get("win_prob", "50.0%")
    stat_val = bet_obj.get("status", "Pending")
    is_fin = live_m.get("completed", False) or "final" in live_m.get("status", "").lower()
    if is_fin:
        return "100.0%" if stat_val == "Won" else "0.0%"

    curr_away = live_m.get("away_score", 0)
    curr_home = live_m.get("home_score", 0)
    curr_tot = curr_away + curr_home
    t_line = bet_obj.get("target_line")
    b_side = bet_obj.get("bet_direction", "Under")
    b_cat = bet_obj.get("bet_category", "Total")
    period = live_m.get("period", 1)
    is_nba = (live_m.get("league") == "NBA")

    if not (live_m.get("state_text") != "pre" and period > 0):
        return bet_obj.get("win_prob", "50.0%")

    if "Total" in b_cat and t_line:
        sigma = (8.0 if period >= 3 else 14.0) if is_nba else (3.5 if period >= 3 else 6.0)
        rem_proj = (54.0 if period >= 3 else 110.0) if is_nba else (14.0 if period >= 3 else 24.0)
        p = calculate_win_prob(t_line, curr_tot + rem_proj, sigma, is_under=(b_side == "Under"))
        return f"{p * 100:.1f}%"
    elif b_cat == "Moneyline":
        add_pts = 40 if is_nba else 14
        h_prob = calculate_moneyline_prob(curr_home + add_pts, curr_away + add_pts, live_m.get("home_record", "0-0"), live_m.get("away_record", "0-0"))
        p = h_prob if bet_obj.get("picked_team") == live_m.get("home_team") else (1.0 - h_prob)
        return f"{p * 100:.1f}%"
    elif "Spread" in b_cat and t_line:
        margin = curr_home - curr_away
        diff = margin if bet_obj.get("picked_team") == live_m.get("home_team") else -margin
        p = calculate_spread_prob(diff, t_line, std_dev=(7.5 if is_nba else 5.0))
        return f"{p * 100:.1f}%"
    return bet_obj.get("win_prob", "52.0%")

def get_numeric_prob(bet_obj, games_data):
    is_combo = (bet_obj.get("bet_category") == "Combo" or "Leg" in bet_obj.get("type", ""))
    if is_combo:
        compound_p = 1.0
        legs_list = bet_obj.get("parsed_legs", [])
        if not legs_list:
            raw_str = str(bet_obj.get("win_prob", "50.0%")).replace("%", "").strip()
            try: return float(raw_str) / 100.0
            except: return 0.50
        for l_item in legs_list:
            m_g = find_game_for_bet({"matchup": l_item.get("matchup", "")}, games_data)
            p_str = calculate_live_bet_prob({
                "status": bet_obj.get("status"),
                "target_line": l_item.get("line"),
                "bet_direction": l_item.get("side"),
                "bet_category": l_item.get("type"),
                "picked_team": l_item.get("picked_team"),
                "win_prob": "65.0%"
            }, m_g)
            try: compound_p *= (float(p_str.replace("%", "").strip()) / 100.0)
            except: compound_p *= 0.50
        return max(0.001, min(0.999, compound_p))
    else:
        live_m = find_game_for_bet(bet_obj, games_data)
        p_str = calculate_live_bet_prob(bet_obj, live_m)
        try: return max(0.001, min(0.999, float(p_str.replace("%", "").strip()) / 100.0))
        except: return 0.50

def render_ticket_card(b, real_idx, games_data, can_delete=False):
    status_val = b.get("status", "Pending")
    is_combo = (b.get("bet_category") == "Combo" or "Leg" in b.get("type", ""))

    if is_combo:
        compound_p = 1.0
        for l_item in b.get("parsed_legs", []):
            m_g = find_game_for_bet({"matchup": l_item.get("matchup", "")}, games_data)
            p_str = calculate_live_bet_prob({"status": b.get("status"), "target_line": l_item.get("line"), "bet_direction": l_item.get("side"), "bet_category": l_item.get("type"), "picked_team": l_item.get("picked_team"), "win_prob": "65.0%"}, m_g)
            try: compound_p *= (float(p_str.replace("%", "")) / 100.0)
            except: compound_p *= 0.5
        live_prob_str = f"{compound_p * 100:.1f}%"
        live_m = None
    else:
        live_m = find_game_for_bet(b, games_data)
        live_prob_str = calculate_live_bet_prob(b, live_m)

    game_started = False
    if live_m:
        chk = live_m.get("checkpoint", "")
        stt = live_m.get("status", "").lower()
        game_started = ("pre" not in chk.lower()) and ("pm" not in stt and "am" not in stt)

    badge = "<span style='background-color:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;'>🏆 WON</span>" if status_val == "Won" else \
            ("<span style='background-color:#ef4444;color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;'>❌ LOST</span>" if status_val == "Lost" else \
            ("<span style='background-color:#eab308;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;'>⚡ IN PLAY</span>" if game_started else \
            "<span style='background-color:rgba(255,255,255,0.12);color:#94a3b8;padding:2px 8px;border-radius:12px;font-weight:700;'>⏳ SCHEDULED</span>"))

    with st.container(border=True):
        st.markdown(f"**Ticket #{real_idx+1}** | Status: {badge}", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([3.5, 3.5, 2.0, 1.2])
        c1.write(f"**Pick:** `{b.get('bet')}`\n\n🗓️ Logged: `{b.get('date', 'N/A')}`")
        r_val = float(b.get("risk_dollars", 10.0))
        p_val = float(b.get("payout_dollars", b.get("payout", 19.0)))
        profit = float(b.get("locked_profit", p_val - r_val))
        c2.write(f"Risk: **${r_val:.2f}** ➔ Return: **${p_val:.2f}**\n\nProfit: **+${profit:.2f}**")
        c3.caption(f"Type: **{b.get('bet_category', 'Single')}**\n\nLive Prob: **{live_prob_str}**")
        if c4.button("🏟️ War Room", key=f"open_tkt_{b.get('id', real_idx)}_{real_idx}", use_container_width=True):
            st.session_state.selected_bet_id = b["id"]
            st.rerun()
        if can_delete and c4.button("🗑️", key=f"del_tkt_{b.get('id', real_idx)}_{real_idx}", use_container_width=True):
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
if "pending_verify_user" not in st.session_state: st.session_state.pending_verify_user = None

b_data, c_data, u_data, banned_data, snap_data, tkt_data = load_storage()
if "saved_bets" not in st.session_state: st.session_state.saved_bets = b_data
if "chat_messages" not in st.session_state: st.session_state.chat_messages = c_data
if "user_accounts" not in st.session_state: st.session_state.user_accounts = u_data
if "banned_emails" not in st.session_state: st.session_state.banned_emails = banned_data
if "game_snapshots" not in st.session_state: st.session_state.game_snapshots = snap_data
if "support_tickets" not in st.session_state: st.session_state.support_tickets = tkt_data

# URL Persistent Token Check
token_in_url = st.query_params.get("auth_token") or st.query_params.get("session_token")
if st.session_state.logged_in_user is None and token_in_url:
    for u_obj in st.session_state.user_accounts.values():
        if u_obj.get("session_token") == token_in_url and not u_obj.get("is_banned", False) and u_obj.get("is_verified", True):
            st.session_state.logged_in_user = u_obj
            break

# Authentication Gateway
if st.session_state.logged_in_user is None:
    st.title("🔮 Flurkstradamus")
    st.caption("Algorithmic sports betting intelligence, in-game pace modeling, and automated bankroll tracking.")

    if st.session_state.pending_verify_user is not None:
        target_u = st.session_state.user_accounts.get(st.session_state.pending_verify_user)
        with st.container(border=True):
            st.markdown("### ✉️ Verify Your Email Address")
            st.write(f"A 6-digit confirmation passcode was issued for **{target_u.get('email')}**.")
            if "email_dispatch_status" in st.session_state:
                ok, msg = st.session_state.email_dispatch_status
                if ok: st.success(f"📬 {msg}")
                else: st.warning(f"⚠️ {msg} | Activation Code: `{target_u.get('verification_code')}`")
            elif not st.secrets.get("smtp"):
                st.info(f"💡 Dev Activation Code: **`{target_u.get('verification_code')}`**")

            with st.form("verify_form"):
                code_in = st.text_input("Enter 6-Digit Code", placeholder="123456").strip()
                if st.form_submit_button("Verify & Activate", use_container_width=True):
                    if code_in == target_u.get("verification_code"):
                        target_u["is_verified"] = True
                        target_u["verification_code"] = None
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                        st.session_state.logged_in_user = target_u
                        st.session_state.pending_verify_user = None
                        st.session_state.pop("email_dispatch_status", None)
                        st.rerun()
                    else:
                        st.error("Invalid verification code.")
            if st.button("Cancel & Return to Login", use_container_width=True):
                st.session_state.pending_verify_user = None
                st.rerun()
        st.stop()

    tab_login, tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])
    with tab_login:
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
                    if not matched.get("is_verified", True):
                        st.session_state.pending_verify_user = matched["username"].lower()
                        st.rerun()
                    matched["session_token"] = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    if rem: st.query_params["auth_token"] = matched["session_token"]
                    st.session_state.logged_in_user = matched
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    with tab_signup:
        with st.form("signup_form"):
            nu = st.text_input("Username").strip().lower()
            ne = st.text_input("Email").strip().lower()
            np1 = st.text_input("Password", type="password")
            np2 = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Sign Up", use_container_width=True):
                if nu and ne and np1 == np2 and len(np1) >= 4:
                    code = ''.join(random.choices(string.digits, k=6))
                    new_u = {
                        "username": nu, "email": ne, "display_name": nu,
                        "password_hash": hash_password(np1), "is_admin": False, "is_banned": False,
                        "is_verified": False, "verification_code": code, "session_token": ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    }
                    st.session_state.user_accounts[nu] = new_u
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    sent_ok, s_msg = send_verification_email(ne, code)
                    st.session_state.email_dispatch_status = (sent_ok, s_msg)
                    st.session_state.pending_verify_user = nu
                    st.rerun()
                else:
                    st.error("Fill all fields and ensure passwords match.")
    st.stop()

# Active Context
curr_user = st.session_state.logged_in_user
active_uname = curr_user.get("username", "bettor").lower()
is_admin = curr_user.get("is_admin", False)

st.sidebar.markdown(f"## 🔮 Flurkstradamus")
st.sidebar.caption(f"Logged in as **@{active_uname}**")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in_user = None
    st.query_params.clear()
    st.rerun()

st.sidebar.markdown("---")
league_choice = st.sidebar.radio("Primary League", ["NBA", "NFL", "NCAA Football", "All Games"])

# Ingest Game Data through Dedicated Engines
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
    "💬 The Locker Room", "💡 How It Works", "📖 Model Methodology & Math",
    "⚙️ Account Settings", "📩 Feedback & Support", "ℹ️ About Flurkstradamus"
]
if is_admin: nav_list.append("🛡️ Admin")

for page in nav_list:
    btn_type = "primary" if (st.session_state.active_nav_page == page and st.session_state.selected_bet_id is None) else "secondary"
    if st.sidebar.button(page, key=f"nav_{page}", type=btn_type, use_container_width=True):
        st.session_state.selected_bet_id = None
        st.session_state.active_nav_page = page
        st.rerun()

menu_choice = st.session_state.active_nav_page

# WAR ROOM VIEW
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)
    if st.button("⬅️ Back", use_container_width=True) or not selected_bet:
        st.session_state.selected_bet_id = None
        st.rerun()

    live_g = find_game_for_bet(selected_bet, games_data)
    live_p = calculate_live_bet_prob(selected_bet, live_g)
    st.title(f"🏟️ War Room: {selected_bet.get('matchup')}")
    st.write(f"**Pick:** `{selected_bet.get('bet')}` | Live Probability: **{live_p}**")
    if live_g:
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.metric(live_g['away_short'], live_g['away_score'])
        c2.metric("Clock", live_g.get('displayClock', live_g['status']))
        c3.metric(live_g['home_short'], live_g['home_score'])
    st.stop()

# =========================================================================
# 1. DASHBOARD
# =========================================================================
if menu_choice == "📊 My Dashboard":
    st.subheader("📊 Multi-Sport Betting Dashboard")
    my_bets = [b for b in st.session_state.saved_bets if str(b.get("user", "")).lower() in [active_uname, curr_user.get("display_name", "").lower()]]
    if not my_bets:
        st.info("No tickets recorded yet.")
    else:
        won = [b for b in my_bets if b.get("status") == "Won"]
        lost = [b for b in my_bets if b.get("status") == "Lost"]
        pending = [b for b in my_bets if b.get("status") == "Pending"]
        tot_won = sum(float(b.get("locked_profit", 0)) for b in won)
        tot_lost = sum(float(b.get("risk_dollars", 0)) for b in lost)
        pending_risk = sum(float(b.get("risk_dollars", 0)) for b in pending)
        pending_max = sum(float(b.get("locked_profit", 0)) for b in pending)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Bets", len(my_bets))
        k2.metric("Money Won", f"${tot_won:.2f}")
        k3.metric("Money Lost", f"${tot_lost:.2f}")
        k4.metric("Net Profit / Loss", f"${tot_won - tot_lost:+.2f}")

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Capital at Risk", f"${pending_risk:.2f}")
        p2.metric("Max Potential Profit", f"+${pending_max:.2f}")
        p3.metric("Pending In Play", len(pending))
        p4.metric("Win Rate", f"{(len(won) / max(len(won) + len(lost), 1)) * 100:.1f}%")

# =========================================================================
# 2. SINGLE GAME ENGINE
# =========================================================================
elif menu_choice == "⚡ Single Game Engine":
    st.subheader("⚡ Single Game Analytics Engine")
    pool = games_data
    if not pool:
        st.info("No games active for selected league.")
        st.stop()

    game_opts = [f"[{g['kickoff']}] [{g['league']}] {g['away_short']} @ {g['home_short']}" for g in pool]
    sel_idx = st.selectbox("Select Matchup", range(len(game_opts)), format_func=lambda x: game_opts[x])
    g = pool[sel_idx]
    is_nba = (g["league"] == "NBA")

    c1, c2 = st.columns(2)
    c1.metric(f"{g['away_short']} Score", g['away_score'])
    c2.metric(f"{g['home_short']} Score", g['home_score'])

    # Pull Sport-Specific Rosters
    if is_nba:
        h_players = get_live_nba_roster(g["home_id"] or g["home_short"])
        a_players = get_live_nba_roster(g["away_id"] or g["away_short"])
    else:
        h_players = get_live_football_roster(g["home_id"] or g["home_short"], g["league"])
        a_players = get_live_football_roster(g["away_id"] or g["away_short"], g["league"])

    with st.expander("🤖 AI Strategy Cards", expanded=True):
        st.write(f"Pace Projections & Edge Cards active for **{g['name']}**.")
        if is_nba and h_players:
            p_name, p_pos, p_val = h_players[0]
            st.success(f"🎯 Top Prop: **{p_name} ({p_pos}) Over {p_val} Points** (-110)")
        elif h_players:
            p_name, p_pos = h_players[0][:2]
            st.success(f"🎯 Top Touchdown Prop: **{p_name} ({p_pos}) Any Time TD** (+105)")

    with st.form("lock_in_form"):
        st.markdown("#### 📝 Lock In Ticket")
        w_types = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"]
        if is_nba: w_types.append("Player Points Prop")
        else: w_types.append("Player Anytime Touchdown Scorer")

        bet_t = st.radio("Market", w_types, horizontal=True)
        picked_player = None
        side_val = "Under"
        line_val = float(g["market_ou"])

        if bet_t == "Player Points Prop":
            all_roster = [p[0] for p in (h_players + a_players)]
            picked_player = st.selectbox("Player", all_roster)
            side_val = st.selectbox("Side", ["Over", "Under"])
            line_val = st.number_input("Points Line", value=22.5, step=0.5)
        elif bet_t == "Player Anytime Touchdown Scorer":
            all_roster = [p[0] for p in (h_players + a_players)]
            picked_player = st.selectbox("Player", all_roster)
            side_val = "TD"
            line_val = 1.0
        elif bet_t == "Game Total":
            side_val = st.selectbox("Side", ["Under", "Over"])
            line_val = st.number_input("Total Line", value=float(g["market_ou"]), step=0.5)
        elif bet_t == "Point Spread (ATS)":
            picked_player = st.selectbox("Covering Team", [g["home_team"], g["away_team"]])
            side_val = "Spread"
            line_val = st.number_input("Spread Line", value=float(g["market_spread"]), step=0.5)
        else:
            picked_player = st.selectbox("Moneyline Winner", [g["home_team"], g["away_team"]])
            side_val = "Moneyline"
            line_val = None

        col_r, col_p = st.columns(2)
        r_in = col_r.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        p_in = col_p.number_input("Payout ($)", min_value=1.0, value=19.10, step=5.0)

        if st.form_submit_button("Lock In Bet Slip", use_container_width=True):
            lbl = f"{picked_player} {side_val} {line_val} Pts" if bet_t == "Player Points Prop" else \
                  (f"{picked_player} TD" if bet_t == "Player Anytime Touchdown Scorer" else \
                  (f"{side_val} {line_val}" if line_val is not None else f"{picked_player} ML"))

            tkt = {
                "id": str(datetime.now().timestamp()),
                "user": active_uname,
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                "type": "Single",
                "bet_category": bet_t,
                "home_team": g["home_team"],
                "away_team": g["away_team"],
                "picked_team": picked_player,
                "matchup": f"{g['away_short']} @ {g['home_short']}",
                "bet": lbl,
                "target_line": line_val,
                "bet_direction": side_val,
                "risk_dollars": float(r_in),
                "payout_dollars": float(p_in),
                "locked_profit": float(p_in) - float(r_in),
                "status": "Pending",
                "notes": f"[{g['league']}] {bet_t}"
            }
            st.session_state.saved_bets.insert(0, tkt)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success(f"Ticket Locked: {lbl}")
            st.rerun()

# =========================================================================
# 3. COMBO BUILDER
# =========================================================================
elif menu_choice == "🔗 Multi-Leg Combo Builder":
    st.subheader("🔗 Multi-Leg Cross-Sport Combo Builder")
    if not games_data:
        st.info("No active games available.")
        st.stop()

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in games_data]
    if not st.session_state.combo_active_legs:
        st.session_state.combo_active_legs = [{"idx": 0, "side": "Under", "line": float(games_data[0]["market_ou"])}]

    if st.button("➕ Add Leg", use_container_width=True, disabled=len(st.session_state.combo_active_legs) >= 12):
        st.session_state.combo_active_legs.append({"idx": 0, "side": "Under", "line": float(games_data[0]["market_ou"])})
        st.rerun()

    legs_payload = []
    comp_prob = 1.0
    for i, leg in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            s_idx = st.selectbox(f"Leg {i+1} Matchup", range(len(choices)), index=min(leg["idx"], len(choices)-1), format_func=lambda x: choices[x], key=f"leg_{i}")
            g_leg = games_data[s_idx]
            side_sel = st.selectbox(f"Side (Leg {i+1})", ["Under", "Over"], key=f"side_{i}")
            line_sel = st.number_input(f"Line (Leg {i+1})", value=float(g_leg["market_ou"]), step=0.5, key=f"line_{i}")
            legs_payload.append({"matchup": f"{g_leg['away_short']} @ {g_leg['home_short']}", "type": "Game Total", "side": side_sel, "line": line_sel})
            comp_prob *= 0.52

    st.metric("Compound Win Expectancy", f"{comp_prob * 100:.1f}%")
    with st.form("combo_form"):
        cr = st.number_input("Risk ($)", value=10.0, step=5.0)
        cp = st.number_input("Payout ($)", value=50.0, step=10.0)
        if st.form_submit_button("Lock In Combo"):
            c_tkt = {
                "id": str(datetime.now().timestamp()),
                "user": active_uname,
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                "type": f"{len(legs_payload)}-Leg Combo",
                "bet_category": "Combo",
                "matchup": " | ".join([f"{l['matchup']} ({l['side']} {l['line']})" for l in legs_payload]),
                "bet": f"{len(legs_payload)} Legs Parlay",
                "risk_dollars": float(cr),
                "payout_dollars": float(cp),
                "locked_profit": float(cp) - float(cr),
                "status": "Pending",
                "parsed_legs": legs_payload
            }
            st.session_state.saved_bets.insert(0, c_tkt)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success("Combo slip locked in!")
            st.rerun()

# =========================================================================
# 4. LOCKED BETS HISTORY
# =========================================================================
elif menu_choice == "📜 Locked Bets History":
    st.subheader("📜 Locked Bets History")
    my_tkts = [b for b in st.session_state.saved_bets if str(b.get("user", "")).lower() in [active_uname, curr_user.get("display_name", "").lower()]]
    if not my_tkts: st.info("No bets placed yet.")
    else:
        for idx, b in enumerate(my_tkts):
            render_ticket_card(b, st.session_state.saved_bets.index(b), games_data, can_delete=True)

# =========================================================================
# 5. LEADERBOARD
# =========================================================================
elif menu_choice == "🏆 Leaderboard":
    st.subheader("🏆 Leaderboard")
    stats = {}
    for b in st.session_state.saved_bets:
        u = str(b.get("user", "bettor")).lower()
        if u not in stats: stats[u] = {"name": u, "won": 0, "lost": 0, "net": 0.0}
        if b.get("status") == "Won":
            stats[u]["won"] += 1
            stats[u]["net"] += float(b.get("locked_profit", 0))
        elif b.get("status") == "Lost":
            stats[u]["lost"] += 1
            stats[u]["net"] -= float(b.get("risk_dollars", 0))

    for item in sorted(stats.values(), key=lambda x: x["net"], reverse=True):
        st.write(f"**@{item['name']}** — Profit: **${item['net']:+.2f}** ({item['won']}W - {item['lost']}L)")

# =========================================================================
# 6. SQUAD FEED
# =========================================================================
elif menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    for idx, b in enumerate(st.session_state.saved_bets[:25]):
        render_ticket_card(b, idx, games_data, can_delete=False)

# =========================================================================
# 7. THE LOCKER ROOM
# =========================================================================
elif menu_choice == "💬 The Locker Room":
    st.subheader("💬 The Locker Room")
    with st.form("chat_form"):
        m_in = st.text_input("Message")
        if st.form_submit_button("Send") and m_in.strip():
            st.session_state.chat_messages.insert(0, {"user": active_uname, "text": m_in.strip(), "time": get_current_et_time().strftime("%I:%M %p ET")})
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.rerun()
    for m in st.session_state.chat_messages[:20]:
        st.write(f"**@{m.get('user')}**: {m.get('text')}")

# =========================================================================
# 8. HOW IT WORKS
# =========================================================================
elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: Multi-Sport Edge Engine")
    st.markdown("""
    * **🏀 NBA & Football Coverage**: Automatically streams live slates across **NBA, NFL, and NCAA Football**.
    * **🎯 Dynamic NBA Points Props**: Pulls real-time rosters from live ESPN endpoints to surface **Player Over/Under X Points** proposition bets.
    * **📊 Real-time Bankroll Dashboard**: Comprehensive telemetry for your realized P&L, expected return (EV), and open risk capital.
    * **🔗 Multi-Leg Cross-Sport Builder**: Construct up to 12-leg parlays combining NBA and football matchups with compound probability modeling.
    """)

# =========================================================================
# 9. METHODOLOGY & MATH
# =========================================================================
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Mathematical Architecture")
    st.latex(r"Z = \frac{\text{Line} - \mu_{\text{in-game}}}{\sigma_{\text{decay}}}")
    st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")

# =========================================================================
# 10. SETTINGS
# =========================================================================
elif menu_choice == "⚙️ Account Settings":
    st.subheader("⚙️ Account Settings")
    with st.form("settings_form"):
        fav = st.text_input("Favorite Team", value=curr_user.get("favorite_team", "NBA/NFL"))
        p1 = st.text_input("New Password", type="password")
        if st.form_submit_button("Save"):
            curr_user["favorite_team"] = fav
            if p1 and len(p1) >= 4: curr_user["password_hash"] = hash_password(p1)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success("Settings updated!")

# =========================================================================
# 11. FEEDBACK & SUPPORT
# =========================================================================
elif menu_choice == "📩 Feedback & Support":
    st.subheader("📩 Feedback & Support")
    with st.form("tkt_form"):
        cat = st.selectbox("Category", ["🏀 NBA Request", "🏈 Football Request", "🐛 Bug Report", "💬 General"])
        sub = st.text_input("Subject")
        det = st.text_area("Details")
        if st.form_submit_button("Submit"):
            if sub and det:
                t = {"id": f"TKT-{random.randint(100,999)}", "user": active_uname, "category": cat, "subject": sub, "details": det, "status": "Open", "reply": ""}
                st.session_state.support_tickets.insert(0, t)
                save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                st.success("Support ticket sent!")

# =========================================================================
# 12. ABOUT
# =========================================================================
elif menu_choice == "ℹ️ About Flurkstradamus":
    st.subheader("ℹ️ About Flurkstradamus")
    st.markdown("""
    * **Developer**: Adam Sowers
    * **Firm**: Sowers Web Technologies
    * **Location**: Altamonte Springs, Florida
    * **Website**: [sweetcustomwebsites.com](https://sweetcustomwebsites.com)
    """)

# =========================================================================
# 13. ADMIN CONSOLE
# =========================================================================
elif menu_choice == "🛡️ Admin" and is_admin:
    st.subheader("🛡️ Commissioner Admin Console")
    st.write(f"Total Users: **{len(st.session_state.user_accounts)}**")
    for tkt in st.session_state.support_tickets:
        st.write(f"**[{tkt.get('id')}] {tkt.get('subject')}** (@{tkt.get('user')})")
