"""Context Window Monitor — TASK-332 (AI-008).

Checks the line counts of key context files (CLAUDE.md, MEMORY.md, JOURNAL.md)
against configurable warning and error thresholds.  Exits:
  0 — all files within thresholds
  1 — one or more files exceed the error threshold
  2 — usage or path error

Usage:
    python tools/context_window_check.py [--warn N] [--error N] [--json]

Options:
    --warn N    Lines-per-file warning threshold (default 150)
    --error N   Lines-per-file error threshold   (default 200)
    --json      Output machine-readable JSON instead of plain text
    --quiet     Suppress output (still exits non-zero on breach)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Files to check — resolved relative to the repository root
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

# Each entry: (label, path, warn_override, error_override)
# warn/error overrides are None → use the global threshold.
_CONTEXT_FILES: list[tuple[str, Path, int | None, int | None]] = [
    ("CLAUDE.md (project)",  REPO_ROOT / "CLAUDE.md",                     None, None),
    ("MEMORY.md",            Path.home() / ".claude" / "projects" /
                             "C--Users-Matt1-OneDrive-Desktop-Solo-Builder" /
                             "memory" / "MEMORY.md",                       None, None),
    # JOURNAL.md is append-only — use higher per-file thresholds
    ("JOURNAL.md",           REPO_ROOT / "claude" / "JOURNAL.md",         500,  1000),
]

DEFAULT_WARN  = 150
DEFAULT_ERROR = 200


def _count_lines(path: Path) -> int | None:
    """Return line count or None if file is absent/unreadable."""
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def check(warn: int = DEFAULT_WARN, error: int = DEFAULT_ERROR,
          quiet: bool = False, as_json: bool = False) -> int:
    """Run the check; return exit code (0=ok, 1=error threshold exceeded)."""
    results: list[dict] = []
    exit_code = 0

    for label, path, warn_ov, error_ov in _CONTEXT_FILES:
        eff_warn  = warn_ov  if warn_ov  is not None else warn
        eff_error = error_ov if error_ov is not None else error
        count = _count_lines(path)
        if count is None:
            status = "missing"
        elif count >= eff_error:
            status = "error"
            exit_code = 1
        elif count >= eff_warn:
            status = "warn"
        else:
            status = "ok"
        results.append({
            "file":   label,
            "path":   str(path),
            "lines":  count,
            "status": status,
        })

    if not quiet:
        if as_json:
            print(json.dumps({"results": results, "exit_code": exit_code},
                             ensure_ascii=False))
        else:
            print("Context window check")
            print(f"  warn={warn}  error={error}")
            print()
            for r in results:
                lines_str = str(r["lines"]) if r["lines"] is not None else "N/A"
                flag = {"ok": "OK", "warn": "WARN", "error": "ERR", "missing": "???"}.get(
                    r["status"], "???"
                )
                print(f"  {flag}  {r['file']:<35}  {lines_str:>6} lines  [{r['status']}]")
            print()
            if exit_code:
                print("ERROR: one or more files exceed the error threshold.")
            else:
                print("All files within thresholds.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check context-window file sizes against thresholds."
    )
    parser.add_argument("--warn",  type=int, default=DEFAULT_WARN,
                        help=f"Warning threshold in lines (default {DEFAULT_WARN})")
    parser.add_argument("--error", type=int, default=DEFAULT_ERROR,
                        help=f"Error threshold in lines (default {DEFAULT_ERROR})")
    parser.add_argument("--json",  action="store_true", dest="as_json",
                        help="Output JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress output")
    args = parser.parse_args(argv)

    if args.warn >= args.error:
        print("ERROR: --warn must be less than --error", file=sys.stderr)
        return 2

    return check(warn=args.warn, error=args.error,
                 quiet=args.quiet, as_json=args.as_json)


if __name__ == "__main__":
    sys.exit(main())
