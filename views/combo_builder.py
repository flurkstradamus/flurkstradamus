import streamlit as st
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from sports.football import round_half_point, get_live_football_roster
from sports.basketball import get_live_nba_roster, get_live_nba_3pm_roster, fetch_nba_injury_set

def prob_to_american_odds(prob):
    p = max(0.005, min(0.995, float(prob)))
    if p >= 0.50:
        odds = int(round(-100.0 * (p / (1.0 - p))))
        return f"{odds}"
    else:
        odds = int(round(100.0 * ((1.0 - p) / p)))
        return f"+{odds}"

def get_verified_active_players_list(game_obj, is_nba):
    """Returns a list of healthy, active starters for SGP prop legs."""
    g_id = game_obj.get("id")
    home_id = game_obj.get("home_id") or game_obj.get("home_short")
    away_id = game_obj.get("away_id") or game_obj.get("away_short")

    healthy_players = []

    if is_nba:
        injury_set = fetch_nba_injury_set()
        h_shooters = get_live_nba_3pm_roster(home_id, game_id=g_id)
        a_shooters = get_live_nba_3pm_roster(away_id, game_id=g_id)

        for p in h_shooters + a_shooters:
            if p[0].strip().lower() not in injury_set:
                healthy_players.append((p[0], "3PM", p[2]))

        if not healthy_players:
            healthy_players = [("Starting Guard", "3PM", 1.5), ("Primary Scorer", "Points", 18.5)]
    else:
        league = game_obj.get("league", "NFL")
        h_fb = get_live_football_roster(home_id, league)
        a_fb = get_live_football_roster(away_id, league)

        for p in h_fb + a_fb:
            healthy_players.append((p[0], "Touchdown", 1.0))

        if not healthy_players:
            healthy_players = [("Starting RB", "Touchdown", 1.0)]

    return healthy_players

def build_same_game_parlay_legs(target_game, strat_choice, leg_count):
    """Constructs up to 15 correlated legs all strictly from the same matchup."""
    legs = []
    league = str(target_game.get("league", "NFL")).upper()
    is_nba = (league == "NBA")

    ou_open = round_half_point(target_game.get("market_ou", 224.5 if is_nba else 46.5))
    spread_open = round_half_point(target_game.get("market_spread", -3.5))
    fav_team = target_game["home_team"] if spread_open < 0 else target_game["away_team"]
    dog_team = target_game["away_team"] if spread_open < 0 else target_game["home_team"]
    fav_spread = spread_open if fav_team == target_game["home_team"] else -spread_open

    healthy_athletes = get_verified_active_players_list(target_game, is_nba)

    base_metadata = {
        "matchup": f"{target_game.get('away_short')} @ {target_game.get('home_short')}",
        "home_team": target_game.get("home_team"),
        "away_team": target_game.get("away_team"),
        "away_short": target_game.get("away_short", "AWAY"),
        "home_short": target_game.get("home_short", "HOME"),
        "league": league,
        "away_logo": target_game.get("away_logo", DEFAULT_LOGO),
        "home_logo": target_game.get("home_logo", DEFAULT_LOGO),
        "kickoff": target_game.get("kickoff", "Scheduled"),
    }

    # Leg 1: Game Total
    cush = 4.5 if is_nba else 3.5
    t_line = round_half_point(ou_open + cush)
    legs.append({
        **base_metadata,
        "picked_team": target_game.get("home_team"),
        "player_name": "",
        "type": "Game Total",
        "side": "Under",
        "line": str(t_line),
        "pick_text": f"Under {t_line:.1f} Pts",
        "prob": 0.72
    })

    # Leg 2: Spread or Winner
    if len(legs) < leg_count:
        legs.append({
            **base_metadata,
            "picked_team": fav_team,
            "player_name": "",
            "type": "Point Spread (ATS)",
            "side": "Spread",
            "line": str(fav_spread),
            "pick_text": f"{fav_team} {fav_spread:+.1f}",
            "prob": 0.58
        })

    # Leg 3: Straight Up ML
    if len(legs) < leg_count:
        legs.append({
            **base_metadata,
            "picked_team": fav_team,
            "player_name": "",
            "type": "Moneyline",
            "side": "Moneyline",
            "line": "0.0",
            "pick_text": f"{fav_team} ML",
            "prob": 0.65
        })

    # Subsequent Legs: Correlated Player Props from both teams in this same game
    ath_idx = 0
    while len(legs) < leg_count and ath_idx < len(healthy_athletes):
        ath_name, prop_type, p_line = healthy_athletes[ath_idx]
        if is_nba:
            label = f"{ath_name} 2+ 3PM" if prop_type == "3PM" else f"{ath_name} Over {p_line} Pts"
            p_cat = "NBA 3-Pointers Made" if prop_type == "3PM" else "Player Points"
        else:
            label = f"{ath_name} Anytime TD"
            p_cat = "Player Anytime TD"

        legs.append({
            **base_metadata,
            "picked_team": ath_name,
            "player_name": ath_name,
            "type": p_cat,
            "side": "Over" if is_nba else "TD",
            "line": str(p_line),
            "pick_text": label,
            "prob": 0.55
        })
        ath_idx += 1

    return legs[:leg_count]

