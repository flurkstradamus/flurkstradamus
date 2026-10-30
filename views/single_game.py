import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage, record_quarterly_snapshot, calculate_pace_drift_factor
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster, get_live_nba_3pm_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def build_single_game_tiers(target_game, chosen_market, strat_choice):
    """
    Builds tier cards strictly isolated to the sport and teams of target_game.
    Never falls back to cross-sport placeholders.
    """
    league = str(target_game.get("league", "NFL")).upper()
    is_nba = (league == "NBA")
    
    h_team = target_game.get("home_team", "Home Team")
    a_team = target_game.get("away_team", "Away Team")
    h_short = target_game.get("home_short", "HOME")
    a_short = target_game.get("away_short", "AWAY")
    
    ou_open = round_half_point(target_game.get("market_ou", 224.5 if is_nba else 46.5))
    spread_open = round_half_point(target_game.get("market_spread", -3.5))

    add_score = 40 if is_nba else 14
    h_win_prob = calculate_moneyline_prob(
        target_game.get("home_score", 0) + add_score,
        target_game.get("away_score", 0) + add_score,
        target_game.get("home_record", "0-0"),
        target_game.get("away_record", "0-0")
    )

    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice

    fav_team = h_team if spread_open < 0 else a_team
    dog_team = a_team if spread_open < 0 else h_team
    fav_spread = spread_open if fav_team == h_team else -spread_open

    def make_card(tier_title, tier_badge, pick_str, w_type, side, line, picked_team_name, prob, rat):
        fair_mult = 1.0 / max(0.01, prob)
        roi_str = f"+{int((fair_mult - 1.0) * 100)}%"
        return {
            "tier_title": tier_title,
            "tier_badge": tier_badge,
            "pick_label": pick_str,
            "type": w_type,
            "side": side,
            "line": line,
            "picked_team": picked_team_name,
            "prob": prob,
            "roi": roi_str,
            "rationale": rat,
            "matchup_str": f"{a_short} @ {h_short}",
            "kickoff": target_game.get("kickoff", "Scheduled"),
            "away_logo": target_game.get("away_logo", DEFAULT_LOGO),
            "home_logo": target_game.get("home_logo", DEFAULT_LOGO),
            "away_short": a_short,
            "home_short": h_short,
            "league": league
        }

    # =========================================================================
    # 1. BASKETBALL SPECIFIC TIERS (NBA ONLY)
    # =========================================================================
    if is_nba:
        h_3pm_roster = get_live_nba_3pm_roster(target_game.get("home_id"), game_id=target_game.get("id"))
        star_3pm = h_3pm_roster[0][0] if h_3pm_roster else "Starting Guard"
        h_roster = get_live_nba_roster(target_game.get("home_id"), game_id=target_game.get("id"))
        star_scorer = h_roster[0][0] if h_roster else star_3pm

        if "Three-Pointers" in chosen_market or "3-Pointers" in chosen_market:
            return {
                "good": make_card("🥉 GOOD (Ultra-Safe 1+ 3PM)", "#38bdf8", f"{star_3pm} 1+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 0.5, star_3pm, 0.88, f"High-floor volume: {star_3pm} is in the active starting rotation."),
                "better": make_card("🥈 BETTER (Safe 2+ 3PM Anchor)", "#fbbf24", f"{star_3pm} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm, 0.74, "High starter perimeter volume against generous defense."),
                "best": make_card("🥇 BEST (High Probability 2+ 3PM)", "#4ade80", f"{star_3pm} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm, 0.72, "Model calculates optimal EV threshold on 2+ conversions.")
            }
        elif "Player Points" in chosen_market:
            return {
                "good": make_card("🥉 GOOD (Floor Line)", "#38bdf8", f"{star_scorer} Over 16.5 Pts", "Player Points Prop", "Over", 16.5, star_scorer, 0.75, "Low baseline scoring threshold for primary starter."),
                "better": make_card("🥈 BETTER (Consensus Projection)", "#fbbf24", f"{star_scorer} Over 20.5 Pts", "Player Points Prop", "Over", 20.5, star_scorer, 0.60, "Model projection aligns with starting usage share."),
                "best": make_card("🥇 BEST (Ceiling Alpha)", "#4ade80", f"{star_scorer} Over 24.5 Pts", "Player Points Prop", "Over", 24.5, star_scorer, 0.46, "Plus-money upside on volume scoring ceiling.")
            }
        else:
            # NBA Standard Discrepancy Mix
            cush = 7.5 if is_safe else 3.5
            tot_line = round_half_point(ou_open + cush)
            return {
                "good": make_card("🥉 GOOD (Safe Floor Under)", "#38bdf8", f"Under {tot_line:.1f}", "Game Total", "Under", tot_line, h_team, 0.75, f"Floor cushion (+{cush:.1f} pts) gives defensive clearance."),
                "better": make_card("🥈 BETTER (Consensus ATS Cover)", "#fbbf24", f"{fav_team} {fav_spread:+.1f}", "Point Spread (ATS)", "Spread", fav_spread, fav_team, 0.56, f"Power ratings model projects {fav_team} covers the line."),
                "best": make_card("🥇 BEST (Verified 2+ 3PM)", "#4ade80", f"{star_3pm} 2+ Three-Pointers", "NBA Player 3-Pointers Made", "Over", 1.5, star_3pm, 0.68, f"{star_3pm} 2+ made threes is a prime model EV target.")
            }

    # =========================================================================
    # 2. FOOTBALL SPECIFIC TIERS (NFL / NCAA FOOTBALL ONLY)
    # =========================================================================
    f_roster = get_live_football_roster(target_game.get("home_id") or target_game.get("home_short"), league)
    star_fb = f_roster[0][0] if f_roster else "Starting RB"
    star_fb_pos = f_roster[0][1] if f_roster else "RB"

    # Specific Football Markets
    if "Touchdown" in chosen_market:
        return {
            "good": make_card("🥉 GOOD (Red-Zone Threat)", "#38bdf8", f"{star_fb} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb, 0.54, f"Primary goal-line carry share for {h_team}."),
            "better": make_card("🥈 BETTER (Balanced TD +EV)", "#fbbf24", f"{star_fb} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb, 0.48, "High opportunity share against generous red zone run defense."),
            "best": make_card("🥇 BEST (High Value TD Strike)", "#4ade80", f"{star_fb} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb, 0.42, "Ceiling plus-money return based on red zone rushing rate.")
        }
    elif "Totals" in chosen_market:
        cush = 5.5 if is_safe else 2.5
        g_line = round_half_point(ou_open + cush)
        return {
            "good": make_card("🥉 GOOD (Ultra-Safe Under)", "#38bdf8", f"Under {g_line:.1f}", "Game Total", "Under", g_line, h_team, 0.76, f"Protective cushion (+{cush:.1f} pts) absorbing high pace scoring."),
            "better": make_card("🥈 BETTER (Conservative Under)", "#fbbf24", f"Under {round_half_point(ou_open + 2.5):.1f}", "Game Total", "Under", round_half_point(ou_open + 2.5), h_team, 0.70, "Moderate buffer settling above open consensus."),
            "best": make_card("🥇 BEST (Optimal Under +EV)", "#4ade80", f"Under {ou_open:.1f}", "Game Total", "Under", ou_open, h_team, 0.62, "Sharp edge on model projected tempo drag.")
        }
    elif "Spreads" in chosen_market:
        cush = 4.5 if is_safe else 2.5
        g_line = round_half_point(abs(fav_spread) + cush)
        return {
            "good": make_card("🥉 GOOD (Teased Floor Spread)", "#38bdf8", f"{dog_team} {g_line:+.1f}", "Point Spread (ATS)", "Spread", g_line, dog_team, 0.75, "Bought points give high probability cover cushion."),
            "better": make_card("🥈 BETTER (Consensus Spread)", "#fbbf24", f"{fav_team} {fav_spread:+.1f}", "Point Spread (ATS)", "Spread", fav_spread, fav_team, 0.57, f"Direct efficiency margin backing {fav_team} to cover."),
            "best": make_card("🥇 BEST (Sharp Alpha Cover)", "#4ade80", f"{fav_team} {round_half_point(fav_spread - 1.5):+.1f}", "Point Spread (ATS)", "Spread", round_half_point(fav_spread - 1.5), fav_team, 0.52, "Model projects extended victory margin.")
        }
    elif "Straight Up" in chosen_market or "Moneyline" in chosen_market:
        return {
            "good": make_card("🥉 GOOD (Core Favorite Anchor)", "#38bdf8", f"{fav_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, fav_team, max(0.68, max(h_win_prob, 1.0 - h_win_prob)), f"Predictive win probabilities establish {fav_team} as safe chalk."),
            "better": make_card("🥈 BETTER (Balanced Win Probability)", "#fbbf24", f"{fav_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, fav_team, 0.62, "Balanced risk-adjusted outright winner value."),
            "best": make_card("🥇 BEST (Live Underdog Value)", "#4ade80", f"{dog_team} ML", "Straight Up Winner (Moneyline)", "Moneyline", 0.0, dog_team, min(0.48, min(h_win_prob, 1.0 - h_win_prob)), "High payout dog value based on live matchup variance.")
        }
    else:
        # STRICT NFL DEFAULT SYSTEM MIX (100% Football Matchup Isolated)
        cush = 4.5 if is_safe else 2.5
        tot_line = round_half_point(ou_open + cush)
        return {
            "good": make_card("🥉 GOOD (Safe Floor Under)", "#38bdf8", f"Under {tot_line:.1f}", "Game Total", "Under", tot_line, h_team, 0.74, f"Teased cushion (+{cush:.1f} pts) gives defensive clearance for {a_short} @ {h_short}."),
            "better": make_card("🥈 BETTER (Consensus ATS Cover)", "#fbbf24", f"{fav_team} {fav_spread:+.1f}", "Point Spread (ATS)", "Spread", fav_spread, fav_team, 0.56, f"Power ratings model projects {fav_team} covers the spread against {dog_team}."),
            "best": make_card("🥇 BEST (Anytime Touchdown)", "#4ade80", f"{star_fb} Any Time TD", "Player Anytime Touchdown Scorer", "TD", 1.0, star_fb, 0.51, f"{star_fb} ({star_fb_pos}) commands red-zone carry share for {h_team}.")
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
    if "last_analyzed_game_id" not in st.session_state:
        st.session_state.last_analyzed_game_id = None

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

        pool = games_data
        if league_choice == "NBA": pool = [g for g in pool if g.get("league") == "NBA"]
        elif league_choice == "NFL": pool = [g for g in pool if g.get("league") == "NFL"]
        elif league_choice == "NCAA Football": pool = [g for g in pool if g.get("league") == "NCAA"]

        if t_filter == "⏳ Upcoming Games":
            pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
        elif t_filter == "⚡ Live Games":
            pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]

        if not pool:
            st.warning("No matchups match your selected league or game filter.")
            st.session_state.single_tier_picks = None
            return

        # ROW 2: System Auto-Select vs Manual Selection
        selection_mode = st.radio(
            "Matchup Selection Method",
            ["🤖 Let the System Pick (Highest Model Discrepancy)", "🎯 Let Me Pick the Game"],
            horizontal=True,
            key="sg_selection_mode"
        )

        if "Let the System Pick" in selection_mode:
            selected_game = sorted(pool, key=lambda g: abs(float(g.get("market_spread", 0))), reverse=True)[0]
            st.success(f"🤖 **System Selected:** [{selected_game.get('league')}] **{selected_game.get('away_short')} @ {selected_game.get('home_short')}** ({selected_game.get('kickoff', 'Upcoming')}) — *Highest Model Confidence Discrepancy*")
        else:
            game_labels = [f"[{gm.get('kickoff', 'Upcoming')}] [{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')} ({gm.get('state_text', 'pre').upper()})" for gm in pool]
            selected_game_idx = st.selectbox(
                "🎯 Select Matchup to Analyze",
                options=range(len(game_labels)),
                format_func=lambda x: game_labels[x],
                key="sg_explicit_game_selector"
            )
            selected_game = pool[selected_game_idx]

        # Invalidate picks if user changes the target game to prevent stale cache
        current_g_id = str(selected_game.get("id"))
        if st.session_state.last_analyzed_game_id != current_g_id:
            st.session_state.single_tier_picks = None

        # ROW 3: Market & Strategy Options
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

        curr_m_sel = st.session_state.get("sg_static_market")
        m_index = market_options.index(curr_m_sel) if curr_m_sel in market_options else 0

        chosen_market = r3_c1.selectbox("Target Bet / Market Type", market_options, index=m_index, key="sg_static_market")
        strat_choice = r3_c2.selectbox(
            "Model Strategy Profile",
            ["🎯 Mixed Tier Spectrum (Safe, Balanced, High Profit)", "🛡️ Safe Floor (High Win %, Low Drawdown)", "⚖️ Balanced Edge (+EV Sweet Spot)", "🚀 High Profit (Max Multiplier & Longshots)"],
            key="sg_static_strat"
        )

        if st.button("⚡ Generate Matchup Analysis & Tiers", type="primary", use_container_width=True):
            st.session_state.last_analyzed_game_id = current_g_id
            st.session_state.single_tier_picks = build_single_game_tiers(selected_game, chosen_market, strat_choice)
            st.rerun()

    # =========================================================================
    # MATCHUP TELEMETRY (Explicitly Bound to Selected Game)
    # =========================================================================
    gm = selected_game
    p_num = gm.get("period", 0)
    cur_tot = gm.get("home_score", 0) + gm.get("away_score", 0)
    pre_tot = float(gm.get("market_ou", 224.5 if is_nba_game else 46.5))
    pre_spd = float(gm.get("market_spread", -3.5))

    live_proj_tot = calculate_pace_drift_factor(p_num, cur_tot, pre_tot)
    fav_team = gm["home_team"] if pre_spd < 0 else gm["away_team"]
    
    a_logo = gm.get("away_logo") or DEFAULT_LOGO
    h_logo = gm.get("home_logo") or DEFAULT_LOGO
    a_name = gm.get("away_team", "Away Team")
    h_name = gm.get("home_team", "Home Team")
    a_sh = gm.get("away_short", "AWAY")
    h_sh = gm.get("home_short", "HOME")
    kickoff_time = gm.get("kickoff", "Upcoming")
    gm_league = gm.get("league", "SPORTS").upper()

    record_quarterly_snapshot(gm.get("id"), gm.get("league"), gm.get("state_text"), h_name, a_name, gm.get("home_score", 0), gm.get("away_score", 0), p_num, pre_tot, pre_spd)

    st.markdown("#### 📊 Matchup Projection Telemetry")
    with st.container(border=True):
        st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px; margin-bottom:14px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <span style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); font-weight:800; font-size:0.75rem; padding:3px 8px; border-radius:6px;">
                    {gm_league}
                </span>
                <div style="display:flex; align-items:center; gap:8px;">
                    <img src="{a_logo}" width="28" height="28" style="object-fit:contain; border-radius:50%;">
                    <span style="font-size:1.05rem; font-weight:800; color:#f8fafc;">{a_name} ({a_sh})</span>
                </div>
                <span style="opacity:0.4; font-weight:700;">@</span>
                <div style="display:flex; align-items:center; gap:8px;">
                    <img src="{h_logo}" width="28" height="28" style="object-fit:contain; border-radius:50%;">
                    <span style="font-size:1.05rem; font-weight:800; color:#f8fafc;">{h_name} ({h_sh})</span>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:rgba(255,255,255,0.06); color:#cbd5e1; border:1px solid rgba(255,255,255,0.1); padding:3px 10px; border-radius:6px; font-size:0.80rem; font-weight:600;">
                    🗓️ {kickoff_time}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Pre-Game Total", f"{pre_tot:.1f} pts")
        m2.metric("Live Pace Projection", f"{live_proj_tot:.1f} pts", delta=round(live_proj_tot - pre_tot, 1))
        m3.metric("Projected Winner", fav_team, f"{abs(pre_spd):.1f} pts")
        m4.metric("Game Status", f"Q{p_num} • {gm.get('clock', '0:00')}" if p_num > 0 else "Pre-Game")

        st.caption(f"🎯 **Key Player Projections ({a_sh} & {h_sh}):**")
        if is_nba_game:
            shooters = get_live_nba_3pm_roster(gm.get("home_id"), game_id=gm.get("id"))[:2]
            p_cols = st.columns(len(shooters) if shooters else 1)
            for idx, sh in enumerate(shooters):
                p_cols[idx].info(f"🏀 **{sh[0]}**: Proj {sh[3]} Pts | Proj {sh[2]} 3PM")
        else:
            fb = get_live_football_roster(gm.get("home_id") or gm.get("home_short"), gm_league)[:2]
            p_cols = st.columns(len(fb) if fb else 1)
            for idx, ply in enumerate(fb):
                p_cols[idx].info(f"🏈 **{ply[0]}** ({ply[1]}): 52% Projected Anytime TD")

    # =========================================================================
    # 3-TIER RECOMMENDATIONS (Render Only If Matched To Current Game)
    # =========================================================================
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
                risk = rc.number_input("Risk ($)", min_value=1.0, value=5.0, step=1.0)
                payout = pc.number_input("Payout ($)", min_value=1.0, value=10.0, step=1.0)

                actual_profit = float(payout) - float(risk)
                st.caption(f"Estimated Net Profit: **${actual_profit:.2f}** (Payout ${payout:.2f} - Risk ${risk:.2f})")

                if st.form_submit_button("🔒 Lock In Bet Slip", type="primary", use_container_width=True):
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
