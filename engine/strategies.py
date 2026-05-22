"""
engine/strategies.py — 5 official built-in strategies.

Design principles (in order of importance):
  1. Robustness — works across symbols and timeframes
  2. Low drawdown — tight stops, conservative sizing
  3. Consistency — repeatable rules, no curve-fitting
  4. Realistic execution — only publicly available data
  5. Adaptability — regime-aware, volatility-adjusted
"""

from dataclasses import dataclass
from enum import Enum


class SignalDirection(Enum):
    LONG = "BUY"
    SHORT = "SELL"
    FLAT = "HOLD"


@dataclass
class StrategySignal:
    direction: SignalDirection
    confidence_contribution: float
    rationale: str
    indicators_used: dict


@dataclass
class RiskParams:
    max_position_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_days: int
    trailing_stop: bool = False


class Strategy:
    name: str = ""
    description: str = ""
    category: str = ""
    difficulty: str = ""
    compatible_regimes: list[str] = None
    risk_params: RiskParams = None
    min_confidence: float = 35.0

    def evaluate(self, indicators: dict, bars: list[dict], regime: str) -> StrategySignal | None:
        raise NotImplementedError


# ─── Strategy 1: EMA + RSI + Volume (Trend / Easy) ──────────────────────────


class EMARSIVolume(Strategy):
    name = "ema_rsi_volume"
    description = "Trend-following strategy using EMA alignment, RSI momentum, and volume confirmation"
    category = "Trend"
    difficulty = "Easy"
    compatible_regimes = ["BULL", "NEUTRAL"]
    risk_params = RiskParams(
        max_position_pct=7.0,
        stop_loss_pct=6.0,
        take_profit_pct=12.0,
        max_holding_days=25,
        trailing_stop=True,
    )
    min_confidence = 35.0

    def evaluate(self, indicators: dict, bars: list[dict], regime: str) -> StrategySignal | None:
        price = indicators.get("price", 0)
        ema_20 = indicators.get("ema_20")
        ema_50 = indicators.get("ema_50")
        ema_9 = indicators.get("ema_9")
        rsi = indicators.get("rsi_14", 50)
        vol_ratio = indicators.get("volume_ratio", 1.0)
        adx = indicators.get("adx", 0)

        if not all([ema_20, ema_50, price]):
            return None

        conditions_met = 0
        total_checks = 0

        total_checks += 1
        if price > ema_20 and price > ema_50:
            conditions_met += 1

        total_checks += 1
        if ema_20 > ema_50:
            conditions_met += 1

        total_checks += 1
        if 50 <= rsi <= 75:
            conditions_met += 1

        total_checks += 1
        if vol_ratio >= 0.8:
            conditions_met += 1

        total_checks += 1
        if adx >= 20:
            conditions_met += 1

        total_checks += 1
        if ema_9 and price > ema_9:
            conditions_met += 1

        score = (conditions_met / total_checks) * 100 if total_checks else 0

        if conditions_met < 4:
            return None

        return StrategySignal(
            direction=SignalDirection.LONG,
            confidence_contribution=score,
            rationale=f"EMA+RSI+Vol: {conditions_met}/{total_checks} cond. "
                      f"Price=${price:.2f} > EMA20=${ema_20:.2f} > EMA50=${ema_50:.2f}, "
                      f"RSI={rsi:.1f}, Vol={vol_ratio:.1f}x",
            indicators_used={
                "price": price, "ema_20": ema_20, "ema_50": ema_50,
                "rsi": rsi, "vol_ratio": vol_ratio, "adx": adx,
                "conditions_met": conditions_met, "total_checks": total_checks,
            },
        )


# ─── Strategy 2: Supertrend + MACD (Trend / Medium) ─────────────────────────


class SupertrendMACD(Strategy):
    name = "supertrend_macd"
    description = "Trend-following strategy using Supertrend direction and MACD crossover confirmation"
    category = "Trend"
    difficulty = "Medium"
    compatible_regimes = ["BULL", "VOLATILE", "NEUTRAL"]
    risk_params = RiskParams(
        max_position_pct=6.0,
        stop_loss_pct=5.0,
        take_profit_pct=10.0,
        max_holding_days=20,
        trailing_stop=True,
    )
    min_confidence = 40.0

    def evaluate(self, indicators: dict, bars: list[dict], regime: str) -> StrategySignal | None:
        price = indicators.get("price", 0)
        st_trend = indicators.get("supertrend_trend")  # "up" or "down"
        st_line = indicators.get("supertrend_line")
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)
        atr = indicators.get("atr_14", 0)
        ema_20 = indicators.get("ema_20")

        if st_trend is None or st_line is None:
            return None

        conditions_met = 0
        total_checks = 0

        total_checks += 1
        if st_trend == "up":
            conditions_met += 1

        total_checks += 1
        if macd > macd_signal:
            conditions_met += 1

        total_checks += 1
        if st_line is not None and price > st_line:
            conditions_met += 1

        total_checks += 1
        if ema_20 and price > ema_20:
            conditions_met += 1

        total_checks += 1
        if atr > 0:
            conditions_met += 1

        score = (conditions_met / total_checks) * 100 if total_checks else 0

        if conditions_met < 3:
            return None

        return StrategySignal(
            direction=SignalDirection.LONG,
            confidence_contribution=score,
            rationale=f"Supertrend+MACD: {conditions_met}/{total_checks} cond. "
                      f"ST={st_trend}, MACD={macd:.2f}/{macd_signal:.2f}, "
                      f"Price=${price:.2f} > SL=${st_line:.2f}" if st_line else
                      f"ST={st_trend}, MACD cross={macd > macd_signal}",
            indicators_used={
                "price": price, "supertrend_trend": st_trend,
                "supertrend_line": st_line, "macd": macd,
                "macd_signal": macd_signal, "atr": atr,
                "conditions_met": conditions_met, "total_checks": total_checks,
            },
        )


