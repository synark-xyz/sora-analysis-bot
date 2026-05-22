"""
analysis/sentiment.py — Sentiment analysis.

On-demand sentiment fetcher. Crypto uses CryptoPanic RSS.
US market provides a basic interface — extend with Reddit or other sources.
"""

from analysis.news import fetch_news


SENTIMENT_SIGNALS = {
    "bullish": ["surge", "rally", "bullish", "upgrade", "outperform", "beat", "growth", "positive"],
    "bearish": ["crash", "decline", "downgrade", "sell", "underperform", "miss", "negative", "warning"],
}


def get_sentiment(symbol: str, market: str = "us") -> dict:
    source = "cryptopanic" if market == "crypto" else "yahoo"
    articles = fetch_news(symbol, source=source)

    if not articles:
        return {"overall": "neutral", "score": 0.0, "signals": []}

    bullish_count = 0
    bearish_count = 0
    signals = []

    for a in articles:
        title = (a.get("title") or "").lower()
        summary = (a.get("summary") or "").lower()
        text = f"{title} {summary}"

        bull_hits = sum(1 for w in SENTIMENT_SIGNALS["bullish"] if w in text)
        bear_hits = sum(1 for w in SENTIMENT_SIGNALS["bearish"] if w in text)

        if bull_hits > bear_hits:
            bullish_count += 1
            signals.append({"headline": a["title"], "sentiment": "bullish"})
        elif bear_hits > bull_hits:
            bearish_count += 1
            signals.append({"headline": a["title"], "sentiment": "bearish"})

    total = bullish_count + bearish_count
    if total == 0:
        return {"overall": "neutral", "score": 0.0, "signals": signals}

    score = (bullish_count - bearish_count) / total
    score = max(-1.0, min(1.0, score))

    if score > 0.3:
        overall = "bullish"
    elif score < -0.3:
        overall = "bearish"
    else:
        overall = "neutral"

    return {
        "overall": overall,
        "score": round(score, 3),
        "signals": signals[:10],
    }
