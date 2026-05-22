"""
engine/confidence.py — Deterministic, explainable confidence engine.

Seven dimensions, each scored 0-100, weighted to produce a final 0-100 score.
Every score component is deterministic and comes with an explanation string.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from engine.regime import RegimeResult


@dataclass
class ConfidenceComponent:
    score: float        # 0-100
    weight: float       # weight in final aggregation (sums to 1.0)
    reason: str         # human-readable explanation


@dataclass
class ConfidenceResult:
    total: float        # 0-100 final score
    verdict: str        # REJECT / LOW / MEDIUM / HIGH
    components: dict[str, ConfidenceComponent]
    breakdown: dict = field(default_factory=dict)


VERDICT_THRESHOLDS = [
    (75, "HIGH"),
    (55, "MEDIUM"),
    (35, "LOW"),
    (0, "REJECT"),
]


def _verdict(score: float) -> str:
    for threshold, label in VERDICT_THRESHOLDS:
        if score >= threshold:
            return label
    return "REJECT"


class ConfidenceEngine:
    """Deterministic confidence engine with 7 explainable dimensions."""

    WEIGHTS = {
        "trend_strength": 0.18,
        "signal_alignment": 0.22,
        "volatility_quality": 0.10,
        "volume_confirmation": 0.12,
        "market_regime_fit": 0.16,
        "historical_performance": 0.12,
        "drawdown_state": 0.10,
    }

    def compute(
        self,
        strategy_name: str,
        indicators: dict,
        bars: list[dict],
        regime: RegimeResult | None = None,
        account: Optional[dict] = None,
        history: Optional[dict] = None,
    ) -> ConfidenceResult:
        components = {}

        score, reason = self._trend_strength(indicators)
        components["trend_strength"] = ConfidenceComponent(
            score=score, weight=self.WEIGHTS["trend_strength"], reason=reason
        )

        score, reason = self._signal_alignment(indicators)
        components["signal_alignment"] = ConfidenceComponent(
            score=score, weight=self.WEIGHTS["signal_alignment"], reason=reason
        )

        score, reason = self._volatility_quality(indicators, bars)
        components["volatility_quality"] = ConfidenceComponent(
            score=score, weight=self.WEIGHTS["volatility_quality"], reason=reason
        )

        score, reason = self._volume_confirmation(indicators, bars)
        components["volume_confirmation"] = ConfidenceComponent(
            score=score, weight=self.WEIGHTS["volume_confirmation"], reason=reason
        )

        score, reason = self._regime_fit(strategy_name, indicators, regime)
        components["market_regime_fit"] = ConfidenceComponent(
            score=score, weight=self.WEIGHTS["market_regime_fit"], reason=reason
        )

        score, reason = self._historical_performance(strategy_name, history)
        components["historical_performance"] = ConfidenceComponent(
            score=score, weight=self.WEIGHTS["historical_performance"], reason=reason
        )

        score, reason = self._drawdown_state(account)
        components["drawdown_state"] = ConfidenceComponent(
            score=score, weight=self.WEIGHTS["drawdown_state"], reason=reason
        )

        total = sum(c.score * c.weight for c in components.values())

        # Build breakdown dict for serialization
        breakdown = {
            k: {"score": round(v.score, 1), "weight": v.weight, "reason": v.reason}
            for k, v in components.items()
        }

        return ConfidenceResult(
            total=round(total, 1),
            verdict=_verdict(total),
            components=components,
            breakdown=breakdown,
        )

    # ─── Dimension scorers (each returns score 0-100 + reason string) ───

    @staticmethod
    def _trend_strength(indicators: dict) -> tuple[float, str]:
        adx = indicators.get("adx", 0)
        ema_20 = indicators.get("ema_20")
        ema_50 = indicators.get("ema_50")
        price = indicators.get("price", 0)
        trend_strength_val = indicators.get("trend_strength", 0)

        reasons = []
        score = 50.0

        if adx >= 30:
            score += 25
            reasons.append(f"ADX={adx:.1f} (strong trend)")
        elif adx >= 25:
            score += 10
            reasons.append(f"ADX={adx:.1f} (moderate trend)")
        elif adx >= 20:
            reasons.append(f"ADX={adx:.1f} (weak trend)")
            score -= 10
        else:
            reasons.append(f"ADX={adx:.1f} (no trend)")
            score -= 20

        if price and ema_20 and ema_50:
            if price > ema_20 > ema_50:
                score += 15
                reasons.append("Price > EMA20 > EMA50 (bullish alignment)")
            elif price < ema_20 < ema_50:
                score += 10
                reasons.append("Price < EMA20 < EMA50 (bearish alignment)")
            elif abs(ema_20 - ema_50) / ema_50 < 0.01:
                score -= 15
                reasons.append("EMAs converging (low trend conviction)")

        score += min(10, abs(trend_strength_val) * 5)
        if abs(trend_strength_val) > 5:
            reasons.append(f"Trend strength={trend_strength_val:.1f}%")

        final_score = max(0, min(100, score))
        return final_score, "; ".join(reasons) if reasons else "No trend data"

    @staticmethod
    def _signal_alignment(indicators: dict) -> tuple[float, str]:
        rsi = indicators.get("rsi_14", 50)
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        price = indicators.get("price", 0)

        aligned = 0
        total = 0
        reasons = []

        total += 1
        if rsi > 50:
            aligned += 1
            reasons.append(f"RSI={rsi:.1f} > 50 (bullish)")
        elif rsi < 50:
            reasons.append(f"RSI={rsi:.1f} < 50 (bearish)")

        total += 1
        if macd > macd_signal:
            aligned += 1
            reasons.append("MACD above signal (bullish)")
        else:
            reasons.append("MACD below signal (bearish)")

        total += 1
        if bb_lower and bb_upper and price:
            bb_width = (bb_upper - bb_lower) / ((bb_upper + bb_lower) / 2)
            if 0.02 <= bb_width <= 0.08:
                aligned += 1
                reasons.append(f"BB width={bb_width:.3f} (normal range)")

        score = (aligned / total) * 100 if total else 50
        score = max(0, min(100, score))
        return score, "; ".join(reasons) if reasons else "No signal data"

    @staticmethod
    def _volatility_quality(indicators: dict, bars: list[dict]) -> tuple[float, str]:
        atr = indicators.get("atr_14", 0)
        price = indicators.get("price", 0)
        volatility = indicators.get("volatility", 0)
        hist_vol = indicators.get("historical_vol", 0)

        if price == 0 or atr == 0:
            return 50.0, "No volatility data — neutral"

        atr_pct = atr / price * 100
        reasons = []
        score = 60.0

        if atr_pct < 0.5:
            score -= 20
            reasons.append(f"ATR={atr_pct:.2f}% (very low volatility)")
        elif atr_pct < 1.0:
            score -= 5
            reasons.append(f"ATR={atr_pct:.2f}% (low volatility)")
        elif atr_pct <= 3.0:
            score += 15
            reasons.append(f"ATR={atr_pct:.2f}% (ideal volatility)")
        elif atr_pct <= 5.0:
            score += 5
            reasons.append(f"ATR={atr_pct:.2f}% (elevated volatility)")
        else:
            score -= 25
            reasons.append(f"ATR={atr_pct:.2f}% (extreme volatility — risky)")

        if hist_vol and volatility:
            vol_ratio = volatility / hist_vol if hist_vol > 0 else 1.0
            if vol_ratio > 2.0:
                score -= 15
                reasons.append(f"Vol ratio={vol_ratio:.1f}x hist (abnormal)")
            elif vol_ratio > 1.5:
                score -= 5
                reasons.append(f"Vol ratio={vol_ratio:.1f}x hist (elevated)")

        final_score = max(0, min(100, score))
        return final_score, "; ".join(reasons) if reasons else "Neutral volatility"

    @staticmethod
    def _volume_confirmation(indicators: dict, bars: list[dict]) -> tuple[float, str]:
        vol_ratio = indicators.get("volume_ratio", 1.0)
        reasons = []
        score = 50.0

        if vol_ratio > 2.0:
            score += 25
            reasons.append(f"Volume {vol_ratio:.1f}x avg (strong confirmation)")
        elif vol_ratio > 1.5:
            score += 15
            reasons.append(f"Volume {vol_ratio:.1f}x avg (above average)")
        elif vol_ratio > 1.0:
            score += 5
            reasons.append(f"Volume {vol_ratio:.1f}x avg (average)")
        elif vol_ratio < 0.5:
            score -= 25
            reasons.append(f"Volume {vol_ratio:.1f}x avg (very low — unreliable)")
        else:
            score -= 10
            reasons.append(f"Volume {vol_ratio:.1f}x avg (below average)")

        if len(bars) > 10:
            recent_vols = [b["volume"] for b in bars[-10:]]
            vol_trend = recent_vols[-1] / (sum(recent_vols[:-1]) / max(len(recent_vols) - 1, 1))
            if vol_trend > 1.2:
                score += 5
                reasons.append("Volume rising over last 10 days")
            elif vol_trend < 0.8:
                score -= 5
                reasons.append("Volume declining over last 10 days")

        final_score = max(0, min(100, score))
        return final_score, "; ".join(reasons) if reasons else "Neutral volume"

    @staticmethod
    def _regime_fit(strategy_name: str, indicators: dict, regime: RegimeResult | None) -> tuple[float, str]:
        if regime is None:
            return 50.0, "No regime data"

        regime_label = regime.regime
        regime_confidence = regime.confidence

        strategy_regime_map = {
            "ema_rsi_volume": ["BULL", "NEUTRAL"],
            "supertrend_macd": ["BULL", "VOLATILE", "NEUTRAL"],
            "bollinger_squeeze": ["BULL", "VOLATILE", "RANGING"],
            "rsi_mean_reversion": ["RANGING", "VOLATILE", "NEUTRAL"],
            "vwap_momentum": ["BULL", "NEUTRAL", "VOLATILE"],
        }

        compatible = strategy_regime_map.get(strategy_name, [])
        reasons = []

        if regime_label in compatible:
            base = 80.0
            reasons.append(f"Regime={regime_label} matches {strategy_name}")
            bonus = regime_confidence * 20
            score = base + bonus
            score = min(100, score)
        else:
            base = 30.0
            reasons.append(f"Regime={regime_label} suboptimal for {strategy_name}")
            score = base

        score = max(0, min(100, score))
        return score, "; ".join(reasons)

    @staticmethod
    def _historical_performance(strategy_name: str, history: dict | None) -> tuple[float, str]:
        if not history:
            return 50.0, "No historical data (neutral)"

        win_rate = history.get("win_rate", 0.5)
        sharpe = history.get("sharpe", 0)
        total_trades = history.get("total_trades", 0)
        reasons = []

        if total_trades < 5:
            return 50.0, f"Only {total_trades} trades — insufficient data"

        score = 50.0

        if win_rate >= 0.60:
            score += 20
            reasons.append(f"Win rate={win_rate:.0%} (strong)")
        elif win_rate >= 0.50:
            score += 10
            reasons.append(f"Win rate={win_rate:.0%} (breakeven+)")
        else:
            score -= 15
            reasons.append(f"Win rate={win_rate:.0%} (below breakeven)")

        if sharpe >= 1.5:
            score += 20
            reasons.append(f"Sharpe={sharpe:.2f} (excellent)")
        elif sharpe >= 1.0:
            score += 10
            reasons.append(f"Sharpe={sharpe:.2f} (good)")
        elif sharpe >= 0:
            reasons.append(f"Sharpe={sharpe:.2f} (neutral)")
        else:
            score -= 20
            reasons.append(f"Sharpe={sharpe:.2f} (negative — losing strategy)")

        final_score = max(0, min(100, score))
        return final_score, "; ".join(reasons) if reasons else "No performance data"

    @staticmethod
    def _drawdown_state(account: dict | None) -> tuple[float, str]:
        if not account:
            return 70.0, "No account data — conservative default"

        current_dd = account.get("current_drawdown_pct", 0)
        max_dd = account.get("max_drawdown_pct", 20)
        daily_pnl_pct = account.get("daily_pnl_pct", 0)
        reasons = []
        score = 80.0

        dd_ratio = current_dd / max_dd if max_dd > 0 else 0

        if dd_ratio > 0.8:
            score = 20.0
            reasons.append(f"Drawdown {current_dd:.1f}% near max {max_dd:.1f}% (high risk)")
        elif dd_ratio > 0.5:
            score = 50.0
            reasons.append(f"Drawdown {current_dd:.1f}% at {dd_ratio:.0%} of max (elevated risk)")
        elif dd_ratio > 0.2:
            score = 70.0
            reasons.append(f"Drawdown {current_dd:.1f}% within normal range")
        else:
            score = 90.0
            reasons.append(f"Drawdown {current_dd:.1f}% (minimal)")

        if daily_pnl_pct < -3:
            score -= 20
            reasons.append(f"Today -{abs(daily_pnl_pct):.1f}% (bad day) — pausing")

        final_score = max(0, min(100, score))
        return final_score, "; ".join(reasons) if reasons else "Normal drawdown state"
