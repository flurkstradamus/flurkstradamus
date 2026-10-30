import streamlit as st
from config import DEFAULT_LOGO
from database import load_game_snapshots, calculate_pace_drift_factor

def render_war_room(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🏟️ Live Command War Room")
    st.caption("Real-time game tracking, official telemetry, quarter-by-quarter progressions, and projection drift analytics.")

    if not games_data:
        st.info("No active games available on the board.")
        return

    # Game Filter
    c_f1, c_f2 = st.columns([2, 2])
    l_filter = c_f1.selectbox("Filter League", ["All", "NBA", "NFL", "NCAA"], key="wr_league_filter")
    state_filter = c_f2.selectbox("Matchup Status", ["⚡ Live & In-Progress", "⏳ Upcoming Matchups", "🌐 All Board Games"], key="wr_state_filter")

    disp_games = games_data
    if l_filter != "All":
        disp_games = [g for g in disp_games if g.get("league") == l_filter]

    if state_filter == "⚡ Live & In-Progress":
        disp_games = [g for g in disp_games if g.get("state_text") != "pre" and not g.get("completed", False)]
    elif state_filter == "⏳ Upcoming Matchups":
        disp_games = [g for g in disp_games if g.get("state_text") == "pre" and not g.get("completed", False)]

    if not disp_games:
        st.info("No matchups found matching this filter.")
        return

    # Render each game card with complete telemetry
    for gm in disp_games:
        is_nba = (gm.get("league") == "NBA")
        h_logo = gm.get("home_logo") or DEFAULT_LOGO
        a_logo = gm.get("away_logo") or DEFAULT_LOGO
        h_score = gm.get("home_score", 0)
        a_score = gm.get("away_score", 0)
        cur_total = h_score + a_score

        period = gm.get("period", 0)
        clock = gm.get("clock", "")
        status_txt = f"Q{period} • {clock}" if period > 0 and not gm.get("completed") else ("Final" if gm.get("completed") else gm.get("kickoff", "Scheduled"))

        # Pre-game baseline
        pre_total = float(gm.get("market_ou", 224.5 if is_nba else 47.5))
        pre_spread = float(gm.get("market_spread", -3.5))

        # Real-time quarter drift projection
        live_drift_total = calculate_pace_drift_factor(period, cur_total, pre_total)
        total_drift = round(live_drift_total - pre_total, 1)

        with st.container(border=True):
            # Header Row: Teams, Logos, Score
            top_col1, top_col2, top_col3 = st.columns([2.5, 2.0, 2.5], vertical_alignment="center")
            with top_col1:
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:10px;">
                    <img src="{a_logo}" width="38" height="38" style="object-fit:contain; border-radius:50%;">
                    <div>
                        <div style="font-size:1.1rem; font-weight:800;">{gm.get('away_team')}</div>
                        <div style="font-size:0.8rem; opacity:0.6;">{gm.get('away_record', '0-0')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with top_col2:
                st.markdown(f"""
                <div style="text-align:center;">
                    <div style="font-size:1.6rem; font-weight:900; letter-spacing:1px;">{a_score} - {h_score}</div>
                    <span style="background:rgba(239,68,68,0.2); color:#ef4444; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:800;">
                        {status_txt}
                    </span>
                </div>
                """, unsafe_allow_html=True)

            with top_col3:
                st.markdown(f"""
                <div style="display:flex; align-items:center; justify-content:flex-end; gap:10px;">
                    <div style="text-align:right;">
                        <div style="font-size:1.1rem; font-weight:800;">{gm.get('home_team')}</div>
                        <div style="font-size:0.8rem; opacity:0.6;">{gm.get('home_record', '0-0')}</div>
                    </div>
                    <img src="{h_logo}" width="38" height="38" style="object-fit:contain; border-radius:50%;">
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<hr style='margin:10px 0; opacity:0.1;'>", unsafe_allow_html=True)

            # Quarter Progression Telemetry (Q1, Halftime, Q3, Final)
            q_cols = st.columns(4)
            h_lines = gm.get("home_linescores", [])
            a_lines = gm.get("away_linescores", [])

            q1_tot = (h_lines[0] + a_lines[0]) if len(h_lines) > 0 and len(a_lines) > 0 else "-"
            half_tot = sum(h_lines[:2] + a_lines[:2]) if len(h_lines) >= 2 and len(a_lines) >= 2 else "-"
            q3_tot = sum(h_lines[:3] + a_lines[:3]) if len(h_lines) >= 3 and len(a_lines) >= 3 else "-"
            final_tot = (h_score + a_score) if gm.get("completed") else "-"

            q_cols[0].metric("Q1 Score Total", q1_tot)
            q_cols[1].metric("Halftime Total", half_tot)
            q_cols[2].metric("Q3 Total", q3_tot)
            q_cols[3].metric("Final Terminal", final_tot)

            # Projection Shifts (Pre vs Live)
            p_c1, p_c2, p_c3 = st.columns(3)
            p_c1.metric("Pre-Game Baseline Total", f"{pre_total:.1f} pts")
            p_c2.metric("Live Pace Projection", f"{live_drift_total:.1f} pts", delta=f"{total_drift:+.1f} pts since start")
            
            # Win probability estimation based on live margin
            margin = h_score - a_score
            live_win_p = min(96.0, max(4.0, 50.0 + (margin * (2.8 if is_nba else 7.5))))
            lead_team = gm["home_short"] if margin >= 0 else gm["away_short"]
            p_c3.metric(f"Live Lead Win Probability", f"{lead_team} {live_win_p:.1f}%")
