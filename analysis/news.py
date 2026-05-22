"""
analysis/news.py — News headline fetcher.

Sources:
  - Yahoo Finance RSS (free, no key) for US equities
  - CryptoPanic RSS (free, no key) for crypto
"""

import requests
from xml.etree import ElementTree
from datetime import datetime


YAHOO_FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
CRYPTO_FEED = "https://cryptopanic.com/api/v1/static/feeds/news.xml"


def fetch_news(symbol: str, source: str = "yahoo") -> list[dict]:
    if source == "cryptopanic":
        return _fetch_cryptopanic()

    url = YAHOO_FEED.format(symbol=symbol.upper())
    try:
        resp = requests.get(url, timeout=10)
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
        return items
    except Exception:
        return []


def _fetch_cryptopanic() -> list[dict]:
    try:
        resp = requests.get(CRYPTO_FEED, timeout=10)
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
        return items
    except Exception:
        return []
