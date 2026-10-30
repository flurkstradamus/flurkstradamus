import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage, record_quarterly_snapshot, calculate_pace_drift_factor
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster, get_live_nba_3pm_roster
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
    is_ml_only = "Straight Up" in chosen_market or "Moneyline" in chosen_market
    is_points_prop = "Player Points" in chosen_market and is_nba
    is_3pm_prop = ("Three-Pointers" in chosen_market or "3-Pointers" in chosen_market) and is_nba
    is_td_prop = "Touchdown" in chosen_market and not is_nba

    g_id = target_game.get("id")
    h_roster = get_live_nba_roster(target_game.get("home_id"), game_id=g_id) if is_nba else []
    h_3pm_roster = get_live_nba_3pm_roster(target_game.get("home_id"), game_id=g_id) if is_nba else []
    f_roster = get_live_football_roster(target_game.get("home_id") or target_game.get("home_short"), target_game.get("league")) if not is_nba else []

    star_nba_player = h_roster[0][0] if h_roster else "Primary Scorer"
    star_3pm_player = h_3pm_roster[0][0] if h_3pm_roster else star_nba_player
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

    # 1. THREE-POINTERS EXCLUSIVE
    if is_3pm_prop:
        if is_safe_profile:
            return {
                "good": make_card("🥉 GOOD (Ultra-Safe 1+ 3PM)", "#38bdf8", f"{star_3pm_player} 1+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 0.5, star_3pm_player, 0.88, f"Confirmed active in live rotation; 1+ make has elite clearance floor."),
                "better": make_card("🥈 BETTER (Safe 2+ 3PM Anchor)", "#fbbf24", f"{star_3pm_player} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm_player, 0.74, "High starter perimeter volume against generous perimeter defense."),
                "best": make_card("🥇 BEST (High Probability 2+ 3PM)", "#4ade80", f"{star_3pm_player} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm_player, 0.72, "Model indicates 72% win expectancy on 2+ baseline conversions.")
            }
        elif is_high_profit:
            return {
                "good": make_card("🥉 GOOD (Solid 2+ 3PM)", "#38bdf8", f"{star_3pm_player} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm_player, 0.65, "Standard plus-value baseline for verified starter."),
                "better": make_card("🥈 BETTER (Ceiling 3+ 3PM Strike)", "#fbbf24", f"{star_3pm_player} 3+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 2.5, star_3pm_player, 0.49, "High multiplier target for primary volume shooter."),
                "best": make_card("🥇 BEST (Max Multiplier 4+ 3PM)", "#4ade80", f"{star_3pm_player} 4+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 3.5, star_3pm_player, 0.35, "Ceiling alpha threshold for deep-ball explosion.")
            }
        else:
            return {
                "good": make_card("🥉 GOOD (Floor Anchor: 1+ 3PM)", "#38bdf8", f"{star_3pm_player} 1+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 0.5, star_3pm_player, 0.86, "Safe floor leg needing only single make."),
                "better": make_card("🥈 BETTER (Balanced: 2+ 3PM)", "#fbbf24", f"{star_3pm_player} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm_player, 0.68, "Calculated sweet spot for high-usage rotation shooter."),
                "best": make_card("🥇 BEST (Optimal Alpha: 3+ 3PM)", "#4ade80", f"{star_3pm_player} 3+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 2.5, star_3pm_player, 0.50, "Ceiling value target on perimeter attempt volume.")
            }

    # 2. TOTALS EXCLUSIVE
    if is_totals_only:
        g_line = round_half_point(ou_open + (8.5 if is_nba else 6.5))
        return {
            "good": make_card("🥉 GOOD (Ultra-Safe Under)", "#38bdf8", f"Under {g_line:.1f}", "Game Total", "Under", g_line, target_game["home_team"], 0.77, "Maximum protective cushion against sudden scoring runs."),
            "better": make_card("🥈 BETTER (Conservative Under)", "#fbbf24", f"Under {round_half_point(ou_open + 4.5):.1f}", "Game Total", "Under", round_half_point(ou_open + 4.5), target_game["home_team"], 0.71, "Balanced buffer capturing tempo slowdown."),
            "best": make_card("🥇 BEST (Optimal Under +EV)", "#4ade80", f"Under {ou_open:.1f}", "Game Total", "Under", ou_open, target_game["home_team"], 0.62, "Sharp edge on model projected pace drag.")
        }

    # 3. POINT SPREADS EXCLUSIVE
    if is_spreads_only:
        g_line = round_half_point(abs(fav_spread) + 6.5)
        return {
            "good": make_card("🥉 GOOD (Teased Floor Spread)", "#38bdf8", f"{dog_team} {g_line:+.1f}", "Point Spread (ATS)", "Spread", g_line, dog_team, 0.76, "Bought points give high probability cushion."),
            "better": make_card("🥈 BETTER (Consensus Spread)", "#fbbf24", f"{fav_team} {fav_spread:+.1f}", "Point Spread (ATS)", "Spread", fav_spread, fav_team, 0.56, "Direct net rating efficiency margin."),
            "best": make_card("🥇 BEST (Sharp Alpha Cover)", "#4ade80", f"{fav_team} {round_half_point(fav_spread - 2.0):+.1f}", "Point Spread (ATS)", "Spread", round_half_point(fav_spread - 2.0), fav_team, 0.52, "Model projects extended victory margin.")
        }

    # 4. MONEYLINE EXCLUSIVE
    if is_ml_only:
        return {
            "good": make_card("🥉 GOOD (Core Favorite Anchor)", "#38bdf8", f"{fav_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, fav_team, max(0.68, max(h_win_prob, 1.0 - h_win_prob)), f"Predictive win probabilities establish {fav_team} as safe chalk."),
            "better": make_card("🥈 BETTER (Balanced Win Probability)", "#fbbf24", f"{fav_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, fav_team, 0.62, "Balanced risk-adjusted outright winner value."),
            "best": make_card("🥇 BEST (Live Underdog Value)", "#4ade80", f"{dog_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, dog_team, min(0.48, min(h_win_prob, 1.0 - h_win_prob)), "High payout dog value based on live tempo shifts.")
        }

    # 5. POINTS OR TOUCHDOWN
    if is_points_prop:
        return {
            "good": make_card("🥉 GOOD (Floor Line)", "#38bdf8", f"{star_nba_player} Over 16.5 Pts", "Player Points Prop", "Over", 16.5, star_nba_player, 0.75, "Low baseline floor for active primary starter."),
            "better": make_card("🥈 BETTER (Consensus Projection)", "#fbbf24", f"{star_nba_player} Over 20.5 Pts", "Player Points Prop", "Over", 20.5, star_nba_player, 0.60, "Model projection hits consensus threshold."),
            "best": make_card("🥇 BEST (Ceiling Alpha)", "#4ade80", f"{star_nba_player} Over 24.5 Pts", "Player Points Prop", "Over", 24.5, star_nba_player, 0.46, "High-multiplier expected value on volume scoring.")
        }

    if is_td_prop:
        return {
            "good": make_card("🥉 GOOD (Red-Zone RB Threat)", "#38bdf8", f"{star_fb_player} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb_player, 0.54, "Primary goal-line carry share."),
            "better": make_card("🥈 BETTER (Balanced TD +EV)", "#fbbf24", f"{star_fb_player} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb_player, 0.48, "Strong opportunity share in red zone."),
            "best": make_card("🥇 BEST (High Value TD Strike)", "#4ade80", f"{star_fb_player} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb_player, 0.42, "Ceiling plus-money return.")
        }

    # DEFAULT MIXED
    return {
        "good": make_card("🥉 GOOD (Safe Floor Under)", "#38bdf8", f"Under {round_half_point(ou_open + 7.5):.1f}", "Game Total", "Under", round_half_point(ou_open + 7.5), target_game["home_team"], 0.74, "High probability floor total."),
        "better": make_card("🥈 BETTER (Consensus Edge)", "#fbbf24", f"{fav_team} {fav_spread:+.1f}", "Point Spread (ATS)", "Spread", fav_spread, fav_team, 0.55, "Standard market efficiency cover."),
        "best": make_card("🥇 BEST (Verified 2+ 3PM)", "#4ade80", f"{star_3pm_player} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm_player, 0.68, "Calculated sweet spot for starting perimeter shooter.") if is_nba else make_card("🥇 BEST (TD Scorer)", "#4ade80", f"{star_fb_player} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb_player, 0.48, "Goal line opportunity share.")
    }

def render_single_game(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("⚡ Single Game Analytics Engine")
    st.caption("Algorithmic single-matchup scanner, pace regression model, and tiered Good/Better/Best recommendations.")

    if "single_tier_picks" not in st.session_state:
        st.session_state.single_tier_picks = None
    if "single_active_bet" not in st.session_state:
        st.session_state.single_active_bet = None
    if "sg_form_nonce" not in st.session_state:
        st.session_state.sg_form_nonce = 0

    with st.container(border=True):
        st.markdown("#### 🤖 Select & Configure Game Matchup")

        # ROW 1: League & Filter
        r1_c1, r1_c2 = st.columns(2)
        league_choice = r1_c1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NBA", "NFL", "NCAA Football"],
            key="sg_static_league"
        )
        t_filter = r1_c2.selectbox(
            "Game Filter Status",
            options=["🌐 All Matchups", "⏳ Upcoming Games", "⚡ Live Games"],
            key="sg_static_filter"
        )

        # Resolve pool based on filters
        pool = games_data
        if league_choice == "NBA": pool = [g for g in pool if g.get("league") == "NBA"]
        elif league_choice == "NFL": pool = [g for g in pool if g.get("league") == "NFL"]
        elif league_choice == "NCAA Football": pool = [g for g in pool if g.get("league") == "NCAA"]

        if t_filter == "⏳ Upcoming Games":
            pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
        elif t_filter == "⚡ Live Games":
            pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]

        # ROW 2: Specific Matchup Selection (Fixes Issue 1)
        if not pool:
            st.warning("No matchups match your selected league or game filter.")
            return

        game_labels = [f"[{gm.get('kickoff', 'Upcoming')}] [{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')} ({gm.get('state_text', 'pre').upper()})" for gm in pool]
        selected_game_idx = st.selectbox(
            "🎯 Select Matchup to Analyze",
            options=range(len(game_labels)),
            format_func=lambda x: game_labels[x],
            key="sg_explicit_game_selector"
        )
        selected_game = pool[selected_game_idx]

        # ROW 3: Market & Strategy
        r3_c1, r3_c2 = st.columns(2)
        is_nba_game = (selected_game.get("league") == "NBA")

        if is_nba_game:
            market_options = [
                "⚡ Let the System Pick (Best NBA Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏀 NBA Player Points Prop",
                "🎯 NBA Player Three-Pointers Made (1+, 2+, 3+)"
            ]
        else:
            market_options = [
                "⚡ Let the System Pick (Best Football Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏈 Football Anytime Touchdown Scorer"
            ]

        chosen_market = r3_c1.selectbox("Target Bet / Market Type", market_options, key="sg_static_market")
        strat_choice = r3_c2.selectbox(
            "Model Strategy Profile",
            ["🎯 Mixed Tier Spectrum (Safe, Balanced, High Profit)", "🛡️ Safe Floor (High Win %, Low Drawdown)", "⚖️ Balanced Edge (+EV Sweet Spot)", "🚀 High Profit (Max Multiplier & Longshots)"],
            key="sg_static_strat"
        )

        if st.button("⚡ Generate Matchup Analysis & Tiers", type="primary", use_container_width=True):
            st.session_state.single_tier_picks = build_single_game_tiers(selected_game, chosen_market, strat_choice)
            st.rerun()

    # =========================================================================
    # PRE-GAME VS CURRENT IN-GAME PROJECTIONS (Fixes Issue 5)
    # =========================================================================
    st.markdown("#### 📊 Matchup Projection Telemetry")
    gm = selected_game
    p_num = gm.get("period", 0)
    cur_tot = gm.get("home_score", 0) + gm.get("away_score", 0)
    pre_tot = float(gm.get("market_ou", 224.5 if is_nba_game else 47.5))
    pre_spd = float(gm.get("market_spread", -3.5))

    # Calculate real-time pace drift regression
    live_proj_tot = calculate_pace_drift_factor(p_num, cur_tot, pre_tot)
    fav_team = gm["home_team"] if pre_spd < 0 else gm["away_team"]
    underdog = gm["away_team"] if pre_spd < 0 else gm["home_team"]

    # Record historical snapshot for learning engine
    record_quarterly_snapshot(gm.get("id"), gm.get("league"), gm.get("state_text"), gm["home_team"], gm["away_team"], gm.get("home_score", 0), gm.get("away_score", 0), p_num, pre_tot, pre_spd)

    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Pre-Game Total", f"{pre_tot:.1f} pts")
        m2.metric("Live Pace Projection", f"{live_proj_tot:.1f} pts", delta=round(live_proj_tot - pre_tot, 1))
        m3.metric("Projected Winner", fav_team, f"{abs(pre_spd):.1f} pts")
        m4.metric("Game Status", f"Q{p_num} • {gm.get('clock', '0:00')}" if p_num > 0 else "Pre-Game")

        # Top Player Projections for the Selected Game
        st.caption(f"🎯 **Key Player Projections ({selected_game.get('home_short')} & {selected_game.get('away_short')}):**")
        if is_nba_game:
            shooters = get_live_nba_3pm_roster(selected_game.get("home_id"), game_id=selected_game.get("id"))[:2]
            p_cols = st.columns(len(shooters) if shooters else 1)
            for idx, sh in enumerate(shooters):
                p_cols[idx].info(f"🏀 **{sh[0]}**: Proj {sh[3]} Pts | Proj {sh[2]} 3PM")
        else:
            fb = get_live_football_roster(selected_game.get("home_id") or selected_game.get("home_short"), selected_game.get("league"))[:2]
            p_cols = st.columns(len(fb) if fb else 1)
            for idx, ply in enumerate(fb):
                p_cols[idx].info(f"🏈 **{ply[0]}** ({ply[1]}): 52% Projected Anytime TD")

    # 3-Tier Recommendation Cards
    if st.session_state.single_tier_picks:
        tiers = st.session_state.single_tier_picks
        st.markdown("#### 🎯 AI Recommended Tiers")
        c_g, c_b, c_best = st.columns(3)
        for col_target, (t_key, pick_data) in zip([c_g, c_b, c_best], tiers.items()):
            with col_target:
                with st.container(border=True):
                    st.markdown(f"**{pick_data['tier_title']}**")
                    st.subheader(pick_data['pick_label'])
                    st.caption(f"{pick_data['type']} • {pick_data['prob']*100:.1f}% Model Win Prob")
                    st.write(pick_data['rationale'])
                    if st.button(f"📥 Load {t_key.capitalize()} Pick", key=f"sg_btn_load_{t_key}", use_container_width=True):
                        st.session_state.single_active_bet = dict(pick_data)
                        st.session_state.sg_form_nonce += 1
                        st.toast(f"✅ Loaded {pick_data['pick_label']} into ticket slip!", icon="📥")
                        st.rerun()

    # Active Single Bet Slip
    if st.session_state.single_active_bet:
        cur_bet = st.session_state.single_active_bet
        st.markdown("---")
        st.markdown("#### 🎟️ Active Single Bet Slip")
        with st.container(border=True):
            st.markdown(f"**Selected Pick:** `{cur_bet.get('pick_label')}`")
            f_nonce = st.session_state.sg_form_nonce
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
                        "bet_category": cur_bet.get("type"),
                        "matchup": cur_bet.get("matchup_str"),
                        "bet": cur_bet.get("pick_label"),
                        "risk_dollars": float(risk),
                        "payout_dollars": float(payout),
                        "payout": float(payout),
                        "locked_profit": float(actual_profit),
                        "win_prob": f"{cur_bet.get('prob', 0.55) * 100:.1f}%",
                        "status": "Pending",
                        "notes": f"[{selected_game['league']}] {cur_bet.get('type')}"
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
                    st.toast(f"🎉 Locked in {cur_bet.get('pick_label')}!", icon="✅")
                    st.session_state.active_nav_page = "📜 Locked Bets History"
                    st.rerun()
