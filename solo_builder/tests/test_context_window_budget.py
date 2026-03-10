"""Tests for tools/context_window_budget.py (TASK-355, AI-008 to AI-013)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "context_window_budget", _TOOLS_DIR / "context_window_budget.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["context_window_budget"] = _mod
_spec.loader.exec_module(_mod)

check_budget       = _mod.check_budget
BudgetConfig       = _mod.BudgetConfig
BudgetReport       = _mod.BudgetReport
FileResult         = _mod.FileResult
load_budget_config = _mod.load_budget_config
run                = _mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_files(tmp, contents: dict[str, str]) -> list[tuple[str, Path, str]]:
    """Create temp files and return tracked_files list."""
    tmp = Path(tmp)
    result = []
    for label, content in contents.items():
        p = tmp / f"{label}.md"
        p.write_text(content, encoding="utf-8")
        result.append((label, p, f"CW_BUDGET_{label.upper().replace('.', '_')}"))
    return result


def _make_config(budgets: dict[str, int], warn_pct: float = 70.0, crit_pct: float = 90.0) -> BudgetConfig:
    return BudgetConfig(budgets=budgets, warn_pct=warn_pct, crit_pct=crit_pct)


def _lines(n: int) -> str:
    return "\n".join(f"line {i}" for i in range(n))


# ---------------------------------------------------------------------------
# BudgetConfig
# ---------------------------------------------------------------------------

class TestBudgetConfig(unittest.TestCase):

    def test_immutable(self):
        c = BudgetConfig(budgets={"A": 100})
        with self.assertRaises((AttributeError, TypeError)):
            c.warn_pct = 50.0  # type: ignore[misc]

    def test_default_thresholds(self):
        c = BudgetConfig(budgets={})
        self.assertEqual(c.warn_pct, 70.0)
        self.assertEqual(c.crit_pct, 90.0)


# ---------------------------------------------------------------------------
# load_budget_config
# ---------------------------------------------------------------------------

class TestLoadBudgetConfig(unittest.TestCase):

    def test_missing_settings_uses_defaults(self):
        c = load_budget_config(settings_path=Path("/nonexistent/settings.json"))
        self.assertGreater(c.budgets.get("CLAUDE.md", 0), 0)

    def test_settings_override_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"CW_BUDGET_CLAUDE_MD": 50}), encoding="utf-8")
            c = load_budget_config(settings_path=p)
        self.assertEqual(c.budgets["CLAUDE.md"], 50)

    def test_settings_override_warn_pct(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"CW_BUDGET_WARN_PCT": 60}), encoding="utf-8")
            c = load_budget_config(settings_path=p)
        self.assertAlmostEqual(c.warn_pct, 60.0)

    def test_partial_settings_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"CW_BUDGET_CLAUDE_MD": 300}), encoding="utf-8")
            c = load_budget_config(settings_path=p)
        self.assertAlmostEqual(c.warn_pct, 70.0)


# ---------------------------------------------------------------------------
# FileResult / BudgetReport
# ---------------------------------------------------------------------------

class TestFileResult(unittest.TestCase):

    def test_to_dict_keys(self):
        r = FileResult("A", "/a.md", 50, 100, 50.0, "ok")
        d = r.to_dict()
        for k in ("label", "path", "lines", "budget", "utilization", "status"):
            self.assertIn(k, d)

    def test_utilization_rounded(self):
        r = FileResult("A", "/a.md", 73, 100, 73.333, "warn")
        d = r.to_dict()
        self.assertEqual(d["utilization"], 73.3)


class TestBudgetReport(unittest.TestCase):

    def test_all_ok_no_issues(self):
        r = BudgetReport(results=[
            FileResult("A", "/a", 10, 100, 10.0, "ok"),
        ])
        self.assertFalse(r.has_issues)

    def test_warn_triggers_issues(self):
        r = BudgetReport(results=[
            FileResult("A", "/a", 75, 100, 75.0, "warn"),
        ])
        self.assertTrue(r.has_issues)

    def test_critical_triggers_issues(self):
        r = BudgetReport(results=[
            FileResult("A", "/a", 95, 100, 95.0, "critical"),
        ])
        self.assertTrue(r.has_issues)

    def test_over_budget_triggers_issues(self):
        r = BudgetReport(results=[
            FileResult("A", "/a", 120, 100, 120.0, "over_budget"),
        ])
        self.assertTrue(r.has_issues)

    def test_missing_no_issue(self):
        r = BudgetReport(results=[
            FileResult("A", "/a", None, 100, 0.0, "missing"),
        ])
        self.assertFalse(r.has_issues)

    def test_to_dict_structure(self):
        r = BudgetReport(results=[FileResult("A", "/a", 10, 100, 10.0, "ok")])
        d = r.to_dict()
        self.assertIn("has_issues", d)
        self.assertIn("results", d)


# ---------------------------------------------------------------------------
# check_budget
# ---------------------------------------------------------------------------

class TestCheckBudget(unittest.TestCase):

    def test_ok_within_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = _make_files(tmp, {"A": _lines(10)})
            config = _make_config({"A": 100})
            report = check_budget(config=config, tracked_files=files)
        self.assertFalse(report.has_issues)
        self.assertEqual(report.results[0].status, "ok")

    def test_warn_at_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = _make_files(tmp, {"A": _lines(70)})  # 70/100 = 70% = warn threshold
            config = _make_config({"A": 100}, warn_pct=70.0)
            report = check_budget(config=config, tracked_files=files)
        self.assertEqual(report.results[0].status, "warn")

    def test_critical_at_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = _make_files(tmp, {"A": _lines(90)})
            config = _make_config({"A": 100}, warn_pct=70.0, crit_pct=90.0)
            report = check_budget(config=config, tracked_files=files)
        self.assertEqual(report.results[0].status, "critical")

    def test_over_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = _make_files(tmp, {"A": _lines(110)})
            config = _make_config({"A": 100})
            report = check_budget(config=config, tracked_files=files)
        self.assertEqual(report.results[0].status, "over_budget")

    def test_missing_file_status(self):
        config = _make_config({"A": 100})
        files = [("A", Path("/nonexistent/A.md"), "CW_BUDGET_A")]
        report = check_budget(config=config, tracked_files=files)
        self.assertEqual(report.results[0].status, "missing")
        self.assertIsNone(report.results[0].lines)

    def test_utilization_calculated(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = _make_files(tmp, {"A": _lines(50)})
            config = _make_config({"A": 100})
            report = check_budget(config=config, tracked_files=files)
        self.assertAlmostEqual(report.results[0].utilization, 50.0, places=0)

    def test_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = _make_files(tmp, {"A": _lines(10), "B": _lines(80)})
            config = _make_config({"A": 100, "B": 100}, warn_pct=70.0)
            report = check_budget(config=config, tracked_files=files)
        self.assertEqual(len(report.results), 2)
        statuses = {r.label: r.status for r in report.results}
        self.assertEqual(statuses["A"], "ok")
        self.assertEqual(statuses["B"], "warn")


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_all_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = _make_files(tmp, {"A": _lines(10)})
            config = _make_config({"A": 100})
            report = check_budget(config=config, tracked_files=files)
        with patch.object(_mod, "check_budget", return_value=report):
            code = run(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_1_with_warn(self):
        report = BudgetReport(results=[FileResult("A", "/a", 80, 100, 80.0, "warn")])
        with patch.object(_mod, "check_budget", return_value=report):
            code = run(quiet=True)
        self.assertEqual(code, 1)

    def test_json_output_structure(self):
        report = BudgetReport(results=[FileResult("A", "/a", 10, 100, 10.0, "ok")])
        with patch.object(_mod, "check_budget", return_value=report):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(as_json=True)
                data = json.loads(mock_out.getvalue())
        self.assertIn("has_issues", data)
        self.assertIn("results", data)

    def test_quiet_suppresses_output(self):
        report = BudgetReport(results=[FileResult("A", "/a", 10, 100, 10.0, "ok")])
        with patch.object(_mod, "check_budget", return_value=report):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_text_output_shows_budget(self):
        report = BudgetReport(results=[FileResult("CLAUDE.md", "/a", 50, 200, 25.0, "ok")])
        with patch.object(_mod, "check_budget", return_value=report):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run()
                output = mock_out.getvalue()
        self.assertIn("CLAUDE.md", output)

    def test_text_output_shows_compaction_hint_on_issue(self):
        report = BudgetReport(results=[FileResult("A", "/a", 95, 100, 95.0, "critical")])
        with patch.object(_mod, "check_budget", return_value=report):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run()
                output = mock_out.getvalue()
        self.assertIn("compact", output.lower())


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_0_or_1(self):
        rc = _mod.main(["--quiet"])
        self.assertIn(rc, (0, 1))

    def test_main_json_flag(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            _mod.main(["--json"])
            data = json.loads(mock_out.getvalue())
        self.assertIn("has_issues", data)


if __name__ == "__main__":
    unittest.main()
