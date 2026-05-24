"""
Market breadth filter.
Fetches S&P 500 Bullish Percent Index (^SPXBDP) via yfinance.
Returns % of S&P500 stocks in bullish point-and-figure patterns.
Weak (<40%) = penalize BUY signals. Strong (>60%) = support BUY signals.
"""
from log import get_logger

log = get_logger(__name__)

WEAK_THRESHOLD = 40.0
STRONG_THRESHOLD = 60.0
BREADTH_TICKER = "^SPXBDP"  # S&P 500 Bullish Percent Index on Yahoo Finance


def _fetch_spx_breadth_pct() -> float | None:
    """Fetch latest S&P500 Bullish Percent Index value (0-100)."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(BREADTH_TICKER)
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        return round(float(hist["Close"].iloc[-1]), 1)
    except Exception as e:
        log.debug(f"Breadth fetch failed: {e}")
        return None


def get_market_breadth() -> dict:
    """
    Return breadth dict:
      {
        "breadth_pct": float | None,  # 0-100, % of S&P500 stocks bullish
        "signal": "weak" | "neutral" | "strong" | "unknown"
      }
    """
    pct = _fetch_spx_breadth_pct()
    if pct is None:
        return {"breadth_pct": None, "signal": "unknown"}

    if pct < WEAK_THRESHOLD:
        signal = "weak"
    elif pct > STRONG_THRESHOLD:
        signal = "strong"
    else:
        signal = "neutral"

    return {"breadth_pct": pct, "signal": signal}


def breadth_context_str(breadth: dict) -> str:
    """Format breadth dict into a one-line LLM context string."""
    pct = breadth.get("breadth_pct")
    sig = breadth.get("signal", "unknown")
    if pct is None:
        return "Market breadth: unavailable"
    return (
        f"Market breadth (S&P500 BPI): {pct}% — {sig}. "
        + ({
            "weak": "Less than 40% of S&P500 stocks are bullish — penalize BUY signals.",
            "strong": "Over 60% of S&P500 stocks are bullish — supports BUY setups.",
            "neutral": "Mixed market internals — no breadth bias.",
        }.get(sig, ""))
    )
