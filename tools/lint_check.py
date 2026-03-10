"""Lint check runner — TASK-351 (DX-010 to DX-015).

Runs flake8 over the solo_builder source tree and enforces configurable
violation count thresholds.  Designed to be called from CI or pre-release
gates without requiring the developer to parse raw flake8 output.

Features:
  - Per-severity counts (E = errors, W = warnings, F = pyflakes, C = complexity)
  - Configurable max allowed violations per severity via --max-* flags or
    settings.json (LINT_MAX_E, LINT_MAX_W, LINT_MAX_F, LINT_MAX_C)
  - JSON output for machine consumption
  - Quiet mode for gate integration

Exit codes:
  0 — lint passed (all counts within thresholds)
  1 — threshold exceeded
  2 — flake8 not found or other execution error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT     = Path(__file__).resolve().parent.parent
SOURCE_DIR    = REPO_ROOT / "solo_builder"
SETTINGS_PATH = REPO_ROOT / "solo_builder" / "config" / "settings.json"

_LINT_DEFAULTS: dict[str, Any] = {
    "LINT_MAX_E": 0,    # zero-tolerance for errors
    "LINT_MAX_W": 50,   # some warnings tolerated
    "LINT_MAX_F": 0,    # zero-tolerance for pyflakes issues
    "LINT_MAX_C": 10,   # complexity notices
}

# Violation line pattern: path:line:col: CODE message
_VIOLATION_RE = re.compile(r"^[^:]+:\d+:\d+:\s+([A-Z])(\d+)\s+")


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LintThresholds:
    max_e: int = 0
    max_w: int = 50
    max_f: int = 0
    max_c: int = 10


def load_lint_thresholds(settings_path: Path | None = None) -> LintThresholds:
    if settings_path is None:
        settings_path = SETTINGS_PATH
    settings: dict = {}
    try:
        settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    def _get(key: str) -> int:
        return int(settings.get(key, _LINT_DEFAULTS[key]))

    return LintThresholds(
        max_e=_get("LINT_MAX_E"),
        max_w=_get("LINT_MAX_W"),
        max_f=_get("LINT_MAX_F"),
        max_c=_get("LINT_MAX_C"),
    )


# ---------------------------------------------------------------------------
# Lint result
# ---------------------------------------------------------------------------

@dataclass
class LintReport:
    counts:     dict[str, int] = field(default_factory=lambda: {"E": 0, "W": 0, "F": 0, "C": 0})
    violations: list[str]      = field(default_factory=list)
    thresholds: LintThresholds = field(default_factory=LintThresholds)
    exceeded:   list[str]      = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.exceeded

    def to_dict(self) -> dict:
        return {
            "passed":     self.passed,
            "counts":     self.counts,
            "thresholds": {
                "max_e": self.thresholds.max_e,
                "max_w": self.thresholds.max_w,
                "max_f": self.thresholds.max_f,
                "max_c": self.thresholds.max_c,
            },
            "exceeded":   self.exceeded,
            "violations": self.violations,
        }


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def _parse_counts(output: str) -> tuple[dict[str, int], list[str]]:
    """Parse flake8 stdout into per-letter counts and violation lines."""
    counts: dict[str, int] = {"E": 0, "W": 0, "F": 0, "C": 0}
    violations: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        violations.append(line)
        m = _VIOLATION_RE.match(line)
        if m:
            letter = m.group(1)
            if letter in counts:
                counts[letter] += 1
    return counts, violations


def run_lint(
    source_dir: Path | str | None = None,
    thresholds: LintThresholds | None = None,
    settings_path: Path | str | None = None,
    flake8_args: list[str] | None = None,
) -> LintReport:
    """Run flake8 and return a LintReport."""
    if source_dir is None:
        source_dir = SOURCE_DIR
    source_dir = Path(source_dir)

    if thresholds is None:
        thresholds = load_lint_thresholds(
            settings_path=Path(settings_path) if settings_path else None
        )

    cmd = [sys.executable, "-m", "flake8"]
    if flake8_args:
        cmd.extend(flake8_args)
    cmd.append(str(source_dir))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )
    except FileNotFoundError:
        raise RuntimeError("flake8 not found — install it with: pip install flake8")
    except subprocess.TimeoutExpired:
        raise RuntimeError("flake8 timed out after 120s")

    counts, violations = _parse_counts(result.stdout)

    exceeded: list[str] = []
    if counts["E"] > thresholds.max_e:
        exceeded.append(
            f"E: {counts['E']} violations > max {thresholds.max_e}"
        )
    if counts["W"] > thresholds.max_w:
        exceeded.append(
            f"W: {counts['W']} violations > max {thresholds.max_w}"
        )
    if counts["F"] > thresholds.max_f:
        exceeded.append(
            f"F: {counts['F']} violations > max {thresholds.max_f}"
        )
    if counts["C"] > thresholds.max_c:
        exceeded.append(
            f"C: {counts['C']} violations > max {thresholds.max_c}"
        )

    return LintReport(
        counts=counts,
        violations=violations,
        thresholds=thresholds,
        exceeded=exceeded,
    )


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    source_dir: Path | str | None = None,
    thresholds: LintThresholds | None = None,
    settings_path: Path | str | None = None,
) -> int:
    try:
        report = run_lint(
            source_dir=source_dir,
            thresholds=thresholds,
            settings_path=settings_path,
        )
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 0 if report.passed else 1

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Lint Check Report")
            print()
            c = report.counts
            print(f"  E (errors)     : {c['E']:4d}  (max {report.thresholds.max_e})")
            print(f"  W (warnings)   : {c['W']:4d}  (max {report.thresholds.max_w})")
            print(f"  F (pyflakes)   : {c['F']:4d}  (max {report.thresholds.max_f})")
            print(f"  C (complexity) : {c['C']:4d}  (max {report.thresholds.max_c})")
            if report.exceeded:
                print(f"\n  Threshold breaches ({len(report.exceeded)}):")
                for e in report.exceeded:
                    print(f"    [FAIL] {e}")
            print()
            if exit_code == 0:
                print("Lint check passed.")
            else:
                print("Lint check failed — thresholds exceeded.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run flake8 with configurable violation thresholds."
    )
    parser.add_argument("--json",      action="store_true", dest="as_json")
    parser.add_argument("--quiet",     action="store_true")
    parser.add_argument("--source",    default="", help="Override source directory")
    parser.add_argument("--settings",  default="", help="Override settings.json path")
    parser.add_argument("--max-e",     type=int, default=None,
                        help="Max allowed E (error) violations")
    parser.add_argument("--max-w",     type=int, default=None,
                        help="Max allowed W (warning) violations")
    parser.add_argument("--max-f",     type=int, default=None,
                        help="Max allowed F (pyflakes) violations")
    parser.add_argument("--max-c",     type=int, default=None,
                        help="Max allowed C (complexity) violations")
    args = parser.parse_args(argv)

    thresholds = None
    if any(v is not None for v in (args.max_e, args.max_w, args.max_f, args.max_c)):
        base = load_lint_thresholds(settings_path=args.settings or None)
        thresholds = LintThresholds(
            max_e=args.max_e if args.max_e is not None else base.max_e,
            max_w=args.max_w if args.max_w is not None else base.max_w,
            max_f=args.max_f if args.max_f is not None else base.max_f,
            max_c=args.max_c if args.max_c is not None else base.max_c,
        )

    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        source_dir=args.source or None,
        thresholds=thresholds,
        settings_path=args.settings or None,
    )


if __name__ == "__main__":
    sys.exit(main())
