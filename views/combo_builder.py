import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster, get_live_nba_3pm_roster

def prob_to_american_odds(prob):
    """Converts a probability (0.01 - 0.99) into American Odds string (+150, -110)."""
    p = max(0.01, min(0.99, float(prob)))
    if p >= 0.50:
        odds = int(round(-100.0 * (p / (1.0 - p))))
        return f"{odds}"
    else:
        odds = int(round(100.0 * ((1.0 - p) / p)))
        return f"+{odds}"

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo & Parlay Builder")
    st.caption("Construct correlated tickets, edit leg criteria, calculate compound probabilities, and verify edge mathematics.")

    if "combo_legs" not in st.session_state:
        st.session_state.combo_legs = []

    # Quick Quick-Add Bar from Slate
    with st.expander("⚡ Quick-Add Legs from Available Matchups", expanded=(len(st.session_state.combo_legs) == 0)):
        if not games_data:
            st.info("No active games on the slate to pull automatic legs from.")
        else:
            q_cols = st.columns([2, 2, 2])
            q_league = q_cols[0].selectbox("League", ["All", "NFL", "NBA"], key="cb_q_league")
            
            avail_pool = games_data
            if q_league == "NFL":
                avail_pool = [g for g in avail_pool if g.get("league") == "NFL"]
            elif q_league == "NBA":
                avail_pool = [g for g in avail_pool if g.get("league") == "NBA"]

            if avail_pool:
                gm_opts = [f"[{g.get('league')}] {g.get('away_short')} @ {g.get('home_short')}" for g in avail_pool]
                sel_gm_idx = q_cols[1].selectbox("Select Matchup", range(len(gm_opts)), format_func=lambda i: gm_opts[i], key="cb_q_game")
                target_g = avail_pool[sel_gm_idx]
                
                is_nba = (target_g.get("league") == "NBA")
                ou = target_g.get("market_ou", 224.5 if is_nba else 46.5)
                spd = target_g.get("market_spread", -3.5)
                fav_t = target_g.get("home_team") if spd < 0 else target_g.get("away_team")

                leg_type = q_cols[2].selectbox("Preset Market", [
                    f"Game Total: Under {ou}",
                    f"Game Total: Over {ou}",
                    f"Spread: {fav_t} {spd}",
                    f"Moneyline: {fav_t} ML"
                ], key="cb_q_mkt")

                if st.button("➕ Add Selected Preset Leg", use_container_width=True):
                    parsed_side = "Under" if "Under" in leg_type else ("Over" if "Over" in leg_type else "Cover")
                    parsed_line = ou if "Total" in leg_type else spd
                    st.session_state.combo_legs.append({
                        "matchup": f"{target_g.get('away_short')} @ {target_g.get('home_short')}",
                        "picked_team": fav_t,
                        "type": "Game Total" if "Total" in leg_type else ("Point Spread" if "Spread" in leg_type else "Moneyline"),
                        "side": parsed_side,
                        "line": str(parsed_line),
                        "pick_text": leg_type,
                        "prob": 0.65 if "Under" in leg_type else 0.55
                    })
                    st.toast("✅ Leg added to parlay ticket!", icon="➕")
                    st.rerun()

    # Manual Add Leg Custom Bar
    with st.popover("✍️ Add Custom Prop or Player Leg", use_container_width=True):
        st.markdown("**Custom Ticket Leg**")
        c_m = st.text_input("Matchup / Game", value="TEN @ CIN")
        c_p = st.text_input("Player / Team Pick", value="Chase Brown Any Time TD")
        c_t = st.selectbox("Market Category", ["Player Prop", "Game Total", "Point Spread", "Moneyline", "Other"])
        c_prob = st.slider("Estimated Model Probability (%)", min_value=10, max_value=95, value=58, step=1)
        if st.button("📥 Insert Custom Leg", use_container_width=True, type="primary"):
            st.session_state.combo_legs.append({
                "matchup": c_m.strip(),
                "picked_team": c_p.strip(),
                "type": c_t,
                "side": "Over",
                "line": "1.0",
                "pick_text": c_p.strip(),
                "prob": float(c_prob) / 100.0
            })
            st.rerun()

    st.markdown("---")

    # If no legs exist
    if not st.session_state.combo_legs:
        st.info("Your ticket is empty. Add legs using the Quick-Add slate or the Custom Leg tool above.")
        return

    # Itemized Leg Review and Edit Section
    st.markdown(f"### 📋 Parlay Legs ({len(st.session_state.combo_legs)})")
    st.caption("Fine-tune specific lines, side directions, and pick text below.")

    for idx, leg in enumerate(st.session_state.combo_legs):
        with st.container(border=True):
            r1, r2 = st.columns([5, 1], vertical_alignment="center")
            r1.markdown(f"**Leg #{idx + 1}** — `{leg.get('type', 'Prop')}`")
            if r2.button("🗑️", key=f"cb_del_leg_{idx}", help="Remove leg", use_container_width=True):
                st.session_state.combo_legs.pop(idx)
                st.rerun()

            # Inline text fields to modify leg criteria
            c_ed1, c_ed2, c_ed3, c_ed4 = st.columns([2.5, 3.0, 1.5, 1.5])
            leg["matchup"] = c_ed1.text_input("Matchup", value=leg.get("matchup", ""), key=f"cb_m_{idx}")
            leg["pick_text"] = c_ed2.text_input("Pick Label", value=leg.get("pick_text", ""), key=f"cb_txt_{idx}")
            leg["side"] = c_ed3.text_input("Side / Dir", value=leg.get("side", ""), key=f"cb_sd_{idx}")
            leg["line"] = c_ed4.text_input("Line", value=str(leg.get("line", "")), key=f"cb_ln_{idx}")

            # Leg Probability Slider
            cur_p = int(round(float(leg.get("prob", 0.55)) * 100))
            new_p = st.slider(f"Leg #{idx+1} Probability: {cur_p}%", min_value=5, max_value=95, value=cur_p, step=1, key=f"cb_p_slide_{idx}")
            leg["prob"] = float(new_p) / 100.0

    st.markdown("---")

    # Mathematical Analytics & Probability Engine
    st.markdown("### 🎲 Parlay Analytics & Expected Value")
    
    # Calculate Compound Probability
    compound_prob = 1.0
    for leg in st.session_state.combo_legs:
        compound_prob *= float(leg.get("prob", 0.50))
    compound_prob = max(0.001, min(0.999, compound_prob))

    fair_multiplier = 1.0 / compound_prob
    fair_american = prob_to_american_odds(compound_prob)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compound Win Probability", f"{compound_prob * 100:.2f}%")
    m2.metric("Fair American Odds", fair_american)
    m3.metric("True Dec Multiplier", f"{fair_multiplier:.2f}x")
    m4.metric("Active Legs", len(st.session_state.combo_legs))

    # Risk & Payout Configuration Slip
    with st.container(border=True):
        st.markdown("#### 🎟️ Lock In Multi-Leg Slip")
        with st.form("combo_lock_slip_form"):
            c_r, c_p = st.columns(2)
            default_risk = 5.0
            default_payout = round(default_risk * fair_multiplier, 2)
            
            risk_val = c_r.number_input("Wager Risk Amount ($)", min_value=1.0, value=float(default_risk), step=1.0)
            payout_val = c_p.number_input("Total Potential Payout ($)", min_value=1.0, value=float(default_payout), step=1.0)

            # Net Profit Calculation: Payout - Risk
            net_profit = float(payout_val) - float(risk_val)
            expected_val = (compound_prob * float(payout_val)) - float(risk_val)
            ev_color = "#4ade80" if expected_val >= 0 else "#ef4444"

            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:10px 14px; border-radius:8px; margin-top:6px; margin-bottom:12px; border:1px solid rgba(255,255,255,0.08);">
                <div>Net Profit: <strong style="color:#4ade80;">+${net_profit:.2f}</strong> (ROI: {((net_profit/max(0.01, risk_val))*100):.1f}%)</div>
                <div>Model EV: <strong style="color:{ev_color};">{expected_val:+.2f}</strong></div>
            </div>
            """, unsafe_allow_html=True)

            notes = st.text_input("Ticket Notes / Strategy Tag", value=f"{len(st.session_state.combo_legs)}-Leg Correlated Parlay")

            if st.form_submit_button("🔒 Lock In Parlay Ticket", type="primary", use_container_width=True):
                # Format pick summary string
                summary_picks = ", ".join([l.get("pick_text", "") for l in st.session_state.combo_legs[:3]])
                if len(st.session_state.combo_legs) > 3:
                    summary_picks += f" +{len(st.session_state.combo_legs) - 3} more"

                combo_ticket = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Combo",
                    "bet_category": "Combo",
                    "matchup": f"{len(st.session_state.combo_legs)}-Leg Parlay",
                    "bet": f"{len(st.session_state.combo_legs)}-Leg Combo: {summary_picks}",
                    "risk_dollars": float(risk_val),
                    "payout_dollars": float(payout_val),
                    "payout": float(payout_val),
                    "locked_profit": float(net_profit),
                    "win_prob": f"{compound_prob * 100:.1f}%",
                    "status": "Pending",
                    "notes": notes,
                    "parsed_legs": [
                        {
                            "matchup": l.get("matchup"),
                            "picked_team": l.get("picked_team"),
                            "type": l.get("type"),
                            "side": l.get("side"),
                            "line": l.get("line"),
                            "prob": l.get("prob")
                        }
                        for l in st.session_state.combo_legs
                    ]
                }

                st.session_state.saved_bets.insert(0, combo_ticket)
                save_all_storage(
                    st.session_state.saved_bets,
                    st.session_state.chat_messages,
                    st.session_state.user_accounts,
                    st.session_state.banned_emails,
                    st.session_state.game_snapshots,
                    st.session_state.support_tickets
                )
                st.session_state.combo_legs = []
                st.toast("🎉 Parlay ticket locked in and saved to history!", icon="🔒")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
