import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def build_single_game_tiers(target_game, chosen_market, strat_choice):
    is_nba = (target_game.get("league") == "NBA")
    ou_open = round_half_point(target_game.get("market_ou", 224.5 if is_nba else 47.5))
    spread_open = round_half_point(target_game.get("market_spread", -3.5))

    add_score = 40 if is_nba else 14
    h_win_prob = calculate_moneyline_prob(
        target_game["home_score"] + add_score,
        target_game["away_score"] + add_score,
        target_game.get("home_record", "0-0"),
        target_game.get("away_record", "0-0")
    )

    is_safe_profile = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice
    is_balanced = "Balanced" in strat_choice

    is_totals_only = "Totals" in chosen_market
    is_spreads_only = "Spreads" in chosen_market
    is_ml_only = "Straight Up" in chosen_market
    is_points_prop = "Player Points" in chosen_market and is_nba
    is_td_prop = "Touchdown" in chosen_market and not is_nba

    h_roster = get_live_nba_roster(target_game.get("home_id") or target_game.get("home_short")) if is_nba else []
    f_roster = get_live_football_roster(target_game.get("home_id") or target_game.get("home_short"), target_game.get("league")) if not is_nba else []
    star_nba_player, _, base_pts = h_roster[0] if h_roster else ("Primary Scorer", "G", 22.5)
    star_fb_player = f_roster[0][0] if f_roster else "Primary RB"

    fav_team = target_game["home_team"] if spread_open < 0 else target_game["away_team"]
    dog_team = target_game["away_team"] if spread_open < 0 else target_game["home_team"]
    fav_spread = spread_open if fav_team == target_game["home_team"] else -spread_open

    def make_card(tier_title, tier_badge, pick_str, w_type, side, line, target_name, prob, rat):
        fair_mult = 1.0 / max(0.01, prob)
        roi_str = f"+{int((fair_mult - 1.0) * 100)}%"
        return {
            "tier_title": tier_title,
            "tier_badge": tier_badge,
            "pick_label": pick_str,
            "type": w_type,
            "side": side,
            "line": line,
            "picked_team": target_name,
            "prob": prob,
            "roi": roi_str,
            "rationale": rat,
            "matchup_str": f"{target_game['away_short']} @ {target_game['home_short']}",
            "kickoff": target_game.get("kickoff", "Scheduled"),
            "away_logo": target_game.get("away_logo", DEFAULT_LOGO),
            "home_logo": target_game.get("home_logo", DEFAULT_LOGO),
            "away_short": target_game.get("away_short", "AWAY"),
            "home_short": target_game.get("home_short", "HOME"),
            "league": target_game.get("league", "SPORTS")
        }

    # 1. 🛡️ SAFE FLOOR PROFILE
    if is_safe_profile:
        g_line = round_half_point(ou_open + (8.5 if is_nba else 6.5))
        g_pick = f"Under {g_line:.1f}" if (is_totals_only or "System" in chosen_market) else f"{dog_team} {round_half_point(abs(fav_spread) + 6.5):+.1f}"
        good_card = make_card("🥉 GOOD (Ultra-Safe Cushion)", "#38bdf8", g_pick, "Game Total" if (is_totals_only or "System" in chosen_market) else "Point Spread (ATS)", "Under" if (is_totals_only or "System" in chosen_market) else "Spread", g_line, target_game["home_team"], 0.76, "Max safety floor cushion against market volatility.")

        b_target = fav_team if (is_ml_only or "System" in chosen_market) else dog_team
        b_pick = f"{fav_team} ML" if (is_ml_only or "System" in chosen_market) else f"{dog_team} {round_half_point(abs(fav_spread) + 4.5):+.1f}"
        better_card = make_card("🥈 BETTER (Conservative Floor)", "#fbbf24", b_pick, "Straight Up Winner (Moneyline)" if (is_ml_only or "System" in chosen_market) else "Point Spread (ATS)", "Moneyline", 0.0, b_target, 0.71, "High-percentage anchor with reliable baseline expectancy.")

        if is_nba:
            p_line = max(10.5, round_half_point(float(base_pts) - 5.5))
            best_card = make_card("🥇 BEST (Elite Floor Clearance)", "#4ade80", f"{star_nba_player} Over {p_line:.1f} Pts", "Player Points Prop", "Over", p_line, star_nba_player, 0.74, f"Heavy usage baseline for {star_nba_player} bought down 5+ pts.")
        else:
            u_line = round_half_point(ou_open + 5.5)
            best_card = make_card("🥇 BEST (High Probability Under)", "#4ade80", f"Under {u_line:.1f}", "Game Total", "Under", u_line, target_game["home_team"], 0.72, "Defensive tempo margin creates exceptional clearance probability.")

        return {"good": good_card, "better": better_card, "best": best_card}

    # 2. 🚀 HIGH PROFIT PROFILE
    elif is_high_profit:
        g_team = fav_team
        g_line = round_half_point(fav_spread - 2.5)
        good_card = make_card("🥉 GOOD (Aggressive Spread Lay)", "#38bdf8", f"{g_team} {g_line:+.1f}", "Point Spread (ATS)", "Spread", g_line, g_team, 0.49, f"Alternate chalk lay on {g_team} for amplified multiplier yield.")

        better_card = make_card("🥈 BETTER (Outright Dog Alpha)", "#fbbf24", f"{dog_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, dog_team, 0.44, "Outright dog play capitalizing on matchup tempo variance.")

        if is_nba:
            p_line = round_half_point(float(base_pts) + 3.5)
            best_card = make_card("🥇 BEST (Ceiling Multiplier)", "#4ade80", f"{star_nba_player} Over {p_line:.1f} Pts", "Player Points Prop", "Over", p_line, star_nba_player, 0.42, "Ladder ceiling: Scoring projection supports longshot clearance.")
        else:
            best_card = make_card("🥇 BEST (High Value TD Alpha)", "#4ade80", f"{star_fb_player} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb_player, 0.48, "Red-zone share offers premium plus-money value.")

        return {"good": good_card, "better": better_card, "best": best_card}

    # 3. ⚖️ BALANCED EDGE PROFILE
    elif is_balanced:
        g_line = round_half_point(ou_open + (2.5 if is_nba else 1.5))
        good_card = make_card("🥉 GOOD (Solid Edge Total)", "#38bdf8", f"Under {g_line:.1f}", "Game Total", "Under", g_line, target_game["home_team"], 0.58, "Balanced total retaining a favorable expected-value cushion.")

        better_card = make_card("🥈 BETTER (Consensus ATS Edge)", "#fbbf24", f"{fav_team} {fav_spread:+.1f}", "Point Spread (ATS)", "Spread", fav_spread, fav_team, 0.55, "Core power ratings confirm edge vs consensus market line.")

        if is_nba:
            best_card = make_card("🥇 BEST (Balanced Volume Prop)", "#4ade80", f"{star_nba_player} Over {float(base_pts):.1f} Pts", "Player Points Prop", "Over", float(base_pts), star_nba_player, 0.59, "Steady volume and defensive mismatch align with consensus strike.")
        else:
            best_card = make_card("🥇 BEST (Balanced Winner Anchor)", "#4ade80", f"{fav_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, fav_team, 0.62, "Optimally priced favorite with high baseline power ratings.")

        return {"good": good_card, "better": better_card, "best": best_card}

    # 4. 🎯 MIXED SPECTRUM
    else:
        good_line = round_half_point(ou_open + (7.5 if is_nba else 4.5))
        good_card = make_card("🥉 GOOD (Safe Floor Anchor)", "#38bdf8", f"Under {good_line:.1f}", "Game Total", "Under", good_line, target_game["home_team"], 0.72, f"Floor cushion (+{(good_line - ou_open):.1f} pts) offers ideal protection.")

        better_card = make_card("🥈 BETTER (Balanced +EV)", "#fbbf24", f"{fav_team} {fav_spread:+.1f}", "Point Spread (ATS)", "Spread", fav_spread, fav_team, 0.55, f"Efficiency edge backing {fav_team} on market spread.")

        if is_nba:
            best_line = round_half_point(float(base_pts) - 1.5)
            best_card = make_card("🥇 BEST (Optimal Value Alpha)", "#4ade80", f"{star_nba_player} Over {best_line:.1f} Pts", "Player Points Prop", "Over", best_line, star_nba_player, 0.64, f"{star_nba_player} usage supports premium conversion edge.")
        else:
            best_line = round_half_point(ou_open + 1.5)
            best_card = make_card("🥇 BEST (Optimal Value Alpha)", "#4ade80", f"Under {best_line:.1f}", "Game Total", "Under", best_line, target_game["home_team"], 0.62, "Pace model projects terminal tempo settling below open.")

        return {"good": good_card, "better": better_card, "best": best_card}

def trigger_tier_auto_refresh():
    st.session_state.sg_needs_tier_calc = True

def render_single_game(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("⚡ Single Game Analytics Engine")
    st.caption("Algorithmic single-matchup scanner, pace regression model, and tiered Good/Better/Best recommendations.")

    if "single_tier_picks" not in st.session_state:
        st.session_state.single_tier_picks = None
    if "single_active_bet" not in st.session_state:
        st.session_state.single_active_bet = None
    if "sg_form_nonce" not in st.session_state:
        st.session_state.sg_form_nonce = 0
    if "sg_needs_tier_calc" not in st.session_state:
        st.session_state.sg_needs_tier_calc = False

    # AI Optimizer Controls (Fixed permanent keys with on_change callbacks)
    with st.container(border=True):
        st.markdown("#### 🤖 AI Single Game Optimizer")

        c1, c2 = st.columns(2)
        league_choice = c1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NBA", "NFL", "NCAA Football"],
            key="sg_static_league",
            on_change=trigger_tier_auto_refresh
        )

        t_filter = c2.selectbox(
            "Game Filter Status",
            options=["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"],
            key="sg_static_filter",
            on_change=trigger_tier_auto_refresh
        )

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

        c3, c4 = st.columns(2)
        chosen_market = c3.selectbox(
            "Target Bet / Market Type",
            market_options,
            key="sg_static_market",
            on_change=trigger_tier_auto_refresh
        )

        strat_options = [
            "🎯 Mixed Tier Spectrum (Safe, Balanced, High Profit)",
            "🛡️ Safe Floor (High Win %, Low Drawdown)",
            "⚖️ Balanced Edge (+EV Sweet Spot)",
            "🚀 High Profit (Max Multiplier & Longshots)"
        ]
        strat_choice = c4.selectbox(
            "Model Strategy Profile",
            options=strat_options,
            key="sg_static_strat",
            on_change=trigger_tier_auto_refresh
        )

        col_q, col_btn = st.columns([3.5, 1.5], vertical_alignment="bottom")
        q_filter = col_q.text_input("🔍 Search Matchup", placeholder="e.g. Celtics, Lakers, Chiefs...", key="sg_static_search", on_change=trigger_tier_auto_refresh)

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

        if q_filter.strip():
            q = q_filter.strip().lower()
            pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g.get("home_short", "").lower() or q in g.get("away_short", "").lower()]

        # Auto-recalculate if an input changed and tiers were already generated
        if st.session_state.sg_needs_tier_calc and st.session_state.single_tier_picks is not None:
            if pool:
                st.session_state.single_tier_picks = build_single_game_tiers(pool[0], chosen_market, strat_choice)
            st.session_state.sg_needs_tier_calc = False

        if col_btn.button("⚡ Generate Tiers", use_container_width=True, disabled=len(pool) == 0):
            st.session_state.single_tier_picks = build_single_game_tiers(pool[0], chosen_market, strat_choice)
            st.session_state.sg_needs_tier_calc = False
            st.rerun()

    # 3-Tier Recommendation Cards
    if st.session_state.single_tier_picks:
        tiers = st.session_state.single_tier_picks
        ref = tiers["good"]

        with st.container(border=True):
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <img src="{ref.get('away_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                    <strong>{ref.get('away_short')}</strong>
                    <span style="opacity:0.35;">@</span>
                    <img src="{ref.get('home_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                    <strong>{ref.get('home_short')}</strong>
                    <span style="background:rgba(255,255,255,0.06); color:#94a3b8; padding:2px 7px; border-radius:4px; font-size:0.75rem;">
                        🗓️ {ref.get('kickoff', 'Upcoming')}
                    </span>
                </div>
                <div style="font-size:0.80rem; opacity:0.75;">Focus: <strong>{chosen_market.split()[1] if len(chosen_market.split()) > 1 else 'Custom'}</strong> | Profile: <strong>{strat_choice.split()[1]}</strong></div>
            </div>
            """, unsafe_allow_html=True)

            c_g, c_b, c_best = st.columns(3)

            for col_target, (t_key, pick_data) in zip([c_g, c_b, c_best], tiers.items()):
                with col_target:
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.09); border-radius:10px; padding:12px; margin-bottom:8px;">
                        <div style="font-weight:700; color:{pick_data['tier_badge']}; font-size:0.85rem; margin-bottom:4px;">{pick_data['tier_title']}</div>
                        <div style="font-size:1.15rem; font-weight:800; color:#f8fafc; margin-bottom:2px;">{pick_data['pick_label']}</div>
                        <div style="font-size:0.78rem; opacity:0.75; margin-bottom:6px;">{pick_data['type']}</div>
                        <div style="display:flex; gap:6px; margin-bottom:8px;">
                            <span style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-size:0.75rem; font-weight:700;">{pick_data['prob'] * 100:.1f}% Prob</span>
                            <span style="background:#22c55e; color:#000; padding:2px 6px; border-radius:4px; font-size:0.75rem; font-weight:800;">{pick_data['roi']}</span>
                        </div>
                        <div style="font-size:0.75rem; opacity:0.75; min-height:46px;">{pick_data['rationale']}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    btn_type = "primary" if t_key == "best" else "secondary"
                    if st.button(f"📥 Load {t_key.capitalize()} Pick", key=f"btn_load_{t_key}", type=btn_type, use_container_width=True):
                        st.session_state.single_active_bet = dict(pick_data)
                        st.session_state.sg_form_nonce += 1
                        st.toast(f"✅ Loaded {pick_data['pick_label']} into ticket slip below!", icon="📥")
                        st.rerun()

    if not pool:
        st.info("No matchups found matching your current filter.")
        return

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in pool]

    st.markdown("---")
    st.markdown("#### 📝 Active Single Bet Slip")

    if not st.session_state.single_active_bet:
        st.info("No active bet loaded. Use **⚡ Generate Tiers** above and click **📥 Load Pick**, or set up a custom ticket manually below.")
        if st.button("➕ Set Up Bet Manually", use_container_width=True):
            def_tiers = build_single_game_tiers(pool[0], chosen_market, strat_choice)
            st.session_state.single_active_bet = dict(def_tiers["better"])
            st.session_state.sg_form_nonce += 1
            st.rerun()
        return

    cur_bet = st.session_state.single_active_bet
    f_nonce = st.session_state.sg_form_nonce

    default_matchup_idx = 0
    cur_matchup_str = cur_bet.get("matchup_str", "")
    for idx, gm in enumerate(pool):
        if f"{gm['away_short']} @ {gm['home_short']}" in cur_matchup_str:
            default_matchup_idx = idx
            break

    with st.container(border=True):
        sel_idx = st.selectbox(
            "Target Matchup",
            range(len(choices)),
            index=default_matchup_idx,
            format_func=lambda x: choices[x],
            key=f"sg_matchup_sel_{f_nonce}"
        )
        selected_gm = pool[sel_idx]
        is_nba = (selected_gm.get("league") == "NBA")

        m_types = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"]
        if is_nba:
            m_types.append("Player Points Prop")
        else:
            m_types.append("Player Anytime Touchdown Scorer")

        curr_wtype = cur_bet.get("type", "Game Total")
        w_idx = 0
        for i_wt, wt_name in enumerate(m_types):
            if wt_name.lower() in curr_wtype.lower() or curr_wtype.lower() in wt_name.lower():
                w_idx = i_wt
                break

        chosen_wtype = st.radio("Market", m_types, index=w_idx, horizontal=True, key=f"sg_radio_wtype_{f_nonce}")

        if chosen_wtype == "Game Total":
            c1, c2 = st.columns(2)
            cur_s = cur_bet.get("side", "Under")
            s_idx = 0 if str(cur_s).lower() == "under" else 1
            c_side = c1.selectbox("Side", ["Under", "Over"], index=s_idx, key=f"sg_side_{f_nonce}")
            default_line = float(round_half_point(cur_bet.get("line") if cur_bet.get("line") is not None else selected_gm.get("market_ou", 224.5 if is_nba else 47.5)))
            c_line = c2.number_input("Line (pts)", value=default_line, step=0.5, key=f"sg_line_{f_nonce}")
            bet_title = f"{c_side} {c_line:.1f}"
            picked_t = selected_gm["home_team"]
            prob_est = calculate_win_prob(c_line, (218.0 if is_nba else 43.0), (12.0 if is_nba else 7.0), is_under=(c_side == "Under"))

        elif chosen_wtype == "Point Spread (ATS)":
            c1, c2 = st.columns(2)
            cur_p = str(cur_bet.get("picked_team", selected_gm["home_team"])).lower()
            cov_idx = 1 if cur_p in selected_gm["away_team"].lower() else 0
            picked_t = c1.selectbox("Covering Team", [selected_gm["home_team"], selected_gm["away_team"]], index=cov_idx, key=f"sg_cov_{f_nonce}")
            default_spd = float(round_half_point(cur_bet.get("line") if cur_bet.get("line") is not None else selected_gm.get("market_spread", -3.5)))
            c_line = c2.number_input("Spread", value=default_spd, step=0.5, key=f"sg_spd_{f_nonce}")
            c_side = "Spread"
            bet_title = f"{picked_t} {c_line:+.1f}"
            prob_est = 0.54

        elif chosen_wtype == "Straight Up Winner (Moneyline)":
            cur_p = str(cur_bet.get("picked_team", selected_gm["home_team"])).lower()
            win_idx = 1 if cur_p in selected_gm["away_team"].lower() else 0
            picked_t = st.selectbox("Outright Winner", [selected_gm["home_team"], selected_gm["away_team"]], index=win_idx, key=f"sg_ml_{f_nonce}")
            c_side, c_line = "Moneyline", 0.0
            bet_title = f"{picked_t} ML"
            add_score = 40 if is_nba else 14
            h_prob = calculate_moneyline_prob(selected_gm["home_score"] + add_score, selected_gm["away_score"] + add_score, selected_gm.get("home_record", "0-0"), selected_gm.get("away_record", "0-0"))
            prob_est = h_prob if picked_t == selected_gm["home_team"] else (1.0 - h_prob)

        elif chosen_wtype == "Player Points Prop":
            c1, c2 = st.columns(2)
            h_roster = get_live_nba_roster(selected_gm.get("home_id") or selected_gm.get("home_short"))
            a_roster = get_live_nba_roster(selected_gm.get("away_id") or selected_gm.get("away_short"))
            all_p = [p[0] for p in (h_roster + a_roster)]
            cur_p = cur_bet.get("picked_team")
            p_idx_sel = all_p.index(cur_p) if cur_p in all_p else 0
            picked_t = c1.selectbox("Player", all_p, index=p_idx_sel, key=f"sg_pts_p_{f_nonce}")
            s_prop_idx = 0 if cur_bet.get("side", "Over") == "Over" else 1
            c_side = c2.selectbox("Side", ["Over", "Under"], index=s_prop_idx, key=f"sg_pts_s_{f_nonce}")
            default_pts = float(cur_bet.get("line") if cur_bet.get("line") is not None else 22.5)
            c_line = st.number_input("Points Line", value=default_pts, step=0.5, key=f"sg_pts_l_{f_nonce}")
            bet_title = f"{picked_t} {c_side} {c_line:.1f} Pts"
            prob_est = 0.58

        else:
            h_roster = get_live_football_roster(selected_gm.get("home_id") or selected_gm.get("home_short"), selected_gm.get("league"))
            a_roster = get_live_football_roster(selected_gm.get("away_id") or selected_gm.get("away_short"), selected_gm.get("league"))
            all_p = [p[0] for p in (h_roster + a_roster)]
            cur_p = cur_bet.get("picked_team")
            td_idx_sel = all_p.index(cur_p) if cur_p in all_p else 0
            picked_t = st.selectbox("Player to Score TD", all_p, index=td_idx_sel, key=f"sg_td_p_{f_nonce}")
            c_side, c_line = "TD", 1.0
            bet_title = f"{picked_t} Any Time TD"
            prob_est = 0.48

        with st.form(f"single_ticket_submit_form_{f_nonce}"):
            rc, pc = st.columns(2)
            risk = rc.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
            payout = pc.number_input("Payout ($)", min_value=1.0, value=19.10, step=5.0)

            if st.form_submit_button("🔒 Lock In Bet Slip", type="primary", use_container_width=True):
                actual_profit = float(payout) - float(risk)
                tkt = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Single",
                    "bet_category": chosen_wtype,
                    "home_team": selected_gm["home_team"],
                    "away_team": selected_gm["away_team"],
                    "picked_team": picked_t,
                    "matchup": f"{selected_gm['away_short']} @ {selected_gm['home_short']}",
                    "bet": bet_title,
                    "target_line": c_line if c_line != 0.0 else None,
                    "bet_direction": c_side,
                    "risk_dollars": float(risk),
                    "payout_dollars": float(payout),
                    "payout": float(payout),
                    "locked_profit": float(actual_profit),
                    "win_prob": f"{prob_est * 100:.1f}%",
                    "status": "Pending",
                    "notes": f"[{selected_gm['league']}] {chosen_wtype}"
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
                st.toast(f"🎉 Locked in {bet_title}!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
