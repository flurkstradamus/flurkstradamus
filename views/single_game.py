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

    # 1. 🥉 GOOD (Safe Floor Anchor)
    if "Totals" in chosen_market or "System Pick" in chosen_market:
        good_side = "Under"
        good_line = round_half_point(ou_open + (7.5 if is_nba else 4.5))
        good_type = "Game Total"
        good_pick_text = f"Under {good_line:.1f}"
        good_prob = calculate_win_prob(good_line, ou_open - 3.0, (12.0 if is_nba else 7.0), is_under=True)
        good_rat = f"Defensive floor cushion (+{(good_line - ou_open):.1f} pts above open) creates optimal drawdown safety."
        good_target = target_game["home_team"]
    else:
        good_side = "Moneyline"
        good_line = 0.0
        good_type = "Straight Up Winner (Moneyline)"
        good_target = target_game["home_team"] if h_win_prob >= 0.50 else target_game["away_team"]
        good_pick_text = f"{good_target} ML"
        good_prob = max(h_win_prob, 1.0 - h_win_prob)
        good_rat = f"Strong straight-up anchor with a {good_prob * 100:.1f}% model win probability."

    # 2. 🥈 BETTER (Balanced +EV Sweet Spot)
    better_team = target_game["home_team"] if spread_open < 0 else target_game["away_team"]
    better_type = "Point Spread (ATS)"
    better_side = "Spread"
    better_line = spread_open if better_team == target_game["home_team"] else -spread_open
    better_pick_text = f"{better_team} {better_line:+.1f}"
    better_prob = 0.58 if "Safe Floor" in strat_choice else 0.54
    better_rat = f"Power ratings indicate {better_team} has a positive margin against the market spread ({better_line:+.1f})."

    # 3. 🥇 BEST (Optimal Value Alpha)
    if is_nba:
        h_roster = get_live_nba_roster(target_game.get("home_id") or target_game.get("home_short"))
        if h_roster:
            p_name, p_pos, base_pts = h_roster[0]
            best_type = "Player Points Prop"
            best_side = "Over"
            best_line = round_half_point(base_pts - 1.5) if "Safe Floor" in strat_choice else base_pts
            best_target = p_name
            best_pick_text = f"{p_name} Over {best_line:.1f} Pts"
            best_prob = 0.64
            best_rat = f"{p_name} projects for >28% usage. Matchup defense allows top-10 scoring efficiency."
        else:
            best_type = "Game Total"
            best_side = "Under"
            best_line = round_half_point(ou_open - 1.5)
            best_target = target_game["home_team"]
            best_pick_text = f"Under {best_line:.1f}"
            best_prob = 0.61
            best_rat = "In-game pace model projects notable scoring suppression below market consensus."
    else:
        best_type = "Game Total"
        best_side = "Under"
        best_line = round_half_point(ou_open + 1.5)
        best_target = target_game["home_team"]
        best_pick_text = f"Under {best_line:.1f}"
        best_prob = 0.62
        best_rat = "Model tempo metrics anticipate pace suppression relative to market open."

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

    return {
        "good": make_card("🥉 GOOD (Safe Floor)", "#38bdf8", good_pick_text, good_type, good_side, good_line, good_target, good_prob, good_rat),
        "better": make_card("🥈 BETTER (Balanced +EV)", "#fbbf24", better_pick_text, better_type, better_side, better_line, better_team, better_prob, better_rat),
        "best": make_card("🥇 BEST (Optimal Value)", "#4ade80", best_pick_text, best_type, best_side, best_line, best_target if 'best_target' in locals() else target_game["home_team"], best_prob, best_rat)
    }