# ─── Strategy 3: Bollinger Squeeze (Breakout / Medium) ───────────────────────


class BollingerSqueeze(Strategy):
    name = "bollinger_squeeze"
    description = "Captures breakouts following Bollinger Band squeeze (low volatility contraction then expansion)"
    category = "Breakout"
    difficulty = "Medium"
    compatible_regimes = ["BULL", "VOLATILE", "RANGING"]
    risk_params = RiskParams(
        max_position_pct=5.0,
        stop_loss_pct=7.0,
        take_profit_pct=14.0,
        max_holding_days=15,
        trailing_stop=True,
    )
    min_confidence = 45.0

    def evaluate(self, indicators: dict, bars: list[dict], regime: str) -> StrategySignal | None:
        price = indicators.get("price", 0)
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        bb_width = indicators.get("bb_width")
        bb_squeeze = indicators.get("bb_squeeze", False)
        vol_ratio = indicators.get("volume_ratio", 1.0)
        rsi = indicators.get("rsi_14", 50)
        ema_20 = indicators.get("ema_20")

        if not all([bb_upper, bb_lower, bb_width]):
            return None

        conditions_met = 0
        total_checks = 0

        total_checks += 1
        if bb_squeeze:
            conditions_met += 1

        total_checks += 1
        if vol_ratio >= 1.2:
            conditions_met += 1

        total_checks += 1
        if rsi > 50 and price >= bb_upper * 0.98:
            conditions_met += 2
        elif rsi < 50 and price <= bb_lower * 1.02:
            conditions_met += 2

        total_checks += 1
        if ema_20 and price > ema_20:
            conditions_met += 1

        score = (conditions_met / total_checks) * 100 if total_checks else 0

        if conditions_met < 3:
            return None

        direction = SignalDirection.LONG if rsi > 50 else SignalDirection.SHORT
        direction_label = "upward" if rsi > 50 else "downward"

        return StrategySignal(
            direction=direction,
            confidence_contribution=score,
            rationale=f"BB Squeeze: {conditions_met}/{total_checks} cond. "
                      f"BW={bb_width:.3f}, squeeze={bb_squeeze}, "
                      f"Vol={vol_ratio:.1f}x, {direction_label} breakout",
            indicators_used={
                "price": price, "bb_upper": bb_upper, "bb_lower": bb_lower,
                "bb_width": bb_width, "bb_squeeze": bb_squeeze,
                "vol_ratio": vol_ratio, "rsi": rsi,
                "conditions_met": conditions_met, "total_checks": total_checks,
            },
        )


# ─── Strategy 4: RSI Mean Reversion (Mean Reversion / Easy) ──────────────────


class RSIMeanReversion(Strategy):
    name = "rsi_mean_reversion"
    description = "Mean reversion using RSI extremes — buys oversold, sells overbought"
    category = "Mean Reversion"
    difficulty = "Easy"
    compatible_regimes = ["RANGING", "VOLATILE", "NEUTRAL"]
    risk_params = RiskParams(
        max_position_pct=4.0,
        stop_loss_pct=4.0,
        take_profit_pct=7.0,
        max_holding_days=8,
    )
    min_confidence = 30.0

    def evaluate(self, indicators: dict, bars: list[dict], regime: str) -> StrategySignal | None:
        price = indicators.get("price", 0)
        rsi = indicators.get("rsi_14", 50)
        bb_lower = indicators.get("bb_lower")
        bb_upper = indicators.get("bb_upper")
        vol_ratio = indicators.get("volume_ratio", 1.0)
        ema_50 = indicators.get("ema_50")

        oversold = rsi < 30
        overbought = rsi > 70

        if not oversold and not overbought:
            return None

        conditions_met = 0
        total_checks = 0

        total_checks += 1
        if oversold:
            conditions_met += 1

        total_checks += 1
        if oversold and bb_lower and price >= bb_lower * 0.95:
            conditions_met += 1
        elif overbought and bb_upper and price <= bb_upper * 1.05:
            conditions_met += 1

        total_checks += 1
        if vol_ratio > 0.7:
            conditions_met += 1

        total_checks += 1
        if oversold and ema_50 and price > ema_50:
            conditions_met += 1
        elif overbought and ema_50 and price < ema_50:
            conditions_met += 1

        score = (conditions_met / total_checks) * 100 if total_checks else 0

        if conditions_met < 2:
            return None

        direction = SignalDirection.LONG if oversold else SignalDirection.SHORT
        label = "oversold" if oversold else "overbought"

        return StrategySignal(
            direction=direction,
            confidence_contribution=score,
            rationale=f"RSI MeanRev: {conditions_met}/{total_checks} cond. "
                      f"RSI={rsi:.1f} ({label}), Vol={vol_ratio:.1f}x",
            indicators_used={
                "price": price, "rsi": rsi,
                "bb_lower": bb_lower, "bb_upper": bb_upper,
                "vol_ratio": vol_ratio, "conditions_met": conditions_met,
                "total_checks": total_checks,
            },
        )


