"""
engine/signal_gate.py — Hard pre-notification signal filters.

8 rules. Mandatory: R:R >= 1.5 and Entry zone active.
Scorecard: fire only if 5/6 of remaining checks pass.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

CONFIDENCE_FLOOR = 70
CONFIDENCE_NEUTRAL_FLOOR = 75
RSI_LONG_MAX = 65
RSI_NEUTRAL_LONG_MAX = 60
MIN_RR = 1.5
MAX_STOP_PCT = 15.0
VOLUME_CONFIRM_MULT = 1.5
NEWS_COOLDOWN_DAYS = 7  # 5 trading days ≈ 7 calendar days

CATALYST_KEYWORDS = [
    "earnings", "beat", "miss", "revenue", "guidance",
    "contract", "fda", "approval", "merger", "acquisition",
    "buyout", "investigation", "lawsuit", "settlement",
    "indictment", "restatement", "bankruptcy",
]


@dataclass
class GateCheck:
    name: str
    passed: bool
    mandatory: bool = False
    reason: str = ""


@dataclass
class GateResult:
    passed: bool
    checks: list = field(default_factory=list)
    fail_reason: str = ""
    scorecard_summary: str = ""

    def scorecard_text(self) -> str:
        lines = []
        for c in self.checks:
            mark = "✓" if c.passed else "✗"
            tag = " [MANDATORY]" if c.mandatory else ""
            lines.append(f"{mark} {c.name}{tag}: {c.reason}")
        if self.scorecard_summary:
            lines.append(self.scorecard_summary)
        return "\n".join(lines)


def check_gate(
    verdict: str,
    indicators: dict,
    entry_price: float,
    stop_loss: float | None,
    take_profit: float | None,
    confidence: float,
    regime: str,
    symbol: str,
    market: str = "us",
) -> GateResult:
    if verdict == "HOLD":
        return GateResult(passed=True, fail_reason="HOLD — gate skipped")

    checks = []

    rr_check = _check_rr(entry_price, stop_loss, take_profit)
    rr_check.mandatory = True
    checks.append(rr_check)

    entry_check = _check_entry_zone(indicators, entry_price, stop_loss)
    entry_check.mandatory = True
    checks.append(entry_check)

    checks.append(_check_confidence(confidence, regime))

    if verdict in ("BUY", "LONG"):
        checks.append(_check_rsi(indicators, regime))

    checks.append(_check_volume(indicators))
    checks.append(_check_news_cooldown(symbol, market))
    checks.append(_check_stop_sanity(entry_price, stop_loss, indicators))

    mandatory_failed = [c for c in checks if c.mandatory and not c.passed]
    if mandatory_failed:
        reasons = "; ".join(c.reason for c in mandatory_failed)
        return GateResult(
            passed=False,
            checks=checks,
            fail_reason=f"MANDATORY FAIL — {reasons}",
            scorecard_summary=_summary(checks),
        )

    scorecard_checks = [c for c in checks if not c.mandatory]
    passed_count = sum(1 for c in scorecard_checks if c.passed)
    total = len(scorecard_checks)
    required = total - 1  # allow 1 failure

    summary = f"{passed_count}/{total} scorecard checks passed"
    if passed_count < required:
        failed = [c for c in scorecard_checks if not c.passed]
        reasons = "; ".join(c.reason for c in failed)
        return GateResult(
            passed=False,
            checks=checks,
            fail_reason=f"SCORECARD FAIL ({summary}) — {reasons}",
            scorecard_summary=summary,
        )

    return GateResult(passed=True, checks=checks, scorecard_summary=summary)


def compute_rr(entry_price: float, stop_loss: float | None, take_profit: float | None) -> float | None:
    if not entry_price or not stop_loss or not take_profit or entry_price <= 0:
        return None
    stop_dist = abs(entry_price - stop_loss)
    target_dist = abs(take_profit - entry_price)
    return round(target_dist / stop_dist, 2) if stop_dist > 0 else None


def _summary(checks: list) -> str:
    passed = sum(1 for c in checks if c.passed)
    return f"{passed}/{len(checks)} checks passed"


def _check_rr(entry_price: float, stop_loss: float | None, take_profit: float | None) -> GateCheck:
    rr = compute_rr(entry_price, stop_loss, take_profit)
    if rr is None:
        return GateCheck("R:R", False, reason="Cannot compute — missing price data")
    passed = rr >= MIN_RR
    return GateCheck(
        "R:R", passed,
        reason=f"{rr:.2f}:1 ({'≥' if passed else '<'} {MIN_RR}:1 required)",
    )


def _check_entry_zone(indicators: dict, entry_price: float, stop_loss: float | None) -> GateCheck:
    price = indicators.get("price", 0)
    atr = indicators.get("atr_14", 0)
    entry_high = entry_price + (atr * 0.5) if atr else entry_price * 1.01
    if not price:
        return GateCheck("Entry zone", False, reason="No live price data")
    passed = price <= entry_high
    return GateCheck(
        "Entry zone", passed,
        reason=f"price ${price:.2f} ({'≤' if passed else '>'} zone top ${entry_high:.2f})",
    )


def _check_confidence(confidence: float, regime: str) -> GateCheck:
    floor = CONFIDENCE_NEUTRAL_FLOOR if regime == "NEUTRAL" else CONFIDENCE_FLOOR
    passed = confidence >= floor
    return GateCheck(
        "Confidence", passed,
        reason=f"{confidence:.0f} ({'≥' if passed else '<'} {floor} floor, regime={regime})",
    )


def _check_rsi(indicators: dict, regime: str) -> GateCheck:
    rsi = indicators.get("rsi_14", 50)
    limit = RSI_NEUTRAL_LONG_MAX if regime == "NEUTRAL" else RSI_LONG_MAX
    passed = rsi <= limit
    return GateCheck(
        "RSI", passed,
        reason=f"{rsi:.1f} ({'≤' if passed else '>'} {limit} max for long entry)",
    )


def _check_volume(indicators: dict) -> GateCheck:
    current = indicators.get("current_volume", 0)
    avg = indicators.get("avg_volume", 0)
    if avg <= 0:
        return GateCheck("Volume", True, reason="No avg volume — skipped")
    ratio = current / avg
    passed = ratio >= VOLUME_CONFIRM_MULT
    return GateCheck(
        "Volume", passed,
        reason=f"{ratio:.2f}× 20d avg ({'≥' if passed else '<'} {VOLUME_CONFIRM_MULT}× required)",
    )


def _check_news_cooldown(symbol: str, market: str) -> GateCheck:
    try:
        from analysis.news import fetch_news
        source = "cryptopanic" if market == "crypto" else "yahoo"
        articles = fetch_news(symbol, source=source)
        cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_COOLDOWN_DAYS)

        for a in articles:
            pub = a.get("published_at")
            if not pub:
                continue
            try:
                if isinstance(pub, str):
                    from dateutil import parser as dp
                    pub_dt = dp.parse(pub)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                else:
                    pub_dt = pub
                if pub_dt >= cutoff:
                    title = a.get("title", "").lower()
                    if any(kw in title for kw in CATALYST_KEYWORDS):
                        snippet = a.get("title", "")[:55]
                        return GateCheck(
                            "Post-catalyst", False,
                            reason=f"Catalyst within {NEWS_COOLDOWN_DAYS}d: \"{snippet}\"",
                        )
            except Exception:
                continue

        return GateCheck("Post-catalyst", True, reason=f"No catalyst news in {NEWS_COOLDOWN_DAYS}d")
    except Exception as e:
        return GateCheck("Post-catalyst", True, reason=f"News check unavailable ({e})")


def _check_stop_sanity(entry_price: float, stop_loss: float | None, indicators: dict) -> GateCheck:
    if not entry_price or not stop_loss or entry_price <= 0:
        return GateCheck("Stop sanity", True, reason="No price data — skipped")

    stop_dist = abs(entry_price - stop_loss)
    stop_pct = (stop_dist / entry_price) * 100
    atr = indicators.get("atr_14", 0)

    if stop_pct > MAX_STOP_PCT:
        return GateCheck(
            "Stop sanity", False,
            reason=f"Stop {stop_pct:.1f}% > {MAX_STOP_PCT}% max for swing",
        )

    if atr > 0:
        atr_mult = stop_dist / atr
        if atr_mult < 1.0:
            return GateCheck(
                "Stop sanity", False,
                reason=f"Stop {atr_mult:.1f}× ATR — too tight",
            )
        detail = f"Stop {stop_pct:.1f}% = {atr_mult:.1f}× ATR"
    else:
        detail = f"Stop {stop_pct:.1f}%"

    return GateCheck("Stop sanity", True, reason=detail)