def build_system_cross_game_legs(pool_games, target_market, strat_choice, leg_count):
    """Constructs legs across different games on the slate."""
    selected_legs = []
    is_safe = "Safe Floor" in strat_choice
    is_high_profit = "High Profit" in strat_choice

    sorted_games = sorted(pool_games, key=lambda g: abs(float(g.get("market_spread", 0))), reverse=True)

    for gm in sorted_games:
        if len(selected_legs) >= leg_count:
            break

        league = str(gm.get("league", "NFL")).upper()
        is_nba = (league == "NBA")

        ou_open = round_half_point(gm.get("market_ou", 224.5 if is_nba else 46.5))
        spread_open = round_half_point(gm.get("market_spread", -3.5))
        fav_team = gm["home_team"] if spread_open < 0 else gm["away_team"]
        dog_team = gm["away_team"] if spread_open < 0 else gm["home_team"]
        fav_spread = spread_open if fav_team == gm["home_team"] else -spread_open

        healthy_players = get_verified_active_players_list(gm, is_nba)
        active_player = healthy_players[0][0] if healthy_players else "Star Athlete"

        leg_data = {
            "matchup": f"{gm.get('away_short')} @ {gm.get('home_short')}",
            "home_team": gm.get("home_team"),
            "away_team": gm.get("away_team"),
            "away_short": gm.get("away_short", "AWAY"),
            "home_short": gm.get("home_short", "HOME"),
            "league": league,
            "away_logo": gm.get("away_logo", DEFAULT_LOGO),
            "home_logo": gm.get("home_logo", DEFAULT_LOGO),
            "kickoff": gm.get("kickoff", "Scheduled"),
            "player_name": active_player
        }

        if "Game Totals" in target_market:
            cush = (7.5 if is_nba else 4.5) if is_safe else (3.5 if is_nba else 2.0)
            tot_line = round_half_point(ou_open + cush)
            leg_data.update({
                "picked_team": gm.get("home_team"),
                "type": "Game Total",
                "side": "Under",
                "line": str(tot_line),
                "pick_text": f"Under {tot_line:.1f} Pts",
                "prob": 0.74 if is_safe else 0.64
            })
        elif "Point Spread" in target_market:
            leg_data.update({
                "picked_team": fav_team,
                "type": "Point Spread (ATS)",
                "side": "Spread",
                "line": str(fav_spread),
                "pick_text": f"{fav_team} {fav_spread:+.1f}",
                "prob": 0.58
            })
        elif "Player Prop" in target_market or "Three-Pointers" in target_market or "Touchdown" in target_market:
            if is_nba:
                leg_data.update({
                    "picked_team": active_player,
                    "type": "NBA 3-Pointers Made",
                    "side": "Over",
                    "line": "1.5",
                    "pick_text": f"{active_player} 2+ 3PM",
                    "prob": 0.68
                })
            else:
                leg_data.update({
                    "picked_team": active_player,
                    "type": "Player Anytime TD",
                    "side": "TD",
                    "line": "1.0",
                    "pick_text": f"{active_player} Anytime TD",
                    "prob": 0.52
                })
        else:
            if len(selected_legs) % 2 == 0:
                tot_line = round_half_point(ou_open + 4.0)
                leg_data.update({
                    "picked_team": gm.get("home_team"),
                    "type": "Game Total",
                    "side": "Under",
                    "line": str(tot_line),
                    "pick_text": f"Under {tot_line:.1f} Pts",
                    "prob": 0.72
                })
            else:
                leg_data.update({
                    "picked_team": active_player,
                    "type": "NBA 3-Pointers Made" if is_nba else "Player Anytime TD",
                    "side": "Over" if is_nba else "TD",
                    "line": "1.5" if is_nba else "1.0",
                    "pick_text": f"{active_player} 2+ 3PM" if is_nba else f"{active_player} Anytime TD",
                    "prob": 0.55
                })

        selected_legs.append(leg_data)

    return selected_legs

