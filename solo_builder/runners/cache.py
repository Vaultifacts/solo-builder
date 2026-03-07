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
    """SHA-256-keyed, disk-backed cache for LLM API responses.

    Per-session hit/miss counters are held in memory; call stats() to read them.
    Disk state (size, clear) reflects the persistent on-disk cache directory.
    Cumulative hit/miss totals are persisted across sessions in session_stats.json.
    """

    # Approximate tokens per cached entry (prompt + response).
    # Used only for the estimated_tokens_saved figure in stats().
    _AVG_TOKENS_PER_ENTRY = 550
    _STATS_FILE = "session_stats.json"

    def __init__(self, cache_dir: str = "") -> None:
        self._dir = Path(cache_dir or os.environ.get("CACHE_DIR", _DEFAULT_CACHE_DIR))
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # cache dir creation failure is non-fatal; get/set will no-op
        self._hits   = 0
        self._misses = 0
        prev = self._load_cumulative()
        self._cum_hits   = prev.get("cumulative_hits", 0)
        self._cum_misses = prev.get("cumulative_misses", 0)

    def _load_cumulative(self) -> dict:
        """Load persisted cumulative stats from disk, returning empty dict on any error."""
        try:
            path = self._dir / self._STATS_FILE
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def persist_stats(self) -> None:
        """Write updated cumulative hit/miss totals to session_stats.json."""
        try:
            data = {
                "cumulative_hits":   self._cum_hits + self._hits,
                "cumulative_misses": self._cum_misses + self._misses,
                "updated_at":        datetime.now(timezone.utc).isoformat(),
            }
            path = self._dir / self._STATS_FILE
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass  # non-fatal

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
            value = data.get("response")
            if value is not None:
                self._hits += 1
                return value
        except Exception:
            pass
        self._misses += 1
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

    def stats(self) -> dict:
        """Return per-session hit/miss counters, cumulative totals, and disk-state summary.

        Keys
        ----
        hits                  : int   — cache hits this session
        misses                : int   — cache misses this session
        cumulative_hits       : int   — total hits across all sessions (prev + current)
        cumulative_misses     : int   — total misses across all sessions (prev + current)
        size                  : int   — entries currently on disk
        estimated_tokens_saved: int   — cumulative_hits × _AVG_TOKENS_PER_ENTRY
        """
        cum_hits   = self._cum_hits + self._hits
        cum_misses = self._cum_misses + self._misses
        return {
            "hits":                   self._hits,
            "misses":                 self._misses,
            "cumulative_hits":        cum_hits,
            "cumulative_misses":      cum_misses,
            "size":                   self.size(),
            "estimated_tokens_saved": cum_hits * self._AVG_TOKENS_PER_ENTRY,
        }


def make_cache(cache_dir: str = "") -> Optional[ResponseCache]:
    """Return a ResponseCache instance, or None if NOCACHE=1 is set.

    This is the preferred factory used by runners so that tests can
    disable caching without touching runner internals.
    """
    if os.environ.get("NOCACHE", "0") == "1":
        return None
    return ResponseCache(cache_dir=cache_dir)
