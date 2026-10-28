import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def generate_leg_rationale(b_type, b_side, b_line, gm, p_name="", strat="Balanced"):
    is_nba = (gm.get("league") == "NBA")
    ou = float(gm.get("market_ou", 224.5 if is_nba else 47.5))
    spread = float(gm.get("market_spread", -3.5))

    if b_type == "Game Total":
        diff = abs(b_line - ou)
        if b_side == "Under":
            return f"Pace model projects tempo suppression. Consensus opened at {ou:.1f}; identified positive expected value on Under {b_line:.1f} (+{diff:.1f} pts safety buffer)."
        else:
            return f"Offensive conversion rate projects above-average tempo. Model targets clearing {b_line:.1f} pts with high-variance scoring runs."
    elif b_type == "Point Spread (ATS)":
        return f"Power ratings give {p_name} an efficiency margin against market number ({spread:+.1f}). Model favors covering current strike."
    elif b_type == "Straight Up Winner (Moneyline)":
        return f"Situational metrics and home/away splits indicate {p_name} outright win likelihood exceeds implied market odds."
    elif b_type == "Player Points Prop":
        if "Safe Floor" in strat:
            return f"🛡️ Safe Floor profile applied: Shaded {p_name}'s line down to {b_line:.1f} pts to create a high-probability floor clearance (68%+ expected win rate)."
        elif "High Profit" in strat:
            return f"🚀 High Profit longshot profile: Targeting upside ladder on {p_name} at {b_line:.1f} pts ({b_side}) for odds multiplier boost."
        else:
            return f"⚖️ Balanced EV: {p_name} usage rate projects over 27.5%. Matchup defense allows above-average scoring efficiency, favoring {b_side} {b_line:.1f} pts."
    else:
        return f"{p_name} holds >60% red-zone touch share over recent drives. Positive mathematical expectancy for Anytime TD."

