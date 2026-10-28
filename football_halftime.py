import streamlit as st
import requests
import re
import json
import base64
import random
import string
import io
from PIL import Image
from datetime import datetime, timezone, timedelta
import streamlit.components.v1 as components

# Import modular engines
try:
    from config import DEFAULT_LOGO, OFFICIAL_ABBR_MAP
    from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob
    from database import (
        load_storage, save_all_storage, find_game_for_bet, auto_resolve_bets,
        hash_password, get_admin_credentials, send_verification_email
    )
except Exception as import_err:
    st.error(f"Error loading backend modules: {import_err}")
    st.stop()

st.set_page_config(
    page_title="Flurkstradamus Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Responsive Desktop + Mobile styling & Custom 3D Spinning Football Loader
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
        .dashboard-header-desktop {
            display: block !important;
        }
        .dashboard-header-mobile {
            display: none !important;
        }
    }
    @media (max-width: 767px) {
        .block-container {
            padding-top: 2.2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        .dashboard-header-desktop {
            display: none !important;
        }
        .dashboard-header-mobile {
            display: block !important;
            font-size: 1.45rem !important;
            font-weight: 700 !important;
            margin-bottom: 0.3rem !important;
        }
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

    /* DISABLE HOVER COPY LINK ICONS GLOBALLY */
    a.header-anchor, a[data-testid="stHeaderAnchor"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
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

    /* CUSTOM 3D SPINNING FOOTBALL LOADER */
    @keyframes spinFootball {
        0% { transform: rotate(0deg) scale(1); }
        50% { transform: rotate(180deg) scale(1.15); }
        100% { transform: rotate(360deg) scale(1); }
    }
    [data-testid="stSpinner"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 18px 0 !important;
    }
    [data-testid="stSpinner"] > div {
        display: none !important;
    }
    [data-testid="stSpinner"]::before {
        content: "🏈" !important;
        font-size: 2.8rem !important;
        display: inline-block !important;
        animation: spinFootball 0.85s cubic-bezier(0.4, 0.0, 0.2, 1) infinite !important;
        filter: drop-shadow(0px 4px 10px rgba(0, 0, 0, 0.45)) !important;
        margin: 0 auto !important;
    }
    [data-testid="stStatusWidget"] {
        background: transparent !important;
        border: none !important;
    }
    [data-testid="stStatusWidget"] svg,
    [data-testid="stStatusWidget"] [data-testid="stStatusWidget-Icon"] {
        display: none !important;
    }
    [data-testid="stStatusWidget"]::before {
        content: "🏈" !important;
        font-size: 1.25rem !important;
        display: inline-block !important;
        animation: spinFootball 0.8s linear infinite !important;
    }

    .rec-card-box {
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.025);
        padding: 12px;
        margin-bottom: 12px;
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

# LIVE ESPN ACTIVE ROSTER EXTRACTOR
@st.cache_data(ttl=600)
def get_live_team_players(team_id_or_abbr, league="nfl"):
    sport_path = "college-football" if league.upper() in ["NCAA", "NCAA FOOTBALL"] else "nfl"
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/{sport_path}/teams/{str(team_id_or_abbr).lower()}/roster"
    
    players_found = []
    try:
        r = requests.get(url, timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            for athlete in data.get("athletes", []):
                items = athlete.get("items", []) if "items" in athlete else [athlete]
                for p in items:
                    pos = p.get("position", {}).get("abbreviation", "")
                    name = p.get("displayName") or p.get("fullName")
                    if pos in ["QB", "RB", "WR", "TE"] and name:
                        players_found.append((name, pos))
    except Exception:
        pass

    if not players_found:
        return [("Lead Running Back", "RB"), ("Top Wideout", "WR"), ("Starting Tight End", "TE")]

    order = {"RB": 0, "WR": 1, "TE": 2, "QB": 3}
    players_found.sort(key=lambda x: order.get(x[1], 4))
    return players_found[:6]

def get_current_et_time():
    utc_now = datetime.now(timezone.utc)
    return utc_now - timedelta(hours=4)

def clean_abbr(team_name, espn_abbr):
    if team_name in OFFICIAL_ABBR_MAP: return OFFICIAL_ABBR_MAP[team_name]
    if espn_abbr and espn_abbr.strip():
        clean = espn_abbr.strip().upper()
        if len(clean) <= 5: return clean
    words = re.findall(r"[A-Z0-9]", team_name)
    return "".join(words[:4]) if words else "TEAM"

def format_espn_kickoff(date_str, fallback_status):
    if not date_str: return fallback_status
    try:
        dt = datetime.strptime(date_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M%z")
        dt_et = dt - timedelta(hours=4)
        return dt_et.strftime("%a %m/%d - %I:%M %p ET")
    except Exception: return fallback_status

def round_half_point(val):
    try: return round(float(val) * 2.0) / 2.0
    except (ValueError, TypeError): return 47.5

def calculate_live_bet_prob(bet_obj, live_m):
    if not live_m: return bet_obj.get("win_prob", "50.0%")
    stat_val = bet_obj.get("status", "Pending")
    is_fin = live_m.get("completed", False) or "final" in live_m.get("status", "").lower()
    if is_fin: return "100.0%" if stat_val == "Won" else "0.0%"

    curr_away = live_m.get("away_score", 0)
    curr_home = live_m.get("home_score", 0)
    curr_tot = curr_away + curr_home
    t_line = bet_obj.get("target_line")
    b_side = bet_obj.get("bet_direction", "Under")
    b_cat = bet_obj.get("bet_category", "Total")
    period = live_m.get("period", 1)

    is_started = (live_m.get("state_text") != "pre" and period > 0)
    if not is_started: return bet_obj.get("win_prob", "50.0%")

    if b_cat in ["Total", "2H Total"] and t_line:
        sigma = 3.5 if period >= 3 else 6.0
        rem_proj = 14.0 if period >= 3 else 24.0
        p = calculate_win_prob(t_line, curr_tot + rem_proj, sigma, is_under=(b_side == "Under"))
        return f"{p * 100:.1f}%"
    elif b_cat == "Moneyline":
        h_prob = calculate_moneyline_prob(curr_home + 14, curr_away + 14, live_m.get("home_record", "0-0"), live_m.get("away_record", "0-0"))
        p = h_prob if bet_obj.get("picked_team") == live_m.get("home_team") else (1.0 - h_prob)
        return f"{p * 100:.1f}%"
    elif b_cat == "Spread" and t_line:
        margin = curr_home - curr_away
        diff = margin if bet_obj.get("picked_team") == live_m.get("home_team") else -margin
        p = calculate_spread_prob(diff, t_line, std_dev=5.0)
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

# UNIVERSAL BET SLIP & SCREENSHOT PARSER WITH FAST IMAGE PRE-COMPRESSION
def parse_bet_slip_image(image_bytes):
    raw_key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    if not raw_key:
        return None, "GEMINI_API_KEY is not defined in Streamlit Secrets."

    gemini_key = str(raw_key).strip().strip('"').strip("'")

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        if pil_img.width > 1024:
            ratio = 1024 / float(pil_img.width)
            new_h = int(float(pil_img.height) * ratio)
            pil_img = pil_img.resize((1024, new_h), Image.Resampling.LANCZOS)
        
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        compressed_bytes = buf.getvalue()
        b64_img = base64.b64encode(compressed_bytes).decode("utf-8")
    except Exception:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
    You are an expert sports betting and event contracts OCR parser.
    Analyze this bet slip or event contract screenshot (Robinhood, DraftKings, FanDuel, BetMGM, Caesars, Kalshi, etc.).
    Extract the bet parameters into a strictly valid JSON object:
    {
        "away_team": "string or null (e.g. Delaware, Sam Houston)",
        "home_team": "string or null (e.g. Western Kentucky, Missouri State)",
        "picked_team": "string or null (team name chosen if spread or moneyline)",
        "wager_type": "Point Spread" | "Game Total" | "Moneyline" | "Anytime TD",
        "side": "Under" | "Over" | "Spread" | "Moneyline",
        "line": float or null (e.g. 77.5, 33.5, -7.5),
        "payout": float (total payout / return in dollars including stake),
        "profit": float or null (realized or potential profit in dollars),
        "risk": float or null (amount staked / risked in dollars),
        "is_settled": true if the screenshot indicates a payout, settlement, or won status, else false
    }
    Rules:
    1. If headline says "Over X points Payout" and pick says "No · Over X", side is "Under", line is X, wager_type is "Game Total".
    2. If pick says "Yes · Over X", side is "Over", line is X, wager_type is "Game Total".
    3. If headline says "Will Team -X.X points win?" or "Team -X.X points Payout", this is a Point Spread bet on that team covering -X.X.
    4. In "Event", extract both competing teams (e.g. "Delaware vs Western Kentucky" -> away_team: "Delaware", home_team: "Western Kentucky").
    5. If profit is present but risk is missing: risk = payout - profit.
    6. If both risk and payout are present: profit = payout - risk.
    Return ONLY raw JSON without markdown formatting.
    """

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
            ]
        }],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    candidate_endpoints = [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
    ]

    last_error = ""
    for endpoint_url in candidate_endpoints:
        url = f"{endpoint_url}?key={gemini_key}"
        try:
            r = requests.post(url, json=payload, timeout=22.0)
            if r.status_code == 200:
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = re.sub(r"^```json\s*", "", txt.strip())
                cleaned = re.sub(r"```$", "", cleaned.strip())
                return json.loads(cleaned), None
            else:
                last_error = f"HTTP {r.status_code}: {r.text[:160]}"
        except Exception as e:
            last_error = str(e)

    return None, f"Vision API error ({last_error}). Please check your API key in Streamlit Secrets."

def match_game_in_pool(away_name, home_name, pool, picked_name=""):
    """Finds the index of a game in pool based on partial team name matches."""
    if not pool:
        return 0
    a_target = (away_name or "").lower().strip()
    h_target = (home_name or "").lower().strip()
    p_target = (picked_name or "").lower().strip()

    for idx, gm in enumerate(pool):
        gm_h = gm["home_team"].lower()
        gm_a = gm["away_team"].lower()
        gm_hs = gm["home_short"].lower()
        gm_as = gm["away_short"].lower()

        h_match = (h_target in gm_h or h_target in gm_hs or gm_h in h_target) if h_target else True
        a_match = (a_target in gm_a or a_target in gm_as or gm_a in a_target) if a_target else True
        if h_match and a_match:
            return idx

    for idx, gm in enumerate(pool):
        gm_h = gm["home_team"].lower()
        gm_a = gm["away_team"].lower()
        gm_hs = gm["home_short"].lower()
        gm_as = gm["away_short"].lower()
        for mc in [h_target, a_target, p_target]:
            if mc and len(mc) >= 3 and (mc in gm_h or mc in gm_hs or gm_h in mc or mc in gm_a or mc in gm_as or gm_a in mc):
                return idx

    return 0

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

    with st.container(border=True):
        st.markdown(f"**Ticket #{real_idx+1}** | Status: {badge_html}", unsafe_allow_html=True)
        c_row1, c_row2, c_row3, c_row4 = st.columns([3.5, 3.5, 2.0, 1.2])
        with c_row1:
            st.write(f"**Pick:** `{b.get('bet')}`")
            st.caption(f"🗓️ Logged: `{b.get('date', 'N/A')}`")

        with c_row2:
            try: r_val = float(b.get("risk_dollars", 10.0))
            except: r_val = 10.0
            try: p_val = float(b.get("payout_dollars", b.get("payout", 19.0)))
            except: p_val = 19.0
            try: profit_locked = float(b.get("locked_profit", p_val - r_val))
            except: profit_locked = p_val - r_val
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

# Session State Initializations
if "logged_in_user" not in st.session_state: st.session_state.logged_in_user = None
if "selected_bet_id" not in st.session_state: st.session_state.selected_bet_id = None
if "combo_active_legs" not in st.session_state: st.session_state.combo_active_legs = []
if "ai_recommended_combo" not in st.session_state: st.session_state.ai_recommended_combo = None
if "active_nav_page" not in st.session_state: st.session_state.active_nav_page = "📊 My Dashboard"
if "combo_version" not in st.session_state: st.session_state.combo_version = 0
if "scroll_to_form" not in st.session_state: st.session_state.scroll_to_form = False
if "pending_verify_user" not in st.session_state: st.session_state.pending_verify_user = None

# Form state
if "single_selected_idx" not in st.session_state: st.session_state.single_selected_idx = 0
if "single_applied_pick" not in st.session_state: st.session_state.single_applied_pick = None
if "single_form_version" not in st.session_state: st.session_state.single_form_version = 0

# Database Load
loaded_storage = load_storage()
if len(loaded_storage) == 6:
    b_data, c_data, u_data, banned_emails_data, game_snapshots_data, support_tickets_data = loaded_storage
else:
    b_data, c_data, u_data, banned_emails_data, game_snapshots_data, support_tickets_data = [], [], {}, [], {}, []

if "saved_bets" not in st.session_state: st.session_state.saved_bets = b_data
if "chat_messages" not in st.session_state: st.session_state.chat_messages = c_data
if "user_accounts" not in st.session_state: st.session_state.user_accounts = u_data
if "banned_emails" not in st.session_state: st.session_state.banned_emails = banned_emails_data
if "game_snapshots" not in st.session_state: st.session_state.game_snapshots = game_snapshots_data
if "support_tickets" not in st.session_state: st.session_state.support_tickets = support_tickets_data

# PERSISTENT "REMEMBER ME" AUTHENTICATION TOKEN CHECK
query_params = st.query_params
if st.session_state.logged_in_user is None:
    token_in_url = query_params.get("auth_token") or query_params.get("session_token")
    if token_in_url:
        for u_obj in st.session_state.user_accounts.values():
            if u_obj.get("session_token") == token_in_url and not u_obj.get("is_banned", False) and u_obj.get("is_verified", True):
                st.session_state.logged_in_user = u_obj
                break

# Authentication Gateway & Email Passcode Verification
if st.session_state.logged_in_user is None:
    st.title("🔮 Flurkstradamus")
    st.caption("Sign in, create an account, or confirm your registration code.")

    # Verification Code Form
    if st.session_state.pending_verify_user is not None:
        target_u = st.session_state.user_accounts.get(st.session_state.pending_verify_user)
        with st.container(border=True):
            st.markdown(f"### ✉️ Verify Your Email Address")
            st.write(f"A 6-digit confirmation passcode was issued for **{target_u.get('email')}**.")
            
            # If SMTP is not active, display activation code directly on screen for testing convenience
            if not st.secrets.get("smtp"):
                st.info(f"💡 Dev/Test Activation Code: **`{target_u.get('verification_code')}`**")
                
            with st.form("verify_code_form"):
                entered_code = st.text_input("6-Digit Verification Code", placeholder="123456").strip()
                v_submit = st.form_submit_button("Confirm & Activate Account", use_container_width=True)
                if v_submit:
                    if entered_code == target_u.get("verification_code"):
                        target_u["is_verified"] = True
                        target_u["verification_code"] = None
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                        st.session_state.logged_in_user = target_u
                        st.session_state.pending_verify_user = None
                        st.success("Account successfully verified!")
                        st.rerun()
                    else:
                        st.error("Invalid verification code. Please check and try again.")
            if st.button("⬅️ Cancel & Back to Login", use_container_width=True):
                st.session_state.pending_verify_user = None
                st.rerun()
        st.stop()

    tab_login, tab_signup, tab_forgot = st.tabs(["🔐 Sign In", "📝 Create Account", "🔑 Forgot Password"])
    
    with tab_login:
        with st.form("user_login_form"):
            uname_input = st.text_input("Username or Email", placeholder="sharpbettor").strip()
            pword_input = st.text_input("Password", type="password", placeholder="••••••••")
            remember_me = st.checkbox("Remember me on this device", value=True)
            submit_login = st.form_submit_button("Sign In", use_container_width=True)
            if submit_login:
                clean_target = uname_input.lower()
                target_hash = hash_password(pword_input)
                admin_cred = get_admin_credentials()
                
                # Check Secrets-Configured Admin Credentials
                if (clean_target in [admin_cred["username"].lower(), admin_cred["email"].lower()] 
                    and pword_input == admin_cred["password"]):
                    admin_key = admin_cred["username"].lower()
                    admin_profile = st.session_state.user_accounts.get(admin_key, {
                        "username": admin_cred["username"],
                        "email": admin_cred["email"],
                        "display_name": admin_cred["username"],
                        "is_admin": True,
                        "is_banned": False,
                        "is_verified": True,
                        "password_hash": target_hash
                    })
                    admin_profile["password_hash"] = target_hash
                    admin_profile["is_admin"] = True
                    admin_profile["is_banned"] = False
                    admin_profile["is_verified"] = True
                    admin_profile["last_login"] = get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET")
                    if not admin_profile.get("session_token"):
                        admin_profile["session_token"] = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    
                    st.session_state.user_accounts[admin_key] = admin_profile
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    
                    if remember_me:
                        st.query_params["auth_token"] = admin_profile["session_token"]
                    st.session_state.logged_in_user = admin_profile
                    st.rerun()

                # Standard Account Match
                matched_user = None
                for u_key, u_val in st.session_state.user_accounts.items():
                    if (u_key.lower() == clean_target or 
                        u_val.get("username", "").lower() == clean_target or 
                        u_val.get("email", "").lower() == clean_target or 
                        u_val.get("display_name", "").lower() == clean_target):
                        matched_user = u_val
                        break

                if matched_user and matched_user.get("password_hash") == target_hash and not matched_user.get("is_banned"):
                    if not matched_user.get("is_verified", True):
                        st.session_state.pending_verify_user = matched_user["username"].lower()
                        st.rerun()

                    if not matched_user.get("session_token"):
                        matched_user["session_token"] = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    matched_user["last_login"] = get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET")
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    
                    if remember_me:
                        st.query_params["auth_token"] = matched_user["session_token"]
                    st.session_state.logged_in_user = matched_user
                    st.rerun()
                else:
                    st.error("Invalid credentials or banned account.")
                    
    with tab_signup:
        with st.form("user_signup_form"):
            new_uname = st.text_input("Username", placeholder="gridiron_guru").strip().lower()
            new_email = st.text_input("Email", placeholder="bettor@example.com").strip().lower()
            new_dname = st.text_input("Display Name", placeholder="Gridiron Guru")
            new_pword = st.text_input("Password", type="password")
            new_pword_confirm = st.text_input("Confirm Password", type="password")
            fav_team = st.text_input("Favorite Team (Optional)", placeholder="Philadelphia Eagles")
            if st.form_submit_button("Create My Account", use_container_width=True):
                if new_uname and new_email and new_pword == new_pword_confirm and len(new_pword) >= 4:
                    new_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    verify_code = ''.join(random.choices(string.digits, k=6))
                    
                    new_user = {
                        "username": new_uname,
                        "email": new_email,
                        "display_name": new_dname or new_uname,
                        "password_hash": hash_password(new_pword),
                        "is_admin": False,
                        "is_banned": False,
                        "is_verified": False,
                        "verification_code": verify_code,
                        "created_at": get_current_et_time().strftime("%Y-%m-%d"),
                        "last_login": get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET"),
                        "favorite_team": fav_team or "NFL",
                        "bio": "Bettor.",
                        "avatar_url": "",
                        "is_public": True,
                        "share_feed": True,
                        "searches": [],
                        "reset_token": None,
                        "session_token": new_token
                    }
                    st.session_state.user_accounts[new_uname] = new_user
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    
                    # Send code via email if SMTP is configured
                    send_verification_email(new_email, verify_code)
                    
                    st.session_state.pending_verify_user = new_uname
                    st.rerun()
                else:
                    st.error("Please fill all required fields and verify password.")

    with tab_forgot:
        with st.form("request_reset_form"):
            recover_email = st.text_input("Registered Email").strip().lower()
            if st.form_submit_button("Request Reset Code", use_container_width=True):
                target_user = next((u for u in st.session_state.user_accounts.values() if u.get("email", "").lower() == recover_email), None)
                if target_user:
                    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    target_user["reset_token"] = token
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    st.success(f"Recovery Code: **`{token}`**")
                else:
                    st.error("Account not found.")
    st.stop()

# Active Context
current_user_profile = st.session_state.logged_in_user
active_uname = current_user_profile.get("username", "").strip().lower()
current_user = current_user_profile.get("display_name", current_user_profile.get("username", "Bettor"))
is_user_admin = current_user_profile.get("is_admin", False)

# Scoreboard Ingestion
@st.cache_data(ttl=30)
def get_extended_games(selected_league="All Games"):
    all_games = []
    seen_ids = set()
    now_et = get_current_et_time()
    
    date_queries = [""]
    for d in range(-3, 8):
        dt_day = (now_et + timedelta(days=d)).strftime("%Y%m%d")
        date_queries.append(dt_day)

    endpoints = []
    for dq in date_queries:
        d_param = f"&dates={dq}" if dq else ""
        if selected_league in ["NFL", "All Games"]:
            endpoints.append(("NFL", f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=100{d_param}"))
        if selected_league in ["NCAA Football", "All Games"]:
            endpoints.append(("NCAA", f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?limit=100&groups=80{d_param}"))

    for l_label, url in endpoints:
        try:
            r = requests.get(url, timeout=3.5)
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
                    checkpoint = "Final / Game Completed" if is_completed else ("Pre-Game" if (state_text == "pre" or period == 0) else ("Halftime" if "half" in status_desc.lower() else f"Q{period}"))

                    all_games.append({
                        "id": ev_id,
                        "raw_date": raw_date,
                        "league": l_label,
                        "name": event["name"],
                        "kickoff": kickoff_formatted,
                        "home_team": home_name,
                        "home_id": home_team_obj.get("id"),
                        "home_short": clean_abbr(home_name, home_team_obj.get("abbreviation")),
                        "home_logo": home_team_obj.get("logo", DEFAULT_LOGO),
                        "home_record": home.get("records", [{}])[0].get("summary", "0-0") if home.get("records") else "0-0",
                        "away_team": away_name,
                        "away_id": away_team_obj.get("id"),
                        "away_short": clean_abbr(away_name, away_team_obj.get("abbreviation")),
                        "away_logo": away_team_obj.get("logo", DEFAULT_LOGO),
                        "away_record": away.get("records", [{}])[0].get("summary", "0-0") if away.get("records") else "0-0",
                        "home_score": int(home.get("score", 0)),
                        "away_score": int(away.get("score", 0)),
                        "status": status_desc,
                        "state_text": state_text,
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

# Sidebar Navigation Items
st.sidebar.markdown(f"## 🔮 Flurkstradamus")

if st.sidebar.button(f"👤 {current_user} (@{current_user_profile.get('username')})", key="sidebar_user_profile_link"):
    st.session_state.selected_bet_id = None
    st.session_state.active_nav_page = "⚙️ Account Settings"
    st.rerun()

col_u1, _ = st.sidebar.columns(2)
with col_u1:
    if st.button("🚪 Logout", key="logout_btn", use_container_width=True):
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
    ("📩 Feedback & Support", "📩 Feedback & Support"),
    ("💡 How It Works", "💡 How It Works"),
    ("ℹ️ About Flurkstradamus", "ℹ️ About Flurkstradamus"),
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
league = st.sidebar.radio("Primary League", ["NFL", "NCAA Football", "All Games"])
games_data = get_extended_games(league)
auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages, st.session_state.game_snapshots, st.session_state.support_tickets)

# =========================================================================
# 1. MY DASHBOARD
# =========================================================================
if menu_choice == "📊 My Dashboard":
    st.markdown('<div class="dashboard-header-desktop"><h3>📊 Personal Betting Dashboard</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-header-mobile">📊 Dashboard</div>', unsafe_allow_html=True)
    st.caption("Complete portfolio telemetry: settled P&L, live pending stakes, and probability-modeled expected returns.")

    clean_u = active_uname.lower()
    clean_disp = current_user_profile.get("display_name", "").strip().lower()
    
    my_bets = [b for b in st.session_state.saved_bets if str(b.get("user", "")).strip().lower() in [clean_u, clean_disp]]

    if not my_bets:
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

        tot_won = sum(float(b.get("locked_profit", float(b.get("payout_dollars", b.get("payout", 0))) - float(b.get("risk_dollars", 0)))) for b in won_bets)
        tot_lost = sum(float(b.get("risk_dollars", 0)) for b in lost_bets)
        net_pl = tot_won - tot_lost
        tot_risk = sum(float(b.get("risk_dollars", 0)) for b in my_bets if b.get("status") in ["Won", "Lost"])
        roi = (net_pl / tot_risk * 100) if tot_risk > 0 else 0.0

        pending_risk = sum(float(b.get("risk_dollars", 0)) for b in pending_bets)
        pending_max_profit = sum(float(b.get("locked_profit", float(b.get("payout_dollars", b.get("payout", 0))) - float(b.get("risk_dollars", 0)))) for b in pending_bets)

        st.markdown("##### 💼 Realized Performance (Settled Slips)")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Bets Logged", len(my_bets))
        k2.metric("Money Won", f"${tot_won:.2f}")
        k3.metric("Money Lost", f"${tot_lost:.2f}")
        k4.metric("Net Profit / Loss", f"${net_pl:+.2f}", delta=f"{roi:+.1f}% ROI")

        st.markdown("##### ⏳ Active Book & Pending Analytics")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Capital at Risk", f"${pending_risk:.2f}", f"{len(pending_bets)} Slips Active")
        p2.metric("Max Potential Profit", f"+${pending_max_profit:.2f}")
        p3.metric("Win Rate", f"{(len(won_bets) / max(len(won_bets) + len(lost_bets), 1)) * 100:.1f}%")
        p4.metric("Pending In Play", f"{len(pending_bets)} Slips")

# =========================================================================
# 2. SINGLE GAME ENGINE
# =========================================================================
elif menu_choice == "⚡ Single Game Engine":
    st.subheader("⚡ Single Game Analytics Engine")
    form_ver = st.session_state.single_form_version

    with st.expander("📸 Auto-Fill via Slip Screenshot (Robinhood, DraftKings, FanDuel, etc.)", expanded=False):
        uploaded_slip = st.file_uploader("Upload Slip Screenshot (PNG, JPG)", type=["png", "jpg", "jpeg"], key=f"slip_uploader_v{form_ver}")
        if uploaded_slip is not None and st.button("⚡ Extract & Auto-Fill Form", use_container_width=True):
            with st.spinner("Analyzing screenshot..."):
                parsed_res, err_msg = parse_bet_slip_image(uploaded_slip.read())
                if parsed_res:
                    away_t = parsed_res.get("away_team", "")
                    home_t = parsed_res.get("home_team", "")
                    picked_t = parsed_res.get("picked_team", "")
                    matched_idx = match_game_in_pool(away_t, home_t, games_data, picked_t)
                    
                    w_risk = float(parsed_res.get("risk", 10.0))
                    w_payout = float(parsed_res.get("payout", 20.0))
                    w_profit = float(parsed_res.get("profit", w_payout - w_risk))

                    st.session_state.single_selected_idx = matched_idx
                    st.session_state.single_applied_pick = {
                        "category": parsed_res.get("wager_type", "Game Total"),
                        "side": parsed_res.get("side", "Under"),
                        "target_line": float(parsed_res.get("line", 44.5)) if parsed_res.get("line") is not None else 44.5,
                        "risk": w_risk,
                        "payout": w_payout,
                        "profit": w_profit,
                        "override_away": away_t,
                        "override_home": home_t,
                        "picked_team": picked_t,
                        "status": "Won" if parsed_res.get("is_settled") else "Pending"
                    }
                    st.session_state.single_form_version += 1
                    st.rerun()
                else:
                    st.error(f"Error parsing image: {err_msg}")

    # Render Matchup Selection
    pool = games_data
    if pool:
        game_options = [f"[{g['kickoff']}] [{g['league']}] {g['away_short']} @ {g['home_short']}" for g in pool]
        if st.session_state.single_selected_idx >= len(game_options):
            st.session_state.single_selected_idx = 0
        selected_idx = st.selectbox("Select Matchup", range(len(game_options)), index=st.session_state.single_selected_idx, format_func=lambda x: game_options[x])
        g = pool[selected_idx]
    else:
        st.info("No games currently available.")
        st.stop()

    applied = st.session_state.single_applied_pick
    with st.form(f"single_entry_form_v{form_ver}"):
        st.markdown(f"#### 📝 Lock In Bet: **{g['away_short']} @ {g['home_short']}**")
        c1, c2 = st.columns(2)
        home_team = c1.text_input("Home Team", value=applied.get("override_home", g["home_team"]) if applied else g["home_team"])
        away_team = c2.text_input("Away Team", value=applied.get("override_away", g["away_team"]) if applied else g["away_team"])

        bet_type = st.radio("Wager Type", ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"], horizontal=True)
        r_col, p_col = st.columns(2)
        risk_amt = r_col.number_input("Risk ($)", min_value=1.0, value=float(applied.get("risk", 10.0)) if applied else 10.0, step=5.0)
        payout_amt = p_col.number_input("Payout ($)", min_value=1.0, value=float(applied.get("payout", 19.10)) if applied else 19.10, step=5.0)

        if st.form_submit_button("Lock In Bet Slip", use_container_width=True):
            profit = float(payout_amt) - float(risk_amt)
            initial_status = applied.get("status", "Pending") if applied else "Pending"
            ticket_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "date": get_current_et_time().strftime("%Y-%m-%d %H:%M ET"),
                "type": "Single",
                "bet_category": bet_type,
                "home_team": home_team,
                "away_team": away_team,
                "matchup": f"{clean_abbr(away_team, '')} @ {clean_abbr(home_team, '')}",
                "bet": f"{bet_type} Ticket",
                "risk_dollars": float(risk_amt),
                "payout_dollars": float(payout_amt),
                "payout": float(payout_amt),
                "locked_profit": profit,
                "status": initial_status,
                "notes": f"Locked {bet_type}"
            }
            st.session_state.saved_bets.insert(0, ticket_record)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.session_state.single_applied_pick = None
            st.success("Ticket locked successfully!")
            st.rerun()

# =========================================================================
# 3. FEEDBACK, SUPPORT & TICKET SYSTEM
# =========================================================================
elif menu_choice == "📩 Feedback & Support":
    st.subheader("📩 Feedback, Support & Ticket Desk")
    st.caption("Submit bug reports, feature suggestions, or account assistance requests directly to the team.")

    tab_sub, tab_view = st.tabs(["📝 Submit a Ticket", "📂 My Ticket History"])
    
    with tab_sub:
        with st.form("new_support_ticket_form"):
            t_category = st.selectbox("Category", ["🐛 Bug Report / Broken Line", "💡 Feature Suggestion", "📸 OCR Vision Parser Issue", "💼 Account & Billing", "💬 General Feedback"])
            t_priority = st.select_slider("Priority", options=["Low", "Medium", "High", "Critical"], value="Medium")
            t_subject = st.text_input("Subject", placeholder="e.g. Screenshot failed on DraftKings parlay")
            t_description = st.text_area("Details", placeholder="Provide relevant matchup, wager amounts, or description of what happened...")
            
            if st.form_submit_button("Submit Support Ticket", use_container_width=True):
                if t_subject.strip() and t_description.strip():
                    new_ticket = {
                        "id": f"TKT-{random.randint(1000, 9999)}",
                        "user": current_user.strip(),
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
                    st.success("Support ticket submitted! Our team will review your report.")
                    st.rerun()
                else:
                    st.error("Please provide both a subject and details.")

    with tab_view:
        user_tickets = [t for t in st.session_state.support_tickets if t.get("username") == active_uname or is_user_admin]
        if not user_tickets:
            st.info("You haven't submitted any tickets yet.")
        else:
            for tkt in user_tickets:
                with st.container(border=True):
                    stat_color = "#22c55e" if tkt.get("status") == "Resolved" else "#eab308"
                    st.markdown(f"**[{tkt.get('id')}] {tkt.get('subject')}** &nbsp; <span style='background:{stat_color};color:#000;padding:2px 8px;border-radius:10px;font-weight:700;font-size:0.75rem;'>{tkt.get('status')}</span>", unsafe_allow_html=True)
                    st.caption(f"🗓️ Logged: {tkt.get('date')} | Category: **{tkt.get('category')}** | Priority: **{tkt.get('priority')}**")
                    st.write(tkt.get("description"))
                    if tkt.get("admin_reply"):
                        st.info(f"👑 **Response from Team:** {tkt.get('admin_reply')}")

# =========================================================================
# 4. HOW IT WORKS
# =========================================================================
elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: The Comprehensive User Guide")
    st.markdown("""
    Welcome to **Flurkstradamus** — the algorithmic sports betting dashboard built for live second-half modeling, positive expectation (+EV) market exploitation, and automated bankroll tracking.
    
    ---
    ### 🔑 Core Features & System Architecture
    
    * **📸 Universal Screenshot & Slip Parser**: Upload screenshots from any major sportsbook (DraftKings, FanDuel, BetMGM, Caesars, Kalshi, or Robinhood Derivatives)[cite: 5]. Our multimodal vision engine automatically matches competing teams, wager type, covering spread or total, stake, and payout, automatically grading settled tickets as **Won** without manual entry.
    * **📊 Bankroll & Telemetry Dashboard**: Complete visibility across your betting portfolio:
        * **Settled Realized P&L**: Tracks pure cash won, money lost, and net return on investment (ROI).
        * **Capital at Risk**: Real-time dollar volume of all active, in-flight tickets.
        * **Probability-Adjusted EV Profit**: True mathematical return calculated from live Bayesian quarter-by-quarter score decay.
    * **⚡ Single Game Analytics Engine**: Scan full NFL and NCAA slates with live Bayesian pace regression. Tracks scoring momentum, second-half total drift, and ATS cover probabilities across quarters.
    * **🔗 Multi-Leg Combo Builder**: Scan cross-slate parlay combinations with automated compound true probability modeling and cross-game line cushion optimization.
    * **🏟️ In-Game War Room**: Click any ticket in your history to enter the live game operations room. View projection drift history, real-time possession clock updates, and dynamically shifting cover odds.
    * **🛡️ Immutable Slip Protection**: Your risk stake and entered payout amounts are locked at entry and preserved permanently against container restarts.
    """)

# =========================================================================
# 5. ABOUT THIS APP & DEVELOPER ATTRIBUTION
# =========================================================================
elif menu_choice == "ℹ️ About Flurkstradamus":
    st.subheader("ℹ️ About Flurkstradamus")
    
    with st.container(border=True):
        st.markdown("""
        ### 🔮 Flurkstradamus Edge Engine
        
        **Flurkstradamus** is a predictive sports analytics and bankroll intelligence platform engineered for modern sports investors and market traders. The system pairs real-time game telemetry with automated vision-based bet parsing to give bettors an analytical edge.
        
        ---
        
        #### 👨‍💻 Developer & Company Information
        
        * **Architect & Developer:** Adam Sowers
        * **Engineering Firm:** Sowers Web Technologies
        * **Location:** Altamonte Springs, Florida, United States
        * **Official Website:** [sweetcustomwebsites.com](https://sweetcustomwebsites.com)
        
        ---
        
        *Engineered with Streamlit, Python, Google Gemini Multimodal Vision, and Bayesian Tempo Regression Models.*
        """)

# =========================================================================
# 6. LOCKED BETS HISTORY
# =========================================================================
elif menu_choice == "📜 Locked Bets History":
    st.subheader(f"📜 {current_user}'s Locked Bets")
    clean_u = active_uname.lower()
    my_tickets = [b for b in st.session_state.saved_bets if str(b.get("user", "")).strip().lower() in [clean_u, current_user.lower()]]

    if not my_tickets:
        st.info("No tickets recorded yet.")
    else:
        for b in my_tickets:
            real_idx = st.session_state.saved_bets.index(b)
            render_ticket_card(b, real_idx, games_data, can_delete=True)

# =========================================================================
# 7. LEADERBOARD
# =========================================================================
elif menu_choice == "🏆 Leaderboard":
    st.subheader("🏆 Leaderboard")
    st.info("Leaderboard active.")

# =========================================================================
# 8. LIVE SQUAD FEED
# =========================================================================
elif menu_choice == "🔥 Live Squad Feed":
    st.subheader("🔥 Live Squad Feed")
    for idx, b in enumerate(st.session_state.saved_bets[:25]):
        render_ticket_card(b, idx, games_data, can_delete=False)

# =========================================================================
# 9. THE LOCKER ROOM
# =========================================================================
elif menu_choice == "💬 The Locker Room":
    st.subheader("💬 The Locker Room")
    with st.form("locker_room_chat"):
        msg_in = st.text_input("Message")
        if st.form_submit_button("Post") and msg_in.strip():
            st.session_state.chat_messages.insert(0, {
                "user": current_user, "text": msg_in.strip(), "time": get_current_et_time().strftime("%I:%M %p ET")
            })
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.rerun()

# =========================================================================
# 10. MODEL METHODOLOGY & MATH
# =========================================================================
elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Machine Learning Architecture & Core Math")
    st.latex(r"Z = \frac{\text{Line} - \mu_{\text{in-game}}}{\sigma_{\text{decay}}}")
    st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")

# =========================================================================
# 11. ACCOUNT SETTINGS
# =========================================================================
elif menu_choice == "⚙️ Account Settings":
    st.subheader("⚙️ Account Settings")
    with st.form("settings_form"):
        dname = st.text_input("Display Name", value=current_user_profile.get("display_name", ""))
        fav_team = st.text_input("Favorite Team", value=current_user_profile.get("favorite_team", "NFL"))
        if st.form_submit_button("Save Settings"):
            current_user_profile["display_name"] = dname
            current_user_profile["favorite_team"] = fav_team
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success("Settings updated!")
            st.rerun()

# =========================================================================
# 12. COMMISSIONER ADMIN CONSOLE
# =========================================================================
elif menu_choice == "🛡️ Admin" and is_user_admin:
    st.subheader("🛡️ Commissioner Admin Console")
    st.markdown("##### 📩 Inbound Support Tickets")
    
    if not st.session_state.support_tickets:
        st.info("No support tickets currently pending.")
    else:
        for t_idx, tkt in enumerate(st.session_state.support_tickets):
            with st.container(border=True):
                st.write(f"**[{tkt.get('id')}] {tkt.get('subject')}** by `{tkt.get('user')}` ({tkt.get('date')})")
                st.write(f"Category: **{tkt.get('category')}** | Priority: **{tkt.get('priority')}** | Status: **{tkt.get('status')}**")
                st.write(tkt.get("description"))
                
                with st.form(f"reply_tkt_{tkt.get('id')}"):
                    reply_text = st.text_input("Admin Response", value=tkt.get("admin_reply") or "")
                    new_status = st.selectbox("Update Status", ["Open", "In Review", "Resolved"], index=0 if tkt.get("status") == "Open" else (1 if tkt.get("status") == "In Review" else 2))
                    if st.form_submit_button("Save Ticket Status"):
                        tkt["admin_reply"] = reply_text
                        tkt["status"] = new_status
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                        st.success("Ticket updated!")
                        st.rerun()
