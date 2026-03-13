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


_SLO_OK_RESULTS = [
    {"slo": "SLO-003", "target": ">=95%", "value": 1.0, "status": "ok",
     "detail": "40/40 SDK calls succeeded (100.0%)"},
    {"slo": "SLO-005", "target": "<=10.0s median", "value": 0.001, "status": "ok",
     "detail": "median=0.001s over 10 records"},
]


def _slo_mod(records=None, results=None, min_records=5):
    m = MagicMock()
    m.METRICS_PATH       = MagicMock()
    m.DEFAULT_MIN_RECORDS = min_records
    m._load_records      = MagicMock(return_value=records if records is not None else [{}]*10)
    m._check_slo003      = MagicMock(return_value=(results or _SLO_OK_RESULTS)[0])
    m._check_slo005      = MagicMock(return_value=(results or _SLO_OK_RESULTS)[1])
    return m


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

    def _mock_tools(self, sv=None, cd=None, mac=None, sc=None):
        """Patch _load_tool to return controlled mock modules."""
        sv_mod  = MagicMock()
        cd_mod  = MagicMock()
        mac_mod = MagicMock()
        sv_mod.validate      = MagicMock(return_value=sv   or _sv_report())
        cd_mod.detect_drift  = MagicMock(return_value=cd   or _cd_report())
        mac_mod.check_alerts = MagicMock(return_value=mac  or _mac_report())
        sc_mod = sc if sc is not None else _slo_mod()

        def _fake_load(name):
            return {"state_validator":     sv_mod,
                    "config_drift":        cd_mod,
                    "metrics_alert_check": mac_mod,
                    "slo_check":           sc_mod}[name]

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

    def test_checks_has_slo_status(self):
        with self._mock_tools():
            data = json.loads(self._get().data)
        self.assertIn("slo_status", data["checks"])

    def test_slo_status_shape(self):
        with self._mock_tools():
            checks = json.loads(self._get().data)["checks"]
        slo = checks["slo_status"]
        for k in ("ok", "records", "results"):
            self.assertIn(k, slo)


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
            if name == "metrics_alert_check":
                m = MagicMock(); m.check_alerts = MagicMock(return_value=_mac_report()); return m
            return _slo_mod()

        with patch.object(hd_mod, "_load_tool", side_effect=_bad_load):
            data = json.loads(self._get().data)
        self.assertFalse(data["checks"]["state_valid"]["ok"])

    def test_config_drift_exception_ok_false(self):
        def _bad_load(name):
            if name == "config_drift":
                raise RuntimeError("drift tool broken")
            if name == "state_validator":
                m = MagicMock(); m.validate = MagicMock(return_value=_sv_report()); return m
            if name == "metrics_alert_check":
                m = MagicMock(); m.check_alerts = MagicMock(return_value=_mac_report()); return m
            return _slo_mod()

        with patch.object(hd_mod, "_load_tool", side_effect=_bad_load):
            data = json.loads(self._get().data)
        self.assertFalse(data["checks"]["config_drift"]["ok"])

    def test_metrics_exception_ok_false(self):
        def _bad_load(name):
            if name == "metrics_alert_check":
                raise RuntimeError("metrics broken")
            if name == "state_validator":
                m = MagicMock(); m.validate = MagicMock(return_value=_sv_report()); return m
            if name == "config_drift":
                m = MagicMock(); m.detect_drift = MagicMock(return_value=_cd_report()); return m
            return _slo_mod()

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


# ---------------------------------------------------------------------------
# SLO status check (TASK-363, OM-035 to OM-040)
# ---------------------------------------------------------------------------

