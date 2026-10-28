import streamlit as st

def render_dashboard(curr_user, active_uname, games_data, get_numeric_prob_fn):
    st.markdown('<div class="dashboard-header-desktop"><h3>📊 Personal Betting Dashboard</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-header-mobile">📊 Dashboard</div>', unsafe_allow_html=True)
    st.caption("Complete portfolio telemetry: settled P&L, live pending stakes, probability-modeled expected returns, and historical discipline.")

    clean_u = active_uname.lower()
    clean_disp = curr_user.get("display_name", "").strip().lower()

    my_bets = [b for b in st.session_state.saved_bets if str(b.get("user", "")).strip().lower() in [clean_u, clean_disp]]
    tot_placed = len(my_bets)

    if tot_placed == 0:
        with st.container(border=True):
            st.markdown("### 👋 Welcome! Let's Lock In Your First Edge")
            st.write("You haven't locked in any bet slips yet. Choose an engine below to start scanning live lines:")
            ob_c1, ob_c2 = st.columns(2)
            if ob_c1.button("⚡ Go to Single Game Engine", use_container_width=True):
                st.session_state.active_nav_page = "⚡ Single Game Engine"
                st.rerun()
            if ob_c2.button("🔗 Go to Multi-Leg Combo Builder", use_container_width=True):
                st.session_state.active_nav_page = "🔗 Multi-Leg Combo Builder"
                st.rerun()
        return

    won_bets = [b for b in my_bets if b.get("status") == "Won"]
    lost_bets = [b for b in my_bets if b.get("status") == "Lost"]
    pending_bets = [b for b in my_bets if b.get("status") == "Pending"]

    tot_won_dollars = sum(float(b.get("locked_profit", float(b.get("payout_dollars", b.get("payout", 0))) - float(b.get("risk_dollars", 0)))) for b in won_bets)
    tot_lost_dollars = sum(float(b.get("risk_dollars", 0)) for b in lost_bets)
    net_pl = tot_won_dollars - tot_lost_dollars
    tot_risk = sum(float(b.get("risk_dollars", 0)) for b in my_bets if b.get("status") in ["Won", "Lost"])
    roi = (net_pl / tot_risk * 100) if tot_risk > 0 else 0.0
    avg_stake = (sum(float(b.get("risk_dollars", 0)) for b in my_bets) / tot_placed) if tot_placed > 0 else 0.0

    pending_risk_dollars = sum(float(b.get("risk_dollars", 0)) for b in pending_bets)
    pending_max_profit = sum(float(b.get("locked_profit", float(b.get("payout_dollars", b.get("payout", 0))) - float(b.get("risk_dollars", 0)))) for b in pending_bets)

    pending_expected_profit = 0.0
    sum_weighted_prob = 0.0
    pending_live_count = 0
    pending_sched_count = 0

    for b in pending_bets:
        r_amt = float(b.get("risk_dollars", 0))
        p_amt = float(b.get("payout_dollars", b.get("payout", 0)))
        net_win = float(b.get("locked_profit", p_amt - r_amt))
        prob = get_numeric_prob_fn(b, games_data)

        ev_ticket = (prob * net_win) - ((1.0 - prob) * r_amt)
        pending_expected_profit += ev_ticket
        sum_weighted_prob += (prob * r_amt)

        m_check = None
        for g in games_data:
            if g.get("away_short") in b.get("matchup", "") and g.get("home_short") in b.get("matchup", ""):
                m_check = g
                break
        if m_check and m_check.get("state_text") != "pre" and m_check.get("period", 0) > 0 and not m_check.get("completed", False):
            pending_live_count += 1
        else:
            pending_sched_count += 1

    weighted_avg_prob = (sum_weighted_prob / max(pending_risk_dollars, 0.01)) * 100 if pending_risk_dollars > 0 else 0.0

    st.markdown("##### 💼 Realized Performance (Settled Slips)")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Bets Logged", tot_placed, help="All slips created under your profile.")
    k2.metric("Money Won", f"${tot_won_dollars:.2f}", help="Total net profit from settled winners.")
    k3.metric("Money Lost", f"${tot_lost_dollars:.2f}", help="Total staked capital lost on graded losses.")
    k4.metric("Net Profit / Loss", f"${net_pl:+.2f}", delta=f"{roi:+.1f}% ROI", help="Realized bankroll net profit/loss and return on investment.")

    st.markdown("##### ⏳ Active Book & Pending Analytics (In Play & Scheduled)")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Capital at Risk", f"${pending_risk_dollars:.2f}", f"{len(pending_bets)} Slips Active")
    p2.metric("Max Potential Profit", f"+${pending_max_profit:.2f}")
    p3.metric("Expected Profit (EV)", f"${pending_expected_profit:+.2f}", delta="Prob-Adjusted Return")
    p4.metric("Portfolio Win Expectancy", f"{weighted_avg_prob:.1f}%", f"{pending_live_count} Live | {pending_sched_count} Upcoming")

    st.markdown("##### 📈 Historical Discipline & Records")
    d1, d2, d3, d4 = st.columns(4)
    decided = len(won_bets) + len(lost_bets)
    win_pct = (len(won_bets) / decided * 100) if decided > 0 else 0.0
    d1.metric("Graded Win Rate", f"{win_pct:.1f}%", f"{len(won_bets)}W - {len(lost_bets)}L")
    d2.metric("Average Stake", f"${avg_stake:.2f}")
    d3.metric("Pending In Play", f"{len(pending_bets)} tickets")

    types_count = {}
    for b in my_bets:
        t = b.get("bet_category", b.get("type", "Single"))
        types_count[t] = types_count.get(t, 0) + 1
    most_common_type = max(types_count, key=types_count.get) if types_count else "None"
    d4.metric("Favorite Market", most_common_type)

    st.markdown("---")
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("##### 🚀 Top Winner")
        if won_bets:
            best_win = max(won_bets, key=lambda x: float(x.get("locked_profit", float(x.get("payout_dollars", x.get("payout", 0))) - float(x.get("risk_dollars", 0)))))
            profit = float(best_win.get("locked_profit", float(best_win.get("payout_dollars", best_win.get("payout", 0))) - float(best_win.get("risk_dollars", 0))))
            payout_show = float(best_win.get("payout_dollars", best_win.get("payout", 0)))
            st.success(f"{best_win.get('bet')} on `{best_win.get('matchup')}`\n\nProfit: **+${profit:.2f}** | Return: ${payout_show:.2f}")
        else:
            st.info("No graded winning slips yet.")
    with h2:
        st.markdown("##### 💀 Toughest Beat")
        if lost_bets:
            worst_loss = max(lost_bets, key=lambda x: float(x.get("risk_dollars", 0)))
            st.error(f"{worst_loss.get('bet')} on `{worst_loss.get('matchup')}`\n\nStake Lost: **-${float(worst_loss.get('risk_dollars', 0)):.2f}**")
        else:
            st.info("No recorded losses.")
