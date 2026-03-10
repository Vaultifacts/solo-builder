"""Tests for GatesDashboardWidget — TASK-369 (AI-026, AI-033).

Covers:
  1. dashboard.html — gates-detailed-content div present in Health tab
  2. dashboard_panels.js — pollGatesDetailed exported and well-formed
  3. dashboard.js — pollGatesDetailed imported and called in tick()
  4. /executor/gates endpoint integration (light)
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

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestGatesDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_gates_detailed_content_div_present(self):
        self.assertIn('id="gates-detailed-content"', self._html)

    def test_gates_div_inside_health_tab(self):
        # Both the health tab and gates div must appear, health tab first
        health_pos = self._html.index('id="tab-health"')
        gates_pos  = self._html.index('id="gates-detailed-content"')
        self.assertGreater(gates_pos, health_pos)

    def test_gates_loading_placeholder(self):
        self.assertIn("Loading gates", self._html)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestGatesPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollGatesDetailed_exported(self):
        self.assertIn("export async function pollGatesDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/executor/gates", self._js)

    def test_gates_content_el_queried(self):
        self.assertIn("gates-detailed-content", self._js)

    def test_blocked_label_present(self):
        self.assertIn("BLOCKED", self._js)

    def test_hitl_name_rendered(self):
        self.assertIn("hitl_name", self._js)

    def test_scope_denied_rendered(self):
        self.assertIn("scope_denied", self._js)

    def test_running_count_in_header(self):
        self.assertIn("running_count", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No Running subtasks", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestGatesMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollGatesDetailed_imported(self):
        self.assertIn("pollGatesDetailed", self._js)

    def test_pollGatesDetailed_called_in_tick(self):
        self.assertIn("pollGatesDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollGatesDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# 4. Endpoint integration
# ---------------------------------------------------------------------------

class TestGatesEndpointViaWidget(unittest.TestCase):

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

    def test_endpoint_accessible(self):
        resp = self.client.get("/executor/gates")
        self.assertEqual(resp.status_code, 200)

    def test_empty_dag_ok_true(self):
        data = json.loads(self.client.get("/executor/gates").data)
        self.assertTrue(data["ok"])

    def test_gates_key_present(self):
        data = json.loads(self.client.get("/executor/gates").data)
        self.assertIn("gates", data)

    def test_content_type_json(self):
        resp = self.client.get("/executor/gates")
        self.assertIn("application/json", resp.content_type)


if __name__ == "__main__":
    unittest.main()
