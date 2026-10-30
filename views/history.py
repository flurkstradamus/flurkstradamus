import streamlit as st
from database import save_all_storage

def render_history(curr_user, active_uname, is_admin, games_data, render_ticket_card_fn):
    st.subheader("📜 Locked Bets History & Tickets")
    st.caption("Review, edit amounts, track settlement status, and evaluate historical bankroll performance.")

    all_bets = st.session_state.saved_bets
    user_bets = [b for b in all_bets if is_admin or (b.get("user", "").lower() == active_uname.lower() or b.get("user") == curr_user.get("display_name"))]

    if not user_bets:
        st.info("No bets have been locked yet. Use the Single Game Engine or Combo Builder to create and track bets.")
        return

    # Aggregate Analytics
    total_wagered = sum(float(b.get("risk_dollars", 0.0)) for b in user_bets)
    total_payout = sum(float(b.get("payout_dollars", b.get("payout", 0.0))) for b in user_bets if b.get("status") == "Won")
    net_profit = sum(float(b.get("locked_profit", float(b.get("payout_dollars", 0.0)) - float(b.get("risk_dollars", 0.0)))) for b in user_bets if b.get("status") == "Won")
    
    # Add negative risk for lost bets
    lost_risk = sum(float(b.get("risk_dollars", 0.0)) for b in user_bets if b.get("status") == "Lost")
    total_net = net_profit - lost_risk

    # Analytics Bar
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Tickets", len(user_bets))
    c2.metric("Total Risked", f"${total_wagered:.2f}")
    c3.metric("Total Won Payout", f"${total_payout:.2f}")
    c4.metric("Realized Net Profit", f"${total_net:+.2f}", delta=f"{total_net:+.2f}")

    st.markdown("---")

    # Filter Bar
    f1, f2 = st.columns([2, 2])
    status_filter = f1.selectbox("Filter Status", ["All", "Pending", "Won", "Lost"], key="hist_status_filter")
    type_filter = f2.selectbox("Filter Category", ["All", "Single", "Combo"], key="hist_type_filter")

    display_bets = user_bets
    if status_filter != "All":
        display_bets = [b for b in display_bets if b.get("status") == status_filter]
    if type_filter != "All":
        display_bets = [b for b in display_bets if (type_filter in b.get("type", "") or type_filter in b.get("bet_category", ""))]

    if not display_bets:
        st.info("No tickets match the selected filters.")
        return

    # Render each ticket with editing capability
    for b in display_bets:
        real_idx = all_bets.index(b)
        render_ticket_card_fn(b, real_idx, games_data, can_delete=True)
