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

# Global styling & Left Alignment
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

    /* FORCED LEFT ALIGNMENT FOR NAVIGATION BUTTONS */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.25rem !important;
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
        padding-top: 5px !important;
        padding-bottom: 5px !important;
        min-height: 2.2rem !important;
        height: 2.2rem !important;
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

    /* SIDEBAR USERNAME BUTTON LINK */
    div[data-testid="stSidebar"] div[data-testid="stButton"]:has(button[key="sidebar_user_profile_link"]) button {
        background: transparent !important;
        border: none !important;
        padding-left: 4px !important;
        padding-top: 2px !important;
        padding-bottom: 2px !important;
        height: auto !important;
        min-height: 1.8rem !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stButton"]:has(button[key="sidebar_user_profile_link"]) button:hover {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 6px !important;
    }

    .rec-card-box {
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.025);
        padding: 12px;
        margin-bottom: 12px;
    }
    .rec-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 6px;
        margin-bottom: 8px;
    }
    .rec-matchup-meta {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.85rem;
    }
    .rec-pick-row {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 8px;
    }
    .badge-roi {
        background-color: #22c55e;
        color: #000;
        font-weight: 800;
        font-size: 0.75rem;
        padding: 2px 7px;
        border-radius: 4px;
    }
    .badge-prob {
        background-color: rgba(255, 255, 255, 0.08);
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.78rem;
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
        legs_list = b.get("parsed_legs", [])
        for l_item in legs_list:
            m_g = find_game_for_bet({"matchup": l_item.get("matchup", "")}, games_data)
            p_str = calculate_live_bet_prob({
                "status": b.get("status"),
                "target_line": l_item.get("line"),
                "bet_direction": l_item.get("side"),
                "bet_category": l_item.get("type"),
                "picked_team": l_item.get("picked_team"),
                "win_prob": "65.0%"
            }, m_g)
            try: compound_p *= (float(p_str.replace("%", "")) / 100.0)
            except: compound_p *= 0.5
        live_prob_str = f"{compound_p * 100:.1f}%"
        live_m = None
    else:
        live_m = find_game_for_bet(b, games_data)
        live_prob_str = calculate_live_bet_prob(b, live_m)

    game_started = False
    is_final = False
    if live_m:
        chk = live_m.get("checkpoint", "")
        stt = live_m.get("status", "").lower()
        game_started = ("pre" not in chk.lower()) and ("pm" not in stt and "am" not in stt)
        is_final = live_m.get("completed", False) or "final" in stt

    if status_val == "Won":
        badge_html = "<span style='background-color:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>🏆 WON</span>"
    elif status_val == "Lost":
        badge_html = "<span style='background-color:#ef4444;color:#fff;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>❌ LOST</span>"
    elif game_started:
        badge_html = "<span style='background-color:#eab308;color:#000;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>⚡ IN PLAY</span>"
    else:
        badge_html = "<span style='background-color:rgba(255,255,255,0.12);color:#94a3b8;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;'>⏳ SCHEDULED</span>"

    if is_combo:
        header_html = f"""
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:6px; margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:1.0rem; font-weight:700;">🔗 Multi-Leg Parlay ({len(b.get('parsed_legs', []))} Legs)</span>
                <span style="opacity:0.55; font-size:0.80rem;">by <strong>{b.get('user', 'Bettor')}</strong></span>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background-color:rgba(56,189,248,0.15); color:#38bdf8; font-weight:700; padding:2px 8px; border-radius:6px; font-size:0.80rem;">
                    🎲 Live Win Prob: {live_prob_str}
                </span>
                {badge_html}
            </div>
        </div>
        """
    elif live_m:
        a_sh = live_m.get("away_short", "AWAY")
        h_sh = live_m.get("home_short", "HOME")
        a_sc = live_m.get("away_score", 0)
        h_sc = live_m.get("home_score", 0)
        tot_pts = a_sc + h_sc
        status_txt = live_m.get("displayClock") or live_m.get("status")

        if game_started or is_final:
            score_badge = f"<span style='background-color:rgba(255,255,255,0.08); padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.82rem;'>{a_sh} {a_sc} - {h_sc} {h_sh} ({tot_pts} pts | {status_txt})</span>"
        else:
            score_badge = f"<span style='opacity:0.65; font-size:0.80rem;'>🗓️ {live_m.get('kickoff', status_txt)}</span>"

        header_html = f"""
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:6px; margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <img src="{live_m.get('away_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%;">
                <strong>{a_sh}</strong> <span style='opacity:0.4;'>@</span>
                <img src="{live_m.get('home_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%;">
                <strong>{h_sh}</strong>
                {score_badge}
                <span style="opacity:0.55; font-size:0.80rem; margin-left:4px;">by <strong>{b.get('user', 'Bettor')}</strong></span>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background-color:rgba(56,189,248,0.15); color:#38bdf8; font-weight:700; padding:2px 8px; border-radius:6px; font-size:0.80rem;">
                    🎲 Live Win Prob: {live_prob_str}
                </span>
                {badge_html}
            </div>
        </div>
        """
    else:
        header_html = f"""
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:6px; margin-bottom:8px;">
            <div><strong>{b.get('matchup', 'Matchup')}</strong> <span style="opacity:0.55; font-size:0.80rem;">by <strong>{b.get('user', 'Bettor')}</strong></span></div>
            <div>{badge_html}</div>
        </div>
        """

    with st.container(border=True):
        st.markdown(header_html, unsafe_allow_html=True)
        c_row1, c_row2, c_row3, c_row4 = st.columns([3.5, 3.5, 2.0, 1.2])
        with c_row1:
            st.write(f"**Pick:** `{b.get('bet')}`")
            st.caption(f"🗓️ Logged: `{b.get('date', 'N/A')}`")

        with c_row2:
            r_val = float(b.get("risk_dollars", 10.0))
            p_val = float(b.get("payout_dollars", b.get("payout", 19.0)))
            profit_locked = float(b.get("locked_profit", p_val - r_val))
            roi_pct = (profit_locked / max(r_val, 0.01)) * 100
            st.write(f"Risk: **${r_val:.2f}** ➔ Payout: **${p_val:.2f}**")
            st.markdown(f"<span style='color:#4ade80; font-size:0.82rem;'>Potential Profit: +${profit_locked:.2f} (+{roi_pct:.1f}%)</span>", unsafe_allow_html=True)

        with c_row3:
            cat_label = b.get("bet_category", b.get("type", "Single"))
            st.caption(f"Type: **{cat_label}**")
            if b.get("notes"):
                st.caption(f"*{b.get('notes')}*")

        with c_row4:
            if st.button("🏟️ War Room", key=f"open_ticket_war_{b.get('id', real_idx)}_{real_idx}", use_container_width=True):
                st.session_state.selected_bet_id = b["id"]
                st.rerun()
            if can_delete:
                if st.button("🗑️", key=f"del_ticket_{b.get('id', real_idx)}_{real_idx}", help="Delete ticket", use_container_width=True):
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

# Username link to Account Settings
if st.sidebar.button(f"👤 {curr_user.get('display_name', active_uname)} (@{active_uname})", key="sidebar_user_profile_link"):
    st.session_state.selected_bet_id = None
    st.session_state.active_nav_page = "⚙️ Account Settings"
    st.rerun()

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in_user = None
    st.query_params.clear()
    st.rerun()

st.sidebar.markdown("---")

# League Selector
league_choice = st.sidebar.radio("Primary League", ["NBA", "NFL", "NCAA Football", "All Games"])

# 30px Spacing between League Selector and Nav Menu
st.sidebar.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Ingest Game Data through Dedicated Engines
if league_choice == "NBA":
    games_data = fetch_nba_scoreboard()
elif league_choice in ["NFL", "NCAA Football"]:
    games_data = fetch_football_scoreboard(league_choice)
else:
    games_data = fetch_nba_scoreboard() + fetch_football_scoreboard("All Games")

auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages, st.session_state.game_snapshots, st.session_state.support_tickets)

