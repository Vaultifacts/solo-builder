"""Tests for tools/run_mutation_tests.py — TASK-334 (QA-035)."""
import sys
import subprocess
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import run_mutation_tests as rmt


class TestCheckMutmutAvailable(unittest.TestCase):

    def test_returns_true_when_mutmut_installed(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            self.assertTrue(rmt._check_mutmut_available())

    def test_returns_false_when_mutmut_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertFalse(rmt._check_mutmut_available())

    def test_returns_false_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            self.assertFalse(rmt._check_mutmut_available())

    def test_returns_false_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("mutmut", 10)):
            self.assertFalse(rmt._check_mutmut_available())


class TestParseResults(unittest.TestCase):

    def _mock_run(self, stdout: str):
        mock = MagicMock()
        mock.stdout = stdout
        mock.stderr = ""
        return mock

    def test_parses_survived_count(self):
        with patch("subprocess.run", return_value=self._mock_run("3 survived\n")):
            r = rmt._parse_results()
        self.assertEqual(r["survived"], 3)

    def test_zero_survived_when_no_match(self):
        with patch("subprocess.run", return_value=self._mock_run("all killed\n")):
            r = rmt._parse_results()
        self.assertEqual(r["survived"], 0)

    def test_raw_included_in_result(self):
        with patch("subprocess.run", return_value=self._mock_run("some output\n")):
            r = rmt._parse_results()
        self.assertIn("some output", r["raw"])


class TestMain(unittest.TestCase):

    def test_dry_run_exits_0(self):
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = rmt.main(["--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("Dry-run", buf.getvalue())

    def test_returns_2_when_mutmut_not_installed(self):
        with patch.object(rmt, "_check_mutmut_available", return_value=False):
            buf = StringIO()
            with patch("sys.stderr", buf):
                code = rmt.main([])
        self.assertEqual(code, 2)

    def test_returns_1_when_survivors_exceed_threshold(self):
        with patch.object(rmt, "_check_mutmut_available", return_value=True):
            with patch.object(rmt, "_run_mutmut", return_value=0):
                with patch.object(rmt, "_parse_results", return_value={"raw": "", "survived": 5}):
                    buf = StringIO()
                    with patch("sys.stdout", buf):
                        code = rmt.main(["--max-survivors", "3"])
        self.assertEqual(code, 1)

    def test_returns_0_when_survivors_within_threshold(self):
        with patch.object(rmt, "_check_mutmut_available", return_value=True):
            with patch.object(rmt, "_run_mutmut", return_value=0):
                with patch.object(rmt, "_parse_results", return_value={"raw": "", "survived": 2}):
                    buf = StringIO()
                    with patch("sys.stdout", buf):
                        code = rmt.main(["--max-survivors", "5"])
        self.assertEqual(code, 0)

    def test_dry_run_skips_mutmut_check(self):
        check_called = []
        with patch.object(rmt, "_check_mutmut_available",
                          side_effect=lambda: check_called.append(1) or True):
            buf = StringIO()
            with patch("sys.stdout", buf):
                rmt.main(["--dry-run"])
        self.assertEqual(check_called, [], "mutmut availability should not be checked in dry-run")

    def test_pyproject_path_shown_in_config_output(self):
        buf = StringIO()
        with patch("sys.stdout", buf):
            rmt.main(["--dry-run"])
        self.assertIn("pyproject.toml", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
