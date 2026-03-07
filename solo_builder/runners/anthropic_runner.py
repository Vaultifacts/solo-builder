"""AnthropicRunner — calls the Anthropic SDK directly (no subprocess).

Optional response caching
--------------------------
Pass a ResponseCache instance as *cache* to avoid re-consuming API tokens
for identical prompts across sessions.  When cache=None (default), every
call hits the API normally.

Set NOCACHE=1 in the environment to disable caching globally, or pass
cache=None explicitly.
"""
import os
from typing import Optional

from .cache import ResponseCache


class AnthropicRunner:
    """Calls the Anthropic SDK directly — no subprocess, no CLI required.

    Activated when ANTHROPIC_API_KEY is set in the environment.
    Used for Running subtasks that have no tools requirement.
    Falls back gracefully if the SDK is not installed or key is absent.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 300,
        cache: Optional[ResponseCache] = None,
    ) -> None:
        self.model        = model
        self.max_tokens   = max_tokens
        self.cache        = cache
        self.client       = None
        self.async_client = None
        self.available    = self._init()

    def _init(self) -> bool:
        try:
            import anthropic                        # noqa: PLC0415
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                return False
            self.client       = anthropic.Anthropic(api_key=key)
            self.async_client = anthropic.AsyncAnthropic(api_key=key)
            return True
        except ImportError:
            return False

    def run(self, prompt: str) -> tuple:
        """Returns (success: bool, output: str).

        Checks the cache before calling the API; stores the response on miss.
        """
        if not self.available:
            return False, "Anthropic SDK unavailable"
        if self.cache is not None:
            key = ResponseCache.make_key(prompt)
            cached = self.cache.get(key)
            if cached is not None:
                return True, cached
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            result = msg.content[0].text.strip()
            if self.cache is not None:
                self.cache.set(ResponseCache.make_key(prompt), result)
            return True, result
        except Exception as exc:
            return False, str(exc)[:200]

    async def arun(self, prompt: str) -> tuple:
        """Async version — awaitable, for use with asyncio.gather().

        Cache-aware: same hit/miss/store logic as run().
        """
        if not self.available:
            return False, "Anthropic SDK unavailable"
        if self.cache is not None:
            key = ResponseCache.make_key(prompt)
            cached = self.cache.get(key)
            if cached is not None:
                return True, cached
        try:
            msg = await self.async_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            result = msg.content[0].text.strip()
            if self.cache is not None:
                self.cache.set(ResponseCache.make_key(prompt), result)
            return True, result
        except Exception as exc:
            return False, str(exc)[:200]