nav_list = [
    "📊 My Dashboard", 
    "⚡ Single Game Engine", 
    "🔗 Multi-Leg Combo Builder",
    "📜 Locked Bets History", 
    "🏆 Leaderboard", 
    "🔥 Live Squad Feed",
    "💡 How It Works", 
    "📖 Model Methodology & Math",
    "⚙️ Account Settings", 
    "📩 Feedback & Support", 
    "ℹ️ About Flurkstradamus"
]
if is_admin: 
    nav_list.append("🛡️ Admin")

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
    if st.button("⬅️ Back to Tickets", use_container_width=True) or not selected_bet:
        st.session_state.selected_bet_id = None
        st.rerun()

    live_g = find_game_for_bet(selected_bet, games_data)
    live_p = calculate_live_bet_prob(selected_bet, live_g)
    st.title(f"🏟️ War Room: {selected_bet.get('matchup')}")
    st.caption(f"Pick: `{selected_bet.get('bet')}` | Status: `{selected_bet.get('status')}`")

    wm1, wm2, wm3, wm4, wm5 = st.columns(5)
    r_val = float(selected_bet.get("risk_dollars", 10.0))
    p_val = float(selected_bet.get("payout_dollars", selected_bet.get("payout", 19.0)))
    profit_locked = float(selected_bet.get("locked_profit", p_val - r_val))

    wm1.metric("Risk", f"${r_val:.2f}")
    wm2.metric("Payout", f"${p_val:.2f}")
    wm3.metric("Profit Potential", f"+${profit_locked:.2f}")
    wm4.metric("Status", selected_bet.get("status", "Pending"))
    wm5.metric("🎲 Live Win Prob", live_p)

    if live_g:
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.image(live_g.get("away_logo", DEFAULT_LOGO), width=45)
        c1.metric(live_g['away_short'], live_g['away_score'])
        c2.metric("Clock", live_g.get('displayClock', live_g['status']))
        c3.image(live_g.get("home_logo", DEFAULT_LOGO), width=45)
        c3.metric(live_g['home_short'], live_g['home_score'])
    st.stop()

# =========================================================================
# 1. MY DASHBOARD (FULL 12-METRIC TELEMETRY)
# =========================================================================
if menu_choice == "📊 My Dashboard":
    st.markdown('<div class="dashboard-header-desktop"><h3>📊 Personal Betting Dashboard</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-header-mobile">📊 Dashboard</div>', unsafe_allow_html=True)
    st.caption("Complete portfolio telemetry: settled P&L, live pending stakes, probability-modeled expected returns, and historical discipline.")

    clean_u = active_uname.lower()
    clean_disp = curr_user.get("display_name", "").strip().lower()
    
    my_bets = [b for b in st.session_state.saved_bets if str(b.get("user", "")).strip().lower() in [clean_u, clean_disp]]
    tot_placed = len(my_bets)

    if tot_placed == 0:
        with st.container(border=True):
            st.markdown("### 👋 Welcome! Let's Lock In Your First Edge")
            st.write("You haven't locked in any bet slips yet. Choose an engine below to start scanning live lines:")
            ob_c1, ob_c2 = st.columns(2)
            if ob_c1.button("⚡ Go to Single Game Engine", use_container_width=True):
                st.session_state.active_nav_page = "⚡ Single Game Engine"
                st.rerun()
            if ob_c2.button("🔗 Go to Multi-Leg Combo Builder", use_container_width=True):
                st.session_state.active_nav_page = "🔗 Multi-Leg Combo Builder"
                st.rerun()
    else:
        won_bets = [b for b in my_bets if b.get("status") == "Won"]
        lost_bets = [b for b in my_bets if b.get("status") == "Lost"]
        pending_bets = [b for b in my_bets if b.get("status") == "Pending"]

        tot_won_dollars = sum(float(b.get("locked_profit", float(b.get("payout_dollars", b.get("payout", 0))) - float(b.get("risk_dollars", 0)))) for b in won_bets)
        tot_lost_dollars = sum(float(b.get("risk_dollars", 0)) for b in lost_bets)
        net_pl = tot_won_dollars - tot_lost_dollars
        tot_risk = sum(float(b.get("risk_dollars", 0)) for b in my_bets if b.get("status") in ["Won", "Lost"])
        roi = (net_pl / tot_risk * 100) if tot_risk > 0 else 0.0
        avg_stake = (sum(float(b.get("risk_dollars", 0)) for b in my_bets) / tot_placed) if tot_placed > 0 else 0.0

        pending_risk_dollars = sum(float(b.get("risk_dollars", 0)) for b in pending_bets)
        pending_max_profit = sum(float(b.get("locked_profit", float(b.get("payout_dollars", b.get("payout", 0))) - float(b.get("risk_dollars", 0)))) for b in pending_bets)

        pending_expected_profit = 0.0
        sum_weighted_prob = 0.0
        pending_live_count = 0
        pending_sched_count = 0

        for b in pending_bets:
            r_amt = float(b.get("risk_dollars", 0))
            p_amt = float(b.get("payout_dollars", b.get("payout", 0)))
            net_win = float(b.get("locked_profit", p_amt - r_amt))
            prob = get_numeric_prob(b, games_data)
            
            ev_ticket = (prob * net_win) - ((1.0 - prob) * r_amt)
            pending_expected_profit += ev_ticket
            sum_weighted_prob += (prob * r_amt)

            m_check = find_game_for_bet(b, games_data)
            if m_check and m_check.get("state_text") != "pre" and m_check.get("period", 0) > 0 and not m_check.get("completed", False):
                pending_live_count += 1
            else:
                pending_sched_count += 1

        weighted_avg_prob = (sum_weighted_prob / max(pending_risk_dollars, 0.01)) * 100 if pending_risk_dollars > 0 else 0.0

        st.markdown("##### 💼 Realized Performance (Settled Slips)")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Bets Logged", tot_placed, help="All slips created under your profile.")
        k2.metric("Money Won", f"${tot_won_dollars:.2f}", help="Total net profit from settled winners.")
        k3.metric("Money Lost", f"${tot_lost_dollars:.2f}", help="Total staked capital lost on graded losses.")
        k4.metric("Net Profit / Loss", f"${net_pl:+.2f}", delta=f"{roi:+.1f}% ROI", help="Realized bankroll net profit/loss and return on investment.")

        st.markdown("##### ⏳ Active Book & Pending Analytics (In Play & Scheduled)")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Capital at Risk", f"${pending_risk_dollars:.2f}", f"{len(pending_bets)} Slips Active")
        p2.metric("Max Potential Profit", f"+${pending_max_profit:.2f}")
        p3.metric("Expected Profit (EV)", f"${pending_expected_profit:+.2f}", delta="Prob-Adjusted Return")
        p4.metric("Portfolio Win Expectancy", f"{weighted_avg_prob:.1f}%", f"{pending_live_count} Live | {pending_sched_count} Upcoming")

        st.markdown("##### 📈 Historical Discipline & Records")
        d1, d2, d3, d4 = st.columns(4)
        decided = len(won_bets) + len(lost_bets)
        win_pct = (len(won_bets) / decided * 100) if decided > 0 else 0.0
        d1.metric("Graded Win Rate", f"{win_pct:.1f}%", f"{len(won_bets)}W - {len(lost_bets)}L")
        d2.metric("Average Stake", f"${avg_stake:.2f}")
        d3.metric("Pending In Play", f"{len(pending_bets)} tickets")

        types_count = {}
        for b in my_bets:
            t = b.get("bet_category", b.get("type", "Single"))
            types_count[t] = types_count.get(t, 0) + 1
        most_common_type = max(types_count, key=types_count.get) if types_count else "None"
        d4.metric("Favorite Market", most_common_type)

        st.markdown("---")
        h1, h2 = st.columns(2)
        with h1:
            st.markdown("##### 🚀 Top Winner")
            if won_bets:
                best_win = max(won_bets, key=lambda x: float(x.get("locked_profit", float(x.get("payout_dollars", x.get("payout", 0))) - float(x.get("risk_dollars", 0)))))
                profit = float(best_win.get("locked_profit", float(best_win.get("payout_dollars", best_win.get("payout", 0))) - float(best_win.get("risk_dollars", 0))))
                payout_show = float(best_win.get("payout_dollars", best_win.get("payout", 0)))
                st.success(f"{best_win.get('bet')} on `{best_win.get('matchup')}`\n\nProfit: **+${profit:.2f}** | Return: ${payout_show:.2f}")
            else:
                st.info("No graded winning slips yet.")
        with h2:
            st.markdown("##### 💀 Toughest Beat")
            if lost_bets:
                worst_loss = max(lost_bets, key=lambda x: float(x.get("risk_dollars", 0)))
                st.error(f"{worst_loss.get('bet')} on `{worst_loss.get('matchup')}`\n\nStake Lost: **-${float(worst_loss.get('risk_dollars', 0)):.2f}**")
            else:
                st.info("No recorded losses.")

