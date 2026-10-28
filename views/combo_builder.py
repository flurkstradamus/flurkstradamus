import streamlit as st
from datetime import datetime
from database import save_all_storage
from sports.football import round_half_point
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Cross-Sport Combo Builder (Up to 12 Legs)")
    st.caption("Automated cross-slate parlay scanner, compound probability calculator, and slip builder.")

    # Top-Level AI Automation & Strategy Controls (Dropdown Selection)
    with st.container(border=True):
        st.markdown("#### 🤖 AI Combo Optimizer & Auto-Assembler")
        c_top1, c_top2 = st.columns(2)
        
        leg_options = list(range(2, 13))
        current_len = len(st.session_state.combo_active_legs) if st.session_state.combo_active_legs else 3
        default_leg_idx = leg_options.index(max(2, min(current_len, 12)))

        target_legs = c_top1.selectbox(
            "Target Number of Legs",
            options=leg_options,
            index=default_leg_idx,
            format_func=lambda x: f"{x} Legs",
            key="combo_target_legs_select"
        )

        strat_options = [
            "🛡️ Safe Floor (High Win %, Low Drawdown)",
            "⚖️ Balanced Edge (+EV Sweet Spot)",
            "🚀 High Profit (Max Multiplier & Longshots)"
        ]
        strat_choice = c_top2.selectbox(
            "Combo Strategy Profile",
            options=strat_options,
            index=1,
            key="combo_strat_profile_select"
        )

        col_filter1, col_filter2, col_gen = st.columns([1.5, 2, 1.5], vertical_alignment="bottom")
        t_filter = col_filter1.selectbox("Filter Games", ["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"], key="combo_t_filter")
        q_filter = col_filter2.text_input("🔍 Search Slate", placeholder="e.g. Celtics, Lakers, Chiefs...", key="combo_q_filter")

        pool = games_data
        if t_filter == "⏳ Upcoming Games":
            pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
        elif t_filter == "⚡ Live Games":
            pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]

        if q_filter.strip():
            q = q_filter.strip().lower()
            pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g["home_short"].lower() or q in g["away_short"].lower()]

        if col_gen.button("⚡ Auto-Generate Combo", use_container_width=True, disabled=len(pool) == 0):
            new_legs = []
            selected_games = pool[:target_legs]
            for j, g_item in enumerate(selected_games):
                is_nba = (g_item.get("league") == "NBA")
                line_val = round_half_point(g_item.get("market_ou", 224.5 if is_nba else 47.5))
                
                # Apply strategy bias
                if "Safe Floor" in strat_choice:
                    side_val = "Under"
                    line_val = round_half_point(line_val + (6.5 if is_nba else 3.5))
                elif "High Profit" in strat_choice:
                    side_val = "Over" if j % 2 == 0 else "Under"
                    line_val = round_half_point(line_val + (-4.5 if is_nba else -2.5))
                else:
                    side_val = "Under"

                new_legs.append({
                    "matchup_idx": pool.index(g_item),
                    "type": "Game Total",
                    "side": side_val,
                    "line": line_val,
                    "picked_team": g_item["home_team"]
                })
            st.session_state.combo_active_legs = new_legs
            st.rerun()

    if not pool:
        st.info("No matchups found matching your current filter.")
        return

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in pool]

    if not st.session_state.combo_active_legs:
        st.session_state.combo_active_legs = []
        for j in range(min(target_legs, len(pool))):
            st.session_state.combo_active_legs.append({
                "matchup_idx": j,
                "type": "Game Total",
                "side": "Under",
                "line": round_half_point(pool[j].get("market_ou", 47.5)),
                "picked_team": pool[j]["home_team"]
            })

    ctrl1, ctrl2, ctrl3 = st.columns([3, 1, 1], vertical_alignment="center")
    ctrl1.markdown(f"#### Active Ticket Slip ({len(st.session_state.combo_active_legs)} Legs)")
    if ctrl2.button("➕ Add Leg", use_container_width=True, disabled=(len(st.session_state.combo_active_legs) >= 12 or not pool)):
        next_i = min(len(st.session_state.combo_active_legs), len(pool) - 1)
        st.session_state.combo_active_legs.append({
            "matchup_idx": next_i,
            "type": "Game Total",
            "side": "Under",
            "line": round_half_point(pool[next_i].get("market_ou", 47.5)),
            "picked_team": pool[next_i]["home_team"]
        })
        st.rerun()

    if ctrl3.button("🗑️ Clear Legs", use_container_width=True):
        st.session_state.combo_active_legs = []
        st.rerun()

    combo_legs = []
    compound_prob = 1.0

    for i, leg in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            col_hdr1, col_hdr2 = st.columns([5, 1])
            col_hdr1.markdown(f"**Leg #{i+1}**")
            if col_hdr2.button("❌", key=f"del_leg_{i}", help="Remove leg"):
                st.session_state.combo_active_legs.pop(i)
                st.rerun()

            safe_idx = min(max(leg.get("matchup_idx", 0), 0), len(choices) - 1)
            sel_m = st.selectbox(f"Matchup", range(len(choices)), index=safe_idx, format_func=lambda x: choices[x], key=f"cb_m_{i}")
            leg["matchup_idx"] = sel_m
            gm = pool[sel_m]
            is_nba = (gm.get("league") == "NBA")

            w_type = st.radio(f"Market", ["Game Total", "Straight Up Winner (Moneyline)"], horizontal=True, index=0 if leg["type"] == "Game Total" else 1, key=f"cb_wt_{i}")
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
            else:
                b1, b2 = st.columns(2)
                winner = b1.selectbox("Winner", [gm["home_team"], gm["away_team"]], key=f"cb_win_{i}")
                leg["picked_team"] = winner

                add_score = 40 if is_nba else 14
                h_prob = calculate_moneyline_prob(gm["home_score"] + add_score, gm["away_score"] + add_score, gm.get("home_record", "0-0"), gm.get("away_record", "0-0"))
                leg_prob = h_prob if winner == gm["home_team"] else (1.0 - h_prob)
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {winner} ML", "prob": leg_prob})

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
                    "picked_team": item.get("picked_team", "")
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
                "notes": f"{len(combo_legs)}-Leg Cross-Sport Combo [{strat_choice.split()[1]}]"
            }
            st.session_state.saved_bets.insert(0, c_tkt)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.toast(f"🎉 Locked in {len(combo_legs)}-leg combo!", icon="✅")
            st.session_state.active_nav_page = "📜 Locked Bets History"
            st.rerun()
