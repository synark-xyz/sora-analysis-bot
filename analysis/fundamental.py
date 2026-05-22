"""
analysis/fundamental.py — Fundamentals from Financial Modeling Prep (FMP).

Free tier provides P/E, revenue growth, insider trading, institutional ownership.
Returns empty dict on error — never crashes.
"""

import os
import time
import requests

from log import get_logger

log = get_logger("analysis.fundamental", "FUND")

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
        t0 = time.monotonic()
        resp = requests.get(url, params={"apikey": api_key}, timeout=10)
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        data = resp.json()
        log.http("FMP profile %s  %.1fs", symbol, elapsed)
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
        t0 = time.monotonic()
        resp = requests.get(url, params={"apikey": api_key, "limit": 10}, timeout=10)
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        data = resp.json()
        log.http("FMP insider %s  %.1fs", symbol, elapsed)
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
        t0 = time.monotonic()
        resp = requests.get(url, params={"apikey": api_key}, timeout=10)
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        data = resp.json()
        log.http("FMP institutional %s  %.1fs", symbol, elapsed)
        if not data:
            return None
        total = sum(h.get("shares", 0) for h in data)
        return total
    except Exception:
        return None


def get_valuation(symbol: str) -> dict:
    """Fetch valuation metrics from FMP — P/B, P/S, PEG, EV/EBITDA, ROE, ROA, analyst estimates.
    Returns {} on error or missing API key — never crashes."""
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        return {}

    result = {}

    try:
        url = f"{FMP_BASE}/key-metrics/{symbol}"
        t0 = time.monotonic()
        resp = requests.get(url, params={"apikey": api_key, "limit": 1}, timeout=10)
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        data = resp.json()
        log.http("FMP key-metrics %s  %.1fs", symbol, elapsed)
        if data:
            m = data[0]
            result["pb_ratio"] = m.get("pbRatio")
            result["ps_ratio"] = m.get("psRatio")
            result["peg_ratio"] = m.get("pegRatio")
            result["ev_to_ebitda"] = m.get("enterpriseValueOverEBITDA")
            result["roe"] = m.get("roe") or m.get("returnOnEquity")
            result["roa"] = m.get("roa") or m.get("returnOnAssets")
            result["current_ratio"] = m.get("currentRatio")
            result["debt_to_equity"] = m.get("debtToEquity")
            result["dividend_yield"] = m.get("dividendYield")
            result["book_value_per_share"] = m.get("bookValuePerShare")
    except Exception:
        pass

    try:
        url = f"{FMP_BASE}/analyst-estimates/{symbol}"
        t0 = time.monotonic()
        resp = requests.get(url, params={"apikey": api_key, "limit": 1}, timeout=10)
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        data = resp.json()
        log.http("FMP analyst-est %s  %.1fs", symbol, elapsed)
        if data:
            e = data[0]
            result["estimated_eps_current"] = e.get("estimatedEpsCurrentYear")
            result["estimated_eps_next"] = e.get("estimatedEpsNextYear")
            result["estimated_revenue_current"] = e.get("estimatedRevenueCurrentYear")
            result["estimated_revenue_next"] = e.get("estimatedRevenueNextYear")
            result["number_analysts"] = e.get("numberAnalystEstimates")
    except Exception:
        pass

    return {k: v for k, v in result.items() if v is not None}
