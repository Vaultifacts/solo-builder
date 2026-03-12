"""Tests for DebtScanDashboardWidget — TASK-377 (ME-003).

Covers:
  1. dashboard.html — debt-scan-detailed-content div present in Health tab
  2. dashboard_panels.js — pollDebtScanDetailed exported and well-formed
  3. dashboard.js — pollDebtScanDetailed imported and called in tick()
  4. GET /health/debt-scan endpoint (shape, ok, count, results)
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
import api.blueprints.debt_scan as ds_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_health.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestDebtScanDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_div_present(self):
        self.assertIn('id="debt-scan-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        ds_pos     = self._html.index('id="debt-scan-detailed-content"')
        self.assertGreater(ds_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading debt scan", self._html)

    def test_div_after_prompt_regression_div(self):
        pr_pos = self._html.index('id="prompt-regression-detailed-content"')
        ds_pos = self._html.index('id="debt-scan-detailed-content"')
        self.assertGreater(ds_pos, pr_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestDebtScanPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollDebtScanDetailed_exported(self):
        self.assertIn("export async function pollDebtScanDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/debt-scan", self._js)

    def test_content_el_queried(self):
        self.assertIn("debt-scan-detailed-content", self._js)

    def test_ok_flag_used(self):
        self.assertIn("d.ok", self._js)

    def test_count_rendered(self):
        self.assertIn("d.count", self._js)

    def test_marker_rendered(self):
        self.assertIn("r.marker", self._js)

    def test_path_rendered(self):
        self.assertIn("r.path", self._js)

    def test_text_rendered(self):
        self.assertIn("r.text", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No debt items found", self._js)

    def test_fixme_marker_color_defined(self):
        self.assertIn("FIXME", self._js)

    def test_todo_marker_color_defined(self):
        self.assertIn("TODO", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestDebtScanMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollDebtScanDetailed_imported(self):
        self.assertIn("pollDebtScanDetailed", self._js)

    def test_pollDebtScanDetailed_called_in_tick(self):
        self.assertIn("pollDebtScanDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollDebtScanDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(path="solo_builder/foo.py", line=42, marker="TODO", text="fix this"):
    m = MagicMock()
    m.path = path
    m.line = line
    m.marker = marker
    m.text = text
    return m


def _mock_ds(items=None):
    mod = MagicMock()
    if items is None:
        items = [_item()]
    mod.scan.return_value = items
    return mod


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

    def _get(self, mod=None):
        if mod is None:
            mod = _mock_ds()
        with patch.object(ds_mod, "_load_tool", return_value=mod):
            return self.client.get("/health/debt-scan")

    def _data(self, mod=None):
        return json.loads(self._get(mod=mod).data)


class TestDebtScanEndpointStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


class TestDebtScanEndpointShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_count_key_present(self):
        self.assertIn("count", self._data())

    def test_results_key_present(self):
        self.assertIn("results", self._data())

    def test_results_is_list(self):
        self.assertIsInstance(self._data()["results"], list)

    def test_ok_is_bool(self):
        self.assertIsInstance(self._data()["ok"], bool)


class TestDebtScanEndpointBehavior(_Base):

    def test_ok_true_when_no_items(self):
        mod = _mock_ds(items=[])
        self.assertTrue(self._data(mod)["ok"])

    def test_ok_false_when_items_exist(self):
        mod = _mock_ds(items=[_item()])
        self.assertFalse(self._data(mod)["ok"])

    def test_count_zero_when_no_items(self):
        mod = _mock_ds(items=[])
        self.assertEqual(self._data(mod)["count"], 0)

    def test_count_reflects_all_items(self):
        mod = _mock_ds(items=[_item()] * 3)
        self.assertEqual(self._data(mod)["count"], 3)

    def test_results_capped_at_20(self):
        mod = _mock_ds(items=[_item()] * 25)
        d = self._data(mod)
        self.assertEqual(d["count"], 25)
        self.assertLessEqual(len(d["results"]), 20)

    def test_result_has_path(self):
        self.assertIn("path", self._data()["results"][0])

    def test_result_has_line(self):
        self.assertIn("line", self._data()["results"][0])

    def test_result_has_marker(self):
        self.assertIn("marker", self._data()["results"][0])

    def test_result_has_text(self):
        self.assertIn("text", self._data()["results"][0])


if __name__ == "__main__":
    unittest.main()
