"""
data/us_feed.py — US equities OHLCV feed via Alpaca.

Fetches daily bars for NASDAQ/NYSE symbols.
Falls back to empty bars if Alpaca is unavailable.
"""

import os
from datetime import datetime, timezone, timedelta


def fetch_bars(symbol: str, days: int = 90) -> list[dict]:
    api_key = os.getenv("ALPACA_API_KEY", "")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "")
    if not api_key or not secret_key:
        return _mock_bars()

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.enums import DataFeed

        client = StockHistoricalDataClient(api_key, secret_key)
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        req = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame(1, TimeFrameUnit.Day),
            start=start,
            end=now,
            limit=500,
            feed=DataFeed.IEX,
        )
        raw = client.get_stock_bars(req)
        bars_data = raw.data.get(symbol, [])
        bars = [
            {
                "time": int(b.timestamp.timestamp()),
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": int(b.volume),
            }
            for b in bars_data
        ]
        if bars:
            return bars
    except Exception:
        pass

    return _mock_bars()


def _mock_bars() -> list[dict]:
    return []
