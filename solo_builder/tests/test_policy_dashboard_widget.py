"""Tests for PolicyDashboardWidget — TASK-371 (AI-026, AI-033).

Covers:
  1. dashboard.html — policy-detailed-content div present in Health tab
  2. dashboard_panels.js — pollPolicyDetailed exported and well-formed
  3. dashboard.js — pollPolicyDetailed imported and called in tick()
  4. /policy/hitl + /policy/scope endpoint integration (light)
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

class TestPolicyDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_policy_detailed_content_div_present(self):
        self.assertIn('id="policy-detailed-content"', self._html)

    def test_policy_div_inside_health_tab(self):
        health_pos  = self._html.index('id="tab-health"')
        policy_pos  = self._html.index('id="policy-detailed-content"')
        self.assertGreater(policy_pos, health_pos)

    def test_policy_loading_placeholder(self):
        self.assertIn("Loading policy", self._html)

    def test_policy_div_after_gates_div(self):
        gates_pos  = self._html.index('id="gates-detailed-content"')
        policy_pos = self._html.index('id="policy-detailed-content"')
        self.assertGreater(policy_pos, gates_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestPolicyPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollPolicyDetailed_exported(self):
        self.assertIn("export async function pollPolicyDetailed", self._js)

    def test_hitl_endpoint_called(self):
        self.assertIn("/policy/hitl", self._js)

    def test_scope_endpoint_called(self):
        self.assertIn("/policy/scope", self._js)

    def test_policy_content_el_queried(self):
        self.assertIn("policy-detailed-content", self._js)

    def test_pause_tools_rendered(self):
        self.assertIn("pause_tools", self._js)

    def test_block_keywords_rendered(self):
        self.assertIn("block_keywords", self._js)

    def test_default_action_type_rendered(self):
        self.assertIn("default_action_type", self._js)

    def test_allowlists_rendered(self):
        self.assertIn("allowlists", self._js)

    def test_warnings_rendered(self):
        self.assertIn("warnings", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_hitl_label_present(self):
        self.assertIn("HITL", self._js)

    def test_scope_label_present(self):
        self.assertIn("Scope", self._js)

    def test_promise_all_used(self):
        self.assertIn("Promise.all", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestPolicyMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollPolicyDetailed_imported(self):
        self.assertIn("pollPolicyDetailed", self._js)

    def test_pollPolicyDetailed_called_in_tick(self):
        self.assertIn("pollPolicyDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollPolicyDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# 4. Endpoint integration
# ---------------------------------------------------------------------------

class TestPolicyEndpointsViaWidget(unittest.TestCase):

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

    def test_hitl_endpoint_accessible(self):
        resp = self.client.get("/policy/hitl")
        self.assertEqual(resp.status_code, 200)

    def test_scope_endpoint_accessible(self):
        resp = self.client.get("/policy/scope")
        self.assertEqual(resp.status_code, 200)

    def test_hitl_ok_key_present(self):
        data = json.loads(self.client.get("/policy/hitl").data)
        self.assertIn("ok", data)

    def test_scope_ok_key_present(self):
        data = json.loads(self.client.get("/policy/scope").data)
        self.assertIn("ok", data)

    def test_hitl_policy_key_present(self):
        data = json.loads(self.client.get("/policy/hitl").data)
        self.assertIn("policy", data)

    def test_scope_allowlists_present(self):
        data = json.loads(self.client.get("/policy/scope").data)
        self.assertIn("allowlists", data["policy"])


if __name__ == "__main__":
    unittest.main()
