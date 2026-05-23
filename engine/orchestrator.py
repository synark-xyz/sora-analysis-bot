"""
engine/orchestrator.py — Multi-market signal pipeline.

Pipeline flow:
  Market Data (us_feed | crypto_feed)
  -> Indicator Engine
  -> Market Regime Engine
  -> StrategySelector
  -> Confidence Engine
  -> Confluence Validator
  -> Signal Result

Principles:
  - Trade less, trade higher quality
  - Prefer confluence over frequency
  - Prioritize survivability
  - All confidence scores are deterministic and explainable
  - Markets: 'us' (Alpaca) or 'crypto' (CoinGecko)
"""

import math
from datetime import datetime, timezone, timedelta

from engine.strategies import StrategySelector, SignalDirection, StrategySignal
from engine.confidence import ConfidenceEngine
from engine.regime import detect_regime, RegimeResult


_confidence_engine = ConfidenceEngine()
_strategy_selector = StrategySelector()


def run_pipeline(symbol: str, market: str = 'us', timeframe: str = 'swing') -> dict | None:
    try:
        bars = _fetch_bars(symbol, market)
        if not bars or len(bars) < 20:
            return None

        indicators = _compute_indicators(symbol, bars)

        regime = detect_regime()
        strategy_result = _select_strategy(indicators, bars, regime, symbol)
        if strategy_result is None:
            return None

        strategy, signal = strategy_result

        confidence = _confidence_engine.compute(
            strategy_name=strategy.name,
            indicators=indicators,
            bars=bars,
            regime=regime,
        )

        if confidence.verdict == "REJECT":
            return _build_result(
                symbol=symbol, verdict="HOLD", confidence=confidence.total,
                strategy=strategy.name, reason=confidence.verdict,
                regime=regime.regime, indicators=indicators,
            )

        if not _validate_confluence(strategy.name, signal, indicators, regime):
            return _build_result(
                symbol=symbol, verdict="HOLD", confidence=confidence.total,
                strategy=strategy.name, reason="CONFLUENCE_REJECTED",
                regime=regime.regime, indicators=indicators,
            )

        verdict_str = signal.direction.value
        reason = _build_reason(signal, confidence)
        entry_price = indicators.get("price", 0)
        stop_loss = _compute_stop_loss(signal, entry_price, strategy.risk_params, indicators)
        take_profit = _compute_take_profit(signal, entry_price, strategy.risk_params)

        from engine.signal_gate import check_gate, compute_rr
        gate = check_gate(
            verdict=verdict_str,
            indicators=indicators,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence.total,
            regime=regime.regime,
            symbol=symbol,
            market=market,
        )

        if not gate.passed:
            result = _build_result(
                symbol=symbol, verdict="HOLD", confidence=confidence.total,
                strategy=strategy.name, reason=f"GATE_REJECT: {gate.fail_reason}",
                regime=regime.regime, indicators=indicators,
            )
            result["gate_passed"] = False
            result["gate_scorecard"] = gate.scorecard_text()
            return result

        rr = compute_rr(entry_price, stop_loss, take_profit)
        result = _build_result(
            symbol=symbol, verdict=verdict_str,
            confidence=confidence.total,
            strategy=strategy.name,
            reason=reason,
            regime=regime.regime,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence_breakdown=confidence.breakdown,
            atr=indicators.get("atr_14"),
            timeframe=timeframe,
            indicators=indicators,
        )
        result["gate_passed"] = True
        result["gate_scorecard"] = gate.scorecard_text()
        result["rr_ratio"] = rr
        return result

    except Exception as e:
        return None


def _fetch_bars(symbol: str, market: str) -> list[dict]:
    if market == "crypto":
        from data.crypto_feed import fetch_bars
    else:
        from data.us_feed import fetch_bars
    return fetch_bars(symbol)