class TestHealthDetailedSloStatus(_Base):

    def test_slo_ok_true_when_all_ok(self):
        with self._mock_tools():
            checks = json.loads(self._get().data)["checks"]
        self.assertTrue(checks["slo_status"]["ok"])

    def test_slo_ok_false_when_breach(self):
        breach_results = [
            {"slo": "SLO-003", "target": ">=95%", "value": 0.5, "status": "breach",
             "detail": "50% success rate"},
            {"slo": "SLO-005", "target": "<=10.0s median", "value": 0.001, "status": "ok",
             "detail": "fast"},
        ]
        sc = _slo_mod(results=breach_results)
        sc._check_slo003.return_value = breach_results[0]
        sc._check_slo005.return_value = breach_results[1]
        with self._mock_tools(sc=sc):
            checks = json.loads(self._get().data)["checks"]
        self.assertFalse(checks["slo_status"]["ok"])

    def test_slo_results_list_present(self):
        with self._mock_tools():
            checks = json.loads(self._get().data)["checks"]
        self.assertIsInstance(checks["slo_status"]["results"], list)

    def test_slo_results_have_slo_key(self):
        with self._mock_tools():
            slo_results = json.loads(self._get().data)["checks"]["slo_status"]["results"]
        self.assertTrue(len(slo_results) > 0)
        self.assertIn("slo", slo_results[0])

    def test_slo_results_have_target_and_value(self):
        with self._mock_tools():
            slo_results = json.loads(self._get().data)["checks"]["slo_status"]["results"]
        for r in slo_results:
            self.assertIn("target", r)
            self.assertIn("value", r)

    def test_slo_ok_true_when_insufficient_records(self):
        sc = _slo_mod(records=[], min_records=5)
        with self._mock_tools(sc=sc):
            checks = json.loads(self._get().data)["checks"]
        # Insufficient records → slo_ok=True (no breach possible)
        self.assertTrue(checks["slo_status"]["ok"])

    def test_slo_records_count_returned(self):
        sc = _slo_mod(records=[{}] * 7)
        with self._mock_tools(sc=sc):
            checks = json.loads(self._get().data)["checks"]
        self.assertEqual(checks["slo_status"]["records"], 7)

    def test_slo_breach_makes_overall_ok_false(self):
        breach_results = [
            {"slo": "SLO-003", "target": ">=95%", "value": 0.5, "status": "breach",
             "detail": "50%"},
            {"slo": "SLO-005", "target": "<=10.0s median", "value": 0.001, "status": "ok",
             "detail": "fast"},
        ]
        sc = _slo_mod(results=breach_results)
        sc._check_slo003.return_value = breach_results[0]
        sc._check_slo005.return_value = breach_results[1]
        with self._mock_tools(sc=sc):
            data = json.loads(self._get().data)
        self.assertFalse(data["ok"])

    def test_slo_exception_ok_false(self):
        def _bad_load(name):
            if name == "slo_check":
                raise RuntimeError("slo broken")
            if name == "state_validator":
                m = MagicMock(); m.validate = MagicMock(return_value=_sv_report()); return m
            if name == "config_drift":
                m = MagicMock(); m.detect_drift = MagicMock(return_value=_cd_report()); return m
            m = MagicMock(); m.check_alerts = MagicMock(return_value=_mac_report()); return m

        with patch.object(hd_mod, "_load_tool", side_effect=_bad_load):
            data = json.loads(self._get().data)
        self.assertFalse(data["checks"]["slo_status"]["ok"])


# ---------------------------------------------------------------------------
# Dashboard JS SLO panel (TASK-363)
# ---------------------------------------------------------------------------

class TestSloStatusPanelJs(unittest.TestCase):

    def _panels_js(self):
        return (Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_health.js"
                ).read_text(encoding="utf-8")

    def test_slo_status_key_referenced(self):
        self.assertIn("slo_status", self._panels_js())

    def test_slo_results_rendered(self):
        self.assertIn("sloResults", self._panels_js())

    def test_slo_row_label(self):
        self.assertIn("SLO Status", self._panels_js())

    def test_slo_target_shown(self):
        self.assertIn("target", self._panels_js())

    def test_slo_value_shown(self):
        # value field displayed per SLO result row
        js = self._panels_js()
        # check the sub-row rendering includes value
        self.assertIn("r.value", js)


