import streamlit as st
import pandas as pd
from config import DEFAULT_LOGO
from database import load_game_snapshots

def render_history_lab():
    st.subheader("🧪 Game History & Model Learning Lab")
    st.caption("Inspect season game progressions, quarterly projection drift, verified rosters, and empirical model accuracy.")

    snapshots = load_game_snapshots()

    if not snapshots:
        st.info("No historical game progression snapshots recorded yet. As games are analyzed and played, their quarterly telemetry will accumulate here.")
        return

    # Filter controls
    c1, c2 = st.columns(2)
    league_filter = c1.selectbox("Filter League", ["All", "NFL", "NBA", "NCAA Football"], key="lab_league")
    status_filter = c2.selectbox("Filter Status", ["All", "Completed", "In Progress", "Scheduled"], key="lab_status")

    filtered = snapshots
    if league_filter != "All":
        filtered = [g for g in filtered if g.get("league") == league_filter]
    if status_filter != "All":
        filtered = [g for g in filtered if status_filter.lower() in g.get("status", "").lower()]

    # Season Summary Metrics
    completed_games = [g for g in filtered if "completed" in g.get("status", "").lower()]
    total_games = len(filtered)
    
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Games Tracked", total_games)
    m2.metric("Completed Matchups", len(completed_games))
    
    # Calculate average model error if completed games exist
    tot_errors = []
    for g in completed_games:
        cps = g.get("checkpoints", {})
        pre = cps.get("pre", {}).get("projected_total")
        final_tot = g.get("final_score_away", 0) + g.get("final_score_home", 0)
        if pre and final_tot > 0:
            tot_errors.append(abs(final_tot - pre))

    avg_err = round(sum(tot_errors) / len(tot_errors), 1) if tot_errors else 0.0
    m3.metric("Avg Pre-Game Total Error", f"{avg_err} pts" if tot_errors else "N/A")
    m4.metric("Learning Dataset Status", "Active (Logging)" if total_games > 0 else "Idle")

    st.markdown("### 📋 Season Game Matchup Database")

    if not filtered:
        st.warning("No games match the selected filters.")
        return

    # Display Games
    for g in filtered:
        a_logo = g.get("away_logo") or DEFAULT_LOGO
        h_logo = g.get("home_logo") or DEFAULT_LOGO
        a_team = g.get("away_team", "Away")
        h_team = g.get("home_team", "Home")
        a_sh = g.get("away_short", "AWAY")
        h_sh = g.get("home_short", "HOME")
        date_str = g.get("date", "Scheduled")
        status = g.get("status", "Scheduled")
        cps = g.get("checkpoints", {})

        with st.expander(f"[{g.get('league')}] {a_sh} @ {h_sh} — {date_str} ({status})", expanded=False):
            # Top Banner
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <img src="{a_logo}" width="26" height="26">
                    <span style="font-weight:700; font-size:1.0rem;">{a_team}</span>
                    <span style="opacity:0.4;">@</span>
                    <img src="{h_logo}" width="26" height="26">
                    <span style="font-weight:700; font-size:1.0rem;">{h_team}</span>
                </div>
                <span style="font-weight:600; opacity:0.8; font-size:0.85rem;">🗓️ {date_str}</span>
            </div>
            """, unsafe_allow_html=True)

            # Checkpoint Progression Table
            st.markdown("##### 📈 Projection & Score Progression by Quarter")
            if cps:
                table_rows = []
                checkpoints_order = ["pre", "q1", "half", "q3", "final"]
                labels = {
                    "pre": "Pre-Game",
                    "q1": "After 1st Quarter",
                    "half": "Halftime (After 2nd)",
                    "q3": "After 3rd Quarter",
                    "final": "Final Outcome"
                }

                for cp_key in checkpoints_order:
                    if cp_key in cps:
                        c_data = cps[cp_key]
                        table_rows.append({
                            "Checkpoint": labels.get(cp_key, cp_key.upper()),
                            "Away Score": c_data.get("away_score"),
                            "Home Score": c_data.get("home_score"),
                            "Score at Stage": c_data.get("score_total"),
                            "Projected Final Total": f"{c_data.get('projected_total'):.1f} pts",
                            "Projected Winner": c_data.get("projected_winner")
                        })

                if table_rows:
                    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No quarter progression snapshots logged yet for this game.")

            # Confirmed Active Rosters
            col_a, col_h = st.columns(2)
            with col_a:
                st.markdown(f"**Verified Lineup: {a_team}**")
                roster_a = g.get("confirmed_players_away", [])
                if roster_a:
                    st.caption(", ".join([f"{p[0]} ({p[1]})" for p in roster_a[:12]]))
                else:
                    st.caption("Active game-day roster pending synchronization.")

            with col_h:
                st.markdown(f"**Verified Lineup: {h_team}**")
                roster_h = g.get("confirmed_players_home", [])
                if roster_h:
                    st.caption(", ".join([f"{p[0]} ({p[1]})" for p in roster_h[:12]]))
                else:
                    st.caption("Active game-day roster pending synchronization.")
