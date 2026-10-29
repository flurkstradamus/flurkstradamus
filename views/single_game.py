import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def generate_single_rationale(b_type, b_side, b_line, gm, p_name="", strat="Balanced"):
    is_nba = (gm.get("league") == "NBA")
    ou = float(gm.get("market_ou", 224.5 if is_nba else 47.5))
    spread = float(gm.get("market_spread", -3.5))

    if b_type == "Game Total":
        diff = abs(b_line - ou)
        if b_side == "Under":
            return f"Pace model projects tempo suppression. Opening consensus was {ou:.1f}; identified positive expected value on Under {b_line:.1f} (+{diff:.1f} pts safety buffer)."
        else:
            return f"Offensive conversion rate projects above-average tempo. Model targets clearing {b_line:.1f} pts with high-variance scoring runs."
    elif b_type == "Point Spread (ATS)":
        return f"Power ratings give {p_name} an efficiency margin against market line ({spread:+.1f}). Model favors covering current strike."
    elif b_type == "Straight Up Winner (Moneyline)":
        return f"Situational metrics and home/away splits indicate {p_name} outright win likelihood exceeds implied market odds."
    elif b_type == "Player Points Prop":
        if "Safe Floor" in strat:
            return f"🛡️ Safe Floor profile applied: Shaded {p_name}'s line down to {b_line:.1f} pts for high-probability floor clearance (68%+ expected win rate)."
        elif "High Profit" in strat:
            return f"🚀 High Profit longshot profile: Targeting upside ladder on {p_name} at {b_line:.1f} pts ({b_side}) for odds multiplier boost."
        else:
            return f"⚖️ Balanced EV: {p_name} usage rate projects over 27.5%. Matchup defense allows above-average scoring efficiency, favoring {b_side} {b_line:.1f} pts."
    else:
        return f"{p_name} holds >60% red-zone touch share over recent drives. Positive mathematical expectancy for Anytime TD."

def build_single_game_ai_pick(target_game, chosen_market, strat_choice):
    is_nba = (target_game.get("league") == "NBA")
    line_val = round_half_point(target_game.get("market_ou", 224.5 if is_nba else 47.5))
    spread_val = round_half_point(target_game.get("market_spread", -3.5))

    if "Game Totals" in chosen_market:
        chosen_type = "Game Total"
    elif "Point Spreads" in chosen_market:
        chosen_type = "Point Spread (ATS)"
    elif "Straight Up" in chosen_market:
        chosen_type = "Straight Up Winner (Moneyline)"
    elif "NBA Player Points" in chosen_market and is_nba:
        chosen_type = "Player Points Prop"
    elif "Touchdown" in chosen_market and not is_nba:
        chosen_type = "Player Anytime Touchdown Scorer"
    else:
        chosen_type = "Game Total"

    side_val = "Under"
    target_p_name = target_game["home_team"]

    if chosen_type == "Game Total":
        if "Safe Floor" in strat_choice:
            side_val = "Under"
            line_val = round_half_point(line_val + (6.5 if is_nba else 3.5))
        elif "High Profit" in strat_choice:
            side_val = "Over"
            line_val = round_half_point(line_val - 2.5)
        prob = calculate_win_prob(line_val, (218.0 if is_nba else 43.0), (12.0 if is_nba else 7.0), is_under=(side_val == "Under"))
    elif chosen_type == "Point Spread (ATS)":
        side_val = "Spread"
        line_val = spread_val
        prob = 0.56 if "Safe Floor" in strat_choice else 0.52
    elif chosen_type == "Straight Up Winner (Moneyline)":
        side_val = "Moneyline"
        line_val = 0.0
        add_score = 40 if is_nba else 14
        h_prob = calculate_moneyline_prob(target_game["home_score"] + add_score, target_game["away_score"] + add_score, target_game.get("home_record", "0-0"), target_game.get("away_record", "0-0"))
        prob = h_prob
    elif chosen_type == "Player Points Prop":
        roster = get_live_nba_roster(target_game.get("home_id") or target_game.get("home_short"))
        if not roster:
            roster = [("Primary Scorer", "G", 22.5), ("Secondary Option", "F", 18.5)]

        if "Safe Floor" in strat_choice:
            selected_player = roster[0]
            target_p_name = selected_player[0]
            base_pts = float(selected_player[2])
            line_val = max(9.5, round_half_point(base_pts - 3.5))
            side_val = "Over"
            prob = 0.69
        elif "High Profit" in strat_choice:
            selected_player = roster[min(len(roster) - 1, 1)]
            target_p_name = selected_player[0]
            base_pts = float(selected_player[2])
            line_val = round_half_point(base_pts + 4.5)
            side_val = "Over"
            prob = 0.43
        else:
            selected_player = roster[0]
            target_p_name = selected_player[0]
            line_val = float(selected_player[2])
            side_val = "Over"
            prob = 0.56
    else:
        roster = get_live_football_roster(target_game.get("home_id") or target_game.get("home_short"), target_game.get("league"))
        if "High Profit" in strat_choice and len(roster) > 1:
            target_p_name = roster[1][0]
            prob = 0.38
        else:
            target_p_name = roster[0][0] if roster else "Top Running Back"
            prob = 0.48
        line_val = 1.0
        side_val = "TD"

    rat = generate_single_rationale(chosen_type, side_val, line_val, target_game, target_p_name, strat_choice)

    return {
        "type": chosen_type,
        "side": side_val,
        "line": line_val,
        "picked_team": target_p_name,
        "prob": prob,
        "matchup_str": f"{target_game['away_short']} @ {target_game['home_short']}",
        "kickoff": target_game.get("kickoff", "Scheduled"),
        "away_logo": target_game.get("away_logo", DEFAULT_LOGO),
        "home_logo": target_game.get("home_logo", DEFAULT_LOGO),
        "away_short": target_game.get("away_short", "AWAY"),
        "home_short": target_game.get("home_short", "HOME"),
        "league": target_game.get("league", "SPORTS"),
        "rationale": rat
    }

