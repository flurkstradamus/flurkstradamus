import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

def generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice):
    if not pool:
        return []

    is_mixed = "Mixed" in strat_choice
    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice
    is_balanced = "Balanced" in strat_choice

    is_totals_only = "Totals" in chosen_market
    is_spreads_only = "Spreads" in chosen_market
    is_ml_only = "Straight Up" in chosen_market or "Moneyline" in chosen_market

    candidates = []

    for gm in pool:
        is_nba = (gm.get("league") == "NBA")
        ou_open = round_half_point(gm.get("market_ou", 224.5 if is_nba else 47.5))
        spread_open = round_half_point(gm.get("market_spread", -3.5))

        fav_team = gm["home_team"] if spread_open < 0 else gm["away_team"]
        dog_team = gm["away_team"] if spread_open < 0 else gm["home_team"]
        fav_spread = spread_open if fav_team == gm["home_team"] else -spread_open

        add_score = 40 if is_nba else 14
        h_prob = calculate_moneyline_prob(
            gm["home_score"] + add_score,
            gm["away_score"] + add_score,
            gm.get("home_record", "0-0"),
            gm.get("away_record", "0-0")
        )

        # 1. TOTALS CANDIDATE
        if is_safe:
            cushion = 8.5 if is_nba else 6.5
            tot_line = round_half_point(ou_open + cushion)
            tot_prob = 0.77
            tot_desc = f"Under {tot_line:.1f}"
        elif is_high_profit:
            tot_line = round_half_point(ou_open - (4.5 if is_nba else 3.5))
            tot_prob = 0.49
            tot_desc = f"Under {tot_line:.1f}"
        elif is_balanced:
            tot_line = round_half_point(ou_open + (2.5 if is_nba else 1.5))
            tot_prob = 0.60
            tot_desc = f"Under {tot_line:.1f}"
        else: # Mixed
            tot_line = round_half_point(ou_open + (7.5 if is_nba else 4.5))
            tot_prob = 0.73
            tot_desc = f"Under {tot_line:.1f}"

        candidates.append({
            "game": gm,
            "type": "Game Total",
            "side": "Under",
            "line": tot_line,
            "picked_team": gm["home_team"],
            "desc": tot_desc,
            "prob": tot_prob,
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
        })

        # 2. SPREAD CANDIDATE
        if is_safe:
            dog_line = round_half_point(abs(fav_spread) + (6.5 if is_nba else 4.5))
            spd_prob = 0.75
            spd_team = dog_team
            spd_desc = f"{dog_team} {dog_line:+.1f}"
            spd_side = "Spread"
        elif is_high_profit:
            lay_line = round_half_point(fav_spread - (3.5 if is_nba else 2.5))
            spd_prob = 0.46
            spd_team = fav_team
            spd_desc = f"{fav_team} {lay_line:+.1f}"
            spd_side = "Spread"
        elif is_balanced:
            spd_team = fav_team
            lay_line = fav_spread
            spd_prob = 0.55
            spd_desc = f"{fav_team} {lay_line:+.1f}"
            spd_side = "Spread"
        else: # Mixed
            dog_line = round_half_point(abs(fav_spread) + (4.5 if is_nba else 3.5))
            spd_prob = 0.69
            spd_team = dog_team
            spd_desc = f"{dog_team} {dog_line:+.1f}"
            spd_side = "Spread"

        candidates.append({
            "game": gm,
            "type": "Point Spread (ATS)",
            "side": spd_side,
            "line": dog_line if 'dog_line' in locals() else lay_line,
            "picked_team": spd_team,
            "desc": spd_desc,
            "prob": spd_prob,
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
        })

        # 3. MONEYLINE CANDIDATE
        if is_high_profit:
            ml_target = dog_team
            ml_prob = min(0.46, min(h_prob, 1.0 - h_prob))
        else:
            ml_target = fav_team
            ml_prob = max(0.68, max(h_prob, 1.0 - h_prob))

        candidates.append({
            "game": gm,
            "type": "Straight Up Winner (Moneyline)",
            "side": "Moneyline",
            "line": None,
            "picked_team": ml_target,
            "desc": f"{ml_target} ML",
            "prob": ml_prob,
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}"
        })

    if is_totals_only:
        filtered = [c for c in candidates if c["type"] == "Game Total"]
    elif is_spreads_only:
        filtered = [c for c in candidates if c["type"] == "Point Spread (ATS)"]
    elif is_ml_only:
        filtered = [c for c in candidates if "Moneyline" in c["type"]]
    else:
        filtered = candidates

    selected = []
    used_matchups = set()
    sorted_candidates = sorted(filtered, key=lambda x: x["prob"], reverse=not is_high_profit)

    for item in sorted_candidates:
        m = item["matchup"]
        if m not in used_matchups:
            selected.append(item)
            used_matchups.add(m)
            if len(selected) == num_legs:
                break

    return selected

