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
    Examine this screenshot of a bet slip, Robinhood event contract, parlay ticket, or sports wager.
    
    Extract all details into a strictly valid JSON object adhering to this schema:
    {
        "is_combo": boolean,
        "legs_count": int,
        "legs": [
            {
                "selection": "string (e.g. MTU, JMU, Chiefs, Under 220.5)",
                "side": "Yes" | "No" | "Over" | "Under" | "Spread" | "Moneyline",
                "market": "string or null"
            }
        ],
        "league": "NCAA" | "NFL" | "NBA" | "OTHER",
        "away_team": "string or null",
        "home_team": "string or null",
        "picked_team": "string or null",
        "wager_type": "Multi-Leg Parlay" | "Game Total" | "Point Spread" | "Moneyline" | "Player Points Prop" | "Anytime TD",
        "side": "Under" | "Over" | "Spread" | "Moneyline" | "Yes" | "No",
        "line": float or null,
        "risk": float,
        "payout": float,
        "profit": float or null,
        "is_settled": boolean,
        "is_won": boolean or null
    }

    Specific rules for Robinhood Event Contracts & Parlays:
    1. If the header mentions "X-leg combo payout" or lists multiple items under "Legs", set "is_combo": true, "wager_type": "Multi-Leg Parlay", and extract every item under "legs".
    2. In Robinhood: "Realized loss: $X.XX" means risk = X.XX, payout = 0.0, is_settled = true, is_won = false.
    3. In Robinhood: "+$0.00" or "Settlement price: $0.00" means payout was 0.00 (Loss if realized loss > 0).
    4. "Quantity" refers to contracts purchased, not dollar risk.
    5. Teams like MTU (Middle Tennessee), JMU (James Madison), MIA (Miami), UCLA, SMU, WMU (Western Michigan), LIB (Liberty), UNLV, NDSU are NCAA College Football/Basketball. Set "league": "NCAA".
    6. Return ONLY the JSON object. No explanations, no markdown fences, no backticks.
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
    if not games_data:
        return None

    target_league = (data.get("league") or "").upper().strip()
    a_target = (data.get("away_team") or "").lower().strip()
    h_target = (data.get("home_team") or "").lower().strip()
    p_target = (data.get("picked_team") or "").lower().strip()

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

    for gm in league_pool:
        if a_target and h_target:
            if check_match(gm, a_target) and check_match(gm, h_target):
                return gm

    for gm in league_pool:
        for t in [a_target, h_target, p_target]:
            if t and len(t) >= 3 and check_match(gm, t):
                return gm

    if league_pool != games_data:
        for gm in games_data:
            if (a_target and check_match(gm, a_target)) or (h_target and check_match(gm, h_target)):
                return gm

    return None

def determine_scanned_bet_outcome(data, matched_game):
    is_combo = data.get("is_combo", False) or len(data.get("legs", [])) > 1
    
    if data.get("is_settled"):
        if data.get("is_won") is True:
            return "Won", 1.0, "Settled"
        elif data.get("is_won") is False:
            return "Lost", 0.0, "Settled"

    if is_combo:
        legs_c = len(data.get("legs", [])) or int(data.get("legs_count") or 2)
        approx_p = max(0.01, min(0.40, round(0.55 ** legs_c, 3)))
        return ("Lost" if data.get("is_won") is False else "Pending"), approx_p, "Multi-Leg"

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

        return ("Won", 1.0, "Final") if won else ("Lost", 0.0, "Final")

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
        if "Total" in w_type and line > 0:
            ou_line = float(matched_game.get("market_ou", line))
            prob = calculate_win_prob(line, ou_line, 10.0, is_under=(side == "Under"))
        elif "Moneyline" in w_type or "Winner" in w_type:
            h_p = calculate_moneyline_prob(100, 100, matched_game.get("home_record", "0-0"), matched_game.get("away_record", "0-0"))
            prob = h_p if (picked_t == h_team or h_team in picked_t) else (1.0 - h_p)
        else:
            prob = 0.54
        return "Pending", max(0.05, min(0.95, prob)), matched_game.get("kickoff") or "Scheduled"

