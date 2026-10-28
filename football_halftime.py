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

    /* SIDEBAR USERNAME BUTTON LINK STYLING */
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

# Client-side mobile helpers
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
    if clean_a in STAR_ROSTER:
        return STAR_ROSTER[clean_a]
    for k, v in STAR_ROSTER.items():
        if k in clean_a or k in clean_n:
            return v
    if "PANTHERS" in clean_n or "CAROLINA" in clean_n:
        return STAR_ROSTER["CAR"]
    if "PACKERS" in clean_n or "GREEN BAY" in clean_n:
        return STAR_ROSTER["GB"]
    if "COWBOYS" in clean_n or "DALLAS" in clean_n:
        return STAR_ROSTER["DAL"]
    if "EAGLES" in clean_n or "PHILADELPHIA" in clean_n:
        return STAR_ROSTER["PHI"]
    city = team_name.split()[0] if team_name else "Team"
    return [(f"{city} Lead Rusher", "RB"), (f"{city} Top Target", "WR"), (f"{city} Goal-Line TE", "TE")]

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

    is_started = (live_m.get("state_text") != "pre" and period > 0)
    if not is_started:
        return bet_obj.get("win_prob", "50.0%")

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
    """Returns probability as a decimal float (0.0 to 1.0) for EV calculations."""
    is_combo = (bet_obj.get("bet_category") == "Combo" or "Leg" in bet_obj.get("type", ""))
    if is_combo:
        compound_p = 1.0
        legs_list = bet_obj.get("parsed_legs", [])
        if not legs_list:
            raw_str = bet_obj.get("win_prob", "50.0%").replace("%", "").strip()
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

# Global Card Renderer
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
            r_val = float(b.get('risk_dollars', 10.0))
            p_val = float(b.get('payout_dollars', 19.0))
            roi_pct = ((p_val - r_val) / max(r_val, 0.01)) * 100
            st.write(f"Risk: **${r_val:.2f}** ➔ Payout: **${p_val:.2f}**")
            st.markdown(f"<span style='color:#4ade80; font-size:0.82rem;'>Potential Profit: +${p_val - r_val:.2f} (+{roi_pct:.1f}%)</span>", unsafe_allow_html=True)

        with c_row3:
            cat_label = b.get("bet_category", b.get("type", "Single"))
            st.caption(f"Type: **{cat_label}**")
            if b.get("notes"):
                st.caption(f"*{b.get('notes')}*")

        with c_row4:
            if st.button("🏟️ War Room", key=f"open_ticket_war_{b['id']}_{real_idx}", use_container_width=True):
                st.session_state.selected_bet_id = b["id"]
                st.rerun()
            if can_delete:
                if st.button("🗑️", key=f"del_ticket_{b['id']}_{real_idx}", help="Delete ticket", use_container_width=True):
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

# Session State Keys
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
if "selected_admin_user" not in st.session_state:
    st.session_state.selected_admin_user = None
if "scroll_to_form" not in st.session_state:
    st.session_state.scroll_to_form = False

# Form state
if "single_selected_idx" not in st.session_state:
    st.session_state.single_selected_idx = 0
if "single_applied_pick" not in st.session_state:
    st.session_state.single_applied_pick = None
if "single_form_version" not in st.session_state:
    st.session_state.single_form_version = 0

# Database Load
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
    r_val = float(selected_bet.get('risk_dollars', 10.0))
    p_val = float(selected_bet.get('payout_dollars', 19.0))
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

