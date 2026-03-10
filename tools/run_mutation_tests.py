"""Mutation testing runner — TASK-334 (QA-035).

Thin wrapper around mutmut that:
  - validates mutmut is installed before attempting a run
  - supports a --dry-run mode that reports config without running mutations
  - parses and pretty-prints the mutmut results summary
  - exits 0 on clean (no surviving mutants), 1 if mutants survive

Usage:
    python tools/run_mutation_tests.py [--dry-run] [--max-survivors N]

Options:
    --dry-run           Print config and exit without running mutmut
    --max-survivors N   Exit code 1 if surviving mutants > N (default 0)
    --path PATH         Override paths_to_mutate (passed through to mutmut run)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT  = REPO_ROOT / "pyproject.toml"

MUTMUT_PATHS = [
    "solo_builder/runners/",
    "solo_builder/api/",
    "solo_builder/commands/",
    "solo_builder/utils/",
]


def _check_mutmut_available() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mutmut", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _print_config(max_survivors: int) -> None:
    print("Mutation testing configuration")
    print(f"  config: {PYPROJECT}")
    print(f"  paths:  {', '.join(MUTMUT_PATHS)}")
    print(f"  runner: python -m pytest solo_builder/tests/ -x -q --tb=no")
    print(f"  max-survivors threshold: {max_survivors}")


def _run_mutmut(path_override: str | None) -> int:
    cmd = [sys.executable, "-m", "mutmut", "run"]
    if path_override:
        cmd += ["--paths-to-mutate", path_override]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode


def _parse_results() -> dict:
    """Run mutmut results and parse surviving mutant count."""
    result = subprocess.run(
        [sys.executable, "-m", "mutmut", "results"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    output = result.stdout + result.stderr
    survived = 0
    for line in output.splitlines():
        if "survived" in line.lower():
            parts = line.split()
            for i, p in enumerate(parts):
                if p.isdigit():
                    survived = int(p)
                    break
    return {"raw": output, "survived": survived}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run mutation tests via mutmut (QA-035)."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print config and exit without running mutmut")
    parser.add_argument("--max-survivors", type=int, default=0,
                        help="Acceptable surviving mutant count (default 0)")
    parser.add_argument("--path", default=None,
                        help="Override paths_to_mutate")
    args = parser.parse_args(argv)

    _print_config(args.max_survivors)

    if args.dry_run:
        print("\nDry-run mode — skipping mutmut execution.")
        return 0

    if not _check_mutmut_available():
        print(
            "\nERROR: mutmut is not installed.\n"
            "Install it with:  pip install mutmut\n"
            "Then re-run this script.",
            file=sys.stderr,
        )
        return 2

    rc = _run_mutmut(args.path)
    results = _parse_results()
    print(results["raw"])
    survived = results["survived"]
    print(f"\nSurviving mutants: {survived}  (threshold: {args.max_survivors})")
    if survived > args.max_survivors:
        print(f"FAIL — {survived} mutants survived (>{args.max_survivors} allowed).")
        return 1
    print("PASS — mutation score within threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
