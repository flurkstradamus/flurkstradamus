import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster, get_live_nba_3pm_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def generate_same_game_combo(target_gm, num_legs, chosen_market, strat_choice):
    if not target_gm:
        return []

    effective_legs = max(2, int(num_legs))
    is_nba = (target_gm.get("league") == "NBA")

    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice
    is_balanced = "Balanced" in strat_choice

    is_totals_only = "Totals" in chosen_market
    is_spreads_only = "Spreads" in chosen_market
    is_ml_only = "Straight Up" in chosen_market or "Moneyline" in chosen_market
    is_points_prop = "Player Points" in chosen_market
    is_3pm_prop = ("Three-Pointers" in chosen_market or "3-Pointers" in chosen_market) and is_nba
    is_td_prop = "Touchdown" in chosen_market

    ou_open = round_half_point(target_gm.get("market_ou", 224.5 if is_nba else 47.5))
    spread_open = round_half_point(target_gm.get("market_spread", -3.5))

    fav_team = target_gm["home_team"] if spread_open < 0 else target_gm["away_team"]
    dog_team = target_gm["away_team"] if spread_open < 0 else target_gm["home_team"]
    fav_spread = spread_open if fav_team == target_gm["home_team"] else -spread_open

    m_str = f"{target_gm.get('away_short')} @ {target_gm.get('home_short')}"
    g_id = target_gm.get("id")

    # 1. THREE-POINTERS EXCLUSIVE (Active Players Only)
    if is_3pm_prop and is_nba:
        h_roster = get_live_nba_3pm_roster(target_gm.get("home_id"), game_id=g_id)
        a_roster = get_live_nba_3pm_roster(target_gm.get("away_id"), game_id=g_id)

        combined_players = []
        max_len = max(len(h_roster), len(a_roster))
        for i in range(max_len):
            if i < len(h_roster): combined_players.append(h_roster[i][0])
            if i < len(a_roster): combined_players.append(a_roster[i][0])

        three_legs = []
        for idx, p_name in enumerate(combined_players):
            if is_safe:
                m_label = "1+ Three-Pointers" if idx % 2 == 0 else "2+ Three-Pointers"
                line_val = 0.5 if "1+" in m_label else 1.5
                prob_val = 0.86 if "1+" in m_label else 0.72
            elif is_high_profit:
                m_label = "3+ Three-Pointers" if idx % 2 == 0 else "2+ Three-Pointers"
                line_val = 2.5 if "3+" in m_label else 1.5
                prob_val = 0.49 if "3+" in m_label else 0.65
            else:
                m_label = "2+ Three-Pointers"
                line_val = 1.5
                prob_val = 0.68

            three_legs.append({
                "game": target_gm,
                "type": "NBA Player 3-Pointers Made",
                "side": "Over",
                "line": line_val,
                "picked_team": p_name,
                "desc": f"{p_name} {m_label}",
                "prob": prob_val,
                "matchup": m_str
            })

            if len(three_legs) == effective_legs:
                break

        return three_legs

    # 2. POINTS PROPS
    if is_points_prop and is_nba:
        h_roster = get_live_nba_roster(target_gm.get("home_id"), game_id=g_id)
        a_roster = get_live_nba_roster(target_gm.get("away_id"), game_id=g_id)
        combined_players = h_roster + a_roster

        prop_legs = []
        for p_info in combined_players:
            p_name = p_info[0]
            p_line = 18.5 if is_safe else 22.5
            p_prob = 0.72 if is_safe else 0.58

            prop_legs.append({
                "game": target_gm,
                "type": "Player Points Prop",
                "side": "Over",
                "line": p_line,
                "picked_team": p_name,
                "desc": f"{p_name} Over {p_line:.1f} Pts",
                "prob": p_prob,
                "matchup": m_str
            })

            if len(prop_legs) == effective_legs:
                break
        return prop_legs

    # 3. TOUCHDOWNS (Football)
    if is_td_prop and not is_nba:
        f_roster = get_live_football_roster(target_gm.get("home_id") or target_gm.get("home_short"), target_gm.get("league"))
        td_legs = []
        for p in f_roster[:effective_legs]:
            td_legs.append({
                "game": target_gm,
                "type": "Football Anytime Touchdown Scorer",
                "side": "TD",
                "line": 1.0,
                "picked_team": p[0],
                "desc": f"{p[0]} Any Time TD",
                "prob": 0.52,
                "matchup": m_str
            })
        return td_legs

    # 4. GAME TOTALS
    if is_totals_only:
        tot_legs = []
        steps = [6.5, 4.5, 2.5, 0.5, -1.5, -3.5]
        for step in steps[:effective_legs]:
            c_line = round_half_point(ou_open + (step if is_safe else -step))
            c_side = "Under" if is_safe or "Mixed" in strat_choice else "Over"
            tot_legs.append({
                "game": target_gm,
                "type": "Game Total",
                "side": c_side,
                "line": c_line,
                "picked_team": target_gm["home_team"],
                "desc": f"{c_side} {c_line:.1f}",
                "prob": 0.70 if is_safe else 0.56,
                "matchup": m_str
            })
        return tot_legs

    # 5. POINT SPREADS
    if is_spreads_only:
        spd_legs = []
        margins = [abs(fav_spread) + 4.5, abs(fav_spread) + 2.5, abs(fav_spread)]
        for m_val in margins[:effective_legs]:
            s_line = round_half_point(m_val)
            s_team = dog_team if is_safe else fav_team
            spd_legs.append({
                "game": target_gm,
                "type": "Point Spread (ATS)",
                "side": "Spread",
                "line": s_line,
                "picked_team": s_team,
                "desc": f"{s_team} {s_line:+.1f}",
                "prob": 0.70 if is_safe else 0.54,
                "matchup": m_str
            })
        return spd_legs

    # 6. SYSTEM DEFAULT MIX
    candidates = [
        {"game": target_gm, "type": "Game Total", "side": "Under", "line": round_half_point(ou_open + 6.5), "picked_team": target_gm["home_team"], "desc": f"Under {round_half_point(ou_open + 6.5):.1f}", "prob": 0.75, "matchup": m_str},
        {"game": target_gm, "type": "Point Spread (ATS)", "side": "Spread", "line": fav_spread, "picked_team": fav_team, "desc": f"{fav_team} {fav_spread:+.1f}", "prob": 0.68, "matchup": m_str},
        {"game": target_gm, "type": "Straight Up Winner (Moneyline)", "side": "Moneyline", "line": None, "picked_team": fav_team, "desc": f"{fav_team} ML", "prob": 0.70, "matchup": m_str}
    ]

    if is_nba:
        h_sh = get_live_nba_3pm_roster(target_gm.get("home_id"), game_id=g_id)
        if h_sh:
            candidates.append({"game": target_gm, "type": "NBA Player 3-Pointers Made", "side": "Over", "line": 1.5, "picked_team": h_sh[0][0], "desc": f"{h_sh[0][0]} 2+ Three-Pointers", "prob": 0.68, "matchup": m_str})

    return candidates[:effective_legs]

def generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice, lead_game=None):
    if not pool:
        return []

    effective_legs = max(2, int(num_legs))
    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice

    is_totals_only = "Totals" in chosen_market
    is_spreads_only = "Spreads" in chosen_market
    is_ml_only = "Straight Up" in chosen_market or "Moneyline" in chosen_market
    is_points_prop = "Player Points" in chosen_market
    is_3pm_prop = ("Three-Pointers" in chosen_market or "3-Pointers" in chosen_market)
    is_td_prop = "Touchdown" in chosen_market

    eval_pool = list(pool)
    if lead_game and lead_game in eval_pool:
        eval_pool.remove(lead_game)
        eval_pool.insert(0, lead_game)

    candidates = []
    for gm in eval_pool:
        is_nba = (gm.get("league") == "NBA")
        ou_open = round_half_point(gm.get("market_ou", 224.5 if is_nba else 47.5))
        spread_open = round_half_point(gm.get("market_spread", -3.5))

        fav_team = gm["home_team"] if spread_open < 0 else gm["away_team"]
        dog_team = gm["away_team"] if spread_open < 0 else gm["home_team"]
        fav_spread = spread_open if fav_team == gm["home_team"] else -spread_open

        # Totals candidate
        tot_line = round_half_point(ou_open + (7.5 if is_safe else 1.5))
        candidates.append({"game": gm, "type": "Game Total", "side": "Under", "line": tot_line, "picked_team": gm["home_team"], "desc": f"Under {tot_line:.1f}", "prob": 0.74 if is_safe else 0.60, "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"})

        # Spread candidate
        spd_line = round_half_point(abs(fav_spread) + 4.5) if is_safe else fav_spread
        spd_team = dog_team if is_safe else fav_team
        candidates.append({"game": gm, "type": "Point Spread (ATS)", "side": "Spread", "line": spd_line, "picked_team": spd_team, "desc": f"{spd_team} {spd_line:+.1f}", "prob": 0.72 if is_safe else 0.55, "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"})

        # Props candidate (verified live active rosters)
        if is_nba:
            h_sh = get_live_nba_3pm_roster(gm.get("home_id"), game_id=gm.get("id"))
            if h_sh:
                candidates.append({"game": gm, "type": "NBA Player 3-Pointers Made", "side": "Over", "line": 1.5, "picked_team": h_sh[0][0], "desc": f"{h_sh[0][0]} 2+ Three-Pointers", "prob": 0.68, "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"})

    if is_totals_only: filtered = [c for c in candidates if c["type"] == "Game Total"]
    elif is_spreads_only: filtered = [c for c in candidates if c["type"] == "Point Spread (ATS)"]
    elif is_ml_only: filtered = [c for c in candidates if "Moneyline" in c["type"]]
    elif is_3pm_prop: filtered = [c for c in candidates if c["type"] == "NBA Player 3-Pointers Made"]
    else: filtered = candidates

    selected = []
    used_matchups = set()
    sorted_candidates = sorted(filtered, key=lambda x: x["prob"], reverse=not is_high_profit)

    for item in sorted_candidates:
        m = item["matchup"]
        if m not in used_matchups:
            selected.append(item)
            used_matchups.add(m)
            if len(selected) == effective_legs:
                break

    return selected

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo Builder")
    st.caption("Algorithmic parlay optimizer with verified active player rosters and SGP engine.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []
    if "cb_form_nonce" not in st.session_state:
        st.session_state.cb_form_nonce = 0

    with st.container(border=True):
        st.markdown("#### 🤖 Multi-Leg Optimizer Controls")

        sgp_mode = st.radio("Parlay Scope Structure", ["🌐 Cross-Game Parlay", "🏟️ Same-Game Parlay (All Legs from 1 Game)"], horizontal=True, key="cb_sgp_mode")
        is_sgp = "Same-Game" in sgp_mode

        r1_c1, r1_c2, r1_c3 = st.columns(3)
        league_choice = r1_c1.selectbox("Primary League", ["All Games (Cross-Sport)", "NBA", "NFL", "NCAA Football"], key="cb_static_league")
        t_filter = r1_c2.selectbox("Game Filter Status", ["🌐 All Matchups", "⏳ Upcoming Games", "⚡ Live Games"], key="cb_static_filter")
        num_legs = r1_c3.number_input("Target # of Legs", min_value=2, max_value=8 if is_sgp else 15, value=3 if is_sgp else 4, step=1, key="cb_static_legs")

        pool = games_data
        if league_choice == "NBA": pool = [g for g in pool if g.get("league") == "NBA"]
        elif league_choice == "NFL": pool = [g for g in pool if g.get("league") == "NFL"]
        elif league_choice == "NCAA Football": pool = [g for g in pool if g.get("league") == "NCAA"]

        if t_filter == "⏳ Upcoming Games": pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
        elif t_filter == "⚡ Live Games": pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]

        r2_c1, r2_c2 = st.columns(2)
        if league_choice == "NBA":
            market_options = ["⚡ System Mix", "📊 Game Totals", "🛡️ Point Spreads", "🏆 Moneylines", "🎯 NBA Player Three-Pointers Made (1+, 2+, 3+)"]
        else:
            market_options = ["⚡ System Mix", "📊 Game Totals", "🛡️ Point Spreads", "🏆 Moneylines"]

        chosen_market = r2_c1.selectbox("Target Market Focus", market_options, key="cb_static_market")
        strat_choice = r2_c2.selectbox("Strategy Profile", ["🎯 Mixed Tier Spectrum", "🛡️ Safe Floor", "⚖️ Balanced Edge", "🚀 High Profit"], key="cb_static_strat")

        target_selected_game = None
        if pool:
            game_labels = [f"[{gm.get('kickoff', 'Upcoming')}] [{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')}" for gm in pool]
            sel_g_idx = st.selectbox("Select Target Matchup (SGP / Anchor)", range(len(game_labels)), format_func=lambda x: game_labels[x], key="cb_game_specific_selector")
            target_selected_game = pool[sel_g_idx]

        if st.button("⚡ Generate Combo Ticket", type="primary", use_container_width=True, disabled=not bool(pool)):
            if is_sgp and target_selected_game:
                st.session_state.combo_active_legs = generate_same_game_combo(target_selected_game, num_legs, chosen_market, strat_choice)
            else:
                st.session_state.combo_active_legs = generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice, lead_game=target_selected_game)
            st.session_state.cb_form_nonce += 1
            st.rerun()

    # Active Parlay Ticket Display
    legs = st.session_state.combo_active_legs
    if legs:
        st.markdown("---")
        compound_p = 1.0
        for lg in legs: compound_p *= float(lg.get("prob", 0.55))
        fair_mult = max(1.1, round(1.0 / max(0.001, compound_p), 2))

        with st.container(border=True):
            st.markdown(f"#### 🔗 Active {len(legs)}-Leg Combo Ticket (Est Payout: {fair_mult}x)")
            for idx, leg in enumerate(legs):
                st.info(f"**#{idx+1}**: {leg.get('desc')} [{leg.get('matchup')}] — {leg.get('prob', 0.55)*100:.1f}% Leg Win Prob")

        f_nonce = st.session_state.cb_form_nonce
        with st.form(f"combo_form_{f_nonce}"):
            c1, c2 = st.columns(2)
            risk = c1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
            payout = c2.number_input("Payout ($)", min_value=1.0, value=round(risk * fair_mult, 2), step=5.0)

            if st.form_submit_button("🔒 Lock In Parlay", type="primary", use_container_width=True):
                tkt = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": f"{len(legs)}-Leg Combo",
                    "bet_category": "Combo",
                    "matchup": legs[0].get("matchup") if is_sgp else f"{len(legs)}-Leg Multi-Game",
                    "bet": f"{len(legs)}-Leg Parlay: " + ", ".join([l['desc'] for l in legs[:2]]) + "...",
                    "risk_dollars": float(risk),
                    "payout_dollars": float(payout),
                    "payout": float(payout),
                    "locked_profit": float(payout) - float(risk),
                    "win_prob": f"{compound_p * 100:.1f}%",
                    "status": "Pending",
                    "notes": f"[{league_choice}] {strat_choice}"
                }
                st.session_state.saved_bets.insert(0, tkt)
                save_all_storage(
                    st.session_state.saved_bets,
                    st.session_state.chat_messages,
                    st.session_state.user_accounts,
                    st.session_state.banned_emails,
                    st.session_state.game_snapshots,
                    st.session_state.support_tickets
                )
                st.toast(f"🎉 Locked in {len(legs)}-Leg Combo!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
