import json
import logging
import re

logger = logging.getLogger(__name__)

CONFIDENCE_LABELS = {
    (0, 30): "LOW",
    (30, 60): "MEDIUM",
    (60, 80): "HIGH",
    (80, 101): "VERY HIGH",
}

CONFIDENCE_DIMENSIONS = [
    ("Trend Strength", "trend_strength"),
    ("Signal Alignment", "signal_alignment"),
    ("Volatility Quality", "volatility_quality"),
    ("Volume Confirm", "volume_confirm"),
    ("Regime Fit", "regime_fit"),
    ("Historical Perf", "historical_perf"),
]


def _confidence_label(score: int) -> str:
    for (lo, hi), label in CONFIDENCE_LABELS.items():
        if lo <= score < hi:
            return label
    return "UNKNOWN"


def build_confidence_bar(score: float, width: int = 12) -> str:
    filled = round(score / 100 * width)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


def parse_signal_response(llm_text: str) -> dict:
    text = llm_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        )
        text = text.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM JSON: %s", e)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse LLM response as JSON: {e}")


def build_report(signal_data: dict, indicators: dict, regime: dict) -> str:
    verdict = signal_data.get("verdict", "HOLD")
    confidence = signal_data.get("confidence", 0)
    entry_low = signal_data.get("entry_low", 0)
    entry_high = signal_data.get("entry_high", 0)
    exit_target = signal_data.get("exit_target", 0)
    stop_loss = signal_data.get("stop_loss", 0)
    rr = signal_data.get("rr_ratio", 0)
    timeframe = signal_data.get("timeframe", "N/A")
    summary = signal_data.get("summary", "")
    rules_check = signal_data.get("rules_check", "all passed")
    strategy = indicators.get("strategy", "N/A")
    regime_name = regime.get("regime", "Unknown")
    adx = indicators.get("adx", "N/A")
    symbol = indicators.get("symbol", "UNKNOWN")
    label = _confidence_label(confidence)

    entry_zone = f"${entry_low:.2f} \u2013 ${entry_high:.2f}" if entry_low else "N/A"
    exit_str = f"${exit_target:.2f}" if exit_target else "N/A"
    stop_str = f"${stop_loss:.2f}" if stop_loss else "N/A"
    delta_str = ""
    if exit_target and entry_low:
        pct = (exit_target / entry_low - 1) * 100
        delta_str = f"  ({'+' if pct >= 0 else ''}{pct:.1f}%)"
    stop_pct = ""
    if stop_loss and entry_high:
        p = (stop_loss / entry_high - 1) * 100
        stop_pct = f"  ({p:.1f}%)"

    lines = [
        "\u2501" * 30,
        f"\U0001f4ca {symbol}  \u00b7  {verdict} SIGNAL",
        "\u2501" * 30,
        f"Confidence  {confidence} / 100  [{label}]",
        f"Strategy    {strategy}",
        f"Regime      {regime_name} \u00b7 ADX {adx}",
        "",
        f"\U0001f4cd ENTRY ZONE    {entry_zone}",
        f"\u2696\ufe0f  RISK / REWARD   1 : {rr:.1f}" if rr else "",
        f"\U0001f3af EXIT TARGET   {exit_str}{delta_str}",
        f"\U0001f6d1 STOP LOSS     {stop_str}{stop_pct}",
        f"\u23f1  Timeframe        {timeframe}",
        "",
        "CONFIDENCE BREAKDOWN",
    ]

    cb = signal_data.get("confidence_breakdown", {})
    for label_key, dim_key in CONFIDENCE_DIMENSIONS:
        val = cb.get(dim_key, 0)
        bar = build_confidence_bar(val)
        lines.append(f"  {label_key:<20} {bar}  {val}%")

    if rules_check:
        tick = "\u2713" if rules_check.startswith("all") else "\u2717"
        lines.append(f"\nYour rules: {tick} {rules_check}")

    if summary:
        lines.append(f"\n{summary}")

    return "\n".join(lines)


def format_report(signal: dict) -> str:
    verdict = signal.get("verdict", "HOLD")
    confidence = signal.get("confidence", 0)
    entry_low = signal.get("entry_low", 0)
    entry_high = signal.get("entry_high", 0)
    exit_target = signal.get("exit_target", 0)
    stop_loss = signal.get("stop_loss", 0)
    rr = signal.get("rr_ratio", 0)
    timeframe = signal.get("timeframe", "N/A")
    summary = signal.get("summary", "")
    rules_check = signal.get("rules_check", "")
    cb = signal.get("confidence_breakdown", {})
    label = _confidence_label(confidence)
    symbol = signal.get("symbol", "UNKNOWN")

    entry_zone = f"${entry_low:.2f} \u2013 ${entry_high:.2f}" if entry_low else "N/A"
    exit_str = f"${exit_target:.2f}" if exit_target else "N/A"
    stop_str = f"${stop_loss:.2f}" if stop_loss else "N/A"

    lines = [
        "\u2501" * 30,
        f"\U0001f4ca {symbol}  \u00b7  {verdict} SIGNAL",
        "\u2501" * 30,
        f"Confidence  {confidence} / 100  [{label}]",
        f"\U0001f4cd ENTRY ZONE    {entry_zone}",
        f"\U0001f3af EXIT TARGET   {exit_str}",
        f"\U0001f6d1 STOP LOSS     {stop_str}",
        f"\u2696\ufe0f  RISK / REWARD   1 : {rr:.1f}" if rr else "",
        f"\u23f1  Timeframe        {timeframe}",
        "",
        "CONFIDENCE BREAKDOWN",
    ]

    for label_key, dim_key in CONFIDENCE_DIMENSIONS:
        val = cb.get(dim_key, 0)
        bar = build_confidence_bar(val)
        lines.append(f"  {label_key:<20} {bar}  {val}%")

    if rules_check:
        tick = "\u2713" if rules_check.startswith("all") else "\u2717"
        lines.append(f"\nYour rules: {tick} {rules_check}")

    if summary:
        lines.append(f"\n{summary}")

    return "\n".join(lines)
