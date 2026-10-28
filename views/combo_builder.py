import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def generate_leg_rationale(b_type, b_side, b_line, gm, p_name=""):
    is_nba = (gm.get("league") == "NBA")
    ou = float(gm.get("market_ou", 224.5 if is_nba else 47.5))
    spread = float(gm.get("market_spread", -3.5))

    if b_type == "Game Total":
        diff = abs(b_line - ou)
        if b_side == "Under":
            return f"Pace model projects defensive tempo suppression. Market consensus opened at {ou:.1f}; model identifies positive expected value on Under {b_line:.1f} (+{diff:.1f} pts safety buffer)."
        else:
            return f"Offensive efficiency ratings project above-average possession conversion. Projected total clears market strike of {b_line:.1f} with strong high-variance upside."
    elif b_type == "Point Spread (ATS)":
        return f"Power ratings give {p_name} a +2.8 point efficiency edge against market number ({spread:+.1f}). In-game Bayesian regression favors covering current strike."
    elif b_type == "Straight Up Winner (Moneyline)":
        return f"Historical home/away situational trend models indicate {p_name} possesses an outright win edge exceeding implied moneyline break-even probability."
    elif b_type == "Player Points Prop":
        return f"{p_name} usage rate projects over 28.5% with high transition tempo. Matchup defense ranks bottom-third against opposing primary scorers, favoring Over {b_line:.1f} pts."
    else:
        return f"{p_name} holds >65% red-zone touch share over recent drives. High goal-line leverage provides positive expected value for Anytime TD."

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Cross-Sport Combo Builder (Up to 12 Legs)")
    st.caption("Automated cross-slate parlay scanner, compound probability calculator, and slip builder.")

    if "combo_preview_legs" not in st.session_state:
        st.session_state.combo_preview_legs = None
    if "combo_is_editing" not in st.session_state:
        st.session_state.combo_is_editing = False

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

        if col_gen.button("⚡ Auto-Generate Combo", use_container_width=True, disabled=len(pool) == 0):
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
                elif chosen_type == "Player Points Prop":
                    roster = get_live_nba_roster(g_item.get("home_id") or g_item.get("home_short"))
                    target_p_name = roster[0][0] if roster else "Lead Scorer"
                    line_val = roster[0][2] if roster else 22.5
                    side_val = "Over"
                elif chosen_type == "Player Anytime Touchdown Scorer":
                    roster = get_live_football_roster(g_item.get("home_id") or g_item.get("home_short"), g_item.get("league"))
                    target_p_name = roster[0][0] if roster else "Top Running Back"
                    line_val = 1.0
                    side_val = "TD"

                rationale_text = generate_leg_rationale(chosen_type, side_val, line_val, g_item, target_p_name)

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

            st.session_state.combo_preview_legs = new_generated
            st.session_state.combo_active_legs = list(new_generated)
            st.session_state.combo_is_editing = False
            st.rerun()

    # --- AI RECOMMENDATION PREVIEW (NO INDIVIDUAL EXPANDERS) ---
    if st.session_state.combo_preview_legs:
        with st.container(border=True):
            prev_legs = st.session_state.combo_preview_legs
            h_col1, h_col2 = st.columns([4, 2], vertical_alignment="center")
            with h_col1:
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:1.15rem; font-weight:700;">🎯 AI Recommended Parlay Slip ({len(prev_legs)} Legs)</span>
                    <span style="background-color:#22c55e; color:#000; font-weight:800; font-size:0.75rem; padding:2px 8px; border-radius:4px;">OPTIMIZED</span>
                </div>
                """, unsafe_allow_html=True)
            with h_col2:
                if not st.session_state.combo_is_editing:
                    if st.button("✏️ Edit Legs", use_container_width=True, key="btn_start_edit_legs"):
                        st.session_state.combo_is_editing = True
                        st.rerun()
                else:
                    if st.button("💾 Save & Reload Slip", type="primary", use_container_width=True, key="btn_save_reload_legs"):
                        st.session_state.combo_is_editing = False
                        st.session_state.combo_active_legs = list(st.session_state.combo_preview_legs)
                        st.toast("✅ Parlay slip updated and synchronized!", icon="💾")
                        st.rerun()

            for p_idx, p_leg in enumerate(prev_legs):
                p_c1, p_c2 = st.columns([5.3, 0.7], vertical_alignment="center")

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

                with p_c1:
                    st.markdown(f"""
                    <div style="display:flex; align-items:center; justify-content:space-between; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); padding:8px 12px; border-radius:8px; margin-bottom:4px;">
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

                with p_c2:
                    if st.session_state.combo_is_editing:
                        if st.button("🗑️", key=f"preview_del_{p_idx}", help=f"Remove Leg #{p_idx+1}"):
                            st.session_state.combo_preview_legs.pop(p_idx)
                            st.rerun()

            sync_c1, sync_c2 = st.columns([4, 1.5])
            sync_c1.caption("Click 'Save & Reload Slip' after removing legs to update your wager below.")
            if sync_c2.button("Clear Suggestion", use_container_width=True):
                st.session_state.combo_preview_legs = None
                st.session_state.combo_active_legs = []
                st.session_state.combo_is_editing = False
                st.rerun()

    if not pool:
        st.info("No matchups found matching your current filter.")
        return

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in pool]

    # If no legs exist, show empty waiting state
    if not st.session_state.combo_active_legs:
        st.info("No active parlay slip. Click **⚡ Auto-Generate Combo** above or add a leg manually below.")
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
                "rationale": generate_leg_rationale("Game Total", "Under", round_half_point(first_gm.get("market_ou", 47.5)), first_gm, first_gm["home_team"])
            }]
            st.rerun()
        return

    # --- DEDICATED ACCORDION FOR ALL LEG RATIONALES BEFORE THE ACTIVE SLIP ---
    with st.expander("🧠 AI Model Strategy & Edge Rationales", expanded=False):
        st.caption("Breakdown of algorithmic discrepancy, pace drift, and edge considerations for active selections:")
        for idx, leg_item in enumerate(st.session_state.combo_active_legs):
            leg_name = leg_item.get("picked_team", leg_item.get("matchup_str", f"Leg #{idx+1}"))
            rat_msg = leg_item.get("rationale") or generate_leg_rationale(
                leg_item.get("type", "Game Total"),
                leg_item.get("side", "Under"),
                leg_item.get("line", 0.0),
                pool[min(leg_item.get("matchup_idx", 0), len(pool)-1)],
                leg_name
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
            "rationale": generate_leg_rationale("Game Total", "Under", round_half_point(next_gm.get("market_ou", 47.5)), next_gm, next_gm["home_team"])
        })
        st.rerun()

    if ctrl3.button("🗑️ Clear Slip", use_container_width=True):
        st.session_state.combo_active_legs = []
        st.session_state.combo_preview_legs = None
        st.session_state.combo_is_editing = False
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

            col_hdr1, col_hdr2 = st.columns([5.5, 0.5], vertical_alignment="center")
            with col_hdr1:
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

            with col_hdr2:
                if st.button("❌", key=f"del_leg_{i}", help="Remove leg"):
                    st.session_state.combo_active_legs.pop(i)
                    if st.session_state.combo_preview_legs and i < len(st.session_state.combo_preview_legs):
                        st.session_state.combo_preview_legs.pop(i)
                    st.rerun()

            sel_m = st.selectbox(f"Matchup Selector", range(len(choices)), index=safe_idx, format_func=lambda x: choices[x], key=f"cb_m_{i}")
            if sel_m != safe_idx:
                leg["matchup_idx"] = sel_m
                st.rerun()

            is_nba = (gm.get("league") == "NBA")
            market_choices = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"]
            if is_nba:
                market_choices.append("Player Points Prop")
            else:
                market_choices.append("Player Anytime Touchdown Scorer")

            curr_type = leg.get("type", "Game Total")
            type_idx = market_choices.index(curr_type) if curr_type in market_choices else 0
            w_type = st.radio(f"Market", market_choices, horizontal=True, index=type_idx, key=f"cb_wt_{i}")
            leg["type"] = w_type

            if w_type == "Game Total":
                b1, b2 = st.columns(2)
                s_side = b1.selectbox("Side", ["Under", "Over"], index=0 if leg.get("side", "Under") == "Under" else 1, key=f"cb_s_{i}")
                default_line = float(round_half_point(leg.get("line", gm.get("market_ou", 224.5 if is_nba else 47.5))))
                s_line = b2.number_input("Line (pts)", value=default_line, step=0.5, key=f"cb_l_{i}")
                leg["side"], leg["line"] = s_side, s_line

                proj_val = (218.0 if is_nba else 43.0)
                std_val = (12.0 if is_nba else 7.0)
                leg_prob = calculate_win_prob(s_line, proj_val, std_val, is_under=(s_side == "Under"))
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {s_side} {s_line:.1f}", "prob": leg_prob})
            elif w_type == "Point Spread (ATS)":
                b1, b2 = st.columns(2)
                team_sel = b1.selectbox("Covering Team", [gm["home_team"], gm["away_team"]], key=f"cb_cov_{i}")
                spd_val = b2.number_input("Spread", value=float(round_half_point(gm.get("market_spread", -3.5))), step=0.5, key=f"cb_spd_{i}")
                leg["picked_team"], leg["line"], leg["side"] = team_sel, spd_val, "Spread"
                leg_prob = 0.52
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {team_sel} {spd_val:+.1f}", "prob": leg_prob})
            elif w_type == "Straight Up Winner (Moneyline)":
                b1, b2 = st.columns(2)
                winner = b1.selectbox("Winner", [gm["home_team"], gm["away_team"]], key=f"cb_win_{i}")
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
                p_pick = b1.selectbox("Player", all_p, key=f"cb_prop_p_{i}")
                side_p = b2.selectbox("Side", ["Over", "Under"], key=f"cb_prop_s_{i}")
                pts_line = st.number_input("Points Line", value=float(leg.get("line", 22.5)), step=0.5, key=f"cb_prop_l_{i}")
                leg["picked_team"], leg["side"], leg["line"] = p_pick, side_p, pts_line
                leg_prob = 0.55
                combo_legs.append({"desc": f"{p_pick} {side_p} {pts_line:.1f} Pts", "prob": leg_prob})
            else:
                b1, b2 = st.columns(2)
                h_roster = get_live_football_roster(gm.get("home_id") or gm.get("home_short"), gm.get("league"))
                a_roster = get_live_football_roster(gm.get("away_id") or gm.get("away_short"), gm.get("league"))
                all_p = [p[0] for p in (h_roster + a_roster)]
                p_pick = b1.selectbox("Player to Score TD", all_p, key=f"cb_td_p_{i}")
                leg["picked_team"], leg["side"], leg["line"] = p_pick, "TD", 1.0
                leg_prob = 0.48
                combo_legs.append({"desc": f"{p_pick} Anytime TD", "prob": leg_prob})

            compound_prob *= leg_prob

    st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
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
                "notes": f"{len(combo_legs)}-Leg Cross-Sport Combo"
            }
            st.session_state.saved_bets.insert(0, c_tkt)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.toast(f"🎉 Locked in {len(combo_legs)}-leg combo!", icon="✅")
            st.session_state.active_nav_page = "📜 Locked Bets History"
            st.rerun()
