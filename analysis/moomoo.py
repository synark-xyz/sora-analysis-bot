"""
analysis/moomoo.py — Moomoo analytical framework.

Structured 5-step methodology for comprehensive stock analysis.
Provides prompt templates and the build_moomoo_prompt() assembler.
"""

MOOMOO_STEP1 = """Step 1: Define Analysis Objective & Scope
Assess the investment merit of {symbol} by evaluating intrinsic value,
growth trajectory, financial health, and market timing.
Explicitly identify potential price levels for entry and exit/risk management.
"""

MOOMOO_STEP2 = """Step 2: Data Collection & Processing
Internal data — fundamental financials (income, balance sheet, cash flow),
real-time and historical market data (price, volume), analyst estimates.
External data — news for sentiment and catalyst analysis, sector/industry context.
"""

MOOMOO_STEP3 = """Step 3: Multi-Dimensional Analysis

3a. Fundamental Analysis — Assess the Business:
- Financial Health: profitability margins, ROE/ROA, liquidity, leverage
- Growth Drivers: revenue and EPS trends, market share, industry tailwinds, R&D
- Competitive Moat: barriers to entry, brand, technology edge
- Management: capital allocation, buybacks, dividends, guidance credibility

3b. Valuation Analysis — Price vs Value:
- Comparative: P/E (vs history and industry), P/B, P/S, PEG
- Fair Value: analyst price targets, model-based estimates
- Verdict: overvalued, fairly valued, or undervalued

3c. Technical & Sentiment Analysis — Timing:
- Price Action: key support/resistance, 52-week range, chart patterns
- Momentum: RSI, MACD, moving averages (50/200 SMA), trend strength (ADX)
- Market Sentiment: volume analysis, news tone, catalysts
"""

MOOMOO_STEP4 = """Step 4: Synthesis & Entry/Exit Zone Detection
- Growth Potential: integrate fundamental findings into a clear narrative
- Entry Zone: confluences where valuation becomes attractive AND price
  approaches technical support (value entry) or breaks resistance with
  volume (tactical entry)
- Exit / Risk: profit-taking where overvalued + resistance; stop-loss
  below key support that invalidates the thesis
"""

MOOMOO_STEP5 = """Step 5: Structured Report
1. Executive Summary — integrated verdict upfront
2. Detailed Breakdown — growth, valuation, technical sections
3. Strategic Synthesis — entry zones (aggressive vs patient), exit/risk levels
4. Monitoring Catalysts — upcoming events that could impact the thesis
"""

ENTRY_EXIT_STRATEGY = """
Entry Zone Strategy (apply in Step 4):
- Tactical Entry: Enter a portion when price breaks above key resistance
  on above-average volume (momentum confirmation)
- Value Entry: Primary entry zone where valuation is compelling (near
  historical avg P/E, below fair value) AND price approaches major
  technical support (200-day MA, prior swing low)
- Scale In: 25-50% at tactical trigger, remainder on value zone pullback
"""

EXIT_RISK_STRATEGY = """
Exit / Risk Management Strategy:
- Technical Stop: Place just below the key support that defined the entry
  zone (3-5% below support invalidates the setup)
- Fundamental Stop: Exit if core thesis breaks (lost client, guidance cut)
- Profit-Taking: Scale out at valuation targets; let remainder run with
  a trailing stop (10% below highest close)
- Scale Out: Sell 25-50% at first target, let rest run with trailing stop
"""

RISK_PRINCIPLES = """
Risk Management Principles:
1. Process Over Prediction — follow rigorous process, results follow
2. Margin of Safety — seek gap between price and intrinsic value
3. Let Winners Run, Cut Losers Short — rigid stops keep losses small
4. Position Sizing — bet size = f(conviction, risk/distance to stop);
   never risk >1-2% of capital per idea
"""

_MOOMOO_FRAMEWORK_TEXT = f"""
{MOOMOO_STEP1}
{MOOMOO_STEP2}
{MOOMOO_STEP3}
{MOOMOO_STEP4}
{MOOMOO_STEP5}
{ENTRY_EXIT_STRATEGY}
{EXIT_RISK_STRATEGY}
{RISK_PRINCIPLES}
"""


def build_moomoo_prompt(
    symbol: str,
    indicators: dict,
    regime: dict,
    news: str,
    fundamentals: str,
    valuation: str,
    wiki_context: str = "",
) -> str:
    market_data = f"""
Symbol: {symbol}
Indicators: {indicators}
Regime: {regime}
News: {news}
Fundamentals: {fundamentals}
Valuation: {valuation}
User Context: {wiki_context}
"""
    return f"""{_MOOMOO_FRAMEWORK_TEXT}

---
DATA FOR {symbol}:
{market_data}
---
"""


def build_executive_data(symbol: str, indicator_summary: dict) -> str:
    rsi = indicator_summary.get("rsi_14", "N/A")
    adx = indicator_summary.get("adx", "N/A")
    price = indicator_summary.get("price", "N/A")
    ema_20 = indicator_summary.get("ema_20", "N/A")
    ema_50 = indicator_summary.get("ema_50", "N/A")
    return f"Price=${price} | RSI={rsi} | ADX={adx} | EMA20=${ema_20} | EMA50=${ema_50}"
