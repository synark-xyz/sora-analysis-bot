import asyncio
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-2.5-flash"
FAST_MODEL = "deepseek/deepseek-v4-flash:free"
ANALYSIS_MODEL = "deepseek/deepseek-chat-v3-0324:free"
CACHE_TTL_HOURS = 5
MAX_RETRIES = 3
RETRY_BASE_WAIT = 2.0


def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")
    return key


class LLMClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        db_path: str = "sora.db",
    ):
        self.model = model
        self._key = api_key or _get_api_key()
        self.db_path = db_path
        self._ensure_cache_table()

    def _ensure_cache_table(self) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    input_hash TEXT PRIMARY KEY,
                    output TEXT,
                    cached_at TEXT,
                    expires_at TEXT
                )
                """
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("Cache table error: %s", e)

    async def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        use_cache: bool = True,
    ) -> str:
        model = model or self.model
        cache_key = self._cache_key(messages, model)

        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        OPENROUTER_BASE + "/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )

                if resp.status_code == 429:
                    wait = float(
                        resp.headers.get(
                            "Retry-After", RETRY_BASE_WAIT * (2**attempt)
                        )
                    )
                    logger.warning(
                        "OpenRouter rate limited — sleeping %.1fs (attempt %d)",
                        wait,
                        attempt + 1,
                    )
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code == 402:
                    raise RuntimeError(
                        "OpenRouter: insufficient credits (402). "
                        "Top up at https://openrouter.ai/keys"
                    )

                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                if use_cache:
                    self._cache_set(cache_key, content)

                return content

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_error = e
                wait = RETRY_BASE_WAIT * (2**attempt)
                logger.warning(
                    "OpenRouter request failed (attempt %d): %s — retry in %.1fs",
                    attempt + 1,
                    e,
                    wait,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)

        raise RuntimeError(
            f"OpenRouter failed after {MAX_RETRIES} attempts: {last_error}"
        )

    async def complete_json(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        use_cache: bool = True,
    ) -> dict:
        raw = await self.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            use_cache=use_cache,
        )
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned non-JSON: {e}\nRaw: {raw[:200]}"
            )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sora-trading.app",
            "X-Title": "Sora Trading Bot",
        }

    def _cache_key(self, messages: list[dict], model: str) -> str:
        payload = json.dumps(
            {"messages": messages, "model": model}, sort_keys=True
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _cache_get(self, key: str) -> Optional[str]:
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT output, expires_at FROM llm_cache WHERE input_hash = ?",
                (key,),
            ).fetchone()
            conn.close()
            if row is None:
                return None
            output, expires_at = row
            if expires_at:
                exp = datetime.fromisoformat(
                    expires_at.replace("Z", "+00:00")
                )
                if datetime.now(timezone.utc) > exp:
                    return None
            return output
        except Exception as e:
            logger.debug("Cache get error: %s", e)
            return None

    def _cache_set(self, key: str, output: str) -> None:
        try:
            expires = (
                datetime.now(timezone.utc)
                + timedelta(hours=CACHE_TTL_HOURS)
            ).isoformat()
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (input_hash, output, cached_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    key,
                    output,
                    datetime.now(timezone.utc).isoformat(),
                    expires,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("Cache set error: %s", e)