# =========================================================================
# 1. MY DASHBOARD (EXPANDED WITH PENDING BET ANALYTICS & PROBABILITY EV)
# =========================================================================
if menu_choice == "📊 My Dashboard":
    st.subheader(f"📊 {current_user}'s Personal Betting Dashboard")
    st.caption("Complete portfolio telemetry: settled P&L, live pending stakes, and probability-modeled expected returns.")

    curr_user_clean = current_user.strip().lower()
    my_bets = [b for b in st.session_state.saved_bets if b.get("user", "").strip().lower() == curr_user_clean or (curr_user_clean == "flurk" and b.get("user", "").strip().lower() in ["flurk", "admin"])]
    tot_placed = len(my_bets)

    if tot_placed == 0:
        with st.container(border=True):
            st.markdown("### 👋 Welcome to Flurkstradamus! Let's Lock In Your First Edge")
            st.write("You haven't locked in any bet slips yet. Choose an engine below to start scanning:")
            ob_c1, ob_c2 = st.columns(2)
            if ob_c1.button("⚡ Go to Single Game Engine", use_container_width=True):
                st.session_state.active_nav_page = "⚡ Single Game Engine"
                st.rerun()
            if ob_c2.button("🔗 Go to Multi-Leg Combo Builder", use_container_width=True):
                st.session_state.active_nav_page = "🔗 Multi-Leg Combo Builder"
                st.rerun()

    # Settled metrics
    won_bets = [b for b in my_bets if b.get("status") == "Won"]
    lost_bets = [b for b in my_bets if b.get("status") == "Lost"]
    pending_bets = [b for b in my_bets if b.get("status") == "Pending"]

    tot_won_dollars = sum(float(b.get("payout_dollars", 0)) - float(b.get("risk_dollars", 0)) for b in won_bets)
    tot_lost_dollars = sum(float(b.get("risk_dollars", 0)) for b in lost_bets)
    net_pl = tot_won_dollars - tot_lost_dollars
    tot_risk = sum(float(b.get("risk_dollars", 0)) for b in my_bets if b.get("status") in ["Won", "Lost"])
    roi = (net_pl / tot_risk * 100) if tot_risk > 0 else 0.0
    avg_stake = (sum(float(b.get("risk_dollars", 0)) for b in my_bets) / tot_placed) if tot_placed > 0 else 0.0

    # Advanced Pending Analytics & Probability-Adjusted Value
    pending_risk_dollars = sum(float(b.get("risk_dollars", 0)) for b in pending_bets)
    pending_max_profit = sum(float(b.get("payout_dollars", 0)) - float(b.get("risk_dollars", 0)) for b in pending_bets)
    
    # Expected Value (Probability-Adjusted Profit)
    pending_expected_profit = 0.0
    sum_weighted_prob = 0.0
    pending_live_count = 0
    pending_sched_count = 0

    for b in pending_bets:
        r_amt = float(b.get("risk_dollars", 0))
        p_amt = float(b.get("payout_dollars", 0))
        net_win = p_amt - r_amt
        prob = get_numeric_prob(b, games_data)
        
        # EV = (Prob * Profit) - ((1 - Prob) * Risk)
        ev_ticket = (prob * net_win) - ((1.0 - prob) * r_amt)
        pending_expected_profit += ev_ticket
        sum_weighted_prob += (prob * r_amt)

        # Check if currently live
        m_check = find_game_for_bet(b, games_data)
        if m_check and m_check.get("state_text") != "pre" and m_check.get("period", 0) > 0 and not m_check.get("completed", False):
            pending_live_count += 1
        else:
            pending_sched_count += 1

    weighted_avg_prob = (sum_weighted_prob / max(pending_risk_dollars, 0.01)) * 100 if pending_risk_dollars > 0 else 0.0

    # SECTION 1: SETTLED PORTFOLIO PERFORMANCE
    st.markdown("##### 💼 Realized Performance (Settled Slips)")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Bets Logged", tot_placed, help="All slips created under your profile.")
    k2.metric("Money Won", f"${tot_won_dollars:.2f}", help="Total net profit from settled winners.")
    k3.metric("Money Lost", f"${tot_lost_dollars:.2f}", help="Total stake lost on graded losses.")
    k4.metric("Net Profit / Loss", f"${net_pl:+.2f}", delta=f"{roi:+.1f}% ROI", help="Realized bankroll net profit/loss and return on investment.")

    # SECTION 2: EXPANDED PENDING SLIPS & PROBABILITY-ADJUSTED PROFIT
    st.markdown("##### ⏳ Active Book & Pending Analytics (In Play & Scheduled)")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric(
        "Capital at Risk", 
        f"${pending_risk_dollars:.2f}", 
        f"{len(pending_bets)} Slips Active", 
        help="Total dollars currently staked on open tickets."
    )
    p2.metric(
        "Max Potential Profit", 
        f"+${pending_max_profit:.2f}", 
        help="Maximum possible net profit if 100% of your open bets win."
    )
    p3.metric(
        "Expected Profit (EV)", 
        f"${pending_expected_profit:+.2f}", 
        delta=f"Prob-Adjusted Return",
        help="True statistical expected return calculated from real-time live game probabilities minus drawdown risk."
    )
    p4.metric(
        "Portfolio Win Expectancy", 
        f"{weighted_avg_prob:.1f}%", 
        f"{pending_live_count} Live | {pending_sched_count} Upcoming",
        help="Dollar-weighted true win probability across your active tickets."
    )

    # SECTION 3: WIN RATE & DISCIPLINE
    st.markdown("##### 📈 Historical Discipline & Records")
    k5, k6, k7, k8 = st.columns(4)
    decided = len(won_bets) + len(lost_bets)
    win_pct = (len(won_bets) / decided * 100) if decided > 0 else 0.0
    k5.metric("Graded Win Rate", f"{win_pct:.1f}%", f"{len(won_bets)}W - {len(lost_bets)}L")
    k6.metric("Average Stake", f"${avg_stake:.2f}")
    k7.metric("Pending In Play", f"{len(pending_bets)} tickets")
    types_count = {}
    for b in my_bets:
        t = b.get("bet_category", b.get("type", "Single"))
        types_count[t] = types_count.get(t, 0) + 1
    most_common_type = max(types_count, key=types_count.get) if types_count else "None"
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
            ["⏳ Upcoming Games", "⚡ Live Games", "📜 Past / Completed Games", "🌐 All Matchups"]
        )
    with f_col2:
        search_query = st.text_input("🔍 Search Matchup or Team", placeholder="e.g. Eagles, Dallas, Packers, Panthers...")

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
            
        selected_idx = st.selectbox("Select Matchup", range(len(game_options)), index=st.session_state.single_selected_idx, format_func=lambda x: game_options[x], key=f"single_matchup_dropdown_v{form_ver}")
        st.session_state.single_selected_idx = selected_idx
        
        g = pool[selected_idx]
        g_id = g.get("id", str(selected_idx))
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
        std_bracket = 8.5
    else:
        period_weight = 0.25 if detected_stage == "1st Quarter" else (0.50 if detected_stage == "Halftime" else 0.75)
        expected_pts_so_far = pregame_tot * period_weight
        pace_shock_ratio = pts_scored / max(expected_pts_so_far, 1.0)
        if pace_shock_ratio > 1.25:
            final_proj = pregame_tot + ((pts_scored - expected_pts_so_far) * 0.85)
            std_bracket = 9.5
        else:
            final_proj = pregame_tot + ((pts_scored - expected_pts_so_far) * 0.30)
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

    # Section 1: Overview
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

    # Section 2: AI Strategy Engine
    with st.expander("🤖 Section 2: AI Strategy Engine & Market Filters", expanded=True):
        col_scope, col_type_filter = st.columns(2)
        scope_choice = col_scope.selectbox("Target Slate", ["🎯 Focus on Selected Game Above", "⚡ Scan Full Slate for Highest Discrepancy"])
        filter_choice = col_type_filter.selectbox("Type of Bet", [
            "⚡ Let the System Pick (All Markets Combined)", 
            "📊 Full Game Total Score Over/Under", 
            "⏱️ 2nd Half Total Points", 
            "🛡️ Spread (ATS Cover)",
            "🏆 Team Win/Loser (Moneyline)", 
            "🏈 Player Anytime Touchdown Scorer"
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
                "rationale": f"Selected because scoring tempo indicates {final_proj:.1f} pts vs open line of {pregame_tot:.1f}."
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
                "rationale": "Selected to insulate against sudden fourth-quarter scoring bursts by buying line cushion."
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
                "rationale": f"Selected to provide an insulated cover floor for {s_abbr}."
            }
        ]

        # Touchdowns: Real Player Names Guaranteed
        home_players = get_real_players_for_team(tg_home_short, active_game_for_strat["home_team"])
        away_players = get_real_players_for_team(tg_away_short, active_game_for_strat["away_team"])

        p1_name, p1_pos = home_players[0]
        p2_name, p2_pos = away_players[0]
        p3_name, p3_pos = home_players[1] if len(home_players) > 1 else away_players[1]

        touchdown_bets = [
            {
                "type": f"Anytime Touchdown ({obj_tag})",
                "pick": f"{p1_name} ({p1_pos} - {tg_home_short}) Any Time TD",
                "prob": 0.58 if "Safe Floor" in strategy_dial else 0.52,
                "category": "Anytime TD",
                "side": "TD",
                "target_line": 1.0,
                "picked_team": p1_name,
                "game_index": strat_game_index,
                "est_payout_multiplier": 1.85,
                "roi_label": "+85% Profit (-115)",
                "drift_info": "Red-zone share & offensive goal-line touches",
                "rationale": f"{p1_name} ({p1_pos}) commands {tg_home_short}'s goal-line touches inside the 5-yard line with unmatched red-zone volume."
            },
            {
                "type": f"Anytime Touchdown ({obj_tag})",
                "pick": f"{p2_name} ({p2_pos} - {tg_away_short}) Any Time TD",
                "prob": 0.46 if "Safe Floor" in strategy_dial else 0.41,
                "category": "Anytime TD",
                "side": "TD",
                "target_line": 1.0,
                "picked_team": p2_name,
                "game_index": strat_game_index,
                "est_payout_multiplier": 2.25,
                "roi_label": "+125% Profit (+125)",
                "drift_info": "Primary red-zone target volume",
                "rationale": f"{p2_name} ({p2_pos}) is {tg_away_short}'s lead target in goal-to-go opportunities in high-scoring game scripts."
            },
            {
                "type": f"Anytime Touchdown ({obj_tag})",
                "pick": f"{p3_name} ({p3_pos} - {tg_home_short}) Any Time TD",
                "prob": 0.36 if "Safe Floor" in strategy_dial else 0.32,
                "category": "Anytime TD",
                "side": "TD",
                "target_line": 1.0,
                "picked_team": p3_name,
                "game_index": strat_game_index,
                "est_payout_multiplier": 3.10,
                "roi_label": "+210% Profit (+210)",
                "drift_info": "High-value situational red zone threat",
                "rationale": f"{p3_name} ({p3_pos}) serves as a key red-zone target on goal-line play-action passing concepts."
            }
        ]

        if filter_choice == "📊 Full Game Total Score Over/Under":
            strat_candidates = full_totals_bets
        elif filter_choice == "🛡️ Spread (ATS Cover)":
            strat_candidates = spread_bets
        elif filter_choice == "🏈 Player Anytime Touchdown Scorer":
            strat_candidates = touchdown_bets
        else:
            strat_candidates = [spread_bets[0], full_totals_bets[0], touchdown_bets[0]]

        for idx, sc in enumerate(strat_candidates[:3]):
            tier_lbl = ["🥇 BEST", "🥈 BETTER", "🥉 GOOD"][idx]
            st.markdown(f"""
            <div class="rec-card-box">
                <div class="rec-header-row">
                    <div>
                        <strong style="font-size:0.92rem;">{tier_lbl}</strong>
                        <span style="opacity:0.4; margin:0 4px;">•</span>
                        <code style="font-size:0.80rem;">{sc['type']}</code>
                    </div>
                    <div class="rec-matchup-meta">
                        <span style="background-color:rgba(255,255,255,0.08); padding:1px 5px; border-radius:3px; font-weight:700; font-size:0.75rem;">[{tg_league_str}]</span>
                        <img src="{tg_away_logo}" width="20" height="20" style="border-radius:50%;">
                        <strong>{tg_away_short}</strong>
                        <span style="opacity:0.4;">@</span>
                        <img src="{tg_home_logo}" width="20" height="20" style="border-radius:50%;">
                        <strong>{tg_home_short}</strong>
                        <span style="opacity:0.65; font-size:0.75rem; margin-left:2px;">({tg_date_str})</span>
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

    # Section 3: Wager Type & Lock In Bet Slip
    applied = st.session_state.single_applied_pick
    with st.expander("📝 Section 3: Wager Type & Lock In Bet Slip", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}_v{form_ver}")
            away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}_v{form_ver}")
            pregame_total = st.number_input("Pre-Game Baseline Total", value=float(espn_ou), step=0.5, format="%.1f", key=f"pre_{g_id}_v{form_ver}")
        with c2:
            h_pts_in = st.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"], key=f"hp_{g_id}_v{form_ver}")
            a_pts_in = st.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"], key=f"ap_{g_id}_v{form_ver}")
            spread_line = st.number_input(f"{g['home_short']} Spread", value=float(espn_spread), step=0.5, format="%.1f", key=f"spd_{g_id}_v{form_ver}")

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
            key=f"btype_{g_id}_v{form_ver}"
        )

        with st.form(f"single_form_{g_id}_v{form_ver}"):
            if bet_type == "Game Total":
                f1, f2 = st.columns(2)
                side = f1.selectbox("Side", ["Under", "Over"], index=0 if (applied and applied.get("side") == "Under") else 1)
                default_strike = round_half_point(applied["target_line"]) if (applied and applied.get("target_line")) else round_half_point(final_proj)
                strike = f2.number_input("Target Line (pts)", value=float(default_strike), step=0.5, format="%.1f")
                picked_t = None
                dynamic_note = f"Game Total: {side} {strike:.1f} | Model Proj: {final_proj:.1f} pts ({delta_full:+.1f} vs open)"
            elif bet_type == "Point Spread (ATS)":
                f1, f2 = st.columns(2)
                picked_t = f1.selectbox("Covering Team", [home_team, away_team])
                default_spread = round_half_point(applied["target_line"]) if (applied and applied.get("target_line") is not None) else round_half_point(spread_line)
                strike = f2.number_input("Spread Line", value=float(default_spread), step=0.5, format="%.1f")
                side = "Spread"
                dynamic_note = f"Point Spread: {picked_t} {strike:+.1f} | Expected ATS Margin: {live_proj_margin:+.1f} pts"
            elif bet_type == "Straight Up Winner (Moneyline)":
                picked_t = st.selectbox("Outright Winner", [home_team, away_team])
                strike = None
                side = "Moneyline"
                dynamic_note = f"Moneyline Winner: {picked_t} | Model Outright Win Expectancy: {live_h_prob*100 if picked_t==home_team else live_a_prob*100:.1f}%"
            else:
                default_p = applied["picked_team"] if (applied and applied.get("picked_team")) else p1_name
                picked_t = st.text_input("Player to Score TD", value=default_p)
                strike = 1.0
                side = "Anytime TD"
                dynamic_note = f"Touchdown Prop: {picked_t} Any Time TD | Red zone share & goal-line touch volume play"

            p1, p2 = st.columns(2)
            risk_amt = p1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
            mult = applied.get("est_payout_multiplier", 1.91) if applied else 1.91
            payout_amt = p2.number_input("Payout ($)", min_value=1.0, value=round(risk_amt * mult, 2))
            ticket_notes = st.text_input("Notes", value=dynamic_note)

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
        c_timing_view = c_fcol1.selectbox("Game Status Filter (Combo)", ["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"])
    with c_fcol2:
        c_search = c_fcol2.text_input("🔍 Search Game Slate", placeholder="e.g. Chiefs, Lions, Ravens...")

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
        col_strat1, col_strat2 = st.columns(2)
        active_candidate_games = [gm for gm in c_pool if not gm.get("completed", False)]
        if not active_candidate_games:
            active_candidate_games = c_pool
        max_possible_legs = min(12, max(2, len(active_candidate_games)))

        suggest_legs_count = col_strat1.number_input("Target Legs (Up to 12)", min_value=2, max_value=max_possible_legs, value=min(max(len(st.session_state.combo_active_legs), 3), max_possible_legs))
        strategy_mode = col_strat2.selectbox("Strategy Objective", [
            "🎯 Maximum Win Probability (Safest Floor)",
            "🔥 High Expected Value (+EV Total Edge)",
            "🏆 Straight-Up Moneyline Dominance"
        ])

        generate_clicked = st.button("⚡ Scan & Recommend Across Slates", use_container_width=True)

        if generate_clicked and c_pool:
            candidate_legs = []
            for g_c in active_candidate_games:
                c_h, c_a = g_c["home_team"], g_c["away_team"]
                c_h_abbr, c_a_abbr = g_c["home_short"], g_c["away_short"]
                c_tot_pts = g_c["home_score"] + g_c["away_score"]
                c_ou = g_c.get("market_ou", 47.5)
                c_period = g_c.get("period", 1)
                proj_tot = c_ou if c_period <= 1 else (c_tot_pts + (c_ou * 0.475))
                sigma = 8.0 if c_period <= 1 else 6.0
                h_prob = calculate_moneyline_prob(g_c["home_score"] + 14, g_c["away_score"] + 14, g_c.get("home_record", "0-0"), g_c.get("away_record", "0-0"))

                if "Maximum Win Probability" in strategy_mode:
                    cushion_line = round_half_point(proj_tot + (sigma * 1.5))
                    p = calculate_win_prob(cushion_line, proj_tot, sigma, is_under=True)
                    candidate_legs.append({
                        "leg_id": f"tot_{g_c['id']}",
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
                    tgt_line = round_half_point(c_ou)
                    p = calculate_win_prob(tgt_line, proj_tot, sigma, is_under=(proj_tot < c_ou))
                    candidate_legs.append({
                        "leg_id": f"ev_{g_c['id']}",
                        "matchup_idx": c_pool.index(g_c),
                        "type": "Game Total",
                        "side": "Under" if proj_tot < c_ou else "Over",
                        "line": tgt_line,
                        "picked_team": c_h,
                        "prob": p,
                        "desc": f"{'Under' if proj_tot < c_ou else 'Over'} {tgt_line:.1f}",
                        "detail": f"Edge: {abs(proj_tot - c_ou):.1f} pts",
                        "score_metric": abs(proj_tot - c_ou) * p
                    })
                else:
                    ml_fav = c_h if h_prob >= 0.5 else c_a
                    fav_abbr = c_h_abbr if h_prob >= 0.5 else c_a_abbr
                    candidate_legs.append({
                        "leg_id": f"ml_{g_c['id']}",
                        "matchup_idx": c_pool.index(g_c),
                        "type": "Straight Up Winner",
                        "side": "Under",
                        "line": round_half_point(c_ou),
                        "picked_team": ml_fav,
                        "prob": max(h_prob, 1.0 - h_prob),
                        "desc": f"{fav_abbr} ML",
                        "detail": f"{max(h_prob, 1.0 - h_prob)*100:.1f}%",
                        "score_metric": max(h_prob, 1.0 - h_prob)
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

        if st.session_state.ai_recommended_combo:
            num_legs_rec = len(st.session_state.ai_recommended_combo)
            comp_p = 1.0
            for l_item in st.session_state.ai_recommended_combo:
                comp_p *= l_item["prob"]

            st.markdown(f"#### 🎯 Recommended Ticket ({num_legs_rec} Legs):")
            for idx_ai, l_ai in enumerate(st.session_state.ai_recommended_combo):
                m_idx = min(max(l_ai.get("matchup_idx", 0), 0), len(c_pool) - 1)
                g_match = c_pool[m_idx]
                st.markdown(f"""
                <div class="rec-card-box">
                    <div class="rec-header-row">
                        <div><span style="background-color: #22c55e; color: #000; font-weight: 800; font-size: 0.75rem; padding: 2px 7px; border-radius: 4px;">LEG {idx_ai+1}</span></div>
                        <div class="rec-matchup-meta">
                            <img src="{g_match['away_logo']}" width="20" height="20" style="border-radius: 50%;">
                            <strong>{g_match['away_short']}</strong> @
                            <img src="{g_match['home_logo']}" width="20" height="20" style="border-radius: 50%;">
                            <strong>{g_match['home_short']}</strong>
                            <span style="opacity: 0.65; font-size: 0.75rem; margin-left: 2px;">({g_match.get('kickoff')})</span>
                        </div>
                    </div>
                    <div class="rec-pick-row">
                        <strong style="color: #4ade80; font-size: 1.05rem;">{l_ai['desc']}</strong>
                        <span class="badge-prob">{l_ai['prob']*100:.1f}% Win Prob</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            m_rec1, m_rec2 = st.columns([2, 1], vertical_alignment="center")
            m_rec1.metric("Compound Recommended Win Expectancy", f"{comp_p * 100:.1f}%")
            if m_rec2.button("📥 Apply Picks into Ticket Slip", use_container_width=True):
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
            sel_matchup = st.selectbox(f"Leg {i+1} Matchup", range(len(game_choices)), index=safe_m_idx, format_func=lambda x: game_choices[x], key=f"m_sel_{i}_v{ver}")
            leg_data["matchup_idx"] = sel_matchup
            leg_g = c_pool[sel_matchup]

            wager_cat = st.radio(f"Wager Type (Leg {i+1})", ["Game Total", "Straight Up Winner"], horizontal=True, index=0 if leg_data["type"] == "Game Total" else 1, key=f"wtype_{i}_v{ver}")
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
    st.caption("Active slips with live in-game win probabilities, scoreboard telemetry, and total points.")

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
            render_ticket_card(b, real_idx, games_data, can_delete=True)

# =========================================================================
# 5. LEADERBOARD
# =========================================================================
elif menu_choice == "🏆 Leaderboard":
    st.subheader("🏆 Leaderboard")
    st.caption("Consensus standings, return on investment, member tenure, and betting volume.")

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
        if not acc.get("is_public", True): continue
        last_act = acc.get("last_active", "")
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
    st.caption("Real-time stream of all community tickets with live game telemetry, scores, and win probabilities.")

    feed_tickets = []
    for b in st.session_state.saved_bets:
        u_raw = b.get("user", "Flurk").strip().lower()
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
# 7. THE LOCKER ROOM
# =========================================================================
elif menu_choice == "💬 The Locker Room":
    st.subheader("💬 The Locker Room")
    with st.form("send_msg_form", clear_on_submit=True):
        user_msg = st.text_input("Send a message", placeholder="Share your thoughts...")
        if st.form_submit_button("Post Message", use_container_width=True) and user_msg.strip():
            st.session_state.chat_messages.insert(0, {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip(),
                "time": get_current_et_time().strftime("%I:%M %p ET"),
                "text": user_msg.strip(),
                "reactions": {},
                "replies": []
            })
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

elif menu_choice == "💡 How It Works":
    st.subheader("💡 How It Works: The User Manual")
    st.markdown("""
    * **📊 My Dashboard**: Review personal performance, money won, money lost, ROI, active capital at risk, and probability-adjusted expected profit.
    * **⚡ Single Game Engine**: Filter games by upcoming, live, or past. Model projections, point spreads, anytime touchdown props with guaranteed real player names, and auto-scrolling form loading.
    * **🔗 Multi-Leg Combo Builder**: Scan slates for optimal multi-leg parlay opportunities with compound true win probabilities.
    * **🏟️ In-Game War Room**: Click any single or multi-leg combo ticket in Locked Bets History or Live Squad Feed to evaluate live score updates, all team logos, and live probability chances of winning.
    * **⚙️ Account Settings**: Personalize your profile, bio, avatar, and privacy settings.
    """)

elif menu_choice == "📖 Model Methodology & Math":
    st.subheader("📖 Flurkstradamus Machine Learning & Mathematical Architecture")
    st.latex(r"Z = \frac{\text{Line} - \mu_{\text{in-game}}}{\sigma_{\text{decay}}}")
    st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")
    st.latex(r"P(\text{TD}) = 1 - e^{-\left(\lambda_{\text{Team TD}} \times \text{Player Share} \times \text{Defensive Matchup Modifier}\right)}")

elif menu_choice == "⚙️ Account Settings":
    st.subheader("⚙️ Account Settings & Profile Management")
    with st.form("account_settings_form"):
        new_display = st.text_input("Display Name", value=current_user_profile.get("display_name", ""))
        new_email = st.text_input("Email Address", value=current_user_profile.get("email", ""))
        new_team = st.text_input("Favorite Team", value=current_user_profile.get("favorite_team", "NFL"))
        new_avatar = st.text_input("Profile Avatar URL", value=current_user_profile.get("avatar_url", ""))
        new_bio = st.text_area("Short Bio", value=current_user_profile.get("bio", "Football strategist."))
        pub_lead = st.toggle("Show My Profile on Public Leaderboard", value=current_user_profile.get("is_public", True))
        share_fd = st.toggle("Publish My Slips to Live Squad Feed", value=current_user_profile.get("share_feed", True))
        p_change1 = st.text_input("New Password", type="password")
        p_change2 = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Save Account Settings", use_container_width=True):
            if new_display.strip(): current_user_profile["display_name"] = new_display.strip()
            if new_email.strip(): current_user_profile["email"] = new_email.strip()
            current_user_profile["favorite_team"] = new_team.strip()
            current_user_profile["avatar_url"] = new_avatar.strip()
            current_user_profile["bio"] = new_bio.strip()
            current_user_profile["is_public"] = pub_lead
            current_user_profile["share_feed"] = share_fd
            if p_change1 and p_change1 == p_change2 and len(p_change1) >= 4:
                current_user_profile["password_hash"] = hash_password(p_change1)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots)
            st.success("Settings updated!")
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
            u_display_clean = u_info.get("display_name", "").strip().lower()
            u_bets = [b for b in st.session_state.saved_bets if b.get("user", "").strip().lower() in [u_clean, u_display_clean]]
            
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
