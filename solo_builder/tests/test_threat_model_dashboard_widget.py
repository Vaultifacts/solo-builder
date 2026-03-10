"""Tests for ThreatModelDashboardWidget — TASK-374 (SE-001 to SE-006).

Covers:
  1. dashboard.html — threat-model-detailed-content div present in Health tab
  2. dashboard_panels.js — pollThreatModelDetailed exported and well-formed
  3. dashboard.js — pollThreatModelDetailed imported and called in tick()
  4. GET /health/threat-model endpoint (shape, ok flag, checks list)
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
import api.blueprints.threat_model as tm_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestThreatModelDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_threat_model_div_present(self):
        self.assertIn('id="threat-model-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        tm_pos     = self._html.index('id="threat-model-detailed-content"')
        self.assertGreater(tm_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading threat model", self._html)

    def test_div_after_context_window_div(self):
        cw_pos = self._html.index('id="context-window-detailed-content"')
        tm_pos = self._html.index('id="threat-model-detailed-content"')
        self.assertGreater(tm_pos, cw_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestThreatModelPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollThreatModelDetailed_exported(self):
        self.assertIn("export async function pollThreatModelDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/threat-model", self._js)

    def test_content_el_queried(self):
        self.assertIn("threat-model-detailed-content", self._js)

    def test_checks_rendered(self):
        self.assertIn("d.checks", self._js)

    def test_ok_flag_used(self):
        self.assertIn("d.ok", self._js)

    def test_check_name_rendered(self):
        self.assertIn("c.name", self._js)

    def test_check_passed_rendered(self):
        self.assertIn("c.passed", self._js)

    def test_check_detail_rendered(self):
        self.assertIn("c.detail", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No threat model checks available", self._js)

    def test_ok_badge_present(self):
        self.assertIn('"OK"', self._js)

    def test_fail_badge_present(self):
        self.assertIn('"FAIL"', self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestThreatModelMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollThreatModelDetailed_imported(self):
        self.assertIn("pollThreatModelDetailed", self._js)

    def test_pollThreatModelDetailed_called_in_tick(self):
        self.assertIn("pollThreatModelDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollThreatModelDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Helpers for endpoint tests
# ---------------------------------------------------------------------------

def _check(name, required=True, passed=True, detail=""):
    """Return a mock CheckResult-like NamedTuple substitute."""
    m = MagicMock()
    m.name = name
    m.required = required
    m.passed = passed
    m.detail = detail
    return m


def _mock_tm(file_ok=True):
    """Build a mock threat_model_check module using a temp or missing path."""
    import tempfile, os
    mod = MagicMock()

    if file_ok:
        # Create a real temp file so blueprint can read it
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        tmp.write("SE-001 SE-002 SE-003 SE-004 SE-005 SE-006\n"
                  "Last updated: 2026-01-01\nhitl HitlPolicy ToolScopePolicy secret_scan\n")
        tmp.close()
        mod.THREAT_MODEL_PATH = Path(tmp.name)
    else:
        mod.THREAT_MODEL_PATH = Path("/nonexistent/THREAT_MODEL.md")

    file_check = _check("file-exists", passed=file_ok)
    mod._check_file_exists.return_value = file_check

    if file_ok:
        gap_check  = _check("gap-ids",         passed=True)
        date_check = _check("date",             passed=True)
        ctrl_check = [_check("control-hitl",    passed=True)]
        sec_check  = _check("threat-sections",  passed=True)
        mod._check_gap_ids.return_value             = gap_check
        mod._check_date.return_value                = date_check
        mod._check_controls.return_value            = ctrl_check
        mod._check_threat_sections.return_value     = sec_check

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
            mod = _mock_tm()
        with patch.object(tm_mod, "_load_tool", return_value=mod):
            return self.client.get("/health/threat-model")

    def _data(self, mod=None):
        return json.loads(self._get(mod=mod).data)


class TestThreatModelEndpointStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


class TestThreatModelEndpointShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_checks_key_present(self):
        self.assertIn("checks", self._data())

    def test_checks_is_list(self):
        self.assertIsInstance(self._data()["checks"], list)

    def test_ok_is_bool(self):
        self.assertIsInstance(self._data()["ok"], bool)


class TestThreatModelEndpointChecks(_Base):

    def test_check_has_name(self):
        checks = self._data()["checks"]
        self.assertTrue(len(checks) > 0)
        self.assertIn("name", checks[0])

    def test_check_has_required(self):
        self.assertIn("required", self._data()["checks"][0])

    def test_check_has_passed(self):
        self.assertIn("passed", self._data()["checks"][0])

    def test_check_has_detail(self):
        self.assertIn("detail", self._data()["checks"][0])

    def test_ok_true_when_all_required_pass(self):
        mod = _mock_tm(file_ok=True)
        self.assertTrue(self._data(mod)["ok"])

    def test_ok_false_when_file_missing(self):
        mod = _mock_tm(file_ok=False)
        self.assertFalse(self._data(mod)["ok"])


if __name__ == "__main__":
    unittest.main()
