"""
engine/filters.py — Pre-execution trade filters (v2, crypto-friendly).

Each filter returns a FilterResult. If any filter blocks, the trade is rejected.
All filters are deterministic and explainable.

Differences from core/trade_filters.py:
  - No shariah check
  - No earnings check for crypto symbols
  - No alpaca_client or fmp_key constructor deps
  - Pure static function interface
"""

from dataclasses import dataclass


@dataclass
class FilterResult:
    passed: bool
    reason: str = ""
    severity: str = "info"  # "block" | "warn" | "info"


def check_all(symbol: str, indicators: dict, bars: list[dict], market: str = "us") -> FilterResult:
    """Run all applicable filters. Returns first blocking failure or a pass."""
    checks = []

    if market != "crypto":
        checks.append(("earnings", _check_earnings(symbol)))

    checks.extend([
        ("liquidity", _check_liquidity(indicators, bars)),
        ("volume_environment", _check_volume_environment(indicators, bars)),
        ("spread", _check_spread(indicators)),
    ])

    for name, result in checks:
        if not result.passed:
            return FilterResult(passed=False, reason=f"[{name}] {result.reason}", severity="block")

    return FilterResult(passed=True, reason="All filters passed")


def _check_earnings(symbol: str) -> FilterResult:
    """Skip if earnings within 3 days using yfinance earnings calendar."""
    try:
        import yfinance as yf
        tk = yf.Ticker(symbol)
        cal = tk.calendar
        if cal is None or cal.empty:
            return FilterResult(passed=True, reason="No earnings calendar data")

        earnings_date = None
        if "Earnings Date" in cal.index:
            val = cal.loc["Earnings Date"]
            earnings_date = val.iloc[0] if hasattr(val, 'iloc') else val
        elif "Earnings High" in cal.index:
            earnings_date = cal.index[0]

        if earnings_date is None or isinstance(earnings_date, str):
            return FilterResult(passed=True, reason="No upcoming earnings date")

        if hasattr(earnings_date, 'date'):
            earnings_dt = earnings_date
        elif hasattr(earnings_date, 'to_pydatetime'):
            earnings_dt = earnings_date.to_pydatetime()
        elif isinstance(earnings_date, datetime):
            earnings_dt = earnings_date
        else:
            return FilterResult(passed=True, reason="Cannot parse earnings date")

        from datetime import datetime
        now = datetime.now(earnings_dt.tzinfo) if earnings_dt.tzinfo else datetime.now()
        days_until = (earnings_dt - now).days

        if 0 <= days_until <= 3:
            return FilterResult(
                passed=False,
                reason=f"Earnings in {days_until} day(s) on {earnings_dt.date()}",
            )
        if days_until < 0:
            return FilterResult(passed=True, reason=f"Last earnings was {-days_until} day(s) ago")

        return FilterResult(passed=True, reason=f"Next earnings in {days_until} days (outside blackout)")
    except Exception as e:
        return FilterResult(passed=True, reason=f"Earnings check unavailable: {e}")


def _check_liquidity(indicators: dict, bars: list[dict]) -> FilterResult:
    """Skip if insufficient liquidity."""
    price = indicators.get("price", 0)
    avg_volume = indicators.get("avg_volume", 0)
    atr = indicators.get("atr_14", 0)

    if avg_volume > 0 and avg_volume < 300_000:
        return FilterResult(
            passed=False,
            reason=f"Avg volume {avg_volume:,.0f} < 300K (illiquid)",
        )

    if price > 0 and atr > 0:
        atr_pct = (atr / price) * 100
        if atr_pct > 8.0:
            return FilterResult(
                passed=False,
                reason=f"ATR {atr_pct:.1f}% of price — too volatile for safe entry",
            )

    if len(bars) > 0 and price > 0:
        if price < 3.0:
            return FilterResult(passed=False, reason=f"Price ${price:.2f} < $3 (penny stock filter)")
        if price > 2500:
            return FilterResult(passed=False, reason=f"Price ${price:.2f} > $2500 (position sizing broken)")

    return FilterResult(passed=True, reason="Liquidity OK")


def _check_volume_environment(indicators: dict, bars: list[dict]) -> FilterResult:
    """Skip if overall volume environment is abnormal."""
    vol_ratio = indicators.get("volume_ratio", 1.0)
    current_vol = indicators.get("current_volume", 0)
    avg_vol = indicators.get("avg_volume", 1)

    if avg_vol > 0:
        if current_vol < avg_vol * 0.3:
            return FilterResult(
                passed=False,
                reason=f"Volume {current_vol:,.0f} is 30% of avg {avg_vol:,.0f} (dead market)",
            )

    if vol_ratio > 5.0:
        return FilterResult(
            passed=False,
            reason=f"Volume spike {vol_ratio:.1f}x avg — possible news event or manipulation",
        )

    return FilterResult(passed=True, reason="Volume environment normal")


def _check_spread(indicators: dict) -> FilterResult:
    """Check bid-ask spread for abnormal width."""
    spread_pct = indicators.get("spread_pct", None)
    if spread_pct is None:
        return FilterResult(passed=True, reason="No spread data available")

    if spread_pct > 1.0:
        return FilterResult(
            passed=False,
            reason=f"Spread {spread_pct:.2f}% > 1% (abnormal)",
        )
    if spread_pct > 0.5:
        return FilterResult(
            passed=True,
            reason=f"Spread {spread_pct:.2f}% (elevated but acceptable)",
            severity="warn",
        )

    return FilterResult(passed=True, reason=f"Spread {spread_pct:.2f}% (normal)")
