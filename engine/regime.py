"""
engine/regime.py

Market regime detection with confidence scoring.
Fetches SPY daily bars via Alpaca (US stocks) or BTC data via CoinGecko (crypto)
and runs ADX/trend/volatility analysis.
"""

import os
import math
import time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from log import get_logger

log = get_logger("engine.regime", "REGME")


REGIME_LABELS = {
    "BULL":     {"label": "Bull Market",    "color": "#00C896", "emoji": "🐂", "desc": "Strong uptrend, high ADX, rising prices"},
    "BEAR":     {"label": "Bear Market",    "color": "#E84848", "emoji": "🐻", "desc": "Strong downtrend, high ADX, falling prices"},
    "NEUTRAL":  {"label": "Neutral",        "color": "#94A3B8", "emoji": "➡️", "desc": "Mixed signals, no clear direction"},
    "RANGING":  {"label": "Ranging",        "color": "#F59E0B", "emoji": "📊", "desc": "Low ADX, price oscillating in a range"},
    "VOLATILE": {"label": "Volatile",       "color": "#EF4444", "emoji": "🌊", "desc": "High volatility, wide price swings"},
}


@dataclass
class RegimeResult:
    regime: str
    confidence: float
    adx: float
    trend_strength: float
    volatility: float
    historical_vol: float
    description: str
    color: str
    emoji: str


def fetch_spy_bars(days: int = 90, market: str = "us") -> list[dict]:
    """Fetch SPY daily OHLCV bars from Alpaca (market='us') or BTC from CoinGecko (market='crypto')."""
    if market == "crypto":
        return fetch_crypto_bars(days)
    return _fetch_alpaca_spy(days)


def _fetch_alpaca_spy(days: int = 90) -> list[dict]:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.enums import DataFeed

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        return _get_mock_bars(days)

    try:
        client = StockHistoricalDataClient(api_key, secret_key)
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        req = StockBarsRequest(
            symbol_or_symbols="SPY",
            timeframe=TimeFrame(1, TimeFrameUnit.Day),
            start=start,
            end=now,
            limit=200,
            feed=DataFeed.IEX,
        )
        t0 = time.monotonic()
        raw = client.get_stock_bars(req)
        elapsed = time.monotonic() - t0
        bars_data = raw.data.get("SPY", [])
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
        log.http("Alpaca SPY  %d bars  %.1fs", len(bars), elapsed)
        if bars:
            return bars
    except Exception:
        pass
    return _get_mock_bars(days)


def fetch_crypto_bars(days: int = 90) -> list[dict]:
    """Fetch BTC/USD daily OHLCV bars from CoinGecko (free API, no key needed)."""
    try:
        import requests
        vs_currency = "usd"
        url = (
            f"https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"
            f"?vs_currency={vs_currency}&days={days}"
        )
        t0 = time.monotonic()
        resp = requests.get(url, timeout=15)
        elapsed = time.monotonic() - t0
        if resp.status_code != 200:
            return _get_mock_bars(days)
        data = resp.json()
        bars = []
        for entry in data:
            timestamp_ms, o, h, l, c, *_ = entry
            bars.append({
                "time": int(timestamp_ms / 1000),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": 0,
            })
        log.http("CoinGecko BTC  %d bars  %.1fs", len(bars), elapsed)
        if len(bars) > 1:
            return bars
    except Exception:
        pass
    return _get_mock_bars(days)


def _get_mock_bars(days: int = 90) -> list[dict]:
    """Generate mock bars for fallback when data sources are unavailable."""
    import random
    random.seed(42)
    now = datetime.now(timezone.utc)
    price = 500.0
    bars = []
    for i in range(min(days, 90)):
        change = random.gauss(0, 1.5)
        price += change
        t = int((now - timedelta(days=(days - i))).timestamp())
        bars.append({
            "time": t,
            "open": round(price - change, 2),
            "high": round(price + abs(change) + random.random(), 2),
            "low": round(price - abs(change) - random.random(), 2),
            "close": round(price, 2),
            "volume": int(random.gauss(50_000_000, 10_000_000)),
        })
    return bars


