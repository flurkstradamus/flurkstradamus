import streamlit as st
import random
import string
from datetime import datetime, timezone, timedelta

# Import modules
from config import DEFAULT_LOGO
from database import (
    load_storage, save_all_storage, find_game_for_bet, auto_resolve_bet,
    hash_password, get_admin_credentials, send_verification_email
)
from sports import fetch_football_scoreboard, fetch_nba_scoreboard
from views.dashboard import render_dashboard
from views.single_game import render_single_game
from views.combo_builder import render_combo_builder
from views.slip_scanner import render_slip_scanner
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
    if not ga_id: 
        return
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

# CSS Layout & Mobile Optimization
st.markdown("""
<style>
    @media (min-width: 768px) {
        .block-container { 
            padding-top: 4.0rem !important; 
            padding-bottom: 2.5rem !important; 
            padding-left: 2.5rem !important; 
            padding-right: 2.5rem !important; 
            max-width: 1200px !important; 
        }
        .dashboard-header-desktop { display: block !important; }
        .dashboard-header-mobile { display: none !important; }
    }
    @media (max-width: 767px) {
        .block-container { 
            padding-top: 2.0rem !important; 
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

        /* Prevent Streamlit from stacking nested button columns vertically on mobile */
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"]:has(button) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            gap: 8px !important;
            width: 100% !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"]:has(button) > div[data-testid="column"] {
            flex: 1 1 0px !important;
            min-width: 0 !important;
            width: auto !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"]:has(button) button {
            width: 100% !important;
            min-height: 2.4rem !important;
            padding: 4px 8px !important;
            font-size: 0.85rem !important;
        }

        /* 2x2 grid for metrics on mobile */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 8px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="column"] {
            width: 100% !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.03) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 8px !important;
            padding: 8px 12px !important;
        }
        div[data-testid="stMetricLabel"] p {
            font-size: 0.78rem !important;
            opacity: 0.8 !important;
        }
        div[data-testid="stMetricValue"] div {
            font-size: 1.3rem !important;
            font-weight: 700 !important;
        }
        input, select, textarea {
            font-size: 16px !important;
        }
    }

    a.header-anchor, a[data-testid="stHeaderAnchor"] { display: none !important; }
    
    /* Strict left alignment on sidebar */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { 
        gap: 0.25rem !important; 
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        text-align: left !important; 
        justify-content: flex-start !important; 
        display: flex !important;
        align-items: center !important; 
        padding-left: 14px !important; 
        padding-right: 14px !important;
        min-height: 2.2rem !important;
        font-weight: 600 !important; 
        border-radius: 6px !important; 
        width: 100% !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button div {
        text-align: left !important;
        justify-content: flex-start !important;
        width: 100% !important;
        display: flex !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button p {
        text-align: left !important; 
        justify-content: flex-start !important; 
        width: 100% !important; 
        margin: 0 !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding: 12px 16px !important;
        margin-bottom: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# Client-Side Mobile Behavior Controller
import streamlit.components.v1 as components
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
</script>
""", height=0)

def get_current_et_time():
    return datetime.now(timezone.utc) - timedelta(hours=4)

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

    from models import calculate_win_prob, calculate_moneyline_prob, calculate_spread_prob
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
        try: return max(0.001, min(0.999, float(str(p_str).replace("%", "").strip()) / 100.0))
        except: return 0.50

