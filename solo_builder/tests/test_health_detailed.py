"""Tests for api/blueprints/health_detailed.py (TASK-357, OM-001 to OM-005)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
import api.blueprints.health_detailed as hd_mod


# ---------------------------------------------------------------------------
# Report mock factories
# ---------------------------------------------------------------------------

def _sv_report(is_valid=True, errors=None, warnings=None):
    r = MagicMock()
    r.is_valid = is_valid
    r.errors   = errors   or []
    r.warnings = warnings or []
    return r


def _cd_report(has_drift=False, missing=None, overridden=None, unknown=None):
    r = MagicMock()
    r.has_drift      = has_drift
    r.missing_keys   = missing    or []
    r.overridden_keys = overridden or []
    r.unknown_keys   = unknown    or []
    return r


def _mac_report(has_alerts=False, alerts=None):
    r = MagicMock()
    r.has_alerts = has_alerts
    r.alerts     = alerts or []
    return r


# ---------------------------------------------------------------------------
# Base test class — Flask test client with patched paths
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
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _get(self):
        return self.client.get("/health/detailed")

    def _mock_tools(self, sv=None, cd=None, mac=None):
        """Patch _load_tool to return controlled mock modules."""
        sv_mod  = MagicMock()
        cd_mod  = MagicMock()
        mac_mod = MagicMock()
        sv_mod.validate      = MagicMock(return_value=sv   or _sv_report())
        cd_mod.detect_drift  = MagicMock(return_value=cd   or _cd_report())
        mac_mod.check_alerts = MagicMock(return_value=mac  or _mac_report())

        def _fake_load(name):
            return {"state_validator": sv_mod,
                    "config_drift":    cd_mod,
                    "metrics_alert_check": mac_mod}[name]

        return patch.object(hd_mod, "_load_tool", side_effect=_fake_load)


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

class TestHealthDetailedShape(_Base):

    def test_status_200(self):
        with self._mock_tools():
            resp = self._get()
        self.assertEqual(resp.status_code, 200)

    def test_top_level_ok_key(self):
        with self._mock_tools():
            data = json.loads(self._get().data)
        self.assertIn("ok", data)

    def test_checks_key_present(self):
        with self._mock_tools():
            data = json.loads(self._get().data)
        self.assertIn("checks", data)

    def test_checks_has_state_valid(self):
        with self._mock_tools():
            data = json.loads(self._get().data)
        self.assertIn("state_valid", data["checks"])

    def test_checks_has_config_drift(self):
        with self._mock_tools():
            data = json.loads(self._get().data)
        self.assertIn("config_drift", data["checks"])

    def test_checks_has_metrics_alerts(self):
        with self._mock_tools():
            data = json.loads(self._get().data)
        self.assertIn("metrics_alerts", data["checks"])

    def test_state_valid_shape(self):
        with self._mock_tools():
            checks = json.loads(self._get().data)["checks"]
        sv = checks["state_valid"]
        for k in ("ok", "errors", "warnings"):
            self.assertIn(k, sv)

    def test_config_drift_shape(self):
        with self._mock_tools():
            checks = json.loads(self._get().data)["checks"]
        cd = checks["config_drift"]
        for k in ("ok", "has_drift", "missing_keys", "overridden_count", "unknown_keys"):
            self.assertIn(k, cd)

    def test_metrics_alerts_shape(self):
        with self._mock_tools():
            checks = json.loads(self._get().data)["checks"]
        ma = checks["metrics_alerts"]
        for k in ("ok", "has_alerts", "alert_count", "alerts"):
            self.assertIn(k, ma)


# ---------------------------------------------------------------------------
# Overall ok flag
# ---------------------------------------------------------------------------

class TestHealthDetailedOk(_Base):

    def test_all_pass_overall_ok_true(self):
        with self._mock_tools():
            data = json.loads(self._get().data)
        self.assertTrue(data["ok"])

    def test_state_invalid_overall_ok_false(self):
        sv = _sv_report(is_valid=False, errors=["schema error"])
        with self._mock_tools(sv=sv):
            data = json.loads(self._get().data)
        self.assertFalse(data["ok"])

    def test_drift_present_overall_ok_false(self):
        cd = _cd_report(has_drift=True, unknown=["EXTRA_KEY"])
        with self._mock_tools(cd=cd):
            data = json.loads(self._get().data)
        self.assertFalse(data["ok"])

    def test_alerts_present_overall_ok_false(self):
        mac = _mac_report(has_alerts=True, alerts=[{"name": "failure_rate"}])
        with self._mock_tools(mac=mac):
            data = json.loads(self._get().data)
        self.assertFalse(data["ok"])

    def test_all_fail_overall_ok_false(self):
        sv  = _sv_report(is_valid=False, errors=["bad"])
        cd  = _cd_report(has_drift=True)
        mac = _mac_report(has_alerts=True)
        with self._mock_tools(sv=sv, cd=cd, mac=mac):
            data = json.loads(self._get().data)
        self.assertFalse(data["ok"])


# ---------------------------------------------------------------------------
# Per-check details
# ---------------------------------------------------------------------------

class TestHealthDetailedStateValid(_Base):

    def test_errors_propagated(self):
        sv = _sv_report(is_valid=False, errors=["Missing 'step' key"])
        with self._mock_tools(sv=sv):
            checks = json.loads(self._get().data)["checks"]
        self.assertIn("Missing 'step' key", checks["state_valid"]["errors"])

    def test_warnings_propagated(self):
        sv = _sv_report(is_valid=True, warnings=["Cycle hint"])
        with self._mock_tools(sv=sv):
            checks = json.loads(self._get().data)["checks"]
        self.assertIn("Cycle hint", checks["state_valid"]["warnings"])

    def test_ok_true_when_valid(self):
        with self._mock_tools(sv=_sv_report(is_valid=True)):
            checks = json.loads(self._get().data)["checks"]
        self.assertTrue(checks["state_valid"]["ok"])

    def test_ok_false_when_invalid(self):
        with self._mock_tools(sv=_sv_report(is_valid=False)):
            checks = json.loads(self._get().data)["checks"]
        self.assertFalse(checks["state_valid"]["ok"])


class TestHealthDetailedConfigDrift(_Base):

    def test_no_drift_ok_true(self):
        with self._mock_tools(cd=_cd_report(has_drift=False)):
            checks = json.loads(self._get().data)["checks"]
        self.assertTrue(checks["config_drift"]["ok"])

    def test_drift_ok_false(self):
        with self._mock_tools(cd=_cd_report(has_drift=True)):
            checks = json.loads(self._get().data)["checks"]
        self.assertFalse(checks["config_drift"]["ok"])

    def test_overridden_count_computed(self):
        cd = _cd_report(overridden=[{"key": "A"}, {"key": "B"}])
        with self._mock_tools(cd=cd):
            checks = json.loads(self._get().data)["checks"]
        self.assertEqual(checks["config_drift"]["overridden_count"], 2)

    def test_unknown_keys_propagated(self):
        cd = _cd_report(has_drift=True, unknown=["FOO"])
        with self._mock_tools(cd=cd):
            checks = json.loads(self._get().data)["checks"]
        self.assertIn("FOO", checks["config_drift"]["unknown_keys"])


class TestHealthDetailedMetricsAlerts(_Base):

    def test_no_alerts_ok_true(self):
        with self._mock_tools(mac=_mac_report(has_alerts=False)):
            checks = json.loads(self._get().data)["checks"]
        self.assertTrue(checks["metrics_alerts"]["ok"])

    def test_alerts_ok_false(self):
        with self._mock_tools(mac=_mac_report(has_alerts=True)):
            checks = json.loads(self._get().data)["checks"]
        self.assertFalse(checks["metrics_alerts"]["ok"])

    def test_alert_count(self):
        mac = _mac_report(has_alerts=True, alerts=[{"name": "a"}, {"name": "b"}])
        with self._mock_tools(mac=mac):
            checks = json.loads(self._get().data)["checks"]
        self.assertEqual(checks["metrics_alerts"]["alert_count"], 2)

    def test_alerts_list_propagated(self):
        mac = _mac_report(has_alerts=True, alerts=[{"name": "failure_rate"}])
        with self._mock_tools(mac=mac):
            checks = json.loads(self._get().data)["checks"]
        self.assertEqual(checks["metrics_alerts"]["alerts"][0]["name"], "failure_rate")


# ---------------------------------------------------------------------------
# Exception resilience
# ---------------------------------------------------------------------------

class TestHealthDetailedExceptions(_Base):

    def test_state_validator_exception_ok_false(self):
        def _bad_load(name):
            if name == "state_validator":
                raise RuntimeError("tool unavailable")
            if name == "config_drift":
                m = MagicMock(); m.detect_drift = MagicMock(return_value=_cd_report()); return m
            m = MagicMock(); m.check_alerts = MagicMock(return_value=_mac_report()); return m

        with patch.object(hd_mod, "_load_tool", side_effect=_bad_load):
            data = json.loads(self._get().data)
        self.assertFalse(data["checks"]["state_valid"]["ok"])

    def test_config_drift_exception_ok_false(self):
        def _bad_load(name):
            if name == "config_drift":
                raise RuntimeError("drift tool broken")
            if name == "state_validator":
                m = MagicMock(); m.validate = MagicMock(return_value=_sv_report()); return m
            m = MagicMock(); m.check_alerts = MagicMock(return_value=_mac_report()); return m

        with patch.object(hd_mod, "_load_tool", side_effect=_bad_load):
            data = json.loads(self._get().data)
        self.assertFalse(data["checks"]["config_drift"]["ok"])

    def test_metrics_exception_ok_false(self):
        def _bad_load(name):
            if name == "metrics_alert_check":
                raise RuntimeError("metrics broken")
            if name == "state_validator":
                m = MagicMock(); m.validate = MagicMock(return_value=_sv_report()); return m
            m = MagicMock(); m.detect_drift = MagicMock(return_value=_cd_report()); return m

        with patch.object(hd_mod, "_load_tool", side_effect=_bad_load):
            data = json.loads(self._get().data)
        self.assertFalse(data["checks"]["metrics_alerts"]["ok"])

    def test_exception_still_returns_200(self):
        with patch.object(hd_mod, "_load_tool", side_effect=RuntimeError("all bad")):
            resp = self._get()
        self.assertEqual(resp.status_code, 200)

    def test_overall_ok_false_on_any_exception(self):
        with patch.object(hd_mod, "_load_tool", side_effect=RuntimeError("all bad")):
            data = json.loads(self._get().data)
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