# ---------------------------------------------------------------------------
# repo_health check (AAWO integration)
# ---------------------------------------------------------------------------

class TestHealthDetailedRepoHealth(_Base):

    _SNAP = {
        "signals":      {"has_tests": True, "has_ci": False},
        "complexity":   {"value": "medium", "file_count": 50},
        "risk_factors": ["no_ci"],
        "captured_at":  "2026-03-10T00:00:00Z",
    }

    def test_repo_health_key_present(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", return_value=None):
            data = json.loads(self._get().data)
        self.assertIn("repo_health", data["checks"])

    def test_repo_health_available_false_when_none(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", return_value=None):
            checks = json.loads(self._get().data)["checks"]
        self.assertFalse(checks["repo_health"]["available"])

    def test_repo_health_available_true_when_snapshot_returned(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", return_value=self._SNAP):
            checks = json.loads(self._get().data)["checks"]
        self.assertTrue(checks["repo_health"]["available"])

    def test_repo_health_signals_propagated(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", return_value=self._SNAP):
            checks = json.loads(self._get().data)["checks"]
        self.assertTrue(checks["repo_health"]["signals"]["has_tests"])
        self.assertFalse(checks["repo_health"]["signals"]["has_ci"])

    def test_repo_health_complexity_propagated(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", return_value=self._SNAP):
            checks = json.loads(self._get().data)["checks"]
        self.assertEqual(checks["repo_health"]["complexity"], "medium")
        self.assertEqual(checks["repo_health"]["file_count"], 50)

    def test_repo_health_risk_factors_propagated(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", return_value=self._SNAP):
            checks = json.loads(self._get().data)["checks"]
        self.assertIn("no_ci", checks["repo_health"]["risk_factors"])

    def test_repo_health_ok_true_even_when_unavailable(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", return_value=None):
            checks = json.loads(self._get().data)["checks"]
        self.assertTrue(checks["repo_health"]["ok"])

    def test_repo_health_exception_does_not_affect_overall_ok(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", side_effect=RuntimeError("aawo down")):
            data = json.loads(self._get().data)
        self.assertTrue(data["ok"])
        self.assertTrue(data["checks"]["repo_health"]["ok"])

    def test_repo_health_error_key_set_on_exception(self):
        with self._mock_tools(), \
             patch("utils.aawo_bridge.get_snapshot", side_effect=RuntimeError("aawo down")):
            checks = json.loads(self._get().data)["checks"]
        self.assertIn("error", checks["repo_health"])


# ---------------------------------------------------------------------------
# _load_tool fresh-load path (lines 38-44 — importlib.util.spec_from_file_location)
# ---------------------------------------------------------------------------

class TestLoadToolFreshImport(unittest.TestCase):
    """Cover the importlib.util path when module is NOT in sys.modules."""

    def test_load_tool_fresh_import(self):
        mod_name = "_test_fresh_load_dummy"
        # Ensure not cached
        sys.modules.pop(mod_name, None)
        # Create a minimal .py file
        import tempfile, importlib.util
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("VALUE = 42\n")
            tmp_path = f.name
        try:
            from pathlib import Path as P
            # Patch _TOOLS_DIR so _load_tool finds our file
            tools_dir = P(tmp_path).parent
            file_name = P(tmp_path).stem
            with patch.object(hd_mod, "_TOOLS_DIR", new=tools_dir):
                result = hd_mod._load_tool(file_name)
            self.assertEqual(result.VALUE, 42)
            self.assertIn(file_name, sys.modules)
        finally:
            import os
            os.unlink(tmp_path)
            sys.modules.pop(file_name, None)

    def test_load_tool_cached_returns_same(self):
        mod_name = "_test_cached_mod"
        fake_mod = MagicMock()
        sys.modules[mod_name] = fake_mod
        try:
            result = hd_mod._load_tool(mod_name)
            self.assertIs(result, fake_mod)
        finally:
            sys.modules.pop(mod_name, None)


if __name__ == "__main__":
    unittest.main()
