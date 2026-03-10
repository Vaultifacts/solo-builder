"""Session Context Report — TASK-359 (AI-013).

Displays a human-readable table of context file sizes at session start,
showing lines used, limits, percentage bar, and status.

Usage:
    python tools/session_context_report.py

Always exits 0 — purely informational.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Re-use the canonical file list and thresholds from context_window_check.py
_TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS_DIR))
from context_window_check import _CONTEXT_FILES, DEFAULT_WARN, DEFAULT_ERROR, _count_lines  # noqa: E402


_BAR_WIDTH = 10


def _bar(count: int, limit: int, width: int = _BAR_WIDTH) -> str:
    filled = min(width, round(count / limit * width)) if limit else 0
    return "=" * filled + " " * (width - filled)


def _status_label(count: int, warn: int, error: int) -> str:
    if count >= error:
        return "ERR "
    if count >= warn:
        return "WARN"
    return "OK  "


def report() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Context window report  ({now})")
    print()

    any_warn = False
    any_error = False

    for label, path, warn_ov, error_ov in _CONTEXT_FILES:
        eff_warn  = warn_ov  if warn_ov  is not None else DEFAULT_WARN
        eff_error = error_ov if error_ov is not None else DEFAULT_ERROR
        count = _count_lines(path)
        if count is None:
            print(f"  {label:<28}  (missing)")
            continue
        pct = round(count / eff_error * 100)
        bar = _bar(count, eff_error)
        status = _status_label(count, eff_warn, eff_error)
        print(f"  {label:<28}  {count:>5} / {eff_error:<5}  [{bar}]  {pct:>3}%  {status}")
        if count >= eff_error:
            any_error = True
        elif count >= eff_warn:
            any_warn = True

    print()
    if any_error:
        print("  ACTION REQUIRED: one or more files exceed the error threshold.")
        print("  Run /clear to reset context, or /compact to compress.")
    elif any_warn:
        print("  NOTICE: one or more files are approaching the compaction limit.")
        print("  Consider running /compact soon.")
    else:
        print("  All files within limits.")


def main(argv: list[str] | None = None) -> int:
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
