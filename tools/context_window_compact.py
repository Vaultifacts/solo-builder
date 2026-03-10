"""Context window auto-compaction — TASK-359 (AI-014 to AI-016).

Evaluates context_window_budget and triggers compaction actions for any file
at critical or over_budget status.

Compaction strategies by file:
  JOURNAL.md  — archive entries older than --older-than days via archive_journal.py
  MEMORY.md   — truncate to budget (keep first N lines)
  CLAUDE.md   — warning only (manual compaction required)

Usage:
  python tools/context_window_compact.py
  python tools/context_window_compact.py --dry-run      # show what would happen
  python tools/context_window_compact.py --json --quiet
  python tools/context_window_compact.py --threshold critical  # compact at critical+

Exit codes:
  0 — no compaction needed (all files below threshold)
  1 — compaction performed (or needed in dry-run)
  2 — error
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parent.parent
ARCHIVE_DIR  = REPO_ROOT / "claude" / "journal_archive"
TOOLS_DIR    = Path(__file__).resolve().parent


def _load_tool(name: str):
    """Load a tool module from tools/ by name; cache in sys.modules."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CompactionAction:
    label:        str           # CLAUDE.md / MEMORY.md / JOURNAL.md
    path:         str
    action:       str           # archived | truncated | warning_only | skipped | error
    lines_before: int | None = None
    lines_after:  int | None = None
    message:      str = ""

    def to_dict(self) -> dict:
        return {
            "label":        self.label,
            "path":         self.path,
            "action":       self.action,
            "lines_before": self.lines_before,
            "lines_after":  self.lines_after,
            "message":      self.message,
        }


@dataclass
class CompactionReport:
    actions:  list[CompactionAction] = field(default_factory=list)
    dry_run:  bool = False

    @property
    def has_actions(self) -> bool:
        return any(a.action not in ("skipped",) for a in self.actions)

    def to_dict(self) -> dict:
        return {
            "has_actions": self.has_actions,
            "dry_run":     self.dry_run,
            "actions":     [a.to_dict() for a in self.actions],
        }


# ---------------------------------------------------------------------------
# Compaction helpers
# ---------------------------------------------------------------------------

_COMPACT_STATUSES = ("critical", "over_budget")


