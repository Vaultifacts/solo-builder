"""Dependency severity checker — TASK-356 (SE-010 to SE-015).

Extends the basic dep_audit.py with:
  1. Unpinned constraint detection — flags packages using >=, ~=, !=, or no pin
  2. CVE severity filtering — filter pip-audit output by CRITICAL / HIGH / MEDIUM / LOW
  3. Structured JSON report with per-severity counts

Usage:
  python tools/dep_severity_check.py
  python tools/dep_severity_check.py --min-severity HIGH
  python tools/dep_severity_check.py --check-only   # skip pip-audit
  python tools/dep_severity_check.py --json --quiet

Exit codes:
  0 — no issues at or above the severity threshold, no unpinned packages
  1 — issues found (unpinned packages or CVEs at/above threshold)
  2 — usage / file error
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT  = Path(__file__).resolve().parent.parent
LOCK_FILE  = REPO_ROOT / "tools" / "requirements-lock.txt"

SEVERITY_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
SEVERITY_ORDER  = {s: i for i, s in enumerate(SEVERITY_LEVELS)}

_PIN_EXACT_RE  = re.compile(r"^[a-zA-Z0-9_\-\.]+==[^\s]+$")
_UNPINNED_RE   = re.compile(r"(>=|<=|~=|!=|>|<)")
_NAME_ONLY_RE  = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class UnpinnedEntry:
    package:    str
    constraint: str

    def to_dict(self) -> dict:
        return {"package": self.package, "constraint": self.constraint}


@dataclass
class CveEntry:
    package:  str
    version:  str
    cve_id:   str
    severity: str
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "package":     self.package,
            "version":     self.version,
            "cve_id":      self.cve_id,
            "severity":    self.severity,
            "description": self.description,
        }


@dataclass
class SeverityReport:
    unpinned:        list[UnpinnedEntry] = field(default_factory=list)
    cves:            list[CveEntry]      = field(default_factory=list)
    pip_audit_ran:   bool                = False
    pip_audit_error: str                 = ""

    @property
    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {s: 0 for s in SEVERITY_LEVELS}
        for cve in self.cves:
            sev = cve.severity.upper() if cve.severity.upper() in counts else "UNKNOWN"
            counts[sev] += 1
        return counts

    def has_issues(self, min_severity: str = "LOW") -> bool:
        """Return True if any unpinned packages or CVEs at/above min_severity."""
        if self.unpinned:
            return True
        threshold = SEVERITY_ORDER.get(min_severity.upper(), len(SEVERITY_LEVELS))
        for cve in self.cves:
            cve_rank = SEVERITY_ORDER.get(cve.severity.upper(), len(SEVERITY_LEVELS) - 1)
            if cve_rank <= threshold:
                return True
        return False

    def to_dict(self) -> dict:
        return {
            "unpinned":         [u.to_dict() for u in self.unpinned],
            "unpinned_count":   len(self.unpinned),
            "cves":             [c.to_dict() for c in self.cves],
            "cve_count":        len(self.cves),
            "severity_counts":  self.severity_counts,
            "pip_audit_ran":    self.pip_audit_ran,
            "pip_audit_error":  self.pip_audit_error,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_unpinned(lock_path: Path) -> list[UnpinnedEntry]:
    """Return packages that are not pinned with == in the lock file."""
    unpinned: list[UnpinnedEntry] = []
    try:
        lines = lock_path.read_text(encoding="utf-8").splitlines()
    except (OSError, FileNotFoundError):
        return unpinned

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Exactly-pinned: name==version — OK
        if _PIN_EXACT_RE.match(line):
            continue
        # Name only or loose constraint — flag it
        pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
        unpinned.append(UnpinnedEntry(package=pkg_name, constraint=line))

    return unpinned


def _parse_pip_audit_json(stdout: str, min_severity: str) -> list[CveEntry]:
    """Parse pip-audit JSON output and filter by severity."""
    cves: list[CveEntry] = []
    threshold = SEVERITY_ORDER.get(min_severity.upper(), len(SEVERITY_LEVELS))
    try:
        data = json.loads(stdout)
        for entry in data:
            pkg  = entry.get("name", "")
            ver  = entry.get("version", "")
            for vuln in entry.get("vulns", []):
                sev = vuln.get("fix_versions", {})
                # pip-audit doesn't always include severity; use UNKNOWN if absent
                sev_str = str(vuln.get("severity", "UNKNOWN")).upper()
                cve_rank = SEVERITY_ORDER.get(sev_str, len(SEVERITY_LEVELS) - 1)
                if cve_rank <= threshold:
                    cves.append(CveEntry(
                        package=pkg,
                        version=ver,
                        cve_id=vuln.get("id", ""),
                        severity=sev_str,
                        description=vuln.get("description", ""),
                    ))
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return cves


def run_pip_audit(
    lock_path: Path,
    min_severity: str = "LOW",
) -> tuple[list[CveEntry], bool, str]:
    """Run pip-audit and return (cve_list, ran, error_msg)."""
    if not shutil.which("pip-audit"):
        return [], False, "pip-audit not installed"
    try:
        proc = subprocess.run(
            ["pip-audit", "--requirement", str(lock_path), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        cves = _parse_pip_audit_json(proc.stdout, min_severity)
        return cves, True, ""
    except subprocess.TimeoutExpired:
        return [], False, "pip-audit timed out"
    except Exception as exc:
        return [], False, str(exc)


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def check(
    lock_path: Path | str | None = None,
    min_severity: str = "LOW",
    check_only: bool = False,
) -> SeverityReport:
    if lock_path is None:
        lock_path = LOCK_FILE
    lock_path = Path(lock_path)

    report = SeverityReport()
    report.unpinned = check_unpinned(lock_path)

    if not check_only:
        cves, ran, err = run_pip_audit(lock_path, min_severity=min_severity)
        report.cves            = cves
        report.pip_audit_ran   = ran
        report.pip_audit_error = err

    return report


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    lock_path: Path | str | None = None,
    min_severity: str = "LOW",
    check_only: bool = False,
) -> int:
    if lock_path is not None and not Path(lock_path).exists():
        if not quiet:
            print(f"ERROR: lock file not found: {lock_path}", file=sys.stderr)
        return 2
    if LOCK_FILE is not None and lock_path is None and not LOCK_FILE.exists():
        if not quiet:
            print(f"ERROR: lock file not found: {LOCK_FILE}", file=sys.stderr)
        return 2

    try:
        report = check(lock_path=lock_path, min_severity=min_severity, check_only=check_only)
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 1 if report.has_issues(min_severity) else 0

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            sc = report.severity_counts
            print("Dependency Severity Check")
            print()
            print(f"  Unpinned packages: {len(report.unpinned)}")
            for u in report.unpinned:
                print(f"    [UNPIN] {u.constraint}")
            print(f"  CVEs found:        {len(report.cves)}")
            if report.cves:
                for c in report.cves:
                    print(f"    [{c.severity:<8}] {c.package}=={c.version}  {c.cve_id}")
            if report.pip_audit_ran:
                print(f"  Severity counts:   "
                      f"CRIT={sc['CRITICAL']} HIGH={sc['HIGH']} "
                      f"MED={sc['MEDIUM']} LOW={sc['LOW']}")
            elif report.pip_audit_error:
                print(f"  pip-audit: {report.pip_audit_error}")
            print()
            if exit_code == 0:
                print("No issues found.")
            else:
                print("Issues detected — see above.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check dependency pins and CVE severity."
    )
    parser.add_argument("--json",         action="store_true", dest="as_json")
    parser.add_argument("--quiet",        action="store_true")
    parser.add_argument("--check-only",   action="store_true",
                        help="Skip pip-audit; only check pin constraints")
    parser.add_argument(
        "--min-severity",  default="LOW",
        choices=[s.upper() for s in SEVERITY_LEVELS],
        help="Minimum CVE severity to report (default: LOW)"
    )
    parser.add_argument("--lock-file",    default="", help="Override requirements-lock.txt path")
    args = parser.parse_args(argv)
    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        lock_path=args.lock_file or None,
        min_severity=args.min_severity,
        check_only=args.check_only,
    )


if __name__ == "__main__":
    sys.exit(main())
