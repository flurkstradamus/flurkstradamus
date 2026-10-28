import streamlit as st

def render_how_it_works():
    st.subheader("💡 How It Works: The Comprehensive User Guide")
    st.markdown("""
    Welcome to **Flurkstradamus** — the algorithmic sports betting dashboard built for live modeling, positive expectation (+EV) market exploitation, and automated bankroll tracking across **NBA, NFL, and NCAA Football**.
    
    ---
    ### 🔑 Core Features & System Architecture
    
    * **🏀 Multi-Sport Coverage**: Seamlessly switch between the **NBA**, **NFL**, and **NCAA Football** with live quarter-by-quarter scoreboards, adjusted possession clocks, and pace regressions.
    * **🎯 Dynamic Player Props**: Pulls real-time rosters from live ESPN endpoints to construct **Player Over/Under X Points** proposition bets for the NBA and **Anytime Touchdowns** for football.
    * **📊 Bankroll & Telemetry Dashboard**: Complete visibility across your betting portfolio:
        * **Settled Realized P&L**: Tracks pure cash won, money lost, and net return on investment (ROI).
        * **Capital at Risk**: Real-time dollar volume of all active, in-flight tickets.
        * **Probability-Adjusted EV Profit**: True mathematical return calculated from live Bayesian quarter-by-quarter score decay.
    * **⚡ Single Game Analytics Engine**: Scan full NFL, NCAA, and NBA slates with live Bayesian pace regression. Tracks scoring momentum, second-half total drift, and ATS cover probabilities across quarters.
    * **🔗 Multi-Leg Combo Builder**: Scan cross-slate parlay combinations with automated compound true probability modeling and cross-game line cushion optimization up to 12 legs.
    * **🏟️ In-Game War Room**: Click any ticket in your history to enter the live game operations room. View projection drift history, real-time possession clock updates, and dynamically shifting cover odds.
    * **🛡️ Immutable Slip Protection**: Your risk stake and entered payout amounts are locked at entry and preserved permanently against container restarts.
    """)

def render_math():
    st.subheader("📖 Flurkstradamus Machine Learning & Mathematical Architecture")
    st.caption("How our proprietary in-game Bayesian pace models uncover market mispricings.")

    with st.container(border=True):
        st.markdown("### 🏆 Why Flurkstradamus Outperforms Traditional Sportsbooks")
        st.markdown("""
        * **Dynamic Tempo Learning:** Flurkstradamus adjusts scoring projections continuously by evaluating drive success, yards per play, possession counts, and quarter-by-quarter pace deviations.
        * **Pace-Shock Variance Insulation:** When shootouts or defensive slogs emerge, our engine dynamically widens or compresses standard deviation ($\sigma$) brackets.
        * **Real Value Margins:** The AI compares its derived mathematical probability against implied sportsbook breakeven lines to surface only positive expected value (+EV) tickets.
        """)

    with st.container(border=True):
        st.markdown("### 📐 Mathematical Formulas & Core Distribution Functions")
        st.markdown("##### 1. Over/Under Win Expectancy (Gaussian Error Function)")
        st.latex(r"Z = \frac{\text{Line} - \mu_{\text{in-game}}}{\sigma_{\text{decay}}}")
        st.latex(r"P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right], \quad P(\text{Over}) = 1 - P(\text{Under})")

        st.markdown("##### 2. Point Spread (ATS) Cover Probability")
        st.latex(r"\Delta_{\text{margin}} = (\text{Home Proj} - \text{Away Proj}) + \text{Line}")
        st.latex(r"P(\text{Home Cover}) = \frac{1}{1 + e^{-\frac{\Delta_{\text{margin}}}{5.0}}}")

        st.markdown("##### 3. Straight-Up Moneyline Logistic Expectancy")
        st.latex(r"P(\text{Home Win}) = \frac{1}{1 + 10^{-\frac{\Delta_{\text{pts}} + (\text{Win\% Diff} \times 7.0)}{14.5}}}")

        st.markdown("##### 4. Player Prop Scoring Engine (Poisson & Volume)")
        st.latex(r"P(\text{Prop}) = 1 - e^{-\left(\lambda_{\text{Team Event}} \times \text{Player Share} \times \text{Defensive Modifier}\right)}")

def render_about():
    st.subheader("ℹ️ About Flurkstradamus")
    st.markdown("""
    * **Lead Architect**: Adam Sowers
    * **Firm**: Sowers Web Technologies
    * **Location**: Altamonte Springs, Florida, United States
    * **Website**: [sweetcustomwebsites.com](https://sweetcustomwebsites.com)
    """)
