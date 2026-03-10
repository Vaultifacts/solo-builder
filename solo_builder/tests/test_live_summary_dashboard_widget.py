"""Tests for HealthTabLiveRunCheck — TASK-381.

Covers:
  1. dashboard.html — live-summary-detailed-content div present in Health tab
  2. dashboard_panels.js — pollLiveSummaryDetailed exported and well-formed
  3. dashboard.js — pollLiveSummaryDetailed imported and called in tick()
  4. GET /health/live-summary endpoint (shape, aggregation, pass/fail counts)
"""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
import api.blueprints.live_summary as ls_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestLiveSummaryDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_div_present(self):
        self.assertIn('id="live-summary-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        ls_pos     = self._html.index('id="live-summary-detailed-content"')
        self.assertGreater(ls_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading live summary", self._html)

    def test_div_before_health_detailed(self):
        ls_pos  = self._html.index('id="live-summary-detailed-content"')
        hdc_pos = self._html.index('id="health-detailed-content"')
        self.assertLess(ls_pos, hdc_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestLiveSummaryPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollLiveSummaryDetailed_exported(self):
        self.assertIn("export async function pollLiveSummaryDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/live-summary", self._js)

    def test_content_el_queried(self):
        self.assertIn("live-summary-detailed-content", self._js)

    def test_passed_rendered(self):
        self.assertIn("d.passed", self._js)

    def test_total_rendered(self):
        self.assertIn("d.total", self._js)

    def test_check_name_rendered(self):
        self.assertIn("c.name", self._js)

    def test_ok_badge_shown(self):
        self.assertIn('"OK"', self._js)

    def test_fail_badge_shown(self):
        self.assertIn('"FAIL"', self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No live checks configured.", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestLiveSummaryMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollLiveSummaryDetailed_imported(self):
        self.assertIn("pollLiveSummaryDetailed", self._js)

    def test_pollLiveSummaryDetailed_called_in_tick(self):
        self.assertIn("pollLiveSummaryDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollLiveSummaryDetailed[^}]*\}\s*from\s*["\']\./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check(name="threat-model", ok=True):
    return {"name": name, "ok": ok, "detail": ""}


def _mock_runners(results):
    """Build a list of runner mocks returning the given results."""
    mocks = []
    for r in results:
        fn = MagicMock(return_value=r)
        fn.__name__ = f"_run_{r['name'].replace('-', '_')}"
        mocks.append(fn)
    return mocks


# ---------------------------------------------------------------------------
# 4. Endpoint tests
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

    def _get(self, runners=None):
        if runners is None:
            runners = [
                _check("threat-model", True),
                _check("context-window", True),
                _check("slo", True),
            ]
            mocks = _mock_runners(runners)
        else:
            mocks = runners
        with patch.object(ls_mod, "_CHECK_RUNNERS", new=mocks):
            return self.client.get("/health/live-summary")

    def _data(self, runners=None):
        return json.loads(self._get(runners=runners).data)


class TestLiveSummaryEndpointStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


class TestLiveSummaryEndpointShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_passed_key_present(self):
        self.assertIn("passed", self._data())

    def test_total_key_present(self):
        self.assertIn("total", self._data())

    def test_checks_key_present(self):
        self.assertIn("checks", self._data())

    def test_checks_is_list(self):
        self.assertIsInstance(self._data()["checks"], list)

    def test_ok_is_bool(self):
        self.assertIsInstance(self._data()["ok"], bool)


class TestLiveSummaryEndpointBehavior(_Base):

    def test_ok_true_when_all_pass(self):
        runners = _mock_runners([_check("a", True), _check("b", True)])
        self.assertTrue(self._data(runners)["ok"])

    def test_ok_false_when_any_fail(self):
        runners = _mock_runners([_check("a", True), _check("b", False)])
        self.assertFalse(self._data(runners)["ok"])

    def test_passed_count_all_pass(self):
        runners = _mock_runners([_check("a", True), _check("b", True), _check("c", True)])
        self.assertEqual(self._data(runners)["passed"], 3)

    def test_passed_count_partial(self):
        runners = _mock_runners([_check("a", True), _check("b", False)])
        self.assertEqual(self._data(runners)["passed"], 1)

    def test_total_reflects_runner_count(self):
        runners = _mock_runners([_check("a"), _check("b"), _check("c")])
        self.assertEqual(self._data(runners)["total"], 3)

    def test_default_three_checks(self):
        self.assertEqual(self._data()["total"], 3)

    def test_check_has_name(self):
        check = self._data()["checks"][0]
        self.assertIn("name", check)

    def test_check_has_ok_field(self):
        check = self._data()["checks"][0]
        self.assertIn("ok", check)

    def test_check_names_in_order(self):
        names = [c["name"] for c in self._data()["checks"]]
        self.assertEqual(names, ["threat-model", "context-window", "slo"])


if __name__ == "__main__":
    unittest.main()
