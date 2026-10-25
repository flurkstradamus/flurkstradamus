import streamlit as st
import requests
import math
import json
import os
from datetime import datetime

st.set_page_config(page_title="Robinhood Halftime Betting & Bet Tracker", layout="wide")

st.title("🏈 Robinhood Football Halftime Edge & Tracker")

DB_FILE = "bets_history.json"

# --- Database Storage Helpers ---
def load_bets():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_bets(bets):
    with open(DB_FILE, "w") as f:
        json.dump(bets, f, indent=4)

if "saved_bets" not in st.session_state:
    st.session_state.saved_bets = load_bets()

# --- Probability Helper ---
def under_win_prob(target_line, projected_total, std_dev=7.0):
    z = (target_line - projected_total) / std_dev
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

# --- ESPN Live Data ---
@st.cache_data(ttl=15)
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
            games.append({
                "id": event.get("id", ""),
                "name": event["name"],
                "home_team": home["team"]["displayName"],
                "away_team": away["team"]["displayName"],
                "home_score": int(home.get("score", 0)),
                "away_score": int(away.get("score", 0)),
                "status": comp["status"]["type"]["shortDetail"],
            })
        return games
    except Exception:
        return []

tab_single, tab_combo, tab_history = st.tabs(["Single Game & Suggestions", "3-5 Leg Combo Builder", "Locked Bets & History"])

league = st.sidebar.radio("Select League", ["NFL", "College Football (NCAA)"])
league_param = "nfl" if league == "NFL" else "college-football"
games_data = get_live_games(league_param)

# ==========================================
# TAB 1: SINGLE GAME & LOCK IN CUSTOM BET
# ==========================================
with tab_single:
    if games_data:
        game_options = [f"{g['away_team']} @ {g['home_team']} ({g['status']})" for g in games_data]
        selected_idx = st.selectbox("Select Active Matchup", range(len(game_options)), format_func=lambda x: game_options[x])
        g = games_data[selected_idx]
        g_id = g.get("id", str(selected_idx))
    else:
        st.warning("Could not fetch ESPN games. Using manual inputs.")
        g = {"id": "man", "home_team": "Home", "away_team": "Away", "home_score": 14, "away_score": 10, "status": "Halftime"}
        g_id = "man"

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Initial Baseline (Pre-Game)")
        home_team = st.text_input("Home Team", value=g["home_team"], key=f"h_{g_id}")
        away_team = st.text_input("Away Team", value=g["away_team"], key=f"a_{g_id}")
        pregame_total = st.number_input("Pre-Game Total (Full)", value=47.5, step=0.5, key=f"pre_{g_id}")
        initial_projected_final = pregame_total

    with col2:
        st.subheader("2. Halftime Reality")
        sc1, sc2 = st.columns(2)
        with sc1:
            h1_home = st.number_input(f"{home_team} 1H Pts", min_value=0, value=g["home_score"], key=f"hpts_{g_id}")
        with sc2:
            h1_away = st.number_input(f"{away_team} 1H Pts", min_value=0, value=g["away_score"], key=f"apts_{g_id}")
        
        live_book_line = st.number_input("Current Live Total on Robinhood (pts)", value=round(pregame_total) + 0.5, step=0.5, key=f"rh_{g_id}")

    # Halftime Projection Calculation
    h1_total = h1_home + h1_away
    margin = abs(h1_home - h1_away)
    base_2h = pregame_total * 0.475
    pace_diff = h1_total - (pregame_total * 0.525)
    pace_modifier = pace_diff * 0.30
    
    script_mod = -3.5 if margin >= 17 else (-1.5 if margin >= 10 else (1.5 if margin <= 3 else 0.0))
    proj_2h = base_2h + pace_modifier + script_mod + 0.5
    final_proj = h1_total + proj_2h
    shift = final_proj - initial_projected_final

    st.markdown("---")
    st.subheader("3. Projection Drift")
    m1, m2, m3 = st.columns(3)
    m1.metric("Pre-Game Projection", f"{initial_projected_final:.1f} pts")
    m2.metric("Halftime Revised Projection", f"{final_proj:.1f} pts", delta=f"{shift:+.1f} shift")
    m3.metric("Live Market Baseline", f"{live_book_line:.1f} pts")

    st.markdown("---")
    st.subheader("4. Suggested Under Options (Good, Better, Best)")

    line_good = round(final_proj + 9.5) + 0.5
    line_better = round(final_proj + 5.5) + 0.5
    line_best = round(final_proj + 2.5) + 0.5

    prob_good = under_win_prob(line_good, final_proj)
    prob_better = under_win_prob(line_better, final_proj)
    prob_best = under_win_prob(line_best, final_proj)

    c_good, c_better, c_best = st.columns(3)
    with c_good:
        st.success("🟢 **GOOD: Safest Floor**")
        st.write(f"**Line:** Under {line_good}")
        st.write(f"**Safety Cushion:** +{line_good - final_proj:.1f} pts")
        st.write(f"**Win Probability:** {prob_good * 100:.1f}%")

    with c_better:
        st.info("🟡 **BETTER: Balanced Value**")
        st.write(f"**Line:** Under {line_better}")
        st.write(f"**Safety Cushion:** +{line_better - final_proj:.1f} pts")
        st.write(f"**Win Probability:** {prob_better * 100:.1f}%")

    with c_best:
        st.warning("🔥 **BEST: Maximum Edge**")
        st.write(f"**Line:** Under {line_best}")
        st.write(f"**Safety Cushion:** +{line_best - final_proj:.1f} pts")
        st.write(f"**Win Probability:** {prob_best * 100:.1f}%")

    st.markdown("---")
    st.subheader("🔒 Lock In Your Actual Bet")

    # This form allows you to type your exact number (like 40 or 40.5)
    with st.form("save_actual_bet_form"):
        f1, f2, f3 = st.columns(3)
        with f1:
            bet_direction = st.selectbox("Side", ["Under", "Over"])
        with f2:
            actual_line = st.number_input("Line You Actually Bet (Type any number)", value=40.0, step=0.5)
        with f3:
            contract_price = st.number_input("Robinhood Share Price (¢)", min_value=1, max_value=99, value=52, step=1)
        
        user_notes = st.text_input("Notes (e.g., Denver under 40 contract)")
        lock_btn = st.form_submit_button("Lock In Bet to History")

        if lock_btn:
            calc_prob = under_win_prob(actual_line, final_proj) if bet_direction == "Under" else (1.0 - under_win_prob(actual_line, final_proj))
            new_bet = {
                "id": str(datetime.now().timestamp()),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": "Single",
                "matchup": f"{away_team} @ {home_team}",
                "bet": f"{bet_direction} {actual_line} (@ {contract_price}¢)",
                "pregame_proj": round(initial_projected_final, 1),
                "halftime_proj": round(final_proj, 1),
                "proj_shift": f"{shift:+.1f}",
                "win_prob": f"{calc_prob * 100:.1f}%",
                "status": "Pending",
                "notes": user_notes
            }
            st.session_state.saved_bets.insert(0, new_bet)
            save_bets(st.session_state.saved_bets)
            st.success(f"Locked in: {bet_direction} {actual_line} at {contract_price}¢!")

