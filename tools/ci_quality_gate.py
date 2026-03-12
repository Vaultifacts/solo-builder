"""CI Quality Gate — TASK-343 (DX, DevOps).

Runs all six quality tools in sequence and reports a consolidated pass/fail.
Designed to be the single command run before every merge or release.

Tools run (in order):
  1. threat_model_check  — docs/THREAT_MODEL.md freshness (SE-001 to SE-006)
  2. context_window_check — CLAUDE.md / MEMORY.md / JOURNAL.md line counts
  3. slo_check           — SLO-003 SDK success rate + SLO-005 latency median
  4. dep_audit           — pip-audit dependency vulnerability scan
  5. debt_scan           — TODO/FIXME/HACK/XXX code marker count gate
  6. pre_release_check   — full VERIFY.json gate runner

Exit codes:
  0 — all required tools passed
  1 — one or more required tools failed
  2 — usage error

Usage:
  python tools/ci_quality_gate.py [--json] [--quiet] [--skip TOOL[,TOOL...]]
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
_PYTHON   = sys.executable


class ToolResult(NamedTuple):
    name:       str
    command:    str
    required:   bool
    passed:     bool
    output:     str
    duration_s: float


def _run_tool(name: str, command: str, timeout: int = 120) -> ToolResult:
    """Run *command*; return a ToolResult."""
    import shlex
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            shlex.split(command), shell=False, capture_output=True, text=True,
            timeout=timeout, cwd=str(REPO_ROOT),
        )
        elapsed = round(time.monotonic() - t0, 2)
        passed  = result.returncode == 0
        output  = (result.stdout + result.stderr).strip()[:600]
        return ToolResult(name=name, command=command, required=True,
                          passed=passed, output=output, duration_s=elapsed)
    except subprocess.TimeoutExpired:
        return ToolResult(name=name, command=command, required=True,
                          passed=False,
                          output=f"TIMEOUT after {timeout}s",
                          duration_s=round(time.monotonic() - t0, 2))
    except Exception as exc:
        return ToolResult(name=name, command=command, required=True,
                          passed=False, output=str(exc)[:200], duration_s=0.0)


def _tool_definitions() -> list[dict]:
    """Return ordered list of quality tool definitions."""
    return [
        {
            "name":    "threat-model",
            "command": f'"{_PYTHON}" tools/threat_model_check.py --quiet',
            "timeout": 10,
        },
        {
            "name":    "context-window",
            "command": f'"{_PYTHON}" tools/context_window_check.py --quiet',
            "timeout": 10,
        },
        {
            "name":    "slo-check",
            "command": f'"{_PYTHON}" tools/slo_check.py --quiet',
            "timeout": 10,
        },
        {
            "name":    "dep-audit",
            "command": f'"{_PYTHON}" tools/dep_audit.py --quiet',
            "timeout": 60,
        },
        {
            "name":    "debt-scan",
            "command": f'"{_PYTHON}" tools/debt_scan.py --quiet',
            "timeout": 30,
        },
        {
            "name":    "pre-release",
            "command": f'"{_PYTHON}" tools/pre_release_check.py --quiet',
            "timeout": 180,
        },
    ]


def run_gate(
    quiet: bool = False,
    as_json: bool = False,
    skip: set[str] | None = None,
) -> int:
    """Run all quality tools; return 0 if all required pass, 1 otherwise."""
    skip = skip or set()
    tool_defs = [t for t in _tool_definitions() if t["name"] not in skip]

    results: list[ToolResult] = []
    for td in tool_defs:
        r = _run_tool(td["name"], td["command"], td.get("timeout", 60))
        results.append(r)

    exit_code = 0 if all(r.passed for r in results if r.required) else 1

    if not quiet:
        if as_json:
            print(json.dumps({
                "timestamp":    datetime.datetime.now().isoformat(),
                "gate_passed":  exit_code == 0,
                "tools_run":    len(results),
                "tools_passed": sum(1 for r in results if r.passed),
                "tools_failed": sum(1 for r in results if not r.passed),
                "results":      [r._asdict() for r in results],
            }, ensure_ascii=False))
        else:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            print(f"CI Quality Gate  {now}")
            print()
            for r in results:
                flag = "PASS" if r.passed else "FAIL"
                print(f"  {flag}  {r.name:<22}  ({r.duration_s:.1f}s)")
                if not r.passed and r.output:
                    for line in r.output.splitlines()[:3]:
                        print(f"        {line}")
            print()
            total   = len(results)
            passed  = sum(1 for r in results if r.passed)
            failed  = total - passed
            print(f"  {passed}/{total} tools passed  |  {failed} failed")
            print()
            if exit_code == 0:
                print("GATE PASSED — ready to merge / release.")
            else:
                print("GATE FAILED — fix failures before merging.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CI quality gate.")
    parser.add_argument("--json",  action="store_true", dest="as_json",
                        help="Output JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress output")
    parser.add_argument("--skip",  default="",
                        help="Comma-separated tool names to skip")
    args = parser.parse_args(argv)
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    return run_gate(quiet=args.quiet, as_json=args.as_json, skip=skip)


if __name__ == "__main__":
    sys.exit(main())
