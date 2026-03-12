"""Tests for ContextWindowDashboardWidget — TASK-372 (AI-008 to AI-013).

Covers:
  1. dashboard.html — context-window-detailed-content div present in Health tab
  2. dashboard_panels.js — pollContextWindowDetailed exported and well-formed
  3. dashboard.js — pollContextWindowDetailed imported and called in tick()
  4. /health/context-window endpoint integration (light)
"""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
import api.blueprints.context_window as cw_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_health.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestContextWindowDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_context_window_detailed_content_div_present(self):
        self.assertIn('id="context-window-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        cw_pos     = self._html.index('id="context-window-detailed-content"')
        self.assertGreater(cw_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading context window", self._html)

    def test_div_after_policy_div(self):
        policy_pos = self._html.index('id="policy-detailed-content"')
        cw_pos     = self._html.index('id="context-window-detailed-content"')
        self.assertGreater(cw_pos, policy_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestContextWindowPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollContextWindowDetailed_exported(self):
        self.assertIn("export async function pollContextWindowDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/context-window", self._js)

    def test_content_el_queried(self):
        self.assertIn("context-window-detailed-content", self._js)

    def test_has_issues_rendered(self):
        self.assertIn("has_issues", self._js)

    def test_utilization_rendered(self):
        self.assertIn("utilization", self._js)

    def test_status_rendered(self):
        self.assertIn("r.status", self._js)

    def test_label_rendered(self):
        self.assertIn("r.label", self._js)

    def test_lines_rendered(self):
        self.assertIn("r.lines", self._js)

    def test_budget_rendered(self):
        self.assertIn("r.budget", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No tracked files", self._js)

    def test_over_budget_status(self):
        self.assertIn("over_budget", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestContextWindowMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollContextWindowDetailed_imported(self):
        self.assertIn("pollContextWindowDetailed", self._js)

    def test_pollContextWindowDetailed_called_in_tick(self):
        self.assertIn("pollContextWindowDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollContextWindowDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# 4. Endpoint integration
# ---------------------------------------------------------------------------

class TestContextWindowEndpointViaWidget(unittest.TestCase):

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

    def _data(self):
        from unittest.mock import MagicMock
        mock_report = MagicMock()
        mock_report.has_issues = False
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "label": "CLAUDE.md", "path": "/fake/CLAUDE.md",
            "lines": 50, "budget": 200, "utilization": 25.0, "status": "ok",
        }
        mock_report.results = [mock_result]
        mock_cwb = MagicMock()
        mock_cwb.check_budget.return_value = mock_report
        with patch.object(cw_mod, "_load_tool", return_value=mock_cwb):
            return json.loads(self.client.get("/health/context-window").data)

    def test_endpoint_accessible(self):
        from unittest.mock import MagicMock
        mock_report = MagicMock()
        mock_report.has_issues = False
        mock_report.results = []
        mock_cwb = MagicMock()
        mock_cwb.check_budget.return_value = mock_report
        with patch.object(cw_mod, "_load_tool", return_value=mock_cwb):
            resp = self.client.get("/health/context-window")
        self.assertEqual(resp.status_code, 200)

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_has_issues_key_present(self):
        self.assertIn("has_issues", self._data())

    def test_results_key_present(self):
        self.assertIn("results", self._data())

    def test_content_type_json(self):
        from unittest.mock import MagicMock
        mock_report = MagicMock()
        mock_report.has_issues = False
        mock_report.results = []
        mock_cwb = MagicMock()
        mock_cwb.check_budget.return_value = mock_report
        with patch.object(cw_mod, "_load_tool", return_value=mock_cwb):
            resp = self.client.get("/health/context-window")
        self.assertIn("application/json", resp.content_type)


if __name__ == "__main__":
    unittest.main()