# ==========================================
# TAB 2: 3, 4, OR 5 LEG COMBO BUILDER
# ==========================================
with tab_combo:
    st.subheader("🔗 Multi-Leg Combo Builder (3 to 5 Legs)")
    st.write("Pick 3, 4, or 5 game legs to calculate compound win probability and log full tickets.")

    legs_count = st.radio("Number of Legs in Combo", [3, 4, 5], horizontal=True)
    combo_legs = []
    compound_prob = 1.0

    for i in range(legs_count):
        st.markdown(f"**Leg {i+1}**")
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            leg_name = st.text_input(f"Matchup {i+1}", f"Game {i+1}", key=f"leg_matchup_{i}")
        with col_b:
            leg_dir = st.selectbox(f"Side {i+1}", ["Under", "Over"], key=f"leg_dir_{i}")
        with col_c:
            leg_proj = st.number_input(f"Projected Score {i+1}", value=35.0, step=0.5, key=f"leg_proj_{i}")
        with col_d:
            leg_line = st.number_input(f"Target Line {i+1}", value=40.0, step=0.5, key=f"leg_line_{i}")
        
        prob = under_win_prob(leg_line, leg_proj) if leg_dir == "Under" else (1.0 - under_win_prob(leg_line, leg_proj))
        compound_prob *= prob
        combo_legs.append({"matchup": leg_name, "pick": f"{leg_dir} {leg_line}", "prob": f"{prob*100:.1f}%"})

    st.markdown("---")
    st.metric("Compound Ticket Win Probability", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        combo_notes = st.text_input("Combo Notes (e.g., Robinhood 4-leg event ticket)")
        save_combo = st.form_submit_button("Lock In Combo Ticket")
        if save_combo:
            combo_record = {
                "id": str(datetime.now().timestamp()),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": f"{legs_count}-Leg Combo",
                "matchup": " | ".join([f"{l['matchup']}: {l['pick']}" for l in combo_legs]),
                "bet": f"{legs_count} Legs",
                "pregame_proj": "N/A",
                "halftime_proj": f"{compound_prob * 100:.1f}% Prob",
                "proj_shift": "N/A",
                "status": "Pending",
                "notes": combo_notes
            }
            st.session_state.saved_bets.insert(0, combo_record)
            save_bets(st.session_state.saved_bets)
            st.success("Combo ticket saved to history!")

# ==========================================
# TAB 3: BET HISTORY & DELETION
# ==========================================
with tab_history:
    st.subheader("📜 Locked Bets History & Review")
    
    if not st.session_state.saved_bets:
        st.info("No bets have been recorded yet.")
    else:
        for idx, bet in enumerate(list(st.session_state.saved_bets)):
            with st.container():
                h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([2, 3, 2, 2, 1])
                
                with h_col1:
                    st.write(f"**{bet['date']}**")
                    st.caption(f"Type: {bet['type']}")
                
                with h_col2:
                    st.write(f"**{bet['matchup']}**")
                    st.write(f"Pick: `{bet['bet']}`")
                    if bet.get("notes"):
                        st.caption(f"Notes: {bet['notes']}")
                
                with h_col3:
                    st.write(f"Pre-Game: **{bet['pregame_proj']}**")
                    st.write(f"Halftime: **{bet['halftime_proj']}**")
                    if bet['proj_shift'] != "N/A":
                        st.caption(f"Shift: {bet['proj_shift']} pts")
                
                with h_col4:
                    status_options = ["Pending", "Won", "Lost"]
                    current_idx = status_options.index(bet["status"]) if bet["status"] in status_options else 0
                    new_status = st.selectbox("Status", status_options, index=current_idx, key=f"status_{bet['id']}")
                    if new_status != bet["status"]:
                        st.session_state.saved_bets[idx]["status"] = new_status
                        save_bets(st.session_state.saved_bets)
                        st.rerun()

                with h_col5:
                    if st.button("🗑️ Delete", key=f"del_{bet['id']}"):
                        st.session_state.saved_bets.pop(idx)
                        save_bets(st.session_state.saved_bets)
                        st.rerun()

                st.markdown("---")