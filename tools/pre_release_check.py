"""Pre-release check — TASK-340 (RD-001, RD-002).

Runs all verification gates and generates a release readiness checklist.
Exits 0 only when all required gates pass.

Usage:
    python tools/pre_release_check.py [--json] [--quiet]

Options:
    --json    Output machine-readable JSON
    --quiet   Suppress text output

Exit codes:
    0 — all required gates passed (release ready)
    1 — one or more required gates failed
    2 — usage / environment error
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFY_JSON = REPO_ROOT / "claude" / "VERIFY.json"

_PYTHON = sys.executable


class GateResult(NamedTuple):
    name:     str
    command:  str
    required: bool
    passed:   bool
    output:   str
    duration_s: float


def _run_gate(name: str, command: str, timeout: int = 120) -> tuple[bool, str, float]:
    """Run a shell command; return (passed, output, duration_s)."""
    import time
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(REPO_ROOT),
        )
        elapsed = round(time.monotonic() - t0, 2)
        passed = result.returncode == 0
        output = (result.stdout + result.stderr).strip()[:500]
        return passed, output, elapsed
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s", round(time.monotonic() - t0, 2)
    except Exception as exc:
        return False, str(exc)[:200], 0.0


def _load_verify_gates() -> list[dict]:
    """Load gates from claude/VERIFY.json."""
    try:
        return json.loads(VERIFY_JSON.read_text(encoding="utf-8")).get("commands", [])
    except (OSError, json.JSONDecodeError):
        return []


# ---------------------------------------------------------------------------
# Built-in gates (always run, not from VERIFY.json)
# ---------------------------------------------------------------------------

def _builtin_gates() -> list[dict]:
    return [
        {
            "name":     "python-tests",
            "command":  f'"{_PYTHON}" -m pytest solo_builder/tests/ solo_builder/api/test_app.py -q --tb=no',
            "required": True,
            "timeout_sec": 120,
        },
        {
            "name":     "git-clean",
            "command":  "git status --porcelain",
            "required": False,
            "timeout_sec": 10,
        },
        {
            "name":     "context-window",
            "command":  f'"{_PYTHON}" tools/context_window_check.py --quiet',
            "required": False,
            "timeout_sec": 10,
        },
        {
            "name":     "slo-check",
            "command":  f'"{_PYTHON}" tools/slo_check.py --quiet',
            "required": False,
            "timeout_sec": 10,
        },
    ]


def run_checks(quiet: bool = False, as_json: bool = False) -> int:
    """Run all gates; return 0 if all required gates pass, 1 otherwise."""
    verify_gates = _load_verify_gates()
    all_gates = _builtin_gates() + [
        g for g in verify_gates if g["name"] not in {"unittest-discover"}
    ]

    results: list[GateResult] = []
    for g in all_gates:
        passed, output, dur = _run_gate(g["name"], g["command"], g.get("timeout_sec", 60))
        results.append(GateResult(
            name=g["name"],
            command=g["command"],
            required=g.get("required", False),
            passed=passed,
            output=output,
            duration_s=dur,
        ))

    exit_code = 0 if all(r.passed for r in results if r.required) else 1

    if not quiet:
        if as_json:
            print(json.dumps({
                "timestamp": datetime.datetime.now().isoformat(),
                "release_ready": exit_code == 0,
                "gates": [r._asdict() for r in results],
            }, ensure_ascii=False))
        else:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            print(f"Pre-release check  {now}")
            print()
            for r in results:
                req = "[REQ]" if r.required else "[OPT]"
                flag = "PASS" if r.passed else "FAIL"
                print(f"  {flag}  {req}  {r.name:<30}  ({r.duration_s:.1f}s)")
                if not r.passed and r.output:
                    for line in r.output.splitlines()[:3]:
                        print(f"        {line}")
            print()
            if exit_code == 0:
                print("RELEASE READY — all required gates passed.")
            else:
                print("NOT READY — one or more required gates failed.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pre-release gates.")
    parser.add_argument("--json",  action="store_true", dest="as_json",
                        help="Output JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress output")
    args = parser.parse_args(argv)
    return run_checks(quiet=args.quiet, as_json=args.as_json)


if __name__ == "__main__":
    sys.exit(main())
