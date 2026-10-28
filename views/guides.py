import streamlit as st

def render_how_it_works():
    st.title("💡 How Flurkstradamus Works")
    st.caption("A complete guide to our predictive modeling engine, vision slip parser, and parlay optimization tools.")

    st.markdown("""
    Flurkstradamus is an institutional-grade sports betting analytics engine. Rather than relying on gut feeling, 
    the platform applies **real-time Poisson distributions**, **possession tempo drift models**, and **multimodal vision OCR** 
    to pinpoint positive mathematical expectancy (+EV) across NBA, NFL, and NCAA slates.
    """)

    st.markdown("---")

    # Core Tools Breakdown
    st.markdown("## 🛠️ Deep Dive into Core Tools")

    # Tool 1: Single Game Engine
    with st.expander("⚡ 1. Single Game Engine (In-Game Drift & OCR Auto-Fill)", expanded=True):
        st.markdown("""
        The **Single Game Engine** is designed for deep matchup analysis before kickoff or during live gameplay.

        ### Key Capabilities:
        * **Live Pace & Terminal Drift Modeling**: Dynamically calculates projected final scores, 2nd-half total variance, ATS covering probability, and outright win expectancies using Bayesian scoring distributions.
        * **Multimodal Vision OCR Slip Parser**: Upload bet slips from Robinhood, DraftKings, FanDuel, BetMGM, or Caesars. Gemini Vision extracts the teams, strike lines, side, risk dollars, and payout to automatically populate your ticket form.
        * **Consensus Edge Recommendations**: Compares the bookmakers' opening lines against live pace metrics to output highest-conviction market picks.
        * **Tiered Strategy Picks (Good, Better, Best)**: Choose between safe floor anchors, balanced +EV value, and optimal alpha plays with automated slip population.

        ### Step-by-Step Workflow:
        1. **Select Matchup Method**: Choose between **🎯 Manual Matchup Selection** or let the **🤖 AI Auto-Select Optimal Matchup** with the highest market divergence.
        2. **Review Matchup Telemetry**: Observe live pace drift, projected second-half totals, and ATS coverage margins.
        3. **Review Tiered Recommendations**: Compare the **🥉 Good**, **🥈 Better**, and **🥇 Best** suggested picks.
        4. **Lock In Ticket**: Click **📥 Load Pick** to populate the slip form below, fine-tune your risk or payout, and submit to your bankroll tracker.
        """)

    # Tool 2: Multi-Leg Combo Builder
    with st.expander("🔗 2. Multi-Leg Cross-Sport Combo Builder", expanded=True):
        st.markdown("""
        The **Combo Builder** enables cross-sport parlay construction spanning up to 12 legs with true compound probability evaluation.

        ### Key Capabilities:
        * **Automated AI Parlay Optimizer**: Automatically scans the slate for market inefficiencies based on your selected strategy:
            * **🛡️ Safe Floor**: Optimizes for high individual leg win percentages and defensive variance cushions.
            * **⚖️ Balanced Edge**: Targets the sweet spot between +EV value and compound risk.
            * **🚀 High Profit**: Explores maximum odds multipliers and offensive upside.
        * **Dynamic Multi-Market Support**: Automatically adapts options to the selected sport:
            * **NBA**: Totals, Spreads, Moneylines, and *Player Points Props*.
            * **Football**: Totals, Spreads, Moneylines, and *Anytime Touchdown Scorers*.
            * **All Games**: Cross-sport combinations.
        * **True Compound Expectancy & Analytics**: Multiplies independent mathematical probabilities rather than bookmaker-juiced odds to provide honest break-even probability, zero-vig fair odds, and volatility profiles.

        ### Step-by-Step Workflow:
        1. Select your target **League Scope**, **Target Market Focus**, **Number of Legs** (2–12), and **Strategy Profile**.
        2. Click **⚡ Auto-Generate Combo** to generate a parlay slate with team logos, kickoff timestamps, and analytics metrics.
        3. Review individual edge rationale in the **🧠 AI Model Strategy & Edge Rationales** accordion.
        4. Use **✏️ Edit selection or remove legs** to adjust any legs you want to discard.
        5. Click **📥 Load Combo to Slips** to transfer the picks to the ticket builder below, set your risk amount, and lock in the parlay.
        """)

    # Tool 3: Live Squad Feed & Locked Bets History
    with st.expander("📜 3. Locked Bets History & 🔥 Live Squad Feed", expanded=False):
        st.markdown("""
        Real-time tracking and community transparency tools.

        ### Key Capabilities:
        * **Locked Bets History**: Your private ledger tracking every locked wager, exact risk dollars, locked potential profit, ROI %, and real-time settlement status (`🏆 WON`, `❌ LOST`, `⚡ IN PLAY`, `⏳ SCHEDULED`).
        * **Live Squad Feed**: A shared public feed displaying wagers placed across the entire community in real time.
        * **Dynamic Status Badging**: Active games display real-time win probability percentages. Completed and settled games cleanly omit live probability tags once the outcome is finalized.
        * **One-Click War Room Launch**: Every card features a **🏟️ War Room** button that immediately loads a live scoreboard display for that game.
        """)

    # Tool 4: War Room
    with st.expander("🏟️ 4. The Live War Room", expanded=False):
        st.markdown("""
        The **War Room** is a focused game-day command center for actively sweating locked tickets.

        ### Key Capabilities:
        * Real-time game clock and quarter/half progression.
        * Official team circular logos and live score counters.
        * Live win probability tracking that updates as each possession unfolds.
        """)

    st.markdown("---")

    # Pro Tips
    st.markdown("## 💡 Best Practices & Pro Tips")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        #### 📈 Bankroll Discipline
        * **Stick to 1–2% Units**: Avoid wagering more than 1% to 2.5% of your total bankroll on any single ticket.
        * **Trust Expected Value (+EV)**: Short-term variance happens. Consistent long-term profit comes from beating market closing lines.
        """)

    with col2:
        st.markdown("""
        #### 🔍 Parlay Construction
        * **Limit Parlay Legs**: While the engine supports up to 12 legs, 2-to-4 leg combos mathematically produce significantly lower drawdown.
        * **Cross-Market Diversification**: Mix a high-probability Moneyline with a pace-suppressed Game Total Under to reduce slate exposure.
        """)

def render_math():
    st.title("📖 Model Methodology & Mathematics")
    st.caption("Theoretical framework, mathematical derivations, and predictive architecture.")

    st.markdown("""
    Flurkstradamus utilizes a hybrid modeling framework combining **Poisson Process Regression**, 
    **Bayesian In-Game Updating**, and **Monte Carlo Normal Cumulative Distribution Functions (CDF)**.

    ### 1. In-Game Pace & Drift Equation
    Terminal projected score ($S_{proj}$) adapts to in-game pace discrepancies using dynamic ratio dampening:
    """)

    st.latex(r"S_{proj} = S_{open} + \left( S_{scored} - (S_{open} \times P_w) \right) \times \alpha")

    st.markdown("""
    Where:
    * $S_{open}$ is the pregame closing game total.
    * $S_{scored}$ is the sum of live points scored.
    * $P_w$ is the period weight ($0.25$ for Q1, $0.50$ for Half, $0.75$ for Q3).
    * $\alpha$ is the tempo drift dampening coefficient ($0.90$ for extreme blowouts, $0.35$ for steady pace).

    ### 2. Gaussian Probability Integrals
    Win probabilities for Totals and Point Spreads are computed using the normal cumulative distribution function:
    """)

    st.latex(r"P(\text{Under } X) = \Phi\left(\frac{X - \mu}{\sigma}\right) = \frac{1}{\sqrt{2\pi}} \int_{-\infty}^{\frac{X-\mu}{\sigma}} e^{-\frac{t^2}{2}} dt")

    st.markdown("""
    Where $\mu$ represents our model's terminal projection and $\sigma$ represents the volatility bracket for that sport.
    """)

def render_about():
    st.title("ℹ️ About Flurkstradamus")
    st.caption("Algorithmic sports analytics, automated bankroll tracking, and high-performance betting telemetry.")

    st.markdown("""
    **Flurkstradamus** was engineered to replace emotional betting bias with transparent, mathematical modeling. 
    By synthesizing real-time sports APIs, live pace drift regressions, compound Poisson distributions, and computer vision OCR, 
    the platform delivers institutional-grade predictive analytics directly into the hands of everyday sports bettors.
    """)

    st.markdown("---")

    st.markdown("### 👨‍💻 Engineering & Development")
    with st.container(border=True):
        c1, c2 = st.columns([1.2, 2.8])
        with c1:
            st.markdown("""
            **Creator & Lead Engineer:**  
            **Development Company:**  
            **Headquarters:**  
            **Portfolio / Website:**  
            """)
        with c2:
            st.markdown("""
            **Adam Sowers**  
            **Sowers Web Technologies**  
            Altamonte Springs, FL  
            [sweetcustomwebsites.com](https://sweetcustomwebsites.com)
            """)

        st.caption("Crafted by Sowers Web Technologies — specializing in bespoke full-stack applications, data dashboards, and algorithmic engines.")
