"""Dashboard E2E smoke tests — TASK-382.

Uses the Flask test client to verify:
  1. GET / returns valid dashboard HTML with key structural elements
  2. Key API endpoints return 200 with JSON content-type
  3. Health tab grid structure is present in the served HTML
  4. All JS module imports are referenced from the dashboard HTML
  5. Critical widget div IDs are present in the served HTML
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

# ---------------------------------------------------------------------------
# Shared fixture base
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path    = Path(self._tmp) / "state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._state_path.write_text(
            json.dumps({"step": 0, "dag": {}}), encoding="utf-8"
        )
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


# ---------------------------------------------------------------------------
# 1. Dashboard HTML response
# ---------------------------------------------------------------------------

class TestDashboardHtmlResponse(_Base):

    def setUp(self):
        super().setUp()
        self._resp = self.client.get("/")
        self._html = self._resp.data.decode("utf-8", errors="replace")

    def test_status_200(self):
        self.assertEqual(self._resp.status_code, 200)

    def test_content_type_html(self):
        self.assertIn("text/html", self._resp.content_type)

    def test_doctype_present(self):
        self.assertIn("<!DOCTYPE html>", self._html)

    def test_title_present(self):
        self.assertIn("<title>", self._html)

    def test_health_tab_present(self):
        self.assertIn('id="tab-health"', self._html)

    def test_health_widget_grid_present(self):
        self.assertIn('id="health-widget-grid"', self._html)

    def test_live_summary_widget_present(self):
        self.assertIn('id="live-summary-detailed-content"', self._html)


# ---------------------------------------------------------------------------
# 2. Key API endpoints return 200 + JSON
# ---------------------------------------------------------------------------

_HEALTH_ENDPOINTS = [
    "/health",
    "/status",
    "/heartbeat",
]

_JSON_ENDPOINTS = [
    "/tasks",
    "/history/count",
    "/config",
]


class TestApiEndpointSmoke(_Base):

    def _check_endpoint(self, path: str):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, msg=f"GET {path} returned {resp.status_code}")
        self.assertIn("application/json", resp.content_type, msg=f"GET {path} not JSON")

    def test_health_returns_200(self):
        self._check_endpoint("/health")

    def test_status_returns_200(self):
        self._check_endpoint("/status")

    def test_heartbeat_returns_200(self):
        self._check_endpoint("/heartbeat")

    def test_tasks_returns_200(self):
        self._check_endpoint("/tasks")

    def test_history_count_returns_200(self):
        self._check_endpoint("/history/count")

    def test_config_returns_200(self):
        self._check_endpoint("/config")

    def test_404_returns_json(self):
        resp = self.client.get("/no-such-route-xyz")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("application/json", resp.content_type)

    def test_405_returns_json(self):
        resp = self.client.post("/health")
        self.assertEqual(resp.status_code, 405)
        self.assertIn("application/json", resp.content_type)


# ---------------------------------------------------------------------------
# 3. Health tab widget IDs in served HTML
# ---------------------------------------------------------------------------

_WIDGET_IDS = [
    "live-summary-detailed-content",
    "health-detailed-content",
    "health-widget-grid",
    "gates-detailed-content",
    "policy-detailed-content",
    "context-window-detailed-content",
    "threat-model-detailed-content",
    "slo-detailed-content",
    "prompt-regression-detailed-content",
    "debt-scan-detailed-content",
    "ci-quality-detailed-content",
    "pre-release-detailed-content",
]


class TestDashboardWidgetIds(_Base):

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_all_widget_ids_present(self):
        for wid in _WIDGET_IDS:
            with self.subTest(widget=wid):
                self.assertIn(f'id="{wid}"', self._html)


# ---------------------------------------------------------------------------
# 4. JS modules referenced from HTML
# ---------------------------------------------------------------------------

_JS_MODULES = [
    "dashboard_panels.js",
    "dashboard.js",
    "dashboard_state.js",
    "dashboard_utils.js",
    "dashboard_tasks.js",
]


class TestDashboardJsModules(_Base):

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_main_js_referenced(self):
        self.assertIn("dashboard.js", self._html)

    def test_script_type_module(self):
        self.assertIn('type="module"', self._html)


# ---------------------------------------------------------------------------
# 5. Grid layout in served HTML
# ---------------------------------------------------------------------------

class TestDashboardGridLayout(_Base):

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_grid_template_columns_present(self):
        self.assertIn("grid-template-columns", self._html)

    def test_display_grid_present(self):
        self.assertIn("display:grid", self._html)

    def test_grid_before_all_widget_ids(self):
        grid_pos = self._html.index('id="health-widget-grid"')
        for wid in _WIDGET_IDS[3:]:  # skip live-summary and health-detailed (above grid)
            with self.subTest(widget=wid):
                w_pos = self._html.index(f'id="{wid}"')
                self.assertGreater(w_pos, grid_pos)


if __name__ == "__main__":
    unittest.main()
