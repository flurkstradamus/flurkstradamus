# 🔮 Flurkstradamus: In-Game Sports Betting Analytics & Edge Engine

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://flurkstradamus.streamlit.app)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Flurkstradamus** is an algorithmic sports betting analytics engine and bankroll intelligence platform engineered for modern sports investors, bettors, and prediction-market traders.

By pairing real-time live scoreboard telemetry with Bayesian quarter-by-quarter scoring models and automated multimodal slip parsing, Flurkstradamus identifies positive expected value (+EV) market mispricings in college football and the NFL in real time.

---

## ⚡ Key Features

* **📸 Universal Screenshot & Slip Parser**: Upload bet slips or event contracts directly from **Robinhood Derivatives, DraftKings, FanDuel, BetMGM, Caesars, or Kalshi**. Multimodal vision models automatically extract matchup teams, wager types, spread/total lines, risk stakes, potential payouts, and settlement statuses.
* **📊 Comprehensive Bankroll Dashboard**: 
  * **Settled Realized P&L**: Tracks net cash returns and ROI across graded wins and losses.
  * **Active Book Analytics**: Capital at Risk, Max Potential Profit, and Probability-Adjusted Expected Return (EV).
  * **Discipline Metrics**: Tracks average stake sizes, win rates, and preferred market distributions.
* **⚡ Single Game Analytics Engine**: Dynamic Bayesian regression modeling that updates in-game scoring momentum, adjusted second-half totals, and against-the-spread (ATS) cover margins.
* **🔗 Multi-Leg Combo Builder**: Cross-slate parlay constructor supporting up to 12 legs with compound true probability calculations and market cushion filters.
* **🏟️ In-Game War Room**: Detailed match operations view featuring live possession clocks, quarter-by-quarter projection drift tracking, and real-time win probability curves.
* **🏆 Community Leaderboard & Feed**: Public performance leaderboards with verified win rates, member tenure badges, and a live squad stream.
* **🔐 Account & Data Protection**: Persistent session token authentication, email passcode validation on signup, atomic disk saves with automatic `.bak` backups, and a Commissioner admin suite.

---

## 📐 Mathematical Architecture

Flurkstradamus evaluates live game states using continuous probability distributions rather than static pre-game lines:

### 1. Over/Under Win Expectancy (Gaussian Error Function)
Scoring variance around real-time pace expectations is calculated via cumulative normal distributions:
$$Z = \frac{\text{Line} - \mu_{\text{in-game}}}{\sigma_{\text{decay}}}$$
$$P(\text{Under}) = \frac{1}{2} \left[ 1 + \text{erf}\left( \frac{Z}{\sqrt{2}} \right) \right], \quad P(\text{Over}) = 1 - P(\text{Under})$$

### 2. Point Spread (ATS) Cover Probability
Evaluates live score margins through logistic sigmoid curves:
$$\Delta_{\text{margin}} = (\text{Home Proj} - \text{Away Proj}) + \text{Line}$$
$$P(\text{Home Cover}) = \frac{1}{1 + e^{-\frac{\Delta_{\text{margin}}}{5.0}}}$$

### 3. Straight-Up Moneyline Logistic Expectancy
$$P(\text{Home Win}) = \frac{1}{1 + 10^{-\frac{\Delta_{\text{pts}} + (\text{Win\% Diff} \times 7.0)}{14.5}}}$$

### 4. Player Anytime Touchdown Scorer Prop Modeling
Dynamic Poisson TD probability adjusted for red-zone share (< 5 yards) and goal-line touch volume:
$$P(\text{TD}) = 1 - e^{-\left(\lambda_{\text{Team TD}} \times \text{Player Share} \times \text{Defensive Modifier}\right)}$$

---

## 🛠️ Tech Stack

* **Framework**: [Streamlit](https://streamlit.io/)
* **Language**: Python 3.10+
* **Data Ingestion**: ESPN Scoreboard & Live Team Roster API endpoints
* **Multimodal Vision OCR**: Google Gemini API (`gemini-2.0-flash`, `gemini-2.5-flash`)
* **Image Processing**: Pillow (`PIL`)
* **Storage**: Atomic JSON persistence with automatic snapshot failover

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone [https://github.com/flurkstradamus/flurkstradamus.git](https://github.com/flurkstradamus/flurkstradamus.git)
cd flurkstradamus