def _compute_indicators(symbol: str, bars: list[dict]) -> dict:
    if not bars or len(bars) < 20:
        return {}

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    volumes = [b["volume"] for b in bars]
    price = closes[-1]

    indicators = {
        "price": price,
        "open": bars[-1]["open"],
        "high": highs[-1],
        "low": lows[-1],
        "volume": volumes[-1],
        "current_volume": volumes[-1],
    }

    indicators["rsi_14"] = _rsi(closes)
    macd, sig, hist = _macd(closes)
    indicators["macd"] = macd
    indicators["macd_signal"] = sig
    indicators["macd_hist"] = hist
    indicators["ema_9"] = _ema(closes, 9)
    indicators["ema_20"] = _ema(closes, 20)
    indicators["ema_50"] = _ema(closes, 50)
    indicators["atr_14"] = _atr(highs, lows, closes)

    bb_upper, bb_lower = _bollinger(closes)
    indicators["bb_upper"] = bb_upper
    indicators["bb_lower"] = bb_lower

    bb_mid = (bb_upper + bb_lower) / 2
    bb_width_val = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0
    indicators["bb_width"] = round(bb_width_val, 4)
    indicators["bb_squeeze"] = _bb_squeeze(closes)

    indicators["volume_ratio"] = round(
        volumes[-1] / (sum(volumes[-6:-1]) / 5), 2
    ) if len(volumes) >= 6 else 1.0

    indicators["avg_volume"] = sum(volumes[-21:]) / min(len(volumes), 21) if volumes else 0
    indicators["adx"] = _adx(highs, lows, closes)

    trend = _calc_trend(closes)
    indicators["trend_strength"] = round(trend * 100, 2)

    vol = _calc_volatility(closes)
    hist_vol = _calc_historical_volatility(closes)
    indicators["volatility"] = vol
    indicators["historical_volatility"] = hist_vol

    indicators["sma_200"] = _sma(closes, min(200, len(closes)))

    st_trend, st_line = _supertrend(highs, lows, closes)
    indicators["supertrend_trend"] = st_trend
    indicators["supertrend_line"] = st_line

    indicators["vwap_5"] = _vwap(closes, volumes, 5)
    indicators["vwap_20"] = _vwap(closes, volumes, 20)

    stoch_k, stoch_d = _stoch(highs, lows, closes)
    indicators["stoch_k"] = stoch_k
    indicators["stoch_d"] = stoch_d
    indicators["williams_r"] = _williams_r(highs, lows, closes)

    return indicators


def _select_strategy(
    indicators: dict, bars: list[dict], regime: RegimeResult, symbol: str
) -> tuple | None:
    result = _strategy_selector.select(regime.regime, indicators, bars)
    if result is None:
        return None
    return result


def _validate_confluence(
    strategy_name: str, signal: StrategySignal, indicators: dict, regime: RegimeResult
) -> bool:
    adx = indicators.get("adx", 0)
    rsi = indicators.get("rsi_14", 50)
    price = indicators.get("price", 0)
    ema_20 = indicators.get("ema_20")
    ema_50 = indicators.get("ema_50")
    vol_ratio = indicators.get("volume_ratio", 1.0)

    agreements = 0
    disagreements = 0

    if adx >= 25:
        agreements += 1
    else:
        disagreements += 1

    if price and ema_20 and ema_50:
        if signal.direction == SignalDirection.LONG and price > ema_20:
            agreements += 1
        elif signal.direction == SignalDirection.SHORT and price < ema_20:
            agreements += 1
        else:
            disagreements += 1
    else:
        disagreements += 1

    if signal.direction == SignalDirection.LONG and 30 <= rsi <= 80:
        agreements += 1
    elif signal.direction == SignalDirection.SHORT and 20 <= rsi <= 70:
        agreements += 1
    else:
        disagreements += 1

    if vol_ratio >= 0.5:
        agreements += 1
    else:
        disagreements += 1

    if regime.regime in _get_strategy_regimes(strategy_name):
        agreements += 1
    else:
        disagreements += 1

    total = agreements + disagreements
    alignment_ratio = agreements / total if total > 0 else 0
    return alignment_ratio >= 0.5


def _get_strategy_regimes(strategy_name: str) -> list[str]:
    mapping = {
        "ema_rsi_volume": ["BULL", "NEUTRAL"],
        "supertrend_macd": ["BULL", "VOLATILE", "NEUTRAL"],
        "bollinger_squeeze": ["BULL", "VOLATILE", "RANGING"],
        "rsi_mean_reversion": ["RANGING", "VOLATILE", "NEUTRAL"],
        "vwap_momentum": ["BULL", "NEUTRAL", "VOLATILE"],
    }
    return mapping.get(strategy_name, [])


