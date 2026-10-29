import streamlit as st
import io
import base64
import re
import json
import requests
from PIL import Image
from datetime import datetime
from config import DEFAULT_LOGO
from database import save_all_storage, find_game_for_bet
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

def compute_scanned_analytics(data, matched_game):
    w_type = data.get("wager_type", "Game Total")
    side = data.get("side", "Under")
    line = float(data.get("line") or 0.0)

    if not matched_game:
        return 0.55, "+120", 1.82

    is_nba = (matched_game.get("league") == "NBA")
    is_completed = matched_game.get("completed", False) or "final" in str(matched_game.get("status", "")).lower()

    if is_completed:
        tot = matched_game.get("home_score", 0) + matched_game.get("away_score", 0)
        h_sc = matched_game.get("home_score", 0)
        a_sc = matched_game.get("away_score", 0)
        if "Total" in w_type and line > 0:
            won = (tot < line) if side == "Under" else (tot > line)
        elif "Spread" in w_type and line != 0:
            diff = (h_sc - a_sc) if data.get("picked_team") == matched_game.get("home_team") else (a_sc - h_sc)
            won = (diff + line) > 0
        elif "Moneyline" in w_type or "Winner" in w_type:
            won = (h_sc > a_sc) if data.get("picked_team") == matched_game.get("home_team") else (a_sc > h_sc)
        else:
            won = True
        prob = 1.0 if won else 0.0
    else:
        if "Total" in w_type and line > 0:
            proj = float(matched_game.get("market_ou", 224.5 if is_nba else 47.5))
            prob = calculate_win_prob(line, proj, (12.0 if is_nba else 7.0), is_under=(side == "Under"))
        elif "Spread" in w_type and line != 0:
            prob = calculate_spread_prob(0.0, line, (7.5 if is_nba else 5.0))
        elif "Moneyline" in w_type or "Winner" in w_type:
            add = 40 if is_nba else 14
            h_p = calculate_moneyline_prob(
                matched_game["home_score"] + add,
                matched_game["away_score"] + add,
                matched_game.get("home_record", "0-0"),
                matched_game.get("away_record", "0-0")
            )
            prob = h_p if data.get("picked_team") == matched_game.get("home_team") else (1.0 - h_p)
        else:
            prob = 0.58

    prob = max(0.01, min(0.99, prob))
    fair_mult = 1.0 / prob
    fair_odds = f"+{int((fair_mult - 1.0) * 100)}" if fair_mult >= 2.0 else f"-{int(100 / max(0.01, fair_mult - 1.0))}"
    return prob, fair_odds, fair_mult

