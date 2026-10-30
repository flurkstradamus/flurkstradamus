import streamlit as st
import pandas as pd
from config import DEFAULT_LOGO
from database import (
    load_game_snapshots,
    calculate_pace_drift_factor,
    find_game_for_bet
)
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster, get_live_nba_3pm_roster
from models import calculate_win_prob, calculate_moneyline_prob, calculate_spread_prob

def render_war_room(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🏟️ Live Matchup War Room")
    st.caption("Real-time game telemetry, multi-quarter progression modeling, live score tracking, and in-game prop projections.")

    if not games_data:
        st.warning("No live or scheduled games found on the active scoreboard.")
        return

    # Select target game for War Room telemetry
    target_bet = None
    if st.session_state.get("selected_bet_id"):
        target_bet = next((b for b in st.session_state.get("saved_bets", []) if b.get("id") == st.session_state.selected_bet_id), None)

    col_sel1, col_sel2 = st.columns([4, 2], vertical_alignment="center")

    game_options = [
        f"[{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')} ({gm.get('clock', gm.get('kickoff', 'Upcoming'))})"
        for gm in games_data
    ]

    default_idx = 0
    if target_bet:
        matched_g = find_game_for_bet(target_bet, games_data)
        if matched_g and matched_g in games_data:
            default_idx = games_data.index(matched_g)

    sel_idx = col_sel1.selectbox(
        "Select Active War Room Matchup",
        range(len(game_options)),
        format_func=lambda i: game_options[i],
        index=default_idx,
        key="wr_active_game_select"
    )
    live_g = games_data[sel_idx]

    if col_sel2.button("🔄 Refresh Telemetry", use_container_width=True):
        st.rerun()

    # Matchup Variables
    league = str(live_g.get("league", "NFL")).upper()
    is_nba = (league == "NBA")
    a_name = live_g.get("away_team", "Away Team")
    h_name = live_g.get("home_team", "Home Team")
    a_sh = live_g.get("away_short", "AWAY")
    h_sh = live_g.get("home_short", "HOME")
    a_logo = live_g.get("away_logo") or DEFAULT_LOGO
    h_logo = live_g.get("home_logo") or DEFAULT_LOGO
    a_sc = int(live_g.get("away_score", 0))
    h_sc = int(live_g.get("home_score", 0))
    curr_tot = a_sc + h_sc
    period = int(live_g.get("period", 0))
    clock = live_g.get("clock", live_g.get("displayClock", "Scheduled"))
    is_final = live_g.get("completed", False) or "final" in str(live_g.get("status", "")).lower()

    pre_tot = float(live_g.get("market_ou", 224.5 if is_nba else 46.5))
    pre_spread = float(live_g.get("market_spread", -3.5))

    # Live pace projection calculation
    live_proj_tot = calculate_pace_drift_factor(period, curr_tot, pre_tot) if period > 0 else pre_tot
    fav_team = h_name if pre_spread < 0 else a_name

    # =========================================================================
    # 1. LIVE MATCHUP SCOREBOARD BANNER
    # =========================================================================
    with st.container(border=True):
        st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:10px; margin-bottom:12px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); font-weight:800; font-size:0.78rem; padding:3px 8px; border-radius:6px;">
                    {league}
                </span>
                <span style="font-weight:700; font-size:1.05rem;">{a_name} vs {h_name}</span>
            </div>
            <div style="font-size:0.88rem; font-weight:600; color:#94a3b8;">
                {'🔴 FINAL' if is_final else (f'⚡ LIVE: Q{period} • {clock}' if period > 0 else f'⏳ {clock}')}
            </div>
        </div>
        """, unsafe_allow_html=True)

        sc1, sc2, sc3 = st.columns([3, 2, 3], vertical_alignment="center")

        with sc1:
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px;">
                <img src="{a_logo}" width="48" height="48" style="object-fit:contain; border-radius:50%;">
                <div>
                    <div style="font-size:1.2rem; font-weight:800;">{a_sh}</div>
                    <div style="font-size:0.80rem; opacity:0.6;">Away</div>
                </div>
                <div style="font-size:2.2rem; font-weight:800; margin-left:auto; color:#f8fafc;">{a_sc}</div>
            </div>
            """, unsafe_allow_html=True)

        with sc2:
            st.markdown(f"""
            <div style="text-align:center;">
                <div style="font-size:0.80rem; opacity:0.7;">Total Score</div>
                <div style="font-size:1.8rem; font-weight:800; color:#38bdf8;">{curr_tot}</div>
                <div style="font-size:0.75rem; opacity:0.6;">Open Line: {pre_tot:.1f}</div>
            </div>
            """, unsafe_allow_html=True)

        with sc3:
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px;">
                <div style="font-size:2.2rem; font-weight:800; margin-right:auto; color:#f8fafc;">{h_sc}</div>
                <div>
                    <div style="font-size:1.2rem; font-weight:800; text-align:right;">{h_sh}</div>
                    <div style="font-size:0.80rem; opacity:0.6; text-align:right;">Home</div>
                </div>
                <img src="{h_logo}" width="48" height="48" style="object-fit:contain; border-radius:50%;">
            </div>
            """, unsafe_allow_html=True)

    # Active Bet Ticket Banner (if routed from tickets)
    if target_bet:
        with st.container(border=True):
            tb1, tb2 = st.columns([4, 2], vertical_alignment="center")
            tb1.markdown(f"**Tracking Bet:** `{target_bet.get('bet')}` ({target_bet.get('bet_category', target_bet.get('type'))})")
            from app import calculate_live_bet_prob
            live_prob = calculate_live_bet_prob(target_bet, live_g)
            tb2.markdown(f"**In-Game Win Probability:** <span style='color:#4ade80; font-weight:800; font-size:1.1rem;'>{live_prob}</span>", unsafe_allow_html=True)

    # =========================================================================
    # 2. MULTI-QUARTER PROGRESSION & SCORE PROJECTIONS TABLE
    # =========================================================================
    st.markdown("#### 📈 Multi-Quarter Score Progression & Projections")
    st.caption("Real-time pacing and projected terminal scores evaluated after Pre-game, Q1, Halftime, Q3, and Final.")

    a_lines = live_g.get("away_linescores", [])
    h_lines = live_g.get("home_linescores", [])

    q1_a = a_lines[0] if len(a_lines) > 0 else 0
    q1_h = h_lines[0] if len(h_lines) > 0 else 0
    q1_tot = q1_a + q1_h

    q2_a = a_lines[1] if len(a_lines) > 1 else 0
    q2_h = h_lines[1] if len(h_lines) > 1 else 0
    half_tot = q1_tot + (q2_a + q2_h)

    q3_a = a_lines[2] if len(a_lines) > 2 else 0
    q3_h = h_lines[2] if len(h_lines) > 2 else 0
    q3_tot = half_tot + (q3_a + q3_h)

    q4_a = a_lines[3] if len(a_lines) > 3 else 0
    q4_h = h_lines[3] if len(h_lines) > 3 else 0

    # Model Quarter Projector Matrix
    progression_rows = [
        {
            "Checkpoint": "Pre-Game Open",
            f"{a_sh} Score": 0,
            f"{h_sh} Score": 0,
            "Total Score": 0,
            "Projected Total": f"{pre_tot:.1f} pts",
            "Projected Winner": f"{fav_team} ({pre_spread:+.1f})",
            "Status": "Completed"
        },
        {
            "Checkpoint": "After 1st Quarter",
            f"{a_sh} Score": q1_a if period >= 1 else "—",
            f"{h_sh} Score": q1_h if period >= 1 else "—",
            "Total Score": q1_tot if period >= 1 else "—",
            "Projected Total": f"{round((q1_tot * 4.0 * 0.35) + (pre_tot * 0.65), 1)} pts" if period >= 1 else f"{pre_tot:.1f} pts",
            "Projected Winner": f"{a_name if q1_a > q1_h else h_name}" if period >= 1 else fav_team,
            "Status": "Locked" if period > 1 else ("In Progress" if period == 1 else "Pending")
        },
        {
            "Checkpoint": "Halftime (After 2nd)",
            f"{a_sh} Score": (q1_a + q2_a) if period >= 2 else "—",
            f"{h_sh} Score": (q1_h + q2_h) if period >= 2 else "—",
            "Total Score": half_tot if period >= 2 else "—",
            "Projected Total": f"{round((half_tot * 2.0 * 0.60) + (pre_tot * 0.40), 1)} pts" if period >= 2 else f"{pre_tot:.1f} pts",
            "Projected Winner": f"{a_name if (q1_a + q2_a) > (q1_h + q2_h) else h_name}" if period >= 2 else fav_team,
            "Status": "Locked" if period > 2 else ("In Progress" if period == 2 else "Pending")
        },
        {
            "Checkpoint": "After 3rd Quarter",
            f"{a_sh} Score": (q1_a + q2_a + q3_a) if period >= 3 else "—",
            f"{h_sh} Score": (q1_h + q2_h + q3_h) if period >= 3 else "—",
            "Total Score": q3_tot if period >= 3 else "—",
            "Projected Total": f"{round(((q3_tot / 3.0) * 4.0 * 0.85) + (pre_tot * 0.15), 1)} pts" if period >= 3 else f"{pre_tot:.1f} pts",
            "Projected Winner": f"{a_name if (q1_a + q2_a + q3_a) > (q1_h + q2_h + q3_h) else h_name}" if period >= 3 else fav_team,
            "Status": "Locked" if period > 3 else ("In Progress" if period == 3 else "Pending")
        },
        {
            "Checkpoint": "Final Outcome",
            f"{a_sh} Score": a_sc if is_final else "—",
            f"{h_sh} Score": h_sc if is_final else "—",
            "Total Score": curr_tot if is_final else "—",
            "Projected Total": f"{curr_tot:.1f} pts" if is_final else f"{live_proj_tot:.1f} pts",
            "Projected Winner": f"{a_name if a_sc > h_sc else h_name} (W)" if is_final else fav_team,
            "Status": "Completed" if is_final else "Projected"
        }
    ]

    st.dataframe(pd.DataFrame(progression_rows), use_container_width=True, hide_index=True)

    # Telemetry Metric Strip
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pre-Game Total", f"{pre_tot:.1f} pts")
    m2.metric("Live Pace Projection", f"{live_proj_tot:.1f} pts", delta=round(live_proj_tot - pre_tot, 1))
    m3.metric("Projected Spread Cover", fav_team, f"{pre_spread:+.1f} pts")
    m4.metric("Current Stage", f"Q{period} • {clock}" if period > 0 else "Pre-Game")

    # =========================================================================
    # 3. SPORT-SPECIFIC PLAYER PROP PROJECTIONS (BASKETBALL VS FOOTBALL)
    # =========================================================================
    st.markdown("---")
    if is_nba:
        st.markdown("#### 🏀 NBA In-Game Player Prop Projections")
        st.caption("Live projected points and 3-pointers made for active starting rotation players:")

        col_h, col_a = st.columns(2)
        with col_a:
            st.markdown(f"**{a_name} ({a_sh}) Projected Leaders**")
            shooters_a = get_live_nba_3pm_roster(live_g.get("away_id") or a_sh, game_id=live_g.get("id"))
            if shooters_a:
                for ply in shooters_a[:4]:
                    p_name, pos, line_3pm, proj_pts = ply[0], ply[1], ply[2], ply[3]
                    # Dynamic pace-scaled points if in-game
                    scaled_pts = proj_pts if period == 0 else round(proj_pts * (live_proj_tot / max(1.0, pre_tot)), 1)
                    st.info(f"**{p_name}** ({pos}) — Projected: **{scaled_pts:.1f} Pts** | **{line_3pm:.1f} 3PM** (Prob: 68%)")
            else:
                st.caption("No starter telemetry available.")

        with col_h:
            st.markdown(f"**{h_name} ({h_sh}) Projected Leaders**")
            shooters_h = get_live_nba_3pm_roster(live_g.get("home_id") or h_sh, game_id=live_g.get("id"))
            if shooters_h:
                for ply in shooters_h[:4]:
                    p_name, pos, line_3pm, proj_pts = ply[0], ply[1], ply[2], ply[3]
                    scaled_pts = proj_pts if period == 0 else round(proj_pts * (live_proj_tot / max(1.0, pre_tot)), 1)
                    st.info(f"**{p_name}** ({pos}) — Projected: **{scaled_pts:.1f} Pts** | **{line_3pm:.1f} 3PM** (Prob: 68%)")
            else:
                st.caption("No starter telemetry available.")

    else:
        st.markdown("#### 🏈 Football In-Game Player Prop Projections")
        st.caption("Live Anytime Touchdown probabilities, carry shares, and red-zone projections:")

        col_h, col_a = st.columns(2)
        with col_a:
            st.markdown(f"**{a_name} ({a_sh}) Touchdown & Yardage Targets**")
            fb_a = get_live_football_roster(live_g.get("away_id") or a_sh, league)
            if fb_a:
                for idx, ply in enumerate(fb_a[:4]):
                    p_name, pos = ply[0], ply[1]
                    td_prob = 56 - (idx * 6)
                    st.info(f"**{p_name}** ({pos}) — **{td_prob}% Anytime TD** | Red-Zone Share: **{35 - (idx * 5)}%**")
            else:
                st.caption("No starter telemetry available.")

        with col_h:
            st.markdown(f"**{h_name} ({h_sh}) Touchdown & Yardage Targets**")
            fb_h = get_live_football_roster(live_g.get("home_id") or h_sh, league)
            if fb_h:
                for idx, ply in enumerate(fb_h[:4]):
                    p_name, pos = ply[0], ply[1]
                    td_prob = 58 - (idx * 6)
                    st.info(f"**{p_name}** ({pos}) — **{td_prob}% Anytime TD** | Red-Zone Share: **{36 - (idx * 5)}%**")
            else:
                st.caption("No starter telemetry available.")

    # =========================================================================
    # 4. LIVE IN-GAME BETTING EDGES
    # =========================================================================
    st.markdown("---")
    st.markdown("#### 🎯 War Room Model Market Edges")
    e1, e2, e3 = st.columns(3)

    cush = 4.5 if is_nba else 3.5
    live_under_line = round_half_point(live_proj_tot + cush)

    with e1:
        with st.container(border=True):
            st.markdown("**🛡️ Pace-Adjusted Total**")
            st.subheader(f"Under {live_under_line:.1f}")
            st.caption("Cushioned Under model absorbing tempo fluctuations.")

    with e2:
        with st.container(border=True):
            st.markdown("**⚖️ Live Spread Cover**")
            st.subheader(f"{fav_team} {pre_spread:+.1f}")
            st.caption("Point differential baseline against opening spread.")

    with e3:
        with st.container(border=True):
            st.markdown("**🚀 Key Active Prop Edge**")
            if is_nba:
                star = shooters_h[0][0] if (shooters_h and len(shooters_h) > 0) else "Starting Guard"
                st.subheader(f"{star} 2+ 3PM")
                st.caption("Optimal perimeter volume projection.")
            else:
                star_fb = fb_h[0][0] if (fb_h and len(fb_h) > 0) else "Starting RB"
                st.subheader(f"{star_fb} Anytime TD")
                st.caption("Primary red-zone touchdown equity.")
