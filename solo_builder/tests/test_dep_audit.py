"""Tests for tools/dep_audit.py (TASK-328 / TD-SEC-002)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import dep_audit


class TestParseLock(unittest.TestCase):

    def _write_lock(self, content: str) -> Path:
        tmp = Path(tempfile.mkdtemp()) / "requirements-lock.txt"
        tmp.write_text(content, encoding="utf-8")
        return tmp

    def test_parses_pinned_versions(self):
        lock = self._write_lock("requests==2.32.3\npython-dotenv==1.0.1\n")
        result = dep_audit._parse_lock(lock)
        self.assertEqual(result["requests"], "2.32.3")
        self.assertEqual(result["python-dotenv"], "1.0.1")

    def test_skips_comments_and_blanks(self):
        lock = self._write_lock("# comment\n\nrequests==2.32.3\n")
        result = dep_audit._parse_lock(lock)
        self.assertEqual(list(result.keys()), ["requests"])

    def test_names_are_lowercased(self):
        lock = self._write_lock("Requests==2.32.3\n")
        result = dep_audit._parse_lock(lock)
        self.assertIn("requests", result)

    def test_empty_file_returns_empty_dict(self):
        lock = self._write_lock("# just comments\n")
        self.assertEqual(dep_audit._parse_lock(lock), {})


class TestCheckDrift(unittest.TestCase):

    def test_no_drift_when_versions_match(self):
        # requests is definitely installed in this environment
        import importlib.metadata
        try:
            ver = importlib.metadata.version("requests")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("requests not installed")
        drift = dep_audit._check_drift({"requests": ver})
        self.assertEqual(drift, [])

    def test_drift_reported_when_version_differs(self):
        drift = dep_audit._check_drift({"requests": "0.0.0"})
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["package"], "requests")
        self.assertEqual(drift[0]["pinned"], "0.0.0")

    def test_missing_package_reported_as_drift(self):
        drift = dep_audit._check_drift({"__nonexistent_pkg__": "1.0.0"})
        self.assertEqual(len(drift), 1)
        self.assertIsNone(drift[0]["installed"])

    def test_empty_pinned_returns_empty_drift(self):
        self.assertEqual(dep_audit._check_drift({}), [])


class TestRunPipAudit(unittest.TestCase):

    def test_returns_not_ran_when_pip_audit_missing(self):
        with patch("dep_audit.shutil.which", return_value=None):
            result = dep_audit._run_pip_audit(Path("requirements-lock.txt"))
        self.assertFalse(result["ran"])
        self.assertIn("not installed", result["reason"])

    def test_returns_passed_on_zero_exit(self):
        with patch("dep_audit.shutil.which", return_value="/usr/bin/pip-audit"), \
             patch("dep_audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "[]"
            result = dep_audit._run_pip_audit(Path("requirements-lock.txt"))
        self.assertTrue(result["ran"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["vulnerability_count"], 0)

    def test_vulnerabilities_counted_from_output(self):
        fake_output = json.dumps([
            {"name": "requests", "version": "2.0.0",
             "vulns": [{"id": "CVE-2023-0001", "fix_versions": ["2.32.0"]}]}
        ])
        with patch("dep_audit.shutil.which", return_value="/usr/bin/pip-audit"), \
             patch("dep_audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = fake_output
            result = dep_audit._run_pip_audit(Path("requirements-lock.txt"))
        self.assertTrue(result["ran"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["vulnerability_count"], 1)


class TestMain(unittest.TestCase):

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._lock = self._tmp / "requirements-lock.txt"
        self._report = self._tmp / "dep_audit_result.json"
        # Patch paths in dep_audit module
        self._patcher_lock = patch.object(dep_audit, "LOCK_FILE", new=self._lock)
        self._patcher_report = patch.object(dep_audit, "REPORT_PATH", new=self._report)
        self._patcher_lock.start()
        self._patcher_report.start()

    def tearDown(self):
        self._patcher_lock.stop()
        self._patcher_report.stop()
        import shutil
        shutil.rmtree(str(self._tmp), ignore_errors=True)

    def _write_good_lock(self):
        import importlib.metadata
        try:
            ver = importlib.metadata.version("requests")
        except importlib.metadata.PackageNotFoundError:
            ver = "0.0.0"
        self._lock.write_text(f"requests=={ver}\n", encoding="utf-8")

    def test_exit_0_when_no_drift(self):
        self._write_good_lock()
        rc = dep_audit.main(["--check-only"])
        self.assertEqual(rc, 0)

    def test_exit_1_when_drift_found(self):
        self._lock.write_text("requests==0.0.0\n", encoding="utf-8")
        rc = dep_audit.main(["--check-only"])
        self.assertEqual(rc, 1)

    def test_report_written_on_success(self):
        self._write_good_lock()
        dep_audit.main(["--check-only"])
        self.assertTrue(self._report.exists())
        data = json.loads(self._report.read_text(encoding="utf-8"))
        self.assertTrue(data["passed"])
        self.assertEqual(data["drift_count"], 0)

    def test_report_written_on_failure(self):
        self._lock.write_text("requests==0.0.0\n", encoding="utf-8")
        dep_audit.main(["--check-only"])
        data = json.loads(self._report.read_text(encoding="utf-8"))
        self.assertFalse(data["passed"])
        self.assertGreater(data["drift_count"], 0)

    def test_exit_1_when_lock_file_missing(self):
        # lock file does not exist — default setUp leaves it absent
        rc = dep_audit.main(["--check-only"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
