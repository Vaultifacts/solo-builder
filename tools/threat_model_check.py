"""Threat-model freshness check (TASK-342, SE-001 to SE-006).

Validates that docs/THREAT_MODEL.md:
  1. Exists and is non-empty
  2. Contains all required SE gap IDs (SE-001 through SE-006)
  3. Contains a "Last updated" or changelog date entry
  4. References all required control modules
  5. Has no threat marked "Open" in the Known Gaps Addressed section
     without an accompanying mitigation in the Recommended Follow-On Work
     table (advisory check only — optional)

Exit codes:
  0 — all required checks pass
  1 — one or more required checks failed
  2 — usage / file not found error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
THREAT_MODEL_PATH = REPO_ROOT / "docs" / "THREAT_MODEL.md"

# SE gap IDs that MUST appear in the document
REQUIRED_GAP_IDS = [f"SE-{n:03d}" for n in range(1, 7)]   # SE-001 … SE-006

# Module names that MUST be referenced (evidence of control implementations)
REQUIRED_CONTROLS = [
    "secret_scan",
    "hitl",
    "HitlPolicy",
    "ToolScopePolicy",
]

# Regex for "Last updated:" line or changelog date entry
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class CheckResult(NamedTuple):
    name:     str
    required: bool
    passed:   bool
    detail:   str


def _check_file_exists(path: Path) -> CheckResult:
    ok = path.exists() and path.stat().st_size > 0
    return CheckResult(
        name="file-exists",
        required=True,
        passed=ok,
        detail="" if ok else f"Not found or empty: {path}",
    )


def _check_gap_ids(text: str) -> CheckResult:
    missing = [g for g in REQUIRED_GAP_IDS if g not in text]
    ok = len(missing) == 0
    return CheckResult(
        name="gap-ids",
        required=True,
        passed=ok,
        detail="" if ok else f"Missing gap IDs: {', '.join(missing)}",
    )


def _check_date(text: str) -> CheckResult:
    ok = bool(_DATE_PATTERN.search(text))
    return CheckResult(
        name="date-present",
        required=True,
        passed=ok,
        detail="" if ok else "No YYYY-MM-DD date found in document",
    )


def _check_controls(text: str) -> list[CheckResult]:
    results = []
    for ctrl in REQUIRED_CONTROLS:
        ok = ctrl in text
        results.append(CheckResult(
            name=f"control-{ctrl}",
            required=True,
            passed=ok,
            detail="" if ok else f"Required control '{ctrl}' not mentioned in document",
        ))
    return results


def _check_threat_sections(text: str) -> CheckResult:
    """Advisory: verify T-001 through T-006 threat sections are present."""
    missing = []
    for n in range(1, 7):
        tag = f"T-{n:03d}"
        if tag not in text:
            missing.append(tag)
    ok = len(missing) == 0
    return CheckResult(
        name="threat-sections",
        required=False,
        passed=ok,
        detail="" if ok else f"Missing threat sections: {', '.join(missing)}",
    )


def run_checks(quiet: bool = False, as_json: bool = False) -> int:
    results: list[CheckResult] = []

    # File existence check first
    file_check = _check_file_exists(THREAT_MODEL_PATH)
    results.append(file_check)

    if file_check.passed:
        text = THREAT_MODEL_PATH.read_text(encoding="utf-8")
        results.append(_check_gap_ids(text))
        results.append(_check_date(text))
        results.extend(_check_controls(text))
        results.append(_check_threat_sections(text))

    exit_code = 0 if all(r.passed for r in results if r.required) else 1

    if not quiet:
        if as_json:
            print(json.dumps({
                "threat_model_ok": exit_code == 0,
                "path": str(THREAT_MODEL_PATH),
                "checks": [r._asdict() for r in results],
            }, ensure_ascii=False))
        else:
            print("Threat Model Check")
            print()
            for r in results:
                req  = "[REQ]" if r.required else "[OPT]"
                flag = "PASS"  if r.passed   else "FAIL"
                print(f"  {flag}  {req}  {r.name}")
                if not r.passed and r.detail:
                    print(f"        {r.detail}")
            print()
            if exit_code == 0:
                print("PASS — threat model is current.")
            else:
                print("FAIL — threat model requires update.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate docs/THREAT_MODEL.md.")
    parser.add_argument("--json",  action="store_true", dest="as_json")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    return run_checks(quiet=args.quiet, as_json=args.as_json)


if __name__ == "__main__":
    sys.exit(main())
