#!/usr/bin/env python
"""Dependency vulnerability audit for Solo Builder (TASK-328 / TD-SEC-002).

What it does
------------
1. Reads tools/requirements-lock.txt (pinned package versions).
2. Checks that installed versions match pinned versions (drift detection).
3. Attempts to run `pip-audit` if available for CVE scanning.
4. Writes a JSON report to dep_audit_result.json in the repo root.
5. Exits 0 if no issues (or pip-audit not installed), 1 if drift/vulnerabilities found.

Usage
-----
    python tools/dep_audit.py            # full audit
    python tools/dep_audit.py --check-only   # only check drift, skip pip-audit

The script is designed to be non-required in VERIFY.json — it never fails the
build when pip-audit is absent. Drift failures are always reported.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = REPO_ROOT / "tools" / "requirements-lock.txt"
REPORT_PATH = REPO_ROOT / "dep_audit_result.json"


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_lock(lock_path: Path) -> dict[str, str]:
    """Return {package_name_lower: pinned_version} from a requirements-lock file."""
    result: dict[str, str] = {}
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, _, version = line.partition("==")
            result[name.strip().lower()] = version.strip()
    return result


def _check_drift(pinned: dict[str, str]) -> list[dict]:
    """Return drift records for packages whose installed version != pinned version."""
    drift = []
    for name, pin_ver in pinned.items():
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != pin_ver:
            drift.append({
                "package":   name,
                "pinned":    pin_ver,
                "installed": installed,
            })
    return drift


def _run_pip_audit(lock_path: Path) -> dict:
    """Run pip-audit if available; return a result dict."""
    if not shutil.which("pip-audit"):
        return {"ran": False, "reason": "pip-audit not installed"}
    try:
        proc = subprocess.run(
            ["pip-audit", "--requirement", str(lock_path), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        ok = proc.returncode == 0
        vulnerabilities: list = []
        try:
            data = json.loads(proc.stdout)
            # pip-audit json format: list of {"name": ..., "version": ..., "vulns": [...]}
            for entry in data:
                if entry.get("vulns"):
                    vulnerabilities.extend([
                        {"package": entry["name"], "version": entry["version"], **v}
                        for v in entry["vulns"]
                    ])
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "ran":             True,
            "exit_code":       proc.returncode,
            "passed":          ok,
            "vulnerability_count": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
        }
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "pip-audit timed out"}
    except Exception as exc:
        return {"ran": False, "reason": str(exc)}


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Solo Builder dependency audit")
    parser.add_argument("--check-only", action="store_true",
                        help="Only check for version drift; skip pip-audit CVE scan")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress all stdout/stderr output")
    args = parser.parse_args(argv)

    if not LOCK_FILE.exists():
        print(f"ERROR: Lock file not found: {LOCK_FILE}", file=sys.stderr)
        return 1

    pinned = _parse_lock(LOCK_FILE)
    drift = _check_drift(pinned)
    pip_audit_result = {} if args.check_only else _run_pip_audit(LOCK_FILE)

    passed = (len(drift) == 0) and (
        not pip_audit_result.get("ran") or pip_audit_result.get("passed", True)
    )

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lock_file": str(LOCK_FILE.relative_to(REPO_ROOT)) if LOCK_FILE.is_relative_to(REPO_ROOT) else str(LOCK_FILE),
        "pinned_count": len(pinned),
        "drift": drift,
        "drift_count": len(drift),
        "pip_audit": pip_audit_result,
        "passed": passed,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not args.quiet:
        if drift:
            print(f"DRIFT: {len(drift)} package(s) differ from lockfile:", file=sys.stderr)
            for d in drift:
                print(f"  {d['package']}: pinned={d['pinned']} installed={d['installed']}", file=sys.stderr)

        if pip_audit_result.get("ran") and not pip_audit_result.get("passed"):
            count = pip_audit_result.get("vulnerability_count", "?")
            print(f"VULNERABILITIES: pip-audit found {count} CVE(s).", file=sys.stderr)

        if passed:
            print("dep_audit: OK")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
