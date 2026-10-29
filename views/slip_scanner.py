import streamlit as st
import io
import base64
import re
import json
import requests
from PIL import Image
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage
from models import calculate_win_prob, calculate_spread_prob, calculate_moneyline_prob

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
        "league": "NFL" | "NBA" | "NCAA" | "OTHER",
        "away_team": "string or null",
        "home_team": "string or null",
        "picked_team": "string or null",
        "wager_type": "Point Spread" | "Game Total" | "Moneyline" | "Player Points Prop" | "Anytime TD" | "Combo",
        "side": "Under" | "Over" | "Spread" | "Moneyline",
        "line": float or null,
        "payout": float,
        "profit": float or null,
        "risk": float or null,
        "is_settled": boolean,
        "legs_count": int or null
    }
    Rules:
    1. Accurately identify the sport league: If teams are football (e.g. Chiefs, Eagles, Ravens, Cowboys, Alabama, Ohio State, etc.) mark "league": "NFL" or "NCAA". If basketball (e.g. Celtics, Lakers, Warriors, Pacers, etc.) mark "league": "NBA".
    2. If contract says "Over X points Payout" and user chose "No", side is "Under", line is X, wager_type is "Game Total".
    3. If user chose "Yes", side is "Over", line is X, wager_type is "Game Total".
    4. If profit is present but risk is missing: risk = payout - profit.
    5. If risk and payout are present: profit = payout - risk.
    6. Return ONLY raw JSON without markdown markers or backticks.
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
                    active_models.append(m_name.replace("models/", ""))
    except Exception:
        pass

    if not active_models:
        active_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-exp"]

    last_err = ""
    for model_name in active_models:
        clean_model = model_name.replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={gemini_key}"
        try:
            r = requests.post(url, json=payload, timeout=25.0)
            if r.status_code == 200:
                candidates = r.json().get("candidates", [])
                if not candidates:
                    continue
                txt = candidates[0]["content"]["parts"][0]["text"]
                cleaned = re.sub(r"^```json\s*", "", txt.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"^```\s*", "", cleaned.strip())
                cleaned = re.sub(r"```$", "", cleaned.strip())
                return json.loads(cleaned), None
            else:
                last_err = f"{clean_model} (HTTP {r.status_code}): {r.text[:120]}"
        except Exception as e:
            last_err = str(e)
            continue

    return None, f"Parsing failed: {last_err}"

def match_game_robustly(data, games_data):
    """Finds matching game by prioritizing league and testing team abbreviations, cities, and nicknames."""
    if not games_data:
        return None

    target_league = (data.get("league") or "").upper().strip()
    a_target = (data.get("away_team") or "").lower().strip()
    h_target = (data.get("home_team") or "").lower().strip()
    p_target = (data.get("picked_team") or "").lower().strip()

    # Pass 1: Filter by identified league first
    league_pool = [g for g in games_data if target_league in g.get("league", "").upper()] if target_league in ["NFL", "NBA", "NCAA"] else games_data
    if not league_pool:
        league_pool = games_data

    def check_match(gm, t_str):
        if not t_str or len(t_str) < 2:
            return False
        gm_h = gm.get("home_team", "").lower()
        gm_a = gm.get("away_team", "").lower()
        gm_hs = gm.get("home_short", "").lower()
        gm_as = gm.get("away_short", "").lower()
        return (t_str in gm_h or gm_h in t_str or t_str == gm_hs or
                t_str in gm_a or gm_a in t_str or t_str == gm_as)

    # 1. Look for both away and home matching in the league pool
    for gm in league_pool:
        if a_target and h_target:
            if check_match(gm, a_target) and check_match(gm, h_target):
                return gm

    # 2. Look for single strong match on away, home, or picked team in league pool
    for gm in league_pool:
        for t in [a_target, h_target, p_target]:
            if t and len(t) >= 3 and check_match(gm, t):
                return gm

    # 3. Fallback across all games if league filter was too strict
    if league_pool != games_data:
        for gm in games_data:
            if (a_target and check_match(gm, a_target)) or (h_target and check_match(gm, h_target)):
                return gm

    return None

