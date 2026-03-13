"""Tests for metrics blueprint — GET /agents, /forecast, /metrics, /metrics/summary, /metrics/export."""
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
from api.constants import METRICS_JSONL_PATH


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")
        self._metrics_path = Path(self._tmp) / "metrics.jsonl"

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "CACHE_DIR", new=Path(self._tmp) / "cache"),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def _write_state(self, state):
        self._state_path.write_text(json.dumps(state), encoding="utf-8")

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestAgentsEndpoint(_Base):
    def test_agents_empty_dag(self):
        self._write_state({"dag": {}, "step": 0})
        r = self.client.get("/agents")
        d = r.get_json()
        self.assertEqual(d["step"], 0)
        self.assertEqual(d["forecast"]["total"], 0)

    def test_agents_with_meta_history(self):
        self._write_state({"step": 5, "healed_total": 2, "dag": {
            "T1": {"branches": {"m": {"subtasks": {
                "S1": {"status": "Verified"},
                "S2": {"status": "Running", "last_update": 0},
            }}}},
        }, "meta_history": [
            {"verified": 1, "healed": 0},
            {"verified": 2, "healed": 1},
        ]})
        r = self.client.get("/agents")
        d = r.get_json()
        self.assertEqual(d["healer"]["healed_total"], 2)
        self.assertEqual(d["healer"]["currently_stalled"], 1)
        self.assertGreater(d["meta"]["verify_rate"], 0)
        self.assertIsNotNone(d["forecast"]["eta_steps"])

    def test_agents_custom_settings(self):
        self._settings_path.write_text(json.dumps({
            "STALL_THRESHOLD": 100,
            "EXECUTOR_MAX_PER_STEP": 10,
        }), encoding="utf-8")
        self._write_state({"step": 5, "dag": {
            "T1": {"branches": {"m": {"subtasks": {
                "S1": {"status": "Running", "last_update": 3},
            }}}},
        }})
        r = self.client.get("/agents")
        d = r.get_json()
        self.assertEqual(d["executor"]["max_per_step"], 10)
        self.assertEqual(d["healer"]["currently_stalled"], 0)


class TestForecastEndpoint(_Base):
    def test_forecast_empty(self):
        self._write_state({"dag": {}, "step": 0})
        r = self.client.get("/forecast")
        d = r.get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["pct"], 0)
        self.assertIsNone(d["eta_steps"])

    def test_forecast_with_data(self):
        self._write_state({"step": 10, "dag": {
            "T1": {"branches": {"m": {"subtasks": {
                "S1": {"status": "Verified"},
                "S2": {"status": "Running"},
                "S3": {"status": "Pending"},
                "S4": {"status": "Review"},
            }}}},
        }, "meta_history": [{"verified": 1, "healed": 0}] * 5})
        r = self.client.get("/forecast")
        d = r.get_json()
        self.assertEqual(d["total"], 4)
        self.assertEqual(d["verified"], 1)
        self.assertEqual(d["running"], 1)
        self.assertEqual(d["pending"], 1)
        self.assertEqual(d["review"], 1)
        self.assertIsNotNone(d["eta_steps"])


class TestMetricsEndpoint(_Base):
    def test_metrics_with_history(self):
        self._write_state({"step": 3, "healed_total": 1, "dag": {
            "T1": {"branches": {"m": {"subtasks": {
                "S1": {"status": "Verified"},
                "S2": {"status": "Pending"},
            }}}},
        }, "meta_history": [
            {"verified": 1, "healed": 0},
            {"verified": 0, "healed": 1},
        ]})
        r = self.client.get("/metrics")
        d = r.get_json()
        self.assertEqual(d["step"], 3)
        self.assertEqual(d["total"], 2)
        self.assertEqual(d["verified"], 1)
        self.assertEqual(d["pending"], 1)
        self.assertEqual(d["total_healed"], 1)
        self.assertEqual(len(d["history"]), 2)
        self.assertEqual(d["history"][0]["cumulative"], 1)
        self.assertEqual(d["summary"]["peak_verified_per_step"], 1)
        self.assertEqual(d["summary"]["steps_with_heals"], 1)

    def test_metrics_empty(self):
        self._write_state({"dag": {}, "step": 0})
        r = self.client.get("/metrics")
        d = r.get_json()
        self.assertEqual(d["total"], 0)


class TestMetricsSummary(_Base):
    def test_summary_no_file(self):
        from api.blueprints import metrics as m_mod
        with patch.object(m_mod, "METRICS_JSONL_PATH", str(Path(self._tmp) / "missing.jsonl")):
            r = self.client.get("/metrics/summary")
        d = r.get_json()
        self.assertEqual(d["record_count"], 0)
        self.assertIsNone(d["avg_elapsed_s"])

    def test_summary_with_records(self):
        from api.blueprints import metrics as m_mod
        lines = [
            json.dumps({"elapsed_s": 0.5, "sdk_dispatched": 2, "sdk_succeeded": 2, "started": 1, "verified": 1}),
            json.dumps({"elapsed_s": 3.0, "sdk_dispatched": 3, "sdk_succeeded": 2, "started": 2, "verified": 0}),
            json.dumps({"elapsed_s": 8.0, "sdk_dispatched": 1, "sdk_succeeded": 1, "started": 1, "verified": 1}),
            json.dumps({"elapsed_s": 15.0, "sdk_dispatched": 0, "sdk_succeeded": 0, "started": 0, "verified": 0}),
            json.dumps({"elapsed_s": 45.0, "sdk_dispatched": 5, "sdk_succeeded": 4, "started": 3, "verified": 2}),
        ]
        self._metrics_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with patch.object(m_mod, "METRICS_JSONL_PATH", str(self._metrics_path)):
            r = self.client.get("/metrics/summary")
        d = r.get_json()
        self.assertEqual(d["record_count"], 5)
        self.assertIsNotNone(d["avg_elapsed_s"])
        self.assertIsNotNone(d["p50_elapsed_s"])
        self.assertIsNotNone(d["p99_elapsed_s"])
        self.assertIsNotNone(d["latency_buckets"])
        self.assertEqual(d["latency_buckets"]["lt_1s"], 1)
        self.assertEqual(d["latency_buckets"]["1s_5s"], 1)
        self.assertEqual(d["latency_buckets"]["5s_10s"], 1)
        self.assertEqual(d["latency_buckets"]["10s_30s"], 1)
        self.assertEqual(d["latency_buckets"]["gt_30s"], 1)
        self.assertEqual(d["total_started"], 7)
        self.assertEqual(d["total_verified"], 4)
        self.assertAlmostEqual(d["sdk_success_rate"], 9 / 11, places=3)


