"""Tests for tools/lint_check.py (TASK-351, DX-010 to DX-015)."""
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
    "lint_check", _TOOLS_DIR / "lint_check.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["lint_check"] = _mod
_spec.loader.exec_module(_mod)

run_lint          = _mod.run_lint
LintReport        = _mod.LintReport
LintThresholds    = _mod.LintThresholds
load_lint_thresholds = _mod.load_lint_thresholds
_parse_counts     = _mod._parse_counts
run               = _mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLAKE8_OUTPUT_CLEAN = ""

_FLAKE8_OUTPUT_MIXED = """\
solo_builder/foo.py:1:1: E302 expected 2 blank lines
solo_builder/foo.py:2:5: W291 trailing whitespace
solo_builder/foo.py:3:1: F401 'os' imported but unused
solo_builder/bar.py:4:1: E501 line too long (120 > 79 characters)
solo_builder/bar.py:5:1: C901 'foo' is too complex (11)
"""

_FLAKE8_OUTPUT_ERRORS_ONLY = """\
solo_builder/x.py:1:1: E302 expected 2 blank lines
solo_builder/x.py:2:1: E501 line too long
"""


def _make_subprocess_result(stdout: str, returncode: int = 0):
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# _parse_counts
# ---------------------------------------------------------------------------

class TestParseCounts(unittest.TestCase):

    def test_empty_output(self):
        counts, violations = _parse_counts("")
        self.assertEqual(counts, {"E": 0, "W": 0, "F": 0, "C": 0})
        self.assertEqual(violations, [])

    def test_mixed_output(self):
        counts, violations = _parse_counts(_FLAKE8_OUTPUT_MIXED)
        self.assertEqual(counts["E"], 2)
        self.assertEqual(counts["W"], 1)
        self.assertEqual(counts["F"], 1)
        self.assertEqual(counts["C"], 1)

    def test_errors_only(self):
        counts, violations = _parse_counts(_FLAKE8_OUTPUT_ERRORS_ONLY)
        self.assertEqual(counts["E"], 2)
        self.assertEqual(counts["W"], 0)

    def test_violations_list_length(self):
        _, violations = _parse_counts(_FLAKE8_OUTPUT_MIXED)
        self.assertEqual(len(violations), 5)

    def test_unknown_code_letter_ignored(self):
        output = "solo_builder/x.py:1:1: Z999 some unknown code\n"
        counts, _ = _parse_counts(output)
        self.assertEqual(sum(counts.values()), 0)


# ---------------------------------------------------------------------------
# LintThresholds
# ---------------------------------------------------------------------------

class TestLintThresholds(unittest.TestCase):

    def test_defaults(self):
        t = LintThresholds()
        self.assertEqual(t.max_e, 0)
        self.assertEqual(t.max_f, 0)
        self.assertGreater(t.max_w, 0)

    def test_immutable(self):
        t = LintThresholds()
        with self.assertRaises((AttributeError, TypeError)):
            t.max_e = 99  # type: ignore[misc]

    def test_custom_values(self):
        t = LintThresholds(max_e=5, max_w=100, max_f=2, max_c=20)
        self.assertEqual(t.max_e, 5)
        self.assertEqual(t.max_w, 100)


# ---------------------------------------------------------------------------
# LintReport
# ---------------------------------------------------------------------------

class TestLintReport(unittest.TestCase):

    def test_empty_report_passes(self):
        r = LintReport()
        self.assertTrue(r.passed)

    def test_exceeded_causes_failure(self):
        r = LintReport(exceeded=["E: 5 violations > max 0"])
        self.assertFalse(r.passed)

    def test_to_dict_structure(self):
        r = LintReport()
        d = r.to_dict()
        for k in ("passed", "counts", "thresholds", "exceeded", "violations"):
            self.assertIn(k, d)

    def test_to_dict_counts_keys(self):
        r = LintReport()
        d = r.to_dict()
        for k in ("E", "W", "F", "C"):
            self.assertIn(k, d["counts"])


# ---------------------------------------------------------------------------
# load_lint_thresholds
# ---------------------------------------------------------------------------

class TestLoadLintThresholds(unittest.TestCase):

    def test_missing_settings_uses_defaults(self):
        t = load_lint_thresholds(settings_path=Path("/nonexistent/settings.json"))
        self.assertEqual(t.max_e, 0)

    def test_settings_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"LINT_MAX_E": 5, "LINT_MAX_W": 100}), encoding="utf-8")
            t = load_lint_thresholds(settings_path=p)
        self.assertEqual(t.max_e, 5)
        self.assertEqual(t.max_w, 100)

    def test_partial_override_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"LINT_MAX_E": 3}), encoding="utf-8")
            t = load_lint_thresholds(settings_path=p)
        self.assertEqual(t.max_f, 0)  # default unchanged