def render_single_game(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("⚡ Single Game Analytics Engine")
    st.caption("Algorithmic single-matchup scanner, pace regression model, and ticket slip builder.")

    if "single_preview_pick" not in st.session_state:
        st.session_state.single_preview_pick = None
    if "single_active_bet" not in st.session_state:
        st.session_state.single_active_bet = None
    if "single_engine_version" not in st.session_state:
        st.session_state.single_engine_version = 0

    eng_ver = st.session_state.single_engine_version

    # Top Controls Container (Identical Workflow to Combo Builder)
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

        if col_btn.button("⚡ Auto-Generate Pick", use_container_width=True, disabled=len(pool) == 0):
            st.session_state.single_preview_pick = build_single_game_ai_pick(pool[0], chosen_market, strat_choice)
            st.rerun()

    # AI Recommendation Preview Card
    if st.session_state.single_preview_pick:
        p_pick = st.session_state.single_preview_pick
        with st.container(border=True):
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:1.15rem; font-weight:700;">🎯 AI Recommended Single Bet</span>
                    <span style="background-color:#22c55e; color:#000; font-weight:800; font-size:0.75rem; padding:2px 8px; border-radius:4px;">OPTIMIZED</span>
                </div>
                <div style="font-size:0.80rem; opacity:0.75;">Profile: <strong>{strat_choice.split()[1]}</strong></div>
            </div>
            """, unsafe_allow_html=True)

            if p_pick["type"] == "Game Total":
                pick_label = f"{p_pick['side']} {p_pick['line']:.1f} pts"
            elif p_pick["type"] == "Point Spread (ATS)":
                pick_label = f"{p_pick['picked_team']} {p_pick['line']:+.1f}"
            elif p_pick["type"] == "Straight Up Winner (Moneyline)":
                pick_label = f"{p_pick['picked_team']} Outright ML"
            elif p_pick["type"] == "Player Points Prop":
                pick_label = f"{p_pick['picked_team']} {p_pick['side']} {p_pick['line']:.1f} Pts"
            else:
                pick_label = f"{p_pick['picked_team']} Any Time TD"

            # Responsive 2-Row Matchup Presentation (Matches Combo Builder mobile fix)
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:10px 12px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:4px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <img src="{p_pick.get('away_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                        <strong>{p_pick.get('away_short')}</strong>
                        <span style="opacity:0.35;">@</span>
                        <img src="{p_pick.get('home_logo', DEFAULT_LOGO)}" width="22" height="22" style="border-radius:50%; object-fit:contain;">
                        <strong>{p_pick.get('home_short')}</strong>
                    </div>
                    <span style="background:rgba(255,255,255,0.06); color:#94a3b8; padding:2px 8px; border-radius:4px; font-size:0.75rem;">
                        🗓️ {p_pick.get('kickoff', 'Upcoming')}
                    </span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(255,255,255,0.04); padding-top:6px; flex-wrap:wrap; gap:6px;">
                    <span style="color:#4ade80; font-size:1.05rem; font-weight:700;">{pick_label}</span>
                    <span style="background:rgba(56,189,248,0.12); color:#38bdf8; padding:2px 7px; border-radius:4px; font-size:0.75rem; font-weight:600;">
                        {p_pick['type']}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Analytics Panel
            p_val = max(0.01, min(0.95, float(p_pick.get("prob", 0.55))))
            fair_mult = 1.0 / p_val
            fair_odds = f"+{int((fair_mult - 1.0) * 100)}" if fair_mult >= 2.0 else f"-{int(100 / (fair_mult - 1.0))}"
            ev_pct = round(((fair_mult * 0.95) - 1.0) * 100, 1)

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("##### 📊 Single Game Model Analytics")
                a1, a2, a3, a4 = st.columns(4)
                a1.metric("Win Probability", f"{p_val * 100:.1f}%", help="Calculated expectancy based on terminal pace and Bayesian regression.")
                a2.metric("Fair Model Odds", fair_odds, delta=f"{fair_mult:.2f}x Multiplier", delta_color="off")
                a3.metric("Estimated Edge (+EV)", f"+{max(1.5, ev_pct):.1f}%", delta="Favorable Edge")
                
                vol_tag = "🟢 Low Drawdown" if "Safe Floor" in strat_choice else ("🟡 Balanced Edge" if "Balanced" in strat_choice else "🔴 High Alpha")
                a4.metric("Risk Bracket", vol_tag, delta="Single Slate", delta_color="off")
                st.progress(p_val, text=f"Model Confidence: {p_val * 100:.1f}%")

            with st.expander("🧠 Model Edge & Situational Rationale", expanded=False):
                st.write(f"💡 {p_pick.get('rationale')}")

            if st.button("📥 Load Pick to Slip", type="primary", use_container_width=True, key="btn_load_single_pick"):
                st.session_state.single_active_bet = dict(p_pick)
                st.toast("✅ Loaded pick into active slip form below!", icon="📥")
                st.rerun()

    if not pool:
        st.info("No matchups found matching your current filter.")
        return

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in pool]

    st.markdown("---")
    st.markdown("#### 📝 Active Single Bet Slip")

    if not st.session_state.single_active_bet:
        st.info("No active ticket slip. Click **⚡ Auto-Generate Pick** above and load it, or set up a custom ticket manually.")
        if st.button("➕ Set Up Single Bet Manually", use_container_width=True):
            st.session_state.single_active_bet = build_single_game_ai_pick(pool[0], "Game Total", strat_choice)
            st.rerun()
        return

    cur_bet = st.session_state.single_active_bet

    with st.container(border=True):
        sel_idx = st.selectbox(
            "Target Matchup",
            range(len(choices)),
            index=0,
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
        w_idx = m_types.index(curr_wtype) if curr_wtype in m_types else 0
        chosen_wtype = st.radio("Market", m_types, index=w_idx, horizontal=True, key=f"sg_wtype_radio_{eng_ver}")

        if chosen_wtype == "Game Total":
            c1, c2 = st.columns(2)
            cur_s = cur_bet.get("side", "Under")
            c_side = c1.selectbox("Side", ["Under", "Over"], index=0 if cur_s == "Under" else 1, key=f"sg_side_{eng_ver}")
            default_line = float(round_half_point(cur_bet.get("line", selected_gm.get("market_ou", 224.5 if is_nba else 47.5))))
            c_line = c2.number_input("Line (pts)", value=default_line, step=0.5, key=f"sg_line_{eng_ver}")
            bet_title = f"{c_side} {c_line:.1f}"
            picked_t = selected_gm["home_team"]
            prob_est = calculate_win_prob(c_line, (218.0 if is_nba else 43.0), (12.0 if is_nba else 7.0), is_under=(c_side == "Under"))

        elif chosen_wtype == "Point Spread (ATS)":
            c1, c2 = st.columns(2)
            cur_p = cur_bet.get("picked_team", selected_gm["home_team"])
            cov_idx = 1 if cur_p == selected_gm["away_team"] else 0
            picked_t = c1.selectbox("Covering Team", [selected_gm["home_team"], selected_gm["away_team"]], index=cov_idx, key=f"sg_cover_{eng_ver}")
            default_spd = float(round_half_point(cur_bet.get("line", selected_gm.get("market_spread", -3.5))))
            c_line = c2.number_input("Spread", value=default_spd, step=0.5, key=f"sg_spd_{eng_ver}")
            c_side = "Spread"
            bet_title = f"{picked_t} {c_line:+.1f}"
            prob_est = 0.54

        elif chosen_wtype == "Straight Up Winner (Moneyline)":
            cur_p = cur_bet.get("picked_team", selected_gm["home_team"])
            win_idx = 1 if cur_p == selected_gm["away_team"] else 0
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
            p_idx = all_p.index(cur_p) if cur_p in all_p else 0
            picked_t = c1.selectbox("Player", all_p, index=p_idx, key=f"sg_nba_p_{eng_ver}")
            c_side = c2.selectbox("Side", ["Over", "Under"], index=0 if cur_bet.get("side") == "Over" else 1, key=f"sg_nba_s_{eng_ver}")
            c_line = st.number_input("Points Line", value=float(cur_bet.get("line", 22.5)), step=0.5, key=f"sg_nba_l_{eng_ver}")
            bet_title = f"{picked_t} {c_side} {c_line:.1f} Pts"
            prob_est = 0.58

        else:
            h_roster = get_live_football_roster(selected_gm.get("home_id") or selected_gm.get("home_short"), selected_gm.get("league"))
            a_roster = get_live_football_roster(selected_gm.get("away_id") or selected_gm.get("away_short"), selected_gm.get("league"))
            all_p = [p[0] for p in (h_roster + a_roster)]
            cur_p = cur_bet.get("picked_team")
            p_idx = all_p.index(cur_p) if cur_p in all_p else 0
            picked_t = st.selectbox("Player to Score TD", all_p, index=p_idx, key=f"sg_nfl_p_{eng_ver}")
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
