"""Tests for GET /health/context-window endpoint (TASK-370, AI-008 to AI-013)."""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
import api.blueprints.context_window as cw_mod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR  = _REPO_ROOT / "tools"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(label="CLAUDE.md", lines=100, budget=200,
                 util=50.0, status="ok") -> dict:
    return {
        "label":       label,
        "path":        f"/fake/{label}",
        "lines":       lines,
        "budget":      budget,
        "utilization": util,
        "status":      status,
    }


def _mock_report(has_issues=False, results=None):
    """Return a MagicMock BudgetReport-like object."""
    if results is None:
        results = [_make_result()]
    mock_r = MagicMock()
    mock_r.has_issues = has_issues
    mock_fr_list = []
    for r in results:
        fr = MagicMock()
        fr.to_dict.return_value = r
        mock_fr_list.append(fr)
    mock_r.results = mock_fr_list
    return mock_r


def _cwb_mod(has_issues=False, results=None):
    """Build a mock context_window_budget module."""
    report = _mock_report(has_issues=has_issues, results=results)
    mod = MagicMock()
    mod.check_budget.return_value = report
    return mod


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path    = Path(self._tmp) / "state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._state_path.write_text(json.dumps({"step": 0, "dag": {}}), encoding="utf-8")
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "STATE_PATH",    new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read  = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _get(self, cwb=None):
        if cwb is None:
            cwb = _cwb_mod()
        with patch.object(cw_mod, "_load_tool", return_value=cwb):
            return self.client.get("/health/context-window")

    def _data(self, cwb=None):
        return json.loads(self._get(cwb=cwb).data)


# ===========================================================================
# HTTP basics
# ===========================================================================

class TestContextWindowStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


# ===========================================================================
# Response shape
# ===========================================================================

class TestContextWindowShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_has_issues_key_present(self):
        self.assertIn("has_issues", self._data())

    def test_results_key_present(self):
        self.assertIn("results", self._data())

    def test_results_is_list(self):
        self.assertIsInstance(self._data()["results"], list)

    def test_ok_is_bool(self):
        self.assertIsInstance(self._data()["ok"], bool)

    def test_has_issues_is_bool(self):
        self.assertIsInstance(self._data()["has_issues"], bool)


# ===========================================================================
# Ok vs issues
# ===========================================================================

class TestContextWindowOkFlag(_Base):

    def test_ok_true_when_no_issues(self):
        cwb = _cwb_mod(has_issues=False)
        self.assertTrue(self._data(cwb)["ok"])

    def test_ok_false_when_has_issues(self):
        cwb = _cwb_mod(has_issues=True)
        self.assertFalse(self._data(cwb)["ok"])

    def test_has_issues_false_when_ok(self):
        cwb = _cwb_mod(has_issues=False)
        self.assertFalse(self._data(cwb)["has_issues"])

    def test_has_issues_true_when_issues(self):
        cwb = _cwb_mod(has_issues=True)
        self.assertTrue(self._data(cwb)["has_issues"])

    def test_ok_and_has_issues_are_inverse(self):
        for has_issues in (True, False):
            cwb = _cwb_mod(has_issues=has_issues)
            d = self._data(cwb)
            self.assertNotEqual(d["ok"], d["has_issues"])


# ===========================================================================
# Results content
# ===========================================================================

class TestContextWindowResults(_Base):

    def _results(self, **kw):
        cwb = _cwb_mod(**kw)
        return self._data(cwb)["results"]

    def test_results_length_matches(self):
        r = [_make_result("CLAUDE.md"), _make_result("MEMORY.md"), _make_result("JOURNAL.md")]
        cwb = _cwb_mod(results=r)
        self.assertEqual(len(self._data(cwb)["results"]), 3)

    def test_result_has_label(self):
        self.assertIn("label", self._results()[0])

    def test_result_has_path(self):
        self.assertIn("path", self._results()[0])

    def test_result_has_lines(self):
        self.assertIn("lines", self._results()[0])

    def test_result_has_budget(self):
        self.assertIn("budget", self._results()[0])

    def test_result_has_utilization(self):
        self.assertIn("utilization", self._results()[0])

    def test_result_has_status(self):
        self.assertIn("status", self._results()[0])

    def test_result_label_value(self):
        r = [_make_result("MEMORY.md", status="warn")]
        cwb = _cwb_mod(results=r)
        self.assertEqual(self._data(cwb)["results"][0]["label"], "MEMORY.md")

    def test_result_status_value(self):
        r = [_make_result("CLAUDE.md", status="critical")]
        cwb = _cwb_mod(results=r)
        self.assertEqual(self._data(cwb)["results"][0]["status"], "critical")

    def test_result_utilization_value(self):
        r = [_make_result("CLAUDE.md", util=75.0)]
        cwb = _cwb_mod(results=r)
        self.assertAlmostEqual(self._data(cwb)["results"][0]["utilization"], 75.0)


# ===========================================================================
# check_budget called with settings_path
# ===========================================================================

class TestContextWindowCallsCheckBudget(_Base):

    def test_check_budget_called(self):
        cwb = _cwb_mod()
        self._get(cwb=cwb)
        cwb.check_budget.assert_called_once()

    def test_check_budget_receives_settings_path(self):
        cwb = _cwb_mod()
        self._get(cwb=cwb)
        _, kwargs = cwb.check_budget.call_args
        self.assertIn("settings_path", kwargs)


# ===========================================================================
# Empty results
# ===========================================================================

class TestContextWindowEmptyResults(_Base):

    def test_empty_results_ok(self):
        cwb = _cwb_mod(has_issues=False, results=[])
        d = self._data(cwb)
        self.assertTrue(d["ok"])
        self.assertEqual(d["results"], [])


if __name__ == "__main__":
    unittest.main()
