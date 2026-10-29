import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def generate_same_game_combo(target_gm, num_legs, chosen_market, strat_choice):
    if not target_gm:
        return []

    effective_legs = max(2, int(num_legs))
    is_nba = (target_gm.get("league") == "NBA")

    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice
    is_balanced = "Balanced" in strat_choice

    ou_open = round_half_point(target_gm.get("market_ou", 224.5 if is_nba else 47.5))
    spread_open = round_half_point(target_gm.get("market_spread", -3.5))

    fav_team = target_gm["home_team"] if spread_open < 0 else target_gm["away_team"]
    dog_team = target_gm["away_team"] if spread_open < 0 else target_gm["home_team"]
    fav_spread = spread_open if fav_team == target_gm["home_team"] else -spread_open

    add_score = 40 if is_nba else 14
    h_prob = calculate_moneyline_prob(
        target_gm["home_score"] + add_score,
        target_gm["away_score"] + add_score,
        target_gm.get("home_record", "0-0"),
        target_gm.get("away_record", "0-0")
    )

    m_str = f"{target_gm.get('away_short')} @ {target_gm.get('home_short')}"
    candidates = []

    # 1. TOTALS LEG
    if is_safe:
        t_line = round_half_point(ou_open + (8.5 if is_nba else 6.5))
        t_prob = 0.77
        t_side = "Under"
    elif is_high_profit:
        t_line = round_half_point(ou_open - (4.5 if is_nba else 3.5))
        t_prob = 0.49
        t_side = "Under"
    elif is_balanced:
        t_line = round_half_point(ou_open + (2.5 if is_nba else 1.5))
        t_prob = 0.60
        t_side = "Under"
    else: # Mixed
        t_line = round_half_point(ou_open + (7.5 if is_nba else 4.5))
        t_prob = 0.73
        t_side = "Under"

    candidates.append({
        "game": target_gm,
        "type": "Game Total",
        "side": t_side,
        "line": t_line,
        "picked_team": target_gm["home_team"],
        "desc": f"{t_side} {t_line:.1f}",
        "prob": t_prob,
        "matchup": m_str
    })

    # 2. SPREAD LEG
    if is_safe:
        spd_team = dog_team
        s_line = round_half_point(abs(fav_spread) + (6.5 if is_nba else 4.5))
        s_prob = 0.75
    elif is_high_profit:
        spd_team = fav_team
        s_line = round_half_point(fav_spread - (3.5 if is_nba else 2.5))
        s_prob = 0.46
    elif is_balanced:
        spd_team = fav_team
        s_line = fav_spread
        s_prob = 0.55
    else: # Mixed
        spd_team = dog_team
        s_line = round_half_point(abs(fav_spread) + (4.5 if is_nba else 3.5))
        s_prob = 0.69

    candidates.append({
        "game": target_gm,
        "type": "Point Spread (ATS)",
        "side": "Spread",
        "line": s_line,
        "picked_team": spd_team,
        "desc": f"{spd_team} {s_line:+.1f}",
        "prob": s_prob,
        "matchup": m_str
    })

    # 3. MONEYLINE LEG
    if is_high_profit:
        ml_t = dog_team
        ml_p = min(0.46, min(h_prob, 1.0 - h_prob))
    else:
        ml_t = fav_team
        ml_p = max(0.68, max(h_prob, 1.0 - h_prob))

    candidates.append({
        "game": target_gm,
        "type": "Straight Up Winner (Moneyline)",
        "side": "Moneyline",
        "line": None,
        "picked_team": ml_t,
        "desc": f"{ml_t} ML",
        "prob": ml_p,
        "matchup": m_str
    })

    # 4. PLAYER PROPS LEGS
    if is_nba:
        h_roster = get_live_nba_roster(target_gm.get("home_id") or target_gm.get("home_short")) or [("Primary Scorer", "G", 22.5)]
        a_roster = get_live_nba_roster(target_gm.get("away_id") or target_gm.get("away_short")) or [("Away Scorer", "G", 20.5)]

        p1_name, _, p1_pts = h_roster[0]
        p1_line = max(9.5, round_half_point(float(p1_pts) - (5.5 if is_safe else 1.5)))
        candidates.append({
            "game": target_gm,
            "type": "Player Points Prop",
            "side": "Over",
            "line": p1_line,
            "picked_team": p1_name,
            "desc": f"{p1_name} Over {p1_line:.1f} Pts",
            "prob": 0.72 if is_safe else 0.62,
            "matchup": m_str
        })

        p2_name, _, p2_pts = a_roster[0]
        p2_line = max(8.5, round_half_point(float(p2_pts) - (4.5 if is_safe else 2.0)))
        candidates.append({
            "game": target_gm,
            "type": "Player Points Prop",
            "side": "Over",
            "line": p2_line,
            "picked_team": p2_name,
            "desc": f"{p2_name} Over {p2_line:.1f} Pts",
            "prob": 0.68 if is_safe else 0.58,
            "matchup": m_str
        })

        if len(h_roster) > 1:
            p3_name, _, p3_pts = h_roster[1]
            p3_line = max(7.5, round_half_point(float(p3_pts) - 3.5))
            candidates.append({
                "game": target_gm,
                "type": "Player Points Prop",
                "side": "Over",
                "line": p3_line,
                "picked_team": p3_name,
                "desc": f"{p3_name} Over {p3_line:.1f} Pts",
                "prob": 0.65,
                "matchup": m_str
            })
    else:
        h_fb = get_live_football_roster(target_gm.get("home_id") or target_gm.get("home_short"), target_gm.get("league")) or [("Primary RB", "RB")]
        a_fb = get_live_football_roster(target_gm.get("away_id") or target_gm.get("away_short"), target_gm.get("league")) or [("Away RB", "RB")]

        p1_fb = h_fb[0][0]
        candidates.append({
            "game": target_gm,
            "type": "Football Anytime Touchdown Scorer",
            "side": "TD",
            "line": 1.0,
            "picked_team": p1_fb,
            "desc": f"{p1_fb} Any Time TD",
            "prob": 0.52 if is_safe else 0.47,
            "matchup": m_str
        })

        p2_fb = a_fb[0][0]
        candidates.append({
            "game": target_gm,
            "type": "Football Anytime Touchdown Scorer",
            "side": "TD",
            "line": 1.0,
            "picked_team": p2_fb,
            "desc": f"{p2_fb} Any Time TD",
            "prob": 0.48,
            "matchup": m_str
        })

    return candidates[:effective_legs]

def generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice, lead_game=None):
    if not pool:
        return []

    effective_legs = max(2, int(num_legs))

    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice
    is_balanced = "Balanced" in strat_choice

    is_totals_only = "Totals" in chosen_market
    is_spreads_only = "Spreads" in chosen_market
    is_ml_only = "Straight Up" in chosen_market or "Moneyline" in chosen_market
    is_points_prop = "Player Points" in chosen_market
    is_td_prop = "Touchdown" in chosen_market

    # Put lead game at the top of the pool if specified
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

        add_score = 40 if is_nba else 14
        h_prob = calculate_moneyline_prob(
            gm["home_score"] + add_score,
            gm["away_score"] + add_score,
            gm.get("home_record", "0-0"),
            gm.get("away_record", "0-0")
        )

        # TOTALS CANDIDATE
        if is_safe:
            cushion = 8.5 if is_nba else 6.5
            tot_line = round_half_point(ou_open + cushion)
            tot_prob = 0.77
            tot_desc = f"Under {tot_line:.1f}"
        elif is_high_profit:
            tot_line = round_half_point(ou_open - (4.5 if is_nba else 3.5))
            tot_prob = 0.49
            tot_desc = f"Under {tot_line:.1f}"
        elif is_balanced:
            tot_line = round_half_point(ou_open + (2.5 if is_nba else 1.5))
            tot_prob = 0.60
            tot_desc = f"Under {tot_line:.1f}"
        else: # Mixed
            tot_line = round_half_point(ou_open + (7.5 if is_nba else 4.5))
            tot_prob = 0.73
            tot_desc = f"Under {tot_line:.1f}"

        candidates.append({
            "game": gm,
            "type": "Game Total",
            "side": "Under",
            "line": tot_line,
            "picked_team": gm["home_team"],
            "desc": tot_desc,
            "prob": tot_prob,
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
        })

        # SPREAD CANDIDATE
        if is_safe:
            dog_line = round_half_point(abs(fav_spread) + (6.5 if is_nba else 4.5))
            spd_prob = 0.75
            spd_team = dog_team
            spd_desc = f"{dog_team} {dog_line:+.1f}"
            spd_side = "Spread"
        elif is_high_profit:
            lay_line = round_half_point(fav_spread - (3.5 if is_nba else 2.5))
            spd_prob = 0.46
            spd_team = fav_team
            spd_desc = f"{fav_team} {lay_line:+.1f}"
            spd_side = "Spread"
        elif is_balanced:
            spd_team = fav_team
            lay_line = fav_spread
            spd_prob = 0.55
            spd_desc = f"{fav_team} {lay_line:+.1f}"
            spd_side = "Spread"
        else: # Mixed
            dog_line = round_half_point(abs(fav_spread) + (4.5 if is_nba else 3.5))
            spd_prob = 0.69
            spd_team = dog_team
            spd_desc = f"{dog_team} {dog_line:+.1f}"
            spd_side = "Spread"

        candidates.append({
            "game": gm,
            "type": "Point Spread (ATS)",
            "side": spd_side,
            "line": dog_line if 'dog_line' in locals() else lay_line,
            "picked_team": spd_team,
            "desc": spd_desc,
            "prob": spd_prob,
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
        })

        # MONEYLINE CANDIDATE
        if is_high_profit:
            ml_target = dog_team
            ml_prob = min(0.46, min(h_prob, 1.0 - h_prob))
        else:
            ml_target = fav_team
            ml_prob = max(0.68, max(h_prob, 1.0 - h_prob))

        candidates.append({
            "game": gm,
            "type": "Straight Up Winner (Moneyline)",
            "side": "Moneyline",
            "line": None,
            "picked_team": ml_target,
            "desc": f"{ml_target} ML",
            "prob": ml_prob,
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
        })

        # PLAYER PROPS CANDIDATES
        if is_nba:
            h_roster = get_live_nba_roster(gm.get("home_id") or gm.get("home_short")) or [("Primary Scorer", "G", 22.5)]
            star_player, _, base_pts = h_roster[0]
            if is_safe:
                prop_line = max(9.5, round_half_point(float(base_pts) - 5.5))
                prop_prob = 0.74
            elif is_high_profit:
                prop_line = round_half_point(float(base_pts) + 3.5)
                prop_prob = 0.44
            else:
                prop_line = float(base_pts)
                prop_prob = 0.58

            candidates.append({
                "game": gm,
                "type": "Player Points Prop",
                "side": "Over",
                "line": prop_line,
                "picked_team": star_player,
                "desc": f"{star_player} Over {prop_line:.1f} Pts",
                "prob": prop_prob,
                "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
            })
        else:
            f_roster = get_live_football_roster(gm.get("home_id") or gm.get("home_short"), gm.get("league")) or [("Primary RB", "RB")]
            star_fb = f_roster[0][0]
            td_prob = 0.46 if is_high_profit else (0.54 if is_safe else 0.49)
            candidates.append({
                "game": gm,
                "type": "Football Anytime Touchdown Scorer",
                "side": "TD",
                "line": 1.0,
                "picked_team": star_fb,
                "desc": f"{star_fb} Any Time TD",
                "prob": td_prob,
                "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
            })

    if is_totals_only:
        filtered = [c for c in candidates if c["type"] == "Game Total"]
    elif is_spreads_only:
        filtered = [c for c in candidates if c["type"] == "Point Spread (ATS)"]
    elif is_ml_only:
        filtered = [c for c in candidates if "Moneyline" in c["type"]]
    elif is_points_prop:
        filtered = [c for c in candidates if c["type"] == "Player Points Prop"]
    elif is_td_prop:
        filtered = [c for c in candidates if "Touchdown" in c["type"]]
    else:
        filtered = candidates

    selected = []
    used_matchups = set()

    # If a lead game is designated, ensure its top pick is selected first
    if lead_game:
        lead_m = f"{lead_game.get('away_short')} @ {lead_game.get('home_short')}"
        lead_candidates = [c for c in filtered if c["matchup"] == lead_m]
        if lead_candidates:
            best_lead = sorted(lead_candidates, key=lambda x: x["prob"], reverse=not is_high_profit)[0]
            selected.append(best_lead)
            used_matchups.add(lead_m)

    sorted_candidates = sorted(filtered, key=lambda x: x["prob"], reverse=not is_high_profit)

    for item in sorted_candidates:
        m = item["matchup"]
        if m not in used_matchups:
            selected.append(item)
            used_matchups.add(m)
            if len(selected) == effective_legs:
                break

    return selected

