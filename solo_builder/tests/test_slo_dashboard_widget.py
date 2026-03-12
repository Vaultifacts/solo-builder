"""Tests for SLODashboardWidget — TASK-375 (OM-035 to OM-040).

Covers:
  1. dashboard.html — slo-detailed-content div present in Health tab
  2. dashboard_panels.js — pollSloDetailed exported and well-formed
  3. dashboard.js — pollSloDetailed imported and called in tick()
  4. GET /health/slo endpoint (shape, ok flag, records, results)
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
import api.blueprints.slo as slo_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_health.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestSloDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_slo_div_present(self):
        self.assertIn('id="slo-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        slo_pos    = self._html.index('id="slo-detailed-content"')
        self.assertGreater(slo_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading SLOs", self._html)

    def test_div_after_threat_model_div(self):
        tm_pos  = self._html.index('id="threat-model-detailed-content"')
        slo_pos = self._html.index('id="slo-detailed-content"')
        self.assertGreater(slo_pos, tm_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestSloPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollSloDetailed_exported(self):
        self.assertIn("export async function pollSloDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/slo", self._js)

    def test_content_el_queried(self):
        self.assertIn("slo-detailed-content", self._js)

    def test_ok_flag_used(self):
        self.assertIn("d.ok", self._js)

    def test_records_rendered(self):
        self.assertIn("d.records", self._js)

    def test_slo_field_rendered(self):
        self.assertIn("r.slo", self._js)

    def test_status_field_rendered(self):
        self.assertIn("r.status", self._js)

    def test_value_field_rendered(self):
        self.assertIn("r.value", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("Insufficient metrics data", self._js)

    def test_breach_color_defined(self):
        self.assertIn("breach", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestSloMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollSloDetailed_imported(self):
        self.assertIn("pollSloDetailed", self._js)

    def test_pollSloDetailed_called_in_tick(self):
        self.assertIn("pollSloDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollSloDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Helpers for endpoint tests
# ---------------------------------------------------------------------------

def _slo_result(slo="SLO-003", status="ok", value=0.98, target=">=0.95", detail=""):
    return {"slo": slo, "target": target, "value": value, "status": status, "detail": detail}


def _mock_sc(records=None, results=None, min_records=5):
    mod = MagicMock()
    mod.METRICS_PATH = Path("/fake/metrics.jsonl")
    mod.DEFAULT_MIN_RECORDS = min_records
    if records is None:
        records = [{}] * min_records
    mod._load_records.return_value = records
    if results is None:
        results = [_slo_result("SLO-003"), _slo_result("SLO-005", value=2.1, target="<=10s")]
    mod._check_slo003.return_value = results[0] if results else {}
    mod._check_slo005.return_value = results[1] if len(results) > 1 else {}
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

    def _get(self, sc=None):
        if sc is None:
            sc = _mock_sc()
        with patch.object(slo_mod, "_load_tool", return_value=sc):
            return self.client.get("/health/slo")

    def _data(self, sc=None):
        return json.loads(self._get(sc=sc).data)


class TestSloEndpointStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


class TestSloEndpointShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_records_key_present(self):
        self.assertIn("records", self._data())

    def test_results_key_present(self):
        self.assertIn("results", self._data())

    def test_results_is_list(self):
        self.assertIsInstance(self._data()["results"], list)

    def test_ok_is_bool(self):
        self.assertIsInstance(self._data()["ok"], bool)


class TestSloEndpointBehavior(_Base):

    def test_ok_true_when_all_pass(self):
        sc = _mock_sc(results=[
            _slo_result("SLO-003", status="ok"),
            _slo_result("SLO-005", status="ok"),
        ])
        self.assertTrue(self._data(sc)["ok"])

    def test_ok_false_when_breach(self):
        sc = _mock_sc(results=[
            _slo_result("SLO-003", status="breach"),
            _slo_result("SLO-005", status="ok"),
        ])
        self.assertFalse(self._data(sc)["ok"])

    def test_ok_true_insufficient_data(self):
        sc = _mock_sc(records=[], min_records=5)
        d = self._data(sc)
        self.assertTrue(d["ok"])
        self.assertEqual(d["results"], [])

    def test_records_count_returned(self):
        sc = _mock_sc(records=[{}] * 8)
        self.assertEqual(self._data(sc)["records"], 8)


if __name__ == "__main__":
    unittest.main()