def _compute_stop_loss(signal, entry_price: float, risk_params, indicators: dict) -> float | None:
    if signal.direction == SignalDirection.FLAT or entry_price <= 0:
        return None
    atr = indicators.get("atr_14", 0)
    if atr > 0:
        stop = entry_price - (atr * 2) if signal.direction == SignalDirection.LONG else entry_price + (atr * 2)
    else:
        stop = entry_price * (1 - risk_params.stop_loss_pct / 100) if signal.direction == SignalDirection.LONG else \
               entry_price * (1 + risk_params.stop_loss_pct / 100)
    return round(stop, 2)


def _compute_take_profit(signal, entry_price: float, risk_params) -> float | None:
    if signal.direction == SignalDirection.FLAT or entry_price <= 0:
        return None
    tp = entry_price * (1 + risk_params.take_profit_pct / 100) if signal.direction == SignalDirection.LONG else \
         entry_price * (1 - risk_params.take_profit_pct / 100)
    return round(tp, 2)


def _build_reason(signal: StrategySignal, confidence) -> str:
    return f"{signal.rationale} | Confidence: {confidence.verdict} ({confidence.total:.0f}%)"


def _build_result(
    symbol: str, verdict: str, confidence: float,
    strategy: str = "", reason: str = "",
    regime: str = "",
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    confidence_breakdown: dict | None = None,
    atr: float | None = None,
    timeframe: str = "swing",
    indicators: dict | None = None,
) -> dict:
    zone_half = atr * 0.5 if atr else 0
    entry_low = (entry_price - zone_half) if entry_price else None
    entry_high = (entry_price + zone_half) if entry_price else None

    anchor_ema = "VWAP + SMA50" if timeframe == "swing" else "SMA200 + weekly support"
    stop_mult = "1.5" if timeframe == "swing" else "2.5"

    result = {
        "symbol": symbol,
        "verdict": verdict,
        "confidence": round(confidence, 1),
        "strategy": strategy,
        "reason": reason,
        "regime": regime,
        "entry_low": round(entry_low, 2) if entry_low else None,
        "entry_high": round(entry_high, 2) if entry_high else None,
        "exit_target": round(take_profit, 2) if take_profit else None,
        "stop_loss": round(stop_loss, 2) if stop_loss else None,
        "entry_anchor": anchor_ema,
        "exit_anchor": "Resistance cluster + Fib extension",
        "stop_anchor": f"{stop_mult}× ATR below entry",
    }
    if confidence_breakdown:
        result["confidence_breakdown"] = confidence_breakdown
    if indicators:
        result["tech_conditions"] = _assess_conditions(indicators)
    return result


