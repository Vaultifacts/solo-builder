"""Standalone cache statistics reporter.

Usage
-----
    python tools/cache_stats.py [--clear]

Prints a summary of the disk-backed response cache (solo_builder/runners/cache.py):
  - Number of entries on disk
  - Total estimated tokens those entries represent
  - Cache directory path

Pass --clear to delete all cached entries after printing the summary.
"""
import argparse
import os
import sys
from pathlib import Path

# Resolve repo root (tools/ → repo root)
_ROOT = Path(__file__).resolve().parent.parent
_SOLO = _ROOT / "solo_builder"

if str(_SOLO) not in sys.path:
    sys.path.insert(0, str(_SOLO))

from runners.cache import ResponseCache, _DEFAULT_CACHE_DIR  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Show disk-backed LLM response cache stats.")
    parser.add_argument("--clear", action="store_true", help="Delete all cached entries after printing stats.")
    args = parser.parse_args()

    cache_dir = os.environ.get("CACHE_DIR", _DEFAULT_CACHE_DIR)
    cache = ResponseCache(cache_dir=cache_dir)

    disk_size = cache.size()
    est_tokens = disk_size * ResponseCache._AVG_TOKENS_PER_ENTRY

    print(f"Cache directory : {cache_dir}")
    print(f"Entries on disk : {disk_size}")
    print(f"Est. tokens held: {est_tokens:,}  (~{est_tokens / 1_000_000:.3f}M tokens)")

    if args.clear:
        deleted = cache.clear()
        print(f"Cleared         : {deleted} entries deleted")
    else:
        print("(Pass --clear to wipe the cache)")


if __name__ == "__main__":
    main()
