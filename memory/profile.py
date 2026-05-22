import json
import logging
from typing import Optional

from db.store import get_profile, save_profile
from memory.wiki import query_wiki
from llm.client import LLMClient, ANALYSIS_MODEL

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    "risk_tolerance": "moderate",
    "preferred_timeframes": ["swing"],
    "favorite_strategies": [],
    "max_position_size": 1000,
    "common_mistakes": [],
}


def load_profile() -> dict:
    profile = get_user_profile()
    if profile:
        try:
            data = json.loads(profile) if isinstance(profile, str) else profile
            return {**DEFAULT_PROFILE, **data}
        except (json.JSONDecodeError, TypeError):
            pass
    return dict(DEFAULT_PROFILE)


def save_profile(profile: dict):
    save_user_profile(json.dumps(profile, indent=2))


async def update_from_wiki() -> dict:
    wiki_text = await query_wiki()
    if not wiki_text:
        return load_profile()

    prompt = f"""Extract the user's trading profile from their wiki.

WIKI CONTENT:
{wiki_text}

Return a JSON object with these fields:
- risk_tolerance: "conservative" | "moderate" | "aggressive"
- preferred_timeframes: list of strings (e.g., ["swing", "long"])
- favorite_strategies: list of strategy names mentioned
- max_position_size: estimated max position size in USD (number)
- common_mistakes: list of behavioral patterns or errors

Return ONLY valid JSON, no markdown."""

    llm = LLMClient(model=ANALYSIS_MODEL)
    messages = [{"role": "user", "content": prompt}]
    try:
        result = await llm.complete_json(messages, temperature=0.2, use_cache=False)
        profile = {**DEFAULT_PROFILE, **result}
        save_profile(profile)
        return profile
    except Exception as e:
        logger.warning("Failed to update profile from wiki: %s", e)
        return load_profile()