class TestMetricsExport(_Base):
    def test_export_csv_default(self):
        self._write_state({"step": 2, "meta_history": [
            {"verified": 3, "healed": 0},
            {"verified": 1, "healed": 1},
        ]})
        r = self.client.get("/metrics/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)
        lines = r.data.decode().strip().splitlines()
        self.assertEqual(lines[0].strip(), "step_index,verified,healed,cumulative")
        self.assertEqual(len(lines), 3)

    def test_export_json_format(self):
        self._write_state({"step": 1, "meta_history": [{"verified": 2, "healed": 0}]})
        r = self.client.get("/metrics/export?format=json")
        d = r.get_json()
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["verified"], 2)

    def test_export_since_filter(self):
        self._write_state({"step": 3, "meta_history": [
            {"verified": 1, "healed": 0},
            {"verified": 2, "healed": 0},
            {"verified": 3, "healed": 0},
        ]})
        r = self.client.get("/metrics/export?format=json&since=1")
        d = r.get_json()
        self.assertEqual(len(d), 2)
        self.assertEqual(d[0]["step_index"], 2)

    def test_export_limit(self):
        self._write_state({"step": 3, "meta_history": [
            {"verified": 1, "healed": 0},
            {"verified": 2, "healed": 0},
            {"verified": 3, "healed": 0},
        ]})
        r = self.client.get("/metrics/export?format=json&limit=1")
        d = r.get_json()
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["step_index"], 3)

    def test_export_empty_history(self):
        self._write_state({"step": 0})
        r = self.client.get("/metrics/export?format=json")
        d = r.get_json()
        self.assertEqual(len(d), 0)


# ---------------------------------------------------------------------------
# Coverage: agents settings exception (lines 35-36)
# ---------------------------------------------------------------------------

class TestAgentsSettingsException(_Base):
    def test_agents_corrupt_settings_uses_defaults(self):
        self._settings_path.write_text("NOT JSON", encoding="utf-8")
        self._write_state({"step": 1, "dag": {
            "T1": {"branches": {"m": {"subtasks": {"S1": {"status": "Running", "last_update": 0}}}}},
        }})
        r = self.client.get("/agents")
        d = r.get_json()
        self.assertEqual(d["executor"]["max_per_step"], 6)  # default


# ---------------------------------------------------------------------------
# Coverage: metrics settings exception (lines 130-131)
# ---------------------------------------------------------------------------

class TestMetricsSettingsException(_Base):
    def test_metrics_corrupt_settings_uses_defaults(self):
        self._settings_path.write_text("NOT JSON", encoding="utf-8")
        self._write_state({"step": 1, "dag": {
            "T1": {"branches": {"m": {"subtasks": {"S1": {"status": "Running", "last_update": 0}}}}},
        }})
        r = self.client.get("/metrics")
        d = r.get_json()
        self.assertEqual(d["step"], 1)


# ---------------------------------------------------------------------------
# Coverage: metrics Review status (line 145)
# ---------------------------------------------------------------------------

class TestMetricsReviewStatus(_Base):
    def test_metrics_counts_review_subtasks(self):
        self._write_state({"step": 2, "dag": {
            "T1": {"branches": {"m": {"subtasks": {
                "S1": {"status": "Review"},
                "S2": {"status": "Verified"},
            }}}},
        }})
        r = self.client.get("/metrics")
        d = r.get_json()
        self.assertEqual(d["review"], 1)
        self.assertEqual(d["verified"], 1)


# ---------------------------------------------------------------------------
# Coverage: metrics elapsed_s stat exception (lines 158-160)
# ---------------------------------------------------------------------------

class TestMetricsElapsedStatException(_Base):
    def test_metrics_no_state_file_elapsed_none(self):
        self._write_state({"step": 0, "dag": {}})
        self._state_path.unlink()
        r = self.client.get("/metrics")
        d = r.get_json()
        self.assertIsNone(d["elapsed_s"])

    def test_metrics_with_step_has_steps_per_min(self):
        self._write_state({"step": 10, "dag": {
            "T1": {"branches": {"m": {"subtasks": {"S1": {"status": "Verified"}}}}},
        }})
        import time as _t
        # Mock stat to return ctime 60s ago
        real_stat = Path.stat
        def _fake_stat(self_path):
            s = real_stat(self_path)
            if "state" in str(self_path):
                # Return a mock with st_ctime 60s ago
                from unittest.mock import MagicMock
                ms = MagicMock(wraps=s)
                ms.st_ctime = _t.time() - 60
                return ms
            return s
        with patch.object(Path, "stat", _fake_stat):
            r = self.client.get("/metrics")
        d = r.get_json()
        self.assertIsNotNone(d["elapsed_s"])
        self.assertGreater(d["elapsed_s"], 0)
        self.assertIsNotNone(d["steps_per_min"])


if __name__ == "__main__":
    unittest.main()