def trigger_combo_auto_refresh():
    st.session_state.cb_needs_refresh = True

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo Builder")
    st.caption("Algorithmic parlay optimizer with cross-sport leg modeling, compound win probability, and automated bankroll tracking.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []
    if "cb_form_nonce" not in st.session_state:
        st.session_state.cb_form_nonce = 0
    if "cb_needs_refresh" not in st.session_state:
        st.session_state.cb_needs_refresh = False

    # AI Combo Optimizer Controls
    # Sequence: 1. League, 2. Filter Status, 3. Target # of Legs, 4. Target Market Focus, 5. Combo Strategy Profile
    with st.container(border=True):
        st.markdown("#### 🤖 AI Multi-Leg Optimizer")

        c1, c2 = st.columns(2)
        league_choice = c1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NBA", "NFL", "NCAA Football"],
            key="cb_static_league",
            on_change=trigger_combo_auto_refresh
        )

        t_filter = c2.selectbox(
            "Game Filter Status",
            options=["⏳ Upcoming Games", "⚡ Live Games", "🌐 All Matchups"],
            key="cb_static_filter",
            on_change=trigger_combo_auto_refresh
        )

        c3, c4 = st.columns(2)
        num_legs = c3.selectbox(
            "Target # of Legs",
            options=[2, 3, 4, 5, 6, 7, 8, 9, 10],
            index=2, # Default: 4 legs
            key="cb_static_legs",
            on_change=trigger_combo_auto_refresh
        )

        if league_choice == "NBA":
            market_options = [
                "⚡ Let the System Pick (Best NBA Multi-Market Mix)",
                "📊 Game Totals Only (Over / Under)",
                "🛡️ Point Spreads Only (ATS Cover)",
                "🏆 Straight Up Winners Only (Moneyline)"
            ]
        elif league_choice in ["NFL", "NCAA Football"]:
            market_options = [
                "⚡ Let the System Pick (Best Football Multi-Market Mix)",
                "📊 Game Totals Only (Over / Under)",
                "🛡️ Point Spreads Only (ATS Cover)",
                "🏆 Straight Up Winners Only (Moneyline)"
            ]
        else:
            market_options = [
                "⚡ Let the System Pick (Best Cross-Sport Mix)",
                "📊 Game Totals Only (Over / Under)",
                "🛡️ Point Spreads Only (ATS Cover)",
                "🏆 Straight Up Winners Only (Moneyline)"
            ]

        chosen_market = c4.selectbox(
            "Target Market Focus",
            options=market_options,
            key="cb_static_market",
            on_change=trigger_combo_auto_refresh
        )

        strat_options = [
            "🎯 Mixed Tier Spectrum (Safe, Balanced, High Profit)",
            "🛡️ Safe Floor (High Win %, Low Drawdown)",
            "⚖️ Balanced Edge (+EV Sweet Spot)",
            "🚀 High Profit (Max Multiplier & Longshots)"
        ]
        strat_choice = st.selectbox(
            "Combo Strategy Profile",
            options=strat_options,
            index=0,
            key="cb_static_strat",
            on_change=trigger_combo_auto_refresh
        )

        # Matchup Pool Resolution
        pool = games_data
        if league_choice == "NBA":
            pool = [g for g in pool if g.get("league") == "NBA"]
        elif league_choice == "NFL":
            pool = [g for g in pool if g.get("league") == "NFL"]
        elif league_choice == "NCAA Football":
            pool = [g for g in pool if g.get("league") == "NCAA"]

        if t_filter == "⏳ Upcoming Games":
            pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
        elif t_filter == "⚡ Live Games":
            pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]
        else:
            pool = [g for g in pool if not g.get("completed", False)]

        # Auto-recalculate if user modified dropdowns and a combo is already loaded
        if st.session_state.cb_needs_refresh and len(st.session_state.combo_active_legs) > 0:
            if pool:
                st.session_state.combo_active_legs = generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice)
                st.session_state.cb_form_nonce += 1
            st.session_state.cb_needs_refresh = False

        c_act1, c_act2 = st.columns([3.5, 1.5], vertical_alignment="bottom")
        with c_act1:
            st.caption(f"Active Pool: {len(pool)} available matchups across {league_choice}")
        with c_act2:
            if st.button("⚡ Generate Combo", type="primary", use_container_width=True, disabled=len(pool) < 2):
                st.session_state.combo_active_legs = generate_algorithmic_combo(pool, num_legs, chosen_market, strat_choice)
                st.session_state.cb_needs_refresh = False
                st.session_state.cb_form_nonce += 1
                st.rerun()

    # ACTIVE TICKET DISPLAY & SUBMISSION
    legs = st.session_state.combo_active_legs

    if legs:
        st.markdown("---")
        st.markdown(f"#### 🎟️ Active {len(legs)}-Leg Combo Ticket")

        compound_p = 1.0
        for lg in legs:
            compound_p *= float(lg.get("prob", 0.55))
        compound_p = max(0.001, min(0.999, compound_p))

        fair_mult = max(1.1, round(1.0 / compound_p, 2))
        est_roi_pct = int((fair_mult - 1.0) * 100)

        with st.container(border=True):
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                <div style="font-size:1.05rem; font-weight:700;">
                    🔗 {len(legs)}-Leg Parlay <span style="opacity:0.6; font-size:0.80rem;">({strat_choice.split()[1]})</span>
                </div>
                <div style="display:flex; gap:6px;">
                    <span style="background:rgba(56,189,248,0.15); color:#38bdf8; padding:3px 10px; border-radius:6px; font-weight:700; font-size:0.82rem;">
                        🎲 Compound Win Prob: {compound_p * 100:.1f}%
                    </span>
                    <span style="background:#22c55e; color:#000; padding:3px 10px; border-radius:6px; font-weight:800; font-size:0.82rem;">
                        Est. Fair Payout: {fair_mult:.2f}x (+{est_roi_pct}%)
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            for idx, leg_item in enumerate(legs):
                gm = leg_item["game"]
                a_logo = gm.get("away_logo") or DEFAULT_LOGO
                h_logo = gm.get("home_logo") or DEFAULT_LOGO
                a_sh = gm.get("away_short", "AWAY")
                h_sh = gm.get("home_short", "HOME")
                p_val = leg_item.get("prob", 0.55) * 100

                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:8px; padding:10px 14px; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="background:rgba(255,255,255,0.08); color:#f8fafc; font-weight:800; padding:2px 8px; border-radius:4px; font-size:0.80rem;">
                            #{idx+1}
                        </span>
                        <img src="{a_logo}" width="20" height="20" style="border-radius:50%; object-fit:contain;">
                        <strong>{a_sh}</strong>
                        <span style="opacity:0.35;">@</span>
                        <img src="{h_logo}" width="20" height="20" style="border-radius:50%; object-fit:contain;">
                        <strong>{h_sh}</strong>
                        <span style="opacity:0.6; font-size:0.75rem;">[{gm.get('league')}]</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <span style="font-weight:700; color:#4ade80; font-size:0.95rem;">{leg_item.get('desc')}</span>
                        <span style="opacity:0.6; font-size:0.78rem;">{leg_item.get('type')}</span>
                        <span style="background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:700;">
                            {p_val:.1f}% Leg Win
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # LOCK-IN FORM
        f_nonce = st.session_state.cb_form_nonce
        with st.form(f"combo_lock_in_form_{f_nonce}"):
            c1, c2 = st.columns(2)
            risk = c1.number_input("Risk ($)", min_value=1.0, value=10.0, step=5.0)
            suggested_payout = round(float(risk) * fair_mult, 2)
            payout = c2.number_input("Payout ($)", min_value=1.0, value=suggested_payout, step=5.0)

            actual_profit = float(payout) - float(risk)
            combo_title = f"{len(legs)}-Leg: " + ", ".join([l.get("desc", "") for l in legs[:3]]) + ("..." if len(legs) > 3 else "")

            if st.form_submit_button("🔒 Lock In Combo Ticket", type="primary", use_container_width=True):
                parsed_legs = [
                    {
                        "matchup": lg.get("matchup"),
                        "type": lg.get("type"),
                        "side": lg.get("side"),
                        "line": lg.get("line"),
                        "picked_team": lg.get("picked_team")
                    } for lg in legs
                ]

                tkt = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": f"{len(legs)}-Leg Combo",
                    "bet_category": "Combo",
                    "matchup": f"{len(legs)}-Leg Cross-Sport Combo",
                    "bet": combo_title,
                    "risk_dollars": float(risk),
                    "payout_dollars": float(payout),
                    "payout": float(payout),
                    "locked_profit": float(actual_profit),
                    "win_prob": f"{compound_p * 100:.1f}%",
                    "status": "Pending",
                    "parsed_legs": parsed_legs,
                    "notes": f"[{league_choice}] {len(legs)}-Leg Combo [{strat_choice.split()[1]}]"
                }

                st.session_state.saved_bets.insert(0, tkt)
                save_all_storage(
                    st.session_state.saved_bets,
                    st.session_state.chat_messages,
                    st.session_state.user_accounts,
                    st.session_state.banned_emails,
                    st.session_state.game_snapshots,
                    st.session_state.support_tickets
                )
                st.session_state.combo_active_legs = []
                st.toast(f"🎉 Locked in {len(legs)}-Leg Combo!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