def determine_scanned_bet_outcome(data, matched_game):
    w_type = data.get("wager_type", "Game Total")
    side = data.get("side", "Under")
    line = float(data.get("line") or 0.0)
    picked_t = data.get("picked_team", "")

    if not matched_game:
        is_settled_flag = data.get("is_settled", False)
        return ("Won" if is_settled_flag else "Pending"), 0.55, "Scheduled"

    chk = matched_game.get("checkpoint", "").lower()
    stt = str(matched_game.get("status", "")).lower()
    is_completed = matched_game.get("completed", False) or "final" in stt
    is_live = ("pre" not in chk) and ("pm" not in stt and "am" not in stt) and not is_completed

    h_sc = matched_game.get("home_score", 0)
    a_sc = matched_game.get("away_score", 0)
    tot_sc = h_sc + a_sc
    h_team = matched_game.get("home_team", "")

    if is_completed:
        won = None
        if "Total" in w_type and line > 0:
            won = (tot_sc < line) if side == "Under" else (tot_sc > line)
        elif "Spread" in w_type and line != 0:
            diff = (h_sc - a_sc) if (picked_t == h_team or h_team in picked_t) else (a_sc - h_sc)
            won = (diff + line) > 0
        elif "Moneyline" in w_type or "Winner" in w_type:
            won = (h_sc > a_sc) if (picked_t == h_team or h_team in picked_t) else (a_sc > h_sc)
        else:
            won = data.get("is_settled", True)

        if won is True:
            return "Won", 1.0, "Final"
        else:
            return "Lost", 0.0, "Final"

    elif is_live:
        is_nba = (matched_game.get("league") == "NBA")
        if "Total" in w_type and line > 0:
            proj = float(matched_game.get("market_ou", 224.5 if is_nba else 47.5))
            prob = calculate_win_prob(line, proj, (12.0 if is_nba else 7.0), is_under=(side == "Under"))
        elif "Spread" in w_type and line != 0:
            prob = calculate_spread_prob(0.0, line, (7.5 if is_nba else 5.0))
        elif "Moneyline" in w_type or "Winner" in w_type:
            add = 40 if is_nba else 14
            h_p = calculate_moneyline_prob(h_sc + add, a_sc + add, matched_game.get("home_record", "0-0"), matched_game.get("away_record", "0-0"))
            prob = h_p if (picked_t == h_team or h_team in picked_t) else (1.0 - h_p)
        else:
            prob = 0.55
        return "In-Play", max(0.01, min(0.99, prob)), matched_game.get("displayClock") or "Live"

    else:
        # Pre-game / Scheduled
        if "Total" in w_type and line > 0:
            ou_line = float(matched_game.get("market_ou", line))
            prob = calculate_win_prob(line, ou_line, 10.0, is_under=(side == "Under"))
        elif "Moneyline" in w_type or "Winner" in w_type:
            h_p = calculate_moneyline_prob(100, 100, matched_game.get("home_record", "0-0"), matched_game.get("away_record", "0-0"))
            prob = h_p if (picked_t == h_team or h_team in picked_t) else (1.0 - h_p)
        else:
            prob = 0.54
        return "Pending", max(0.05, min(0.95, prob)), matched_game.get("kickoff") or "Scheduled"