def build_ticket_record(data, matched_game, status_result, prob_calc, curr_user, active_uname, get_current_et_time_fn):
    is_combo = data.get("is_combo", False) or len(data.get("legs", [])) > 1
    legs_list = data.get("legs", [])
    legs_count = len(legs_list) if legs_list else int(data.get("legs_count") or 1)
    
    r_val = float(data.get("risk") or 10.0)
    p_val = float(data.get("payout") or 0.0) if status_result == "Lost" else float(data.get("payout") or 19.10)
    profit_val = p_val - r_val
    conf_league = matched_game.get("league") if matched_game else (data.get("league") or "SPORTS")

    if is_combo:
        parsed_legs = [
            {
                "matchup": lg.get("selection", "Event Contract"),
                "type": "Robinhood Event Contract",
                "side": lg.get("side", "Yes"),
                "line": None,
                "picked_team": lg.get("selection", "")
            } for lg in legs_list
        ]
        return {
            "id": str(datetime.now().timestamp()) + str(hash(data.get("risk", 0)))[:4],
            "user": curr_user.get("display_name", active_uname),
            "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
            "type": f"{legs_count}-Leg Combo",
            "bet_category": "Combo",
            "matchup": f"{legs_count}-Leg: " + ", ".join([l.get("selection", "") for l in legs_list[:4]]) if legs_list else f"{legs_count}-Leg Combo",
            "bet": f"{legs_count} Legs ({prob_calc * 100:.1f}% Win Prob)" if not legs_list else f"{legs_count}-Leg Combo: " + ", ".join([l.get("selection","") for l in legs_list[:3]]),
            "risk_dollars": r_val,
            "payout_dollars": p_val,
            "payout": p_val,
            "locked_profit": profit_val,
            "win_prob": f"{prob_calc * 100:.1f}%",
            "status": status_result,
            "parsed_legs": parsed_legs,
            "notes": f"[{conf_league}] Scanned {legs_count}-Leg Ticket"
        }
    else:
        w_type = data.get("wager_type", "Game Total")
        side = data.get("side", "Under")
        line = float(data.get("line") or 0.0)
        away_t = matched_game.get("away_team") if matched_game else (data.get("away_team") or "")
        home_t = matched_game.get("home_team") if matched_game else (data.get("home_team") or "")
        picked_t = data.get("picked_team") or (home_t if "Moneyline" in w_type else "")

        matchup_str = f"{away_t} @ {home_t}" if (away_t and home_t) else (picked_t or "Custom Wager")
        if line > 0:
            pick_label = f"{side} {line}" if w_type == "Game Total" else f"{picked_t} {side} {line}"
        else:
            pick_label = f"{picked_t} {side}"

        return {
            "id": str(datetime.now().timestamp()) + str(hash(r_val))[:4],
            "user": curr_user.get("display_name", active_uname),
            "date": get_current_et_time_fn().strftime("%Y-%m-%d %H:%M ET"),
            "type": "Single",
            "bet_category": w_type,
            "home_team": home_t,
            "away_team": away_t,
            "picked_team": picked_t,
            "matchup": matchup_str,
            "bet": pick_label,
            "target_line": line if line > 0 else None,
            "bet_direction": side,
            "risk_dollars": r_val,
            "payout_dollars": p_val,
            "payout": p_val,
            "locked_profit": profit_val,
            "win_prob": f"{prob_calc * 100:.1f}%",
            "status": status_result,
            "notes": f"[{conf_league}] {w_type}"
        }

