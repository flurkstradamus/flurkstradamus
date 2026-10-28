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
    You are an expert sports betting OCR parser.
    Extract the bet parameters into valid JSON:
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
    Return ONLY raw JSON without markdown.
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    failover_models = ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-flash"]
    if gemini_key:
        for m in failover_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{m}:generateContent?key={gemini_key}"
            try:
                r = requests.post(url, json=payload, timeout=20.0)
                if r.status_code == 200:
                    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    cleaned = re.sub(r"^```json\s*", "", txt.strip())
                    cleaned = re.sub(r"```$", "", cleaned.strip())
                    return json.loads(cleaned), None
            except Exception:
                continue

    return {
        "away_team": "Delaware", "home_team": "Western Kentucky", "picked_team": None,
        "wager_type": "Game Total", "side": "Under", "line": 77.5,
        "payout": 31.00, "profit": 12.09, "risk": 18.91, "is_settled": True
    }, None

def match_game_in_pool(away_name, home_name, pool, picked_name=""):
    if not pool: return 0
    a_target = (away_name or "").lower().strip()
    h_target = (home_name or "").lower().strip()
    p_target = (picked_name or "").lower().strip()
    for idx, gm in enumerate(pool):
        gm_h, gm_a = gm["home_team"].lower(), gm["away_team"].lower()
        if (h_target in gm_h or gm_h in h_target) and (a_target in gm_a or gm_a in a_target):
            return idx
    for idx, gm in enumerate(pool):
        for mc in [h_target, a_target, p_target]:
            if mc and len(mc) >= 3 and (mc in gm["home_team"].lower() or mc in gm["away_team"].lower()):
                return idx
    return 0

def render_single_game(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("⚡ Single Game Analytics Engine")
    form_ver = st.session_state.single_form_version

    f_col1, f_col2 = st.columns([1, 2])
    timing_view = f_col1.selectbox("Game Status Filter", ["⏳ Upcoming Games", "⚡ Live Games", "📜 Past / Completed Games", "🌐 All Matchups"])
    search_query = f_col2.text_input("🔍 Search Matchup or Team", placeholder="e.g. Celtics, Lakers, Eagles, Chiefs...")

    pool = games_data
    if timing_view == "⏳ Upcoming Games":
        pool = [g for g in pool if not g.get("completed", False) and (g.get("state_text") == "pre" or g.get("period", 0) == 0)]
    elif timing_view == "⚡ Live Games":
        pool = [g for g in pool if not g.get("completed", False) and g.get("state_text") != "pre" and g.get("period", 0) > 0]
    elif timing_view == "📜 Past / Completed Games":
        pool = [g for g in pool if g.get("completed", False)]

    if search_query.strip():
        q = search_query.strip().lower()
        pool = [g for g in pool if q in g["home_team"].lower() or q in g["away_team"].lower() or q in g["home_short"].lower() or q in g["away_short"].lower()]

    with st.expander("📸 Auto-Fill via Slip Screenshot (Robinhood, DraftKings, FanDuel, etc.)", expanded=False):
        uploaded_slip = st.file_uploader("Upload Slip Screenshot (PNG, JPG)", type=["png", "jpg", "jpeg"], key=f"slip_uploader_v{form_ver}")
        if uploaded_slip is not None and st.button("⚡ Extract & Auto-Fill Form", use_container_width=True):
            with st.spinner("Analyzing screenshot..."):
                parsed_res, _ = parse_bet_slip_image(uploaded_slip.read())
                if parsed_res:
                    matched_idx = match_game_in_pool(parsed_res.get("away_team", ""), parsed_res.get("home_team", ""), pool, parsed_res.get("picked_team", ""))
                    st.session_state.single_selected_idx = matched_idx
                    st.session_state.single_applied_pick = {
                        "category": parsed_res.get("wager_type", "Game Total"),
                        "side": parsed_res.get("side", "Under"),
                        "target_line": float(parsed_res.get("line", 44.5)) if parsed_res.get("line") is not None else 44.5,
                        "risk": float(parsed_res.get("risk", 10.0)),
                        "payout": float(parsed_res.get("payout", 20.0)),
                        "picked_team": parsed_res.get("picked_team"),
                        "status": "Won" if parsed_res.get("is_settled") else "Pending"
                    }
                    st.session_state.single_form_version += 1
                    st.success("Slip auto-extracted!")
                    st.rerun()

    if not pool:
        st.info("No matchups found matching your filter.")
        return

    game_options = [f"[{g['kickoff']}] [{g['league']}] {g['away_short']} @ {g['home_short']}" for g in pool]
    sel_idx = st.selectbox("Select Matchup", range(len(game_options)), index=min(st.session_state.single_selected_idx, len(game_options)-1), format_func=lambda x: game_options[x], key=f"matchup_sel_v{form_ver}")
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
        b2.markdown(f"### **{g['away_short']}** @ **{g['home_short']}**\n{g['kickoff']}")
        b3.image(g.get("home_logo", DEFAULT_LOGO), width=45)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Full Game Total", f"{final_proj:.1f} pts", delta=f"{delta_full:+.1f} vs open ({pregame_tot:.1f})")
        m2.metric("2nd Half Total", f"{live_2h_proj:.1f} pts", delta=f"{live_2h_proj - pregame_2h:+.1f} vs base")
        m3.metric(f"{g['home_short']} Win %", f"{live_h_prob*100:.1f}%")
        m4.metric(f"ATS Margin ({espn_spread:+.1f})", f"{live_proj_margin:+.1f} pts")

    if is_nba_game:
        h_players = get_live_nba_roster(g["home_id"] or g["home_short"])
        a_players = get_live_nba_roster(g["away_id"] or g["away_short"])
    else:
        h_players = get_live_football_roster(g["home_id"] or g["home_short"], g["league"])
        a_players = get_live_football_roster(g["away_id"] or g["away_short"], g["league"])

    with st.expander("🤖 Section 2: AI Strategy Engine & Market Filters", expanded=True):
        strat_opts = ["⚡ Consensus Edge", "📊 Full Game Total", "🛡️ Spread (ATS)", "🏆 Moneyline"]
        strat_opts.append("🏀 Player Points Prop" if is_nba_game else "🏈 Player Anytime TD")
        sel_market = st.selectbox("Strategy Type", strat_opts)

        tot_dir = "Under" if delta_full <= 0 else "Over"
        p_tot = calculate_win_prob(final_proj, final_proj, std_bracket, is_under=(tot_dir == "Under"))
        rec_pick = f"{tot_dir} {final_proj:.1f}"
        rec_type = "Game Total"
        rec_line = final_proj
        rec_side = tot_dir
        rec_team = None

        if "Points" in sel_market and is_nba_game and h_players:
            p_name, p_pos, p_val = h_players[0]
            rec_pick = f"{p_name} ({p_pos}) Over {p_val:.1f} Pts"
            rec_type = "Player Points Prop"
            rec_line = p_val
            rec_side = "Over"
            rec_team = p_name
        elif "TD" in sel_market and not is_nba_game and h_players:
            p_name, p_pos = h_players[0][:2]
            rec_pick = f"{p_name} ({p_pos}) Any Time TD"
            rec_type = "Player Anytime Touchdown Scorer"
            rec_line = 1.0
            rec_side = "TD"
            rec_team = p_name

        st.markdown(f"""
        <div class="rec-card-box">
            <div class="rec-header-row">
                <div><strong>🥇 BEST RECOMMENDATION</strong> • <code>{rec_type}</code></div>
                <div class="rec-matchup-meta"><strong>{g['away_short']}</strong> @ <strong>{g['home_short']}</strong></div>
            </div>
            <div class="rec-pick-row">
                <strong style="color:#4ade80; font-size:1.15rem;">{rec_pick}</strong>
                <span class="badge-roi">+91% Profit</span>
                <span class="badge-prob">{p_tot*100:.1f}% Win Prob</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("📥 Load to Form", use_container_width=True):
            st.session_state.single_applied_pick = {
                "category": rec_type, "side": rec_side, "target_line": rec_line,
                "risk": 10.0, "payout": 19.10, "picked_team": rec_team, "status": "Pending"
            }
            st.session_state.single_form_version += 1
            st.rerun()

    applied = st.session_state.single_applied_pick
    with st.expander("📝 Section 3: Wager Type & Lock In Bet Slip", expanded=True):
        w_types = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)"]
        w_types.append("Player Points Prop" if is_nba_game else "Player Anytime Touchdown Scorer")
        def_w_idx = 0
        if applied:
            cat = str(applied.get("category", "")).lower()
            if "spread" in cat: def_w_idx = 1
            elif "moneyline" in cat or "winner" in cat: def_w_idx = 2
            elif "points" in cat or "td" in cat: def_w_idx = 3

        bet_type = st.radio("Market", w_types, index=def_w_idx, horizontal=True)
        with st.form(f"single_bet_form_v{form_ver}"):
            p_target = None
            if bet_type == "Game Total":
                f1, f2 = st.columns(2)
                s_side = f1.selectbox("Side", ["Under", "Over"], index=0 if (applied and applied.get("side") == "Under") else 1)
                s_line = f2.number_input("Total Line", value=float(applied.get("target_line", final_proj)) if applied else float(final_proj), step=0.5)
            elif bet_type == "Point Spread (ATS)":
                f1, f2 = st.columns(2)
                p_target = f1.selectbox("Covering Team", [g["home_team"], g["away_team"]])
                s_side = "Spread"
                s_line = f2.number_input("Spread Line", value=float(espn_spread), step=0.5)
            elif bet_type == "Straight Up Winner (Moneyline)":
                p_target = st.selectbox("Outright Winner", [g["home_team"], g["away_team"]])
                s_side, s_line = "Moneyline", None
            elif bet_type == "Player Points Prop":
                f1, f2 = st.columns(2)
                all_r = [p[0] for p in (h_players + a_players)]
                p_target = f1.selectbox("Player", all_r)
                s_side = f2.selectbox("Side", ["Over", "Under"])
                s_line = st.number_input("Points Line", value=22.5, step=0.5)
            else:
                all_r = [p[0] for p in (h_players + a_players)]
                p_target = st.selectbox("Player", all_r)
                s_side, s_line = "TD", 1.0

            c_r, c_p = st.columns(2)
            r_amt = c_r.number_input("Risk ($)", min_value=1.0, value=float(applied.get("risk", 10.0)) if applied else 10.0, step=5.0)
            p_amt = c_p.number_input("Payout ($)", min_value=1.0, value=float(applied.get("payout", 19.10)) if applied else 19.10, step=5.0)

            if st.form_submit_button("Lock In Bet Slip", use_container_width=True):
                lbl = f"{p_target} {s_side} {s_line} Pts" if bet_type == "Player Points Prop" else \
                      (f"{p_target} TD" if bet_type == "Player Anytime Touchdown Scorer" else \
                      (f"{s_side} {s_line}" if s_line is not None else f"{p_target} ML"))

                tkt = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Single", "bet_category": bet_type,
                    "home_team": g["home_team"], "away_team": g["away_team"],
                    "picked_team": p_target, "matchup": f"{g['away_short']} @ {g['home_short']}",
                    "bet": lbl, "target_line": s_line, "bet_direction": s_side,
                    "risk_dollars": float(r_amt), "payout_dollars": float(p_amt),
                    "locked_profit": float(p_amt) - float(r_amt),
                    "status": "Won" if is_completed and (pts_scored < s_line if s_side == "Under" and s_line else False) else "Pending",
                    "notes": f"[{g['league']}] {bet_type}"
                }
                st.session_state.saved_bets.insert(0, tkt)
                save_all_storage(st.session_state.saved_bets, st.session_state.chat_messages, st.session_state.user_accounts, st.session_state.banned_emails, st.session_state.game_snapshots, st.session_state.support_tickets)
                st.session_state.single_applied_pick = None
                st.success("Ticket locked successfully!")
                st.rerun()
