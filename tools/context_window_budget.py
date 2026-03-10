"""Context window budget tracker — TASK-355 (AI-008 to AI-013).

Extends the basic context_window_check.py with per-file utilization budgets
and actionable compaction recommendations.

Each tracked file has:
  - A line-count budget (configurable per file via settings.json)
  - A utilization percentage  (lines / budget * 100)
  - A status: ok / warn / critical / over_budget

Thresholds:
  warn     — utilization >= BUDGET_WARN_PCT  (default 70%)
  critical — utilization >= BUDGET_CRIT_PCT  (default 90%)
  over     — lines > budget

Budget keys in settings.json:
  CW_BUDGET_CLAUDE_MD    (default 200 lines)
  CW_BUDGET_MEMORY_MD    (default 200 lines)
  CW_BUDGET_JOURNAL_MD   (default 1000 lines)
  CW_BUDGET_WARN_PCT     (default 70)
  CW_BUDGET_CRIT_PCT     (default 90)

Exit codes:
  0 — all files within budget (below warn threshold)
  1 — at least one file is warn / critical / over budget
  2 — usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = REPO_ROOT / "solo_builder" / "config" / "settings.json"

_BUDGET_DEFAULTS: dict[str, Any] = {
    "CW_BUDGET_CLAUDE_MD":  200,
    "CW_BUDGET_MEMORY_MD":  200,
    "CW_BUDGET_JOURNAL_MD": 1000,
    "CW_BUDGET_WARN_PCT":   70,
    "CW_BUDGET_CRIT_PCT":   90,
}

_TRACKED_FILES = [
    ("CLAUDE.md",   REPO_ROOT / "CLAUDE.md",               "CW_BUDGET_CLAUDE_MD"),
    ("MEMORY.md",   Path.home() / ".claude" / "projects" /
                    "C--Users-Matt1-OneDrive-Desktop-Solo-Builder" /
                    "memory" / "MEMORY.md",                 "CW_BUDGET_MEMORY_MD"),
    ("JOURNAL.md",  REPO_ROOT / "claude" / "JOURNAL.md",   "CW_BUDGET_JOURNAL_MD"),
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BudgetConfig:
    budgets:   dict[str, int]   # label -> line budget
    warn_pct:  float = 70.0
    crit_pct:  float = 90.0


def load_budget_config(settings_path: Path | None = None) -> BudgetConfig:
    if settings_path is None:
        settings_path = SETTINGS_PATH
    settings: dict = {}
    try:
        settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    def _int(key: str) -> int:
        return int(settings.get(key, _BUDGET_DEFAULTS[key]))

    def _float(key: str) -> float:
        return float(settings.get(key, _BUDGET_DEFAULTS[key]))

    budgets = {
        label: _int(budget_key)
        for label, _, budget_key in _TRACKED_FILES
    }
    return BudgetConfig(
        budgets=budgets,
        warn_pct=_float("CW_BUDGET_WARN_PCT"),
        crit_pct=_float("CW_BUDGET_CRIT_PCT"),
    )


# ---------------------------------------------------------------------------
# Per-file result
# ---------------------------------------------------------------------------

@dataclass
class FileResult:
    label:       str
    path:        str
    lines:       int | None
    budget:      int
    utilization: float          # 0–100+ %
    status:      str            # ok | warn | critical | over_budget | missing

    def to_dict(self) -> dict:
        return {
            "label":       self.label,
            "path":        self.path,
            "lines":       self.lines,
            "budget":      self.budget,
            "utilization": round(self.utilization, 1),
            "status":      self.status,
        }


@dataclass
class BudgetReport:
    results:  list[FileResult] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return any(r.status != "ok" and r.status != "missing" for r in self.results)

    def to_dict(self) -> dict:
        return {
            "has_issues": self.has_issues,
            "results":    [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def _count_lines(path: Path) -> int | None:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def check_budget(
    config: BudgetConfig | None = None,
    settings_path: Path | str | None = None,
    tracked_files: list[tuple[str, Path, str]] | None = None,
) -> BudgetReport:
    if config is None:
        config = load_budget_config(
            settings_path=Path(settings_path) if settings_path else None
        )
    if tracked_files is None:
        tracked_files = _TRACKED_FILES

    report = BudgetReport()

    for label, path, budget_key in tracked_files:
        budget = config.budgets.get(label, _BUDGET_DEFAULTS.get(budget_key, 200))
        lines = _count_lines(path)

        if lines is None:
            status = "missing"
            util = 0.0
        else:
            util = (lines / budget * 100) if budget > 0 else 0.0
            if lines > budget:
                status = "over_budget"
            elif util >= config.crit_pct:
                status = "critical"
            elif util >= config.warn_pct:
                status = "warn"
            else:
                status = "ok"

        report.results.append(FileResult(
            label=label,
            path=str(path),
            lines=lines,
            budget=budget,
            utilization=util,
            status=status,
        ))

    return report


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    settings_path: Path | str | None = None,
    config: BudgetConfig | None = None,
) -> int:
    try:
        report = check_budget(config=config, settings_path=settings_path)
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 1 if report.has_issues else 0

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Context Window Budget")
            print()
            _STATUS_ICON = {
                "ok":          "OK  ",
                "warn":        "WARN",
                "critical":    "CRIT",
                "over_budget": "OVER",
                "missing":     "??? ",
            }
            for r in report.results:
                icon = _STATUS_ICON.get(r.status, "????")
                lines_str = f"{r.lines:5d}" if r.lines is not None else "  N/A"
                util_str  = f"{r.utilization:5.1f}%" if r.lines is not None else "    N/A"
                print(f"  [{icon}]  {r.label:<14}  {lines_str} / {r.budget:<5} lines"
                      f"  {util_str}")
            print()
            if exit_code == 0:
                print("All files within budget.")
            else:
                print("Budget pressure detected — consider compacting large files.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Track per-file context window budget utilization."
    )
    parser.add_argument("--json",     action="store_true", dest="as_json")
    parser.add_argument("--quiet",    action="store_true")
    parser.add_argument("--settings", default="", help="Override settings.json path")
    args = parser.parse_args(argv)
    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        settings_path=args.settings or None,
    )


if __name__ == "__main__":
    sys.exit(main())