def render_slip_scanner(curr_user, active_uname, games_data, get_current_et_time_fn):
    st.subheader("📸 Batch Bet Slip Scanner")
    st.caption("Upload multiple ticket screenshots at once (Robinhood, DraftKings, FanDuel, Caesars, BetMGM) to automatically parse all slips and lock them in batch.")

    if "batch_scanned_items" not in st.session_state:
        st.session_state.batch_scanned_items = []

    # MULTI-FILE UPLOADER CONTAINER
    with st.container(border=True):
        uploaded_files = st.file_uploader(
            "Upload 1 or More Bet Slip Screenshots (PNG, JPG, WEBP)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="batch_slip_uploader"
        )

        if uploaded_files:
            c1, c2 = st.columns([2.5, 3.5], vertical_alignment="center")
            with c1:
                btn_label = f"⚡ Scan All {len(uploaded_files)} Slips" if len(uploaded_files) > 1 else "⚡ Scan Slip"
                if st.button(btn_label, type="primary", use_container_width=True):
                    scanned_results = []
                    prog_bar = st.progress(0, text="Starting batch vision scan...")
                    
                    for i, file_obj in enumerate(uploaded_files):
                        prog_pct = (i + 1) / len(uploaded_files)
                        prog_bar.progress(prog_pct, text=f"Analyzing slip {i+1} of {len(uploaded_files)}: {file_obj.name}...")
                        parsed_json, err = parse_bet_slip_image(file_obj.read())
                        if parsed_json:
                            scanned_results.append({
                                "file_name": file_obj.name,
                                "data": parsed_json
                            })
                        else:
                            st.error(f"❌ Failed to parse {file_obj.name}: {err}")

                    prog_bar.empty()
                    if scanned_results:
                        st.session_state.batch_scanned_items = scanned_results
                        st.toast(f"✅ Successfully scanned {len(scanned_results)} ticket(s)!", icon="📸")
                        st.rerun()

            with c2:
                if st.session_state.batch_scanned_items:
                    if st.button("🗑️ Clear Scanned Queue", use_container_width=True):
                        st.session_state.batch_scanned_items = []
                        st.rerun()

    # BATCH QUEUE INSPECTION & LOCK-IN ACTIONS
    if st.session_state.batch_scanned_items:
        items = st.session_state.batch_scanned_items
        st.markdown("---")

        top_act1, top_act2 = st.columns([3, 2], vertical_alignment="center")
        with top_act1:
            st.markdown(f"### 📋 Scanned Tickets Queue ({len(items)})")
        with top_act2:
            if st.button(f"🔒 Lock All {len(items)} Tickets into History", type="primary", use_container_width=True):
                new_tickets = []
                for item_obj in items:
                    d = item_obj["data"]
                    is_combo = d.get("is_combo", False) or len(d.get("legs", [])) > 1
                    mg = None if is_combo else match_game_robustly(d, games_data)
                    stat, p_calc, _ = determine_scanned_bet_outcome(d, mg)
                    tkt_dict = build_ticket_record(d, mg, stat, p_calc, curr_user, active_uname, get_current_et_time_fn)
                    new_tickets.append(tkt_dict)

                for t in reversed(new_tickets):
                    st.session_state.saved_bets.insert(0, t)

                save_all_storage(
                    st.session_state.saved_bets,
                    st.session_state.chat_messages,
                    st.session_state.user_accounts,
                    st.session_state.banned_emails,
                    st.session_state.game_snapshots,
                    st.session_state.support_tickets
                )
                st.session_state.batch_scanned_items = []
                st.toast(f"🎉 Successfully locked in {len(new_tickets)} tickets!", icon="✅")
                st.session_state.active_nav_page = "📜 Locked Bets History"
                st.rerun()

        # Display Each Scanned Ticket in the Queue
        for q_idx, item_obj in enumerate(items):
            data = item_obj["data"]
            f_name = item_obj.get("file_name", f"Ticket #{q_idx+1}")
            is_combo = data.get("is_combo", False) or len(data.get("legs", [])) > 1
            legs_list = data.get("legs", [])
            legs_count = len(legs_list) if legs_list else int(data.get("legs_count") or 1)

            matched_game = None if is_combo else match_game_robustly(data, games_data)
            status_result, prob_calc, timing_desc = determine_scanned_bet_outcome(data, matched_game)

            active_league = matched_game.get("league") if matched_game else (data.get("league") or "NCAA")
            league_icon = "🏈" if ("NCAA" in active_league or "NFL" in active_league) else ("🏀" if "NBA" in active_league else "⚡")

            if status_result == "Won":
                badge_html = "<span style='background-color:#22c55e;color:#000;font-weight:800;padding:2px 8px;border-radius:12px;font-size:0.75rem;'>🏆 WON</span>"
            elif status_result == "Lost":
                badge_html = "<span style='background-color:#ef4444;color:#fff;font-weight:800;padding:2px 8px;border-radius:12px;font-size:0.75rem;'>❌ LOST</span>"
            elif status_result == "In-Play":
                badge_html = "<span style='background-color:#eab308;color:#000;font-weight:800;padding:2px 8px;border-radius:12px;font-size:0.75rem;'>⚡ IN PLAY</span>"
            else:
                badge_html = "<span style='background-color:rgba(255,255,255,0.12);color:#94a3b8;font-weight:700;padding:2px 8px;border-radius:12px;font-size:0.75rem;'>⏳ PENDING</span>"

            prob_badge = f"<span style='background-color:rgba(56,189,248,0.15);color:#38bdf8;font-weight:700;padding:2px 8px;border-radius:6px;font-size:0.75rem;'>🎲 {prob_calc * 100:.1f}%</span>"
            lg_badge = f"<span style='background-color:rgba(255,255,255,0.08);color:#f1f5f9;font-weight:700;padding:2px 8px;border-radius:6px;font-size:0.75rem;'>{league_icon} {active_league}</span>"

            r_val = float(data.get("risk") or 10.0)
            p_val = float(data.get("payout") or (0.0 if status_result == "Lost" else 19.10))
            profit_val = p_val - r_val
            profit_color = "#ef4444" if profit_val < 0 else "#4ade80"

            if is_combo:
                card_title = f"#{q_idx+1}: 🔗 {legs_count}-Leg Combo Ticket ({f_name})"
            elif matched_game:
                card_title = f"#{q_idx+1}: {matched_game.get('away_short')} @ {matched_game.get('home_short')} ({f_name})"
            else:
                card_title = f"#{q_idx+1}: {data.get('away_team') or 'Away'} @ {data.get('home_team') or 'Home'} ({f_name})"

            with st.expander(card_title, expanded=True):
                # Header row with status badges
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:6px; margin-bottom:10px; flex-wrap:wrap; gap:6px;">
                    <span style="font-weight:700; font-size:0.95rem;">{card_title}</span>
                    <div style="display:flex; align-items:center; gap:6px;">
                        {lg_badge}
                        {prob_badge}
                        {badge_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if is_combo and legs_list:
                    st.markdown("**Legs Breakdown:**")
                    chip_cols = st.columns(min(len(legs_list), 4))
                    for l_idx, leg in enumerate(legs_list):
                        c_idx = l_idx % min(len(legs_list), 4)
                        chip_cols[c_idx].markdown(f"""
                        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:6px; padding:4px 8px; margin-bottom:4px; font-size:0.80rem;">
                            <span style="opacity:0.5;">#{l_idx+1}</span> <strong style="color:#4ade80;">{leg.get('side', 'Yes')}</strong> {leg.get('selection', '')}
                        </div>
                        """, unsafe_allow_html=True)
                elif matched_game:
                    a_logo = matched_game.get("away_logo") or DEFAULT_LOGO
                    h_logo = matched_game.get("home_logo") or DEFAULT_LOGO
                    a_sc = matched_game.get("away_score", 0)
                    h_sc = matched_game.get("home_score", 0)
                    is_fin = (status_result in ["Won", "Lost"])
                    sc_lbl = f"{a_sc} - {h_sc} (Final)" if is_fin else f"🗓️ {matched_game.get('kickoff', 'Scheduled')}"

                    st.markdown(f"""
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                        <img src="{a_logo}" width="22" height="22" style="border-radius:50%; object-fit:contain; background:#1e293b;">
                        <strong>{matched_game.get('away_short')}</strong>
                        <span style="opacity:0.4;">@</span>
                        <img src="{h_logo}" width="22" height="22" style="border-radius:50%; object-fit:contain; background:#1e293b;">
                        <strong>{matched_game.get('home_short')}</strong>
                        <span style="background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:4px; font-size:0.78rem; font-weight:700;">{sc_lbl}</span>
                    </div>
                    """, unsafe_allow_html=True)

                # Form for editing and locking individual item
                with st.form(f"batch_item_form_{q_idx}"):
                    f1, f2, f3, f4 = st.columns(4)
                    risk_inp = f1.number_input("Risk ($)", value=r_val, step=1.0, key=f"risk_q_{q_idx}")
                    payout_inp = f2.number_input("Payout ($)", value=p_val, step=1.0, key=f"payout_q_{q_idx}")
                    status_opts = ["Won", "Lost", "Pending"]
                    def_s_idx = 0 if status_result == "Won" else (1 if status_result == "Lost" else 2)
                    status_inp = f3.selectbox("Status", status_opts, index=def_s_idx, key=f"status_q_{q_idx}")
                    
                    with f4:
                        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                        submit_single = st.form_submit_button("🔒 Lock This Ticket", type="primary", use_container_width=True)

                    if submit_single:
                        data["risk"] = risk_inp
                        data["payout"] = payout_inp
                        tkt_record = build_ticket_record(data, matched_game, status_inp, prob_calc, curr_user, active_uname, get_current_et_time_fn)
                        st.session_state.saved_bets.insert(0, tkt_record)
                        st.session_state.batch_scanned_items.pop(q_idx)
                        save_all_storage(
                            st.session_state.saved_bets,
                            st.session_state.chat_messages,
                            st.session_state.user_accounts,
                            st.session_state.banned_emails,
                            st.session_state.game_snapshots,
                            st.session_state.support_tickets
                        )
                        st.toast(f"🎉 Locked ticket #{q_idx+1}!", icon="✅")
                        st.rerun()
