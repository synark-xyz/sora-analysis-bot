import logging
from typing import Optional

from llm.client import LLMClient, FAST_MODEL, ANALYSIS_MODEL

logger = logging.getLogger(__name__)

BULL_MODEL = "meta-llama/llama-3.2-3b-instruct:free"
BEAR_MODEL = "meta-llama/llama-3.2-3b-instruct:free"

BULL_SYSTEM_PROMPT = """You are BullAgent, an expert bullish analyst. Build the strongest possible bullish case. Be specific with price levels and catalysts. Never fabricate data — use only what is provided. Return ONLY valid JSON, no other text."""

BEAR_SYSTEM_PROMPT = """You are BearAgent, an expert risk analyst. Stress-test the bull thesis and build the strongest bearish counter-case. Identify hidden risks, overoptimistic assumptions, and technical weaknesses. Be specific with price levels. Return ONLY valid JSON, no other text."""

ANALYST_SYSTEM_PROMPT = """You are AnalystAgent, the final decision-maker. Synthesize the bull and bear arguments against the user's own trading strategy (from their wiki). Return a structured verdict.

You MUST return valid JSON with these exact keys:
{
  "verdict": "BUY|SELL|HOLD",
  "confidence": 0-100,
  "entry_low": 0.0,
  "entry_high": 0.0,
  "exit_target": 0.0,
  "stop_loss": 0.0,
  "rr_ratio": 0.0,
  "timeframe": "Swing (5-12 days)",
  "summary": "1-2 sentence rationale",
  "rules_check": "all passed or violations",
  "confidence_breakdown": {
    "trend_strength": 0-100,
    "signal_alignment": 0-100,
    "volatility_quality": 0-100,
    "volume_confirm": 0-100,
    "regime_fit": 0-100,
    "historical_perf": 0-100
  }
}

Only output the raw JSON object — no markdown fences, no explanation, no extra text."""


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
Fundamentals: {fundamentals}"""

    bull_messages = [
        {"role": "system", "content": BULL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Build the strongest bullish case for {symbol}.\n\n{market_data}\n\nReturn JSON: {{ \"bull_thesis\": \"...\", \"bull_confidence\": 0-100, \"key_catalysts\": [\"...\"] }}",
        },
    ]
    bull_result = await bull_llm.complete_json(
        bull_messages, temperature=0.3, use_cache=True
    )

    bear_messages = [
        {"role": "system", "content": BEAR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Stress-test this bull thesis for {symbol}.\n\n{market_data}\n\nBull thesis: {bull_result.get('bull_thesis', '')}\n\nReturn JSON: {{ \"bear_thesis\": \"...\", \"bear_confidence\": 0-100, \"key_risks\": [\"...\"] }}",
        },
    ]
    bear_result = await bear_llm.complete_json(
        bear_messages, temperature=0.3, use_cache=True
    )

    synthesis_messages = [
        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Synthesize the bull vs bear debate for {symbol}.\n\nIndicators: {indicators}\nRegime: {regime}\nNews: {news}\nFundamentals: {fundamentals}\n\nBull case: {bull_result.get('bull_thesis', '')}\nBull confidence: {bull_result.get('bull_confidence', 'N/A')}\nCatalysts: {bull_result.get('key_catalysts', [])}\n\nBear case: {bear_result.get('bear_thesis', '')}\nBear confidence: {bear_result.get('bear_confidence', 'N/A')}\nRisks: {bear_result.get('key_risks', [])}\n\nUser wiki context:\n{wiki_context}",
        },
    ]
    synthesis = await llm.complete_json(
        synthesis_messages, temperature=0.2, use_cache=True
    )
    synthesis["bull_thesis"] = bull_result.get("bull_thesis", "")
    synthesis["bear_thesis"] = bear_result.get("bear_thesis", "")
    synthesis["key_catalysts"] = bull_result.get("key_catalysts", [])
    synthesis["key_risks"] = bear_result.get("key_risks", [])
    return synthesis