# =========================================================================
# 2. SINGLE GAME ENGINE
# =========================================================================
elif menu_choice == "⚡ Single Game Engine":
    st.subheader("⚡ Single Game Analytics Engine")

    f_col1, f_col2 = st.columns([1, 2])
    with f_col1:
        timing_view = st.selectbox("Game Status Filter", ["⏳ Upcoming Games", "⚡ Live Games", "📜 Past / Completed Games", "🌐 All Matchups"])
    with f_col2:
        search_query = st.text_input("🔍 Search Matchup or Team", placeholder="e.g. Celtics, Lakers, Eagles, Chiefs...")

    pool = games_data
    if timing_view == "⏳ Upcoming Games":
        pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
    elif timing_view == "⚡ Live Games":
        pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]
    elif timing_view == "📜 Past / Completed Games":
        pool = [g for g in pool if g.get("completed", False)]

    if search_query.strip():
        q = search_query.strip().lower()
        pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g["home_short"].lower() or q in g["away_short"].lower()]

    if pool:
        game_options = [f"[{g['kickoff']}] [{g['league']}] {g['away_short']} @ {g['home_short']}" for g in pool]
        if st.session_state.single_selected_idx >= len(game_options):
            st.session_state.single_selected_idx = 0
            
        selected_idx = st.selectbox("Select Matchup", range(len(game_options)), index=st.session_state.single_selected_idx, format_func=lambda x: game_options[x])
        st.session_state.single_selected_idx = selected_idx
        
        g = pool[selected_idx]
        g_id = g.get("id", str(selected_idx))
        g_league = g.get("league", "NFL")
        is_nba_game = (g_league == "NBA")
        detected_stage = g["checkpoint"]
        espn_ou = round_half_point(g["market_ou"])
        espn_spread = round_half_point(g["market_spread"])
    else:
        st.info("No matchups found matching your filter.")
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
        std_bracket = 14.0 if is_nba_game else 8.5
    else:
        period_weight = 0.25 if detected_stage == "Q1" else (0.50 if "half" in detected_stage.lower() else 0.75)
        expected_pts_so_far = pregame_tot * period_weight
        pace_shock_ratio = pts_scored / max(expected_pts_so_far, 1.0)
        mult = 0.90 if is_nba_game else 0.85
        if pace_shock_ratio > 1.25:
            final_proj = pregame_tot + ((pts_scored - expected_pts_so_far) * mult)
            std_bracket = 16.0 if is_nba_game else 9.5
        else:
            final_proj = pregame_tot + ((pts_scored - expected_pts_so_far) * 0.35)
            std_bracket = 11.0 if is_nba_game else 6.0

    final_proj = round_half_point(final_proj)
    delta_full = final_proj - pregame_tot
    pregame_2h = round_half_point(pregame_tot * 0.51)
    live_2h_proj = round_half_point(pregame_2h + (delta_full * 0.48))
    delta_2h = live_2h_proj - pregame_2h

    market_spd = float(espn_spread)
    pregame_proj_margin = -market_spd
    current_margin = h_pts - a_pts
    live_proj_margin = round_half_point((pregame_proj_margin * 0.40) + (current_margin * 0.60) if "half" in detected_stage.lower() else pregame_proj_margin)
    spread_drift = live_proj_margin - pregame_proj_margin
    home_cover_exp = calculate_spread_prob(live_proj_margin, market_spd, std_bracket)
    add_for_prob = 40 if is_nba_game else 14
    live_h_prob = calculate_moneyline_prob(h_pts + add_for_prob, a_pts + add_for_prob, g.get("home_record", "0-0"), g.get("away_record", "0-0"), is_final=is_completed)

    # Section 1: Matchup Overview & Live Drift Projections
    with st.expander("📊 Section 1: Matchup Overview & Live Drift Projections", expanded=True):
        b1, b2, b3 = st.columns([1, 4, 1])
        b1.image(g.get("away_logo", DEFAULT_LOGO), width=45)
        b2.markdown(f"### **{g['away_short']}** @ **{g['home_short']}**\n{g['kickoff']}")
        b3.image(g.get("home_logo", DEFAULT_LOGO), width=45)

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Full Game Total", f"{final_proj:.1f} pts", delta=f"{delta_full:+.1f} vs open ({pregame_tot:.1f})")
        m_col2.metric("2nd Half Total", f"{live_2h_proj:.1f} pts", delta=f"{delta_2h:+.1f} vs 2H base ({pregame_2h:.1f})")
        m_col3.metric(f"{g['home_short']} Win %", f"{live_h_prob*100:.1f}%")
        m_col4.metric(f"ATS Margin ({g['home_short']} {market_spd:+.1f})", f"{live_proj_margin:+.1f} pts", delta=f"{spread_drift:+.1f} pts vs line")

    # Section 2: AI Strategy Engine & Market Filters
    with st.expander("🤖 Section 2: AI Strategy Engine & Market Filters", expanded=True):
        col_scope, col_type_filter = st.columns(2)
        scope_choice = col_scope.selectbox("Target Slate", ["🎯 Focus on Selected Game Above", "⚡ Scan Full Slate for Highest Discrepancy"])
        
        filter_options = [
            "⚡ Let the System Pick (All Markets Combined)", 
            "📊 Full Game Total Score Over/Under", 
            "🛡️ Spread (ATS Cover)",
            "🏆 Team Win/Loser (Moneyline)"
        ]
        if is_nba_game:
            filter_options.append("🏀 Player Over/Under Points Prop")
        else:
            filter_options.append("🏈 Player Anytime Touchdown Scorer")

        filter_choice = col_type_filter.selectbox("Type of Bet", filter_options)
        
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
        strat_game_index = pool.index(active_game_for_strat)

        tg_away_logo = active_game_for_strat.get("away_logo", DEFAULT_LOGO)
        tg_home_logo = active_game_for_strat.get("home_logo", DEFAULT_LOGO)
        tg_away_short = active_game_for_strat.get("away_short", "AWAY")
        tg_home_short = active_game_for_strat.get("home_short", "HOME")
        tg_league_str = active_game_for_strat.get("league", "NFL")

        s_val = market_spd if home_cover_exp >= 0.5 else -market_spd
        s_team = active_game_for_strat["home_team"] if home_cover_exp >= 0.5 else active_game_for_strat["away_team"]
        s_abbr = tg_home_short if home_cover_exp >= 0.5 else tg_away_short

        if "Safe Floor" in strategy_dial:
            obj_tag, p_mult = "Safe Floor", 1.55
            spd_shift = (5.5 if s_val > 0 else 6.0) if is_nba_game else (3.5 if s_val > 0 else 4.0)
            tot_shift = 7.5 if is_nba_game else 4.5
        elif "High Profit" in strategy_dial:
            obj_tag, p_mult = "High Profit", 2.45
            spd_shift = (-5.5 if s_val > 0 else -6.0) if is_nba_game else (-3.5 if s_val > 0 else -4.0)
            tot_shift = -6.5 if is_nba_game else -3.5
        else:
            obj_tag, p_mult, spd_shift, tot_shift = "Balanced Edge", 1.91, 0.0, 0.0

        tot_dir = "Under" if delta_full <= 0 else "Over"
        base_tot_1 = round_half_point(final_proj + tot_shift)
        p_tot_1 = calculate_win_prob(base_tot_1, final_proj, std_bracket, is_under=(tot_dir == "Under"))
        full_totals_bets = [
            {
                "type": f"Full Game Total ({obj_tag} Consensus)",
                "pick": f"{tot_dir} {base_tot_1:.1f}",
                "prob": p_tot_1,
                "category": "Game Total",
                "side": tot_dir,
                "target_line": base_tot_1,
                "picked_team": None,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_mult,
                "roi_label": f"+{int((p_mult-1)*100)}% Profit",
                "rationale": f"Projected tempo indicates {final_proj:.1f} pts vs market line of {pregame_tot:.1f}."
            }
        ]

        line_spd_1 = round_half_point(s_val + spd_shift)
        p_spd_1 = calculate_spread_prob(live_proj_margin if s_team == active_game_for_strat["home_team"] else -live_proj_margin, line_spd_1, std_bracket)
        spread_bets = [
            {
                "type": f"Spread ({obj_tag} Standard)",
                "pick": f"{s_abbr} {line_spd_1:+.1f}",
                "prob": p_spd_1,
                "category": "Point Spread (ATS)",
                "side": "Spread",
                "target_line": line_spd_1,
                "picked_team": s_team,
                "game_index": strat_game_index,
                "est_payout_multiplier": p_mult,
                "roi_label": f"+{int((p_mult-1)*100)}% Profit",
                "rationale": f"{s_abbr} is outperforming point differential expectations."
            }
        ]

        # Player Props (NBA Points vs Football Touchdowns)
        if is_nba_game:
            home_players = get_live_nba_roster(active_game_for_strat.get("home_id") or tg_home_short)
            away_players = get_live_nba_roster(active_game_for_strat.get("away_id") or tg_away_short)
            p1_name, p1_pos, p1_val = home_players[0]
            p2_name, p2_pos, p2_val = away_players[0]
            player_prop_bets = [
                {
                    "type": f"Player Points ({obj_tag})",
                    "pick": f"{p1_name} ({p1_pos} - {tg_home_short}) Over {p1_val:.1f} Pts",
                    "prob": 0.58 if "Safe Floor" in strategy_dial else 0.53,
                    "category": "Player Points Prop",
                    "side": "Over",
                    "target_line": p1_val,
                    "picked_team": p1_name,
                    "game_index": strat_game_index,
                    "est_payout_multiplier": 1.91,
                    "roi_label": "+91% Profit (-110)",
                    "rationale": f"{p1_name} ({p1_pos}) leads active lineup usage and primary shot volume."
                },
                {
                    "type": f"Player Points ({obj_tag})",
                    "pick": f"{p2_name} ({p2_pos} - {tg_away_short}) Over {p2_val:.1f} Pts",
                    "prob": 0.55 if "Safe Floor" in strategy_dial else 0.51,
                    "category": "Player Points Prop",
                    "side": "Over",
                    "target_line": p2_val,
                    "picked_team": p2_name,
                    "game_index": strat_game_index,
                    "est_payout_multiplier": 1.91,
                    "roi_label": "+91% Profit (-110)",
                    "rationale": f"{p2_name} ({p2_pos}) commands secondary isolation volume."
                }
            ]
        else:
            home_players = get_live_football_roster(active_game_for_strat.get("home_id") or tg_home_short, tg_league_str)
            away_players = get_live_football_roster(active_game_for_strat.get("away_id") or tg_away_short, tg_league_str)
            p1_name, p1_pos = home_players[0][:2]
            player_prop_bets = [
                {
                    "type": f"Anytime Touchdown ({obj_tag})",
                    "pick": f"{p1_name} ({p1_pos} - {tg_home_short}) Any Time TD",
                    "prob": 0.55,
                    "category": "Player Anytime Touchdown Scorer",
                    "side": "TD",
                    "target_line": 1.0,
                    "picked_team": p1_name,
                    "game_index": strat_game_index,
                    "est_payout_multiplier": 1.95,
                    "roi_label": "+95% Profit",
                    "rationale": f"{p1_name} ({p1_pos}) commands goal-line opportunities in active red-zone packages."
                }
            ]

        if "Total" in filter_choice:
            strat_candidates = full_totals_bets
        elif "Spread" in filter_choice:
            strat_candidates = spread_bets
        elif "Points" in filter_choice or "Touchdown" in filter_choice:
            strat_candidates = player_prop_bets
        else:
            strat_candidates = [spread_bets[0], full_totals_bets[0], player_prop_bets[0]]

        for idx, sc in enumerate(strat_candidates[:3]):
            tier_lbl = ["🥇 BEST", "🥈 BETTER", "🥉 GOOD"][idx]
            st.markdown(f"""
            <div class="rec-card-box">
                <div class="rec-header-row">
                    <div><strong>{tier_lbl}</strong> • <code>{sc['type']}</code></div>
                    <div class="rec-matchup-meta">
                        <img src="{tg_away_logo}" width="20" height="20" style="border-radius:50%;">
                        <strong>{tg_away_short}</strong> @
                        <img src="{tg_home_logo}" width="20" height="20" style="border-radius:50%;">
                        <strong>{tg_home_short}</strong>
                    </div>
                </div>
                <div class="rec-pick-row">
                    <strong style="color:#4ade80; font-size:1.15rem;">{sc['pick']}</strong>
                    <span class="badge-roi">{sc['roi_label']}</span>
                    <span class="badge-prob">{sc['prob']*100:.1f}% Win Prob</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.info(f"💡 **Why This Bet Was Selected:** {sc['rationale']}")
            if st.button("📥 Load to Form", key=f"apply_{idx}_{sc['pick']}", use_container_width=True):
                st.session_state.single_applied_pick = sc
                st.session_state.single_selected_idx = sc["game_index"]
                st.rerun()

    # Section 3: Wager Type & Lock In Bet Slip
    applied = st.session_state.single_applied_pick
    with st.expander("📝 Section 3: Wager Type & Lock In Bet Slip", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            home_default = applied.get("override_home", g["home_team"]) if (applied and applied.get("override_home")) else g["home_team"]
            away_default = applied.get("override_away", g["away_team"]) if (applied and applied.get("override_away")) else g["away_team"]
            home_team = st.text_input("Home Team", value=home_default)
            away_team = st.text_input("Away Team", value=away_default)
        with c2:
            h_pts_in = st.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"])
            a_pts_in = st.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"])

        wager_types = [
            "Game Total", 
            "Point Spread (ATS)", 
            "Straight Up Winner (Moneyline)", 
            "Player Points Prop" if is_nba_game else "Player Anytime Touchdown Scorer"
        ]
        
        default_wtype = 0
        if applied:
            cat = str(applied.get("category", "")).lower()
            if "spread" in cat or "ats" in cat: default_wtype = 1
            elif "moneyline" in cat or "winner" in cat: default_wtype = 2
            elif "points" in cat or "td" in cat or "prop" in cat: default_wtype = 3

        bet_type = st.radio("Wager Type", wager_types, index=default_wtype, horizontal=True)

        with st.form("single_bet_form"):
            if bet_type == "Game Total":
                f1, f2 = st.columns(2)
                side_idx = 0 if (applied and applied.get("side") == "Under") else 1
                side = f1.selectbox("Side", ["Under", "Over"], index=side_idx)
                default_strike = round_half_point(applied["target_line"]) if (applied and applied.get("target_line") is not None) else round_half_point(final_proj)
                strike = f2.number_input("Target Line (pts)", value=float(default_strike), step=0.5, format="%.1f")
                picked_t = None
            elif bet_type == "Point Spread (ATS)":
                f1, f2 = st.columns(2)
                team_choices = [home_team, away_team]
                p_cand = applied.get("picked_team", "") if applied else ""
                def_team_idx = 1 if (p_cand and p_cand.lower() in away_team.lower()) else 0
                picked_t = f1.selectbox("Covering Team", team_choices, index=def_team_idx)
                default_spread = float(applied["target_line"]) if (applied and applied.get("target_line") is not None and "spread" in str(applied.get("category", "")).lower()) else float(espn_spread)
                strike = f2.number_input("Spread Line", value=float(default_spread), step=0.5, format="%.1f")
                side = "Spread"
            elif bet_type == "Straight Up Winner (Moneyline)":
                picked_t = st.selectbox("Outright Winner", [home_team, away_team])
                strike = None
                side = "Moneyline"
            elif bet_type == "Player Points Prop":
                f1, f2 = st.columns(2)
                all_roster = [p[0] for p in (home_players + away_players)]
                default_player = applied.get("picked_team", p1_name) if applied else p1_name
                def_p_idx = all_roster.index(default_player) if default_player in all_roster else 0
                picked_t = f1.selectbox("Player", all_roster, index=def_p_idx)
                side = f2.selectbox("Side", ["Over", "Under"], index=0 if (applied and applied.get("side") == "Over") else 1)
                default_pts_line = float(applied.get("target_line", 22.5)) if applied else 22.5
                strike = st.number_input("Points Line", value=default_pts_line, step=0.5, format="%.1f")
            else:
                default_p = applied["picked_team"] if (applied and applied.get("picked_team")) else p1_name
                picked_t = st.text_input("Player to Score TD", value=default_p)
                strike = 1.0
                side = "Anytime TD"

            p1, p2 = st.columns(2)
            risk_amt = p1.number_input("Risk ($)", min_value=1.0, value=float(applied.get("risk", 10.0)) if applied else 10.0, step=5.0)
            payout_amt = p2.number_input("Payout ($)", min_value=1.0, value=float(applied.get("payout", 19.10)) if applied else 19.10, step=5.0)

            if st.form_submit_button("Lock In Bet Slip", use_container_width=True):
                actual_risk = float(risk_amt)
                actual_payout = float(payout_amt)
                actual_profit = actual_payout - actual_risk

                if bet_type == "Player Points Prop":
                    bet_lbl = f"{picked_t} {side} {strike:.1f} Pts"
                elif bet_type == "Player Anytime Touchdown Scorer":
                    bet_lbl = f"{picked_t} Any Time TD"
                elif strike is not None:
                    bet_lbl = f"{side} {strike:.1f}" if bet_type == "Game Total" else f"{picked_t} {strike:+.1f}"
                else:
                    bet_lbl = f"{picked_t} ML"

                initial_status = "Won" if is_completed and (h_pts + a_pts < strike if side == "Under" and strike else False) else "Pending"

                ticket_record = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Single",
                    "bet_category": bet_type,
                    "home_team": home_team,
                    "away_team": away_team,
                    "picked_team": picked_t,
                    "matchup": f"{g['away_short']} @ {g['home_short']}",
                    "bet": bet_lbl,
                    "target_line": strike,
                    "bet_direction": side,
                    "risk_dollars": actual_risk,
                    "payout_dollars": actual_payout,
                    "payout": actual_payout,
                    "locked_profit": actual_profit,
                    "status": initial_status,
                    "notes": f"Locked {bet_type} [{g_league}]"
                }
                st.session_state.saved_bets.insert(0, ticket_record)
                save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                st.session_state.single_applied_pick = None
                st.success("Ticket locked successfully!")
                st.rerun()

# =========================================================================
# 3. MULTI-LEG COMBO BUILDER
# =========================================================================
elif menu_choice == "🔗 Multi-Leg Combo Builder":
    st.subheader("🔗 Multi-Leg Cross-Sport Combo Builder (Up to 12 Legs)")
    st.caption("Automated cross-slate parlay scanner, compound probability calculator, and slip builder.")

    c_fcol1, c_fcol2 = st.columns([1, 2])
    with c_fcol1:
        c_timing_view = c_fcol1.selectbox("Game Status Filter (Combo)", ["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"])
    with c_fcol2:
        c_search = c_fcol2.text_input("🔍 Search Game Slate", placeholder="e.g. Celtics, Lakers, Chiefs, Lions...")

    c_pool = games_data
    if c_timing_view == "⏳ Upcoming Games":
        c_pool = [g for g in c_pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
    elif c_timing_view == "⚡ Live Games":
        c_pool = [g for g in c_pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]

    if c_search.strip():
        cq = c_search.strip().lower()
        c_pool = [g for g in c_pool if cq in g["home_team"].lower() or cq in g["away_team"].lower() or cq in g["home_short"].lower() or cq in g["away_short"].lower()]

    if not c_pool:
        st.info("No games match the selected filter.")
        st.stop()

    game_choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in c_pool]

    if not st.session_state.combo_active_legs and c_pool:
        st.session_state.combo_active_legs = []
        for j in range(min(3, len(c_pool))):
            g_item = c_pool[j]
            st.session_state.combo_active_legs.append({
                "matchup_idx": j,
                "type": "Game Total",
                "side": "Under",
                "line": round_half_point(g_item.get("market_ou", 224.5 if g_item.get("league") == "NBA" else 47.5)),
                "picked_team": g_item["home_team"]
            })

    ctrl_c1, ctrl_c2 = st.columns([3, 1], vertical_alignment="center")
    ctrl_c1.markdown(f"#### Active Ticket Slip ({len(st.session_state.combo_active_legs)} Legs)")
    if ctrl_c2.button("➕ Add Leg", use_container_width=True, disabled=(len(st.session_state.combo_active_legs) >= 12 or not c_pool)):
        next_idx = min(len(st.session_state.combo_active_legs), len(c_pool) - 1)
        g_next = c_pool[next_idx]
        st.session_state.combo_active_legs.append({
            "matchup_idx": next_idx,
            "type": "Game Total",
            "side": "Under",
            "line": round_half_point(g_next.get("market_ou", 224.5 if g_next.get("league") == "NBA" else 47.5)),
            "picked_team": g_next["home_team"]
        })
        st.rerun()

    combo_legs = []
    compound_prob = 1.0

    for i, leg_data in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            safe_m_idx = min(max(leg_data.get("matchup_idx", 0), 0), len(game_choices) - 1)
            sel_matchup = st.selectbox(f"Leg {i+1} Matchup", range(len(game_choices)), index=safe_m_idx, format_func=lambda x: game_choices[x], key=f"m_sel_leg_{i}")
            leg_data["matchup_idx"] = sel_matchup
            leg_g = c_pool[sel_matchup]
            is_leg_nba = (leg_g.get("league") == "NBA")

            wager_cat = st.radio(f"Wager Type (Leg {i+1})", ["Game Total", "Straight Up Winner"], horizontal=True, index=0 if leg_data["type"] == "Game Total" else 1, key=f"wtype_leg_{i}")
            leg_data["type"] = wager_cat

            if wager_cat == "Game Total":
                col_b, col_c = st.columns(2)
                side = col_b.selectbox("Side", ["Under", "Over"], index=0 if leg_data.get("side", "Under") == "Under" else 1, key=f"lside_{i}")
                def_line = float(round_half_point(leg_data.get("line", leg_g.get("market_ou", 224.5 if is_leg_nba else 44.5))))
                strike = col_c.number_input("Line (pts)", value=def_line, step=0.5, format="%.1f", key=f"lstrike_{i}")
                leg_data["side"], leg_data["line"] = side, strike
                leg_prob = calculate_win_prob(strike, (218.0 if is_leg_nba else 42.0), (12.0 if is_leg_nba else 7.0), is_under=(side == "Under"))
                leg_desc = f"{leg_g['away_short']} @ {leg_g['home_short']}: {side} {strike:.1f}"
            else:
                col_b, col_c = st.columns(2)
                teams_opt = [leg_g["home_team"], leg_g["away_team"]]
                prev_pick = leg_data.get("picked_team", leg_g["home_team"])
                pick_idx = teams_opt.index(prev_pick) if prev_pick in teams_opt else 0
                winner = col_b.selectbox("Pick Winner", teams_opt, index=pick_idx, key=f"lwinner_{i}")
                leg_data["picked_team"] = winner
                add_score = 40 if is_leg_nba else 14
                h_prob = calculate_moneyline_prob(leg_g["home_score"] + add_score, leg_g["away_score"] + add_score, leg_g["home_record"], leg_g["away_record"])
                leg_prob = h_prob if winner == leg_g["home_team"] else (1.0 - h_prob)
                leg_desc = f"{leg_g['away_short']} @ {leg_g['home_short']}: {winner} ML"

            compound_prob *= leg_prob
            combo_legs.append({"desc": leg_desc, "prob": leg_prob})

    st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        c_r1, c_r2 = st.columns(2)
        c_risk = c_r1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        c_payout = c_r2.number_input("Payout ($)", min_value=1.0, value=50.0, step=10.0)
        if st.form_submit_button(f"Lock In {len(combo_legs)}-Leg Ticket", use_container_width=True):
            parsed_legs = [
                {
                    "matchup": f"{c_pool[min(item['matchup_idx'], len(c_pool) - 1)]['away_short']} @ {c_pool[min(item['matchup_idx'], len(c_pool) - 1)]['home_short']}",
                    "type": item["type"],
                    "side": item.get("side", ""),
                    "line": round_half_point(item.get("line", 0.0)),
                    "picked_team": item.get("picked_team", "")
                }
                for item in st.session_state.combo_active_legs
            ]
            actual_combo_risk = float(c_risk)
            actual_combo_payout = float(c_payout)
            actual_combo_profit = actual_combo_payout - actual_combo_risk

            combo_record = {
                "id": str(datetime.now().timestamp()),
                "user": curr_user.get("display_name", active_uname),
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                "type": f"{len(combo_legs)}-Leg Combo",
                "bet_category": "Combo",
                "matchup": " | ".join([cl["desc"] for cl in combo_legs]),
                "bet": f"{len(combo_legs)} Legs ({compound_prob * 100:.1f}% Prob)",
                "risk_dollars": actual_combo_risk,
                "payout_dollars": actual_combo_payout,
                "payout": actual_combo_payout,
                "locked_profit": actual_combo_profit,
                "win_prob": f"{compound_prob * 100:.1f}%",
                "status": "Pending",
                "parsed_legs": parsed_legs,
                "notes": f"{len(combo_legs)}-Leg Cross-Sport Parlay"
            }
            st.session_state.saved_bets.insert(0, combo_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success(f"{len(combo_legs)}-Leg combo ticket locked in!")
            st.rerun()

# =========================================================================
# 4. LOCKED BETS HISTORY
# =========================================================================
elif menu_choice == "📜 Locked Bets History":
    st.subheader(f"📜 {curr_user.get('display_name', active_uname)}'s Locked Bets")
    st.caption("Active slips with live in-game win probabilities, team logos, and live scoreboard telemetry.")

    clean_u = active_uname.lower()
    clean_disp = curr_user.get("display_name", "").strip().lower()
    
    col_filter1, col_filter2 = st.columns([3, 1])
    with col_filter2:
        show_all_history = st.toggle("Show All Squad Bets", value=False)
        
    my_tickets = []
    for b in st.session_state.saved_bets:
        if show_all_history:
            my_tickets.append(b)
        else:
            bet_owner = str(b.get("user", "")).strip().lower()
            if (bet_owner in [clean_u, clean_disp]) or (is_admin and bet_owner in [clean_u, "admin"]):
                my_tickets.append(b)

    with col_filter1:
        st.write(f"Showing **{len(my_tickets)}** ticket(s).")
        if st.button("⚡ Grade Finals", use_container_width=True):
            if auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages, st.session_state.game_snapshots, st.session_state.support_tickets):
                st.success("Updated tickets!")
                st.rerun()

    if not my_tickets:
        st.info("No tickets recorded yet.")
    else:
        for b in my_tickets:
            real_idx = st.session_state.saved_bets.index(b)
            render_ticket_card(b, real_idx, games_data, can_delete=True)

# =========================================================================
# 5. LEADERBOARD (RICH VERIFIED FORMAT)
# =========================================================================
elif menu_choice == "🏆 Leaderboard":
    st.subheader("🏆 Leaderboard")
    st.caption("Consensus standings, return on investment, member tenure, and betting volume.")

    user_stats = {}
    for b in st.session_state.saved_bets:
        u_raw = str(b.get("user", "Bettor")).strip().lower()
        if u_raw not in user_stats:
            user_stats[u_raw] = {"name": b.get("user"), "total_bets": 0, "won": 0, "lost": 0, "pending": 0, "net": 0.0, "total_staked": 0.0, "types": {}}
        user_stats[u_raw]["total_bets"] += 1
        r = float(b.get("risk_dollars", 0))
        p = float(b.get("payout_dollars", b.get("payout", 0)))
        profit_locked = float(b.get("locked_profit", p - r))

        cat = b.get("bet_category", b.get("type", "Single"))
        user_stats[u_raw]["types"][cat] = user_stats[u_raw]["types"].get(cat, 0) + 1
        if b.get("status") == "Won":
            user_stats[u_raw]["won"] += 1
            user_stats[u_raw]["net"] += profit_locked
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
        if not acc.get("is_public", True): continue
        last_act = acc.get("last_login", "")
        decided = stat["won"] + stat["lost"]
        win_rate = (stat["won"] / decided * 100) if decided > 0 else 0.0
        roi_val = (stat["net"] / stat["total_staked"] * 100) if stat["total_staked"] > 0 else 0.0
        fav_market = max(stat["types"], key=stat["types"].get) if stat["types"] else "Single Play"
        member_since = acc.get("created_at", "N/A")

        if win_rate >= 65.0 and decided >= 3:
            tier_badge = "🎯 Sniper"
        elif stat["won"] >= 3 and stat["lost"] == 0:
            tier_badge = "🔥 On Fire"
        elif decided > 0:
            tier_badge = "⚡ Contender"
        else:
            tier_badge = "🌱 Rookie"

        board.append({
            "name": stat["name"],
            "online": ("ET" in last_act),
            "total_bets": stat["total_bets"],
            "won": stat["won"],
            "lost": stat["lost"],
            "pending": stat["pending"],
            "win_rate": f"{win_rate:.1f}%",
            "roi": f"{roi_val:+.1f}%",
            "total_staked": stat["total_staked"],
            "fav_market": fav_market,
            "member_since": member_since,
            "tier_badge": tier_badge,
            "net": stat["net"]
        })

    board.sort(key=lambda x: x["net"], reverse=True)
    if not board:
        st.info("No public tickets on leaderboard.")
    else:
        for idx, u in enumerate(board):
            medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"#{idx+1}"))
            status_dot = "🟢 Online" if u["online"] else "⚪ Offline"
            status_color = "#22c55e" if u["online"] else "#94a3b8"

            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 4, 2])
                with c1:
                    st.markdown(f"""
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:2px;">
                        <span style="font-size:1.20rem; font-weight:700;">{medal} {u['name']}</span>
                        <span style="font-size:0.75rem; font-weight:600; color:{status_color}; background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:12px; user-select:none;">
                            {status_dot}
                        </span>
                        <span style="font-size:0.75rem; font-weight:700; background:rgba(56,189,248,0.12); color:#38bdf8; padding:2px 7px; border-radius:4px;">
                            {u['tier_badge']}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"🗓️ Member Since: **{u['member_since']}** | Top Market: **{u['fav_market']}**")

                with c2:
                    st.write(f"📊 **{u['won']}W - {u['lost']}L** ({u['win_rate']} Win Rate) | **{u['total_bets']}** Total Slips ({u['pending']} in play)")
                    st.caption(f"Volume Risked: **${u['total_staked']:.2f}** | Return ROI: **{u['roi']}**")

                with c3:
                    color = "#4ade80" if u['net'] >= 0 else "#f87171"
                    st.markdown(f"<div style='text-align:right;'><span style='color:{color};font-size:1.35rem;font-weight:700;'>${u['net']:+.2f}</span></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align:right;opacity:0.65;font-size:0.80rem;'>Net Profit</div>", unsafe_allow_html=True)