def detect_regime(bars: list[dict] | None = None, market: str = "us") -> RegimeResult:
    """
    Detect market regime from price bars with confidence scoring.

    Uses ADX (>25 = trending), trend slope direction, and volatility
    relative to historical baseline to classify:
      BULL, BEAR, NEUTRAL, RANGING, or VOLATILE

    market='us' uses SPY data; market='crypto' uses BTC data.
    """
    if not bars or len(bars) < 30:
        bars = fetch_spy_bars(market=market)

    prices = [b["close"] for b in bars]
    if len(prices) < 20:
        return RegimeResult("NEUTRAL", 0, 0, 0, 0, 0, "Insufficient data", "#94A3B8", "➡️")

    # Calculate indicators
    volatility = _calc_volatility(prices)
    hist_vol = _calc_historical_volatility(prices) or 0.15
    trend = _calc_trend(prices)
    adx = _calc_adx(prices)

    # Confidence: how clear the signal is
    confidence = 0.5

    # Regime classification
    if adx > 30:
        confidence = 0.7 + min(0.25, (adx - 30) / 100)
        if trend > 0.05:
            regime = "BULL"
        elif trend < -0.05:
            regime = "BEAR"
        else:
            regime = "NEUTRAL"
    elif adx > 25:
        confidence = 0.6
        if trend > 0.08:
            regime = "BULL"
        elif trend < -0.08:
            regime = "BEAR"
        else:
            regime = "NEUTRAL"
    else:
        # Low ADX — ranging or neutral
        if volatility > hist_vol * 1.5:
            regime = "VOLATILE"
            confidence = min(0.8, 0.5 + (volatility / hist_vol - 1.5))
        else:
            regime = "RANGING"
            confidence = 0.5 + abs(trend) * 2 if abs(trend) > 0.03 else 0.4

    confidence = round(min(0.95, confidence), 2)
    info = REGIME_LABELS.get(regime, REGIME_LABELS["NEUTRAL"])

    return RegimeResult(
        regime=regime,
        confidence=confidence,
        adx=round(adx, 1),
        trend_strength=round(trend * 100, 2),
        volatility=round(volatility, 4),
        historical_vol=round(hist_vol, 4),
        description=info["desc"],
        color=info["color"],
        emoji=info["emoji"],
    )


def _calc_volatility(prices: list[float]) -> float:
    if len(prices) < 2:
        return 0.0
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] != 0:
            r = math.log(prices[i] / prices[i - 1])
            returns.append(r)
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return math.sqrt(variance) * math.sqrt(252) * 100 / 100


def _calc_historical_volatility(prices: list[float], window: int = 20) -> float:
    if len(prices) < window * 2:
        return 0.15
    vols = []
    for i in range(window, len(prices)):
        seg = prices[i - window: i]
        v = _calc_volatility(seg)
        vols.append(v)
    return sum(vols) / len(vols) if vols else 0.15


def _calc_trend(prices: list[float], window: int = 50) -> float:
    if len(prices) < window:
        window = len(prices)
    recent = prices[-window:]
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return (num / den) / y_mean


def _calc_adx(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 0.0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        plus_dm.append(diff if diff > 0 else 0)
        minus_dm.append(-diff if diff < 0 else 0)
        trs.append(max(prices[i] - prices[i - 1], abs(prices[i] - prices[i - 1])))
    if len(trs) < period:
        return 0.0
    atr = sum(trs[-period:]) / period
    if atr == 0:
        return 0.0
    pdi = 100 * (sum(plus_dm[-period:]) / period) / atr
    mdi = 100 * (sum(minus_dm[-period:]) / period) / atr
    di_sum = pdi + mdi
    if di_sum == 0:
        return 0.0
    return 100 * abs(pdi - mdi) / di_sum


def get_regime_for_display(market: str = "us") -> dict:
    """Return a dict suitable for JSON serialization (for API)."""
    result = detect_regime(market=market)
    return {
        "regime": result.regime,
        "label": REGIME_LABELS.get(result.regime, REGIME_LABELS["NEUTRAL"])["label"],
        "confidence": result.confidence,
        "adx": result.adx,
        "trend_strength": result.trend_strength,
        "volatility": result.volatility,
        "historical_volatility": result.historical_vol,
        "description": result.description,
        "color": result.color,
        "emoji": result.emoji,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }
