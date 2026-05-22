import logging
from typing import Optional

from db.store import save_feedback as log_feedback
from memory.wiki import ingest_note

logger = logging.getLogger(__name__)


def log_trade_action(
    symbol: str,
    action: str,
    reason: Optional[str] = None,
    emotional_state: Optional[str] = None,
) -> int:
    entry_id = log_feedback(symbol, action, reason, emotional_state)
    logger.info(
        "Trade feedback logged: %s %s (id=%d, reason=%s, emotion=%s)",
        symbol,
        action,
        entry_id,
        reason,
        emotional_state,
    )
    return entry_id


async def process_trade_feedback(
    symbol: str,
    action: str,
    reason: Optional[str] = None,
) -> str:
    entry_id = log_trade_action(symbol, action, reason)

    note_text = f"Trade: {symbol} {action}"
    if reason:
        note_text += f" - reason: {reason}"
    wiki_result = await ingest_note(note_text, symbol=symbol)

    return f"Feedback logged (id={entry_id}). {wiki_result}"
