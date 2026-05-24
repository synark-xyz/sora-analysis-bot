import os
from typing import Optional

from llm.client import LLMClient, FAST_MODEL, ANALYSIS_MODEL
from analysis.moomoo import build_moomoo_prompt

BULL_MODEL = os.getenv("FAST_MODEL", "openrouter/free")
BEAR_MODEL = os.getenv("FAST_MODEL", "openrouter/free")

BULL_SYSTEM_PROMPT = """You are BullAgent, an expert bullish analyst. Build the strongest bullish case using ONLY provided data. Never fabricate data.

Return JSON only:
{
  "catalysts": ["string"],
  "target_levels": {"key_resistance": 0.0, "breakout_point": 0.0},
  "thesis_summary": "string"
}
"""

BEAR_SYSTEM_PROMPT = """You are BearAgent, an expert risk analyst. Stress-test the bull thesis using ONLY provided data. Identify hidden risks and technical weaknesses.

Return JSON only:
{
  "hidden_risks": ["string"],
  "flawed_assumptions": ["string"],
  "support_levels": {"key_support": 0.0, "breakdown_point": 0.0},
  "counter_summary": "string"
}
"""

ANALYST_SYSTEM_PROMPT = """You are AnalystAgent, the final compliance decision-maker. Synthesize the Bull and Bear arguments against the Live Strategy Rules provided in the user message. 

Strictly fail the trade (Verdict: HOLD or WAIT) if the trade setup violates any active constraints, such as minimum Risk-to-Reward (R:R) or forbidden setups.

Return JSON only:
{
  "verdict": "BUY|SELL|HOLD|WAIT",
  "confidence": 75,  # integer 0-100
  "entry_low": 0.0,
  "exit_target": 0.0,
  "stop_loss": 0.0,
  "rr_ratio": 0.0,
  "timeframe": "Swing (5-12 days)",
  "summary": "string",
  "executive_summary": "string",
  "valuation_assessment": {
    "verdict": "undervalued|fair|overvalued",
    "key_metrics": "string",
    "fair_value_estimate": "string"
  },
  "entry_strategy": {
    "tactical_zone": {"price": 0.0, "reason": "string"},
    "value_zone": {"price": 0.0, "reason": "string"},
    "scale_in_plan": "string"
  },
  "risk_management": {
    "stop_loss_type": "technical|percentage|fundamental",
    "position_sizing": "string",
    "margin_of_safety_pct": 0.0
  },
  "monitoring_catalysts": ["string"],
  "moomoo_framework_breakdown": {
    "step1_objective": "string",
    "step3_fundamental_verdict": "string",
    "step3_valuation_verdict": "string",
    "step3_technical_verdict": "string",
    "step4_synthesis": "string"
  }
}
"""


async def analyze_quick(
    symbol: str,
    indicators: dict,
    regime: dict,
    wiki_context: str = "",
    llm: Optional[LLMClient] = None,
) -> dict:
    llm = llm or LLMClient(model=ANALYSIS_MODEL)
    prompt = f"""Analyze {symbol} for a trading signal.

Indicators: {indicators}
Regime: {regime}

User wiki context:
{wiki_context}

Return a structured verdict as JSON with these keys:
verdict (BUY|SELL|HOLD), confidence (0-100), entry_low, entry_high, exit_target, stop_loss, rr_ratio, timeframe, summary, rules_check, confidence_breakdown (object with trend_strength, signal_alignment, volatility_quality, volume_confirm, regime_fit, historical_perf)."""
    messages = [{"role": "user", "content": prompt}]
    return await llm.complete_json(messages, temperature=0.2)


