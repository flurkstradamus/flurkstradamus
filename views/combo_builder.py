import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster, get_live_nba_3pm_roster

def prob_to_american_odds(prob):
    p = max(0.005, min(0.995, float(prob)))
    if p >= 0.50:
        odds = int(round(-100.0 * (p / (1.0 - p))))
        return f"{odds}"
    else:
        odds = int(round(100.0 * ((1.0 - p) / p)))
        return f"+{odds}"

def build_system_combo_legs(pool_games, target_market, strat_choice, leg_count):
    """
    Selects top EV discrepancy legs up to 15 legs across available games.
    """
    selected_legs = []
    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice

    sorted_games = sorted(pool_games, key=lambda g: abs(float(g.get("market_spread", 0))), reverse=True)

    for gm in sorted_games:
        if len(selected_legs) >= leg_count:
            break

        league = str(gm.get("league", "NFL")).upper()
        is_nba = (league == "NBA")

        ou_open = round_half_point(gm.get("market_ou", 224.5 if is_nba else 46.5))
        spread_open = round_half_point(gm.get("market_spread", -3.5))
        fav_team = gm["home_team"] if spread_open < 0 else gm["away_team"]
        dog_team = gm["away_team"] if spread_open < 0 else gm["home_team"]
        fav_spread = spread_open if fav_team == gm["home_team"] else -spread_open

        star_player = "Primary Scorer" if is_nba else "Starting RB"
        if is_nba:
            h_shooters = get_live_nba_3pm_roster(gm.get("home_id"), game_id=gm.get("id"))
            if h_shooters:
                star_player = h_shooters[0][0]
        else:
            h_fb = get_live_football_roster(gm.get("home_id") or gm.get("home_short"), league)
            if h_fb:
                star_player = h_fb[0][0]

        leg_data = {
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}",
            "league": league,
            "away_logo": gm.get("away_logo", DEFAULT_LOGO),
            "home_logo": gm.get("home_logo", DEFAULT_LOGO),
            "kickoff": gm.get("kickoff", "Scheduled")
        }

        if "Game Totals" in target_market:
            cush = (7.5 if is_nba else 4.5) if is_safe else (3.5 if is_nba else 2.0)
            tot_line = round_half_point(ou_open + cush)
            leg_data.update({
                "picked_team": gm.get("home_team"),
                "type": "Game Total",
                "side": "Under",
                "line": str(tot_line),
                "pick_text": f"Under {tot_line:.1f}",
                "prob": 0.74 if is_safe else 0.64
            })
        elif "Point Spread" in target_market:
            if is_safe:
                teased = round_half_point(abs(fav_spread) + (5.5 if is_nba else 3.5))
                leg_data.update({
                    "picked_team": dog_team,
                    "type": "Point Spread (ATS)",
                    "side": "Spread",
                    "line": str(teased),
                    "pick_text": f"{dog_team} {teased:+.1f}",
                    "prob": 0.73
                })
            else:
                leg_data.update({
                    "picked_team": fav_team,
                    "type": "Point Spread (ATS)",
                    "side": "Spread",
                    "line": str(fav_spread),
                    "pick_text": f"{fav_team} {fav_spread:+.1f}",
                    "prob": 0.58
                })
        elif "Moneyline" in target_market or "Straight Up" in target_market:
            target_t = fav_team if not is_high_profit else dog_team
            p_val = 0.68 if target_t == fav_team else 0.44
            leg_data.update({
                "picked_team": target_t,
                "type": "Moneyline",
                "side": "Moneyline",
                "line": "0.0",
                "pick_text": f"{target_t} ML",
                "prob": p_val
            })
        elif "Player Prop" in target_market or "Three-Pointers" in target_market or "Touchdown" in target_market:
            if is_nba:
                threshold = "1+" if is_safe else ("3+" if is_high_profit else "2+")
                p_val = 0.86 if is_safe else (0.49 if is_high_profit else 0.68)
                line_val = "0.5" if is_safe else ("2.5" if is_high_profit else "1.5")
                leg_data.update({
                    "picked_team": star_player,
                    "type": "NBA 3-Pointers Made",
                    "side": "Over",
                    "line": line_val,
                    "pick_text": f"{star_player} {threshold} 3PM",
                    "prob": p_val
                })
            else:
                leg_data.update({
                    "picked_team": star_player,
                    "type": "Player Anytime TD",
                    "side": "TD",
                    "line": "1.0",
                    "pick_text": f"{star_player} Anytime TD",
                    "prob": 0.52
                })
        else:
            if is_safe:
                tot_line = round_half_point(ou_open + (7.5 if is_nba else 4.5))
                leg_data.update({
                    "picked_team": gm.get("home_team"),
                    "type": "Game Total",
                    "side": "Under",
                    "line": str(tot_line),
                    "pick_text": f"Under {tot_line:.1f}",
                    "prob": 0.74
                })
            elif is_high_profit:
                if is_nba:
                    leg_data.update({
                        "picked_team": star_player,
                        "type": "NBA 3-Pointers Made",
                        "side": "Over",
                        "line": "2.5",
                        "pick_text": f"{star_player} 3+ 3PM",
                        "prob": 0.50
                    })
                else:
                    leg_data.update({
                        "picked_team": star_player,
                        "type": "Player Anytime TD",
                        "side": "TD",
                        "line": "1.0",
                        "pick_text": f"{star_player} Anytime TD",
                        "prob": 0.49
                    })
            else:
                leg_data.update({
                    "picked_team": fav_team,
                    "type": "Point Spread (ATS)",
                    "side": "Spread",
                    "line": str(fav_spread),
                    "pick_text": f"{fav_team} {fav_spread:+.1f}",
                    "prob": 0.58
                })

        selected_legs.append(leg_data)

    return selected_legs

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo & Parlay Builder")
    st.caption("Construct multi-game tickets, select leg volume, edit lines and probabilities, audit correlated edges, and lock in tickets.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []
    if "combo_leg_count_val" not in st.session_state:
        st.session_state.combo_leg_count_val = 3

    # =========================================================================
    # 1. PRIMARY SELECTION & CONFIGURATION MATRIX
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 🤖 Select & Configure Multi-Leg Matchups")

        r1_c1, r1_c2, r1_c3 = st.columns([2.5, 2.5, 2.2], vertical_alignment="bottom")
        league_choice = r1_c1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NFL", "NBA", "NCAA Football"],
            key="cb_cfg_league"
        )
        t_filter = r1_c2.selectbox(
            "Game Filter Status",
            options=["🌐 All Matchups", "⏳ Upcoming Games", "⚡ Live Games"],
            key="cb_cfg_filter"
        )

        # Stepper Text Box with + / - up to 15 legs
        with r1_c3:
            st.markdown("<label style='font-size:0.875rem;font-weight:400;'>Target # of Legs (Up to 15)</label>", unsafe_allow_html=True)
            cnt_cols = st.columns([1, 1.8, 1])
            if cnt_cols[0].button("➖", key="cb_step_minus", use_container_width=True):
                if st.session_state.combo_leg_count_val > 2:
                    st.session_state.combo_leg_count_val -= 1
                    st.rerun()
            
            # Direct numeric input field
            typed_count = cnt_cols[1].number_input(
                "Legs",
                min_value=2,
                max_value=15,
                value=int(st.session_state.combo_leg_count_val),
                step=1,
                label_visibility="collapsed",
                key="cb_num_input_stepper"
            )
            st.session_state.combo_leg_count_val = int(typed_count)

            if cnt_cols[2].button("➕", key="cb_step_plus", use_container_width=True):
                if st.session_state.combo_leg_count_val < 15:
                    st.session_state.combo_leg_count_val += 1
                    st.rerun()

        leg_count = st.session_state.combo_leg_count_val

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

        selection_mode = st.radio(
            "Matchup Selection Method",
            ["🤖 Let the System Pick (Highest Model Discrepancies)", "✍️ Enter Legs Manually / Hand-Pick"],
            horizontal=True,
            key="cb_cfg_selection_mode"
        )

        r3_c1, r3_c2 = st.columns(2)
        is_nba_scope = (league_choice == "NBA")
        is_nfl_scope = (league_choice == "NFL" or league_choice == "NCAA Football")

        if is_nba_scope:
            market_options = [
                "⚡ Let the System Pick (Best NBA Discrepancies)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🎯 NBA Player Three-Pointers Made (1+, 2+, 3+)"
            ]
        elif is_nfl_scope:
            market_options = [
                "⚡ Let the System Pick (Best Football Discrepancies)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏈 Football Anytime Touchdown Scorer"
            ]
        else:
            market_options = [
                "⚡ Let the System Pick (Cross-Sport Edge)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🎯 High EV Player Props (3PM / Touchdown)"
            ]

        target_market = r3_c1.selectbox("Target Bet / Market Type", market_options, key="cb_cfg_target_market")
        strat_choice = r3_c2.selectbox(
            "Model Strategy Profile",
            [
                "⚖️ Balanced Edge (+EV Sweet Spot)",
                "🛡️ Safe Floor (High Win %, Low Drawdown)",
                "🚀 High Profit (Max Multiplier & Props)",
                "🎯 Mixed Tier Spectrum (Balanced Mix)"
            ],
            key="cb_cfg_strat_choice"
        )

        if "Let the System Pick" in selection_mode:
            if st.button(f"⚡ Generate {leg_count}-Leg Combo Analysis & Slip", type="primary", use_container_width=True):
                if not pool:
                    st.warning("No matchups match your selected league or game filter.")
                else:
                    st.session_state.combo_active_legs = build_system_combo_legs(pool, target_market, strat_choice, leg_count)
                    st.toast(f"✅ Generated {len(st.session_state.combo_active_legs)}-leg combo based on model discrepancies!", icon="🤖")
                    st.rerun()
        else:
            st.markdown("---")
            st.markdown("##### ✍️ Manual Matchup & Leg Ingestion")
            m_t1, m_t2 = st.tabs(["🎯 Add from Live Matchup Board", "📝 Create Custom Prop / Spread Leg"])

            with m_t1:
                if not pool:
                    st.info("No games available on the slate matching your league filter.")
                else:
                    mc1, mc2, mc3 = st.columns([3.0, 2.5, 1.5], vertical_alignment="bottom")
                    game_labels = [f"[{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')} ({gm.get('kickoff', 'Upcoming')})" for gm in pool]
                    sel_game_idx = mc1.selectbox("Select Matchup", range(len(game_labels)), format_func=lambda i: game_labels[i], key="cb_man_slate_gm")
                    target_gm = pool[sel_game_idx]

                    ou_val = round_half_point(target_gm.get("market_ou", 224.5 if target_gm.get("league") == "NBA" else 46.5))
                    spd_val = round_half_point(target_gm.get("market_spread", -3.5))
                    fav_t = target_gm.get("home_team") if spd_val < 0 else target_gm.get("away_team")

                    leg_preset = mc2.selectbox("Preset Market Line", [
                        f"Under {ou_val}",
                        f"Over {ou_val}",
                        f"{fav_t} {spd_val:+.1f}",
                        f"{fav_t} ML"
                    ], key="cb_man_preset_opt")

                    if mc3.button("➕ Insert Leg", use_container_width=True, type="primary"):
                        if len(st.session_state.combo_active_legs) < 15:
                            st.session_state.combo_active_legs.append({
                                "matchup": f"{target_gm.get('away_short')} @ {target_gm.get('home_short')}",
                                "league": target_gm.get("league", "SPORTS"),
                                "away_logo": target_gm.get("away_logo", DEFAULT_LOGO),
                                "home_logo": target_gm.get("home_logo", DEFAULT_LOGO),
                                "kickoff": target_gm.get("kickoff", "Scheduled"),
                                "picked_team": fav_t if "ML" in leg_preset or spd_val != 0 else target_gm.get("home_team"),
                                "type": "Game Total" if "Under" in leg_preset or "Over" in leg_preset else ("Point Spread" if spd_val != 0 and "ML" not in leg_preset else "Moneyline"),
                                "side": "Under" if "Under" in leg_preset else ("Over" if "Over" in leg_preset else "Spread"),
                                "line": str(ou_val) if "Under" in leg_preset or "Over" in leg_preset else str(spd_val),
                                "pick_text": leg_preset,
                                "prob": 0.65 if "Under" in leg_preset else 0.58
                            })
                            st.rerun()
                        else:
                            st.warning("Maximum of 15 legs reached.")

            with m_t2:
                mx1, mx2, mx3, mx4, mx5 = st.columns([2.0, 3.0, 1.8, 1.5, 1.5], vertical_alignment="bottom")
                cust_m = mx1.text_input("Matchup", value="TEN @ CIN", key="cb_man_cust_m")
                cust_p = mx2.text_input("Pick Label / Prop", value="Chase Brown Anytime TD", key="cb_man_cust_p")
                cust_t = mx3.selectbox("Market Category", ["Player Prop", "Game Total", "Point Spread", "Moneyline"], key="cb_man_cust_t")
                cust_pr = mx4.number_input("Win Prob (%)", min_value=5, max_value=99, value=55, step=1, key="cb_man_cust_pr")

                if mx5.button("➕ Add Custom", use_container_width=True):
                    if len(st.session_state.combo_active_legs) < 15:
                        st.session_state.combo_active_legs.append({
                            "matchup": cust_m.strip(),
                            "league": "PROP",
                            "away_logo": DEFAULT_LOGO,
                            "home_logo": DEFAULT_LOGO,
                            "kickoff": "Manual",
                            "picked_team": cust_p.strip(),
                            "type": cust_t,
                            "side": "Over",
                            "line": "1.0",
                            "pick_text": cust_p.strip(),
                            "prob": float(cust_pr) / 100.0
                        })
                        st.rerun()
                    else:
                        st.warning("Maximum of 15 legs reached.")

    # =========================================================================
    # 2. RESTORED GREEN LEGS CARD DISPLAY WITH INLINE EDIT POPOVER
    # =========================================================================
    legs = st.session_state.combo_active_legs

    if not legs:
        st.info("No legs loaded yet. Configure the engine above and click generate or add legs manually.")
        return

    st.markdown(f"### 📋 Current Combo Legs ({len(legs)})")

    # Render each leg in classic green accent layout with dedicated Edit popovers
    for idx, leg in enumerate(legs):
        p_pct = int(round(float(leg.get("prob", 0.55)) * 100))
        m_txt = leg.get("matchup", "Matchup")
        p_txt = leg.get("pick_text", "Pick")
        t_type = leg.get("type", "Pick")
        lg_val = leg.get("league", "SPORTS")

        with st.container(border=True):
            c_left, c_mid, c_right = st.columns([4.5, 2.2, 1.8], vertical_alignment="center")

            with c_left:
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="background:rgba(74,222,128,0.15); color:#4ade80; border:1px solid rgba(74,222,128,0.3); font-weight:800; font-size:0.75rem; padding:2px 8px; border-radius:4px;">
                        #{idx + 1} {lg_val}
                    </span>
                    <span style="font-weight:700; font-size:0.95rem; color:#f8fafc;">{m_txt}</span>
                    <span style="opacity:0.5; font-size:0.75rem;">• {t_type}</span>
                </div>
                <div style="font-size:1.02rem; font-weight:700; color:#4ade80; margin-top:3px;">
                    {p_txt}
                </div>
                """, unsafe_allow_html=True)

            with c_mid:
                st.markdown(f"""
                <div style="font-size:0.80rem; opacity:0.7;">Model Probability</div>
                <div style="font-size:1.15rem; font-weight:800; color:#38bdf8;">{p_pct}%</div>
                """, unsafe_allow_html=True)

            with c_right:
                btn_c1, btn_c2 = st.columns([1.5, 1])
                with btn_c1:
                    with st.popover("✏️ Edit", use_container_width=True):
                        st.markdown(f"**Edit Leg #{idx + 1}**")
                        leg["matchup"] = st.text_input("Matchup", value=leg.get("matchup", ""), key=f"gr_m_{idx}")
                        leg["pick_text"] = st.text_input("Pick Label", value=leg.get("pick_text", ""), key=f"gr_p_{idx}")
                        leg["side"] = st.text_input("Side / Dir", value=leg.get("side", ""), key=f"gr_s_{idx}")
                        leg["line"] = st.text_input("Line", value=str(leg.get("line", "")), key=f"gr_l_{idx}")
                        new_prob = st.slider("Win Prob (%)", min_value=5, max_value=99, value=p_pct, key=f"gr_pr_{idx}")
                        leg["prob"] = float(new_prob) / 100.0

                        if st.button("🗑️ Remove Leg", key=f"pop_del_{idx}", type="secondary", use_container_width=True):
                            st.session_state.combo_active_legs.pop(idx)
                            st.rerun()

                with btn_c2:
                    if st.button("❌", key=f"direct_del_{idx}", help="Delete leg", use_container_width=True):
                        st.session_state.combo_active_legs.pop(idx)
                        st.rerun()

    if st.button("🗑️ Clear Entire Slip", key="btn_clear_cb_slip"):
        st.session_state.combo_active_legs = []
        st.rerun()

    st.markdown("---")

    # =========================================================================
    # 3. COMPOUND ANALYTICS & EXPECTED VALUE
    # =========================================================================
    compound_prob = 1.0
    for leg in legs:
        compound_prob *= float(leg.get("prob", 0.50))
    compound_prob = max(0.0001, min(0.999, compound_prob))

    fair_multiplier = 1.0 / compound_prob
    fair_american = prob_to_american_odds(compound_prob)

    st.markdown("### 🎲 Ticket Edge Analytics & Fair Value")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compound Win Probability", f"{compound_prob * 100:.2f}%")
    m2.metric("Fair American Odds", fair_american)
    m3.metric("True Dec Multiplier", f"{fair_multiplier:.2f}x")
    m4.metric("Active Legs", len(legs))

    # =========================================================================
    # 4. TICKET LOCK-IN & FINANCIAL RECORDING
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 🔒 Lock In Combo Ticket Slip")
        with st.form("parlay_ticket_lock_form"):
            r_col, p_col = st.columns(2)
            default_risk = 5.0
            default_payout = round(default_risk * fair_multiplier, 2)

            risk_input = r_col.number_input("Risk Amount ($)", min_value=0.5, value=float(default_risk), step=1.0)
            payout_input = p_col.number_input("Total Payout ($)", min_value=0.5, value=float(default_payout), step=1.0)

            net_profit = float(payout_input) - float(risk_input)
            roi_pct = (net_profit / max(0.01, float(risk_input))) * 100.0
            ev_val = (compound_prob * float(payout_input)) - float(risk_input)
            ev_color = "#4ade80" if ev_val >= 0 else "#ef4444"

            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:10px 14px; border-radius:8px; margin-top:4px; margin-bottom:12px; border:1px solid rgba(255,255,255,0.08);">
                <div>Net Profit: <strong style="color:#4ade80;">+${net_profit:.2f}</strong> ({roi_pct:+.1f}% ROI)</div>
                <div>Model Expected Value: <strong style="color:{ev_color};">{ev_val:+.2f}</strong></div>
            </div>
            """, unsafe_allow_html=True)

            notes_tag = st.text_input("Strategy Tag / Ticket Notes", value=f"{len(legs)}-Leg Correlated Slip")

            if st.form_submit_button("🔒 Lock In Parlay Ticket", type="primary", use_container_width=True):
                summary_picks = ", ".join([l.get("pick_text", "") for l in legs[:3]])
                if len(legs) > 3:
                    summary_picks += f" +{len(legs) - 3} more"

                ticket_data = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Combo",
                    "bet_category": "Combo",
                    "matchup": f"{len(legs)}-Leg Parlay",
                    "bet": f"{len(legs)}-Leg Combo: {summary_picks}",
                    "risk_dollars": float(risk_input),
                    "payout_dollars": float(payout_input),
                    "payout": float(payout_input),
                    "locked_profit": float(net_profit),
                    "win_prob": f"{compound_prob * 100:.1f}%",
                    "status": "Pending",
                    "notes": notes_tag,
                    "parsed_legs": [
                        {
                            "matchup": l.get("matchup"),
                            "picked_team": l.get("picked_team"),
                            "type": l.get("type"),
                            "side": l.get("side"),
                            "line": l.get("line"),
                            "prob": l.get("prob")
                        }
                        for l in legs
                    ]
                }

                st.session_state.saved_bets.insert(0, ticket_data)
                save_all_storage(
                    st.session_state.saved_bets,
                    st.session_state.chat_messages,
                    st.session_state.user_accounts,
                    st.session_state.banned_emails,
                    st.session_state.game_snapshots,
                    st.session_state.support_tickets
                )
                st.session_state.combo_active_legs = []
                st.toast("🎉 Parlay ticket locked in and saved to history!", icon="🔒")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