# =========================================================================
# 6. LIVE SQUAD FEED
# =========================================================================
elif menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    st.caption("Live stream of tickets placed across the community with real-time match scores and win probabilities.")
    feed_tickets = []
    for b in st.session_state.saved_bets:
        u_raw = str(b.get("user", "Bettor")).strip().lower()
        acc = st.session_state.user_accounts.get(u_raw, {})
        if acc.get("share_feed", True):
            feed_tickets.append(b)

    if not feed_tickets:
        st.info("No community tickets locked in yet.")
    else:
        for idx, b in enumerate(feed_tickets[:30]):
            real_idx = st.session_state.saved_bets.index(b)
            render_ticket_card(b, real_idx, games_data, can_delete=False)

# =========================================================================
# 7. HOW IT WORKS
# =========================================================================
elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: The Comprehensive User Guide")
    st.markdown("""
    Welcome to **Flurkstradamus** — the algorithmic sports betting dashboard built for live modeling, positive expectation (+EV) market exploitation, and automated bankroll tracking across **NBA, NFL, and NCAA Football**.
    
    ---
    ### 🔑 Core Features & System Architecture
    
    * **🏀 NBA & Football Coverage**: Seamlessly switch between the **NBA**, **NFL**, and **NCAA Football** with live quarter-by-quarter scoreboards, adjusted possession clocks, and pace regressions.
    * **🎯 Dynamic NBA Points Props**: Pulls real-time rosters from live ESPN endpoints to construct **Player Over/Under X Points** proposition bets with calculated cover probabilities.
    * **📊 Bankroll & Telemetry Dashboard**: Complete visibility across your betting portfolio:
        * **Settled Realized P&L**: Tracks pure cash won, money lost, and net return on investment (ROI).
        * **Capital at Risk**: Real-time dollar volume of all active, in-flight tickets.
        * **Probability-Adjusted EV Profit**: True mathematical return calculated from live Bayesian quarter-by-quarter score decay.
    * **⚡ Single Game Analytics Engine**: Scan full NFL, NCAA, and NBA slates with live Bayesian pace regression. Tracks scoring momentum, second-half total drift, and ATS cover probabilities across quarters.
    * **🔗 Multi-Leg Combo Builder**: Scan cross-slate parlay combinations with automated compound true probability modeling and cross-game line cushion optimization up to 12 legs.
    * **🏟️ In-Game War Room**: Click any ticket in your history to enter the live game operations room. View projection drift history, real-time possession clock updates, and dynamically shifting cover odds.
    * **🛡️ Immutable Slip Protection**: Your risk stake and entered payout amounts are locked at entry and preserved permanently against container restarts.
    """)

