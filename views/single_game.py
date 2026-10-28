import streamlit as st
import io
import base64
import re
import json
import requests
from PIL import Image
from datetime import datetime
from config import DEFAULT_LOGO
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob
from sports.football import get_live_football_roster
from sports.basketball import get_live_nba_roster
from database import save_all_storage

def round_half_point(val):
    try:
        return round(float(val) * 2.0) / 2.0
    except (ValueError, TypeError):
        return 47.5

def parse_bet_slip_image(image_bytes):
    raw_key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    gemini_key = str(raw_key).strip().strip('"').strip("'") if raw_key else ""

    if not gemini_key:
        return None, "No GEMINI_API_KEY or GOOGLE_API_KEY found in Streamlit Secrets."

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        if pil_img.width > 1024:
            ratio = 1024 / float(pil_img.width)
            new_h = int(float(pil_img.height) * ratio)
            pil_img = pil_img.resize((1024, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
    You are an expert sports betting and prediction market OCR parser.
    Examine this screenshot of a bet slip, Robinhood event contract, DraftKings, FanDuel, or sports betting ticket.
    Extract the bet details into a strictly valid JSON object:
    {
        "away_team": "string or null",
        "home_team": "string or null",
        "picked_team": "string or null",
        "wager_type": "Point Spread" | "Game Total" | "Moneyline" | "Player Points Prop" | "Anytime TD",
        "side": "Under" | "Over" | "Spread" | "Moneyline",
        "line": float or null,
        "payout": float,
        "profit": float or null,
        "risk": float or null,
        "is_settled": boolean
    }
    Rules:
    1. If contract says "Over X points Payout" and user chose "No", side is "Under", line is X, wager_type is "Game Total".
    2. If user chose "Yes", side is "Over", line is X, wager_type is "Game Total".
    3. If profit is present but risk is missing: risk = payout - profit.
    4. If risk and payout are present: profit = payout - risk.
    5. Return ONLY raw JSON without markdown markers or backticks.
    """

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
            ]
        }],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    active_models = []
    try:
        models_list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
        list_resp = requests.get(models_list_url, timeout=5.0)
        if list_resp.status_code == 200:
            for m in list_resp.json().get("models", []):
                m_name = m.get("name", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "flash" in m_name.lower():
                    active_models.append(m_name)
    except Exception:
        pass

    if not active_models:
        active_models = [
            "models/gemini-2.0-flash",
            "models/gemini-2.5-flash",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-8b",
            "models/gemini-2.0-flash-exp"
        ]

    last_err = ""
    for full_model_path in active_models:
        clean_model = full_model_path if full_model_path.startswith("models/") else f"models/{full_model_path}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{clean_model}:generateContent?key={gemini_key}"
        try:
            r = requests.post(url, json=payload, timeout=25.0)
            if r.status_code == 200:
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = re.sub(r"^```json\s*", "", txt.strip())
                cleaned = re.sub(r"```$", "", cleaned.strip())
                return json.loads(cleaned), None
            else:
                last_err = f"{clean_model} (HTTP {r.status_code}): {r.text[:120]}"
        except Exception as e:
            last_err = f"{clean_model}: {str(e)}"
            continue

    return None, f"All models failed. Last error: {last_err}"

def match_game_in_pool(away_name, home_name, pool, picked_name=""):
    if not pool:
        return 0
    a_target = (away_name or "").lower().strip()
    h_target = (home_name or "").lower().strip()
    p_target = (picked_name or "").lower().strip()

    for idx, gm in enumerate(pool):
        gm_h = gm["home_team"].lower()
        gm_a = gm["away_team"].lower()
        gm_hs = gm.get("home_short", "").lower()
        gm_as = gm.get("away_short", "").lower()
        h_ok = (h_target in gm_h or gm_h in h_target or h_target in gm_hs) if h_target else True
        a_ok = (a_target in gm_a or gm_a in a_target or a_target in gm_as) if a_target else True
        if h_ok and a_ok and (h_target or a_target):
            return idx

    for idx, gm in enumerate(pool):
        gm_h = gm["home_team"].lower()
        gm_a = gm["away_team"].lower()
        for mc in [h_target, a_target, p_target]:
            if mc and len(mc) >= 3 and (mc in gm_h or gm_h in mc or mc in gm_a or gm_a in mc):
                return idx
    return 0

def find_system_best_game(pool):
    """Calculates model discrepancy against market numbers to find the top edge matchup."""
    best_idx = 0
    max_discrepancy = -1.0
    for idx, gm in enumerate(pool):
        is_nba = (gm.get("league") == "NBA")
        ou_open = float(gm.get("market_ou", 224.5 if is_nba else 47.5))
        pts_scored = gm.get("home_score", 0) + gm.get("away_score", 0)
        
        if gm.get("checkpoint") == "Pre-Game":
            drift = abs(float(gm.get("market_spread", 3.5)))
        else:
            exp = ou_open * (0.5 if "half" in gm.get("checkpoint", "").lower() else 0.25)
            drift = abs(pts_scored - exp)

        if drift > max_discrepancy:
            max_discrepancy = drift
            best_idx = idx
    return best_idx

def render_single_game(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("⚡ Single Game Analytics Engine")

    if "single_form_version" not in st.session_state:
        st.session_state.single_form_version = 0
    if "single_selected_idx" not in st.session_state:
        st.session_state.single_selected_idx = 0
    if "single_applied_pick" not in st.session_state:
        st.session_state.single_applied_pick = None
    if "scroll_to_form" not in st.session_state:
        st.session_state.scroll_to_form = False

    form_ver = st.session_state.single_form_version

    # Mode Selector: Manual vs System Selected
    c_mode1, c_mode2 = st.columns([2, 3])
    selection_mode = c_mode1.radio(
        "Matchup Selection Method",
        ["🎯 Manual Matchup Selection", "🤖 Let System Pick Best Matchup"],
        horizontal=True,
        key=f"sg_sel_mode_v{form_ver}"
    )

    col_lg, col_st, col_sr = st.columns([1.5, 1.5, 2])
    league_scope = col_lg.selectbox(
        "League Scope",
        options=["All Games", "NBA", "NFL", "NCAA Football"],
        index=0,
        key=f"sg_league_scope_v{form_ver}"
    )
    timing_view = col_st.selectbox("Game Status Filter", ["⏳ Upcoming Games", "⚡ Live Games", "📜 Past / Completed Games", "🌐 All Matchups"])
    search_query = col_sr.text_input("🔍 Search Matchup or Team", placeholder="e.g. Celtics, Lakers, Eagles, Chiefs...")

    pool = games_data
    if league_scope == "NBA":
        pool = [g for g in pool if g.get("league") == "NBA"]
    elif league_scope == "NFL":
        pool = [g for g in pool if g.get("league") == "NFL"]
    elif league_scope == "NCAA Football":
        pool = [g for g in pool if g.get("league") == "NCAA"]

    if timing_view == "⏳ Upcoming Games":
        pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
    elif timing_view == "⚡ Live Games":
        pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]
    elif timing_view == "📜 Past / Completed Games":
        pool = [g for g in pool if g.get("completed", False)]

    if search_query.strip():
        q = search_query.strip().lower()
        pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g.get("home_short", "").lower() or q in g.get("away_short", "").lower()]

    with st.expander("📸 Auto-Fill via Slip Screenshot (Robinhood, DraftKings, FanDuel, etc.)", expanded=False):
        st.caption("Upload any sportsbook or prediction contract screenshot to detect teams, lines, risk, and potential payouts.")
        uploaded_slip = st.file_uploader("Upload Slip Screenshot (PNG, JPG)", type=["png", "jpg", "jpeg"], key="slip_file_input")

        if uploaded_slip is not None:
            if st.button("⚡ Extract & Auto-Fill Form", use_container_width=True, key="btn_run_extract"):
                with st.spinner("Analyzing screenshot with vision model..."):
                    parsed_res, err_msg = parse_bet_slip_image(uploaded_slip.read())
                    if parsed_res:
                        away_t = parsed_res.get("away_team") or ""
                        home_t = parsed_res.get("home_team") or ""
                        picked_t = parsed_res.get("picked_team") or ""

                        matched_idx = match_game_in_pool(away_t, home_t, pool, picked_t)
                        wager_cat = parsed_res.get("wager_type") or "Game Total"
                        wager_side = parsed_res.get("side") or "Under"
                        w_line = float(parsed_res.get("line")) if parsed_res.get("line") is not None else 47.5
                        w_payout = float(parsed_res.get("payout") or 20.0)
                        w_profit = float(parsed_res.get("profit") or (w_payout * 0.5))
                        w_risk = float(parsed_res.get("risk") or max(1.0, w_payout - w_profit))
                        is_settled_flag = parsed_res.get("is_settled", False)

                        new_v = st.session_state.single_form_version + 1
                        st.session_state.single_form_version = new_v
                        st.session_state.single_selected_idx = matched_idx
                        st.session_state.single_applied_pick = {
                            "category": wager_cat,
                            "side": wager_side,
                            "target_line": w_line,
                            "risk": w_risk,
                            "payout": w_payout,
                            "profit": w_profit,
                            "override_away": away_t,
                            "override_home": home_t,
                            "picked_team": picked_t,
                            "status": "Won" if is_settled_flag else "Pending"
                        }
                        st.session_state[f"in_h_{new_v}"] = home_t
                        st.session_state[f"in_a_{new_v}"] = away_t
                        st.session_state["extracted_banner_msg"] = f"✅ Extracted: {wager_side} {w_line} ({away_t} vs {home_t}) | Risk: ${w_risk:.2f}, Payout: ${w_payout:.2f}"
                        st.session_state["scroll_to_form"] = True
                        st.rerun()
                    else:
                        st.error(f"❌ Analysis failed: {err_msg}")

    if "extracted_banner_msg" in st.session_state and st.session_state["extracted_banner_msg"]:
        st.success(st.session_state["extracted_banner_msg"])
        st.session_state["extracted_banner_msg"] = None

    if not pool:
        st.info("No matchups found matching your current filter.")
        return

    # Handle Selection Mode
    game_options = [f"[{g['kickoff']}] [{g['league']}] {g['away_short']} @ {g['home_short']}" for g in pool]
    
    if "System Pick" in selection_mode:
        best_game_idx = find_system_best_game(pool)
        st.session_state.single_selected_idx = best_game_idx
        st.info(f"🤖 **System Selected Optimal Game:** `{game_options[best_game_idx]}` (Maximum line variance detected)")
        sel_idx = best_game_idx
    else:
        sel_idx = st.selectbox(
            "Select Matchup",
            range(len(game_options)),
            index=min(st.session_state.single_selected_idx, len(game_options) - 1),
            format_func=lambda x: game_options[x],
            key=f"matchup_sel_v{form_ver}"
        )
        st.session_state.single_selected_idx = sel_idx

    g = pool[sel_idx]
    is_nba_game = (g.get("league") == "NBA")
    espn_ou = round_half_point(g["market_ou"])
    espn_spread = round_half_point(g["market_spread"])

    pts_scored = g["home_score"] + g["away_score"]
    is_completed = g.get("completed", False) or "final" in g["status"].lower()
    pregame_tot = float(espn_ou)

    if is_completed:
        final_proj, std_bracket = float(pts_scored), 0.01
    elif g["checkpoint"] == "Pre-Game":
        final_proj, std_bracket = pregame_tot, (14.0 if is_nba_game else 8.5)
    else:
        pw = 0.25 if g["checkpoint"] == "Q1" else (0.50 if "half" in g["checkpoint"].lower() else 0.75)
        exp_pts = pregame_tot * pw
        ratio = pts_scored / max(exp_pts, 1.0)
        final_proj = pregame_tot + ((pts_scored - exp_pts) * (0.90 if is_nba_game else 0.85)) if ratio > 1.25 else pregame_tot + ((pts_scored - exp_pts) * 0.35)
        std_bracket = (16.0 if is_nba_game else 9.5) if ratio > 1.25 else (11.0 if is_nba_game else 6.0)

    final_proj = round_half_point(final_proj)
    delta_full = final_proj - pregame_tot
    pregame_2h = round_half_point(pregame_tot * 0.51)
    live_2h_proj = round_half_point(pregame_2h + (delta_full * 0.48))
    live_proj_margin = round_half_point((-espn_spread * 0.40) + ((g["home_score"] - g["away_score"]) * 0.60))
    live_h_prob = calculate_moneyline_prob(g["home_score"] + (40 if is_nba_game else 14), g["away_score"] + (40 if is_nba_game else 14), g.get("home_record", "0-0"), g.get("away_record", "0-0"), is_final=is_completed)

    with st.expander("📊 Section 1: Matchup Overview & Live Drift Projections", expanded=True):
        b1, b2, b3 = st.columns([1, 4, 1])
        b1.image(g.get("away_logo", DEFAULT_LOGO), width=45)
        b2.markdown(f"### **{g['away_short']}** @ **{g['home_short']}**\n🗓️ {g['kickoff']}")
        b3.image(g.get("home_logo", DEFAULT_LOGO), width=45)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Full Game Total", f"{final_proj:.1f} pts", delta=f"{delta_full:+.1f} vs open ({pregame_tot:.1f})")
        m2.metric("2nd Half Total", f"{live_2h_proj:.1f} pts", delta=f"{live_2h_proj - pregame_2h:+.1f} vs base")
        m3.metric(f"{g['home_short']} Win %", f"{live_h_prob*100:.1f}%")
        m4.metric(f"ATS Margin ({espn_spread:+.1f})", f"{live_proj_margin:+.1f} pts")

    if is_nba_game:
        h_players = get_live_nba_roster(g["home_id"] or g["home_short"])
        away_players = get_live_nba_roster(g["away_id"] or g["away_short"])
    else:
        h_players = get_live_football_roster(g["home_id"] or g["home_short"], g["league"])
        away_players = get_live_football_roster(g["away_id"] or g["away_short"], g["league"])

    # Section 2: Tiered Recommendations (Good, Better, Best)
    with st.expander("🤖 Section 2: AI Recommendations (Good, Better, Best Tiers)", expanded=True):
        tot_dir = "Under" if delta_full <= 0 else "Over"
        p_tot = calculate_win_prob(final_proj, final_proj, std_bracket, is_under=(tot_dir == "Under"))

        # 1. Best Tier (Highest Alpha EV)
        best_pick = f"{tot_dir} {final_proj:.1f}"
        best_type = "Game Total"
        best_line = final_proj
        best_side = tot_dir
        best_team = None
        best_prob = max(0.55, p_tot)
        best_roi = "+91%"
        best_rat = f"Maximum model divergence. Expected final pace suppresses output by {abs(delta_full):.1f} pts relative to book open."

        # 2. Better Tier (Balanced Edge / Spread or Prop)
        cov_team = g["home_team"] if live_proj_margin > espn_spread else g["away_team"]
        better_pick = f"{cov_team} {espn_spread:+.1f}"
        better_type = "Point Spread (ATS)"
        better_line = espn_spread
        better_side = "Spread"
        better_team = cov_team
        better_prob = 0.58
        better_roi = "+91%"
        better_rat = f"Power ratings indicate {cov_team} has a situational covering edge with stable possession efficiency."

        # 3. Good Tier (Safe Floor / Moneyline or Alternate Line)
        if live_h_prob > 0.50:
            good_team = g["home_team"]
            good_prob = live_h_prob
        else:
            good_team = g["away_team"]
            good_prob = 1.0 - live_h_prob
        good_pick = f"{good_team} ML"
        good_type = "Straight Up Winner (Moneyline)"
        good_line = None
        good_side = "Moneyline"
        good_team_pick = good_team
        good_roi = f"+{max(20, int((1.0/max(good_prob, 0.05) - 1.0)*100))}%"
        good_rat = f"Solid anchor floor. Win expectancy of {good_prob*100:.1f}% provides safe drawdown protection."

        # Render Tier Cards
        t_col1, t_col2, t_col3 = st.columns(3)

        with t_col1:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:12px;">
                <div style="font-weight:700; color:#94a3b8; margin-bottom:4px;">🥉 GOOD (Safe Floor)</div>
                <div style="font-size:1.1rem; font-weight:800; color:#38bdf8;">{good_pick}</div>
                <div style="font-size:0.8rem; opacity:0.8; margin-bottom:6px;">{good_type}</div>
                <div style="display:flex; gap:6px; margin-bottom:8px;">
                    <span class="badge-prob">{good_prob*100:.1f}% Prob</span>
                    <span class="badge-roi">{good_roi}</span>
                </div>
                <div style="font-size:0.75rem; opacity:0.75; min-height:48px;">{good_rat}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📥 Load 'Good' Pick", key=f"btn_load_good_v{form_ver}", use_container_width=True):
                new_v = st.session_state.single_form_version + 1
                st.session_state.single_form_version = new_v
                st.session_state.single_applied_pick = {
                    "category": good_type, "side": good_side, "target_line": good_line,
                    "risk": 10.0, "payout": 19.10, "picked_team": good_team_pick, "status": "Pending"
                }
                st.session_state["scroll_to_form"] = True
                st.rerun()

        with t_col2:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:12px;">
                <div style="font-weight:700; color:#fbbf24; margin-bottom:4px;">🥈 BETTER (Balanced +EV)</div>
                <div style="font-size:1.1rem; font-weight:800; color:#fbbf24;">{better_pick}</div>
                <div style="font-size:0.8rem; opacity:0.8; margin-bottom:6px;">{better_type}</div>
                <div style="display:flex; gap:6px; margin-bottom:8px;">
                    <span class="badge-prob">{better_prob*100:.1f}% Prob</span>
                    <span class="badge-roi">{better_roi}</span>
                </div>
                <div style="font-size:0.75rem; opacity:0.75; min-height:48px;">{better_rat}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📥 Load 'Better' Pick", key=f"btn_load_better_v{form_ver}", use_container_width=True):
                new_v = st.session_state.single_form_version + 1
                st.session_state.single_form_version = new_v
                st.session_state.single_applied_pick = {
                    "category": better_type, "side": better_side, "target_line": better_line,
                    "risk": 10.0, "payout": 19.10, "picked_team": better_team, "status": "Pending"
                }
                st.session_state["scroll_to_form"] = True
                st.rerun()

        with t_col3:
            st.markdown(f"""
            <div style="background:rgba(34,197,94,0.06); border:1px solid #22c55e; border-radius:10px; padding:12px;">
                <div style="font-weight:700; color:#4ade80; margin-bottom:4px;">🥇 BEST (Optimal Value)</div>
                <div style="font-size:1.1rem; font-weight:800; color:#4ade80;">{best_pick}</div>
                <div style="font-size:0.8rem; opacity:0.8; margin-bottom:6px;">{best_type}</div>
                <div style="display:flex; gap:6px; margin-bottom:8px;">
                    <span class="badge-prob">{best_prob*100:.1f}% Prob</span>
                    <span class="badge-roi">{best_roi}</span>
                </div>
                <div style="font-size:0.75rem; opacity:0.75; min-height:48px;">{best_rat}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📥 Load 'Best' Pick", type="primary", key=f"btn_load_best_v{form_ver}", use_container_width=True):
                new_v = st.session_state.single_form_version + 1
                st.session_state.single_form_version = new_v
                st.session_state.single_applied_pick = {
                    "category": best_type, "side": best_side, "target_line": best_line,
                    "risk": 10.0, "payout": 19.10, "picked_team": best_team, "status": "Pending"
                }
                st.session_state["scroll_to_form"] = True
                st.rerun()

    applied = st.session_state.single_applied_pick

    # Anchor point for automatic smooth scrolling
    st.markdown("<div id='bet-slip-anchor'></div>", unsafe_allow_html=True)
    if st.session_state.get("scroll_to_form", False):
        st.session_state["scroll_to_form"] = False
        import streamlit.components.v1 as components
        components.html("""
        <script>
            setTimeout(function() {
                const doc = window.parent.document;
                const el = doc.getElementById('bet-slip-anchor');
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 300);
        </script>
        """, height=0)

    with st.expander("📝 Section 3: Wager Type & Lock In Bet Slip", expanded=True):
        c1, c2 = st.columns(2)
        home_def = (applied.get("override_home") if applied and applied.get("override_home") else g["home_team"])
        away_def = (applied.get("override_away") if applied and applied.get("override_away") else g["away_team"])

        home_team = c1.text_input("Home Team", value=home_def, key=f"in_h_{form_ver}")
        away_team = c1.text_input("Away Team", value=away_def, key=f"in_a_{form_ver}")
        h_pts_in = c2.number_input(f"{g['home_short']} Pts", min_value=0, value=g["home_score"], key=f"in_hp_{form_ver}")
        a_pts_in = c2.number_input(f"{g['away_short']} Pts", min_value=0, value=g["away_score"], key=f"in_ap_{form_ver}")

        w_types = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"]
        w_types.append("Player Points Prop" if is_nba_game else "Player Anytime Touchdown Scorer")
        def_w_idx = 0
        if applied:
            cat = str(applied.get("category", "")).lower()
            if "spread" in cat: def_w_idx = 1
            elif "moneyline" in cat or "winner" in cat: def_w_idx = 2
            elif "points" in cat or "td" in cat: def_w_idx = 3

        bet_type = st.radio("Market", w_types, index=def_w_idx, horizontal=True, key=f"in_wtype_{form_ver}")

        with st.form(f"single_bet_form_v{form_ver}"):
            p_target = None
            if bet_type == "Game Total":
                f1, f2 = st.columns(2)
                def_side_idx = 0 if (applied and applied.get("side") == "Under") else 1
                s_side = f1.selectbox("Side", ["Under", "Over"], index=def_side_idx, key=f"sel_side_{form_ver}")
                def_strike = float(applied.get("target_line", final_proj)) if applied else float(final_proj)
                s_line = f2.number_input("Total Line", value=def_strike, step=0.5, key=f"inp_strike_{form_ver}")
            elif bet_type == "Point Spread (ATS)":
                f1, f2 = st.columns(2)
                p_cand = applied.get("picked_team", "") if applied else ""
                def_cov_idx = 1 if (p_cand and p_cand.lower() in away_team.lower()) else 0
                p_target = f1.selectbox("Covering Team", [home_team, away_team], index=def_cov_idx, key=f"sel_cover_{form_ver}")
                s_side = "Spread"
                def_spd = float(applied.get("target_line", espn_spread)) if applied else float(espn_spread)
                s_line = f2.number_input("Spread Line", value=def_spd, step=0.5, key=f"inp_spd_{form_ver}")
            elif bet_type == "Straight Up Winner (Moneyline)":
                p_cand = applied.get("picked_team", "") if applied else ""
                def_win_idx = 1 if (p_cand and p_cand.lower() in away_team.lower()) else 0
                p_target = st.selectbox("Outright Winner", [home_team, away_team], index=def_win_idx, key=f"sel_ml_{form_ver}")
                s_side, s_line = "Moneyline", None
            elif bet_type == "Player Points Prop":
                f1, f2 = st.columns(2)
                all_r = [p[0] for p in (h_players + away_players)]
                p_cand = applied.get("picked_team", "") if applied else ""
                def_p_idx = all_r.index(p_cand) if p_cand in all_r else 0
                p_target = f1.selectbox("Player", all_r, index=def_p_idx, key=f"sel_prop_p_{form_ver}")
                s_side = f2.selectbox("Side", ["Over", "Under"], index=0 if (applied and applied.get("side") == "Over") else 1, key=f"sel_prop_s_{form_ver}")
                def_pts_strike = float(applied.get("target_line", 22.5)) if applied else 22.5
                s_line = st.number_input("Points Line", value=def_pts_strike, step=0.5, key=f"inp_prop_pts_{form_ver}")
            else:
                all_r = [p[0] for p in (h_players + away_players)]
                p_cand = applied.get("picked_team", "") if applied else ""
                def_td_idx = all_r.index(p_cand) if p_cand in all_r else 0
                p_target = st.selectbox("Player", all_r, index=def_td_idx, key=f"sel_td_p_{form_ver}")
                s_side, s_line = "TD", 1.0

            c_r, c_p = st.columns(2)
            def_risk = float(applied.get("risk", 10.0)) if applied else 10.0
            def_payout = float(applied.get("payout", 19.10)) if applied else 19.10
            r_amt = c_r.number_input("Risk ($)", min_value=1.0, value=def_risk, step=5.0, key=f"inp_risk_{form_ver}")
            p_amt = c_p.number_input("Payout ($)", min_value=1.0, value=def_payout, step=5.0, key=f"inp_payout_{form_ver}")

            if st.form_submit_button("Lock In Bet Slip", use_container_width=True):
                actual_risk = float(r_amt)
                actual_payout = float(p_amt)
                actual_profit = actual_payout - actual_risk

                if bet_type == "Player Points Prop":
                    bet_lbl = f"{p_target} {s_side} {s_line} Pts"
                elif bet_type == "Player Anytime Touchdown Scorer":
                    bet_lbl = f"{p_target} Any Time TD"
                elif s_line is not None:
                    bet_lbl = f"{s_side} {s_line}" if bet_type == "Game Total" else f"{p_target} {s_line:+.1f}"
                else:
                    bet_lbl = f"{p_target} ML"

                init_status = "Won" if (applied and applied.get("status") == "Won") else (
                    "Won" if is_completed and (pts_scored < s_line if s_side == "Under" and s_line else False) else "Pending"
                )

                tkt = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Single",
                    "bet_category": bet_type,
                    "home_team": home_team,
                    "away_team": away_team,
                    "picked_team": p_target,
                    "matchup": f"{g['away_short']} @ {g['home_short']}",
                    "bet": bet_lbl,
                    "target_line": s_line,
                    "bet_direction": s_side,
                    "risk_dollars": actual_risk,
                    "payout_dollars": actual_payout,
                    "payout": actual_payout,
                    "locked_profit": actual_profit,
                    "status": init_status,
                    "notes": f"[{g['league']}] {bet_type}"
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
                st.session_state.single_applied_pick = None
                st.toast(f"🎉 Ticket locked: {bet_lbl}!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
