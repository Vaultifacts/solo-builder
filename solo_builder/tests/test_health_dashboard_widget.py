"""Tests for HealthDashboardWidget — TASK-358 (OM-006 to OM-010).

Covers:
  1. dashboard.html — Health tab button present, tab content div present
  2. dashboard_panels.js — pollHealthDetailed exported and well-formed
  3. dashboard.js — pollHealthDetailed imported and called in tick()
  4. /health/detailed endpoint still returns correct shape (integration)
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
import api.blueprints.health_detailed as hd_mod

_REPO_ROOT    = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# Dashboard HTML checks
# ---------------------------------------------------------------------------

class TestDashboardHtmlHealthTab(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_health_tab_button_present(self):
        self.assertIn("switchTab('health')", self._html)

    def test_health_tab_content_div_present(self):
        self.assertIn('id="tab-health"', self._html)

    def test_health_detailed_content_div_present(self):
        self.assertIn('id="health-detailed-content"', self._html)

    def test_health_tab_button_has_data_tab(self):
        self.assertIn('data-tab="health"', self._html)

    def test_health_tab_button_text(self):
        self.assertRegex(self._html, r'onclick="switchTab\(\'health\'\)"[^>]*>Health')


# ---------------------------------------------------------------------------
# dashboard_panels.js checks
# ---------------------------------------------------------------------------

class TestPanelsJsHealthDetailed(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollHealthDetailed_exported(self):
        self.assertIn("export async function pollHealthDetailed", self._js)

    def test_calls_health_detailed_endpoint(self):
        self.assertIn("/health/detailed", self._js)

    def test_renders_to_health_detailed_content(self):
        self.assertIn("health-detailed-content", self._js)

    def test_shows_state_valid_label(self):
        # Any text that refers to state validity
        self.assertTrue(
            "state_valid" in self._js or "State Valid" in self._js
        )

    def test_shows_config_drift_label(self):
        self.assertTrue(
            "config_drift" in self._js or "Config Drift" in self._js
        )

    def test_shows_metrics_alerts_label(self):
        self.assertTrue(
            "metrics_alerts" in self._js or "Metrics Alerts" in self._js
        )

    def test_updates_favicon(self):
        self.assertIn("favicon", self._js)

    def test_catch_block_present(self):
        # Should be exception-safe
        self.assertIn("catch", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)


# ---------------------------------------------------------------------------
# dashboard.js checks
# ---------------------------------------------------------------------------

class TestMainJsHealthDetailed(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollHealthDetailed_imported(self):
        self.assertIn("pollHealthDetailed", self._js)

    def test_pollHealthDetailed_called_in_tick(self):
        # Should be in the Promise.all tick call
        self.assertIn("pollHealthDetailed()", self._js)

    def test_import_from_panels(self):
        # Imported alongside other panel pollers
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollHealthDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Flask endpoint integration (light — delegates detail to test_health_detailed.py)
# ---------------------------------------------------------------------------

def _sv_report(is_valid=True):
    r = MagicMock()
    r.is_valid = is_valid
    r.errors = []
    r.warnings = []
    return r


def _cd_report(has_drift=False):
    r = MagicMock()
    r.has_drift = has_drift
    r.missing_keys = []
    r.overridden_keys = []
    r.unknown_keys = []
    return r


def _mac_report(has_alerts=False):
    r = MagicMock()
    r.has_alerts = has_alerts
    r.alerts = []
    return r


def _slo_mod_widget():
    m = MagicMock()
    m.METRICS_PATH        = MagicMock()
    m.DEFAULT_MIN_RECORDS = 5
    m._load_records       = MagicMock(return_value=[{}] * 10)
    m._check_slo003       = MagicMock(return_value={
        "slo": "SLO-003", "target": ">=95%", "value": 1.0, "status": "ok",
        "detail": "40/40 succeeded",
    })
    m._check_slo005       = MagicMock(return_value={
        "slo": "SLO-005", "target": "<=10.0s median", "value": 0.001, "status": "ok",
        "detail": "fast",
    })
    return m


class _ApiBase(unittest.TestCase):
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
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _mock_tools(self, sv=None, cd=None, mac=None):
        sv_mod  = MagicMock()
        cd_mod  = MagicMock()
        mac_mod = MagicMock()
        sv_mod.validate      = MagicMock(return_value=sv  or _sv_report())
        cd_mod.detect_drift  = MagicMock(return_value=cd  or _cd_report())
        mac_mod.check_alerts = MagicMock(return_value=mac or _mac_report())
        sc_mod = _slo_mod_widget()

        def _fake_load(name):
            return {"state_validator":     sv_mod,
                    "config_drift":        cd_mod,
                    "metrics_alert_check": mac_mod,
                    "slo_check":           sc_mod}[name]
        return patch.object(hd_mod, "_load_tool", side_effect=_fake_load)


class TestHealthDetailedEndpointViaWidget(_ApiBase):

    def test_endpoint_accessible(self):
        with self._mock_tools():
            resp = self.client.get("/health/detailed")
        self.assertEqual(resp.status_code, 200)

    def test_ok_true_all_clean(self):
        with self._mock_tools():
            data = json.loads(self.client.get("/health/detailed").data)
        self.assertTrue(data["ok"])

    def test_ok_false_on_drift(self):
        cd = _cd_report(has_drift=True)
        with self._mock_tools(cd=cd):
            data = json.loads(self.client.get("/health/detailed").data)
        self.assertFalse(data["ok"])

    def test_content_type_json(self):
        with self._mock_tools():
            resp = self.client.get("/health/detailed")
        self.assertIn("application/json", resp.content_type)


if __name__ == "__main__":
    unittest.main()