# =========================================================================
# 8. MODEL METHODOLOGY & MATH
# =========================================================================
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Flurkstradamus Machine Learning & Mathematical Architecture")
    st.caption("How our proprietary in-game Bayesian pace models uncover market mispricings.")

    with st.container(border=True):
        st.markdown("### 🏆 Why Flurkstradamus Outperforms Traditional Sportsbooks")
        st.write(
            "Traditional sportsbooks rely heavily on static opening numbers and rigid algorithms that simply divide full-game lines in half "
            "or adjust lines by flat linear formulas. When unexpected game scripts occur—such as sudden defensive turnovers, torrential weather, "
            "or fast hurry-up offenses—sportsbook live lines lag behind real pace changes."
        )
        st.markdown("""
        * **Dynamic Tempo Learning:** Flurkstradamus adjusts scoring projections continuously by evaluating drive success, yards per play, and quarter-by-quarter pace deviations rather than relying on stale pre-game consensus.
        * **Pace-Shock Variance Insulation:** When shootouts or defensive slogs emerge, our engine dynamically widens or compresses standard deviation ($\sigma$) brackets, ensuring bets are never forced back toward bad pre-game numbers.
        * **Real Value Margins:** The AI compares its derived mathematical probability against implied sportsbook breakeven lines to surface only positive expected value (+EV) tickets.
        """)

    with st.container(border=True):
        st.markdown("### ⚙️ How Bets Are Made: The 4-Step Analytical Pipeline")
        st.markdown("""
        1. **Live Scoreboard & Odds Ingestion:** Real-time play-by-play telemetry, game clock, and open/current odds lines are pulled directly from live feeds.
        2. **Bayesian Halftime & Quarter Regression:** Scoring pace is compared against baseline expectations to generate in-game projections for second-half scoring, full-game totals, and adjusted point spread margins.
        3. **Cumulative Probability Distribution Modeling:** Projections are evaluated against market lines using continuous normal cumulative distributions (CDF) and logistic sigmoid curves to calculate true cover probabilities.
        4. **Multi-Objective Strategy Filtering:** Bettors select their risk profile (`🛡️ Safe Floor`, `⚖️ Balanced Edge`, or `🚀 High Profit`), and the engine selects the highest-discrepancy lines meeting that objective.
        """)

    with st.container(border=True):
        st.markdown("### 📐 Mathematical Formulas & Core Distribution Functions")
        st.markdown("##### 1. Over/Under Win Expectancy (Gaussian Error Function)")
        st.write("Over/Under win probabilities are calculated via continuous cumulative normal distributions:")
        st.latex(r"Z = \frac{\text{Line} - \mu_{\text{in-game}}}{\sigma_{\text{decay}}}")
        st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right], \quad P(\text{Over}) = 1 - P(\text{Under})")

        st.markdown("##### 2. Point Spread (ATS) Cover Probability")
        st.write("Point spread cover expectations pass projected score differentials through a logistic sigmoid distribution:")
        st.latex(r"\Delta_{\text{margin}} = (\text{Home Proj} - \text{Away Proj}) + \text{Line}")
        st.latex(r"P(\text{Home Cover}) = \frac{1}{1 + e^{-\frac{\Delta_{\text{margin}}}{5.0}}}")

        st.markdown("##### 3. Straight-Up Moneyline Logistic Expectancy")
        st.write("Calculates straight-up win probability based on projected team scoring volume and historical win-percentage differentials:")
        st.latex(r"P(\text{Home Win}) = \frac{1}{1 + 10^{-\frac{\Delta_{\text{pts}} + (\text{Win\% Diff} \times 7.0)}{14.5}}}")

        st.markdown("##### 4. Player Prop Scoring Engine (Poisson & Volume)")
        st.write("Player prop models evaluate minutes distribution, usage rates, and situational opportunity shares:")
        st.latex(r"P(\text{Prop}) = 1 - e^{-\left(\lambda_{\text{Team Event}} \times \text{Player Share} \times \text{Defensive Modifier}\right)}")

