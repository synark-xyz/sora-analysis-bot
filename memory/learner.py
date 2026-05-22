import logging
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from db.store import (
    get_signals,
    save_lesson,
    get_lessons,
)
from memory.wiki import ingest_note, query_wiki, _read_wiki_file, _write_wiki_file, WIKI_BASE
from llm.client import LLMClient, ANALYSIS_MODEL

logger = logging.getLogger(__name__)

WIKI_LESSONS = WIKI_BASE / "lessons.md"


async def run_weekly_review(llm: Optional[LLMClient] = None) -> dict:
    llm = llm or LLMClient(model=ANALYSIS_MODEL)
    signals = get_signals_last_week()
    if not signals:
        return {
            "accuracy_stats": {},
            "changes_made": [],
            "summary": "No signals from last week to evaluate.",
        }

    lessons_content = _read_wiki_file(WIKI_LESSONS)
    prompt = f"""You are ReviewAgent. Evaluate last week's trading signals and update the strategy.

LAST WEEK SIGNALS ({len(signals)} total):
{json.dumps(signals, indent=2, default=str)}

CURRENT LESSONS.md:
{lessons_content or "(empty)"}

Task:
1. Evaluate which signals were accurate vs inaccurate based on actual outcomes
2. Identify which strategies over/underperformed
3. Update confidence weights and lessons learned
4. Detect any new behavioral patterns across the user's trades

Return JSON:
{{
  "accuracy_stats": {{
    "total_signals": {len(signals)},
    "accurate": 0,
    "inaccurate": 0,
    "accuracy_pct": 0.0,
    "best_strategy": "",
    "worst_strategy": ""
  }},
  "updated_lessons": "FULL new content for lessons.md incorporating these learnings",
  "new_patterns": ["pattern 1", "pattern 2"],
  "changes_made": ["description of change 1"],
  "summary": "1-2 paragraph weekly review summary"
}}

Return complete updated lessons.md content — do NOT truncate or summarize it."""

    messages = [{"role": "user", "content": prompt}]
    try:
        result = await llm.complete_json(
            messages, temperature=0.3, max_tokens=4096, use_cache=False
        )

        updated_lessons = result.get("updated_lessons", "")
        if updated_lessons:
            _write_wiki_file(WIKI_LESSONS, updated_lessons)

        changes = result.get("changes_made", [])
        for pattern in result.get("new_patterns", []):
            save_agent_lesson(
                lesson_type="pattern",
                symbol="",
                pattern=pattern,
                confidence_impact=0,
            )

        accuracy = result.get("accuracy_stats", {})
        summary = result.get("summary", "Review complete.")

        return {
            "accuracy_stats": accuracy,
            "changes_made": changes,
            "summary": summary,
        }

    except Exception as e:
        logger.error("Weekly review failed: %s", e)
        return {
            "accuracy_stats": {},
            "changes_made": [],
            "summary": f"Review failed: {e}",
        }


class ReviewAgent:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient(model=ANALYSIS_MODEL)

    async def run_weekly_review(self) -> dict:
        return await run_weekly_review(self.llm)
