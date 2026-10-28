import streamlit as st
from database import auto_resolve_bets

def render_history(curr_user, active_uname, is_admin, games_data, render_ticket_card_fn):
    st.subheader(f"📜 {curr_user.get('display_name', active_uname)}'s Locked Bets")
    st.caption("Active slips with live in-game win probabilities, team logos, and live scoreboard telemetry.")

    c1, c2 = st.columns([3, 1])
    show_all = c2.toggle("Show All Squad Bets", value=False)
    clean_u = active_uname.lower()
    clean_disp = curr_user.get("display_name", "").strip().lower()

    my_tickets = []
    for b in st.session_state.saved_bets:
        if show_all:
            my_tickets.append(b)
        else:
            owner = str(b.get("user", "")).strip().lower()
            if (owner in [clean_u, clean_disp]) or (is_admin and owner in [clean_u, "admin"]):
                my_tickets.append(b)

    c1.write(f"Showing **{len(my_tickets)}** ticket(s).")
    if c1.button("⚡ Grade Finals", use_container_width=True):
        if auto_resolve_bets(st.session_state.saved_bets, games_data, st.session_state.chat_messages, st.session_state.game_snapshots, st.session_state.support_tickets):
            st.success("Updated tickets!")
            st.rerun()

    if not my_tickets:
        st.info("No tickets recorded yet.")
    else:
        for b in my_tickets:
            render_ticket_card_fn(b, st.session_state.saved_bets.index(b), games_data, can_delete=True)