def render_ticket_card(b, real_idx, games_data, can_delete=False):
    status_val = b.get("status", "Pending")
    is_combo = (b.get("bet_category") == "Combo" or "Leg" in b.get("type", ""))
    legs_list = b.get("parsed_legs", [])

    live_m = None
    if not is_combo:
        live_m = find_game_for_bet(b, games_data)

    game_started = False
    is_final = False
    if live_m:
        chk = live_m.get("checkpoint", "")
        stt = live_m.get("status", "").lower()
        game_started = ("pre" not in chk.lower()) and ("pm" not in stt and "am" not in stt)
        is_final = live_m.get("completed", False) or "final" in stt

    is_ticket_settled = (status_val in ["Won", "Lost"]) or is_final

    live_prob_badge_html = ""
    if not is_ticket_settled:
        if is_combo:
            compound_p = 1.0
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
                try: 
                    compound_p *= (float(p_str.replace("%", "")) / 100.0)
                except: 
                    compound_p *= 0.5
            live_prob_str = f"{compound_p * 100:.1f}%"
        else:
            live_prob_str = calculate_live_bet_prob(b, live_m)

        live_prob_badge_html = f"<span style='background-color:rgba(56,189,248,0.15);color:#38bdf8;font-weight:700;padding:2px 8px;border-radius:6px;font-size:0.80rem;white-space:nowrap;'>🎲 Win: {live_prob_str}</span>"

    if status_val == "Won":
        badge_html = "<span style='background-color:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-weight:800;font-size:0.75rem;white-space:nowrap;'>🏆 WON</span>"
    elif status_val == "Lost":
        badge_html = "<span style='background-color:#ef4444;color:#fff;padding:2px 8px;border-radius:12px;font-weight:800;font-size:0.75rem;white-space:nowrap;'>❌ LOST</span>"
    elif game_started:
        badge_html = "<span style='background-color:#eab308;color:#000;padding:2px 8px;border-radius:12px;font-weight:800;font-size:0.75rem;white-space:nowrap;'>⚡ IN PLAY</span>"
    else:
        badge_html = "<span style='background-color:rgba(255,255,255,0.12);color:#94a3b8;padding:2px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;white-space:nowrap;'>⏳ SCHEDULED</span>"

    user_name = b.get('user', 'Bettor')

    if is_combo:
        header_title_html = f"<span style='font-size:0.95rem;font-weight:700;'>🔗 {len(legs_list)}-Leg Parlay</span><span style='opacity:0.6;font-size:0.78rem;'>• @{user_name}</span>"
    elif live_m:
        a_sh = live_m.get("away_short", "AWAY")
        h_sh = live_m.get("home_short", "HOME")
        a_sc = live_m.get("away_score", 0)
        h_sc = live_m.get("home_score", 0)
        tot_pts = a_sc + h_sc
        status_txt = live_m.get("displayClock") or live_m.get("status")

        if game_started or is_final:
            score_badge = f"<span style='background-color:rgba(255,255,255,0.08);padding:2px 6px;border-radius:4px;font-weight:700;font-size:0.78rem;white-space:nowrap;'>{a_sc}-{h_sc} ({tot_pts} pts)</span>"
        else:
            score_badge = f"<span style='opacity:0.6;font-size:0.75rem;white-space:nowrap;'>{live_m.get('kickoff', status_txt)}</span>"

        away_logo = live_m.get('away_logo', DEFAULT_LOGO)
        home_logo = live_m.get('home_logo', DEFAULT_LOGO)
        header_title_html = f"<img src='{away_logo}' width='20' height='20' style='border-radius:50%;object-fit:contain;'><strong>{a_sh}</strong> <span style='opacity:0.4;'>@</span><img src='{home_logo}' width='20' height='20' style='border-radius:50%;object-fit:contain;'><strong>{h_sh}</strong>{score_badge}<span style='opacity:0.6;font-size:0.78rem;'>• @{user_name}</span>"
    else:
        m_txt = b.get('matchup', 'Matchup')
        header_title_html = f"<strong>{m_txt}</strong> <span style='opacity:0.6;font-size:0.78rem;'>• @{user_name}</span>"

    r_val = float(b.get("risk_dollars", 10.0))
    p_val = float(b.get("payout_dollars", b.get("payout", 19.0)))
    profit_locked = float(b.get("locked_profit", p_val - r_val))
    roi_pct = (profit_locked / max(r_val, 0.01)) * 100
    cat_label = b.get("bet_category", b.get("type", "Single"))
    bet_pick_str = str(b.get("bet", "N/A"))

    # Generate itemized leg badges for combo tickets
    combo_legs_html = ""
    if is_combo and legs_list:
        chips = []
        for idx, leg_item in enumerate(legs_list):
            m_name = leg_item.get("picked_team") or leg_item.get("matchup", f"Leg #{idx+1}")
            s_side = leg_item.get("side", "")
            s_line = f" {leg_item.get('line')}" if leg_item.get("line") is not None else ""
            chips.append(f"<span style='background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);padding:2px 8px;border-radius:4px;font-size:0.75rem;white-space:nowrap;'><strong>#{idx+1}</strong> {m_name} {s_side}{s_line}</span>")
        combo_legs_html = f"<div style='display:flex;flex-wrap:wrap;gap:5px;margin-top:6px;'>{''.join(chips)}</div>"

    with st.container(border=True):
        # Header Row
        st.markdown(f"""
        <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:6px; border-bottom:1px solid rgba(255,255,255,0.07); padding-bottom:6px; margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">{header_title_html}</div>
            <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">{live_prob_badge_html}{badge_html}</div>
        </div>
        """, unsafe_allow_html=True)

        # Single Clean Row: Desktop stays inline; Mobile stacks and splits buttons 50/50
        c1, c2, c3, c4 = st.columns([3.0, 2.7, 2.3, 2.0], vertical_alignment="center")

        with c1:
            st.markdown(f"""
            <div style="font-size:0.88rem;"><strong>Pick:</strong> <span style="color:#4ade80;font-weight:700;">{bet_pick_str}</span></div>
            <div style="font-size:0.76rem;opacity:0.65;margin-top:2px;">🗓️ Logged: {b.get('date', 'N/A')}</div>
            {combo_legs_html}
            """, unsafe_allow_html=True)

        with c2:
            profit_color = "#ef4444" if profit_locked < 0 else "#4ade80"
            st.markdown(f"""
            <div style="font-size:0.88rem;">Risk: <strong>${r_val:.2f}</strong> ➔ Payout: <strong>${p_val:.2f}</strong></div>
            <div style="font-size:0.78rem;color:{profit_color};font-weight:700;margin-top:2px;">Profit: {'+' if profit_locked>=0 else ''}${profit_locked:.2f} ({roi_pct:+.1f}%)</div>
            """, unsafe_allow_html=True)

        with c3:
            notes_line = f"<div style='font-size:0.74rem;opacity:0.65;'><em>{b.get('notes')}</em></div>" if b.get("notes") else ""
            st.markdown(f"""
            <div style="font-size:0.82rem;opacity:0.85;">Type: <strong>{cat_label}</strong></div>
            {notes_line}
            """, unsafe_allow_html=True)

        with c4:
            # Action buttons: Inline on desktop, 50% width side-by-side on mobile
            if can_delete:
                b1, b2 = st.columns([2.5, 1.5])
                with b1:
                    if st.button("🏟️ War Room", key=f"wr_{b.get('id', real_idx)}_{real_idx}", use_container_width=True):
                        st.session_state.selected_bet_id = b["id"]
                        st.rerun()
                with b2:
                    if st.button("🗑️", key=f"del_{b.get('id', real_idx)}_{real_idx}", help="Delete ticket", use_container_width=True):
                        st.session_state.saved_bets.pop(real_idx)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                        st.rerun()
            else:
                if st.button("🏟️ War Room", key=f"wr_{b.get('id', real_idx)}_{real_idx}", use_container_width=True):
                    st.session_state.selected_bet_id = b["id"]
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

