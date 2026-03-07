"""AnthropicRunner — calls the Anthropic SDK directly (no subprocess)."""
import os


class AnthropicRunner:
    """Calls the Anthropic SDK directly — no subprocess, no CLI required.

    Activated when ANTHROPIC_API_KEY is set in the environment.
    Used for Running subtasks that have no tools requirement.
    Falls back gracefully if the SDK is not installed or key is absent.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 300) -> None:
        self.model        = model
        self.max_tokens   = max_tokens
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
        """Returns (success: bool, output: str)."""
        if not self.available:
            return False, "Anthropic SDK unavailable"
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return True, msg.content[0].text.strip()
        except Exception as exc:
            return False, str(exc)[:200]

    async def arun(self, prompt: str) -> tuple:
        """Async version — awaitable, for use with asyncio.gather()."""
        if not self.available:
            return False, "Anthropic SDK unavailable"
        try:
            msg = await self.async_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return True, msg.content[0].text.strip()
        except Exception as exc:
            return False, str(exc)[:200]
