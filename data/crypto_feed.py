"""
data/crypto_feed.py — Cryptocurrency OHLCV feed via CoinGecko free API.

No API key required. Rate limit: ~30 req/min on free tier.
Returns same dict format as us_feed.py for pipeline compatibility.
"""

import requests

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "DOT": "polkadot",
    "MATIC": "polygon",
    "ADA": "cardano",
    "XRP": "ripple",
}


def fetch_bars(symbol: str, days: int = 90) -> list[dict]:
    coin_id = COINGECKO_IDS.get(symbol.upper())
    if not coin_id:
        return _mock_bars()

    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        resp = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "time": int(c[0] // 1000),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": 0,
            }
            for c in data
        ]
    except Exception:
        return _mock_bars()


def _mock_bars() -> list[dict]:
    return []