def render_slip_scanner(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("📸 Scan & Log Bet Slip")
    st.caption("Upload a screenshot from Robinhood, DraftKings, FanDuel, Caesars, or BetMGM to auto-extract details and lock the ticket into your history.")

    if "scanner_data" not in st.session_state:
        st.session_state.scanner_data = None

    with st.container(border=True):
        uploaded_file = st.file_uploader("Upload Bet Slip Image (PNG, JPG, WEBP)", type=["png", "jpg", "jpeg", "webp"], key="scanner_upload")

        if uploaded_file is not None:
            c_btn1, _ = st.columns([2, 3])
            if c_btn1.button("⚡ Scan Screenshot", type="primary", use_container_width=True):
                with st.spinner("Analyzing bet slip with vision model..."):
                    parsed, err = parse_bet_slip_image(uploaded_file.read())
                    if parsed:
                        st.session_state.scanner_data = parsed
                        st.toast("✅ Extracted ticket data successfully!", icon="📸")
                    else:
                        st.error(f"❌ Could not scan slip: {err}")

    # Section Displayed Directly After Scanning
    if st.session_state.scanner_data:
        data = st.session_state.scanner_data

        # Attempt to match against active live or recent scoreboards
        temp_bet = {
            "matchup": f"{data.get('away_team', '')} @ {data.get('home_team', '')}",
            "home_team": data.get("home_team", ""),
            "away_team": data.get("away_team", "")
        }
        matched_game = find_game_for_bet(temp_bet, games_data)
        prob_val, fair_odds_str, fair_mult_val = compute_scanned_analytics(data, matched_game)

        # Matchup Showcase Card with Official Logos, Telemetry, and Scores
        st.markdown("#### 🏟️ Matched Matchup & Live Telemetry")
        with st.container(border=True):
            if matched_game:
                a_sh = matched_game.get("away_short", data.get("away_team", "AWAY"))
                h_sh = matched_game.get("home_short", data.get("home_team", "HOME"))
                a_sc = matched_game.get("away_score", 0)
                h_sc = matched_game.get("home_score", 0)
                a_logo = matched_game.get("away_logo", DEFAULT_LOGO)
                h_logo = matched_game.get("home_logo", DEFAULT_LOGO)
                is_fin = matched_game.get("completed", False) or "final" in str(matched_game.get("status", "")).lower()
                status_label = "🏆 FINAL" if is_fin else (matched_game.get("displayClock") or matched_game.get("status", "Scheduled"))

                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <img src="{a_logo}" width="30" height="30" style="border-radius:50%; object-fit:contain;">
                        <span style="font-size:1.15rem; font-weight:800;">{a_sh}</span>
                        <span style="font-size:1.25rem; font-weight:800; color:#38bdf8;">{a_sc}</span>
                        <span style="opacity:0.4; font-weight:700;">@</span>
                        <span style="font-size:1.25rem; font-weight:800; color:#38bdf8;">{h_sc}</span>
                        <span style="font-size:1.15rem; font-weight:800;">{h_sh}</span>
                        <img src="{h_logo}" width="30" height="30" style="border-radius:50%; object-fit:contain;">
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="background:rgba(255,255,255,0.08); color:#f8fafc; font-weight:700; font-size:0.80rem; padding:4px 10px; border-radius:6px;">
                            {status_label}
                        </span>
                        <span style="background:rgba(56,189,248,0.12); color:#38bdf8; font-weight:700; font-size:0.80rem; padding:4px 10px; border-radius:6px;">
                            [{matched_game.get('league', 'SPORTS')}]
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px; margin-bottom:12px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <img src="{DEFAULT_LOGO}" width="26" height="26">
                        <strong>{data.get('away_team') or 'Away Team'}</strong>
                        <span style="opacity:0.4;">@</span>
                        <strong>{data.get('home_team') or 'Home Team'}</strong>
                    </div>
                    <span style="background:rgba(255,255,255,0.06); padding:3px 8px; border-radius:4px; font-size:0.78rem;">Scanned Contract</span>
                </div>
                """, unsafe_allow_html=True)

            # Analytics & Probability Grid
            a1, a2, a3 = st.columns(3)
            a1.metric("Model Win Probability", f"{prob_val * 100:.1f}%", help="Calculated expectancy based on Poisson scoring models and historical pace.")
            a2.metric("Fair Zero-Vig Odds", fair_odds_str, delta=f"{fair_mult_val:.2f}x Fair Multiplier", delta_color="off")
            a3.metric("Scanned Wager Type", data.get("wager_type", "Single"), delta=f"Side: {data.get('side', 'N/A')}", delta_color="off")

            st.progress(prob_val, text=f"Calculated Win Expectancy: {prob_val * 100:.1f}%")

        st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

        # Editable Verification & Lock-In Form
        st.markdown("#### 📝 Verify Details & Lock Ticket")

        with st.form("confirm_scanned_slip_form"):
            c1, c2 = st.columns(2)
            away_team = c1.text_input("Away Team", value=data.get("away_team") or "")
            home_team = c2.text_input("Home Team", value=data.get("home_team") or "")

            c3, c4 = st.columns(2)
            w_types = ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Player Points Prop", "Anytime TD", "Multi-Leg Parlay"]
            raw_wtype = data.get("wager_type") or "Game Total"
            w_idx = 0
            for idx, wt in enumerate(w_types):
                if wt.lower() in raw_wtype.lower():
                    w_idx = idx
                    break

            w_type = c3.selectbox("Wager Type", w_types, index=w_idx)
            picked_team = c4.text_input("Picked Selection / Player", value=data.get("picked_team") or "")

            c5, c6 = st.columns(2)
            side_opts = ["Under", "Over", "Spread", "Moneyline", "TD"]
            raw_side = data.get("side") or "Under"
            s_idx = side_opts.index(raw_side) if raw_side in side_opts else (0 if raw_side == "Under" else 1)
            side = c5.selectbox("Side / Direction", side_opts, index=s_idx)
            line = c6.number_input("Line (pts / strike)", value=float(data.get("line") or 0.0), step=0.5)

            c7, c8 = st.columns(2)
            risk = c7.number_input("Risk ($)", min_value=1.0, value=float(data.get("risk") or 10.0), step=5.0)
            payout = c8.number_input("Payout ($)", min_value=1.0, value=float(data.get("payout") or 19.10), step=5.0)

            profit = payout - risk
            status = "Won" if data.get("is_settled") else ("Won" if (matched_game and matched_game.get("completed") and prob_val == 1.0) else "Pending")

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
                    "win_prob": f"{prob_val * 100:.1f}%",
                    "status": status,
                    "notes": f"Scanned ticket [{w_type}]"
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
