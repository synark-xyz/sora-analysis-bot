"""
data/crypto_feed.py — Cryptocurrency OHLCV feed via Binance public API.

No API key required. Real-time data, no meaningful rate limit for public endpoints.
Returns same dict format as us_feed.py for pipeline compatibility.
"""

import time
import requests

from log import get_logger

log = get_logger("data.crypto_feed", "DATA")

BINANCE_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "AVAX": "AVAXUSDT",
    "LINK": "LINKUSDT",
    "DOT": "DOTUSDT",
    "MATIC": "MATICUSDT",
    "ADA": "ADAUSDT",
    "XRP": "XRPUSDT",
}


def fetch_bars(symbol: str, days: int = 90) -> list[dict]:
    pair = BINANCE_SYMBOLS.get(symbol.upper())
    if not pair:
        return []

    try:
        t0 = time.monotonic()
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": pair, "interval": "1d", "limit": days},
            timeout=15,
        )
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        data = resp.json()
        log.http("Binance %s  %d bars  %.1fs", symbol, len(data), elapsed)
        return [
            {
                "time": int(c[0] // 1000),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            }
            for c in data
        ]
    except Exception as e:
        log.error("Binance fetch failed for %s: %s", symbol, e)
        return []