def _stoch(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> tuple[float, float]:
    if len(closes) < period + 1:
        return 50.0, 50.0
    recent_high = max(highs[-period:])
    recent_low = min(lows[-period:])
    if recent_high == recent_low:
        return 50.0, 50.0
    k = (closes[-1] - recent_low) / (recent_high - recent_low) * 100

    def _k_at(i: int) -> float | None:
        end = -i + 1 if i > 1 else None
        h = highs[-period - i + 1: end]
        l = lows[-period - i + 1: end]
        c = closes[-i]
        if not h or not l:
            return None
        hi, lo = max(h), min(l)
        if hi == lo:
            return None
        return (c - lo) / (hi - lo) * 100

    if len(closes) >= period + 3:
        k_vals = [_k_at(i) for i in range(1, 4)]
        valid = [v for v in k_vals if v is not None]
        d = sum(valid) / len(valid) if valid else k
    else:
        d = k
    return round(k, 1), round(d, 1)


def _williams_r(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return -50.0
    recent_high = max(highs[-period:])
    recent_low = min(lows[-period:])
    if recent_high == recent_low:
        return -50.0
    return round((recent_high - closes[-1]) / (recent_high - recent_low) * -100, 1)


def _assess_conditions(indicators: dict) -> dict:
    labels = {}

    rsi = indicators.get("rsi_14", 50)
    if rsi <= 20:
        labels["rsi"] = "severely-oversold"
    elif rsi <= 30:
        labels["rsi"] = "oversold"
    elif rsi >= 80:
        labels["rsi"] = "severely-overbought"
    elif rsi >= 70:
        labels["rsi"] = "overbought"
    else:
        labels["rsi"] = "neutral"

    stoch_k = indicators.get("stoch_k", 50)
    if stoch_k <= 10:
        labels["stoch"] = "severely-oversold"
    elif stoch_k <= 20:
        labels["stoch"] = "oversold"
    elif stoch_k >= 90:
        labels["stoch"] = "severely-overbought"
    elif stoch_k >= 80:
        labels["stoch"] = "overbought"
    else:
        labels["stoch"] = "neutral"

    wr = indicators.get("williams_r", -50)
    if wr <= -90:
        labels["williams_r"] = "severely-oversold"
    elif wr <= -80:
        labels["williams_r"] = "oversold"
    elif wr >= -10:
        labels["williams_r"] = "severely-overbought"
    elif wr >= -20:
        labels["williams_r"] = "overbought"
    else:
        labels["williams_r"] = "neutral"

    price = indicators.get("price", 0)
    bb_lower = indicators.get("bb_lower")
    bb_upper = indicators.get("bb_upper")
    if price and bb_lower and bb_upper:
        if price <= bb_lower:
            labels["bb"] = "oversold"
        elif price >= bb_upper:
            labels["bb"] = "overbought"
        else:
            labels["bb"] = "neutral"
    else:
        labels["bb"] = "neutral"

    extreme_count = sum(1 for v in labels.values() if v.startswith("severely"))
    signal_count = sum(1 for v in labels.values() if v in ("oversold", "overbought"))
    if extreme_count >= 2:
        labels["overall"] = "extreme"
    elif signal_count >= 3:
        oversold_count = sum(1 for v in labels.values() if v == "oversold")
        overbought_count = sum(1 for v in labels.values() if v == "overbought")
        if oversold_count > overbought_count:
            labels["overall"] = "oversold"
        elif overbought_count > oversold_count:
            labels["overall"] = "overbought"
        else:
            labels["overall"] = "mixed"
    else:
        labels["overall"] = "neutral"

    return labels


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = 0, 0
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _ema(closes: list[float], period: int) -> float:
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    multiplier = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def _sma(closes: list[float], period: int) -> float:
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    return sum(closes[-period:]) / period


def _macd(closes: list[float]):
    if len(closes) < 26:
        return 0.0, 0.0, 0.0
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = ema12 - ema26
    signal = _ema(closes[-9:], 9) if len(closes) >= 9 else ema26
    return macd, signal, macd - signal


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(highs) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    return sum(trs[-period:]) / period


def _bollinger(closes: list[float], period: int = 20):
    if len(closes) < period:
        return closes[-1] if closes else 0.0, closes[-1] if closes else 0.0
    sma = sum(closes[-period:]) / period
    variance = sum((c - sma) ** 2 for c in closes[-period:]) / period
    std = variance ** 0.5
    return sma + 2 * std, sma - 2 * std


def _adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 0.0
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(closes)):
        h_diff = highs[i] - highs[i - 1]
        l_diff = lows[i - 1] - lows[i]
        plus_dm.append(h_diff if h_diff > l_diff and h_diff > 0 else 0)
        minus_dm.append(l_diff if l_diff > h_diff and l_diff > 0 else 0)
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
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


def _supertrend(highs: list[float], lows: list[float], closes: list[float],
                period: int = 10, multiplier: float = 3.0) -> tuple[str | None, float | None]:
    if len(closes) < period + 1:
        return None, None

    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)

    atr = sum(trs[-period:]) / period
    hl2 = [(highs[i] + lows[i]) / 2 for i in range(len(closes))]
    upper_band = hl2[-1] + multiplier * atr
    lower_band = hl2[-1] - multiplier * atr

    trend = "up"
    supertrend_val = lower_band

    for i in range(max(period, 1), len(closes)):
        prev_close = closes[i - 1]
        curr_hl2 = hl2[i]
        curr_upper = curr_hl2 + multiplier * atr
        curr_lower = curr_hl2 - multiplier * atr

        if prev_close <= supertrend_val:
            trend = "up" if closes[i] > curr_upper else "down"
        else:
            trend = "down" if closes[i] < curr_lower else "up"

        supertrend_val = curr_lower if trend == "up" else curr_upper

    return trend, round(supertrend_val, 2) if supertrend_val else None


