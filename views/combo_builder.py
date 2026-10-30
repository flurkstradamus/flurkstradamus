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

def detect_leg_conflicts(legs):
    """Detects internal game contradictions (e.g., both Over and Under on same total)."""
    warnings = []
    seen_totals = {}
    seen_mls = {}
    for idx, leg in enumerate(legs):
        m = leg.get("matchup", "").strip().lower()
        t = leg.get("type", "").lower()
        side = leg.get("side", "").lower()
        
        if "total" in t:
            if m in seen_totals and seen_totals[m] != side:
                warnings.append(f"⚠️ Conflict on **{leg.get('matchup')}**: Both Over and Under selected!")
            seen_totals[m] = side
        elif "moneyline" in t:
            if m in seen_mls and seen_mls[m] != leg.get("picked_team", ""):
                warnings.append(f"⚠️ Conflict on **{leg.get('matchup')}**: Opposing Moneylines selected!")
            seen_mls[m] = leg.get("picked_team", "")
    return warnings

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo & Correlated Parlay Builder")
    st.caption("Craft multi-sport parlays, edit lines and probabilities, audit correlated edges, and lock in tickets.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []

    # =========================================================================
    # 1. TOP TOOLBAR: SLATE INGESTION & QUICK INJECTORS
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### ⚡ Add Legs from Live Slate")
        
        t1, t2 = st.tabs(["🎯 Pull from Live Matchups", "✍️ Custom Prop / Line Drafter"])
        
        with t1:
            if not games_data:
                st.info("No active games found on the scoreboard.")
            else:
                c_lg, c_gm, c_mkt, c_btn = st.columns([1.5, 2.5, 2.5, 1.5], vertical_alignment="bottom")
                
                lg_pick = c_lg.selectbox("Sport / League", ["All", "NFL", "NBA", "NCAA Football"], key="cb_slate_lg")
                pool = games_data
                if lg_pick == "NFL": pool = [g for g in pool if g.get("league") == "NFL"]
                elif lg_pick == "NBA": pool = [g for g in pool if g.get("league") == "NBA"]
                elif lg_pick == "NCAA Football": pool = [g for g in pool if g.get("league") == "NCAA"]

                if pool:
                    opts = [f"[{g.get('league')}] {g.get('away_short')} @ {g.get('home_short')}" for g in pool]
                    sel_idx = c_gm.selectbox("Select Matchup", range(len(opts)), format_func=lambda i: opts[i], key="cb_slate_game_sel")
                    target_g = pool[sel_idx]
                    
                    is_nba = (target_g.get("league") == "NBA")
                    ou = round_half_point(target_g.get("market_ou", 224.5 if is_nba else 46.5))
                    spd = round_half_point(target_g.get("market_spread", -3.5))
                    fav_t = target_g.get("home_team") if spd < 0 else target_g.get("away_team")
                    dog_t = target_g.get("away_team") if spd < 0 else target_g.get("home_team")

                    # Preset options
                    presets = [
                        f"Game Total: Under {ou}",
                        f"Game Total: Over {ou}",
                        f"Point Spread: {fav_t} {spd:+.1f}",
                        f"Point Spread: {dog_t} {abs(spd):+.1f}",
                        f"Moneyline: {fav_t} ML",
                        f"Moneyline: {dog_t} ML"
                    ]
                    
                    # Add player prop preset
                    if is_nba:
                        shooters = get_live_nba_3pm_roster(target_g.get("home_id"), game_id=target_g.get("id"))
                        star = shooters[0][0] if shooters else "Primary Shooter"
                        presets.append(f"Prop: {star} 2+ 3-Pointers Made")
                    else:
                        rbs = get_live_football_roster(target_g.get("home_id") or target_g.get("home_short"), target_g.get("league"))
                        star_rb = rbs[0][0] if rbs else "Starting RB"
                        presets.append(f"Prop: {star_rb} Anytime Touchdown")

                    chosen_preset = c_mkt.selectbox("Target Market / Line", presets, key="cb_slate_mkt_sel")

                    if c_btn.button("➕ Inject Leg", use_container_width=True, type="primary"):
                        parsed_type = "Player Prop" if "Prop:" in chosen_preset else ("Game Total" if "Total" in chosen_preset else ("Point Spread" if "Spread" in chosen_preset else "Moneyline"))
                        side = "Under" if "Under" in chosen_preset else ("Over" if ("Over" in chosen_preset or "Prop:" in chosen_preset) else "Spread")
                        line_val = str(ou) if "Total" in chosen_preset else (str(spd) if "Spread" in chosen_preset else "0.0")
                        
                        st.session_state.combo_active_legs.append({
                            "matchup": f"{target_g.get('away_short')} @ {target_g.get('home_short')}",
                            "picked_team": fav_t if ("ML" in chosen_preset or "Spread" in chosen_preset) else target_g.get("home_team"),
                            "type": parsed_type,
                            "side": side,
                            "line": line_val,
                            "pick_text": chosen_preset.replace("Prop: ", "").replace("Game Total: ", "").replace("Point Spread: ", "").replace("Moneyline: ", ""),
                            "prob": 0.68 if "Under" in chosen_preset else (0.58 if "ML" in chosen_preset else 0.52)
                        })
                        st.toast("✅ Leg injected into combo!", icon="📥")
                        st.rerun()

        with t2:
            st.markdown("**Draft a Custom Leg (Prop, Alternate Spread, Futures):**")
            cx1, cx2, cx3, cx4, cx5 = st.columns([2.0, 3.0, 1.8, 1.5, 1.5], vertical_alignment="bottom")
            c_match = cx1.text_input("Matchup", value="TEN @ CIN", key="cb_cust_m")
            c_pick = cx2.text_input("Pick / Player Proposition", value="Chase Brown Any Time TD", key="cb_cust_p")
            c_type = cx3.selectbox("Category", ["Player Prop", "Game Total", "Point Spread", "Moneyline"], key="cb_cust_t")
            c_prob = cx4.number_input("Est. Win %", min_value=5, max_value=95, value=55, step=1, key="cb_cust_pr")
            
            if cx5.button("➕ Add Leg", use_container_width=True):
                st.session_state.combo_active_legs.append({
                    "matchup": c_match.strip(),
                    "picked_team": c_pick.strip(),
                    "type": c_type,
                    "side": "Over",
                    "line": "1.0",
                    "pick_text": c_pick.strip(),
                    "prob": float(c_prob) / 100.0
                })
                st.rerun()

    # =========================================================================
    # 2. ACTIVE TICKET LEGS (INLINE EDITABLE FIELDS)
    # =========================================================================
    legs = st.session_state.combo_active_legs
    
    if not legs:
        st.info("No legs on your parlay ticket yet. Use the tools above to inject legs.")
        return

    st.markdown(f"### 📋 Current Ticket Legs ({len(legs)})")
    
    # Conflict Checker Warnings
    conflicts = detect_leg_conflicts(legs)
    for conf in conflicts:
        st.warning(conf)

    for idx, leg in enumerate(legs):
        with st.container(border=True):
            h_col, del_col = st.columns([5.5, 1.0], vertical_alignment="center")
            h_col.markdown(f"**Leg #{idx + 1}** — <span style='background:rgba(255,255,255,0.06);padding:2px 8px;border-radius:4px;font-size:0.80rem;'>{leg.get('type', 'Custom')}</span>", unsafe_allow_html=True)
            
            if del_col.button("🗑️", key=f"del_combo_leg_{idx}", help="Remove leg", use_container_width=True):
                st.session_state.combo_active_legs.pop(idx)
                st.rerun()

            # Fully editable in-line controls
            ed1, ed2, ed3, ed4, ed5 = st.columns([2.5, 3.5, 1.5, 1.5, 2.0])
            leg["matchup"] = ed1.text_input("Matchup", value=leg.get("matchup", ""), key=f"ed_m_{idx}")
            leg["pick_text"] = ed2.text_input("Pick Description", value=leg.get("pick_text", ""), key=f"ed_txt_{idx}")
            leg["side"] = ed3.text_input("Direction", value=leg.get("side", ""), key=f"ed_sd_{idx}")
            leg["line"] = ed4.text_input("Line", value=str(leg.get("line", "")), key=f"ed_ln_{idx}")
            
            cur_prob_pct = int(round(float(leg.get("prob", 0.55)) * 100))
            new_prob_pct = ed5.number_input("Win Prob (%)", min_value=5, max_value=99, value=cur_prob_pct, step=1, key=f"ed_pr_{idx}")
            leg["prob"] = float(new_prob_pct) / 100.0

    # Clear All Button
    if st.button("🗑️ Clear Entire Slip", key="btn_clear_all_legs"):
        st.session_state.combo_active_legs = []
        st.rerun()

    st.markdown("---")

    # =========================================================================
    # 3. LIVE COMPOUND ANALYTICS & MATH ENGINE
    # =========================================================================
    compound_prob = 1.0
    for leg in legs:
        compound_prob *= float(leg.get("prob", 0.50))
    compound_prob = max(0.001, min(0.999, compound_prob))

    fair_multiplier = 1.0 / compound_prob
    fair_american = prob_to_american_odds(compound_prob)

    st.markdown("### 🎲 Ticket Edge Analytics & Fair Value")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compound Win Probability", f"{compound_prob * 100:.2f}%")
    m2.metric("Fair American Odds", fair_american)
    m3.metric("True Fair Multiplier", f"{fair_multiplier:.2f}x")
    m4.metric("Active Legs", len(legs))

    # =========================================================================
    # 4. SLIP LOCK-IN & FINANCIAL RECORDING
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 🔒 Lock In Combo Ticket Slip")
        with st.form("parlay_ticket_submission_form"):
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
