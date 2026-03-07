"""SdkToolRunner — Anthropic SDK runner with tool-use protocol (Read, Glob, Grep)."""
import asyncio
import os

# Resolve solo_builder/ directory (one level up from this runners/ package)
_SOLO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SdkToolRunner:
    """Anthropic SDK runner with tool-use protocol (Read, Glob, Grep).

    Replaces ClaudeRunner subprocess for subtasks that declare tools,
    eliminating the subprocess cold-start penalty (~30 s → ~5 s).
    Falls back to subprocess via claude_jobs if unavailable.
    """

    _SCHEMAS = [
        {
            "name": "Read",
            "description": "Read the content of a file from disk.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string",
                                  "description": "Absolute or relative file path"},
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "Glob",
            "description": "Find files matching a glob pattern.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string",
                                "description": "Glob pattern, e.g. '**/*.py'"},
                    "path":    {"type": "string",
                                "description": "Root directory (default: project root)"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "Grep",
            "description": "Search file contents for a regex pattern.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string",
                                "description": "Regex to search for"},
                    "path":    {"type": "string",
                                "description": "File or directory to search"},
                    "glob":    {"type": "string",
                                "description": "File filter glob when path is a directory"},
                },
                "required": ["pattern"],
            },
        },
    ]

    def __init__(self, client, async_client, model: str, max_tokens: int) -> None:
        self.client       = client
        self.async_client = async_client
        self.model        = model
        self.max_tokens   = max_tokens
        self.available    = client is not None and async_client is not None

    def run(self, prompt: str, tools_str: str) -> tuple:
        """Tool-use loop. Returns (success: bool, output: str)."""
        if not self.available:
            return False, "SDK unavailable"
        allowed  = {t.strip() for t in tools_str.split(",") if t.strip()}
        schemas  = [s for s in self._SCHEMAS if s["name"] in allowed]
        messages = [{"role": "user", "content": prompt}]
        try:
            for _ in range(8):  # max 8 tool-use rounds
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    tools=schemas,
                    messages=messages,
                )
                if resp.stop_reason == "end_turn":
                    text = " ".join(
                        b.text for b in resp.content if hasattr(b, "text")
                    ).strip()
                    return True, text
                if resp.stop_reason == "tool_use":
                    messages.append({"role": "assistant", "content": resp.content})
                    results = []
                    for block in resp.content:
                        if block.type == "tool_use":
                            out = self._exec(block.name, block.input)
                            results.append({
                                "type":        "tool_result",
                                "tool_use_id": block.id,
                                "content":     str(out)[:8000],
                            })
                    messages.append({"role": "user", "content": results})
                else:
                    break
        except Exception as exc:
            return False, str(exc)[:200]
        return False, "Tool loop exhausted"

    async def arun(self, prompt: str, tools_str: str) -> tuple:
        """Async tool-use loop — awaitable, for use with asyncio.gather()."""
        if not self.available:
            return False, "SDK unavailable"
        import anthropic as _anthropic
        allowed  = {t.strip() for t in tools_str.split(",") if t.strip()}
        schemas  = [s for s in self._SCHEMAS if s["name"] in allowed]
        messages = [{"role": "user", "content": prompt}]
        _backoff = 5.0  # seconds to wait after a rate limit hit
        try:
            for _ in range(8):
                for _attempt in range(3):  # up to 3 retries on rate limit
                    try:
                        resp = await self.async_client.messages.create(
                            model=self.model,
                            max_tokens=self.max_tokens,
                            tools=schemas,
                            messages=messages,
                        )
                        break
                    except _anthropic.RateLimitError:
                        await asyncio.sleep(_backoff)
                        _backoff = min(_backoff * 2, 60.0)
                else:
                    return False, "Rate limit — retries exhausted"
                if resp.stop_reason == "end_turn":
                    text = " ".join(
                        b.text for b in resp.content if hasattr(b, "text")
                    ).strip()
                    return True, text
                if resp.stop_reason == "tool_use":
                    messages.append({"role": "assistant", "content": resp.content})
                    results = []
                    for block in resp.content:
                        if block.type == "tool_use":
                            out = self._exec(block.name, block.input)
                            results.append({
                                "type":        "tool_result",
                                "tool_use_id": block.id,
                                "content":     str(out)[:8000],
                            })
                    messages.append({"role": "user", "content": results})
                else:
                    break
        except Exception as exc:
            return False, str(exc)[:200]
        return False, "Tool loop exhausted"

    def _exec(self, name: str, args: dict) -> str:
        """Execute one tool call; return string result."""
        try:
            if name == "Read":
                path = args.get("file_path", "")
                if not os.path.isabs(path):
                    path = os.path.join(_SOLO, path)
                with open(path, encoding="utf-8", errors="ignore") as f:
                    return f.read()[:12_000]
            if name == "Glob":
                import glob as _glob
                pattern = args.get("pattern", "")
                base    = args.get("path", _SOLO)
                if not os.path.isabs(str(base)):
                    base = os.path.join(_SOLO, base)
                hits = _glob.glob(os.path.join(base, pattern), recursive=True)
                return "\n".join(hits[:100]) or "(no matches)"
            if name == "Grep":
                import re as _re, glob as _glob
                pattern    = args.get("pattern", "")
                path       = args.get("path", _SOLO)
                file_glob  = args.get("glob", "")
                if not os.path.isabs(str(path)):
                    path = os.path.join(_SOLO, path)
                files = (
                    _glob.glob(os.path.join(path, file_glob), recursive=True)
                    if file_glob and os.path.isdir(path) else [path]
                )
                lines = []
                for fp in files[:20]:
                    if not os.path.isfile(fp):
                        continue
                    with open(fp, encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if _re.search(pattern, line):
                                lines.append(f"{fp}:{i}: {line.rstrip()}")
                                if len(lines) >= 200:
                                    break
                return "\n".join(lines) or "(no matches)"
        except Exception as exc:
            return f"Error: {exc}"
        return f"Unknown tool: {name}"
