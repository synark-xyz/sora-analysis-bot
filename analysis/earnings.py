"""
Earnings proximity guard.
Returns days until next earnings and a HIGH/LOW risk flag.
Uses yfinance Ticker.calendar — falls back gracefully if unavailable.
"""
from datetime import datetime, timezone
from log import get_logger

log = get_logger(__name__)

EARNINGS_RISK_DAYS = 5  # within N days = HIGH risk


def _fetch_earnings_date(symbol: str) -> datetime | None:
    """Fetch next earnings date via yfinance. Returns UTC datetime or None."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        cal = ticker.calendar
        if cal is None:
            return None
        # calendar is a dict with 'Earnings Date' key (list of timestamps)
        dates = cal.get("Earnings Date", [])
        if not dates:
            return None
        # Take the first upcoming date
        now = datetime.now(timezone.utc)
        for d in dates:
            # yfinance returns Timestamp objects
            try:
                dt = d.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= now:
                    return dt
            except Exception:
                continue
        return None
    except Exception as e:
        log.debug(f"Earnings fetch failed for {symbol}: {e}")
        return None


def days_to_earnings(symbol: str) -> int | None:
    """
    Return number of calendar days until next earnings.
    Returns None if earnings date is unavailable.
    """
    dt = _fetch_earnings_date(symbol)
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0, (dt - now).days)


def earnings_risk_flag(symbol: str) -> str:
    """
    Return 'HIGH' if earnings within EARNINGS_RISK_DAYS, else 'LOW'.
    Crypto symbols always return 'LOW' (no earnings).
    """
    days = days_to_earnings(symbol)
    if days is None:
        return "LOW"
    return "HIGH" if days <= EARNINGS_RISK_DAYS else "LOW"
