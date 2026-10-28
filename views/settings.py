import streamlit as st
import random
from database import hash_password, save_all_storage

def render_settings(curr_user, active_uname):
    st.subheader("⚙️ Account Settings & Profile Management")
    with st.form("account_settings_form"):
        new_display = st.text_input("Display Name", value=curr_user.get("display_name", ""))
        new_email = st.text_input("Email Address", value=curr_user.get("email", ""))
        new_team = st.text_input("Favorite Team", value=curr_user.get("favorite_team", "Multi-Sport"))
        new_avatar = st.text_input("Profile Avatar URL", value=curr_user.get("avatar_url", ""))
        new_bio = st.text_area("Short Bio", value=curr_user.get("bio", "Sports investor & strategist."))
        pub_lead = st.toggle("Show My Profile on Public Leaderboard", value=curr_user.get("is_public", True))
        share_fd = st.toggle("Publish My Slips to Live Squad Feed", value=curr_user.get("share_feed", True))
        p_change1 = st.text_input("New Password", type="password")
        p_change2 = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Save Account Settings", use_container_width=True):
            if new_display.strip(): curr_user["display_name"] = new_display.strip()
            if new_email.strip(): curr_user["email"] = new_email.strip()
            curr_user["favorite_team"] = new_team.strip()
            curr_user["avatar_url"] = new_avatar.strip()
            curr_user["bio"] = new_bio.strip()
            curr_user["is_public"] = pub_lead
            curr_user["share_feed"] = share_fd
            if p_change1 and p_change1 == p_change2 and len(p_change1) >= 4:
                curr_user["password_hash"] = hash_password(p_change1)
            save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
            st.success("Settings updated!")
            st.rerun()

def render_support(curr_user, active_uname, is_admin, get_current_et_time_fn):
    st.subheader("📩 Feedback, Support & Ticket Desk")
    tab1, tab2 = st.tabs(["📝 Submit a Ticket", "📂 My Ticket History"])
    with tab1:
        with st.form("support_form"):
            cat = st.selectbox("Category", ["🏀 NBA Request", "🏈 Football Request", "🐛 Bug Report", "💡 Feature Suggestion", "💬 General"])
            pri = st.select_slider("Priority", ["Low", "Medium", "High", "Critical"], value="Medium")
            sub = st.text_input("Subject")
            det = st.text_area("Details")
            if st.form_submit_button("Submit Support Ticket", use_container_width=True):
                if sub and det:
                    tkt = {
                        "id": f"TKT-{random.randint(1000, 9999)}", "user": curr_user.get("display_name", active_uname),
                        "username": active_uname, "date": get_current_et_time_fn().strftime("%Y-%m-%d %I:%M %p ET"),
                        "category": cat, "priority": pri, "subject": sub, "description": det, "status": "Open", "admin_reply": None
                    }
                    st.session_state.support_tickets.insert(0, tkt)
                    save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                    st.success("Ticket submitted!")
                    st.rerun()
    with tab2:
        tkts = [t for t in st.session_state.support_tickets if t.get("username") == active_uname or is_admin]
        if not tkts:
            st.info("No tickets recorded.")
        else:
            for t in tkts:
                with st.container(border=True):
                    st.write(f"**[{t.get('id')}] {t.get('subject')}** | Status: **{t.get('status')}**")
                    st.write(t.get("description"))
                    if t.get("admin_reply"):
                        st.info(f"Admin Reply: {t.get('admin_reply')}")
