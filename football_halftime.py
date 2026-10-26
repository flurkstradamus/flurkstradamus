import streamlit as st
import requests
import math
import json
import os
import re
from datetime import datetime

st.set_page_config(
    page_title="Flurkstradamus Edge Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CONFIGURATION & PERSISTENCE ENGINE
# ==========================================
GROUP_PASSCODE = "FLURK2026"
JSONBIN_BIN_ID = "6ade77dbac6210605a51a450"    # Paste your Bin ID here if you have it
JSONBIN_API_KEY = "$2a$10$K8VFT4hzyxMbtkBLLtlaNu/ZB8WthYSFYlKEutPEE4Qg8hi8lA6Ya"   # Paste your Master Key here if you have it

DB_FILE = "bets_history.json"

def fetch_cloud_bets():
    if JSONBIN_BIN_ID and JSONBIN_API_KEY:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
        headers = {"X-Master-Key": JSONBIN_API_KEY}
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                return r.json().get("record", {}).get("bets", [])
        except Exception:
            pass
    return None

def push_cloud_bets(bets):
    if JSONBIN_BIN_ID and JSONBIN_API_KEY:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
        headers = {
            "Content-Type": "application/json",
            "X-Master-Key": JSONBIN_API_KEY
        }
        try:
            r = requests.put(url, json={"bets": bets}, headers=headers, timeout=5)
            return r.status_code == 200
        except Exception:
            pass
    return False

def load_bets():
    cloud_records = fetch_cloud_bets()
    local_records = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                local_records = json.load(f)
        except Exception:
            local_records = []

    merged = {b["id"]: b for b in (local_records + (cloud_records or []))}
    merged_list = list(merged.values())
    merged_list.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return merged_list

def save_bets(bets):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(bets, f, indent=4)
    except Exception:
        pass
    push_cloud_bets(bets)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "selected_bet_id" not in st.session_state:
    st.session_state.selected_bet_id = None

# Access Gatekeeper
if not st.session_state.authenticated:
    st.title("🔮 Flurkstradamus: Private Syndicate")
    st.caption("Mobile Edge & Consensus Terminal")
    with st.form("pin_login"):
        pin_entry = st.text_input("Group Passcode", type="password")
        login_btn = st.form_submit_button("Enter Terminal")
        if login_btn:
            if pin_entry == GROUP_PASSCODE:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid passcode.")
    st.stop()

if "saved_bets" not in st.session_state:
    st.session_state.saved_bets = load_bets()

# ==========================================
# ADVANCED STATISTICAL PROJECTION ENGINES
# ==========================================
def calculate_win_prob(target_line, projected_total, std_dev=7.0, is_under=True):
    std_dev = max(std_dev, 0.75)
    z = (target_line - projected_total) / std_dev
    under_prob = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return under_prob if is_under else (1.0 - under_prob)

def calculate_moneyline_prob(home_proj, away_proj, home_record_str, away_record_str):
    spread_exp = home_proj - away_proj

    def parse_rec(rec):
        parts = re.findall(r"\d+", rec)
        if len(parts) >= 2:
            w, l = float(parts[0]), float(parts[1])
            return w / max(w + l, 1.0)
        return 0.5

    h_pct = parse_rec(home_record_str)
    a_pct = parse_rec(away_record_str)
    record_delta = (h_pct - a_pct) * 7.0

    effective_spread = spread_exp + record_delta
    prob_home_win = 1.0 / (1.0 + math.exp(-effective_spread / 6.5))
    return max(min(prob_home_win, 0.99), 0.01)

# ==========================================
# ESPN LIVE SCOREBOARD DATA FEED
# ==========================================
@st.cache_data(ttl=10)
def get_live_games(league_code="nfl"):
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/{league_code}/scoreboard"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        games = []
        for event in data.get("events", []):
            comp = event["competitions"][0]
            competitors = comp["competitors"]
            home = next(c for c in competitors if c["homeAway"] == "home")
            away = next(c for c in competitors if c["homeAway"] == "away")
            status_obj = comp["status"]

            games.append({
                "id": str(event.get("id", "")),
                "name": event["name"],
                "home_team": home["team"]["displayName"],
                "home_short": home["team"].get("shortDisplayName", home["team"]["displayName"]),
                "home_record": home.get("records", [{}])[0].get("summary", "0-0") if home.get("records") else "0-0",
                "away_team": away["team"]["displayName"],
                "away_short": away["team"].get("shortDisplayName", away["team"]["displayName"]),
                "away_record": away.get("records", [{}])[0].get("summary", "0-0") if away.get("records") else "0-0",
                "home_score": int(home.get("score", 0)),
                "away_score": int(away.get("score", 0)),
                "status": status_obj["type"]["shortDetail"],
                "completed": status_obj["type"].get("completed", False),
                "period": status_obj.get("period", 1),
                "displayClock": status_obj.get("displayClock", "0:00")
            })
        return games
    except Exception:
        return []

def find_game_for_bet(bet, games):
    m_text = bet.get("matchup", "").lower()
    h_team = bet.get("home_team", "").lower()
    a_team = bet.get("away_team", "").lower()
    for g_item in games:
        g_h = g_item["home_team"].lower()
        g_a = g_item["away_team"].lower()
        g_h_short = g_item["home_short"].lower()
        g_a_short = g_item["away_short"].lower()
        if (h_team and h_team in g_h) or (a_team and a_team in g_a):
            return g_item
        if (g_h in m_text or g_h_short in m_text) and (g_a in m_text or g_a_short in m_text):
            return g_item
        if g_h in m_text or g_a in m_text:
            return g_item
    return None

# ==========================================
# MOBILE-FIRST SIDEBAR NAVIGATION
# ==========================================
st.sidebar.markdown("## 🔮 Flurkstradamus")
current_user = st.sidebar.text_input("Bettor Handle", value="Flurk")
league = st.sidebar.radio("Active League", ["NFL", "NCAA Football"])
league_param = "nfl" if league == "NFL" else "college-football"

# Live Refresh Controls
st.sidebar.markdown("---")
st.sidebar.markdown("### ⏱️ Live Updates")
auto_refresh = st.sidebar.toggle("Auto-Refresh Live Scores", value=True)
refresh_interval = st.sidebar.slider("Interval (seconds)", min_value=10, max_value=60, value=15, step=5)
if st.sidebar.button("🔄 Manual Scoreboard Sync"):
    st.cache_data.clear()
    st.session_state.saved_bets = load_bets()
    st.rerun()

st.sidebar.markdown("---")
menu_choice = st.sidebar.radio(
    "Navigation Menu",
    [
        "Single Game Engine",
        "2-5 Leg Combo Builder",
        "Locked Bets History",
        "🏆 Squad Leaderboard",
        "📖 Model Methodology & Math"
    ]
)

# ==========================================
# CORE APP FRAGMENT (AUTO-UPDATES LIVE)
# ==========================================
@st.fragment(run_every=refresh_interval if auto_refresh else None)
def render_main_engine():
    games_data = get_live_games(league_param)

    # ------------------------------------------
    # DETAIL PAGE: IN-GAME BET WAR ROOM
    # ------------------------------------------
    if st.session_state.selected_bet_id is not None:
        selected_bet = next((b for b in st.session_state.saved_bets if b["id"] == st.session_state.selected_bet_id), None)

        if st.button("⬅️ Back to Main Dashboard"):
            st.session_state.selected_bet_id = None
            st.rerun()

        if selected_bet is None:
            st.error("Selected ticket could not be found.")
            return

        st.title(f"🏟️ War Room: {selected_bet['matchup']}")
        st.caption(f"Bettor: **{selected_bet.get('user', 'Flurk')}** | Pick: `{selected_bet['bet']}` | Logged: {selected_bet.get('date', 'N/A')}")

        target_line = selected_bet.get("target_line")
        bet_dir = selected_bet.get("bet_direction", "Under")
        bet_category = selected_bet.get("bet_category", "Total")
        live_game_info = find_game_for_bet(selected_bet, games_data)

        if not live_game_info:
            st.warning("Live feed for this game is currently inactive.")
            st.write(f"Target: **{bet_dir} {target_line}**" if target_line else f"Pick: **{selected_bet['bet']}**")
            return

        curr_away = live_game_info["away_score"]
        curr_home = live_game_info["home_score"]
        total_pts = curr_away + curr_home
        is_final = live_game_info.get("completed", False) or "final" in live_game_info["status"].lower()
        period = live_game_info.get("period", 2)

        col_s1, col_s2, col_s3 = st.columns([2, 1, 2])
        col_s1.markdown(f"### {live_game_info['away_team']}\n# **{curr_away}**\n`{live_game_info['away_record']}`")
        col_s2.markdown(f"### Status\n**{live_game_info['status']}**\nClock: `{live_game_info.get('displayClock', 'Live')}`")
        col_s3.markdown(f"### {live_game_info['home_team']}\n# **{curr_home}**\n`{live_game_info['home_record']}`")

        st.markdown("---")

        if bet_category == "Moneyline":
            h_prob = calculate_moneyline_prob(curr_home, curr_away, live_game_info["home_record"], live_game_info["away_record"])
            picked_home = selected_bet.get("picked_team") == live_game_info["home_team"]
            win_prob = h_prob if picked_home else (1.0 - h_prob)

            m1, m2, m3 = st.columns(3)
            m1.metric("Selected Winner", selected_bet.get("picked_team", "N/A"))
            m2.metric("Current Margin", f"{curr_home - curr_away:+d} pts")
            m3.metric("Live Win Probability", f"{win_prob * 100:.1f}%")

        else:
            is_under = (bet_dir == "Under")
            decay_sigma = 7.0 if period <= 2 else (4.5 if period == 3 else 2.0)
            frac_rem = 0.5 if period <= 2 else (0.25 if period == 3 else 0.08)
            proj_pts = selected_bet.get("model_proj", total_pts + 10.0)

            in_game_proj = total_pts + ((proj_pts - total_pts) * frac_rem) if proj_pts > total_pts else total_pts + 3.0
            prob = calculate_win_prob(target_line, in_game_proj, std_dev=decay_sigma, is_under=is_under)
            cushion = target_line - total_pts if is_under else total_pts - target_line

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Current Total", f"{total_pts} pts")
            m2.metric("Target Line", f"{bet_dir} {target_line}")
            m3.metric("Safety Cushion", f"{cushion:+.1f} pts")
            m4.metric("Live Win Prob", f"{prob * 100:.1f}%")

        return

    # ------------------------------------------
    # PAGE 1: BRACKETED SINGLE GAME ENGINE
    # ------------------------------------------
    if menu_choice == "Single Game Engine":
        st.subheader("⚡ Bracketed Single Game Edge Engine")

        if games_data:
            game_options = [f"{g['away_team']} @ {g['home_team']} ({g['status']})" for g in games_data]
            selected_idx = st.selectbox("Select Active Matchup", range(len(game_options)), format_func=lambda x: game_options[x])
            g = games_data[selected_idx]
            g_id = g.get("id", str(selected_idx))
        else:
            st.warning("Manual Matchup Mode")
            g = {"id": "man", "home_team": "Home", "away_team": "Away", "home_score": 14, "away_score": 10, "status": "Halftime", "home_record": "6-2", "away_record": "5-3"}
            g_id = "man"

        bracket_stage = st.select_slider(
            "Current Game Checkpoint / Bracket",
            options=["Pre-Game", "After 1st Quarter", "Halftime", "After 3rd Quarter"],
            value="Halftime"
        )

        c1, c2 = st.columns(2)
        with c1:
            home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}")
            away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}")
            home_rec = st.text_input(f"{home_team} Season Record", value=g.get("home_record", "0-0"), key=f"h_rec_{g_id}")
            away_rec = st.text_input(f"{away_team} Season Record", value=g.get("away_record", "0-0"), key=f"a_rec_{g_id}")
            pregame_total = st.number_input("Pre-Game Baseline Total", value=47.5, step=0.5, key=f"pre_{g_id}")

        with c2:
            sc1, sc2 = st.columns(2)
            h_pts = sc1.number_input(f"{home_team} Score", min_value=0, value=g["home_score"], key=f"hp_{g_id}")
            a_pts = sc2.number_input(f"{away_team} Score", min_value=0, value=g["away_score"], key=f"ap_{g_id}")
            market_line = st.number_input("Market Total Offered (pts)", value=round(pregame_total) + 0.5, step=0.5, key=f"mkt_{g_id}")

        pts_scored = h_pts + a_pts
        margin = abs(h_pts - a_pts)

        if bracket_stage == "Pre-Game":
            final_proj = pregame_total
            std_bracket = 8.5
        elif bracket_stage == "After 1st Quarter":
            pace_diff = pts_scored - (pregame_total * 0.25)
            final_proj = pregame_total + (pace_diff * 0.40)
            std_bracket = 7.5
        elif bracket_stage == "Halftime":
            pace_diff = pts_scored - (pregame_total * 0.525)
            script = -3.5 if margin >= 17 else (-1.5 if margin >= 10 else (1.5 if margin <= 3 else 0.0))
            final_proj = pts_scored + (pregame_total * 0.475) + (pace_diff * 0.30) + script + 0.5
            std_bracket = 6.0
        else:
            pace_diff = pts_scored - (pregame_total * 0.775)
            final_proj = pts_scored + (pregame_total * 0.225) + (pace_diff * 0.20)
            std_bracket = 3.5

        st.markdown("---")
        st.subheader(f"📊 Projected Consensus ({bracket_stage})")

        home_win_prob = calculate_moneyline_prob(h_pts + (final_proj / 2.0), a_pts + (final_proj / 2.0), home_rec, away_rec)
        away_win_prob = 1.0 - home_win_prob

        m1, m2, m3 = st.columns(3)
        m1.metric("Projected Total", f"{final_proj:.1f} pts", delta=f"{final_proj - pregame_total:+.1f} shift")
        m2.metric(f"{home_team} Win Expectancy", f"{home_win_prob * 100:.1f}%")
        m3.metric(f"{away_team} Win Expectancy", f"{away_win_prob * 100:.1f}%")

        st.markdown("---")
        st.subheader("🎯 Suggested Edge Tiers")

        line_good = round(final_proj + 6.5) + 0.5
        line_better = round(final_proj + 3.5) + 0.5
        prob_good = calculate_win_prob(line_good, final_proj, std_bracket, is_under=True)
        prob_better = calculate_win_prob(line_better, final_proj, std_bracket, is_under=True)

        c_t1, c_t2, c_t3 = st.columns(3)
        c_t1.success(f"🟢 **Safe Floor: Under {line_good}**\n\nWin Prob: **{prob_good * 100:.1f}%**")
        c_t2.info(f"🟡 **Balanced: Under {line_better}**\n\nWin Prob: **{prob_better * 100:.1f}%**")
        fav_team = home_team if home_win_prob > 0.5 else away_team
        fav_prob = max(home_win_prob, away_win_prob)
        c_t3.warning(f"🔥 **Straight-Up Moneyline: {fav_team}**\n\nWin Prob: **{fav_prob * 100:.1f}%**")

        st.markdown("---")
        st.subheader(f"🔒 Lock In Ticket as {current_user}")

        with st.form("single_bet_form"):
            f1, f2, f3 = st.columns(3)
            bet_type = f1.selectbox("Wager Type", ["Game Total", "Straight Up Winner (Moneyline)"])

            if bet_type == "Game Total":
                side = f2.selectbox("Side", ["Under", "Over"])
                strike = f3.number_input("Line (pts)", value=float(line_better), step=0.5)
                picked_t = None
            else:
                side = "Moneyline"
                picked_t = f2.selectbox("Winner", [home_team, away_team])
                strike = None
                f3.write("")

            p1, p2, p3 = st.columns(3)
            risk_amt = p1.number_input("Risk Amount ($)", min_value=1.0, value=10.0, step=5.0)
            payout_amt = p2.number_input("Potential Total Return ($)", min_value=1.0, value=19.0, step=5.0)
            ticket_notes = p3.text_input("Notes", "Model edge play")

            lock_submit = st.form_submit_button("Lock In Bet")
            if lock_submit:
                if bet_type == "Game Total":
                    prob_calc = calculate_win_prob(strike, final_proj, std_bracket, is_under=(side == "Under"))
                    bet_label = f"{side} {strike}"
                else:
                    prob_calc = home_win_prob if picked_t == home_team else away_win_prob
                    bet_label = f"{picked_t} ML"

                ticket_record = {
                    "id": str(datetime.now().timestamp()),
                    "user": current_user.strip() if current_user.strip() else "Flurk",
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "type": "Single",
                    "bet_category": "Total" if bet_type == "Game Total" else "Moneyline",
                    "home_team": home_team,
                    "away_team": away_team,
                    "picked_team": picked_t,
                    "matchup": f"{away_team} @ {home_team}",
                    "bet": bet_label,
                    "target_line": strike,
                    "bet_direction": side,
                    "risk_dollars": float(risk_amt),
                    "payout_dollars": float(payout_amt),
                    "model_proj": round(final_proj, 1),
                    "bracket": bracket_stage,
                    "win_prob": f"{prob_calc * 100:.1f}%",
                    "status": "Pending",
                    "notes": ticket_notes
                }
                st.session_state.saved_bets.insert(0, ticket_record)
                save_bets(st.session_state.saved_bets)
                st.success("Ticket saved to history!")

    # ------------------------------------------
    # PAGE 2: 2 TO 5 LEG COMBO BUILDER
    # ------------------------------------------
    elif menu_choice == "2-5 Leg Combo Builder":
        st.subheader("🔗 Multi-Leg Combo Builder (2 to 5 Legs)")
        legs_count = st.radio("Select Number of Legs", [2, 3, 4, 5], horizontal=True)

        combo_legs = []
        compound_prob = 1.0
        game_choices = [f"{g['away_team']} @ {g['home_team']} ({g['status']})" for g in games_data] if games_data else ["Manual Matchup"]

        for i in range(legs_count):
            st.markdown(f"#### Leg {i+1}")
            def_idx = min(i, len(game_choices) - 1)
            selected_idx = st.selectbox(f"Matchup for Leg {i+1}", range(len(game_choices)), index=def_idx, format_func=lambda x: game_choices[x], key=f"leg_sel_{i}")

            if games_data:
                leg_g = games_data[selected_idx]
                d_h, d_a = leg_g["home_team"], leg_g["away_team"]
                d_h_pts, d_a_pts = leg_g["home_score"], leg_g["away_score"]
                d_h_rec, d_a_rec = leg_g.get("home_record", "0-0"), leg_g.get("away_record", "0-0")
            else:
                d_h, d_a = f"Home {i+1}", f"Away {i+1}"
                d_h_pts, d_a_pts = 14, 10
                d_h_rec, d_a_rec = "5-2", "4-3"

            col_a, col_b, col_c = st.columns(3)
            wager_cat = col_a.selectbox(f"Wager Type (Leg {i+1})", ["Game Total", "Straight Up Winner"], key=f"wtype_{i}")

            if wager_cat == "Game Total":
                side = col_b.selectbox("Side", ["Under", "Over"], key=f"lside_{i}")
                strike = col_c.number_input("Line (pts)", value=44.5, step=0.5, key=f"lstrike_{i}")
                leg_prob = calculate_win_prob(strike, 42.0, 7.0, is_under=(side == "Under"))
                leg_desc = f"{d_a} @ {d_h}: {side} {strike}"
            else:
                winner = col_b.selectbox("Pick Winner", [d_h, d_a], key=f"lwinner_{i}")
                strike = None
                h_prob = calculate_moneyline_prob(d_h_pts + 15, d_a_pts + 15, d_h_rec, d_a_rec)
                leg_prob = h_prob if winner == d_h else (1.0 - h_prob)
                leg_desc = f"{d_a} @ {d_h}: {winner} ML"
                col_c.write(f"Estimated Win: **{leg_prob * 100:.1f}%**")

            compound_prob *= leg_prob
            combo_legs.append({"desc": leg_desc, "prob": leg_prob})
            st.markdown("---")

        st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

        with st.form("save_combo_form"):
            c_r1, c_r2, c_r3 = st.columns(3)
            c_risk = c_r1.number_input("Ticket Risk ($)", min_value=1.0, value=10.0, step=5.0)
            c_payout = c_r2.number_input("Total Potential Return ($)", min_value=1.0, value=round(10.0 / max(compound_prob, 0.05), 2), step=10.0)
            c_notes = c_r3.text_input("Notes", f"{legs_count}-Leg Parlay")

            save_c_btn = st.form_submit_button("Lock In Combo Ticket")
            if save_c_btn:
                legs_str = " | ".join([cl["desc"] for cl in combo_legs])
                combo_record = {
                    "id": str(datetime.now().timestamp()),
                    "user": current_user.strip() if current_user.strip() else "Flurk",
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "type": f"{legs_count}-Leg Combo",
                    "bet_category": "Combo",
                    "matchup": legs_str,
                    "bet": f"{legs_count} Legs ({compound_prob * 100:.1f}% Prob)",
                    "target_line": None,
                    "bet_direction": None,
                    "risk_dollars": float(c_risk),
                    "payout_dollars": float(c_payout),
                    "win_prob": f"{compound_prob * 100:.1f}%",
                    "status": "Pending",
                    "notes": c_notes
                }
                st.session_state.saved_bets.insert(0, combo_record)
                save_bets(st.session_state.saved_bets)
                st.success("Combo ticket locked in!")

    # ------------------------------------------
    # PAGE 3: LOCKED BETS & HISTORY
    # ------------------------------------------
    elif menu_choice == "Locked Bets History":
        st.subheader("📜 Locked Bets History & Live Scoreboard")

        b_col1, b_col2 = st.columns([3, 1])
        user_filter = b_col1.selectbox("Filter Bettor", ["All Bettors"] + sorted(list({b.get("user", "Flurk") for b in st.session_state.saved_bets})))

        if b_col2.button("⚡ Auto-Resolve Finals"):
            res_count = 0
            for b in st.session_state.saved_bets:
                if b.get("status") == "Pending":
                    match_game = find_game_for_bet(b, games_data)
                    if match_game and (match_game.get("completed", False) or "final" in match_game["status"].lower()):
                        tot = match_game["away_score"] + match_game["home_score"]
                        b_cat = b.get("bet_category", "Total")
                        if b_cat == "Total" and b.get("target_line") is not None:
                            is_und = (b.get("bet_direction", "Under") == "Under")
                            b["status"] = "Won" if ((tot < b["target_line"]) if is_und else (tot > b["target_line"])) else "Lost"
                            res_count += 1
                        elif b_cat == "Moneyline" and b.get("picked_team"):
                            h_won = match_game["home_score"] > match_game["away_score"]
                            actual_winner = match_game["home_team"] if h_won else match_game["away_team"]
                            b["status"] = "Won" if (b["picked_team"] == actual_winner) else "Lost"
                            res_count += 1
            if res_count > 0:
                save_bets(st.session_state.saved_bets)
                st.success(f"Resolved {res_count} tickets!")
                st.rerun()

        active_tickets = [b for b in st.session_state.saved_bets if user_filter == "All Bettors" or b.get("user", "Flurk") == user_filter]

        if not active_tickets:
            st.info("No recorded tickets found.")
        else:
            for b in active_tickets:
                real_idx = st.session_state.saved_bets.index(b)
                with st.container():
                    r1, r2, r3, r4, r5 = st.columns([2, 3, 2, 2, 1])
                    r1.write(f"**{b.get('user', 'Flurk')}**\n\n`{b['date']}`\n\n{b['type']}")
                    r2.write(f"**{b['matchup']}**\n\nPick: `{b['bet']}`\n\nRisk: **${b.get('risk_dollars', 10.0):.2f}** | Payout: **${b.get('payout_dollars', 19.0):.2f}**")

                    live_m = find_game_for_bet(b, games_data)
                    if live_m:
                        tot_score = live_m['away_score'] + live_m['home_score']
                        r3.write(f"**{live_m['away_short']} {live_m['away_score']} - {live_m['home_score']} {live_m['home_short']}**\n\nTotal: **{tot_score} pts** ({live_m['status']})")
                    else:
                        r3.write("Score: *Final / Inactive*")

                    status_list = ["Pending", "Won", "Lost"]
                    cur_stat_idx = status_list.index(b["status"]) if b["status"] in status_list else 0
                    new_stat = r4.selectbox("Result", status_list, index=cur_stat_idx, key=f"stat_{b['id']}")
                    if new_stat != b["status"]:
                        st.session_state.saved_bets[real_idx]["status"] = new_stat
                        save_bets(st.session_state.saved_bets)
                        st.rerun()

                    if r5.button("🔍 View", key=f"vw_{b['id']}"):
                        st.session_state.selected_bet_id = b["id"]
                        st.rerun()

                    if r5.button("🗑️", key=f"dl_{b['id']}"):
                        st.session_state.saved_bets.pop(real_idx)
                        save_bets(st.session_state.saved_bets)
                        st.rerun()

                    st.markdown("---")

    # ------------------------------------------
    # PAGE 4: SQUAD LEADERBOARD
    # ------------------------------------------
    elif menu_choice == "🏆 Squad Leaderboard":
        st.subheader("🏆 Flurkstradamus Squad Leaderboard")

        user_stats = {}
        for b in st.session_state.saved_bets:
            u = b.get("user", "Flurk")
            if u not in user_stats:
                user_stats[u] = {"Wins": 0, "Losses": 0, "Pending": 0, "Total_Risk": 0.0, "Net_Profit": 0.0}

            risk = b.get("risk_dollars", 10.0)
            payout = b.get("payout_dollars", 19.0)
            stat = b.get("status", "Pending")

            if stat == "Won":
                user_stats[u]["Wins"] += 1
                user_stats[u]["Total_Risk"] += risk
                user_stats[u]["Net_Profit"] += (payout - risk)
            elif stat == "Lost":
                user_stats[u]["Losses"] += 1
                user_stats[u]["Total_Risk"] += risk
                user_stats[u]["Net_Profit"] -= risk
            else:
                user_stats[u]["Pending"] += 1

        board = []
        for u, s in user_stats.items():
            decided = s["Wins"] + s["Losses"]
            win_rate = (s["Wins"] / decided * 100) if decided > 0 else 0.0
            roi = (s["Net_Profit"] / s["Total_Risk"] * 100) if s["Total_Risk"] > 0 else 0.0
            badge = "🎯 Sniper" if win_rate >= 65 and decided >= 3 else ("🔥 On Fire" if s["Wins"] >= 3 and s["Losses"] == 0 else "⚡ Contender")

            board.append({
                "user": f"{u} ({badge})",
                "record": f"{s['Wins']}-{s['Losses']}-{s['Pending']}",
                "win_rate": f"{win_rate:.1f}%",
                "roi": f"{roi:+.1f}%",
                "decided": decided,
                "net_profit": s["Net_Profit"]
            })

        board.sort(key=lambda x: x["net_profit"], reverse=True)

        if not board:
            st.info("No recorded results available yet.")
        else:
            header = "| Rank | Bettor | Record (W-L-P) | Win Rate | ROI % | Decided | Net Profit ($) |\n|---|---|---|---|---|---|---|\n"
            rows = ""
            for i, row in enumerate(board):
                p_val = f"+${row['net_profit']:.2f}" if row['net_profit'] >= 0 else f"-${abs(row['net_profit']):.2f}"
                rows += f"| **#{i+1}** | **{row['user']}** | `{row['record']}` | {row['win_rate']} | {row['roi']} | {row['decided']} | **{p_val}** |\n"
            st.markdown(header + rows)

    # ------------------------------------------
    # PAGE 5: MODEL METHODOLOGY & MATH BREAKDOWN
    # ------------------------------------------
    elif menu_choice == "📖 Model Methodology & Math":
        st.subheader("📖 Flurkstradamus Quantitative Model Architecture")
        st.caption("How every projection, probability percentage, and edge tier is computed.")

        st.markdown("### 1. In-Game Pace & Drift Modeling")
        st.write(
            "Sportsbooks typically project second-half points using simple static percentages (e.g. dividing the total by 2). "
            "Flurkstradamus calculates pace deviation and applies game-script decay across 4 distinct game checkpoints:"
        )

        st.markdown(
            """
            * **Pre-Game Stage:** $Baseline = Pregame\ Total$, with initial standard deviation $\sigma = 8.5$.
            * **After 1st Quarter:** Measures actual scoring versus expected 25% pace:
              $$Pace\ Delta = Points\ Scored - (Pregame \times 0.25)$$
              Adjusts the final projection by 40% of the pace difference ($\sigma = 7.5$).
            * **Halftime:** Analyzes point differential (blowout vs close game) and possession turnover:
              $$Projected\ 2H = (Pregame \times 0.475) + (Pace\ Delta \times 0.30) + Game\ Script\ Modifier$$
              * *Blowout ($\ge 17$ pt margin):* $-3.5$ pts (teams run the clock out).
              * *Decisive ($10-16$ pt margin):* $-1.5$ pts.
              * *Close ($0-3$ pt margin):* $+1.5$ pts (two-minute drills and late clock stops).
            * **After 3rd Quarter:** Locks 75% of actual scoring, projecting only the remaining 22.5% volume with tight variance ($\sigma = 3.5$).
            """
        )

        st.markdown("---")
        st.markdown("### 2. Normal CDF & Win Probability Calculation")
        st.write(
            "Every edge percentage uses a cumulative distribution function (CDF) comparing the target strike line ($L$) against the model's projected total ($\mu$):"
        )
        st.latex(r"Z = \frac{L - \mu}{\sigma}")
        st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right]")
        st.write(
            "For Over bets, $P(\\text{Over}) = 1 - P(\\text{Under})$. As the game progresses and remaining time decreases, "
            "variance ($\sigma$) decays from $8.5$ down to $2.0$, causing probabilities to harden toward 0% or 100%."
        )

        st.markdown("---")
        st.markdown("### 3. Straight-Up Moneyline / Win Expectancy Engine")
        st.write(
            "Moneyline win expectancy combines the live projected scoring margin with regular season win-rate differentials:"
        )
        st.latex(r"\text{Spread}_{\text{eff}} = (\text{Home Projected} - \text{Away Projected}) + \left[(\text{Home Win \%} - \text{Away Win \%}) \times 7.0\right]")
        st.latex(r"P(\text{Home Win}) = \frac{1}{1 + e^{-\frac{\text{Spread}_{\text{eff}}}{6.5}}}")
        st.write(
            "This logistic sigmoid curve translates the effective scoring advantage into a win percentage calibrated for college and professional football outcomes."
        )

        st.markdown("---")
        st.markdown("### 4. Multi-Leg Combo Compound Math")
        st.write(
            "For 2 to 5 leg combo tickets, the overall probability is the product of all independent leg probabilities:"
        )
        st.latex(r"P(\text{Combo}) = \prod_{i=1}^{n} P(\text{Leg}_i) = P(\text{Leg}_1) \times P(\text{Leg}_2) \times \dots \times P(\text{Leg}_n)")

# Launch the live fragment engine
render_main_engine()
