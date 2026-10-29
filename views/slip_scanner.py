import streamlit as st
import io
import base64
import re
import json
import requests
from PIL import Image
from datetime import datetime
from database import save_all_storage

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

    active_models = [
        "models/gemini-2.0-flash",
        "models/gemini-2.5-flash",
        "models/gemini-1.5-flash"
    ]

    last_err = ""
    for full_model_path in active_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/{full_model_path}:generateContent?key={gemini_key}"
        try:
            r = requests.post(url, json=payload, timeout=25.0)
            if r.status_code == 200:
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = re.sub(r"^```json\s*", "", txt.strip())
                cleaned = re.sub(r"```$", "", cleaned.strip())
                return json.loads(cleaned), None
            else:
                last_err = f"{full_model_path} (HTTP {r.status_code}): {r.text[:120]}"
        except Exception as e:
            last_err = str(e)
            continue

    return None, f"Parsing failed: {last_err}"

def render_slip_scanner(curr_user, active_uname, get_current_et_time_fn):
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
                        st.success("✅ Extracted ticket data successfully!")
                    else:
                        st.error(f"❌ Could not scan slip: {err}")

    # Editable Verification & Lock-In Form
    if st.session_state.scanner_data:
        data = st.session_state.scanner_data
        st.markdown("#### 📝 Verify Details & Lock Ticket")

        with st.form("confirm_scanned_slip_form"):
            c1, c2 = st.columns(2)
            away_team = c1.text_input("Away Team", value=data.get("away_team") or "")
            home_team = c2.text_input("Home Team", value=data.get("home_team") or "")

            c3, c4 = st.columns(2)
            w_type = c3.selectbox("Wager Type", ["Game Total", "Point Spread (ATS)", "Straight Up Winner (Moneyline)", "Player Points Prop", "Anytime TD", "Multi-Leg Parlay"], index=0)
            picked_team = c4.text_input("Picked Selection / Player", value=data.get("picked_team") or "")

            c5, c6 = st.columns(2)
            side = c5.selectbox("Side / Direction", ["Under", "Over", "Spread", "Moneyline", "TD"], index=0 if data.get("side") == "Under" else 1)
            line = c6.number_input("Line (pts / strike)", value=float(data.get("line") or 0.0), step=0.5)

            c7, c8 = st.columns(2)
            risk = c7.number_input("Risk ($)", min_value=1.0, value=float(data.get("risk") or 10.0), step=5.0)
            payout = c8.number_input("Payout ($)", min_value=1.0, value=float(data.get("payout") or 19.10), step=5.0)

            profit = payout - risk
            status = "Won" if data.get("is_settled") else "Pending"

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
                    "win_prob": "55.0%",
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
