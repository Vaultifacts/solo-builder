"""Disk-backed response cache for Anthropic API calls.

Cache entries are stored as individual JSON files under CACHE_DIR
(default: <repo_root>/claude/cache/).

Key:    SHA-256 hex digest of the prompt (or multiple joined inputs).
Value:  JSON with 'response', 'prompt_hash', and 'cached_at' fields.

Environment variables
---------------------
CACHE_DIR   Override the default cache directory path.
NOCACHE     Set to '1' to disable caching entirely (make_cache() returns None).
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Repo root: solo_builder/runners/ -> solo_builder/ -> repo root
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_CACHE_DIR = os.path.join(_REPO_ROOT, "claude", "cache")


class ResponseCache:
    """SHA-256-keyed, disk-backed cache for LLM API responses."""

    def __init__(self, cache_dir: str = "") -> None:
        self._dir = Path(cache_dir or os.environ.get("CACHE_DIR", _DEFAULT_CACHE_DIR))
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # cache dir creation failure is non-fatal; get/set will no-op

    # ── Key construction ──────────────────────────────────────────────────────

    @staticmethod
    def make_key(*parts: str) -> str:
        """Return SHA-256 hex digest of the NUL-joined input parts.

        Usage:
            key = ResponseCache.make_key(prompt)               # single input
            key = ResponseCache.make_key(prompt, tools_str)    # composite key
        """
        raw = "\0".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ── Cache access ──────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[str]:
        """Return the cached response string for *key*, or None on miss."""
        path = self._dir / f"{key}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("response")
        except Exception:
            return None

    def set(self, key: str, response: str) -> None:
        """Store *response* under *key*. Silently ignores write errors."""
        path = self._dir / f"{key}.json"
        entry = {
            "prompt_hash": key,
            "response": response,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            path.write_text(
                json.dumps(entry, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass  # write failure is non-fatal

    # ── Housekeeping ──────────────────────────────────────────────────────────

    def clear(self) -> int:
        """Delete all cached entries. Returns count of files deleted."""
        count = 0
        try:
            for f in self._dir.glob("*.json"):
                try:
                    f.unlink()
                    count += 1
                except OSError:
                    pass
        except Exception:
            pass
        return count

    def size(self) -> int:
        """Return number of cached entries currently on disk."""
        try:
            return sum(1 for _ in self._dir.glob("*.json"))
        except Exception:
            return 0


def make_cache(cache_dir: str = "") -> Optional[ResponseCache]:
    """Return a ResponseCache instance, or None if NOCACHE=1 is set.

    This is the preferred factory used by runners so that tests can
    disable caching without touching runner internals.
    """
    if os.environ.get("NOCACHE", "0") == "1":
        return None
    return ResponseCache(cache_dir=cache_dir)