def render_slip_scanner(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("📸 Scan & Log Bet Slip")
    st.caption("Upload a screenshot from Robinhood, DraftKings, FanDuel, Caesars, or BetMGM to auto-extract details, identify league/teams, and lock the ticket.")

    if "scanner_data" not in st.session_state:
        st.session_state.scanner_data = None

    with st.container(border=True):
        uploaded_file = st.file_uploader("Upload Bet Slip Image (PNG, JPG, WEBP)", type=["png", "jpg", "jpeg", "webp"], key="scanner_upload")

        if uploaded_file is not None:
            c_btn1, _ = st.columns([2, 3])
            if c_btn1.button("⚡ Scan Screenshot", type="primary", use_container_width=True):
                with st.spinner("Analyzing slip and identifying league & teams..."):
                    parsed, err = parse_bet_slip_image(uploaded_file.read())
                    if parsed:
                        st.session_state.scanner_data = parsed
                        st.toast("✅ Extracted ticket data successfully!", icon="📸")
                    else:
                        st.error(f"❌ Could not scan slip: {err}")

    # SCANNED TICKET SECTION
    if st.session_state.scanner_data:
        data = st.session_state.scanner_data

        matched_game = match_game_robustly(data, games_data)
        status_result, prob_calc, timing_desc = determine_scanned_bet_outcome(data, matched_game)

        # Identify League Label & Icon
        active_league = matched_game.get("league") if matched_game else (data.get("league") or "SPORTS")
        league_icon = "🏀" if "NBA" in active_league else ("🏈" if ("NFL" in active_league or "NCAA" in active_league) else "⚡")

        # Build Status Badge
        if status_result == "Won":
            status_badge_html = "<span style='background-color:#22c55e;color:#000;font-weight:800;padding:3px 10px;border-radius:12px;font-size:0.80rem;'>🏆 WON</span>"
        elif status_result == "Lost":
            status_badge_html = "<span style='background-color:#ef4444;color:#fff;font-weight:800;padding:3px 10px;border-radius:12px;font-size:0.80rem;'>❌ LOST</span>"
        elif status_result == "In-Play":
            status_badge_html = "<span style='background-color:#eab308;color:#000;font-weight:800;padding:3px 10px;border-radius:12px;font-size:0.80rem;'>⚡ IN PLAY</span>"
        else:
            status_badge_html = "<span style='background-color:rgba(255,255,255,0.12);color:#94a3b8;font-weight:700;padding:3px 10px;border-radius:12px;font-size:0.80rem;'>⏳ PENDING</span>"

        # Win Prob Badge (100% on Won, 0% on Lost)
        prob_str = f"{prob_calc * 100:.1f}%"
        prob_badge_html = f"<span style='background-color:rgba(56,189,248,0.15);color:#38bdf8;font-weight:700;padding:3px 10px;border-radius:6px;font-size:0.80rem;'>🎲 Win: {prob_str}</span>"
        league_badge_html = f"<span style='background-color:rgba(255,255,255,0.08);color:#f1f5f9;font-weight:700;padding:3px 10px;border-radius:6px;font-size:0.80rem;'>{league_icon} {active_league}</span>"

        w_type_raw = data.get("wager_type", "Game Total")
        side_raw = data.get("side", "Under")
        line_raw = float(data.get("line") or 0.0)
        p_team_raw = data.get("picked_team", "")

        if line_raw > 0:
            pick_desc = f"{side_raw} {line_raw:.1f} pts" if w_type_raw == "Game Total" else f"{p_team_raw} {side_raw} {line_raw}"
        else:
            pick_desc = f"{p_team_raw} ML" if "Moneyline" in w_type_raw else f"{p_team_raw} {side_raw}"

        st.markdown("#### 🎟️ Scanned Ticket")
        with st.container(border=True):
            if matched_game:
                a_sh = matched_game.get("away_short", data.get("away_team", "AWAY"))
                h_sh = matched_game.get("home_short", data.get("home_team", "HOME"))
                a_sc = matched_game.get("away_score", 0)
                h_sc = matched_game.get("home_score", 0)
                a_logo = matched_game.get("away_logo") or DEFAULT_LOGO
                h_logo = matched_game.get("home_logo") or DEFAULT_LOGO
                is_fin = (status_result in ["Won", "Lost"])

                if is_fin:
                    score_info = f"<span style='background:rgba(255,255,255,0.08);padding:3px 8px;border-radius:6px;font-weight:800;font-size:0.95rem;color:#f8fafc;'>{a_sc} - {h_sc} (Final)</span>"
                elif status_result == "In-Play":
                    score_info = f"<span style='background:rgba(234,179,8,0.15);color:#facc15;padding:3px 8px;border-radius:6px;font-weight:800;font-size:0.95rem;'>{a_sc} - {h_sc} ({timing_desc})</span>"
                else:
                    score_info = f"<span style='opacity:0.65;font-size:0.80rem;'>🗓️ {matched_game.get('kickoff', 'Scheduled')}</span>"

                header_html = f"""
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                        <img src="{a_logo}" width="28" height="28" style="border-radius:50%; object-fit:contain; background:#1e293b;">
                        <strong>{a_sh}</strong>
                        <span style="opacity:0.4;">@</span>
                        <img src="{h_logo}" width="28" height="28" style="border-radius:50%; object-fit:contain; background:#1e293b;">
                        <strong>{h_sh}</strong>
                        {score_info}
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        {league_badge_html}
                        {prob_badge_html}
                        {status_badge_html}
                    </div>
                </div>
                """
            else:
                away_lbl = data.get("away_team") or "Away Team"
                home_lbl = data.get("home_team") or "Home Team"
                header_html = f"""
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <img src="{DEFAULT_LOGO}" width="24" height="24">
                        <strong>{away_lbl}</strong>
                        <span style="opacity:0.4;">@</span>
                        <img src="{DEFAULT_LOGO}" width="24" height="24">
                        <strong>{home_lbl}</strong>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        {league_badge_html}
                        {prob_badge_html}
                        {status_badge_html}
                    </div>
                </div>
                """

            st.markdown(header_html, unsafe_allow_html=True)

            # Details Row: Scanned Pick, Risk/Payout, Market
            r_scanned = float(data.get("risk") or 10.0)
            p_scanned = float(data.get("payout") or 19.10)
            profit_scanned = p_scanned - r_scanned

            c_p1, c_p2, c_p3 = st.columns([3.5, 3.5, 3.0])
            with c_p1:
                st.markdown(f"""
                <div style="line-height:1.35;">
                    <span style="font-size:0.75rem; opacity:0.65; text-transform:uppercase;">Scanned Pick</span>
                    <div style="font-weight:700; color:#4ade80; font-size:1.0rem; margin-top:2px;">{pick_desc}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_p2:
                st.markdown(f"""
                <div style="line-height:1.35;">
                    <span style="font-size:0.75rem; opacity:0.65; text-transform:uppercase;">Risk ➔ Payout</span>
                    <div style="font-size:0.92rem; font-weight:600; margin-top:2px;">${r_scanned:.2f} ➔ <strong>${p_scanned:.2f}</strong></div>
                    <div style="color:#4ade80; font-weight:700; font-size:0.80rem;">+${profit_scanned:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_p3:
                st.markdown(f"""
                <div style="line-height:1.35;">
                    <span style="font-size:0.75rem; opacity:0.65; text-transform:uppercase;">Market & Sport</span>
                    <div style="font-size:0.88rem; font-weight:600; margin-top:2px;">{w_type_raw}</div>
                    <div style="font-size:0.78rem; opacity:0.65;">{active_league} • {status_result}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            st.progress(prob_calc, text=f"Calculated Win Expectancy: {prob_calc * 100:.1f}%")

        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

        # EDITABLE VERIFICATION & LOCK-IN FORM
        st.markdown("#### 📝 Verify Details & Lock Ticket")

        with st.form("confirm_scanned_slip_form"):
            c_lg, c_wt = st.columns(2)
            league_options = ["NFL", "NBA", "NCAA Football", "Other"]
            def_lg_idx = 0
            if "NBA" in active_league:
                def_lg_idx = 1
            elif "NCAA" in active_league:
                def_lg_idx = 2
            confirmed_league = c_lg.selectbox("League / Sport", league_options, index=def_lg_idx)

            w_types = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Player Points Prop", "Anytime TD", "Multi-Leg Parlay"]
            raw_wtype = data.get("wager_type") or "Game Total"
            w_idx = 0
            for idx, wt in enumerate(w_types):
                if wt.lower() in raw_wtype.lower():
                    w_idx = idx
                    break
            w_type = c_wt.selectbox("Wager Type", w_types, index=w_idx)

            c1, c2 = st.columns(2)
            away_team = c1.text_input("Away Team", value=matched_game.get("away_team") if matched_game else (data.get("away_team") or ""))
            home_team = c2.text_input("Home Team", value=matched_game.get("home_team") if matched_game else (data.get("home_team") or ""))

            c3, c4 = st.columns(2)
            picked_team = c3.text_input("Picked Selection / Player", value=data.get("picked_team") or (home_team if "Moneyline" in w_type else ""))
            side_opts = ["Under", "Over", "Spread", "Moneyline", "TD"]
            raw_side = data.get("side") or "Under"
            s_idx = side_opts.index(raw_side) if raw_side in side_opts else (0 if raw_side == "Under" else 1)
            side = c4.selectbox("Side / Direction", side_opts, index=s_idx)

            c5, c6 = st.columns(2)
            line = c5.number_input("Line (pts / strike)", value=float(data.get("line") or 0.0), step=0.5)
            risk = c6.number_input("Risk ($)", min_value=1.0, value=r_scanned, step=5.0)

            c7, _ = st.columns(2)
            payout = c7.number_input("Payout ($)", min_value=1.0, value=p_scanned, step=5.0)

            profit = payout - risk
            final_status = "Won" if status_result == "Won" else ("Lost" if status_result == "Lost" else "Pending")

            matchup_str = f"{away_team} @ {home_team}" if (away_team and home_team) else (picked_team or "Custom Wager")
            if line > 0:
                pick_label = f"{side} {line}" if w_type == "Game Total" else f"{picked_team} {side} {line}"
            else:
                pick_label = f"{picked_team} {side}"

            if st.form_submit_button("🔒 Lock In Bet Slip", type="primary", use_container_width=True):
                tkt = {
                    "id": str(datetime.now().timestamp()),
                    "user": curr_user.get("display_name", active_uname),
                    "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
                    "type": "Single" if "Parlay" not in w_type else "Combo",
                    "bet_category": w_type,
                    "home_team": home_team,
                    "away_team": away_team,
                    "picked_team": picked_team,
                    "matchup": matchup_str,
                    "bet": pick_label,
                    "target_line": line if line > 0 else None,
                    "bet_direction": side,
                    "risk_dollars": float(risk),
                    "payout_dollars": float(payout),
                    "payout": float(payout),
                    "locked_profit": float(profit),
                    "win_prob": f"{prob_calc * 100:.1f}%",
                    "status": final_status,
                    "notes": f"[{confirmed_league}] {w_type}"
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
                st.session_state.scanner_data = None
                st.toast(f"🎉 Locked in {pick_label}!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()
