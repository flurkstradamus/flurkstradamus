import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice):
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

    candidates = []

    for gm in pool:
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

        # 1. TOTALS CANDIDATE
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

        # 2. SPREAD CANDIDATE
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

        # 3. MONEYLINE CANDIDATE
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

        # 4. PLAYER PROPS CANDIDATES
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

    # Filter candidates by chosen market
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
    st.caption("Algorithmic parlay optimizer with cross-sport leg modeling, custom manual leg entry, and automated bankroll tracking.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []
    if "cb_form_nonce" not in st.session_state:
        st.session_state.cb_form_nonce = 0
    if "cb_needs_refresh" not in st.session_state:
        st.session_state.cb_needs_refresh = False
    if "cb_editing_idx" not in st.session_state:
        st.session_state.cb_editing_idx = None

    # AI Combo Optimizer Controls
    with st.container(border=True):
        st.markdown("#### 🤖 AI Multi-Leg Optimizer")

        # ROW 1 (3 Columns): Primary League / Slate Scope, Game Filter Status, Target # of Legs
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
            max_value=15,
            value=4,
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

        # Auto-recalculate if user modified dropdowns and a combo is already loaded
        if st.session_state.cb_needs_refresh and len(st.session_state.combo_active_legs) > 0:
            if pool:
                st.session_state.combo_active_legs = generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice)
                st.session_state.cb_form_nonce += 1
            st.session_state.cb_needs_refresh = False

        c_act1, c_act2 = st.columns([3.5, 1.5], vertical_alignment="bottom")
        with c_act1:
            st.caption(f"Active Pool: {len(pool)} available matchups across {league_choice} (Compiling {int(num_legs)} legs)")
        with c_act2:
            if st.button("⚡ Generate Combo", type="primary", use_container_width=True, disabled=len(pool) < 2):
                st.session_state.combo_active_legs = generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice)
                st.session_state.cb_needs_refresh = False
                st.session_state.cb_form_nonce += 1
                st.session_state.cb_editing_idx = None
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
        h_col1, h_col2 = st.columns([3.5, 1.5], vertical_alignment="center")
        with h_col1:
            st.markdown(f"#### 🎟️ Active {len(legs)}-Leg Combo Ticket")
        with h_col2:
            if st.button("🗑️ Clear All Legs", use_container_width=True):
                st.session_state.combo_active_legs = []
                st.session_state.cb_editing_idx = None
                st.rerun()

        # Compound probability calculation
        compound_p = 1.0
        for lg in legs:
            compound_p *= float(lg.get("prob", 0.55))
        compound_p = max(0.001, min(0.999, compound_p))

        # Suggested Fair Multiplier & Odds
        fair_mult = max(1.1, round(1.0 / compound_p, 2))
        est_roi_pct = int((fair_mult - 1.0) * 100)

        # Header Telemetry Row
        with st.container(border=True):
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                <div style="font-size:1.05rem; font-weight:700;">
                    🔗 {len(legs)}-Leg Parlay <span style="opacity:0.6; font-size:0.80rem;">({strat_choice.split()[1]})</span>
                </div>
                <div style="display:flex; gap:6px;">
                    <span style="background:rgba(56,189,248,0.15); color:#38bdf8; padding:3px 10px; border-radius:6px; font-weight:700; font-size:0.82rem;">
                        🎲 Compound Win Prob: {compound_p * 100:.1f}%
                    </span>
                    <span style="background:#22c55e; color:#000; padding:3px 10px; border-radius:6px; font-weight:800; font-size:0.82rem;">
                        Est. Fair Payout: {fair_mult:.2f}x (+{est_roi_pct}%)
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Render Each Leg Item with Inline Edit and Remove
            for idx, leg_item in enumerate(legs):
                gm = leg_item["game"]
                a_logo = gm.get("away_logo") or DEFAULT_LOGO
                h_logo = gm.get("home_logo") or DEFAULT_LOGO
                a_sh = gm.get("away_short", "AWAY")
                h_sh = gm.get("home_short", "HOME")
                p_val = leg_item.get("prob", 0.55) * 100

                row_col1, row_col2, row_col3 = st.columns([4.8, 0.6, 0.6], vertical_alignment="center")
                with row_col1:
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:8px; padding:10px 14px; margin-bottom:4px; flex-wrap:wrap; gap:8px;">
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

                with row_col2:
                    is_editing = (st.session_state.cb_editing_idx == idx)
                    btn_label = "✖️" if is_editing else "✏️"
                    if st.button(btn_label, key=f"edit_toggle_{idx}_{leg_item.get('desc')}", help="Edit this leg"):
                        st.session_state.cb_editing_idx = None if is_editing else idx
                        st.rerun()

                with row_col3:
                    if st.button("🗑️", key=f"del_leg_{idx}_{leg_item.get('desc')}", help="Remove this leg"):
                        st.session_state.combo_active_legs.pop(idx)
                        if st.session_state.cb_editing_idx == idx:
                            st.session_state.cb_editing_idx = None
                        st.rerun()

                # INLINE EDIT EXPANDER FOR THIS LEG
                if st.session_state.cb_editing_idx == idx:
                    with st.container(border=True):
                        st.caption(f"🔧 **Editing Leg #{idx+1}: {a_sh} @ {h_sh}**")
                        e_c1, e_c2, e_c3 = st.columns(3)
                        
                        curr_type = leg_item.get("type", "Game Total")
                        type_opts = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Custom / Player Prop"]
                        type_idx = type_opts.index(curr_type) if curr_type in type_opts else 0
                        new_type = e_c1.selectbox("Wager Type", type_opts, index=type_idx, key=f"edit_type_{idx}")

                        if new_type == "Game Total":
                            curr_side = "Under" if leg_item.get("side") == "Under" else "Over"
                            new_side = e_c2.selectbox("Side", ["Under", "Over"], index=0 if curr_side == "Under" else 1, key=f"edit_side_{idx}")
                            curr_line = float(leg_item.get("line") if leg_item.get("line") is not None else 224.5)
                            new_line = e_c3.number_input("Line (pts)", value=curr_line, step=0.5, key=f"edit_line_{idx}")
                            new_desc = f"{new_side} {new_line:.1f}"
                            new_team = gm.get("home_team", a_sh)
                            new_p = 0.56 if "Under" in new_side else 0.52

                        elif new_type == "Point Spread (ATS)":
                            teams = [gm.get("home_team", h_sh), gm.get("away_team", a_sh)]
                            cur_p_t = leg_item.get("picked_team", teams[0])
                            t_idx = 1 if cur_p_t in teams[1] else 0
                            new_team = e_c2.selectbox("Covering Team", teams, index=t_idx, key=f"edit_team_{idx}")
                            curr_spd = float(leg_item.get("line") if leg_item.get("line") is not None else -3.5)
                            new_line = e_c3.number_input("Spread", value=curr_spd, step=0.5, key=f"edit_spd_{idx}")
                            new_side = "Spread"
                            new_desc = f"{new_team} {new_line:+.1f}"
                            new_p = 0.55

                        elif new_type == "Straight Up Winner (Moneyline)":
                            teams = [gm.get("home_team", h_sh), gm.get("away_team", a_sh)]
                            cur_p_t = leg_item.get("picked_team", teams[0])
                            t_idx = 1 if cur_p_t in teams[1] else 0
                            new_team = e_c2.selectbox("Winner", teams, index=t_idx, key=f"edit_ml_{idx}")
                            new_line = None
                            new_side = "Moneyline"
                            new_desc = f"{new_team} ML"
                            new_p = 0.62

                        else:
                            new_desc = e_c2.text_input("Custom Pick Label", value=leg_item.get("desc", ""), key=f"edit_custom_{idx}")
                            new_line = None
                            new_side = "Custom"
                            new_team = leg_item.get("picked_team", a_sh)
                            new_p = float(leg_item.get("prob", 0.52))

                        if st.button("💾 Apply Leg Update", key=f"save_leg_{idx}", type="primary", use_container_width=True):
                            st.session_state.combo_active_legs[idx] = {
                                "game": gm,
                                "type": new_type,
                                "side": new_side,
                                "line": new_line,
                                "picked_team": new_team,
                                "desc": new_desc,
                                "prob": new_p,
                                "matchup": leg_item.get("matchup")
                            }
                            st.session_state.cb_editing_idx = None
                            st.toast(f"✅ Updated Leg #{idx+1} to {new_desc}!", icon="💾")
                            st.rerun()

        # LOCK-IN FORM
        f_nonce = st.session_state.cb_form_nonce
        with st.form(f"combo_lock_in_form_{f_nonce}"):
            c1, c2 = st.columns(2)
            risk = c1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
            suggested_payout = round(float(risk) * fair_mult, 2)
            payout = c2.number_input("Payout ($)", min_value=1.0, value=suggested_payout, step=5.0)

            actual_profit = float(payout) - float(risk)
            combo_title = f"{len(legs)}-Leg: " + ", ".join([l.get("desc", "") for l in legs[:3]]) + ("..." if len(legs) > 3 else "")

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
                    "type": f"{len(legs)}-Leg Combo",
                    "bet_category": "Combo",
                    "matchup": f"{len(legs)}-Leg Cross-Sport Combo",
                    "bet": combo_title,
                    "risk_dollars": float(risk),
                    "payout_dollars": float(payout),
                    "payout": float(payout),
                    "locked_profit": float(actual_profit),
                    "win_prob": f"{compound_p * 100:.1f}%",
                    "status": "Pending",
                    "parsed_legs": parsed_legs,
                    "notes": f"[{league_choice}] {len(legs)}-Leg Combo [{strat_choice.split()[1]}]"
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
                st.session_state.cb_editing_idx = None
                st.toast(f"🎉 Locked in {len(legs)}-Leg Combo!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