# =========================================================================
# 9. ACCOUNT SETTINGS
# =========================================================================
elif menu_choice == "⚙️ Account Settings":
    st.subheader("⚙️ Account Settings & Profile Management")
    with st.form("account_settings_form"):
        new_display = st.text_input("Display Name", value=curr_user.get("display_name", ""))
        new_email = st.text_input("Email Address", value=curr_user.get("email", ""))
        new_team = st.text_input("Favorite Team", value=curr_user.get("favorite_team", "Multi-Sport"))
        new_avatar = st.text_input("Profile Avatar URL", value=curr_user.get("avatar_url", ""))
        new_bio = st.text_area("Short Bio", value=curr_user.get("bio", "Sports investor & strategist."))
        pub_lead = st.toggle("Show My Profile on Public Leaderboard", value=curr_user.get("is_public", True))
        share_fd = st.toggle("Publish My Slips to Live Squad Feed", value=curr_user.get("share_feed", True))
        p_change1 = st.text_input("New Password", type="password")
        p_change2 = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Save Account Settings", use_container_width=True):
            if new_display.strip(): curr_user["display_name"] = new_display.strip()
            if new_email.strip(): curr_user["email"] = new_email.strip()
            curr_user["favorite_team"] = new_team.strip()
            curr_user["avatar_url"] = new_avatar.strip()
            curr_user["bio"] = new_bio.strip()
            curr_user["is_public"] = pub_lead
            curr_user["share_feed"] = share_fd
            if p_change1 and p_change1 == p_change2 and len(p_change1) >= 4:
                curr_user["password_hash"] = hash_password(p_change1)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success("Settings updated!")
            st.rerun()