def trigger_combo_auto_refresh():
    st.session_state.cb_needs_refresh = True

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo Builder")
    st.caption("Algorithmic parlay optimizer with cross-sport leg modeling, same-game parlays (SGP), and automated bankroll tracking.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []
    if "cb_form_nonce" not in st.session_state:
        st.session_state.cb_form_nonce = 0
    if "cb_needs_refresh" not in st.session_state:
        st.session_state.cb_needs_refresh = False

    # AI Combo Optimizer Controls
    with st.container(border=True):
        st.markdown("#### 🤖 AI Multi-Leg Optimizer")

        # Parlay Scope Selector (Same-Game vs Cross-Game)
        sgp_mode = st.radio(
            "Parlay Scope Structure",
            options=["🌐 Cross-Game Parlay (Different Matchups)", "🏟️ Same-Game Parlay (All Legs from 1 Game)"],
            index=0,
            horizontal=True,
            key="cb_sgp_mode",
            on_change=trigger_combo_auto_refresh
        )
        is_sgp = "Same-Game" in sgp_mode

        # ROW 1 (3 Columns): Primary League, Game Filter Status, Target # of Legs
        r1_c1, r1_c2, r1_c3 = st.columns(3)

        league_choice = r1_c1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NBA", "NFL", "NCAA Football"],
            key="cb_static_league",
            on_change=trigger_combo_auto_refresh
        )

        t_filter = r1_c2.selectbox(
            "Game Filter Status",
            options=["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"],
            key="cb_static_filter",
            on_change=trigger_combo_auto_refresh
        )

        num_legs = r1_c3.number_input(
            "Target # of Legs",
            min_value=2,
            max_value=8 if is_sgp else 15,
            value=3 if is_sgp else 4,
            step=1,
            key="cb_static_legs",
            on_change=trigger_combo_auto_refresh
        )

        # Dynamic Market Focus List Based on League
        if league_choice == "NBA":
            market_options = [
                "⚡ Let the System Pick (Best NBA Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏀 NBA Player Points Prop"
            ]
        elif league_choice in ["NFL", "NCAA Football"]:
            market_options = [
                "⚡ Let the System Pick (Best Football Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏈 Football Anytime Touchdown Scorer"
            ]
        else:
            market_options = [
                "⚡ Let the System Pick (Best Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏀 NBA Player Points Prop",
                "🏈 Football Anytime Touchdown Scorer"
            ]

        # ROW 2 (2 Columns): Target Bet / Market Type, Model Strategy Profile
        r2_c1, r2_c2 = st.columns(2)

        chosen_market = r2_c1.selectbox(
            "Target Bet / Market Type",
            options=market_options,
            key="cb_static_market",
            on_change=trigger_combo_auto_refresh
        )

        strat_options = [
            "🎯 Mixed Tier Spectrum (Safe, Balanced, High Profit)",
            "🛡️ Safe Floor (High Win %, Low Drawdown)",
            "⚖️ Balanced Edge (+EV Sweet Spot)",
            "🚀 High Profit (Max Multiplier & Longshots)"
        ]
        strat_choice = r2_c2.selectbox(
            "Model Strategy Profile",
            options=strat_options,
            index=0,
            key="cb_static_strat",
            on_change=trigger_combo_auto_refresh
        )

        # Matchup Pool Resolution
        pool = games_data
        if league_choice == "NBA":
            pool = [g for g in pool if g.get("league") == "NBA"]
        elif league_choice == "NFL":
            pool = [g for g in pool if g.get("league") == "NFL"]
        elif league_choice == "NCAA Football":
            pool = [g for g in pool if g.get("league") == "NCAA"]

        if t_filter == "⏳ Upcoming Games":
            pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
        elif t_filter == "⚡ Live Games":
            pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]
        else:
            pool = [g for g in pool if not g.get("completed", False)]

        # Specific Game Selection Row (Matchup Search + Dropdown)
        c_search, c_game = st.columns([1.5, 2.5])
        q_game = c_search.text_input("🔍 Search Matchup", placeholder="e.g. Celtics, Lakers, Chiefs...", key="cb_q_game_filter", on_change=trigger_combo_auto_refresh)

        filtered_pool = pool
        if q_game.strip():
            q_clean = q_game.strip().lower()
            filtered_pool = [g for g in pool if q_clean in g["home_team"].lower() or q_clean in g["away_team"].lower() or q_clean in g.get("home_short", "").lower() or q_clean in g.get("away_short", "").lower()]

        target_selected_game = None
        if filtered_pool:
            game_labels = [f"[{gm.get('kickoff', 'Scheduled')}] [{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')}" for gm in filtered_pool]
            label_prefix = "Target Matchup (All Legs from This Game)" if is_sgp else "Lead Anchor Matchup (Optional)"
            sel_g_idx = c_game.selectbox(
                label_prefix,
                options=range(len(game_labels)),
                format_func=lambda x: game_labels[x],
                key="cb_game_specific_selector",
                on_change=trigger_combo_auto_refresh
            )
            target_selected_game = filtered_pool[sel_g_idx]
        else:
            c_game.selectbox("Target Matchup", options=["No matching matchups found"], disabled=True)

        # Auto-recalculate if user modified dropdowns and a combo is already loaded
        if st.session_state.cb_needs_refresh and len(st.session_state.combo_active_legs) > 0:
            if is_sgp and target_selected_game:
                st.session_state.combo_active_legs = generate_same_game_combo(target_selected_game, num_legs, chosen_market, strat_choice)
                st.session_state.cb_form_nonce += 1
            elif pool:
                st.session_state.combo_active_legs = generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice, lead_game=target_selected_game)
                st.session_state.cb_form_nonce += 1
            st.session_state.cb_needs_refresh = False

        c_act1, c_act2 = st.columns([3.5, 1.5], vertical_alignment="bottom")
        with c_act1:
            if is_sgp and target_selected_game:
                st.caption(f"🏟️ SGP Focus: {target_selected_game.get('away_short')} @ {target_selected_game.get('home_short')} ({num_legs} single-game correlated legs)")
            elif target_selected_game:
                st.caption(f"Lead Game: {target_selected_game.get('away_short')} @ {target_selected_game.get('home_short')} + {len(pool)-1} slate games ({int(num_legs)} legs total)")
            else:
                st.caption(f"Active Pool: {len(pool)} available matchups across {league_choice} (Compiling {int(num_legs)} cross-game legs)")
        with c_act2:
            can_gen = bool(target_selected_game) if is_sgp else (len(pool) >= 2)
            if st.button("⚡ Generate Combo", type="primary", use_container_width=True, disabled=not can_gen):
                if is_sgp and target_selected_game:
                    st.session_state.combo_active_legs = generate_same_game_combo(target_selected_game, num_legs, chosen_market, strat_choice)
                else:
                    st.session_state.combo_active_legs = generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice, lead_game=target_selected_game)
                st.session_state.cb_needs_refresh = False
                st.session_state.cb_form_nonce += 1
                st.rerun()

    # MANUAL LEG BUILDER SECTION
    with st.expander("➕ Add Custom Leg Manually", expanded=False):
        st.caption("Select a live match from the active slate or type in your own custom match, line, and selection.")
        
        game_choices = ["📝 Custom / Other Matchup"] + [f"{gm.get('away_short')} @ {gm.get('home_short')} [{gm.get('league')}]" for gm in pool]
        sel_gm_idx = st.selectbox("Select Matchup", range(len(game_choices)), format_func=lambda x: game_choices[x], key="man_gm_select")

        if sel_gm_idx == 0:
            man_matchup_str = st.text_input("Custom Matchup Name", placeholder="e.g. DET @ KC, Lakers @ Warriors, etc.")
            chosen_gm_obj = {"away_short": "CUSTOM", "home_short": "WAGER", "league": league_choice}
        else:
            chosen_gm_obj = pool[sel_gm_idx - 1]
            man_matchup_str = f"{chosen_gm_obj.get('away_short')} @ {chosen_gm_obj.get('home_short')}"

        m_c1, m_c2, m_c3 = st.columns(3)
        man_type = m_c1.selectbox("Wager Type", ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Custom / Player Prop"], key="man_wtype")
        
        if man_type == "Game Total":
            man_side = m_c2.selectbox("Side", ["Under", "Over"], key="man_side_total")
            man_line = m_c3.number_input("Line (pts)", value=float(round_half_point(chosen_gm_obj.get("market_ou", 224.5 if chosen_gm_obj.get("league")=="NBA" else 47.5))), step=0.5, key="man_line_total")
            man_desc = f"{man_side} {man_line:.1f}"
            man_team = chosen_gm_obj.get("home_team", man_matchup_str)
            calc_p = 0.55
        elif man_type == "Point Spread (ATS)":
            teams_opt = [chosen_gm_obj.get("home_team", "Home"), chosen_gm_obj.get("away_team", "Away")]
            man_team = m_c2.selectbox("Covering Team", teams_opt, key="man_team_spread")
            man_line = m_c3.number_input("Spread", value=float(round_half_point(chosen_gm_obj.get("market_spread", -3.5))), step=0.5, key="man_line_spread")
            man_side = "Spread"
            man_desc = f"{man_team} {man_line:+.1f}"
            calc_p = 0.54
        elif man_type == "Straight Up Winner (Moneyline)":
            teams_opt = [chosen_gm_obj.get("home_team", "Home"), chosen_gm_obj.get("away_team", "Away")]
            man_team = m_c2.selectbox("Outright Winner", teams_opt, key="man_team_ml")
            man_line = None
            man_side = "Moneyline"
            man_desc = f"{man_team} ML"
            calc_p = 0.60
        else:
            man_desc = m_c2.text_input("Pick Label / Prop", placeholder="e.g. Over 24.5 Pts, Anytime TD", key="man_custom_desc")
            man_side = "Custom"
            man_line = None
            man_team = man_matchup_str
            calc_p = 0.52

        if st.button("➕ Append Leg to Ticket", type="secondary", use_container_width=True):
            if not man_matchup_str.strip():
                st.error("Please enter a matchup description.")
            else:
                new_leg = {
                    "game": chosen_gm_obj,
                    "type": man_type,
                    "side": man_side,
                    "line": man_line,
                    "picked_team": man_team,
                    "desc": man_desc,
                    "prob": calc_p,
                    "matchup": man_matchup_str
                }
                st.session_state.combo_active_legs.append(new_leg)
                st.session_state.cb_form_nonce += 1
                st.toast(f"✅ Appended {man_desc} to combo!", icon="➕")
                st.rerun()

    # ACTIVE TICKET DISPLAY & SUBMISSION
    legs = st.session_state.combo_active_legs

    if legs:
        st.markdown("---")

        # Compound probability calculation
        compound_p = 1.0
        for lg in legs:
            compound_p *= float(lg.get("prob", 0.55))
        compound_p = max(0.001, min(0.999, compound_p))

        # Suggested Fair Multiplier & Odds
        fair_mult = max(1.1, round(1.0 / compound_p, 2))
        est_roi_pct = int((fair_mult - 1.0) * 100)

        parlay_type_badge = "Same-Game Parlay (SGP)" if len({l.get('matchup') for l in legs}) == 1 else "Cross-Game Parlay"

        # Header Telemetry Row with Clean Popover Edit Trigger
        with st.container(border=True):
            hdr_left, hdr_right = st.columns([3.5, 2.5], vertical_alignment="center")
            with hdr_left:
                st.markdown(f"""
                <div style="font-size:1.05rem; font-weight:700;">
                    🔗 {len(legs)}-Leg {parlay_type_badge} <span style="opacity:0.6; font-size:0.80rem;">({strat_choice.split()[1]})</span>
                </div>
                """, unsafe_allow_html=True)
            with hdr_right:
                r_c1, r_c2, r_c3 = st.columns([2.0, 2.0, 1.4], vertical_alignment="center")
                with r_c1:
                    st.markdown(f"<span style='background:rgba(56,189,248,0.15); color:#38bdf8; padding:3px 8px; border-radius:6px; font-weight:700; font-size:0.78rem; white-space:nowrap;'>🎲 {compound_p * 100:.1f}% Prob</span>", unsafe_allow_html=True)
                with r_c2:
                    st.markdown(f"<span style='background:#22c55e; color:#000; padding:3px 8px; border-radius:6px; font-weight:800; font-size:0.78rem; white-space:nowrap;'>{fair_mult:.2f}x (+{est_roi_pct}%)</span>", unsafe_allow_html=True)
                with r_c3:
                    with st.popover("✏️ Edit", use_container_width=True):
                        st.markdown("**Manage Ticket Legs**")
                        st.caption("Remove or deselect any leg from this ticket.")
                        for idx, l_item in enumerate(legs):
                            col_txt, col_del = st.columns([4.2, 1.0], vertical_alignment="center")
                            with col_txt:
                                st.markdown(f"<div style='font-size:0.82rem;'><strong>#{idx+1}</strong> {l_item.get('desc')} <span style='opacity:0.6;'>({l_item.get('matchup')})</span></div>", unsafe_allow_html=True)
                            with col_del:
                                if st.button("🗑️", key=f"pop_del_{idx}_{l_item.get('desc')}", help="Remove this leg"):
                                    st.session_state.combo_active_legs.pop(idx)
                                    st.rerun()
                        st.divider()
                        if st.button("🗑️ Clear All Legs", type="secondary", use_container_width=True):
                            st.session_state.combo_active_legs = []
                            st.rerun()

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

            # Clean Full-Width Leg Rows
            for idx, leg_item in enumerate(legs):
                gm = leg_item["game"]
                a_logo = gm.get("away_logo") or DEFAULT_LOGO
                h_logo = gm.get("home_logo") or DEFAULT_LOGO
                a_sh = gm.get("away_short", "AWAY")
                h_sh = gm.get("home_short", "HOME")
                p_val = leg_item.get("prob", 0.55) * 100

                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:8px; padding:10px 14px; margin-bottom:6px; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="background:rgba(255,255,255,0.08); color:#f8fafc; font-weight:800; padding:2px 8px; border-radius:4px; font-size:0.80rem;">
                            #{idx+1}
                        </span>
                        <img src="{a_logo}" width="20" height="20" style="border-radius:50%; object-fit:contain;">
                        <strong>{a_sh}</strong>
                        <span style="opacity:0.35;">@</span>
                        <img src="{h_logo}" width="20" height="20" style="border-radius:50%; object-fit:contain;">
                        <strong>{h_sh}</strong>
                        <span style="opacity:0.6; font-size:0.75rem;">[{gm.get('league', 'SPORTS')}]</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <span style="font-weight:700; color:#4ade80; font-size:0.95rem;">{leg_item.get('desc')}</span>
                        <span style="opacity:0.6; font-size:0.78rem;">{leg_item.get('type')}</span>
                        <span style="background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:700;">
                            {p_val:.1f}% Leg Win
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # LOCK-IN FORM
        f_nonce = st.session_state.cb_form_nonce
        with st.form(f"combo_lock_in_form_{f_nonce}"):
            c1, c2 = st.columns(2)
            risk = c1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
            suggested_payout = round(float(risk) * fair_mult, 2)
            payout = c2.number_input("Payout ($)", min_value=1.0, value=suggested_payout, step=5.0)

            actual_profit = float(payout) - float(risk)
            matchup_title = legs[0].get("matchup") if len({l.get('matchup') for l in legs}) == 1 else f"{len(legs)}-Leg Cross-Sport Combo"
            combo_title = f"{len(legs)}-Leg SGP: " if "Same-Game" in parlay_type_badge else f"{len(legs)}-Leg Combo: "
            combo_title += ", ".join([l.get("desc", "") for l in legs[:3]]) + ("..." if len(legs) > 3 else "")

            if st.form_submit_button("🔒 Lock In Combo Ticket", type="primary", use_container_width=True):
                parsed_legs = [
                    {
                        "matchup": lg.get("matchup"),
                        "type": lg.get("type"),
                        "side": lg.get("side"),
                        "line": lg.get("line"),
                        "picked_team": lg.get("picked_team")
                    } for lg in legs
                ]

                tkt = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": f"{len(legs)}-Leg SGP" if "Same-Game" in parlay_type_badge else f"{len(legs)}-Leg Combo",
                    "bet_category": "Combo",
                    "matchup": matchup_title,
                    "bet": combo_title,
                    "risk_dollars": float(risk),
                    "payout_dollars": float(payout),
                    "payout": float(payout),
                    "locked_profit": float(actual_profit),
                    "win_prob": f"{compound_p * 100:.1f}%",
                    "status": "Pending",
                    "parsed_legs": parsed_legs,
                    "notes": f"[{league_choice}] {parlay_type_badge} [{strat_choice.split()[1]}]"
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
                st.session_state.combo_active_legs = []
                st.toast(f"🎉 Locked in {len(legs)}-Leg Ticket!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
