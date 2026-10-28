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
    }
    @media (max-width: 767px) {
        .block-container {
            padding-top: 2.2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
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
    section[data-testid="stSidebar"] div[data-testid="stButton"] button * {
        text-align: left !important;
        justify-content: flex-start !important;
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

STAR_ROSTER = {
    "PHI": [("Saquon Barkley", "RB"), ("A.J. Brown", "WR"), ("Jalen Hurts", "QB"), ("DeVonta Smith", "WR")],
    "DAL": [("CeeDee Lamb", "WR"), ("Rico Dowdle", "RB"), ("Jake Ferguson", "TE"), ("Dak Prescott", "QB")],
    "CAR": [("Chuba Hubbard", "RB"), ("Diontae Johnson", "WR"), ("Xavier Legette", "WR"), ("Bryce Young", "QB")],
    "GB": [("Josh Jacobs", "RB"), ("Jayden Reed", "WR"), ("Tucker Kraft", "TE"), ("Jordan Love", "QB")],
    "KC": [("Travis Kelce", "TE"), ("Isiah Pacheco", "RB"), ("Xavier Worthy", "WR"), ("Patrick Mahomes", "QB")],
    "BAL": [("Derrick Henry", "RB"), ("Lamar Jackson", "QB"), ("Zay Flowers", "WR"), ("Mark Andrews", "TE")],
    "BUF": [("Josh Allen", "QB"), ("James Cook", "RB"), ("Khalil Shakir", "WR"), ("Dalton Kincaid", "TE")],
    "MIA": [("De'Von Achane", "RB"), ("Tyreek Hill", "WR"), ("Jaylen Waddle", "WR"), ("Raheem Mostert", "RB")],
    "SF": [("Christian McCaffrey", "RB"), ("George Kittle", "TE"), ("Deebo Samuel", "WR"), ("Jordan Mason", "RB")],
    "DET": [("Jahmyr Gibbs", "RB"), ("David Montgomery", "RB"), ("Amon-Ra St. Brown", "WR"), ("Sam LaPorta", "TE")],
    "MIN": [("Justin Jefferson", "WR"), ("Aaron Jones", "RB"), ("Jordan Addison", "WR")],
    "CIN": [("Ja'Marr Chase", "WR"), ("Chase Brown", "RB"), ("Tee Higgins", "WR"), ("Zack Moss", "RB")],
    "HOU": [("Joe Mixon", "RB"), ("Nico Collins", "WR"), ("Stefon Diggs", "WR"), ("Tank Dell", "WR")],
    "NYG": [("Tyrone Tracy Jr.", "RB"), ("Malik Nabers", "WR"), ("Wan'Dale Robinson", "WR")],
    "WAS": [("Brian Robinson Jr.", "RB"), ("Jayden Daniels", "QB"), ("Terry McLaurin", "WR")],
    "CHI": [("D'Andre Swift", "RB"), ("DJ Moore", "WR"), ("Rome Odunze", "WR"), ("Caleb Williams", "QB")],
    "ATL": [("Bijan Robinson", "RB"), ("Drake London", "WR"), ("Kyle Pitts", "TE"), ("Tyler Allgeier", "RB")],
    "NO": [("Alvin Kamara", "RB"), ("Chris Olave", "WR"), ("Rashid Shaheed", "WR")],
    "TB": [("Bucky Irving", "RB"), ("Rachaad White", "RB"), ("Mike Evans", "WR"), ("Chris Godwin", "WR")],
    "LAR": [("Kyren Williams", "RB"), ("Cooper Kupp", "WR"), ("Puka Nacua", "WR")],
    "SEA": [("Kenneth Walker III", "RB"), ("DK Metcalf", "WR"), ("Jaxon Smith-Njigba", "WR")],
    "ARI": [("James Conner", "RB"), ("Marvin Harrison Jr.", "WR"), ("Kyler Murray", "QB"), ("Trey McBride", "TE")],
    "DEN": [("Javonte Williams", "RB"), ("Courtland Sutton", "WR"), ("Bo Nix", "QB")],
    "LV": [("Alexander Mattison", "RB"), ("Jakobi Meyers", "WR"), ("Brock Bowers", "TE")],
    "LAC": [("J.K. Dobbins", "RB"), ("Ladd McConkey", "WR"), ("Justin Herbert", "QB")],
    "IND": [("Jonathan Taylor", "RB"), ("Michael Pittman Jr.", "WR"), ("Anthony Richardson", "QB")],
    "JAX": [("Travis Etienne Jr.", "RB"), ("Brian Thomas Jr.", "WR"), ("Evan Engram", "TE")],
    "TEN": [("Tony Pollard", "RB"), ("Calvin Ridley", "WR"), ("Tyjae Spears", "RB")],
    "NYJ": [("Breece Hall", "RB"), ("Garrett Wilson", "WR"), ("Davante Adams", "WR")],
    "NE": [("Rhamondre Stevenson", "RB"), ("Hunter Henry", "TE"), ("DeMario Douglas", "WR")],
    "CLE": [("Nick Chubb", "RB"), ("Jerry Jeudy", "WR"), ("David Njoku", "TE")],
    "PIT": [("Najee Harris", "RB"), ("George Pickens", "WR"), ("Jaylen Warren", "RB")],
    "ALA": [("Jalen Milroe", "QB"), ("Jam Miller", "RB"), ("Ryan Williams", "WR")],
    "UGA": [("Trevor Etienne", "RB"), ("Dillon Bell", "WR"), ("Dominic Lovett", "WR")],
    "OSU": [("Quinshon Judkins", "RB"), ("TreVeyon Henderson", "RB"), ("Jeremiah Smith", "WR")],
    "PSU": [("Nicholas Singleton", "RB"), ("Kaytron Allen", "RB"), ("Tyler Warren", "TE")],
    "TEX": [("Quinn Ewers", "QB"), ("Jaydon Blue", "RB"), ("Isaiah Bond", "WR")],
    "ORE": [("Jordan James", "RB"), ("Tez Johnson", "WR"), ("Dillon Gabriel", "QB")]
}

def get_real_players_for_team(team_abbr, team_name):
    clean_a = str(team_abbr).strip().upper()
    clean_n = str(team_name).strip().upper()
    if clean_a in STAR_ROSTER: return STAR_ROSTER[clean_a]
    for k, v in STAR_ROSTER.items():
        if k in clean_a or k in clean_n: return v
    if "PANTHERS" in clean_n or "CAROLINA" in clean_n: return STAR_ROSTER["CAR"]
    if "PACKERS" in clean_n or "GREEN BAY" in clean_n: return STAR_ROSTER["GB"]
    if "COWBOYS" in clean_n or "DALLAS" in clean_n: return STAR_ROSTER["DAL"]
    if "EAGLES" in clean_n or "PHILADELPHIA" in clean_n: return STAR_ROSTER["PHI"]
    city = team_name.split()[0] if team_name else "Team"
    return [(f"{city} Lead Rusher", "RB"), (f"{city} Top Target", "WR"), (f"{city} Goal-Line TE", "TE")]

def get_current_et_time():
    utc_now = datetime.utcnow()
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
                <span style="opacity:0.55; font-size:0.80rem;">by <strong>{b.get('user', 'Flurk')}</strong></span>
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
                <span style="opacity:0.55; font-size:0.80rem; margin-left:4px;">by <strong>{b.get('user', 'Flurk')}</strong></span>
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
            <div><strong>{b.get('matchup', 'Matchup')}</strong> <span style="opacity:0.55; font-size:0.80rem;">by <strong>{b.get('user', 'Flurk')}</strong></span></div>
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
            try: r_val = float(b.get('risk_dollars', 10.0))
            except: r_val = 10.0
            try: p_val = float(b.get('payout_dollars', b.get('payout', 19.0)))
            except: p_val = 19.0
            roi_pct = ((p_val - r_val) / max(r_val, 0.01)) * 100
            st.write(f"Risk: **${r_val:.2f}** ➔ Payout: **${p_val:.2f}**")
            st.markdown(f"<span style='color:#4ade80; font-size:0.82rem;'>Potential Profit: +${p_val - r_val:.2f} (+{roi_pct:.1f}%)</span>", unsafe_allow_html=True)

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
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.rerun()

        if is_combo:
            with st.expander("📋 View Parlay Legs, Live Points & Scores", expanded=False):
                parsed = b.get("parsed_legs", [])
                for leg_idx, leg in enumerate(parsed):
                    m_g = find_game_for_bet({"matchup": leg["matchup"]}, games_data)
                    if m_g:
                        a_sh = m_g.get("away_short", "AWAY")
                        h_sh = m_g.get("home_short", "HOME")
                        a_sc = m_g.get("away_score", 0)
                        h_sc = m_g.get("home_score", 0)
                        tot_sc = a_sc + h_sc
                        leg_live_p = calculate_live_bet_prob({
                            "status": b.get("status"),
                            "target_line": leg.get("line"),
                            "bet_direction": leg.get("side"),
                            "bet_category": leg.get("type"),
                            "picked_team": leg.get("picked_team"),
                            "win_prob": "65.0%"
                        }, m_g)
                        st.markdown(f"""
                        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:6px 10px; border-radius:6px; margin-bottom:4px;">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="opacity:0.5; font-size:0.75rem;">Leg {leg_idx+1}:</span>
                                <img src="{m_g.get('away_logo', DEFAULT_LOGO)}" width="20" height="20" style="border-radius:50%;">
                                <strong>{a_sh}</strong> @
                                <img src="{m_g.get('home_logo', DEFAULT_LOGO)}" width="20" height="20" style="border-radius:50%;">
                                <strong>{h_sh}</strong>
                                <span style="opacity:0.4;">|</span>
                                <strong style="color:#38bdf8;">{leg.get('side', '')} {leg.get('line', '')} {leg.get('picked_team', '')}</strong>
                                <span style="opacity:0.65; font-size:0.80rem;">({a_sc} - {h_sc} | {tot_sc} pts)</span>
                            </div>
                            <div>
                                <span style="font-weight:700; font-size:0.75rem; background:rgba(56,189,248,0.15); color:#38bdf8; padding:2px 7px; border-radius:4px;">
                                    {leg_live_p}
                                </span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

# Session State Initializations
if "logged_in_user" not in st.session_state: st.session_state.logged_in_user = None
if "selected_bet_id" not in st.session_state: st.session_state.selected_bet_id = None
if "combo_active_legs" not in st.session_state: st.session_state.combo_active_legs = []
if "ai_recommended_combo" not in st.session_state: st.session_state.ai_recommended_combo = None
if "active_nav_page" not in st.session_state: st.session_state.active_nav_page = "📊 My Dashboard"
if "editing_ai_combo" not in st.session_state: st.session_state.editing_ai_combo = False
if "combo_version" not in st.session_state: st.session_state.combo_version = 0
if "editing_msg_id" not in st.session_state: st.session_state.editing_msg_id = None
if "selected_admin_user" not in st.session_state: st.session_state.selected_admin_user = None
if "scroll_to_form" not in st.session_state: st.session_state.scroll_to_form = False

# Form state
if "single_selected_idx" not in st.session_state: st.session_state.single_selected_idx = 0
if "single_applied_pick" not in st.session_state: st.session_state.single_applied_pick = None
if "single_form_version" not in st.session_state: st.session_state.single_form_version = 0

# Database Load
b_data, c_data, u_data, banned_emails_data, game_snapshots_data = load_storage()
if "saved_bets" not in st.session_state: st.session_state.saved_bets = b_data
if "chat_messages" not in st.session_state: st.session_state.chat_messages = c_data
if "user_accounts" not in st.session_state: st.session_state.user_accounts = u_data
if "banned_emails" not in st.session_state: st.session_state.banned_emails = banned_emails_data
if "game_snapshots" not in st.session_state: st.session_state.game_snapshots = game_snapshots_data

# URL token persistence
query_params = st.query_params
if st.session_state.logged_in_user is None:
    token_in_url = query_params.get("session_token")
    if token_in_url:
        for u_obj in st.session_state.user_accounts.values():
            if u_obj.get("session_token") == token_in_url and not u_obj.get("is_banned", False):
                st.session_state.logged_in_user = u_obj
                break

# Authentication Gateway
if st.session_state.logged_in_user is None:
    st.title("🔮 Flurkstradamus")
    st.caption("Sign in, create an account, or recover your password.")
    tab_login, tab_signup, tab_forgot = st.tabs(["🔐 Sign In", "📝 Create Account", "🔑 Forgot Password"])
    
    with tab_login:
        with st.form("user_login_form"):
            uname = st.text_input("Username or Email", placeholder="sharpbettor").strip().lower()
            pword = st.text_input("Password", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Sign In", use_container_width=True)
            if submit_login:
                matched_user = next((u_v for u_k, u_v in st.session_state.user_accounts.items() if u_k.lower() == uname or u_v.get("email", "").lower() == uname), None)
                if matched_user and matched_user.get("password_hash") == hash_password(pword) and not matched_user.get("is_banned"):
                    if not matched_user.get("session_token"):
                        matched_user["session_token"] = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
                    matched_user["last_login"] = get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET")
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.query_params["session_token"] = matched_user["session_token"]
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
                    new_token = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
                    new_user = {
                        "username": new_uname,
                        "email": new_email,
                        "display_name": new_dname or new_uname,
                        "password_hash": hash_password(new_pword),
                        "is_admin": False,
                        "is_banned": False,
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
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.query_params["session_token"] = new_token
                    st.session_state.logged_in_user = new_user
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
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
                    st.success(f"Recovery Code: **`{token}`**")
                else:
                    st.error("Account not found.")
    st.stop()

# Active Context
current_user_profile = st.session_state.logged_in_user
active_uname = current_user_profile.get("username", "").strip().lower()
current_user = "Flurk" if active_uname == "flurk" else current_user_profile.get("display_name", current_user_profile.get("username", "Bettor"))
is_user_admin = current_user_profile.get("is_admin", False)
current_user_profile["last_active"] = get_current_et_time().strftime("%Y-%m-%d %I:%M %p ET")

# ESPN Ingestion
@st.cache_data(ttl=30)
def get_extended_games(selected_league="All Games"):
    all_games = []
    seen_ids = set()
    now_et = get_current_et_time()
    
    date_queries = [""]
    for d in range(0, 10):
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

                    if is_completed:
                        checkpoint = "Final / Game Completed"
                    elif state_text == "pre" or period == 0:
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

# Sidebar
st.sidebar.markdown(f"## 🔮 Flurkstradamus")

if st.sidebar.button(f"👤 {current_user} (@{current_user_profile.get('username')})", key="sidebar_user_profile_link", help="View and edit your profile settings"):
    st.session_state.selected_bet_id = None
    st.session_state.active_nav_page = "⚙️ Account Settings"
    st.rerun()

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
league = st.sidebar.radio("Primary League", ["NFL", "NCAA Football", "All Games"])
auto_refresh = st.sidebar.toggle("Auto-Refresh Live Scores", value=True)
refresh_interval = st.sidebar.slider("Interval (seconds)", 10, 60, 15, 5)
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

# WAR ROOM VIEW
if st.session_state.selected_bet_id is not None:
    selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)
    if st.button("⬅️ Back to Tickets", use_container_width=True):
        st.session_state.selected_bet_id = None
        st.rerun()

    if selected_bet is None:
        st.error("Ticket not found.")
        st.stop()

    is_combo = (selected_bet.get("bet_category") == "Combo" or "Leg" in selected_bet.get("type", ""))
    
    if is_combo:
        compound_p = 1.0
        legs_list = selected_bet.get("parsed_legs", [])
        for l_item in legs_list:
            m_g = find_game_for_bet({"matchup": l_item.get("matchup", "")}, games_data)
            p_str = calculate_live_bet_prob({
                "status": selected_bet.get("status"),
                "target_line": l_item.get("line"),
                "bet_direction": l_item.get("side"),
                "bet_category": l_item.get("type"),
                "picked_team": l_item.get("picked_team"),
                "win_prob": "65.0%"
            }, m_g)
            try: compound_p *= (float(p_str.replace("%", "")) / 100.0)
            except: compound_p *= 0.5
        live_ticket_win_prob = f"{compound_p * 100:.1f}%"
    else:
        live_g = find_game_for_bet(selected_bet, games_data)
        live_ticket_win_prob = calculate_live_bet_prob(selected_bet, live_g)

    st.title(f"🏟️ War Room: {selected_bet.get('matchup', 'Football Ticket')}")
    st.caption(f"Pick: `{selected_bet['bet']}` | Status: `{selected_bet.get('status')}`")

    wm1, wm2, wm3, wm4, wm5 = st.columns(5)
    try: r_val = float(selected_bet.get('risk_dollars', 10.0))
    except: r_val = 10.0
    try: p_val = float(selected_bet.get('payout_dollars', selected_bet.get('payout', 19.0)))
    except: p_val = 19.0
    wm1.metric("Risk", f"${r_val:.2f}")
    wm2.metric("Payout", f"${p_val:.2f}")
    wm3.metric("Profit Potential", f"+${p_val - r_val:.2f}")
    wm4.metric("Status", selected_bet.get("status", "Pending"))
    wm5.metric("🎲 Live Win Prob", live_ticket_win_prob)

    if is_combo:
        legs = selected_bet.get("parsed_legs", [])
        for l_idx, leg in enumerate(legs):
            leg_matchup = leg.get("matchup", "")
            m_g = find_game_for_bet({"matchup": leg_matchup}, games_data)
            leg_live_prob = calculate_live_bet_prob({
                "status": selected_bet.get("status"),
                "target_line": leg.get("line"),
                "bet_direction": leg.get("side"),
                "bet_category": leg.get("type"),
                "picked_team": leg.get("picked_team"),
                "win_prob": "65.0%"
            }, m_g)
            with st.container(border=True):
                if m_g:
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:6px; margin-bottom:8px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="background-color:#38bdf8; color:#000; font-weight:800; font-size:0.75rem; padding:2px 7px; border-radius:4px;">LEG {l_idx+1}</span>
                            <img src="{m_g['away_logo']}" width="22" height="22" style="border-radius:50%;">
                            <strong>{m_g['away_short']}</strong> @
                            <img src="{m_g['home_logo']}" width="22" height="22" style="border-radius:50%;">
                            <strong>{m_g['home_short']}</strong>
                            <span style="opacity:0.6; font-size:0.8rem;">({m_g.get('kickoff', m_g['status'])})</span>
                        </div>
                        <div>
                            <span style="background-color:rgba(56,189,248,0.15); color:#38bdf8; font-weight:700; padding:2px 8px; border-radius:6px; font-size:0.80rem;">
                                Live Win Prob: {leg_live_prob}
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write(f"**Pick:** `{leg.get('side', '')} {leg.get('line', '')} {leg.get('picked_team', '')}`")
                    lc1, lc2, lc3 = st.columns(3)
                    lc1.metric(f"{m_g['away_short']} Score", m_g['away_score'])
                    lc2.metric("Clock", m_g.get('displayClock', m_g['status']))
                    lc3.metric(f"{m_g['home_short']} Score", m_g['home_score'])
                else:
                    st.markdown(f"#### Leg {l_idx+1}: **{leg_matchup}**")
                    st.write(f"**Pick:** `{leg.get('side', '')} {leg.get('line', '')} {leg.get('picked_team', '')}`")
    else:
        live_game_info = find_game_for_bet(selected_bet, games_data)
        if live_game_info:
            c1, c2, c3 = st.columns([2, 1, 2])
            c1.image(live_game_info["away_logo"], width=45)
            c1.metric(live_game_info['away_short'], live_game_info['away_score'])
            c2.metric("Clock", live_game_info.get('displayClock', live_game_info['status']))
            c3.image(live_game_info["home_logo"], width=45)
            c3.metric(live_game_info['home_short'], live_game_info['home_score'])

            gid = live_game_info["id"]
            snap = st.session_state.game_snapshots.get(gid)
            if snap and "stages" in snap:
                st.markdown("##### 📈 Projection Evolution")
                t_rows = []
                for stg, s_val in snap["stages"].items():
                    t_rows.append({
                        "Stage": stg,
                        "Score": f"{s_val['away_score']} - {s_val['home_score']}",
                        "Projected Total": f"{s_val['proj_total']} pts",
                        "Total Drift": f"{s_val['proj_total'] - snap['open_ou']:+.1f} pts"
                    })
                st.table(t_rows)
    st.stop()