# =========================================================================
# 10. FEEDBACK & SUPPORT
# =========================================================================
elif menu_choice == "📩 Feedback & Support":
    st.subheader("📩 Feedback, Support & Ticket Desk")
    st.caption("Submit bug reports, feature suggestions, or account assistance requests directly to the team.")

    tab_sub, tab_view = st.tabs(["📝 Submit a Ticket", "📂 My Ticket History"])
    with tab_sub:
        with st.form("new_support_ticket_form"):
            t_category = st.selectbox("Category", ["🏀 NBA Request", "🏈 Football Request", "🐛 Bug Report", "💡 Feature Suggestion", "💼 Account Assistance", "💬 General Feedback"])
            t_priority = st.select_slider("Priority", options=["Low", "Medium", "High", "Critical"], value="Medium")
            t_subject = st.text_input("Subject", placeholder="Brief description...")
            t_description = st.text_area("Details", placeholder="Provide relevant details...")
            
            if st.form_submit_button("Submit Support Ticket", use_container_width=True):
                if t_subject.strip() and t_description.strip():
                    new_ticket = {
                        "id": f"TKT-{random.randint(1000, 9999)}",
                        "user": curr_user.get("display_name", active_uname),
                        "username": active_uname,
                        "date": get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET"),
                        "category": t_category,
                        "priority": t_priority,
                        "subject": t_subject.strip(),
                        "description": t_description.strip(),
                        "status": "Open",
                        "admin_reply": None
                    }
                    st.session_state.support_tickets.insert(0, new_ticket)
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    st.success("Support ticket submitted!")
                    st.rerun()

    with tab_view:
        user_tickets = [t for t in st.session_state.support_tickets if t.get("username") == active_uname or is_admin]
        if not user_tickets:
            st.info("No support tickets on record.")
        else:
            for tkt in user_tickets:
                with st.container(border=True):
                    st.write(f"**[{tkt.get('id')}] {tkt.get('subject')}** | Status: **{tkt.get('status')}**")
                    st.write(tkt.get("description"))
                    if tkt.get("admin_reply"):
                        st.info(f"Team Response: {tkt.get('admin_reply')}")

