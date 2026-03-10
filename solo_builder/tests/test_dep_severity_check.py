"""Tests for tools/dep_severity_check.py (TASK-356, SE-010 to SE-015)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "dep_severity_check", _TOOLS_DIR / "dep_severity_check.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["dep_severity_check"] = _mod
_spec.loader.exec_module(_mod)

check_unpinned        = _mod.check_unpinned
_parse_pip_audit_json = _mod._parse_pip_audit_json
SeverityReport        = _mod.SeverityReport
UnpinnedEntry         = _mod.UnpinnedEntry
CveEntry              = _mod.CveEntry
check                 = _mod.check
run                   = _mod.run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_LOCK_PINNED = """\
# locked deps
flask==3.0.0
requests==2.31.0
pytest==8.0.0
"""

_LOCK_MIXED = """\
flask==3.0.0
requests>=2.28.0
pytest~=8.0
unpinned_pkg
"""

_PIP_AUDIT_OUTPUT = json.dumps([
    {
        "name": "flask",
        "version": "2.0.0",
        "vulns": [
            {"id": "CVE-2023-001", "severity": "HIGH", "description": "XSS vulnerability"},
            {"id": "CVE-2023-002", "severity": "MEDIUM", "description": "CSRF issue"},
        ],
    },
    {
        "name": "requests",
        "version": "2.28.0",
        "vulns": [],
    },
])

_PIP_AUDIT_CRITICAL = json.dumps([
    {
        "name": "pkg",
        "version": "1.0.0",
        "vulns": [
            {"id": "CVE-2023-CRIT", "severity": "CRITICAL", "description": "RCE"},
        ],
    },
])


def _write_lock(tmp: Path, content: str) -> Path:
    p = tmp / "requirements-lock.txt"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# UnpinnedEntry / CveEntry
# ---------------------------------------------------------------------------

class TestUnpinnedEntry(unittest.TestCase):

    def test_to_dict(self):
        u = UnpinnedEntry("pkg", "pkg>=1.0")
        d = u.to_dict()
        self.assertEqual(d["package"], "pkg")
        self.assertEqual(d["constraint"], "pkg>=1.0")


class TestCveEntry(unittest.TestCase):

    def test_to_dict(self):
        c = CveEntry("flask", "2.0.0", "CVE-2023-001", "HIGH", "xss")
        d = c.to_dict()
        for k in ("package", "version", "cve_id", "severity", "description"):
            self.assertIn(k, d)

    def test_severity_stored(self):
        c = CveEntry("pkg", "1.0", "CVE-X", "CRITICAL")
        self.assertEqual(c.severity, "CRITICAL")


# ---------------------------------------------------------------------------
# SeverityReport
# ---------------------------------------------------------------------------

class TestSeverityReport(unittest.TestCase):

    def test_no_issues_clean(self):
        r = SeverityReport()
        self.assertFalse(r.has_issues())

    def test_unpinned_causes_issues(self):
        r = SeverityReport(unpinned=[UnpinnedEntry("pkg", "pkg>=1.0")])
        self.assertTrue(r.has_issues())

    def test_high_cve_causes_issues(self):
        r = SeverityReport(cves=[CveEntry("pkg", "1.0", "CVE-X", "HIGH")])
        self.assertTrue(r.has_issues("HIGH"))

    def test_low_cve_filtered_by_high_threshold(self):
        r = SeverityReport(cves=[CveEntry("pkg", "1.0", "CVE-X", "LOW")])
        self.assertFalse(r.has_issues("HIGH"))

    def test_critical_above_high_threshold(self):
        r = SeverityReport(cves=[CveEntry("pkg", "1.0", "CVE-X", "CRITICAL")])
        self.assertTrue(r.has_issues("HIGH"))

    def test_severity_counts_correct(self):
        r = SeverityReport(cves=[
            CveEntry("a", "1.0", "CVE-1", "HIGH"),
            CveEntry("b", "1.0", "CVE-2", "MEDIUM"),
            CveEntry("c", "1.0", "CVE-3", "HIGH"),
        ])
        counts = r.severity_counts
        self.assertEqual(counts["HIGH"], 2)
        self.assertEqual(counts["MEDIUM"], 1)
        self.assertEqual(counts["CRITICAL"], 0)

    def test_to_dict_structure(self):
        r = SeverityReport()
        d = r.to_dict()
        for k in ("unpinned", "unpinned_count", "cves", "cve_count",
                  "severity_counts", "pip_audit_ran", "pip_audit_error"):
            self.assertIn(k, d)


# ---------------------------------------------------------------------------
# check_unpinned
# ---------------------------------------------------------------------------

class TestCheckUnpinned(unittest.TestCase):

    def test_all_pinned_no_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_PINNED)
            result = check_unpinned(p)
        self.assertEqual(result, [])

    def test_detects_loose_constraint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_MIXED)
            result = check_unpinned(p)
        constraints = [u.constraint for u in result]
        self.assertTrue(any(">=" in c for c in constraints))

    def test_detects_tilde_constraint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_MIXED)
            result = check_unpinned(p)
        constraints = [u.constraint for u in result]
        self.assertTrue(any("~=" in c for c in constraints))

    def test_detects_name_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_MIXED)
            result = check_unpinned(p)
        self.assertGreater(len(result), 0)

    def test_comments_ignored(self):
        content = "# comment\nflask==3.0.0\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), content)
            result = check_unpinned(p)
        self.assertEqual(result, [])

    def test_missing_file_returns_empty(self):
        result = check_unpinned(Path("/nonexistent/requirements-lock.txt"))
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# _parse_pip_audit_json
# ---------------------------------------------------------------------------

class TestParsePipAuditJson(unittest.TestCase):

    def test_parses_high_cves(self):
        cves = _parse_pip_audit_json(_PIP_AUDIT_OUTPUT, min_severity="LOW")
        self.assertEqual(len(cves), 2)
        ids = [c.cve_id for c in cves]
        self.assertIn("CVE-2023-001", ids)
        self.assertIn("CVE-2023-002", ids)

    def test_severity_filter_high_excludes_medium(self):
        cves = _parse_pip_audit_json(_PIP_AUDIT_OUTPUT, min_severity="HIGH")
        # Only HIGH and above should remain
        for c in cves:
            self.assertIn(c.severity, ("CRITICAL", "HIGH", "UNKNOWN"))

    def test_empty_vulns_no_cves(self):
        data = json.dumps([{"name": "pkg", "version": "1.0", "vulns": []}])
        cves = _parse_pip_audit_json(data, min_severity="LOW")
        self.assertEqual(cves, [])

    def test_invalid_json_returns_empty(self):
        cves = _parse_pip_audit_json("not json", min_severity="LOW")
        self.assertEqual(cves, [])

    def test_critical_cve_detected(self):
        cves = _parse_pip_audit_json(_PIP_AUDIT_CRITICAL, min_severity="LOW")
        self.assertEqual(len(cves), 1)
        self.assertEqual(cves[0].severity, "CRITICAL")


# ---------------------------------------------------------------------------
# check() integration (with mocked pip-audit)
# ---------------------------------------------------------------------------

class TestCheck(unittest.TestCase):

    def test_clean_lock_no_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_PINNED)
            report = check(lock_path=p, check_only=True)
        self.assertFalse(report.has_issues())

    def test_mixed_lock_has_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_MIXED)
            report = check(lock_path=p, check_only=True)
        self.assertTrue(report.has_issues())

    def test_check_only_skips_pip_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_PINNED)
            report = check(lock_path=p, check_only=True)
        self.assertFalse(report.pip_audit_ran)


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_no_issues(self):
        clean_report = SeverityReport()
        with patch.object(_mod, "check", return_value=clean_report):
            with patch.object(_mod, "LOCK_FILE", Path("/fake/lock.txt")):
                with patch.object(Path, "exists", return_value=True):
                    code = run(quiet=True, lock_path="/fake/lock.txt")
        self.assertEqual(code, 0)

    def test_returns_1_with_unpinned(self):
        r = SeverityReport(unpinned=[UnpinnedEntry("pkg", "pkg>=1.0")])
        with patch.object(_mod, "check", return_value=r):
            with patch.object(Path, "exists", return_value=True):
                code = run(quiet=True, lock_path="/fake/lock.txt")
        self.assertEqual(code, 1)

    def test_json_output_structure(self):
        r = SeverityReport()
        with patch.object(_mod, "check", return_value=r):
            with patch.object(Path, "exists", return_value=True):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                    run(as_json=True, lock_path="/fake/lock.txt")
                    data = json.loads(mock_out.getvalue())
        for k in ("unpinned", "cves", "severity_counts"):
            self.assertIn(k, data)

    def test_quiet_suppresses_output(self):
        r = SeverityReport()
        with patch.object(_mod, "check", return_value=r):
            with patch.object(Path, "exists", return_value=True):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                    run(quiet=True, lock_path="/fake/lock.txt")
                    output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_returns_2_missing_lock_file(self):
        code = run(quiet=True, lock_path="/nonexistent/requirements-lock.txt")
        self.assertEqual(code, 2)

    def test_text_output_shows_unpin(self):
        r = SeverityReport(unpinned=[UnpinnedEntry("flask", "flask>=2.0")])
        with patch.object(_mod, "check", return_value=r):
            with patch.object(Path, "exists", return_value=True):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                    run(lock_path="/fake/lock.txt")
                    output = mock_out.getvalue()
        self.assertIn("flask", output)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_check_only_with_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_PINNED)
            rc = _mod.main(["--check-only", "--quiet", "--lock-file", str(p)])
        self.assertEqual(rc, 0)

    def test_main_unpinned_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_MIXED)
            rc = _mod.main(["--check-only", "--quiet", "--lock-file", str(p)])
        self.assertEqual(rc, 1)

    def test_main_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_PINNED)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--check-only", "--json", "--lock-file", str(p)])
                data = json.loads(mock_out.getvalue())
        self.assertIn("unpinned", data)

    def test_main_min_severity_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_lock(Path(tmp), _LOCK_PINNED)
            rc = _mod.main(["--check-only", "--quiet", "--min-severity", "HIGH",
                            "--lock-file", str(p)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