# ---------------------------------------------------------------------------
# run_lint — mocked subprocess
# ---------------------------------------------------------------------------

class TestRunLint(unittest.TestCase):

    def test_clean_output_passes(self):
        with patch("subprocess.run",
                   return_value=_make_subprocess_result(_FLAKE8_OUTPUT_CLEAN)):
            report = run_lint(thresholds=LintThresholds(max_e=0, max_w=0, max_f=0, max_c=0))
        self.assertTrue(report.passed)

    def test_violations_exceed_threshold(self):
        with patch("subprocess.run",
                   return_value=_make_subprocess_result(_FLAKE8_OUTPUT_ERRORS_ONLY)):
            report = run_lint(thresholds=LintThresholds(max_e=0))
        self.assertFalse(report.passed)
        self.assertTrue(any("E" in e for e in report.exceeded))

    def test_violations_within_threshold(self):
        with patch("subprocess.run",
                   return_value=_make_subprocess_result(_FLAKE8_OUTPUT_ERRORS_ONLY)):
            report = run_lint(thresholds=LintThresholds(max_e=10, max_w=100, max_f=10, max_c=10))
        self.assertTrue(report.passed)

    def test_report_contains_violations(self):
        with patch("subprocess.run",
                   return_value=_make_subprocess_result(_FLAKE8_OUTPUT_MIXED)):
            report = run_lint(thresholds=LintThresholds(max_e=999, max_w=999, max_f=999, max_c=999))
        self.assertEqual(len(report.violations), 5)

    def test_flake8_not_found_raises(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaises(RuntimeError):
                run_lint(thresholds=LintThresholds())

    def test_timeout_raises(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("flake8", 120)):
            with self.assertRaises(RuntimeError):
                run_lint(thresholds=LintThresholds())

    def test_counts_correct(self):
        with patch("subprocess.run",
                   return_value=_make_subprocess_result(_FLAKE8_OUTPUT_MIXED)):
            report = run_lint(thresholds=LintThresholds(max_e=99, max_w=99, max_f=99, max_c=99))
        self.assertEqual(report.counts["E"], 2)
        self.assertEqual(report.counts["W"], 1)
        self.assertEqual(report.counts["F"], 1)
        self.assertEqual(report.counts["C"], 1)


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_on_pass(self):
        with patch.object(_mod, "run_lint",
                          return_value=LintReport()):
            code = run(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_1_on_fail(self):
        with patch.object(_mod, "run_lint",
                          return_value=LintReport(exceeded=["E: 5 > 0"])):
            code = run(quiet=True)
        self.assertEqual(code, 1)

    def test_returns_2_on_error(self):
        with patch.object(_mod, "run_lint", side_effect=RuntimeError("flake8 not found")):
            code = run(quiet=True)
        self.assertEqual(code, 2)

    def test_json_output_structure(self):
        with patch.object(_mod, "run_lint", return_value=LintReport()):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=True)
                data = json.loads(mock_out.getvalue())
        for k in ("passed", "counts", "thresholds", "exceeded", "violations"):
            self.assertIn(k, data)

    def test_quiet_suppresses_output(self):
        with patch.object(_mod, "run_lint", return_value=LintReport()):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_text_output_shows_counts(self):
        report = LintReport(counts={"E": 0, "W": 2, "F": 0, "C": 0})
        with patch.object(_mod, "run_lint", return_value=report):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=False)
                output = mock_out.getvalue()
        self.assertIn("W", output)

    def test_text_output_shows_passed(self):
        with patch.object(_mod, "run_lint", return_value=LintReport()):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=False)
                output = mock_out.getvalue()
        self.assertIn("passed", output.lower())


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_pass_returns_0(self):
        with patch.object(_mod, "run_lint", return_value=LintReport()):
            rc = _mod.main(["--quiet"])
        self.assertEqual(rc, 0)

    def test_main_fail_returns_1(self):
        with patch.object(_mod, "run_lint",
                          return_value=LintReport(exceeded=["E: 1 > 0"])):
            rc = _mod.main(["--quiet"])
        self.assertEqual(rc, 1)

    def test_main_json_flag(self):
        with patch.object(_mod, "run_lint", return_value=LintReport()):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--json"])
                data = json.loads(mock_out.getvalue())
        self.assertIn("passed", data)

    def test_main_max_e_override(self):
        # With --max-e 10, an E count of 5 should pass
        report = LintReport(counts={"E": 5, "W": 0, "F": 0, "C": 0})
        with patch.object(_mod, "run_lint", return_value=report):
            rc = _mod.main(["--quiet", "--max-e", "10"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
