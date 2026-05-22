"""
analysis/fundamental.py — Fundamentals from Financial Modeling Prep (FMP).

Free tier provides P/E, revenue growth, insider trading, institutional ownership.
Returns empty dict on error — never crashes.
"""

import os
import requests

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def get_fundamentals(symbol: str) -> dict:
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        return {}

    result = {}

    profile = _fetch_profile(symbol, api_key)
    if profile:
        result.update(profile)

    insider = _fetch_insider(symbol, api_key)
    if insider:
        result["insider_activity"] = insider

    institutional = _fetch_institutional(symbol, api_key)
    if institutional is not None:
        result["institutional_ownership"] = institutional

    return result


def _fetch_profile(symbol: str, api_key: str) -> dict | None:
    try:
        url = f"{FMP_BASE}/profile/{symbol}"
        resp = requests.get(url, params={"apikey": api_key}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        p = data[0]
        return {
            "pe_ratio": p.get("peRatio"),
            "revenue_growth": p.get("revenueGrowth"),
            "market_cap": p.get("mktCap"),
            "sector": p.get("sector"),
            "industry": p.get("industry"),
        }
    except Exception:
        return None


def _fetch_insider(symbol: str, api_key: str) -> list[dict] | None:
    try:
        url = f"{FMP_BASE}/insider-trading/{symbol}"
        resp = requests.get(url, params={"apikey": api_key, "limit": 10}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return [
            {
                "date": t.get("transactionDate", ""),
                "type": t.get("transactionType", ""),
                "shares": t.get("securitiesTransacted", 0),
                "price": t.get("price", 0),
            }
            for t in data[:10]
        ]
    except Exception:
        return None


def _fetch_institutional(symbol: str, api_key: str) -> float | None:
    try:
        url = f"{FMP_BASE}/institutional-holder/{symbol}"
        resp = requests.get(url, params={"apikey": api_key}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        total = sum(h.get("shares", 0) for h in data)
        return total
    except Exception:
        return None