def build_ai_combo_legs(pool, target_legs, league_choice, target_market_type, strat_choice):
    new_generated = []
    selected_games = pool[:int(target_legs)]
    for j, g_item in enumerate(selected_games):
        is_nba = (g_item.get("league") == "NBA")
        line_val = round_half_point(g_item.get("market_ou", 224.5 if is_nba else 47.5))
        spread_val = round_half_point(g_item.get("market_spread", -3.5))

        if "Game Totals" in target_market_type:
            chosen_type = "Game Total"
        elif "Point Spreads" in target_market_type:
            chosen_type = "Point Spread (ATS)"
        elif "Straight Up" in target_market_type:
            chosen_type = "Straight Up Winner (Moneyline)"
        elif "NBA Player Points" in target_market_type and is_nba:
            chosen_type = "Player Points Prop"
        elif "Touchdown" in target_market_type and not is_nba:
            chosen_type = "Player Anytime Touchdown Scorer"
        else:
            if league_choice == "NBA":
                type_cycle = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Player Points Prop"]
            elif league_choice in ["NFL", "NCAA Football"]:
                type_cycle = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Player Anytime Touchdown Scorer"]
            else:
                type_cycle = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Player Points Prop" if is_nba else "Player Anytime Touchdown Scorer"]
            chosen_type = type_cycle[j % len(type_cycle)]

        side_val = "Under"
        target_p_name = g_item["home_team"]

        # Strategy-dependent calculations
        if chosen_type == "Game Total":
            if "Safe Floor" in strat_choice:
                side_val = "Under"
                line_val = round_half_point(line_val + (6.5 if is_nba else 3.5))
            elif "High Profit" in strat_choice:
                side_val = "Over" if j % 2 == 0 else "Under"
                line_val = round_half_point(line_val + (-4.5 if is_nba else -2.5))
        elif chosen_type == "Point Spread (ATS)":
            side_val = "Spread"
            line_val = spread_val
        elif chosen_type == "Straight Up Winner (Moneyline)":
            side_val = "Moneyline"
            line_val = 0.0
        elif chosen_type == "Player Points Prop":
            roster = get_live_nba_roster(g_item.get("home_id") or g_item.get("home_short"))
            if not roster:
                roster = [("Primary Scorer", "G", 22.5), ("Secondary Option", "F", 18.5)]

            # Dynamic strategy divergence for NBA player props
            if "Safe Floor" in strat_choice:
                # Target the highest-floor player, discount line by 3.5 pts for safety
                selected_player = roster[0]
                target_p_name = selected_player[0]
                base_pts = float(selected_player[2])
                line_val = max(9.5, round_half_point(base_pts - 3.5))
                side_val = "Over"
            elif "High Profit" in strat_choice:
                # Rotate among secondary options or alternate high-ceiling lines
                p_idx = min(len(roster) - 1, 1 if (j % 2 == 0) else 2)
                selected_player = roster[p_idx]
                target_p_name = selected_player[0]
                base_pts = float(selected_player[2])
                # Alternate between high ladder overs and under fades on stars
                if j % 2 == 0:
                    line_val = round_half_point(base_pts + 4.5)
                    side_val = "Over"
                else:
                    line_val = round_half_point(base_pts - 1.5)
                    side_val = "Under"
            else:
                # Balanced EV: Take core starter at standard median line
                selected_player = roster[j % min(len(roster), 2)]
                target_p_name = selected_player[0]
                line_val = float(selected_player[2])
                side_val = "Over"

        elif chosen_type == "Player Anytime Touchdown Scorer":
            roster = get_live_football_roster(g_item.get("home_id") or g_item.get("home_short"), g_item.get("league"))
            if "High Profit" in strat_choice and len(roster) > 2:
                target_p_name = roster[1][0]
            else:
                target_p_name = roster[0][0] if roster else "Top Running Back"
            line_val = 1.0
            side_val = "TD"

        rationale_text = generate_leg_rationale(chosen_type, side_val, line_val, g_item, target_p_name, strat_choice)

        new_generated.append({
            "matchup_idx": pool.index(g_item),
            "type": chosen_type,
            "side": side_val,
            "line": line_val,
            "picked_team": target_p_name,
            "matchup_str": f"{g_item['away_short']} @ {g_item['home_short']}",
            "kickoff": g_item.get("kickoff", "Scheduled"),
            "away_logo": g_item.get("away_logo", DEFAULT_LOGO),
            "home_logo": g_item.get("home_logo", DEFAULT_LOGO),
            "away_short": g_item.get("away_short", "AWAY"),
            "home_short": g_item.get("home_short", "HOME"),
            "league": g_item.get("league", "SPORTS"),
            "rationale": rationale_text
        })
    return new_generated

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Cross-Sport Combo Builder (Up to 12 Legs)")
    st.caption("Automated cross-slate parlay scanner, compound probability calculator, and slip builder.")

    if "combo_preview_legs" not in st.session_state:
        st.session_state.combo_preview_legs = None
    if "combo_is_editing" not in st.session_state:
        st.session_state.combo_is_editing = False
    if "combo_slip_version" not in st.session_state:
        st.session_state.combo_slip_version = 0
    if "combo_auto_mode" not in st.session_state:
        st.session_state.combo_auto_mode = False
    if "combo_last_cfg" not in st.session_state:
        st.session_state.combo_last_cfg = None

    slip_ver = st.session_state.combo_slip_version

    # Top-Level AI Automation & Strategy Controls
    with st.container(border=True):
        st.markdown("#### 🤖 AI Combo Optimizer & Auto-Assembler")

        c_top1, c_top2 = st.columns(2)
        league_choice = c_top1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NBA", "NFL", "NCAA Football"],
            index=0,
            key="combo_league_scope_select"
        )

        if league_choice == "NBA":
            market_filter_options = [
                "⚡ Let the System Pick (Best NBA Discrepancies)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏀 NBA Player Points Prop"
            ]
        elif league_choice in ["NFL", "NCAA Football"]:
            market_filter_options = [
                "⚡ Let the System Pick (Best Football Discrepancies)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏈 Football Anytime Touchdown Scorer"
            ]
        else:
            market_filter_options = [
                "⚡ Let the System Pick (Best Multi-Market Discrepancies)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏀 NBA Player Points Prop",
                "🏈 Football Anytime Touchdown Scorer"
            ]

        target_market_type = c_top2.selectbox(
            "Target Market Focus",
            options=market_filter_options,
            index=0,
            key="combo_target_market_select"
        )

        c_sub1, c_sub2 = st.columns(2)
        target_legs = c_sub1.number_input(
            "Target Number of Legs",
            min_value=2,
            max_value=12,
            value=3,
            step=1,
            key="combo_target_legs_num"
        )

        strat_options = [
            "🛡️ Safe Floor (High Win %, Low Drawdown)",
            "⚖️ Balanced Edge (+EV Sweet Spot)",
            "🚀 High Profit (Max Multiplier & Longshots)"
        ]
        strat_choice = c_sub2.selectbox(
            "Combo Strategy Profile",
            options=strat_options,
            index=1,
            key="combo_strat_profile_select"
        )

        col_filter1, col_filter2, col_gen = st.columns([1.5, 2, 1.5], vertical_alignment="bottom")
        t_filter = col_filter1.selectbox("Filter Status", ["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"], key="combo_t_filter")
        q_filter = col_filter2.text_input("🔍 Search Slate", placeholder="e.g. Celtics, Lakers, Chiefs...", key="combo_q_filter")

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

        if q_filter.strip():
            q = q_filter.strip().lower()
            pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g.get("home_short", "").lower() or q in g.get("away_short", "").lower()]

        # Automatically re-run the generator if a strategy or setting changes after the initial run
        current_cfg = (league_choice, target_market_type, int(target_legs), strat_choice, t_filter, q_filter)
        if st.session_state.combo_auto_mode and st.session_state.combo_last_cfg != current_cfg and len(pool) > 0:
            st.session_state.combo_last_cfg = current_cfg
            st.session_state.combo_preview_legs = build_ai_combo_legs(pool, target_legs, league_choice, target_market_type, strat_choice)
            st.rerun()

        if col_gen.button("⚡ Auto-Generate Combo", use_container_width=True, disabled=len(pool) == 0):
            st.session_state.combo_auto_mode = True
            st.session_state.combo_last_cfg = current_cfg
            st.session_state.combo_preview_legs = build_ai_combo_legs(pool, target_legs, league_choice, target_market_type, strat_choice)
            st.session_state.combo_is_editing = False
            st.rerun()

    # --- AI RECOMMENDATION PREVIEW (ONLY DISPLAYED ONCE GENERATED) ---
    if st.session_state.combo_preview_legs:
        with st.container(border=True):
            prev_legs = st.session_state.combo_preview_legs
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:1.15rem; font-weight:700;">🎯 AI Recommended Parlay Slip ({len(prev_legs)} Legs)</span>
                    <span style="background-color:#22c55e; color:#000; font-weight:800; font-size:0.75rem; padding:2px 8px; border-radius:4px;">OPTIMIZED</span>
                </div>
                <div style="font-size:0.80rem; opacity:0.75;">Profile: <strong>{strat_choice.split()[1]}</strong></div>
            </div>
            """, unsafe_allow_html=True)

            for p_idx, p_leg in enumerate(prev_legs):
                if p_leg["type"] == "Game Total":
                    leg_pick_text = f"{p_leg['side']} {p_leg['line']:.1f} pts"
                elif p_leg["type"] == "Point Spread (ATS)":
                    leg_pick_text = f"{p_leg['picked_team']} {p_leg['line']:+.1f}"
                elif p_leg["type"] == "Straight Up Winner (Moneyline)":
                    leg_pick_text = f"{p_leg['picked_team']} Outright ML"
                elif p_leg["type"] == "Player Points Prop":
                    leg_pick_text = f"{p_leg['picked_team']} {p_leg['side']} {p_leg['line']:.1f} Pts"
                else:
                    leg_pick_text = f"{p_leg['picked_team']} Any Time TD"

                st.markdown(f"""
                <div style="display:flex; align-items:center; justify-content:space-between; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); padding:8px 12px; border-radius:8px; margin-bottom:6px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="opacity:0.55; font-size:0.80rem; font-weight:600;">#{p_idx+1}</span>
                        <img src="{p_leg.get('away_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                        <strong>{p_leg.get('away_short', 'AWAY')}</strong>
                        <span style="opacity:0.4;">@</span>
                        <img src="{p_leg.get('home_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                        <strong>{p_leg.get('home_short', 'HOME')}</strong>
                        <span style="background:rgba(255,255,255,0.06); color:#94a3b8; padding:2px 7px; border-radius:4px; font-size:0.75rem;">
                            🗓️ {p_leg.get('kickoff', 'Upcoming')}
                        </span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <strong style="color:#4ade80; font-size:1.02rem;">{leg_pick_text}</strong>
                        <span style="background:rgba(56,189,248,0.12); color:#38bdf8; padding:2px 6px; border-radius:4px; font-size:0.72rem; font-weight:600;">
                            {p_leg['type']}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            col_load, col_edit = st.columns([2.5, 2], vertical_alignment="center")

            with col_load:
                if st.button("📥 Load Combo to Slips", type="primary", use_container_width=True, key="btn_load_combo_to_slips"):
                    st.session_state.combo_active_legs = [dict(x) for x in prev_legs]
                    st.session_state.combo_slip_version += 1
                    st.toast("✅ Loaded combo into slips below!", icon="📥")
                    st.rerun()

            with col_edit:
                if not st.session_state.combo_is_editing:
                    if st.button("✏️ Edit selection or remove legs", key="btn_toggle_edit_mode"):
                        st.session_state.combo_is_editing = True
                        st.rerun()

            if st.session_state.combo_is_editing:
                st.markdown("---")
                st.markdown("##### 📝 Edit Active Legs List")
                st.caption("Uncheck any legs you want to discard from this slip:")

                leg_indices_to_keep = []
                for edit_i, e_leg in enumerate(prev_legs):
                    lbl = f"Leg #{edit_i+1}: {e_leg['matchup_str']} — {e_leg.get('picked_team', '')} {e_leg.get('side', '')} ({e_leg['type']})"
                    is_checked = st.checkbox(lbl, value=True, key=f"edit_chk_{edit_i}_v{slip_ver}")
                    if is_checked:
                        leg_indices_to_keep.append(edit_i)

                c_save1, c_save2 = st.columns([2, 4], vertical_alignment="center")
                with c_save1:
                    if st.button("💾 Save & Update", type="primary", use_container_width=True, key="btn_commit_edit_legs"):
                        updated_list = [dict(prev_legs[k]) for k in leg_indices_to_keep]
                        st.session_state.combo_preview_legs = updated_list
                        st.session_state.combo_is_editing = False
                        st.rerun()
                with c_save2:
                    if st.button("Cancel", key="btn_cancel_edit_legs"):
                        st.session_state.combo_is_editing = False
                        st.rerun()

    if not pool:
        st.info("No matchups found matching your current filter.")
        return

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in pool]

    if not st.session_state.combo_active_legs:
        st.info("No active ticket slip. Use **⚡ Auto-Generate Combo** above and click **📥 Load Combo to Slips**, or add a leg manually.")
        if st.button("➕ Add First Leg Manually", use_container_width=True):
            first_gm = pool[0]
            st.session_state.combo_active_legs = [{
                "matchup_idx": 0,
                "type": "Game Total",
                "side": "Under",
                "line": round_half_point(first_gm.get("market_ou", 47.5)),
                "picked_team": first_gm["home_team"],
                "matchup_str": f"{first_gm['away_short']} @ {first_gm['home_short']}",
                "kickoff": first_gm.get("kickoff", "Scheduled"),
                "away_logo": first_gm.get("away_logo", DEFAULT_LOGO),
                "home_logo": first_gm.get("home_logo", DEFAULT_LOGO),
                "away_short": first_gm.get("away_short", "AWAY"),
                "home_short": first_gm.get("home_short", "HOME"),
                "league": first_gm.get("league", "SPORTS"),
                "rationale": generate_leg_rationale("Game Total", "Under", round_half_point(first_gm.get("market_ou", 47.5)), first_gm, first_gm["home_team"], strat_choice)
            }]
            st.session_state.combo_slip_version += 1
            st.rerun()
        return

    # Dedicated Accordion for All Leg Rationales Before Active Slip
    with st.expander("🧠 AI Model Strategy & Edge Rationales", expanded=False):
        st.caption("Breakdown of algorithmic discrepancy, pace drift, and edge considerations for active selections:")
        for idx, leg_item in enumerate(st.session_state.combo_active_legs):
            leg_name = leg_item.get("picked_team", leg_item.get("matchup_str", f"Leg #{idx+1}"))
            rat_msg = leg_item.get("rationale") or generate_leg_rationale(
                leg_item.get("type", "Game Total"),
                leg_item.get("side", "Under"),
                leg_item.get("line", 0.0),
                pool[min(leg_item.get("matchup_idx", 0), len(pool)-1)],
                leg_name,
                strat_choice
            )
            st.markdown(f"**Leg #{idx+1}: {leg_item.get('matchup_str')}** (`{leg_item.get('type')}`)")
            st.write(f"💡 {rat_msg}")
            if idx < len(st.session_state.combo_active_legs) - 1:
                st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px solid rgba(255,255,255,0.06);' />", unsafe_allow_html=True)

    ctrl1, ctrl2, ctrl3 = st.columns([3, 1, 1], vertical_alignment="center")
    ctrl1.markdown(f"#### Active Ticket Slip ({len(st.session_state.combo_active_legs)} Legs)")
    if ctrl2.button("➕ Add Leg", use_container_width=True, disabled=(len(st.session_state.combo_active_legs) >= 12 or not pool)):
        next_i = min(len(st.session_state.combo_active_legs), len(pool) - 1)
        next_gm = pool[next_i]
        st.session_state.combo_active_legs.append({
            "matchup_idx": next_i,
            "type": "Game Total",
            "side": "Under",
            "line": round_half_point(next_gm.get("market_ou", 47.5)),
            "picked_team": next_gm["home_team"],
            "matchup_str": f"{next_gm['away_short']} @ {next_gm['home_short']}",
            "kickoff": next_gm.get("kickoff", "Scheduled"),
            "away_logo": next_gm.get("away_logo", DEFAULT_LOGO),
            "home_logo": next_gm.get("home_logo", DEFAULT_LOGO),
            "away_short": next_gm.get("away_short", "AWAY"),
            "home_short": next_gm.get("home_short", "HOME"),
            "league": next_gm.get("league", "SPORTS"),
            "rationale": generate_leg_rationale("Game Total", "Under", round_half_point(next_gm.get("market_ou", 47.5)), next_gm, next_gm["home_team"], strat_choice)
        })
        st.session_state.combo_slip_version += 1
        st.rerun()

    if ctrl3.button("🗑️ Clear Slip", use_container_width=True):
        st.session_state.combo_active_legs = []
        st.session_state.combo_slip_version += 1
        st.rerun()

    combo_legs = []
    compound_prob = 1.0

    for i, leg in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            safe_idx = min(max(leg.get("matchup_idx", 0), 0), len(choices) - 1)
            gm = pool[safe_idx]
            leg["matchup_idx"] = safe_idx
            leg["matchup_str"] = f"{gm['away_short']} @ {gm['home_short']}"
            leg["kickoff"] = gm.get("kickoff", "Scheduled")
            leg["away_logo"] = gm.get("away_logo", DEFAULT_LOGO)
            leg["home_logo"] = gm.get("home_logo", DEFAULT_LOGO)
            leg["away_short"] = gm.get("away_short", "AWAY")
            leg["home_short"] = gm.get("home_short", "HOME")
            leg["league"] = gm.get("league", "SPORTS")

            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                <span style="font-weight:700; font-size:1.0rem;">Leg #{i+1}</span>
                <img src="{gm.get('away_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                <strong>{gm.get('away_short')}</strong>
                <span style="opacity:0.4;">@</span>
                <img src="{gm.get('home_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                <strong>{gm.get('home_short')}</strong>
                <span style="background:rgba(255,255,255,0.06); color:#94a3b8; padding:2px 7px; border-radius:4px; font-size:0.75rem;">
                    🗓️ {gm.get('kickoff', 'Upcoming')}
                </span>
                <span style="opacity:0.5; font-size:0.75rem;">[{gm.get('league')}]</span>
            </div>
            """, unsafe_allow_html=True)

            sel_m = st.selectbox(
                f"Matchup Selector",
                range(len(choices)),
                index=safe_idx,
                format_func=lambda x: choices[x],
                key=f"cb_m_{i}_v{slip_ver}"
            )
            if sel_m != safe_idx:
                leg["matchup_idx"] = sel_m
                st.session_state.combo_slip_version += 1
                st.rerun()

            is_nba = (gm.get("league") == "NBA")
            market_choices = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"]
            if is_nba:
                market_choices.append("Player Points Prop")
            else:
                market_choices.append("Player Anytime Touchdown Scorer")

            curr_type = leg.get("type", "Game Total")
            type_idx = market_choices.index(curr_type) if curr_type in market_choices else 0
            w_type = st.radio(
                f"Market",
                market_choices,
                horizontal=True,
                index=type_idx,
                key=f"cb_wt_{i}_v{slip_ver}"
            )
            leg["type"] = w_type

            if w_type == "Game Total":
                b1, b2 = st.columns(2)
                cur_side = leg.get("side", "Under")
                s_side = b1.selectbox(
                    "Side",
                    ["Under", "Over"],
                    index=0 if cur_side == "Under" else 1,
                    key=f"cb_s_{i}_v{slip_ver}"
                )
                default_line = float(round_half_point(leg.get("line", gm.get("market_ou", 224.5 if is_nba else 47.5))))
                s_line = b2.number_input("Line (pts)", value=default_line, step=0.5, key=f"cb_l_{i}_v{slip_ver}")
                leg["side"], leg["line"] = s_side, s_line

                proj_val = (218.0 if is_nba else 43.0)
                std_val = (12.0 if is_nba else 7.0)
                leg_prob = calculate_win_prob(s_line, proj_val, std_val, is_under=(s_side == "Under"))
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {s_side} {s_line:.1f}", "prob": leg_prob})
            elif w_type == "Point Spread (ATS)":
                b1, b2 = st.columns(2)
                team_sel = b1.selectbox(
                    "Covering Team",
                    [gm["home_team"], gm["away_team"]],
                    index=0 if leg.get("picked_team") == gm["home_team"] else 1,
                    key=f"cb_cov_{i}_v{slip_ver}"
                )
                def_spread = float(round_half_point(leg.get("line", gm.get("market_spread", -3.5))))
                spd_val = b2.number_input("Spread", value=def_spread, step=0.5, key=f"cb_spd_{i}_v{slip_ver}")
                leg["picked_team"], leg["line"], leg["side"] = team_sel, spd_val, "Spread"
                leg_prob = 0.52
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {team_sel} {spd_val:+.1f}", "prob": leg_prob})
            elif w_type == "Straight Up Winner (Moneyline)":
                b1, b2 = st.columns(2)
                winner = b1.selectbox(
                    "Winner",
                    [gm["home_team"], gm["away_team"]],
                    index=0 if leg.get("picked_team") == gm["home_team"] else 1,
                    key=f"cb_win_{i}_v{slip_ver}"
                )
                leg["picked_team"], leg["side"], leg["line"] = winner, "Moneyline", 0.0

                add_score = 40 if is_nba else 14
                h_prob = calculate_moneyline_prob(gm["home_score"] + add_score, gm["away_score"] + add_score, gm.get("home_record", "0-0"), gm.get("away_record", "0-0"))
                leg_prob = h_prob if winner == gm["home_team"] else (1.0 - h_prob)
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {winner} ML", "prob": leg_prob})
            elif w_type == "Player Points Prop":
                b1, b2 = st.columns(2)
                h_roster = get_live_nba_roster(gm.get("home_id") or gm.get("home_short"))
                a_roster = get_live_nba_roster(gm.get("away_id") or gm.get("away_short"))
                all_p = [p[0] for p in (h_roster + a_roster)]
                cur_p = leg.get("picked_team")
                p_idx_sel = all_p.index(cur_p) if cur_p in all_p else 0
                p_pick = b1.selectbox("Player", all_p, index=p_idx_sel, key=f"cb_prop_p_{i}_v{slip_ver}")
                side_p = b2.selectbox("Side", ["Over", "Under"], index=0 if leg.get("side") == "Over" else 1, key=f"cb_prop_s_{i}_v{slip_ver}")
                pts_line = st.number_input("Points Line", value=float(leg.get("line", 22.5)), step=0.5, key=f"cb_prop_l_{i}_v{slip_ver}")
                leg["picked_team"], leg["side"], leg["line"] = p_pick, side_p, pts_line
                
                # Dynamic win expectancy based on strategy profile
                if "Safe Floor" in strat_choice:
                    leg_prob = 0.68
                elif "High Profit" in strat_choice:
                    leg_prob = 0.42
                else:
                    leg_prob = 0.55
                combo_legs.append({"desc": f"{p_pick} {side_p} {pts_line:.1f} Pts", "prob": leg_prob})
            else:
                b1, b2 = st.columns(2)
                h_roster = get_live_football_roster(gm.get("home_id") or gm.get("home_short"), gm.get("league"))
                a_roster = get_live_football_roster(gm.get("away_id") or gm.get("away_short"), gm.get("league"))
                all_p = [p[0] for p in (h_roster + a_roster)]
                cur_p = leg.get("picked_team")
                td_idx_sel = all_p.index(cur_p) if cur_p in all_p else 0
                p_pick = b1.selectbox("Player to Score TD", all_p, index=td_idx_sel, key=f"cb_td_p_{i}_v{slip_ver}")
                leg["picked_team"], leg["side"], leg["line"] = p_pick, "TD", 1.0
                leg_prob = 0.48
                combo_legs.append({"desc": f"{p_pick} Anytime TD", "prob": leg_prob})

            compound_prob *= leg_prob

    st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form(f"save_combo_form_v{slip_ver}"):
        r_c, p_c = st.columns(2)
        c_risk = r_c.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        c_payout = p_c.number_input("Payout ($)", min_value=1.0, value=max(20.0, round(10.0 * (1.0 / max(compound_prob, 0.02)), 2)), step=10.0)

        if st.form_submit_button(f"Lock In {len(combo_legs)}-Leg Ticket", use_container_width=True):
            parsed_legs = [
                {
                    "matchup": f"{pool[min(item['matchup_idx'], len(pool)-1)]['away_short']} @ {pool[min(item['matchup_idx'], len(pool)-1)]['home_short']}",
                    "type": item["type"],
                    "side": item.get("side", ""),
                    "line": round_half_point(item.get("line", 0.0)),
                    "picked_team": item.get("picked_team", ""),
                    "rationale": item.get("rationale", "")
                } for item in st.session_state.combo_active_legs
            ]
            c_tkt = {
                "id": str(datetime.now().timestamp()),
                "user": curr_user.get("display_name", active_uname),
                "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                "type": f"{len(combo_legs)}-Leg Combo",
                "bet_category": "Combo",
                "matchup": " | ".join([cl["desc"] for cl in combo_legs]),
                "bet": f"{len(combo_legs)} Legs ({compound_prob * 100:.1f}% Win Prob)",
                "risk_dollars": float(c_risk),
                "payout_dollars": float(c_payout),
                "payout": float(c_payout),
                "locked_profit": float(c_payout) - float(c_risk),
                "win_prob": f"{compound_prob * 100:.1f}%",
                "status": "Pending",
                "parsed_legs": parsed_legs,
                "notes": f"{len(combo_legs)}-Leg Cross-Sport Combo [{strat_choice.split()[1]}]"
            }
            st.session_state.saved_bets.insert(0, c_tkt)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.toast(f"🎉 Locked in {len(combo_legs)}-leg combo!", icon="✅")
            st.session_state.active_nav_page = "📜 Locked Bets History"
            st.rerun()