async def analyze_full(
    symbol: str,
    indicators: dict,
    regime: dict,
    news: str,
    fundamentals: str,
    wiki_context: str = "",
    signal_history: str = "",
    breadth_context: str = "",
    llm: Optional[LLMClient] = None,
) -> dict:
    llm = llm or LLMClient(model=ANALYSIS_MODEL)
    bull_llm = LLMClient(model=BULL_MODEL)
    bear_llm = LLMClient(model=BEAR_MODEL)

    market_data = f"""
Symbol: {symbol}
Indicators: {indicators}
Regime: {regime}
News: {news}
Fundamentals: {fundamentals}
{f"Market Breadth: {breadth_context}" if breadth_context else ""}
{f"Signal History:\n{signal_history}" if signal_history else ""}"""

    bull_messages = [
        {"role": "system", "content": BULL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Build the strongest bullish case for {symbol}.\n\n{market_data}\n\nReturn JSON: {{ \"bull_thesis\": \"...\", \"bull_confidence\": 0-100, \"key_catalysts\": [\"...\"] }}",
        },
    ]
    bull_result = await bull_llm.complete_json(
        bull_messages, temperature=0.3, max_tokens=2048, use_cache=True
    )

    bear_messages = [
        {"role": "system", "content": BEAR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Stress-test this bull thesis for {symbol}.\n\n{market_data}\n\n"
                f"Bull thesis: {bull_result.get('bull_thesis', '')}\n\n"
                f"Return JSON: {{ "
                f"\"bear_thesis\": \"...\", "
                f"\"bear_confidence\": 0-100, "
                f"\"key_risks\": [\"...\"], "
                f"\"bear_score_of_bull\": 0-100 "
                f"}}"
            ),
        },
    ]
    bear_result = await bear_llm.complete_json(
        bear_messages, temperature=0.3, max_tokens=2048, use_cache=True
    )

    # ── Debate scoring: inject bear assessment of bull thesis ──────────────
    bear_score_of_bull = bear_result.get("bear_score_of_bull", 50)
    debate_note = ""
    if isinstance(bear_score_of_bull, (int, float)):
        if bear_score_of_bull < 40:
            debate_note = (
                f"\n\n⚠️ DEBATE SCORE: BearAgent rated the bull thesis only {bear_score_of_bull}/100. "
                f"Bear strongly discredits bull case. Weight bear risks heavily in synthesis. "
                f"Lean toward HOLD or WAIT unless fundamental catalyst is exceptional."
            )
        elif bear_score_of_bull > 70:
            debate_note = (
                f"\n\nDEBATE SCORE: BearAgent rated bull thesis {bear_score_of_bull}/100 — "
                f"bear concedes bull case is credible. Standard synthesis applies."
            )
    # ── end debate ─────────────────────────────────────────────────────────

    synthesis_messages = [
        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Synthesize the bull vs bear debate for {symbol}.\n\n"
                f"Indicators: {indicators}\nRegime: {regime}\nNews: {news}\nFundamentals: {fundamentals}\n"
                f"Market Breadth: {breadth_context}\n\n"
                f"Bull case: {bull_result.get('bull_thesis', '')}\n"
                f"Bull confidence: {bull_result.get('bull_confidence', 'N/A')}\n"
                f"Catalysts: {bull_result.get('key_catalysts', [])}\n\n"
                f"Bear case: {bear_result.get('bear_thesis', '')}\n"
                f"Bear confidence: {bear_result.get('bear_confidence', 'N/A')}\n"
                f"Risks: {bear_result.get('key_risks', [])}\n"
                f"{debate_note}\n\n"
                f"User wiki context:\n{wiki_context}\n\n"
                f"Signal history:\n{signal_history}"
            ),
        },
    ]
    synthesis = await llm.complete_json(
        synthesis_messages, temperature=0.2, max_tokens=2048, use_cache=True
    )
    synthesis["bull_thesis"] = bull_result.get("bull_thesis", "")
    synthesis["bear_thesis"] = bear_result.get("bear_thesis", "")
    synthesis["key_catalysts"] = bull_result.get("key_catalysts", [])
    synthesis["key_risks"] = bear_result.get("key_risks", [])
    return synthesis


async def analyze_moomoo(
    symbol: str,
    indicators: dict,
    regime: dict,
    news: str,
    fundamentals: str,
    valuation: str,
    wiki_context: str = "",
    llm: Optional[LLMClient] = None,
) -> dict:
    llm = llm or LLMClient(model=ANALYSIS_MODEL)
    full_prompt = build_moomoo_prompt(
        symbol=symbol,
        indicators=indicators,
        regime=regime,
        news=news,
        fundamentals=fundamentals,
        valuation=valuation,
        wiki_context=wiki_context,
    )
    messages = [
        {"role": "system", "content": MOOMOO_SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt},
    ]
    result = await llm.complete_json(messages, temperature=0.2, max_tokens=4096, use_cache=True)
    result["moomoo_report"] = True
    for required in ("summary", "executive_summary", "entry_strategy", "risk_management"):
        result.setdefault(required, "")
    for required in ("entry_low", "entry_high", "exit_target", "stop_loss", "rr_ratio", "confidence"):
        result.setdefault(required, 0)
    result.setdefault("verdict", "HOLD")
    result.setdefault("timeframe", "Swing (5-12 days)")
    return result
