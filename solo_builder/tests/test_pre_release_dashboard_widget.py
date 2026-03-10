"""Tests for PreReleaseDashboardWidget — TASK-379.

Covers:
  1. dashboard.html — pre-release-detailed-content div present in Health tab
  2. dashboard_panels.js — pollPreReleaseDetailed exported and well-formed
  3. dashboard.js — pollPreReleaseDetailed imported and called in tick()
  4. GET /health/pre-release endpoint (shape, ok, total, required, gates)
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
import api.blueprints.pre_release as pr_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestPreReleaseDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_div_present(self):
        self.assertIn('id="pre-release-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        pr_pos     = self._html.index('id="pre-release-detailed-content"')
        self.assertGreater(pr_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading pre-release gates", self._html)

    def test_div_after_ci_quality_div(self):
        cq_pos = self._html.index('id="ci-quality-detailed-content"')
        pr_pos = self._html.index('id="pre-release-detailed-content"')
        self.assertGreater(pr_pos, cq_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestPreReleasePanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollPreReleaseDetailed_exported(self):
        self.assertIn("export async function pollPreReleaseDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/pre-release", self._js)

    def test_content_el_queried(self):
        self.assertIn("pre-release-detailed-content", self._js)

    def test_total_rendered(self):
        self.assertIn("d.total", self._js)

    def test_required_rendered(self):
        self.assertIn("d.required", self._js)

    def test_gate_name_rendered(self):
        self.assertIn("g.name", self._js)

    def test_gate_required_badge(self):
        self.assertIn("g.required", self._js)

    def test_req_badge_text(self):
        self.assertIn('"REQ"', self._js)

    def test_opt_badge_text(self):
        self.assertIn('"OPT"', self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No release gates configured.", self._js)

    def test_header_includes_required(self):
        self.assertIn("required)", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestPreReleaseMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollPreReleaseDetailed_imported(self):
        self.assertIn("pollPreReleaseDetailed", self._js)

    def test_pollPreReleaseDetailed_called_in_tick(self):
        self.assertIn("pollPreReleaseDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollPreReleaseDetailed[^}]*\}\s*from\s*["\']\./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gate(name="python-tests", required=True):
    return {"name": name, "required": required, "command": "echo ok"}


def _mock_prc(builtin=None, verify=None):
    mod = MagicMock()
    if builtin is None:
        builtin = [_gate(n, r) for n, r in [
            ("python-tests", True), ("git-clean", False),
            ("context-window", False), ("slo-check", False),
            ("threat-model", False), ("dep-audit", True),
            ("lock-file-fresh", False), ("prompt-regression", True),
        ]]
    if verify is None:
        verify = []
    mod._builtin_gates.return_value = builtin
    mod._load_verify_gates.return_value = verify
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
            mod = _mock_prc()
        with patch.object(pr_mod, "_load_tool", return_value=mod):
            return self.client.get("/health/pre-release")

    def _data(self, mod=None):
        return json.loads(self._get(mod=mod).data)


class TestPreReleaseEndpointStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


class TestPreReleaseEndpointShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_total_key_present(self):
        self.assertIn("total", self._data())

    def test_required_key_present(self):
        self.assertIn("required", self._data())

    def test_gates_key_present(self):
        self.assertIn("gates", self._data())

    def test_gates_is_list(self):
        self.assertIsInstance(self._data()["gates"], list)

    def test_ok_is_bool(self):
        self.assertIsInstance(self._data()["ok"], bool)


class TestPreReleaseEndpointBehavior(_Base):

    def test_ok_always_true(self):
        self.assertTrue(self._data()["ok"])

    def test_default_eight_builtin_gates(self):
        self.assertEqual(self._data()["total"], 8)

    def test_required_count_correct(self):
        self.assertEqual(self._data()["required"], 3)

    def test_total_includes_verify_gates(self):
        mod = _mock_prc(
            builtin=[_gate("a", True)],
            verify=[_gate("b", False), _gate("c", True)],
        )
        self.assertEqual(self._data(mod)["total"], 3)

    def test_required_count_with_mixed_gates(self):
        mod = _mock_prc(
            builtin=[_gate("a", True), _gate("b", False)],
            verify=[_gate("c", True)],
        )
        self.assertEqual(self._data(mod)["required"], 2)

    def test_gate_has_name(self):
        gate = self._data()["gates"][0]
        self.assertIn("name", gate)

    def test_gate_has_required_field(self):
        gate = self._data()["gates"][0]
        self.assertIn("required", gate)

    def test_gate_required_is_bool(self):
        gate = self._data()["gates"][0]
        self.assertIsInstance(gate["required"], bool)

    def test_unittest_discover_excluded(self):
        mod = _mock_prc(
            builtin=[],
            verify=[_gate("unittest-discover", True), _gate("other", False)],
        )
        names = [g["name"] for g in self._data(mod)["gates"]]
        self.assertNotIn("unittest-discover", names)


if __name__ == "__main__":
    unittest.main()
