"""
analysis/news.py — News headline fetcher.

Sources:
  - Yahoo Finance RSS (free, no key) for US equities
  - CryptoPanic RSS (free, no key) for crypto
"""

import time
import requests
import defusedxml.ElementTree as ElementTree
from datetime import datetime

from log import get_logger

log = get_logger("analysis.news", "NEWS")

YAHOO_FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
CRYPTO_FEED = "https://cryptopanic.com/api/v1/static/feeds/news.xml"


def fetch_news(symbol: str, source: str = "yahoo") -> list[dict]:
    if source == "cryptopanic":
        return _fetch_cryptopanic()

    # Try yfinance first — more reliable than Yahoo RSS
    items = _fetch_yfinance(symbol)
    if items:
        return items

    # Fallback: Yahoo RSS
    url = YAHOO_FEED.format(symbol=symbol.upper())
    try:
        t0 = time.monotonic()
        resp = requests.get(url, timeout=10)
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "")
            pub_date_str = item.findtext("pubDate", "")

            pub_date = None
            try:
                pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
            except (ValueError, TypeError):
                pass

            items.append({
                "title": title,
                "summary": description,
                "url": link,
                "published_at": pub_date.isoformat() if pub_date else None,
            })
        log.http("Yahoo RSS %s  %d items  %.1fs", symbol, len(items), elapsed)
        return items
    except Exception:
        return []


def _fetch_yfinance(symbol: str) -> list[dict]:
    try:
        import yfinance as yf
        t0 = time.monotonic()
        ticker = yf.Ticker(symbol.upper())
        raw = ticker.news or []
        elapsed = time.monotonic() - t0
        items = []
        for a in raw:
            content = a.get("content", {})
            title = content.get("title", "")
            summary = content.get("summary", "")
            pub_date = content.get("pubDate", "")
            if not title:
                continue
            items.append({
                "title": title,
                "summary": summary,
                "url": "",
                "published_at": pub_date[:10] if pub_date else None,
            })
        log.http("yfinance news %s  %d items  %.1fs", symbol, len(items), elapsed)
        return items
    except Exception as e:
        log.error("yfinance news failed for %s: %s", symbol, e)
        return []


def _fetch_cryptopanic() -> list[dict]:
    try:
        t0 = time.monotonic()
        resp = requests.get(CRYPTO_FEED, timeout=10)
        elapsed = time.monotonic() - t0
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "")
            pub_date_str = item.findtext("pubDate", "")

            pub_date = None
            try:
                pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
            except (ValueError, TypeError):
                pass

            items.append({
                "title": title,
                "summary": description,
                "url": link,
                "published_at": pub_date.isoformat() if pub_date else None,
            })
        log.http("CryptoPanic  %d items  %.1fs", len(items), elapsed)
        return items
    except Exception:
        return []
