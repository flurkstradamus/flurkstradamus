import streamlit as st

def render_leaderboard():
    st.subheader("🏆 Leaderboard")
    st.caption("Consensus standings, return on investment, member tenure, and betting volume.")

    user_stats = {}
    for b in st.session_state.saved_bets:
        u_raw = str(b.get("user", "Bettor")).strip().lower()
        if u_raw not in user_stats:
            user_stats[u_raw] = {"name": b.get("user"), "total_bets": 0, "won": 0, "lost": 0, "pending": 0, "net": 0.0, "total_staked": 0.0, "types": {}}
        user_stats[u_raw]["total_bets"] += 1
        r = float(b.get("risk_dollars", 0))
        p = float(b.get("payout_dollars", b.get("payout", 0)))
        profit_locked = float(b.get("locked_profit", p - r))
        cat = b.get("bet_category", b.get("type", "Single"))
        user_stats[u_raw]["types"][cat] = user_stats[u_raw]["types"].get(cat, 0) + 1
        if b.get("status") == "Won":
            user_stats[u_raw]["won"] += 1
            user_stats[u_raw]["net"] += profit_locked
            user_stats[u_raw]["total_staked"] += r
        elif b.get("status") == "Lost":
            user_stats[u_raw]["lost"] += 1
            user_stats[u_raw]["net"] -= r
            user_stats[u_raw]["total_staked"] += r
        else:
            user_stats[u_raw]["pending"] += 1

    board = []
    for u_key, stat in user_stats.items():
        acc = st.session_state.user_accounts.get(u_key, {})
        if not acc.get("is_public", True): continue
        last_act = acc.get("last_login", "")
        decided = stat["won"] + stat["lost"]
        win_rate = (stat["won"] / decided * 100) if decided > 0 else 0.0
        roi_val = (stat["net"] / stat["total_staked"] * 100) if stat["total_staked"] > 0 else 0.0
        fav_market = max(stat["types"], key=stat["types"].get) if stat["types"] else "Single Play"
        tier_badge = "🎯 Sniper" if (win_rate >= 65.0 and decided >= 3) else ("🔥 On Fire" if (stat["won"] >= 3 and stat["lost"] == 0) else ("⚡ Contender" if decided > 0 else "🌱 Rookie"))

        board.append({
            "name": stat["name"], "online": ("ET" in last_act),
            "total_bets": stat["total_bets"], "won": stat["won"], "lost": stat["lost"], "pending": stat["pending"],
            "win_rate": f"{win_rate:.1f}%", "roi": f"{roi_val:+.1f}%", "total_staked": stat["total_staked"],
            "fav_market": fav_market, "member_since": acc.get("created_at", "N/A"), "tier_badge": tier_badge, "net": stat["net"]
        })

    board.sort(key=lambda x: x["net"], reverse=True)
    if not board:
        st.info("No public tickets on leaderboard.")
        return

    for idx, u in enumerate(board):
        medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"#{idx+1}"))
        status_dot = "🟢 Online" if u["online"] else "⚪ Offline"
        status_color = "#22c55e" if u["online"] else "#94a3b8"
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 4, 2])
            with c1:
                st.markdown(f"**{medal} {u['name']}** <span style='color:{status_color}; font-size:0.75rem;'>{status_dot}</span> `[{u['tier_badge']}]`", unsafe_allow_html=True)
                st.caption(f"🗓️ Member: {u['member_since']} | Top Market: {u['fav_market']}")
            with c2:
                st.write(f"📊 **{u['won']}W - {u['lost']}L** ({u['win_rate']} Win Rate) | **{u['total_bets']}** Slips")
                st.caption(f"Staked: **${u['total_staked']:.2f}** | ROI: **{u['roi']}**")
            with c3:
                color = "#4ade80" if u['net'] >= 0 else "#f87171"
                st.markdown(f"<div style='text-align:right;'><span style='color:{color};font-size:1.35rem;font-weight:700;'>${u['net']:+.2f}</span></div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align:right;opacity:0.65;font-size:0.80rem;'>Net Profit</div>", unsafe_allow_html=True)

def render_squad_feed(games_data, render_ticket_card_fn):
    st.subheader("🔥 Live Squad Feed")
    st.caption("Live stream of tickets placed across the community with real-time match scores.")
    feed_tickets = [b for b in st.session_state.saved_bets if st.session_state.user_accounts.get(str(b.get("user", "")).strip().lower(), {}).get("share_feed", True)]
    if not feed_tickets:
        st.info("No community tickets locked in yet.")
    else:
        for b in feed_tickets[:30]:
            render_ticket_card_fn(b, st.session_state.saved_bets.index(b), games_data, can_delete=False)
