# Target Market Options (Include 3-Pointers for NBA and Cross-Sport)
        if league_choice == "NBA":
            market_options = [
                "⚡ Let the System Pick (Best NBA Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏀 NBA Player Points Prop",
                "🎯 NBA Player Three-Pointers Made (1+, 2+, 3+)"
            ]
        elif league_choice in ["NFL", "NCAA Football"]:
            market_options = [
                "⚡ Let the System Pick (Best Football Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏈 Football Anytime Touchdown Scorer"
            ]
        else:
            market_options = [
                "⚡ Let the System Pick (Best Discrepancy)",
                "📊 Game Totals (Over / Under)",
                "🛡️ Point Spreads (ATS Cover)",
                "🏆 Straight Up Winners (Moneyline)",
                "🏀 NBA Player Points Prop",
                "🎯 NBA Player Three-Pointers Made (1+, 2+, 3+)",
                "🏈 Football Anytime Touchdown Scorer"
            ]

        # Ensure active selection exists in market_options to prevent Streamlit widget lock
        current_market_val = st.session_state.get("sg_static_market")
        market_idx = 0
        if current_market_val in market_options:
            market_idx = market_options.index(current_market_val)

        chosen_market = c3.selectbox(
            "Target Bet / Market Type",
            market_options,
            index=market_idx,
            key="sg_static_market",
            on_change=trigger_tier_auto_refresh
        )
