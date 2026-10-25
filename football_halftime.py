import streamlit as st
import requests
import math
import json
import os
import re
from datetime import datetime

st.set_page_config(page_title="Flurkstradamus: Live Edge Engine", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# CONFIGURATION & FRIENDS-ONLY GATEKEEPER
# ==========================================
GROUP_PASSCODE = "FLURK2026"

# Optional Cloud Database Setup (JSONBin.io)
JSONBIN_BIN_ID = "6ade77dbac6210605a51a450"    # Paste your Bin ID here if you have it
JSONBIN_API_KEY = "$2a$10$K8VFT4hzyxMbtkBLLtlaNu/ZB8WthYSFYlKEutPEE4Qg8hi8lA6Ya"   # Paste your Master Key here if you have it

DB_FILE = "bets_history.json"

# --- Database Storage Helpers ---
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
            requests.put(url, json={"bets": bets}, headers=headers, timeout=5)
            return True
        except Exception:
            pass
    return False

def load_bets():
    cloud_data = fetch_cloud_bets()
    if cloud_data is not None:
        return cloud_data
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_bets(bets):
    if not push_cloud_bets(bets):
        with open(DB_FILE, "w") as f:
            json.dump(bets, f, indent=4)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# PIN Screen
if not st.session_state.authenticated:
    st.title("🔮 Flurkstradamus: Private Beta")
    st.write("Welcome to the squad's live football edge terminal. Enter the group passcode to enter.")
    
    with st.form("pin_login"):
        pin_entry = st.text_input("Group Passcode", type="password")
        login_btn = st.form_submit_button("Enter Locker Room")
        if login_btn:
            if pin_entry == GROUP_PASSCODE:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect passcode. Ask the commissioner for access.")
    st.stop()

# Load bet database
if "saved_bets" not in st.session_state:
    st.session_state.saved_bets = load_bets()

# --- Probability Helper ---
def calculate_win_prob(target_line, projected_total, std_dev=7.0, is_under=True):
    std_dev = max(std_dev, 0.75)
    z = (target_line - projected_total) / std_dev
    under_prob = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return under_prob if is_under else (1.0 - under_prob)

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
            status_obj = comp["status"]
            games.append({
                "id": str(event.get("id", "")),
                "name": event["name"],
                "home_team": home["team"]["displayName"],
                "home_short": home["team"].get("shortDisplayName", home["team"]["displayName"]),
                "away_team": away["team"]["displayName"],
                "away_short": away["team"].get("shortDisplayName", away["team"]["displayName"]),
                "home_score": int(home.get("score", 0)),
                "away_score": int(away.get("score", 0)),
                "status": status_obj["type"]["shortDetail"],
                "completed": status_obj["type"].get("completed", False),
                "period": status_obj.get("period", 2),
                "displayClock": status_obj.get("displayClock", "0:00")
            })
        return games
    except Exception:
        return []

# --- Sidebar ---
st.sidebar.title("🔮 Flurkstradamus")
current_user = st.sidebar.text_input("Your Bettor Handle", value="Flurk")
league = st.sidebar.radio("Select League", ["NFL", "College Football (NCAA)"])
league_param = "nfl" if league == "NFL" else "college-football"
games_data = get_live_games(league_param)

if st.sidebar.button("🔄 Sync Cloud Bets"):
    st.session_state.saved_bets = load_bets()
    st.sidebar.success("Synced!")

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

st.title("🔮 Flurkstradamus: Live Football Edge Engine")

tab_single, tab_combo, tab_history, tab_board = st.tabs([
    "Single Game Engine", 
    "Combo Ticket Builder", 
    "Locked Bets History", 
    "🏆 Friends Leaderboard"
])

# ==========================================
# TAB 1: SINGLE GAME ENGINE
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
        pregame_total = st.number_input("Pre-Game Baseline Total", value=47.5, step=0.5, key=f"pre_{g_id}")

    with col2:
        st.subheader("2. Live Situation")
        sc1, sc2 = st.columns(2)
        with sc1:
            h1_home = st.number_input(f"{home_team} Points", min_value=0, value=g["home_score"], key=f"hpts_{g_id}")
        with sc2:
            h1_away = st.number_input(f"{away_team} Points", min_value=0, value=g["away_score"], key=f"apts_{g_id}")
        
        live_book_line = st.number_input("Market Total Offered (pts)", value=round(pregame_total) + 0.5, step=0.5, key=f"rh_{g_id}")

    h1_total = h1_home + h1_away
    margin = abs(h1_home - h1_away)
    base_2h = pregame_total * 0.475
    pace_diff = h1_total - (pregame_total * 0.525)
    pace_modifier = pace_diff * 0.30
    script_mod = -3.5 if margin >= 17 else (-1.5 if margin >= 10 else (1.5 if margin <= 3 else 0.0))
    proj_2h = base_2h + pace_modifier + script_mod + 0.5
    final_proj = h1_total + proj_2h
    shift = final_proj - pregame_total

    st.markdown("---")
    st.subheader("3. Flurkstradamus Projected Totals")
    m1, m2, m3 = st.columns(3)
    m1.metric("Pre-Game Baseline", f"{pregame_total:.1f} pts")
    m2.metric("Projected Final Score", f"{final_proj:.1f} pts", delta=f"{shift:+.1f} shift")
    m3.metric("Live Market Line", f"{live_book_line:.1f} pts")

    st.markdown("---")
    st.subheader("4. Target Tiers (Good, Better, Best)")

    line_good = round(final_proj + 9.5) + 0.5
    line_better = round(final_proj + 5.5) + 0.5
    line_best = round(final_proj + 2.5) + 0.5

    prob_good = calculate_win_prob(line_good, final_proj, 7.0, is_under=True)
    prob_better = calculate_win_prob(line_better, final_proj, 7.0, is_under=True)
    prob_best = calculate_win_prob(line_best, final_proj, 7.0, is_under=True)

    c_good, c_better, c_best = st.columns(3)
    with c_good:
        st.success("🟢 **GOOD (Floor Play)**")
        st.write(f"**Line:** Under {line_good}")
        st.write(f"**Safety Margin:** +{line_good - final_proj:.1f} pts")
        st.write(f"**Model Probability:** {prob_good * 100:.1f}%")

    with c_better:
        st.info("🟡 **BETTER (Balanced Edge)**")
        st.write(f"**Line:** Under {line_better}")
        st.write(f"**Safety Margin:** +{line_better - final_proj:.1f} pts")
        st.write(f"**Model Probability:** {prob_better * 100:.1f}%")

    with c_best:
        st.warning("🔥 **BEST (Maximum Value)**")
        st.write(f"**Line:** Under {line_best}")
        st.write(f"**Safety Margin:** +{line_best - final_proj:.1f} pts")
        st.write(f"**Model Probability:** {prob_best * 100:.1f}%")

    st.markdown("---")
    st.subheader(f"🔒 Lock In Bet as {current_user}")

    with st.form("save_actual_bet_form"):
        f1, f2, f3 = st.columns(3)
        with f1:
            bet_direction = st.selectbox("Direction", ["Under", "Over"])
        with f2:
            actual_line = st.number_input("Line Taken (pts)", value=40.0, step=0.5)
        with f3:
            contract_price = st.number_input("Contract Cost (¢)", min_value=1, max_value=99, value=52, step=1)
        
        user_notes = st.text_input("Notes (e.g. Robinhood event contract)")
        lock_btn = st.form_submit_button("Lock In Bet")

        if lock_btn:
            is_under = (bet_direction == "Under")
            calc_prob = calculate_win_prob(actual_line, final_proj, 7.0, is_under=is_under)
            new_bet = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip() if current_user.strip() else "Anonymous",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": "Single",
                "home_team": home_team,
                "away_team": away_team,
                "matchup": f"{away_team} @ {home_team}",
                "bet": f"{bet_direction} {actual_line} (@ {contract_price}¢)",
                "target_line": float(actual_line),
                "bet_direction": bet_direction,
                "cost_cents": int(contract_price),
                "pregame_proj": round(pregame_total, 1),
                "halftime_proj": round(final_proj, 1),
                "proj_shift": f"{shift:+.1f}",
                "original_win_prob": f"{calc_prob * 100:.1f}%",
                "status": "Pending",
                "notes": user_notes
            }
            st.session_state.saved_bets.insert(0, new_bet)
            save_bets(st.session_state.saved_bets)
            st.success(f"Bet saved to {current_user}'s ticket history!")

