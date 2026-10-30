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

def generate_automated_combo_legs(target_games, strat_choice, leg_count):
    """
    Generates intelligent multi-game parlay legs across selected matchups
    based on the chosen model strategy profile (Safe, Balanced, High Profit).
    """
    generated_legs = []
    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice

    for gm in target_games[:leg_count]:
        league = str(gm.get("league", "NFL")).upper()
        is_nba = (league == "NBA")
        
        ou_open = round_half_point(gm.get("market_ou", 224.5 if is_nba else 46.5))
        spread_open = round_half_point(gm.get("market_spread", -3.5))
        fav_team = gm["home_team"] if spread_open < 0 else gm["away_team"]
        dog_team = gm["away_team"] if spread_open < 0 else gm["home_team"]
        fav_spread = spread_open if fav_team == gm["home_team"] else -spread_open

        if is_safe:
            # Safe floor: teased totals or heavy favorite spread
            cush = 6.5 if is_nba else 4.5
            tot_line = round_half_point(ou_open + cush)
            generated_legs.append({
                "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}",
                "league": league,
                "away_logo": gm.get("away_logo", DEFAULT_LOGO),
                "home_logo": gm.get("home_logo", DEFAULT_LOGO),
                "kickoff": gm.get("kickoff", "Scheduled"),
                "picked_team": gm.get("home_team"),
                "type": "Game Total",
                "side": "Under",
                "line": str(tot_line),
                "pick_text": f"Under {tot_line:.1f} Pts",
                "prob": 0.74
            })
        elif is_high_profit:
            # High profit: Player props or underdog value
            if is_nba:
                shooters = get_live_nba_3pm_roster(gm.get("home_id"), game_id=gm.get("id"))
                star = shooters[0][0] if shooters else "Starting Guard"
                generated_legs.append({
                    "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}",
                    "league": league,
                    "away_logo": gm.get("away_logo", DEFAULT_LOGO),
                    "home_logo": gm.get("home_logo", DEFAULT_LOGO),
                    "kickoff": gm.get("kickoff", "Scheduled"),
                    "picked_team": star,
                    "type": "NBA 3-Pointers Made",
                    "side": "Over",
                    "line": "2.5",
                    "pick_text": f"{star} 3+ 3-Pointers Made",
                    "prob": 0.49
                })
            else:
                fb = get_live_football_roster(gm.get("home_id") or gm.get("home_short"), league)
                star_rb = fb[0][0] if fb else "Starting RB"
                generated_legs.append({
                    "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}",
                    "league": league,
                    "away_logo": gm.get("away_logo", DEFAULT_LOGO),
                    "home_logo": gm.get("home_logo", DEFAULT_LOGO),
                    "kickoff": gm.get("kickoff", "Scheduled"),
                    "picked_team": star_rb,
                    "type": "Player Anytime TD",
                    "side": "TD",
                    "line": "1.0",
                    "pick_text": f"{star_rb} Anytime Touchdown",
                    "prob": 0.48
                })
        else:
            # Balanced: market spread efficiency cover
            generated_legs.append({
                "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}",
                "league": league,
                "away_logo": gm.get("away_logo", DEFAULT_LOGO),
                "home_logo": gm.get("home_logo", DEFAULT_LOGO),
                "kickoff": gm.get("kickoff", "Scheduled"),
                "picked_team": fav_team,
                "type": "Point Spread (ATS)",
                "side": "Spread",
                "line": str(fav_spread),
                "pick_text": f"{fav_team} {fav_spread:+.1f}",
                "prob": 0.58
            })

    return generated_legs

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo & Parlay Builder")
    st.caption("Construct multi-game tickets, select leg volume, edit lines and probabilities, audit correlated edges, and lock in tickets.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []

    # =========================================================================
    # 1. COMBO ENGINE CONFIGURATION (Modeled directly after Single Game Engine)
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 🤖 Select & Configure Multi-Leg Matchups")

        # ROW 1: League & Slate Scope
        r1_c1, r1_c2, r1_c3 = st.columns([2.5, 2.5, 2.0])
        league_choice = r1_c1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NFL", "NBA", "NCAA Football"],
            key="cb_static_league"
        )
        t_filter = r1_c2.selectbox(
            "Game Filter Status",
            options=["🌐 All Matchups", "⏳ Upcoming Games", "⚡ Live Games"],
            key="cb_static_filter"
        )
        num_legs = r1_c3.selectbox(
            "Target Number of Legs",
            options=[2, 3, 4, 5, 6, 7, 8],
            index=1,
            key="cb_num_legs_sel"
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
            return

        # ROW 2: Selection Mode (System Pick vs User Pick)
        selection_mode = st.radio(
            "Matchup Selection Method",
            ["🤖 Let the System Pick (Highest Model Discrepancies)", "🎯 Let Me Pick the Matchups"],
            horizontal=True,
            key="cb_selection_mode"
        )

        selected_matchups = []
        if "Let the System Pick" in selection_mode:
            # Sort slate by biggest line discrepancies and take top N games
            selected_matchups = sorted(pool, key=lambda g: abs(float(g.get("market_spread", 0))), reverse=True)[:num_legs]
            matched_summary = " • ".join([f"[{g.get('league')}] {g.get('away_short')}@{g.get('home_short')}" for g in selected_matchups])
            st.success(f"🤖 **System Selected ({len(selected_matchups)} Games):** {matched_summary}")
        else:
            game_labels = [f"[{gm.get('kickoff', 'Upcoming')}] [{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')}" for gm in pool]
            selected_indices = st.multiselect(
                f"🎯 Select exactly {num_legs} Matchups",
                options=range(len(game_labels)),
                format_func=lambda x: game_labels[x],
                default=list(range(min(num_legs, len(game_labels)))),
                key="cb_manual_game_multiselect"
            )
            selected_matchups = [pool[i] for i in selected_indices]

        # ROW 3: Strategy Profile
        strat_choice = st.selectbox(
            "Model Strategy Profile",
            [
                "⚖️ Balanced Edge (+EV Sweet Spot)",
                "🛡️ Safe Floor (High Win %, Low Drawdown)",
                "🚀 High Profit (Max Multiplier & Props)",
                "🎯 Mixed Tier Spectrum (Balanced Mix)"
            ],
            key="cb_static_strat"
        )

        if st.button("⚡ Generate Multi-Leg Combo Analysis & Slip", type="primary", use_container_width=True):
            if not selected_matchups:
                st.error("Please select at least one matchup.")
            else:
                st.session_state.combo_active_legs = generate_automated_combo_legs(selected_matchups, strat_choice, num_legs)
                st.rerun()

    # Manual / Custom Leg Adder
    with st.popover("➕ Add Custom Prop or Specific Leg Manually", use_container_width=True):
        st.markdown("**Draft a Custom Ticket Leg:**")
        cx1, cx2, cx3, cx4, cx5 = st.columns([2.0, 3.0, 1.8, 1.5, 1.5], vertical_alignment="bottom")
        c_match = cx1.text_input("Matchup", value="TEN @ CIN", key="cb_manual_cust_m")
        c_pick = cx2.text_input("Pick / Prop Description", value="Chase Brown Any Time TD", key="cb_manual_cust_p")
        c_type = cx3.selectbox("Category", ["Player Prop", "Game Total", "Point Spread", "Moneyline"], key="cb_manual_cust_t")
        c_prob = cx4.number_input("Win Prob (%)", min_value=5, max_value=99, value=58, step=1, key="cb_manual_cust_pr")
        if cx5.button("📥 Insert Leg", use_container_width=True, type="primary"):
            st.session_state.combo_active_legs.append({
                "matchup": c_match.strip(),
                "league": "PROP",
                "away_logo": DEFAULT_LOGO,
                "home_logo": DEFAULT_LOGO,
                "kickoff": "Custom",
                "picked_team": c_pick.strip(),
                "type": c_type,
                "side": "Over",
                "line": "1.0",
                "pick_text": c_pick.strip(),
                "prob": float(c_prob) / 100.0
            })
            st.rerun()

    legs = st.session_state.combo_active_legs
    if not legs:
        st.info("No legs loaded yet. Configure the engine above and click 'Generate Multi-Leg Combo Analysis & Slip' or add custom legs.")
        return

    # =========================================================================
    # 2. ACTIVE COMBO LEGS (INLINE EDITABLE FIELDS WITH MATCHUP BANNERS)
    # =========================================================================
    st.markdown(f"### 📋 Current Combo Legs ({len(legs)})")
    st.caption("Review, edit pick criteria, fine-tune lines and win probabilities in real-time below.")

    for idx, leg in enumerate(legs):
        with st.container(border=True):
            # Top Banner for each leg
            a_logo = leg.get("away_logo") or DEFAULT_LOGO
            h_logo = leg.get("home_logo") or DEFAULT_LOGO
            kickoff_str = leg.get("kickoff", "Scheduled")
            lg_str = leg.get("league", "SPORTS")

            h_col, del_col = st.columns([5.5, 1.0], vertical_alignment="center")
            h_col.markdown(f"""
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); font-weight:800; font-size:0.75rem; padding:2px 6px; border-radius:4px;">
                    {lg_str}
                </span>
                <span style="font-weight:700; font-size:0.95rem;">Leg #{idx + 1}: {leg.get('matchup')}</span>
                <span style="opacity:0.5; font-size:0.78rem;">• {kickoff_str}</span>
            </div>
            """, unsafe_allow_html=True)

            if del_col.button("🗑️", key=f"del_cb_leg_{idx}", help="Remove this leg", use_container_width=True):
                st.session_state.combo_active_legs.pop(idx)
                st.rerun()

            # Inline text edit fields
            ed1, ed2, ed3, ed4, ed5 = st.columns([2.5, 3.5, 1.5, 1.5, 2.0])
            leg["matchup"] = ed1.text_input("Matchup", value=leg.get("matchup", ""), key=f"cb_ed_m_{idx}")
            leg["pick_text"] = ed2.text_input("Pick Label", value=leg.get("pick_text", ""), key=f"cb_ed_txt_{idx}")
            leg["side"] = ed3.text_input("Side / Dir", value=leg.get("side", ""), key=f"cb_ed_sd_{idx}")
            leg["line"] = ed4.text_input("Line", value=str(leg.get("line", "")), key=f"cb_ed_ln_{idx}")
            
            cur_p_pct = int(round(float(leg.get("prob", 0.55)) * 100))
            new_p_pct = ed5.number_input("Win Prob (%)", min_value=5, max_value=99, value=cur_p_pct, step=1, key=f"cb_ed_pr_{idx}")
            leg["prob"] = float(new_p_pct) / 100.0

    if st.button("🗑️ Clear Entire Slip", key="btn_clear_cb_slip"):
        st.session_state.combo_active_legs = []
        st.rerun()

    st.markdown("---")

    # =========================================================================
    # 3. COMPOUND PROBABILITY & PARLAY ANALYTICS
    # =========================================================================
    compound_prob = 1.0
    for leg in legs:
        compound_prob *= float(leg.get("prob", 0.50))
    compound_prob = max(0.001, min(0.999, compound_prob))

    fair_multiplier = 1.0 / compound_prob
    fair_american = prob_to_american_odds(compound_prob)

    st.markdown("### 🎲 Combo Edge Analytics & Fair Value")
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

            # Strict Net Profit Calculation: Payout - Risk
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
