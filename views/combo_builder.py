import streamlit as st
from datetime import datetime
from database import save_all_storage
from sports.football import round_half_point

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Cross-Sport Combo Builder (Up to 12 Legs)")
    st.caption("Automated cross-slate parlay scanner, compound probability calculator, and slip builder.")

    c1, c2 = st.columns([1, 2])
    t_filter = c1.selectbox("Filter", ["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"])
    q_filter = c2.text_input("🔍 Search", placeholder="e.g. Celtics, Lakers, Chiefs...")

    pool = games_data
    if t_filter == "⏳ Upcoming Games":
        pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
    elif t_filter == "⚡ Live Games":
        pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]

    if q_filter.strip():
        q = q_filter.strip().lower()
        pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g["home_short"].lower() or q in g["away_short"].lower()]

    if not pool:
        st.info("No matchups found.")
        return

    choices = [f"[{gm['kickoff']}] [{gm['league']}] {gm['away_short']} @ {gm['home_short']}" for gm in pool]

    if not st.session_state.combo_active_legs:
        st.session_state.combo_active_legs = []
        for j in range(min(3, len(pool))):
            st.session_state.combo_active_legs.append({
                "matchup_idx": j, "type": "Game Total", "side": "Under",
                "line": round_half_point(pool[j].get("market_ou", 47.5)), "picked_team": pool[j]["home_team"]
            })

    ctrl1, ctrl2 = st.columns([3, 1], vertical_alignment="center")
    ctrl1.markdown(f"#### Active Slip ({len(st.session_state.combo_active_legs)} Legs)")
    if ctrl2.button("➕ Add Leg", use_container_width=True, disabled=(len(st.session_state.combo_active_legs) >= 12 or not pool)):
        next_i = min(len(st.session_state.combo_active_legs), len(pool) - 1)
        st.session_state.combo_active_legs.append({
            "matchup_idx": next_i, "type": "Game Total", "side": "Under",
            "line": round_half_point(pool[next_i].get("market_ou", 47.5)), "picked_team": pool[next_i]["home_team"]
        })
        st.rerun()

    combo_legs = []
    compound_prob = 1.0

    for i, leg in enumerate(st.session_state.combo_active_legs):
        with st.container(border=True):
            safe_idx = min(max(leg.get("matchup_idx", 0), 0), len(choices) - 1)
            sel_m = st.selectbox(f"Leg {i+1} Matchup", range(len(choices)), index=safe_idx, format_func=lambda x: choices[x], key=f"cb_m_{i}")
            leg["matchup_idx"] = sel_m
            gm = pool[sel_m]

            w_type = st.radio(f"Market (Leg {i+1})", ["Game Total", "Straight Up Winner"], horizontal=True, index=0 if leg["type"] == "Game Total" else 1, key=f"cb_wt_{i}")
            leg["type"] = w_type

            if w_type == "Game Total":
                b1, b2 = st.columns(2)
                s_side = b1.selectbox("Side", ["Under", "Over"], index=0 if leg.get("side", "Under") == "Under" else 1, key=f"cb_s_{i}")
                s_line = b2.number_input("Line", value=float(round_half_point(leg.get("line", gm.get("market_ou", 47.5)))), step=0.5, key=f"cb_l_{i}")
                leg["side"], leg["line"] = s_side, s_line
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {s_side} {s_line:.1f}", "prob": 0.52})
            else:
                b1, b2 = st.columns(2)
                winner = b1.selectbox("Winner", [gm["home_team"], gm["away_team"]], key=f"cb_win_{i}")
                leg["picked_team"] = winner
                combo_legs.append({"desc": f"{gm['away_short']} @ {gm['home_short']}: {winner} ML", "prob": 0.50})
            compound_prob *= 0.52

    st.metric("Compound Ticket Win Expectancy", f"{compound_prob * 100:.1f}%")

    with st.form("save_combo_form"):
        r_c, p_c = st.columns(2)
        c_risk = r_c.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
        c_payout = p_c.number_input("Payout ($)", min_value=1.0, value=50.0, step=10.0)
        if st.form_submit_button(f"Lock In {len(combo_legs)}-Leg Ticket", use_container_width=True):
            parsed_legs = [
                {
                    "matchup": f"{pool[min(item['matchup_idx'], len(pool)-1)]['away_short']} @ {pool[min(item['matchup_idx'], len(pool)-1)]['home_short']}",
                    "type": item["type"], "side": item.get("side", ""), "line": round_half_point(item.get("line", 0.0)),
                    "picked_team": item.get("picked_team", "")
                } for item in st.session_state.combo_active_legs
            ]
            c_tkt = {
                "id": str(datetime.now().timestamp()),
                "user": curr_user.get("display_name", active_uname),
                "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                "type": f"{len(combo_legs)}-Leg Combo", "bet_category": "Combo",
                "matchup": " | ".join([cl["desc"] for cl in combo_legs]),
                "bet": f"{len(combo_legs)} Legs Parlay",
                "risk_dollars": float(c_risk), "payout_dollars": float(c_payout),
                "locked_profit": float(c_payout) - float(c_risk),
                "win_prob": f"{compound_prob * 100:.1f}%", "status": "Pending",
                "parsed_legs": parsed_legs
            }
            st.session_state.saved_bets.insert(0, c_tkt)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success("Combo slip locked in!")
            st.rerun()
