import asyncio
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from log import get_logger

log = get_logger("llm.client", "LLM")

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openrouter/free")
FAST_MODEL = os.getenv("FAST_MODEL", "openrouter/free")
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "openrouter/free")
CACHE_TTL_HOURS = 5
MAX_RETRIES = 5
RETRY_BASE_WAIT = 15.0
RATE_LIMIT_RPM = 4


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self._rate = rate / 60.0
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens >= 1:
                self._tokens -= 1
                return 0.0

            wait = (1 - self._tokens) / self._rate if self._rate > 0 else 1.0
            self._tokens = 0.0
            return wait


_bucket = TokenBucket(RATE_LIMIT_RPM, 1)


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
        except Exception:
            pass

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

        wait = await _bucket.acquire()
        if wait > 0:
            await asyncio.sleep(wait)

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
                    t0 = time.monotonic()
                    resp = await client.post(
                        OPENROUTER_BASE + "/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                    elapsed = time.monotonic() - t0

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else RETRY_BASE_WAIT * (2**attempt)
                    last_error = RuntimeError(f"rate limited (429), retry-after={retry_after}")
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

                if not content:
                    last_error = RuntimeError("empty content from model")
                    continue

                log.http(
                    "OK  %s  tokens=%d  %.1fs",
                    model, data.get("usage", {}).get("total_tokens", 0), elapsed,
                )

                if use_cache:
                    self._cache_set(cache_key, content)

                return content

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_error = e
                wait = RETRY_BASE_WAIT * (2**attempt)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
        raise RuntimeError(
            f"OpenRouter failed after {MAX_RETRIES} attempts: {last_error}"
        )

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> tuple[Optional[str], Optional[list]]:
        """Returns (content, None) for text reply or (None, tool_calls) for tool invocations."""
        model = model or self.model
        wait = await _bucket.acquire()
        if wait > 0:
            await asyncio.sleep(wait)

        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
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
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else RETRY_BASE_WAIT * (2**attempt)
                    last_error = RuntimeError(f"rate limited (429)")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code == 402:
                    raise RuntimeError("OpenRouter: insufficient credits (402)")

                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                msg = choice["message"]

                if choice.get("finish_reason") == "tool_calls" or msg.get("tool_calls"):
                    return None, msg["tool_calls"]

                content = msg.get("content") or ""
                if not content:
                    last_error = RuntimeError("empty content from model")
                    continue

                return content, None

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_error = e
                wait = RETRY_BASE_WAIT * (2**attempt)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)

        raise RuntimeError(f"OpenRouter failed after {MAX_RETRIES} attempts: {last_error}")

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

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("{"):
                    text = part
                    break

        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]

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
        except Exception:
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
        except Exception:
            pass
