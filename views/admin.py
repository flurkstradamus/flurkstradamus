import streamlit as st
from database import get_admin_credentials, save_all_storage

def render_admin():
    st.subheader("🛡️ Commissioner Admin Console")
    st.caption("Inspect user activity, audit bet tickets, review search logs, manage accounts, and reply to support tickets.")
    users = st.session_state.user_accounts
    st.write(f"Total Registered Users: **{len(users)}**")

    t1, t2 = st.tabs(["👤 User Accounts & Bet Management", "📩 Inbound Support Tickets"])
    with t1:
        u_list = list(users.keys())
        sel_u = st.selectbox("Select User", options=u_list, format_func=lambda x: f"{users[x].get('display_name', x)} (@{x})")
        if sel_u:
            u_info = users[sel_u]
            with st.container(border=True):
                st.markdown(f"### 👤 User Dossier: **{u_info.get('display_name')}** (`@{sel_u}`)")
                c1, c2, c3 = st.columns(3)
                c1.write(f"📧 Email: `{u_info.get('email')}`\n\n🏈 Team: `{u_info.get('favorite_team')}`")
                c2.write(f"🗓️ Joined: `{u_info.get('created_at')}`\n\n⏱️ Last: `{u_info.get('last_login')}`")
                c3.write(f"Status: **{'🚫 BANNED' if u_info.get('is_banned') else '✅ Active'}**\n\nVerified: **{'✅ Yes' if u_info.get('is_verified', True) else '❌ No'}**")

                u_bets = [b for b in st.session_state.saved_bets if str(b.get("user", "")).lower() in [sel_u.lower(), u_info.get("display_name", "").lower()]]
                st.metric("Total Tickets Placed", len(u_bets))

                admin_cred = get_admin_credentials()
                if sel_u != admin_cred["username"].lower():
                    a1, a2 = st.columns(2)
                    if a1.button("✅ Unban" if u_info.get("is_banned") else "🚫 Ban", key=f"ban_{sel_u}"):
                        u_info["is_banned"] = not u_info.get("is_banned", False)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                        st.rerun()
                    if a2.button("🗑️ Delete User Permanently", key=f"del_{sel_u}"):
                        users.pop(sel_u)
                        save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                        st.rerun()

    with t2:
        if not st.session_state.support_tickets:
            st.info("No open support tickets.")
        else:
            for tkt in st.session_state.support_tickets:
                with st.container(border=True):
                    st.write(f"**[{tkt.get('id')}] {tkt.get('subject')}** by `{tkt.get('user')}` | Status: `{tkt.get('status')}`")
                    st.write(tkt.get("description"))
                    with st.form(f"reply_{tkt.get('id')}"):
                        rep = st.text_input("Reply", value=tkt.get("admin_reply") or "")
                        stt = st.selectbox("Status", ["Open", "In Review", "Resolved"], index=0 if tkt.get("status")=="Open" else (1 if tkt.get("status")=="In Review" else 2))
                        if st.form_submit_button("Save"):
                            tkt["admin_reply"] = rep
                            tkt["status"] = stt
                            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, users, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                            st.rerun()