def _vwap(closes: list[float], volumes: list[int], period: int = 20) -> float | None:
    if len(closes) < period or len(volumes) < period:
        return None
    recent_closes = closes[-period:]
    recent_vols = volumes[-period:]
    tp_vol = sum(c * v for c, v in zip(recent_closes, recent_vols))
    total_vol = sum(recent_vols)
    return tp_vol / total_vol if total_vol > 0 else None


def _bb_squeeze(closes: list[float], period: int = 20, lookback: int = 50) -> bool:
    if len(closes) < max(period + 1, lookback + period):
        return False
    widths = []
    for i in range(lookback, len(closes)):
        segment = closes[i - period:i]
        sma = sum(segment) / period
        variance = sum((c - sma) ** 2 for c in segment) / period
        std = variance ** 0.5
        mid = sma
        upper = sma + 2 * std
        lower = sma - 2 * std
        width = (upper - lower) / mid if mid > 0 else 0
        widths.append(width)

    if len(widths) < 2:
        return False

    current_width = widths[-1]
    min_width = min(widths[:-1])
    return current_width <= min_width * 1.05


def _calc_trend(prices: list[float], window: int = 50) -> float:
    if len(prices) < window:
        window = len(prices)
    recent = prices[-window:]
    n = len(recent)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return (num / den) / y_mean


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
    return math.sqrt(variance) * math.sqrt(252)


def _calc_historical_volatility(prices: list[float], window: int = 20) -> float:
    if len(prices) < window * 2:
        return 0.15
    vols = []
    for i in range(window, len(prices)):
        seg = prices[i - window:i]
        v = _calc_volatility(seg)
        vols.append(v)
    return sum(vols) / len(vols) if vols else 0.15


_CRYPTO_SET = {"BTC", "ETH", "SOL", "BNB", "AVAX", "LINK", "DOT", "MATIC", "ADA", "XRP", "DOGE"}


def _detect_market(symbol: str) -> str:
    return "crypto" if symbol in _CRYPTO_SET else "us"


def _empty_result(symbol: str, market: str) -> dict:
    return {
        "symbol": symbol,
        "market": market,
        "verdict": "HOLD",
        "confidence": 0,
        "reason": "Insufficient data or no signal",
        "strategy": "N/A",
        "regime": "N/A",
    }


async def _run_full_analysis(symbol: str, market: str) -> dict:
    try:
        from llm.analyst import analyze_full

        bars = _fetch_bars(symbol, market)
        if not bars or len(bars) < 20:
            return {}
        indicators = _compute_indicators(symbol, bars)
        regime = detect_regime()

        news = ""
        try:
            from analysis.news import fetch_news
            news_items = fetch_news(symbol)
            news = "; ".join(n.get("title", "") for n in news_items[:5])
        except Exception:
            pass

        fundamentals = ""
        try:
            from analysis.fundamental import get_fundamentals
            fundamentals = str(get_fundamentals(symbol))
        except Exception:
            pass

        wiki_context = ""
        try:
            from memory.wiki import query_wiki
            wiki_context = await query_wiki(symbol)
        except Exception:
            pass

        return await analyze_full(
            symbol=symbol,
            indicators=indicators,
            regime={"regime": regime.regime, "adx": indicators.get("adx", 0)},
            news=news,
            fundamentals=fundamentals,
            wiki_context=wiki_context,
        )
    except ImportError:
        return {}


