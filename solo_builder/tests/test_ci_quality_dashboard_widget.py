"""Tests for CIQualityDashboardWidget — TASK-378.

Covers:
  1. dashboard.html — ci-quality-detailed-content div present in Health tab
  2. dashboard_panels.js — pollCiQualityDetailed exported and well-formed
  3. dashboard.js — pollCiQualityDetailed imported and called in tick()
  4. GET /health/ci-quality endpoint (shape, ok, count, tools)
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
import api.blueprints.ci_quality as cq_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestCiQualityDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_div_present(self):
        self.assertIn('id="ci-quality-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        cq_pos     = self._html.index('id="ci-quality-detailed-content"')
        self.assertGreater(cq_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading CI quality gate", self._html)

    def test_div_after_debt_scan_div(self):
        ds_pos = self._html.index('id="debt-scan-detailed-content"')
        cq_pos = self._html.index('id="ci-quality-detailed-content"')
        self.assertGreater(cq_pos, ds_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestCiQualityPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollCiQualityDetailed_exported(self):
        self.assertIn("export async function pollCiQualityDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/ci-quality", self._js)

    def test_content_el_queried(self):
        self.assertIn("ci-quality-detailed-content", self._js)

    def test_count_rendered(self):
        self.assertIn("d.count", self._js)

    def test_tool_name_rendered(self):
        self.assertIn("t.name", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No CI tools configured.", self._js)

    def test_header_text_includes_configured(self):
        self.assertIn("configured", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestCiQualityMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollCiQualityDetailed_imported(self):
        self.assertIn("pollCiQualityDetailed", self._js)

    def test_pollCiQualityDetailed_called_in_tick(self):
        self.assertIn("pollCiQualityDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollCiQualityDetailed[^}]*\}\s*from\s*["\']\./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_def(name="threat-model"):
    return {"name": name, "command": "echo ok", "timeout": 10}


def _mock_cq(tools=None):
    mod = MagicMock()
    if tools is None:
        tools = [_tool_def(n) for n in ["threat-model", "context-window", "slo-check",
                                         "dep-audit", "debt-scan", "pre-release"]]
    mod._tool_definitions.return_value = tools
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
            mod = _mock_cq()
        with patch.object(cq_mod, "_load_tool", return_value=mod):
            return self.client.get("/health/ci-quality")

    def _data(self, mod=None):
        return json.loads(self._get(mod=mod).data)


class TestCiQualityEndpointStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


class TestCiQualityEndpointShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_count_key_present(self):
        self.assertIn("count", self._data())

    def test_tools_key_present(self):
        self.assertIn("tools", self._data())

    def test_tools_is_list(self):
        self.assertIsInstance(self._data()["tools"], list)

    def test_ok_is_bool(self):
        self.assertIsInstance(self._data()["ok"], bool)


class TestCiQualityEndpointBehavior(_Base):

    def test_ok_always_true(self):
        self.assertTrue(self._data()["ok"])

    def test_count_reflects_tools(self):
        mod = _mock_cq(tools=[_tool_def(n) for n in ["a", "b", "c"]])
        self.assertEqual(self._data(mod)["count"], 3)

    def test_count_zero_when_no_tools(self):
        mod = _mock_cq(tools=[])
        self.assertEqual(self._data(mod)["count"], 0)

    def test_default_six_tools(self):
        self.assertEqual(self._data()["count"], 6)

    def test_tool_has_name(self):
        tools = self._data()["tools"]
        self.assertIn("name", tools[0])

    def test_tool_names_match_definitions(self):
        mod = _mock_cq(tools=[_tool_def("my-tool")])
        tools = self._data(mod)["tools"]
        self.assertEqual(tools[0]["name"], "my-tool")


if __name__ == "__main__":
    unittest.main()