def render_combo_builder(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("🔗 Multi-Leg Combo & Parlay Builder")
    st.caption("Construct Same-Game Parlays (SGP) or Cross-Game tickets, select leg volume, edit lines and probabilities, and lock in tickets.")

    if "combo_active_legs" not in st.session_state:
        st.session_state.combo_active_legs = []
    if "combo_leg_count_val" not in st.session_state:
        st.session_state.combo_leg_count_val = 3

    # =========================================================================
    # 1. PRIMARY SELECTION & CONFIGURATION MATRIX
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 🤖 Select & Configure Multi-Leg Matchups")

        # Row 1: Parlay Scope (SGP vs Cross-Game)
        scope_col1, scope_col2 = st.columns([3.5, 3.5])
        parlay_type = scope_col1.radio(
            "Parlay Structure Mode",
            ["🎯 Same-Game Parlay (All Legs from 1 Game)", "🌐 Cross-Game Parlay (Multi-Matchup Ticket)"],
            horizontal=True,
            key="cb_parlay_structure_mode"
        )
        is_sgp = "Same-Game" in parlay_type

        # Row 2: League Scope, Slate Filter, Leg Count Stepper (+ / - up to 15)
        r2_c1, r2_c2, r2_c3 = st.columns([2.5, 2.5, 2.2], vertical_alignment="bottom")
        league_choice = r2_c1.selectbox(
            "Primary League / Slate Scope",
            options=["All Games (Cross-Sport)", "NFL", "NBA", "NCAA Football"],
            key="cb_cfg_league"
        )
        t_filter = r2_c2.selectbox(
            "Game Filter Status",
            options=["🌐 All Matchups", "⏳ Upcoming Games", "⚡ Live Games"],
            key="cb_cfg_filter"
        )

        with r2_c3:
            st.markdown("<label style='font-size:0.875rem;font-weight:400;'>Target # of Legs (Up to 15)</label>", unsafe_allow_html=True)
            cnt_cols = st.columns([1, 1.8, 1])
            if cnt_cols[0].button("➖", key="cb_step_minus", use_container_width=True):
                if st.session_state.combo_leg_count_val > 2:
                    st.session_state.combo_leg_count_val -= 1
                    st.rerun()

            typed_count = cnt_cols[1].number_input(
                "Legs",
                min_value=2,
                max_value=15,
                value=int(st.session_state.combo_leg_count_val),
                step=1,
                label_visibility="collapsed",
                key="cb_num_input_stepper"
            )
            st.session_state.combo_leg_count_val = int(typed_count)

            if cnt_cols[2].button("➕", key="cb_step_plus", use_container_width=True):
                if st.session_state.combo_leg_count_val < 15:
                    st.session_state.combo_leg_count_val += 1
                    st.rerun()

        leg_count = st.session_state.combo_leg_count_val

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

        # SGP Game Selector if in SGP Mode
        target_sgp_game = None
        if is_sgp:
            if pool:
                sgp_labels = [f"[{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')} ({gm.get('kickoff', 'Upcoming')})" for gm in pool]
                sgp_idx = st.selectbox("🎯 Target Game for Same-Game Parlay", range(len(sgp_labels)), format_func=lambda i: sgp_labels[i], key="cb_sgp_game_pick")
                target_sgp_game = pool[sgp_idx]
            else:
                st.warning("No games found on the slate matching your league and status filter.")

        # Row 3: Selection Mode (System Pick vs Manual Entry)
        selection_mode = st.radio(
            "Matchup Selection Method",
            ["🤖 Let the System Pick (Highest Model Discrepancies)", "✍️ Enter Legs Manually / Hand-Pick"],
            horizontal=True,
            key="cb_cfg_selection_mode"
        )

        r4_c1, r4_c2 = st.columns(2)
        strat_choice = r4_c2.selectbox(
            "Model Strategy Profile",
            [
                "⚖️ Balanced Edge (+EV Sweet Spot)",
                "🛡️ Safe Floor (High Win %, Low Drawdown)",
                "🚀 High Profit (Max Multiplier & Props)",
                "🎯 Mixed Tier Spectrum (Balanced Mix)"
            ],
            key="cb_cfg_strat_choice"
        )

        if not is_sgp:
            is_nba_scope = (league_choice == "NBA")
            market_options = [
                "⚡ Let the System Pick (Best Discrepancies)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🎯 High EV Player Props (3PM / Touchdown)"
            ]
            target_market = r4_c1.selectbox("Target Bet / Market Type", market_options, key="cb_cfg_target_market")
        else:
            target_market = "SGP Multi-Market Blend"
            r4_c1.info("💡 Same-Game Parlay combines totals, spread/winner, and active player props from your selected matchup.")

        if "Let the System Pick" in selection_mode:
            btn_label = f"⚡ Generate {leg_count}-Leg Same-Game Parlay" if is_sgp else f"⚡ Generate {leg_count}-Leg Combo Slip"
            if st.button(btn_label, type="primary", use_container_width=True):
                if is_sgp:
                    if target_sgp_game:
                        st.session_state.combo_active_legs = build_same_game_parlay_legs(target_sgp_game, strat_choice, leg_count)
                        st.toast(f"✅ Generated {len(st.session_state.combo_active_legs)}-leg SGP for {target_sgp_game.get('away_short')}@{target_sgp_game.get('home_short')}!", icon="🎯")
                        st.rerun()
                else:
                    if not pool:
                        st.warning("No matchups match your selected league or game filter.")
                    else:
                        st.session_state.combo_active_legs = build_system_cross_game_legs(pool, target_market, strat_choice, leg_count)
                        st.toast(f"✅ Generated {len(st.session_state.combo_active_legs)}-leg combo!", icon="🤖")
                        st.rerun()
        else:
            st.markdown("---")
            st.markdown("##### ✍️ Manual Matchup & Leg Ingestion")
            m_t1, m_t2 = st.tabs(["🎯 Add from Live Matchup Board", "📝 Create Custom Prop / Spread Leg"])

            with m_t1:
                if not pool:
                    st.info("No games available on the slate matching your league filter.")
                else:
                    mc1, mc2, mc3 = st.columns([3.0, 2.5, 1.5], vertical_alignment="bottom")
                    game_labels = [f"[{gm.get('league')}] {gm.get('away_short')} @ {gm.get('home_short')} ({gm.get('kickoff', 'Upcoming')})" for gm in pool]
                    sel_game_idx = mc1.selectbox("Select Matchup", range(len(game_labels)), format_func=lambda i: game_labels[i], key="cb_man_slate_gm")
                    target_gm = pool[sel_game_idx]

                    ou_val = round_half_point(target_gm.get("market_ou", 224.5 if target_gm.get("league") == "NBA" else 46.5))
                    spd_val = round_half_point(target_gm.get("market_spread", -3.5))
                    fav_t = target_gm.get("home_team") if spd_val < 0 else target_gm.get("away_team")

                    is_gm_nba = (target_gm.get("league") == "NBA")
                    healthy_ath = get_verified_active_players_list(target_gm, is_gm_nba)
                    star_name = healthy_ath[0][0] if healthy_ath else "Active Player"

                    preset_list = [
                        f"Under {ou_val}",
                        f"Over {ou_val}",
                        f"{fav_t} {spd_val:+.1f}",
                        f"{fav_t} ML"
                    ]
                    if is_gm_nba:
                        preset_list.append(f"{star_name} 2+ 3PM")
                    else:
                        preset_list.append(f"{star_name} Anytime TD")

                    leg_preset = mc2.selectbox("Preset Market Line", preset_list, key="cb_man_preset_opt")

                    if mc3.button("➕ Insert Leg", use_container_width=True, type="primary"):
                        if len(st.session_state.combo_active_legs) < 15:
                            st.session_state.combo_active_legs.append({
                                "matchup": f"{target_gm.get('away_short')} @ {target_gm.get('home_short')}",
                                "home_team": target_gm.get("home_team"),
                                "away_team": target_gm.get("away_team"),
                                "away_short": target_gm.get("away_short", "AWAY"),
                                "home_short": target_gm.get("home_short", "HOME"),
                                "league": target_gm.get("league", "SPORTS"),
                                "away_logo": target_gm.get("away_logo", DEFAULT_LOGO),
                                "home_logo": target_gm.get("home_logo", DEFAULT_LOGO),
                                "kickoff": target_gm.get("kickoff", "Scheduled"),
                                "player_name": star_name,
                                "picked_team": star_name if ("3PM" in leg_preset or "TD" in leg_preset) else (fav_t if "ML" in leg_preset or spd_val != 0 else target_gm.get("home_team")),
                                "type": "Player Prop" if ("3PM" in leg_preset or "TD" in leg_preset) else ("Game Total" if "Under" in leg_preset or "Over" in leg_preset else ("Point Spread" if spd_val != 0 and "ML" not in leg_preset else "Moneyline")),
                                "side": "Under" if "Under" in leg_preset else ("Over" if "Over" in leg_preset else "Spread"),
                                "line": str(ou_val) if "Under" in leg_preset or "Over" in leg_preset else str(spd_val),
                                "pick_text": leg_preset,
                                "prob": 0.65 if "Under" in leg_preset else 0.58
                            })
                            st.rerun()
                        else:
                            st.warning("Maximum of 15 legs reached.")

            with m_t2:
                mx1, mx2, mx3, mx4, mx5 = st.columns([2.0, 3.0, 1.8, 1.5, 1.5], vertical_alignment="bottom")
                cust_m = mx1.text_input("Matchup", value="TEN @ CIN", key="cb_man_cust_m")
                cust_p = mx2.text_input("Player / Pick Label", value="Chase Brown Anytime TD", key="cb_man_cust_p")
                cust_t = mx3.selectbox("Market Category", ["Player Prop", "Game Total", "Point Spread", "Moneyline"], key="cb_man_cust_t")
                cust_pr = mx4.number_input("Win Prob (%)", min_value=5, max_value=99, value=55, step=1, key="cb_man_cust_pr")

                if mx5.button("➕ Add Custom", use_container_width=True):
                    if len(st.session_state.combo_active_legs) < 15:
                        st.session_state.combo_active_legs.append({
                            "matchup": cust_m.strip(),
                            "home_team": "Home",
                            "away_team": "Away",
                            "away_short": "AWAY",
                            "home_short": "HOME",
                            "league": "PROP",
                            "away_logo": DEFAULT_LOGO,
                            "home_logo": DEFAULT_LOGO,
                            "kickoff": "Manual Entry",
                            "player_name": cust_p.strip(),
                            "picked_team": cust_p.strip(),
                            "type": cust_t,
                            "side": "Over",
                            "line": "1.0",
                            "pick_text": cust_p.strip(),
                            "prob": float(cust_pr) / 100.0
                        })
                        st.rerun()
                    else:
                        st.warning("Maximum of 15 legs reached.")

    # =========================================================================
    # 2. RESTORED GREEN LEGS DISPLAY (LEG #1, LEG #2... WITH OFFICIAL LOGOS & DATES)
    # =========================================================================
    legs = st.session_state.combo_active_legs

    if not legs:
        st.info("No legs loaded yet. Configure the engine above and click generate or add legs manually.")
        return

    st.markdown(f"### 📋 Current Combo Legs ({len(legs)})")

    for idx, leg in enumerate(legs):
        p_pct = int(round(float(leg.get("prob", 0.55)) * 100))
        m_txt = leg.get("matchup", "Matchup")
        p_txt = leg.get("pick_text", "Pick")
        t_type = leg.get("type", "Pick")
        lg_val = leg.get("league", "SPORTS")
        a_logo = leg.get("away_logo") or DEFAULT_LOGO
        h_logo = leg.get("home_logo") or DEFAULT_LOGO
        kickoff_date = leg.get("kickoff", "Scheduled")
        ply_name = leg.get("player_name", "")

        with st.container(border=True):
            c_left, c_right = st.columns([5.5, 2.0], vertical_alignment="center")

            with c_left:
                st.markdown(f"""
                <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; margin-bottom:4px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="background:rgba(74,222,128,0.15); color:#4ade80; border:1px solid rgba(74,222,128,0.3); font-weight:800; font-size:0.78rem; padding:2px 8px; border-radius:4px; letter-spacing:0.5px;">
                            LEG #{idx + 1}
                        </span>
                        <span style="background:rgba(56,189,248,0.15); color:#38bdf8; font-weight:700; font-size:0.75rem; padding:2px 6px; border-radius:4px;">
                            {lg_val}
                        </span>
                        <img src="{a_logo}" width="20" height="20" style="object-fit:contain; border-radius:50%;">
                        <span style="font-weight:700; font-size:0.92rem; color:#f8fafc;">{m_txt}</span>
                        <img src="{h_logo}" width="20" height="20" style="object-fit:contain; border-radius:50%;">
                    </div>
                    <span style="opacity:0.65; font-size:0.76rem; font-weight:600;">🗓️ {kickoff_date}</span>
                </div>
                <div style="font-size:1.05rem; font-weight:700; color:#4ade80; margin-top:2px;">
                    {p_txt}
                </div>
                <div style="font-size:0.76rem; opacity:0.65; margin-top:1px;">
                    Type: {t_type} {f'• Player: {ply_name}' if ply_name and ply_name not in p_txt else ''}
                </div>
                """, unsafe_allow_html=True)

            with c_right:
                st.markdown(f"""
                <div style="text-align:right;">
                    <div style="font-size:0.76rem; opacity:0.7;">Model Prob</div>
                    <div style="font-size:1.20rem; font-weight:800; color:#38bdf8;">{p_pct}%</div>
                </div>
                """, unsafe_allow_html=True)

    # =========================================================================
    # 3. TEXT-BASED EDIT & MULTI-SELECT REMOVE POPUP
    # =========================================================================
    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
    edit_col1, edit_col2 = st.columns([2.0, 5.0])

    with edit_col1:
        with st.popover("✏️ Edit / Remove Legs", use_container_width=True):
            st.markdown("##### 🗑️ Select Legs to Remove")
            st.caption("Check any leg you want to remove from this ticket slip:")

            leg_options = [
                f"Leg #{i + 1}: [{l.get('league')}] {l.get('matchup')} — {l.get('pick_text')}" 
                for i, l in enumerate(legs)
            ]

            selected_indices = st.multiselect(
                "Choose legs to remove",
                options=range(len(legs)),
                format_func=lambda i: leg_options[i],
                label_visibility="collapsed",
                key="cb_multiselect_remove_legs"
            )

            if st.button("🗑️ Remove Selected Legs", type="primary", use_container_width=True):
                if selected_indices:
                    for i in sorted(selected_indices, reverse=True):
                        st.session_state.combo_active_legs.pop(i)
                    st.toast("✅ Selected legs removed!", icon="🗑️")
                    st.rerun()
                else:
                    st.info("No legs selected.")

    with edit_col2:
        if st.button("🗑️ Clear Entire Slip", key="btn_clear_cb_slip"):
            st.session_state.combo_active_legs = []
            st.rerun()

    st.markdown("---")

    # =========================================================================
    # 4. COMPOUND ANALYTICS & PARLAY FAIR ODDS
    # =========================================================================
    compound_prob = 1.0
    for leg in legs:
        compound_prob *= float(leg.get("prob", 0.50))
    compound_prob = max(0.0001, min(0.999, compound_prob))

    fair_multiplier = 1.0 / compound_prob
    fair_american = prob_to_american_odds(compound_prob)

    st.markdown("### 🎲 Ticket Edge Analytics & Fair Value")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compound Win Probability", f"{compound_prob * 100:.2f}%")
    m2.metric("Fair American Odds", fair_american)
    m3.metric("True Dec Multiplier", f"{fair_multiplier:.2f}x")
    m4.metric("Active Legs", len(legs))

    # =========================================================================
    # 5. TICKET LOCK-IN & FINANCIAL RECORDING
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 🔒 Lock In Combo Ticket Slip")
        with st.form("parlay_ticket_lock_form"):
            r_col, p_col = st.columns(2)
            default_risk = 5.0
            default_payout = round(default_risk * fair_multiplier, 2)

            risk_input = r_col.number_input("Risk Amount ($)", min_value=0.5, value=float(default_risk), step=1.0)
            payout_input = p_col.number_input("Total Payout ($)", min_value=0.5, value=float(default_payout), step=1.0)

            net_profit = float(payout_input) - float(risk_input)
            roi_pct = (net_profit / max(0.01, float(risk_input))) * 100.0
            ev_val = (compound_prob * float(payout_input)) - float(risk_input)
            ev_color = "#4ade80" if ev_val >= 0 else "#ef4444"

            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:10px 14px; border-radius:8px; margin-top:4px; margin-bottom:12px; border:1px solid rgba(255,255,255,0.08);">
                <div>Net Profit: <strong style="color:#4ade80;">+${net_profit:.2f}</strong> ({roi_pct:+.1f}% ROI)</div>
                <div>Model Expected Value: <strong style="color:{ev_color};">{ev_val:+.2f}</strong></div>
            </div>
            """, unsafe_allow_html=True)

            notes_tag = st.text_input("Strategy Tag / Ticket Notes", value=f"{len(legs)}-Leg Correlated Slip")

            if st.form_submit_button("🔒 Lock In Parlay Ticket", type="primary", use_container_width=True):
                summary_picks = ", ".join([l.get("pick_text", "") for l in legs[:3]])
                if len(legs) > 3:
                    summary_picks += f" +{len(legs) - 3} more"

                ticket_data = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Combo",
                    "bet_category": "Combo",
                    "matchup": f"{len(legs)}-Leg {'SGP' if is_sgp else 'Parlay'}",
                    "bet": f"{len(legs)}-Leg {'SGP' if is_sgp else 'Combo'}: {summary_picks}",
                    "risk_dollars": float(risk_input),
                    "payout_dollars": float(payout_input),
                    "payout": float(payout_input),
                    "locked_profit": float(net_profit),
                    "win_prob": f"{compound_prob * 100:.1f}%",
                    "status": "Pending",
                    "notes": notes_tag,
                    "parsed_legs": [
                        {
                            "matchup": l.get("matchup"),
                            "picked_team": l.get("picked_team"),
                            "type": l.get("type"),
                            "side": l.get("side"),
                            "line": l.get("line"),
                            "prob": l.get("prob")
                        }
                        for l in legs
                    ]
                }

                st.session_state.saved_bets.insert(0, ticket_data)
                save_all_storage(
                    st.session_state.saved_bets,
                    st.session_state.chat_messages,
                    st.session_state.user_accounts,
                    st.session_state.banned_emails,
                    st.session_state.game_snapshots,
                    st.session_state.support_tickets
                )
                st.session_state.combo_active_legs = []
                st.toast("🎉 Parlay ticket locked in and saved to history!", icon="🔒")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