async def _run_moomoo_analysis(symbol: str, market: str) -> dict:
    try:
        from llm.analyst import analyze_moomoo

        bars = _fetch_bars(symbol, market)
        if not bars or len(bars) < 20:
            return {}
        indicators = _compute_indicators(symbol, bars)

        regime = None
        try:
            from engine.regime import detect_regime
            regime = detect_regime(bars, market)
        except Exception:
            pass

        news = ""
        try:
            from analysis.news import fetch_news
            news_items = fetch_news(symbol)
            news = "; ".join(n.get("title", "") for n in news_items[:5])
        except Exception:
            pass

        fundamentals = ""
        try:
            from analysis.fundamental import get_fundamentals
            fundamentals = str(get_fundamentals(symbol))
        except Exception:
            pass

        valuation = ""
        try:
            from analysis.fundamental import get_valuation
            valuation = str(get_valuation(symbol))
        except Exception:
            pass

        wiki_context = ""
        try:
            from memory.wiki import query_wiki
            wiki_context = await query_wiki(symbol)
        except Exception:
            pass

        regime_dict = {"regime": regime.regime if regime else "N/A", "adx": indicators.get("adx", 0)}

        return await analyze_moomoo(
            symbol=symbol,
            indicators=indicators,
            regime=regime_dict,
            news=news,
            fundamentals=fundamentals,
            valuation=valuation,
            wiki_context=wiki_context,
        )
    except ImportError:
        return {}


async def run_analysis(
    symbol: str,
    full: bool = False,
    swing: bool = False,
    long_term: bool = False,
    moomoo: bool = False,
) -> dict:
    import asyncio
    market = _detect_market(symbol)
    timeframe = "long" if long_term else "swing"

    result = await asyncio.to_thread(run_pipeline, symbol, market, timeframe)
    if result is None:
        return _empty_result(symbol, market)

    result["market"] = market
    result["timeframe"] = "Position (weeks–months)" if long_term else "Swing (5–12 days)"

    if moomoo:
        llm_result = await _run_moomoo_analysis(symbol, market)
        if llm_result:
            result.update(llm_result)
            result["timeframe"] = "Moomoo (Full Framework)"
    elif full:
        llm_result = await _run_full_analysis(symbol, market)
        if llm_result:
            result["llm_report"] = True
            bull = llm_result.pop("bull_thesis", "")
            bear = llm_result.pop("bear_thesis", "")
            result.update(llm_result)
            if bull:
                result["bull_thesis"] = bull
            if bear:
                result["bear_thesis"] = bear
            result["timeframe"] = "Full (Multi-Agent)"

    return result


async def get_bars(symbol: str) -> list[dict]:
    import asyncio
    return await asyncio.to_thread(_fetch_bars, symbol, _detect_market(symbol))


def quick_score(symbol: str, market: str | None = None) -> dict:
    if market is None:
        market = _detect_market(symbol)
    bars = _fetch_bars(symbol, market)
    if not bars or len(bars) < 20:
        return {"symbol": symbol, "score": 0}

    ind = _compute_indicators(symbol, bars)

    score = 50.0
    reasons = []

    rsi = ind.get("rsi_14", 50)
    if rsi > 70 or rsi < 30:
        score += 15
        reasons.append(f"RSI={rsi:.0f} extreme")
    elif 40 <= rsi <= 60:
        score += 5
        reasons.append(f"RSI={rsi:.0f} neutral")
    else:
        reasons.append(f"RSI={rsi:.0f}")

    adx = ind.get("adx", 0)
    if adx >= 25:
        score += 15
        reasons.append(f"ADX={adx:.0f} trending")
    else:
        reasons.append(f"ADX={adx:.0f} weak")

    price = ind.get("price", 0)
    ema20 = ind.get("ema_20")
    ema50 = ind.get("ema_50")
    if price and ema20 and ema50:
        if price > ema20 > ema50:
            score += 10
            reasons.append("bullish stack")
        elif price < ema20 < ema50:
            score += 10
            reasons.append("bearish stack")
        else:
            score -= 5
            reasons.append("mixed EMAs")

    vol_ratio = ind.get("volume_ratio", 1.0)
    if vol_ratio > 1.5:
        score += 10
        reasons.append(f"vol {vol_ratio:.1f}x")
    elif vol_ratio < 0.5:
        score -= 10
        reasons.append(f"vol {vol_ratio:.1f}x low")

    atr = ind.get("atr_14", 0)
    if price and atr:
        atr_pct = atr / price * 100
        if 0.5 <= atr_pct <= 4.0:
            score += 10
            reasons.append(f"ATR {atr_pct:.1f}% healthy")
        else:
            score -= 5
            reasons.append(f"ATR {atr_pct:.1f}%")

    score = max(0, min(100, int(round(score))))
    return {"symbol": symbol, "score": score, "reasons": reasons}