# ==========================================
# TAB 2: COMBO TICKET BUILDER
# ==========================================
with tab_combo:
    st.subheader("🔗 Multi-Leg Combo Builder (3 to 5 Legs)")
    legs_count = st.radio("Number of Legs", [3, 4, 5], horizontal=True)
    combo_legs_data = []
    compound_prob = 1.0

    game_choices = [f"{g['away_team']} @ {g['home_team']} ({g['status']})" for g in games_data] if games_data else ["Manual Matchup"]

    for i in range(legs_count):
        st.markdown(f"### Leg {i+1}")
        def_idx = min(i, len(game_choices) - 1)
        selected_leg_idx = st.selectbox(f"Select Matchup for Leg {i+1}", range(len(game_choices)), index=def_idx, format_func=lambda x: game_choices[x], key=f"cb_picker_{i}")
        
        if games_data:
            leg_g = games_data[selected_leg_idx]
            leg_gid = leg_g.get("id", str(selected_leg_idx))
            def_home = leg_g["home_team"]
            def_away = leg_g["away_team"]
            def_home_score = leg_g["home_score"]
            def_away_score = leg_g["away_score"]
        else:
            leg_gid = f"man_{i}"
            def_home = f"Home {i+1}"
            def_away = f"Away {i+1}"
            def_home_score = 14
            def_away_score = 10

        l_key = f"leg_{i}_{leg_gid}"

        c_sub1, c_sub2, c_sub3, c_sub4 = st.columns(4)
        with c_sub1:
            pre_tot = st.number_input(f"Pre-Game Total", value=47.5, step=0.5, key=f"c_pre_{l_key}")
        with c_sub2:
            h_pts = st.number_input(f"{def_home} Pts", min_value=0, value=def_home_score, key=f"c_hpts_{l_key}")
        with c_sub3:
            a_pts = st.number_input(f"{def_away} Pts", min_value=0, value=def_away_score, key=f"c_apts_{l_key}")
        with c_sub4:
            leg_h1 = h_pts + a_pts
            leg_margin = abs(h_pts - a_pts)
            leg_pace_diff = leg_h1 - (pre_tot * 0.525)
            leg_script = -3.5 if leg_margin >= 17 else (-1.5 if leg_margin >= 10 else (1.5 if leg_margin <= 3 else 0.0))
            leg_final_proj = leg_h1 + (pre_tot * 0.475) + (leg_pace_diff * 0.30) + leg_script + 0.5
            st.metric("Projected Total", f"{leg_final_proj:.1f} pts")

        b_col1, b_col2, b_col3, b_col4 = st.columns(4)
        with b_col1:
            leg_side = st.selectbox(f"Side", ["Under", "Over"], key=f"c_side_{l_key}")
        with b_col2:
            default_strike = float(round(leg_final_proj + 3.0) if leg_side == "Under" else round(leg_final_proj - 3.0))
            leg_target_line = st.number_input(f"Strike Line", value=default_strike, step=0.5, key=f"c_line_{l_key}")
        with b_col3:
            leg_cost = st.number_input(f"Cost (¢)", min_value=1, max_value=99, value=52, step=1, key=f"c_cost_{l_key}")
        with b_col4:
            leg_prob = calculate_win_prob(leg_target_line, leg_final_proj, 7.0, is_under=(leg_side == "Under"))
            st.metric("Leg Probability", f"{leg_prob * 100:.1f}%")

        compound_prob *= leg_prob
        combo_legs_data.append({
            "matchup": f"{def_away} @ {def_home}",
            "home_team": def_home,
            "away_team": def_away,
            "side": leg_side,
            "line": leg_target_line,
            "cost": leg_cost,
            "prob": leg_prob
        })
        st.markdown("---")

    st.metric("Compound Ticket Probability", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_ticket_form"):
        combo_ticket_notes = st.text_input("Combo Notes")
        lock_combo_btn = st.form_submit_button(f"Lock In Ticket as {current_user}")
        if lock_combo_btn:
            legs_display = " | ".join([f"{l['matchup']}: {l['side']} {l['line']}" for l in combo_legs_data])
            combo_record = {
                "id": str(datetime.now().timestamp()),
                "user": current_user.strip() if current_user.strip() else "Anonymous",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "type": f"{legs_count}-Leg Combo",
                "matchup": legs_display,
                "bet": f"{legs_count} Legs ({compound_prob * 100:.1f}% Prob)",
                "target_line": None,
                "bet_direction": None,
                "cost_cents": 50,
                "pregame_proj": "Multi",
                "halftime_proj": f"{compound_prob * 100:.1f}% Prob",
                "proj_shift": "N/A",
                "original_win_prob": f"{compound_prob * 100:.1f}%",
                "status": "Pending",
                "notes": combo_ticket_notes
            }
            st.session_state.saved_bets.insert(0, combo_record)
            save_bets(st.session_state.saved_bets)
            st.success("Ticket saved!")

# ==========================================
# TAB 3: BET HISTORY & LIVE GAME MONITOR
# ==========================================
with tab_history:
    st.subheader("📜 Live Bet Tracker & History")

    top_c1, top_c2 = st.columns([3, 1])
    with top_c1:
        bettor_options = ["All Bettors"] + sorted(list({b.get("user", "Flurk") for b in st.session_state.saved_bets}))
        user_filter = st.selectbox("Filter Bets by User", bettor_options)
    with top_c2:
        if st.button("⚡ Auto-Resolve Final Games"):
            resolved_count = 0
            for b in st.session_state.saved_bets:
                if b["status"] == "Pending" and b.get("target_line") is not None:
                    matched = find_game_for_bet(b, games_data)
                    if matched and (matched.get("completed", False) or "final" in matched["status"].lower()):
                        tot = matched["away_score"] + matched["home_score"]
                        t_line = b["target_line"]
                        is_und = (b.get("bet_direction", "Under") == "Under")
                        b["status"] = "Won" if ((tot < t_line) if is_und else (tot > t_line)) else "Lost"
                        resolved_count += 1
            if resolved_count > 0:
                save_bets(st.session_state.saved_bets)
                st.success(f"Resolved {resolved_count} completed bets!")
                st.rerun()
            else:
                st.info("No completed pending bets found.")

    filtered_bets = [b for b in st.session_state.saved_bets if user_filter == "All Bettors" or b.get("user", "Flurk") == user_filter]

    if not filtered_bets:
        st.info("No bets recorded for this filter.")
    else:
        for idx, bet in enumerate(filtered_bets):
            real_idx = st.session_state.saved_bets.index(bet)
            with st.container():
                h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([1.8, 2.5, 2.5, 2.5, 1.5, 0.7])
                
                with h_col1:
                    st.write(f"**{bet.get('user', 'Flurk')}**")
                    st.caption(f"{bet['date']} | {bet['type']}")
                
                with h_col2:
                    st.write(f"**{bet['matchup']}**")
                    st.write(f"Pick: `{bet['bet']}`")
                    if bet.get("notes"):
                        st.caption(f"Notes: {bet['notes']}")

                target_line = bet.get("target_line")
                bet_dir = bet.get("bet_direction", "Under")
                if target_line is None:
                    match_num = re.search(r"(\d+(\.\d+)?)", bet.get("bet", ""))
                    if match_num:
                        target_line = float(match_num.group(1))
                    if "over" in bet.get("bet", "").lower():
                        bet_dir = "Over"

                is_under_bet = (bet_dir == "Under")
                live_game_info = find_game_for_bet(bet, games_data)

                with h_col3:
                    if live_game_info:
                        curr_away = live_game_info["away_score"]
                        curr_home = live_game_info["home_score"]
                        total_pts = curr_away + curr_home
                        status_str = live_game_info["status"]
                        
                        st.write(f"**{live_game_info['away_short']} {curr_away} - {curr_home} {live_game_info['home_short']}**")
                        st.write(f"Total: **{total_pts} pts** ({status_str})")
                        
                        if target_line is not None:
                            cushion = target_line - total_pts if is_under_bet else total_pts - target_line
                            if is_under_bet:
                                st.caption(f"🛡️ Cushion: **{cushion:.1f} pts**" if cushion > 0 else f"💥 Busted by **{abs(cushion):.1f} pts**")
                            else:
                                st.caption(f"🎉 Cleared by **{cushion:.1f} pts**" if cushion >= 0 else f"🎯 Needs **{abs(cushion):.1f} pts**")
                    else:
                        st.write("Score: *Final / Inactive*")

                with h_col4:
                    if live_game_info and target_line is not None:
                        curr_total = live_game_info["away_score"] + live_game_info["home_score"]
                        is_final = live_game_info.get("completed", False) or "final" in live_game_info["status"].lower()
                        
                        if is_final:
                            won = (curr_total < target_line) if is_under_bet else (curr_total > target_line)
                            st.success("🏆 **WON - Covered**") if won else st.error("❌ **LOST - Busted**")
                        else:
                            period = live_game_info.get("period", 2)
                            decay_sigma = 7.0 if period <= 2 else (4.8 if period == 3 else 2.4)
                            frac_rem = 0.5 if period <= 2 else (0.25 if period == 3 else 0.08)
                            
                            halftime_pts = bet.get("halftime_proj", curr_total + 10.0)
                            if isinstance(halftime_pts, str):
                                try:
                                    halftime_pts = float(halftime_pts.replace(" pts", ""))
                                except:
                                    halftime_pts = curr_total + 10.0

                            in_game_projected = curr_total + ((halftime_pts - curr_total) * frac_rem) if halftime_pts > curr_total else curr_total + 3.0
                            current_prob = calculate_win_prob(target_line, in_game_projected, std_dev=decay_sigma, is_under=is_under_bet)
                            prob_pct = current_prob * 100
                            
                            st.write(f"In-Game Prob: **{prob_pct:.1f}%**")
                            cost = bet.get("cost_cents", 50)
                            if prob_pct > 80 and cost < 70:
                                st.caption("💡 *High Win Equity: Hold or cash out profit*")
                            elif prob_pct < 25:
                                st.caption("⚠️ *High Danger: Consider cutting early*")
                    else:
                        st.write(f"Baseline: **{bet['pregame_proj']}**")
                        st.write(f"Halftime: **{bet['halftime_proj']}**")

                with h_col5:
                    status_options = ["Pending", "Won", "Lost"]
                    current_idx = status_options.index(bet["status"]) if bet["status"] in status_options else 0
                    new_status = st.selectbox("Result", status_options, index=current_idx, key=f"status_{bet['id']}")
                    if new_status != bet["status"]:
                        st.session_state.saved_bets[real_idx]["status"] = new_status
                        save_bets(st.session_state.saved_bets)
                        st.rerun()

                with h_col6:
                    if st.button("🗑️", key=f"del_{bet['id']}"):
                        st.session_state.saved_bets.pop(real_idx)
                        save_bets(st.session_state.saved_bets)
                        st.rerun()

                st.markdown("---")

# ==========================================
# TAB 4: COMMUNITY LEADERBOARD
# ==========================================
with tab_board:
    st.subheader("🏆 Flurkstradamus Squad Leaderboard")
    
    users_stats = {}
    for bet in st.session_state.saved_bets:
        u = bet.get("user", "Flurk")
        if u not in users_stats:
            users_stats[u] = {"Wins": 0, "Losses": 0, "Pending": 0, "Total": 0, "Net_Profit_Cents": 0, "Total_Risked_Cents": 0}
        
        status = bet.get("status", "Pending")
        cost = bet.get("cost_cents", 50)
        users_stats[u]["Total"] += 1
        
        if status in ["Won", "Lost"]:
            users_stats[u]["Total_Risked_Cents"] += cost
        
        if status == "Won":
            users_stats[u]["Wins"] += 1
            users_stats[u]["Net_Profit_Cents"] += (100 - cost)
        elif status == "Lost":
            users_stats[u]["Losses"] += 1
            users_stats[u]["Net_Profit_Cents"] -= cost
        else:
            users_stats[u]["Pending"] += 1

    board_rows = []
    for u, s in users_stats.items():
        decided = s["Wins"] + s["Losses"]
        win_rate = (s["Wins"] / decided * 100) if decided > 0 else 0.0
        profit_dollars = s["Net_Profit_Cents"] / 100.0
        roi = (s["Net_Profit_Cents"] / s["Total_Risked_Cents"] * 100) if s["Total_Risked_Cents"] > 0 else 0.0
        
        badge = "🎯 Sniper" if win_rate >= 65 and decided >= 3 else ("🔥 On Fire" if s["Wins"] >= 3 and s["Losses"] == 0 else ("🥶 Cold" if s["Losses"] >= 3 and win_rate < 35 else "⚡ Contender"))

        board_rows.append({
            "user": f"{u} ({badge})",
            "record": f"{s['Wins']}-{s['Losses']}-{s['Pending']}",
            "win_rate": f"{win_rate:.1f}%",
            "roi": f"{roi:+.1f}%",
            "decided": decided,
            "profit": profit_dollars
        })

    board_rows.sort(key=lambda x: x["profit"], reverse=True)
    
    if not board_rows:
        st.info("No recorded bets yet to calculate leaderboard standings.")
    else:
        header = "| Rank | Bettor | Record (W-L-P) | Win Rate | ROI | Decided | Est. Profit/Loss |\n|---|---|---|---|---|---|---|\n"
        rows_str = ""
        for i, row in enumerate(board_rows):
            p_str = f"+${row['profit']:.2f}" if row['profit'] >= 0 else f"-${abs(row['profit']):.2f}"
            rows_str += f"| **#{i+1}** | **{row['user']}** | `{row['record']}` | {row['win_rate']} | {row['roi']} | {row['decided']} | **{p_str}** |\n"
        
        st.markdown(header + rows_str)