@st.cache_data(ttl=30, show_spinner=False)
def get_cached_games():
    return fetch_nba_scoreboard() + fetch_football_scoreboard("All Games")

needs_live_data = st.session_state.active_nav_page in [
    "📊 My Dashboard", 
    "⚡ Single Game Engine", 
    "🔗 Multi-Leg Combo Builder", 
    "📸 Scan Bet Slip",
    "📜 Locked Bets History", 
    "🔥 Live Squad Feed"
] or (st.session_state.selected_bet_id is not None)

if needs_live_data:
    games_data = get_cached_games()
    auto_resolve_bets(
        st.session_state.saved_bets, 
        games_data, 
        st.session_state.chat_messages, 
        st.session_state.game_snapshots, 
        st.session_state.support_tickets
    )
else:
    games_data = []

# Navigation Menu
nav_list = [
    "📊 My Dashboard", 
    "⚡ Single Game Engine", 
    "🔗 Multi-Leg Combo Builder", 
    "📸 Scan Bet Slip",
    "📜 Locked Bets History", 
    "🔥 Live Squad Feed", 
    "🏆 Leaderboard", 
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

# War Room Routing
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)
    if st.button("⬅️ Back to Tickets", use_container_width=True) or not selected_bet:
        st.session_state.selected_bet_id = None
        st.rerun()
    live_g = find_game_for_bet(selected_bet, games_data)
    live_p = calculate_live_bet_prob(selected_bet, live_g)
    st.title(f"🏟️ War Room: {selected_bet.get('matchup')}")
    st.write(f"**Pick:** `{selected_bet.get('bet')}` | Live Probability: **{live_p}**")
    if live_g:
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.image(live_g.get("away_logo", DEFAULT_LOGO), width=45)
        c1.metric(live_g['away_short'], live_g['away_score'])
        c2.metric("Clock", live_g.get('displayClock', live_g['status']))
        c3.image(live_g.get("home_logo", DEFAULT_LOGO), width=45)
        c3.metric(live_g['home_short'], live_g['home_score'])
    st.stop()

# Page Routing
if menu_choice == "📊 My Dashboard":
    render_dashboard(curr_user, active_uname, games_data, get_numeric_prob)
elif menu_choice == "⚡ Single Game Engine":
    render_single_game(curr_user, active_uname, games_data, get_current_et_time)
elif menu_choice == "🔗 Multi-Leg Combo Builder":
    render_combo_builder(curr_user, active_uname, games_data, get_current_et_time)
elif menu_choice == "📸 Scan Bet Slip":
    render_slip_scanner(curr_user, active_uname, games_data, get_current_et_time)
elif menu_choice == "📜 Locked Bets History":
    render_history(curr_user, active_uname, is_admin, games_data, render_ticket_card)
elif menu_choice == "🔥 Live Squad Feed":
    render_squad_feed(games_data, render_ticket_card)
elif menu_choice == "🏆 Leaderboard":
    render_leaderboard()
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