# ─── Strategy 5: VWAP Momentum (Intraday / Advanced) ─────────────────────────


class VWAPMomentum(Strategy):
    name = "vwap_momentum"
    description = "Momentum strategy keying off VWAP crossovers with volume and RSI filters"
    category = "Intraday"
    difficulty = "Advanced"
    compatible_regimes = ["BULL", "NEUTRAL", "VOLATILE"]
    risk_params = RiskParams(
        max_position_pct=6.0,
        stop_loss_pct=5.0,
        take_profit_pct=10.0,
        max_holding_days=12,
        trailing_stop=True,
    )
    min_confidence = 35.0

    def evaluate(self, indicators: dict, bars: list[dict], regime: str) -> StrategySignal | None:
        price = indicators.get("price", 0)
        vwap = indicators.get("vwap_20")
        vwap_5 = indicators.get("vwap_5")
        rsi = indicators.get("rsi_14", 50)
        vol_ratio = indicators.get("volume_ratio", 1.0)
        ema_20 = indicators.get("ema_20")

        if vwap is None or price is None:
            return None

        conditions_met = 0
        total_checks = 0

        total_checks += 1
        if price > vwap:
            conditions_met += 1

        total_checks += 1
        if vwap_5 and vwap_5 > vwap:
            conditions_met += 1

        total_checks += 1
        if 50 <= rsi <= 80:
            conditions_met += 1

        total_checks += 1
        if vol_ratio >= 1.0:
            conditions_met += 1

        total_checks += 1
        if ema_20 and price > ema_20:
            conditions_met += 1

        score = (conditions_met / total_checks) * 100 if total_checks else 0

        if conditions_met < 3:
            return None

        return StrategySignal(
            direction=SignalDirection.LONG,
            confidence_contribution=score,
            rationale=f"VWAP Mom: {conditions_met}/{total_checks} cond. "
                      f"Price=${price:.2f} > VWAP=${vwap:.2f}, "
                      f"RSI={rsi:.1f}, Vol={vol_ratio:.1f}x",
            indicators_used={
                "price": price, "vwap_20": vwap, "vwap_5": vwap_5,
                "rsi": rsi, "vol_ratio": vol_ratio,
                "conditions_met": conditions_met, "total_checks": total_checks,
            },
        )


# ─── Registry ─────────────────────────────────────────────────────────────────


_registry: dict[str, Strategy] = {}


def register(strategy: Strategy):
    _registry[strategy.name] = strategy


def get_strategies() -> list[Strategy]:
    return list(_registry.values())


def get_strategy(name: str) -> Strategy | None:
    return _registry.get(name)


def get_strategies_for_regime(regime: str) -> list[Strategy]:
    return [s for s in _registry.values() if regime in s.compatible_regimes]


def get_all_regime_strategies() -> dict[str, list[Strategy]]:
    regimes = {"BULL", "BEAR", "NEUTRAL", "RANGING", "VOLATILE", "CRASH"}
    return {r: get_strategies_for_regime(r) for r in regimes}


# Register all 5 official strategies
register(EMARSIVolume())
register(SupertrendMACD())
register(BollingerSqueeze())
register(RSIMeanReversion())
register(VWAPMomentum())


# ─── Strategy Selector ────────────────────────────────────────────────────────


class StrategySelector:
    """Selects the best strategy for current market conditions."""

    def select(
        self,
        regime: str,
        indicators: dict,
        bars: list[dict],
        confidence_scores: dict[str, float] | None = None,
    ) -> tuple[Strategy, StrategySignal] | None:
        candidates = get_strategies_for_regime(regime)
        if not candidates:
            candidates = get_strategies_for_regime("NEUTRAL")

        best: tuple[Strategy, StrategySignal] | None = None
        best_score = 0.0

        for strategy in candidates:
            try:
                signal = strategy.evaluate(indicators, bars, regime)
            except Exception:
                continue
            if signal is None:
                continue
            if signal.direction == SignalDirection.FLAT:
                continue

            if confidence_scores:
                conf = confidence_scores.get(strategy.name, signal.confidence_contribution)
                blended = signal.confidence_contribution * 0.4 + conf * 0.6
            else:
                blended = signal.confidence_contribution

            if blended < strategy.min_confidence:
                continue

            if blended > best_score:
                best_score = blended
                best = (strategy, signal)

        return best