def _compact_journal(
    journal_path: Path,
    archive_dir: Path,
    older_than: int = 14,
    dry_run: bool = False,
) -> CompactionAction:
    """Archive journal entries older than *older_than* days."""
    lines_before = None
    if journal_path.exists():
        try:
            lines_before = sum(1 for _ in journal_path.open(encoding="utf-8", errors="replace"))
        except OSError:
            pass

    if dry_run:
        return CompactionAction(
            label="JOURNAL.md", path=str(journal_path),
            action="archived", lines_before=lines_before, lines_after=None,
            message=f"[dry-run] would archive entries older than {older_than} days",
        )

    try:
        aj = _load_tool("archive_journal")
        rc = aj.run(older_than=older_than, dry_run=False, quiet=True)
        lines_after = None
        if journal_path.exists():
            try:
                lines_after = sum(1 for _ in journal_path.open(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        reduced = (lines_before or 0) - (lines_after or 0)
        return CompactionAction(
            label="JOURNAL.md", path=str(journal_path),
            action="archived", lines_before=lines_before, lines_after=lines_after,
            message=f"Archived entries older than {older_than} days (−{reduced} lines)",
        )
    except Exception as exc:
        return CompactionAction(
            label="JOURNAL.md", path=str(journal_path),
            action="error", lines_before=lines_before, lines_after=None,
            message=str(exc),
        )


def _truncate_file(
    label: str,
    file_path: Path,
    budget: int,
    dry_run: bool = False,
) -> CompactionAction:
    """Truncate a text file to *budget* lines, keeping the first N lines."""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, FileNotFoundError):
        return CompactionAction(
            label=label, path=str(file_path),
            action="error", message="File not found or unreadable",
        )

    lines_before = len(lines)
    if lines_before <= budget:
        return CompactionAction(
            label=label, path=str(file_path),
            action="skipped", lines_before=lines_before, lines_after=lines_before,
            message="Already within budget",
        )

    if dry_run:
        return CompactionAction(
            label=label, path=str(file_path),
            action="truncated", lines_before=lines_before, lines_after=budget,
            message=f"[dry-run] would truncate {lines_before} → {budget} lines",
        )

    try:
        file_path.write_text("".join(lines[:budget]), encoding="utf-8")
    except OSError as exc:
        return CompactionAction(
            label=label, path=str(file_path),
            action="error", lines_before=lines_before,
            message=str(exc),
        )

    return CompactionAction(
        label=label, path=str(file_path),
        action="truncated", lines_before=lines_before, lines_after=budget,
        message=f"Truncated {lines_before} → {budget} lines",
    )


# ---------------------------------------------------------------------------
# Core compact()
# ---------------------------------------------------------------------------

def compact(
    budget_report=None,
    settings_path=None,
    dry_run: bool = False,
    threshold: str = "critical",
    older_than: int = 14,
) -> CompactionReport:
    """Evaluate budget and compact files at or above *threshold* status.

    *threshold* — one of: "warn", "critical", "over_budget"
    Files below threshold are skipped.
    """
    cwb = _load_tool("context_window_budget")

    if budget_report is None:
        budget_report = cwb.check_budget(
            settings_path=Path(settings_path) if settings_path else None
        )

    # Determine which statuses trigger compaction
    all_statuses = ["warn", "critical", "over_budget"]
    trigger_from = all_statuses.index(threshold) if threshold in all_statuses else 1
    trigger_statuses = set(all_statuses[trigger_from:])

    report = CompactionReport(dry_run=dry_run)

    for result in budget_report.results:
        if result.status not in trigger_statuses:
            report.actions.append(CompactionAction(
                label=result.label, path=result.path,
                action="skipped",
                lines_before=result.lines,
                lines_after=result.lines,
                message=f"Status '{result.status}' below threshold '{threshold}'",
            ))
            continue

        path = Path(result.path)
        label = result.label

        if label == "JOURNAL.md":
            action = _compact_journal(
                journal_path=path,
                archive_dir=ARCHIVE_DIR,
                older_than=older_than,
                dry_run=dry_run,
            )
        elif label == "MEMORY.md":
            action = _truncate_file(
                label=label,
                file_path=path,
                budget=result.budget,
                dry_run=dry_run,
            )
        else:
            # CLAUDE.md and others — warning only, cannot auto-compact
            action = CompactionAction(
                label=label, path=result.path,
                action="warning_only",
                lines_before=result.lines, lines_after=result.lines,
                message=(
                    f"{label} is {result.status} ({result.lines}/{result.budget} lines). "
                    "Manual compaction required."
                ),
            )

        report.actions.append(action)

    return report


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    dry_run: bool = False,
    threshold: str = "critical",
    older_than: int = 14,
    settings_path=None,
) -> int:
    try:
        report = compact(
            dry_run=dry_run,
            threshold=threshold,
            older_than=older_than,
            settings_path=settings_path,
        )
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 1 if report.has_actions else 0

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            prefix = "[DRY-RUN] " if dry_run else ""
            print(f"{prefix}Context Window Compaction")
            print()
            for a in report.actions:
                if a.action == "skipped":
                    continue
                icon = {"archived": "📦", "truncated": "✂", "warning_only": "⚠",
                        "error": "✗"}.get(a.action, "?")
                before = f"{a.lines_before}" if a.lines_before is not None else "?"
                after  = (f" → {a.lines_after}" if a.lines_after is not None
                          and a.lines_after != a.lines_before else "")
                print(f"  [{a.action:<12}]  {a.label:<14}  {before}{after}  {a.message}")
            print()
            if exit_code == 0:
                print("No compaction needed.")
            elif dry_run:
                print("Compaction actions identified (dry-run — no changes made).")
            else:
                print("Compaction complete.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auto-compact context files above budget threshold."
    )
    parser.add_argument("--json",        action="store_true", dest="as_json")
    parser.add_argument("--quiet",       action="store_true")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--threshold",   default="critical",
                        choices=["warn", "critical", "over_budget"],
                        help="Minimum budget status to trigger compaction (default: critical)")
    parser.add_argument("--older-than",  type=int, default=14, dest="older_than",
                        help="Archive journal entries older than N days (default: 14)")
    parser.add_argument("--settings",    default="", help="Override settings.json path")
    args = parser.parse_args(argv)
    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        dry_run=args.dry_run,
        threshold=args.threshold,
        older_than=args.older_than,
        settings_path=args.settings or None,
    )


if __name__ == "__main__":
    sys.exit(main())