# =========================================================================
# 11. ABOUT THIS APP
# =========================================================================
elif menu_choice == "ℹ️ About Flurkstradamus":
    st.subheader("ℹ️ About Flurkstradamus")
    with st.container(border=True):
        st.markdown("""
        ### 🔮 Flurkstradamus Edge Engine
        **Flurkstradamus** is an algorithmic sports betting analytics and bankroll intelligence platform built for modern market investors and bettors.
        
        ---
        #### 👨‍💻 Developer & Company Information
        * **Architect & Developer:** Adam Sowers
        * **Company:** Sowers Web Technologies
        * **Location:** Altamonte Springs, Florida, United States
        * **Official Website:** [sweetcustomwebsites.com](https://sweetcustomwebsites.com)
        """)

# =========================================================================
# 12. ENHANCED COMMISSIONER ADMIN SUITE
# =========================================================================
elif menu_choice == "🛡️ Admin" and is_admin:
    st.subheader("🛡️ Commissioner Admin Console")
    st.caption("Inspect user activity, audit bet tickets, review search logs, manage accounts, and reply to support tickets.")

    users = st.session_state.user_accounts
    st.write(f"Total Registered Users: **{len(users)}**")

    tab_admin_users, tab_admin_tickets = st.tabs(["👤 User Accounts & Bet Management", "📩 Inbound Support Tickets"])

    with tab_admin_users:
        user_list = list(users.keys())
        selected_u = st.selectbox(
            "Select User to Inspect Activity & Dossier",
            options=user_list,
            format_func=lambda x: f"{users[x].get('display_name', users[x].get('username', x))} (@{x})"
        )

        if selected_u:
            u_info = users[selected_u]
            with st.container(border=True):
                st.markdown(f"### 👤 User Dossier: **{u_info.get('display_name')}** (`@{selected_u}`)")
                
                c_a1, c_a2, c_a3 = st.columns(3)
                c_a1.write(f"📧 **Email:** `{u_info.get('email', 'N/A')}`\n\n🏈 **Fav Team:** `{u_info.get('favorite_team', 'Multi-Sport')}`")
                c_a2.write(f"🗓️ **Joined:** `{u_info.get('created_at', 'N/A')}`\n\n⏱️ **Last Login:** `{u_info.get('last_login', 'N/A')}`")
                c_a3.write(f"Status: **{'🚫 BANNED' if u_info.get('is_banned') else '✅ Active'}**\n\nVerified: **{'✅ Yes' if u_info.get('is_verified', True) else '❌ Unverified'}**")

                searches = u_info.get("searches", [])
                st.markdown("##### 🔍 Recent Searches:")
                if searches:
                    st.write(", ".join([f"`{s}`" for s in searches[-15:]]))
                else:
                    st.caption("No search queries logged.")

                u_clean = selected_u.lower()
                u_display_clean = u_info.get("display_name", "").strip().lower()
                u_bets = [b for b in st.session_state.saved_bets if str(b.get("user", "")).strip().lower() in [u_clean, u_display_clean]]
                
                u_won = [b for b in u_bets if b.get("status") == "Won"]
                u_lost = [b for b in u_bets if b.get("status") == "Lost"]
                u_profit = sum(float(b.get("locked_profit", float(b.get("payout_dollars", b.get("payout", 0))) - float(b.get("risk_dollars", 0)))) for b in u_won) - sum(float(b.get("risk_dollars", 0)) for b in u_lost)
                
                p_col1, p_col2, p_col3 = st.columns(3)
                p_col1.metric("Tickets Placed", len(u_bets))
                p_col2.metric("Record", f"{len(u_won)}W - {len(u_lost)}L")
                p_col3.metric("Net P&L", f"${u_profit:+.2f}")

                with st.expander(f"📜 View All Tickets Placed by {u_info.get('display_name')}"):
                    if not u_bets:
                        st.info("No tickets locked in yet.")
                    else:
                        for ub in u_bets:
                            st.markdown(f"• **{ub.get('date')}** — `{ub.get('matchup')}`: **{ub.get('bet')}** | Stake: ${float(ub.get('risk_dollars', 10)):.2f} | Status: `{ub.get('status')}`")

                admin_cred = get_admin_credentials()
                if selected_u != admin_cred["username"].lower():
                    st.markdown("##### ⚙️ Administrative Actions:")
                    act1, act2 = st.columns(2)
                    with act1:
                        ban_label = "✅ Unban Account" if u_info.get("is_banned") else "🚫 Ban Account"
                        if st.button(ban_label, key=f"ban_btn_{selected_u}"):
                            u_info["is_banned"] = not u_info.get("is_banned", False)
                            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                            st.rerun()
                    with act2:
                        if st.button("🗑️ Delete User Permanently", key=f"del_user_btn_{selected_u}"):
                            users.pop(selected_u)
                            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                            st.rerun()

    with tab_admin_tickets:
        if not st.session_state.support_tickets:
            st.info("No support tickets currently pending.")
        else:
            for t_idx, tkt in enumerate(st.session_state.support_tickets):
                with st.container(border=True):
                    st.write(f"**[{tkt.get('id')}] {tkt.get('subject')}** by `{tkt.get('user')}`")
                    st.write(f"Category: **{tkt.get('category')}** | Priority: **{tkt.get('priority')}** | Status: **{tkt.get('status')}**")
                    st.write(tkt.get("description"))
                    with st.form(f"admin_reply_{tkt.get('id')}"):
                        reply = st.text_input("Response", value=tkt.get("admin_reply") or "")
                        status_sel = st.selectbox("Status", ["Open", "In Review", "Resolved"], index=0 if tkt.get("status") == "Open" else (1 if tkt.get("status") == "In Review" else 2))
                        if st.form_submit_button("Save Reply & Status"):
                            tkt["admin_reply"] = reply
                            tkt["status"] = status_sel
                            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                            st.success("Reply saved!")
                            st.rerun()