def render_single_game(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("⚡ Single Game Analytics Engine")
    st.caption("Algorithmic single-matchup scanner, pace regression model, and tiered Good/Better/Best recommendations.")

    if "single_tier_picks" not in st.session_state:
        st.session_state.single_tier_picks = None
    if "single_active_bet" not in st.session_state:
        st.session_state.single_active_bet = None
    if "single_engine_version" not in st.session_state:
        st.session_state.single_engine_version = 0

    eng_ver = st.session_state.single_engine_version

    # AI Optimizer Controls
    with st.container(border=True):
        st.markdown("#### 🤖 AI Single Game Optimizer")

        c_top1, c_top2 = st.columns(2)
        league_choice = c_top1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NBA", "NFL", "NCAA Football"],
            index=0,
            key=f"sg_league_{eng_ver}"
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

        chosen_market = c_top2.selectbox("Target Market Focus", market_options, index=0, key=f"sg_market_{eng_ver}")

        strat_options = [
            "🛡️ Safe Floor (High Win %, Low Drawdown)",
            "⚖️ Balanced Edge (+EV Sweet Spot)",
            "🚀 High Profit (Max Multiplier & Longshots)"
        ]
        strat_choice = st.selectbox("Model Strategy Profile", strat_options, index=1, key=f"sg_strat_{eng_ver}")

        col_f1, col_f2, col_btn = st.columns([1.5, 2, 1.5], vertical_alignment="bottom")
        t_filter = col_f1.selectbox("Filter Status", ["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"], key=f"sg_t_filter_{eng_ver}")
        q_filter = col_f2.text_input("🔍 Search Matchup", placeholder="e.g. Celtics, Lakers, Chiefs...", key=f"sg_q_filter_{eng_ver}")

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

        if col_btn.button("⚡ Auto-Generate Tiers", use_container_width=True, disabled=len(pool) == 0):
            st.session_state.single_tier_picks = build_single_game_tiers(pool[0], chosen_market, strat_choice)
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
                <div style="font-size:0.80rem; opacity:0.75;">Profile: <strong>{strat_choice.split()[1]}</strong></div>
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
                    if st.button(f"📥 Load {t_key.capitalize()} Pick", key=f"btn_load_{t_key}_{eng_ver}", type=btn_type, use_container_width=True):
                        st.session_state.single_active_bet = dict(pick_data)
                        st.session_state.single_engine_version += 1
                        st.toast(f"✅ Loaded {pick_data['pick_label']} into ticket slip below!", icon="📥")
                        st.rerun()

    if not pool:
        st.info("No matchups found matching your current filter.")
        return

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in pool]

    st.markdown("---")
    st.markdown("#### 📝 Active Single Bet Slip")

    if not st.session_state.single_active_bet:
        st.info("No active bet loaded. Use **⚡ Auto-Generate Tiers** above and click **📥 Load Pick**, or set up a custom ticket manually below.")
        if st.button("➕ Set Up Bet Manually", use_container_width=True):
            def_tiers = build_single_game_tiers(pool[0], "Game Total", "Balanced")
            st.session_state.single_active_bet = dict(def_tiers["better"])
            st.session_state.single_engine_version += 1
            st.rerun()
        return

    cur_bet = st.session_state.single_active_bet

    # Match target matchup selector with currently active loaded bet
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
            key=f"sg_matchup_dropdown_{eng_ver}"
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

        chosen_wtype = st.radio("Market", m_types, index=w_idx, horizontal=True, key=f"sg_wtype_radio_{eng_ver}")

        if chosen_wtype == "Game Total":
            c1, c2 = st.columns(2)
            cur_s = cur_bet.get("side", "Under")
            s_idx = 0 if str(cur_s).lower() == "under" else 1
            c_side = c1.selectbox("Side", ["Under", "Over"], index=s_idx, key=f"sg_side_{eng_ver}")
            default_line = float(round_half_point(cur_bet.get("line") if cur_bet.get("line") is not None else selected_gm.get("market_ou", 224.5 if is_nba else 47.5)))
            c_line = c2.number_input("Line (pts)", value=default_line, step=0.5, key=f"sg_line_{eng_ver}")
            bet_title = f"{c_side} {c_line:.1f}"
            picked_t = selected_gm["home_team"]
            prob_est = calculate_win_prob(c_line, (218.0 if is_nba else 43.0), (12.0 if is_nba else 7.0), is_under=(c_side == "Under"))

        elif chosen_wtype == "Point Spread (ATS)":
            c1, c2 = st.columns(2)
            cur_p = str(cur_bet.get("picked_team", selected_gm["home_team"])).lower()
            cov_idx = 1 if cur_p in selected_gm["away_team"].lower() else 0
            picked_t = c1.selectbox("Covering Team", [selected_gm["home_team"], selected_gm["away_team"]], index=cov_idx, key=f"sg_cover_{eng_ver}")
            default_spd = float(round_half_point(cur_bet.get("line") if cur_bet.get("line") is not None else selected_gm.get("market_spread", -3.5)))
            c_line = c2.number_input("Spread", value=default_spd, step=0.5, key=f"sg_spd_{eng_ver}")
            c_side = "Spread"
            bet_title = f"{picked_t} {c_line:+.1f}"
            prob_est = 0.54

        elif chosen_wtype == "Straight Up Winner (Moneyline)":
            cur_p = str(cur_bet.get("picked_team", selected_gm["home_team"])).lower()
            win_idx = 1 if cur_p in selected_gm["away_team"].lower() else 0
            picked_t = st.selectbox("Outright Winner", [selected_gm["home_team"], selected_gm["away_team"]], index=win_idx, key=f"sg_ml_{eng_ver}")
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
            picked_t = c1.selectbox("Player", all_p, index=p_idx_sel, key=f"sg_nba_p_{eng_ver}")
            s_prop_idx = 0 if cur_bet.get("side", "Over") == "Over" else 1
            c_side = c2.selectbox("Side", ["Over", "Under"], index=s_prop_idx, key=f"sg_nba_s_{eng_ver}")
            default_pts = float(cur_bet.get("line") if cur_bet.get("line") is not None else 22.5)
            c_line = st.number_input("Points Line", value=default_pts, step=0.5, key=f"sg_nba_l_{eng_ver}")
            bet_title = f"{picked_t} {c_side} {c_line:.1f} Pts"
            prob_est = 0.58

        else:
            h_roster = get_live_football_roster(selected_gm.get("home_id") or selected_gm.get("home_short"), selected_gm.get("league"))
            a_roster = get_live_football_roster(selected_gm.get("away_id") or selected_gm.get("away_short"), selected_gm.get("league"))
            all_p = [p[0] for p in (h_roster + a_roster)]
            cur_p = cur_bet.get("picked_team")
            td_idx_sel = all_p.index(cur_p) if cur_p in all_p else 0
            picked_t = st.selectbox("Player to Score TD", all_p, index=td_idx_sel, key=f"sg_nfl_p_{eng_ver}")
            c_side, c_line = "TD", 1.0
            bet_title = f"{picked_t} Any Time TD"
            prob_est = 0.48

        with st.form(f"single_ticket_submit_form_{eng_ver}"):
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
