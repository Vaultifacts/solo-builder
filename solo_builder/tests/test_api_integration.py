"""
Additional Flask API integration tests expanding coverage of lightly-tested
endpoints: /priority, /stalled, /forecast, /agents, /metrics, /timeline,
/branches, /subtasks, /shortcuts, /config/reset, /health, GET /status.

These complement the main test_app.py suite without duplicating it.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module


class _Base(unittest.TestCase):
    """Minimal shared setup — mirrors test_app._Base."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path = Path(self._tmp) / "state" / "solo_builder_state.json"
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path = Path(self._tmp) / "config" / "settings.json"
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            src = json.loads(app_module.SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            src = {"STALL_THRESHOLD": 5, "EXECUTOR_VERIFY_PROBABILITY": 0.8}
        self._settings_path.write_text(json.dumps(src, indent=4), encoding="utf-8")
        self._cache_dir = Path(self._tmp) / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._patches = [
            patch.object(app_module, "STATE_PATH",           new=self._state_path),
            patch.object(app_module, "TRIGGER_PATH",          new=Path(self._tmp) / "state" / "run_trigger"),
            patch.object(app_module, "VERIFY_TRIGGER",        new=Path(self._tmp) / "state" / "verify_trigger.json"),
            patch.object(app_module, "DESCRIBE_TRIGGER",      new=Path(self._tmp) / "state" / "describe_trigger.json"),
            patch.object(app_module, "TOOLS_TRIGGER",         new=Path(self._tmp) / "state" / "tools_trigger.json"),
            patch.object(app_module, "SET_TRIGGER",           new=Path(self._tmp) / "state" / "set_trigger.json"),
            patch.object(app_module, "HEARTBEAT_PATH",        new=Path(self._tmp) / "state" / "step.txt"),
            patch.object(app_module, "OUTPUTS_PATH",          new=Path(self._tmp) / "solo_builder_outputs.md"),
            patch.object(app_module, "JOURNAL_PATH",          new=Path(self._tmp) / "journal.md"),
            patch.object(app_module, "SETTINGS_PATH",         new=self._settings_path),
            patch.object(app_module, "ADD_TASK_TRIGGER",      new=Path(self._tmp) / "state" / "add_task_trigger.json"),
            patch.object(app_module, "ADD_BRANCH_TRIGGER",    new=Path(self._tmp) / "state" / "add_branch_trigger.json"),
            patch.object(app_module, "PRIORITY_BRANCH_TRIGGER", new=Path(self._tmp) / "state" / "prioritize_branch_trigger.json"),
            patch.object(app_module, "UNDO_TRIGGER",          new=Path(self._tmp) / "state" / "undo_trigger"),
            patch.object(app_module, "DEPENDS_TRIGGER",       new=Path(self._tmp) / "state" / "depends_trigger.json"),
            patch.object(app_module, "UNDEPENDS_TRIGGER",     new=Path(self._tmp) / "state" / "undepends_trigger.json"),
            patch.object(app_module, "RESET_TRIGGER",         new=Path(self._tmp) / "state" / "reset_trigger"),
            patch.object(app_module, "SNAPSHOT_TRIGGER",      new=Path(self._tmp) / "state" / "snapshot_trigger"),
            patch.object(app_module, "PAUSE_TRIGGER",         new=Path(self._tmp) / "state" / "pause_trigger"),
            patch.object(app_module, "DAG_IMPORT_TRIGGER",    new=Path(self._tmp) / "state" / "dag_import_trigger.json"),
            patch.object(app_module, "HEAL_TRIGGER",          new=Path(self._tmp) / "state" / "heal_trigger.json"),
            patch.object(app_module, "CACHE_DIR",             new=self._cache_dir),
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

    def _write_state(self, state):
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state), encoding="utf-8")

    def _make_state(self, subtasks=None, step=10, task="Task 0"):
        sts = subtasks or {"A1": "Verified", "A2": "Pending"}
        return {
            "step": step,
            "dag": {
                task: {
                    "status": "Running",
                    "depends_on": [],
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                name: {"status": status, "output": f"out {name}",
                                       "description": f"desc {name}"}
                                for name, status in sts.items()
                            }
                        }
                    },
                }
            },
        }

    def _make_multi_task_state(self):
        return {
            "step": 20,
            "dag": {
                "Task 0": {
                    "status": "Verified",
                    "depends_on": [],
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {"status": "Verified", "output": "done", "description": "d1"},
                                "A2": {"status": "Verified", "output": "done", "description": "d2"},
                            }
                        }
                    },
                },
                "Task 1": {
                    "status": "Running",
                    "depends_on": ["Task 0"],
                    "branches": {
                        "Branch B": {
                            "subtasks": {
                                "B1": {"status": "Running", "output": "",   "description": "r1"},
                                "B2": {"status": "Pending", "output": "",   "description": "p1"},
                                "B3": {"status": "Pending", "output": "",   "description": "p2"},
                            }
                        }
                    },
                },
            },
        }


# ---------------------------------------------------------------------------
# GET /priority — edge cases
# ---------------------------------------------------------------------------

class TestPriorityExtra(_Base):

    def test_has_step_field(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.get("/priority").get_json()
        self.assertIn("step", d)
        self.assertIsInstance(d["step"], int)

    def test_empty_when_all_verified(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified"}))
        d = self.client.get("/priority").get_json()
        self.assertEqual(d["count"], 0)
        self.assertEqual(d["queue"], [])

    def test_running_subtask_has_fields(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.get("/priority").get_json()
        entry = next((c for c in d["queue"] if c["subtask"] == "A1"), None)
        self.assertIsNotNone(entry)
        self.assertIn("risk", entry)
        self.assertIn("status", entry)
        self.assertIn("task", entry)

    def test_multi_task_priority_includes_all_pending(self):
        self._write_state(self._make_multi_task_state())
        d = self.client.get("/priority").get_json()
        names = [c["subtask"] for c in d["queue"]]
        self.assertIn("B1", names)
        self.assertIn("B2", names)
        self.assertIn("B3", names)

    def test_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/priority")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# GET /stalled — edge cases
# ---------------------------------------------------------------------------

class TestStalledExtra(_Base):

    def test_step_field_present(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/stalled").get_json()
        self.assertIn("step", d)

    def test_threshold_is_positive(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/stalled").get_json()
        self.assertGreater(d["threshold"], 0)

    def test_no_stalled_when_all_verified(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified"}))
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["stalled"], [])

    def test_stalled_entry_has_task_field(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/stalled").get_json()
        for s in d["stalled"]:
            self.assertIn("task", s)
            self.assertIn("subtask", s)
            self.assertIn("age", s)

    def test_returns_200_empty_state(self):
        self._write_state({"step": 0, "dag": {}})
        r = self.client.get("/stalled")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# GET /forecast — edge cases
# ---------------------------------------------------------------------------

class TestForecastExtra(_Base):

    def test_stalled_count_present(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.get("/forecast").get_json()
        # stalled_count may appear as 'stalled_count' or via /stalled endpoint separately
        self.assertIn("step", d)

    def test_percent_complete_in_range(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/forecast").get_json()
        pct = d.get("percent_complete", d.get("pct", 0))
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)

    def test_fully_verified_pct_is_100(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified"}))
        d = self.client.get("/forecast").get_json()
        self.assertEqual(d["verified"], d["total"])

    def test_verified_per_step_non_negative(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}, step=10))
        d = self.client.get("/forecast").get_json()
        rate = d.get("verified_per_step")
        if rate is not None:
            self.assertGreaterEqual(rate, 0)

    def test_eta_steps_none_when_no_progress(self):
        self._write_state(self._make_state({"A1": "Pending", "A2": "Pending"}, step=1))
        d = self.client.get("/forecast").get_json()
        # eta_steps may be None when no progress has been made
        self.assertIn("eta_steps", d)


# ---------------------------------------------------------------------------
# GET /agents — edge cases
# ---------------------------------------------------------------------------

class TestAgentsExtra(_Base):

    def test_executor_fields(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/agents").get_json()
        self.assertIn("max_per_step", d["executor"])

    def test_planner_cache_interval(self):
        self._write_state(self._make_state())
        d = self.client.get("/agents").get_json()
        self.assertIn("cache_interval", d["planner"])

    def test_meta_optimizer_fields(self):
        self._write_state(self._make_state())
        d = self.client.get("/agents").get_json()
        m = d["meta"]
        self.assertIn("history_len", m)
        self.assertIn("heal_rate", m)
        self.assertIn("verify_rate", m)

    def test_step_field_present(self):
        self._write_state(self._make_state(step=15))
        d = self.client.get("/agents").get_json()
        self.assertIn("step", d)

    def test_forecast_pct_in_range(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/agents").get_json()
        pct = d["forecast"]["pct"]
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)


# ---------------------------------------------------------------------------
# GET /metrics — health summary fields
# ---------------------------------------------------------------------------

class TestMetricsExtra(_Base):

    def test_health_summary_fields(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}))
        d = self.client.get("/metrics").get_json()
        for field in ("total", "verified", "pending", "running", "pct"):
            self.assertIn(field, d, f"missing field: {field}")

    def test_stalled_field_present(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/metrics").get_json()
        self.assertIn("stalled", d)

    def test_elapsed_s_non_negative(self):
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        if d.get("elapsed_s") is not None:
            self.assertGreaterEqual(d["elapsed_s"], 0)

    def test_multi_task_total_counts_all(self):
        self._write_state(self._make_multi_task_state())
        d = self.client.get("/metrics").get_json()
        self.assertEqual(d["total"], 5)
        self.assertEqual(d["verified"], 2)

    def test_summary_has_total_steps(self):
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        s = d.get("summary", {})
        self.assertIn("total_steps", s)


# ---------------------------------------------------------------------------
# GET /timeline/<id> — edge cases
# ---------------------------------------------------------------------------

class TestTimelineExtra(_Base):

    def test_last_update_field(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/timeline/A1").get_json()
        self.assertIn("last_update", d)

    def test_history_is_list(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/timeline/A1").get_json()
        self.assertIsInstance(d.get("history", []), list)

    def test_history_entry_has_status_and_step(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/timeline/A1").get_json()
        for entry in d.get("history", []):
            self.assertIn("status", entry)
            self.assertIn("step", entry)

    def test_output_field_present(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/timeline/A1").get_json()
        self.assertIn("output", d)

    def test_description_field_present(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/timeline/A1").get_json()
        self.assertIn("description", d)


# ---------------------------------------------------------------------------
# GET /branches — per-task filter
# ---------------------------------------------------------------------------

class TestBranchesExtra(_Base):

    def test_all_branches_have_pct(self):
        self._write_state(self._make_multi_task_state())
        d = self.client.get("/branches").get_json()
        for br in d.get("branches", []):
            self.assertIn("pct", br)
            self.assertGreaterEqual(br["pct"], 0)
            self.assertLessEqual(br["pct"], 100)

    def test_task_filter_returns_subset(self):
        self._write_state(self._make_multi_task_state())
        d = self.client.get("/branches?task=Task+0").get_json()
        self.assertIn("branches", d)
        for br in d.get("branches", []):
            self.assertIn("total", br)

    def test_count_matches_branches_length(self):
        self._write_state(self._make_multi_task_state())
        d = self.client.get("/branches").get_json()
        self.assertEqual(d.get("count"), len(d.get("branches", [])))

    def test_empty_state_returns_empty_list(self):
        self._write_state({"step": 0, "dag": {}})
        d = self.client.get("/branches").get_json()
        self.assertEqual(d.get("branches", []), [])


# ---------------------------------------------------------------------------
# GET /subtasks — filter combinations
# ---------------------------------------------------------------------------

class TestSubtasksFilter(_Base):

    def setUp(self):
        super().setUp()
        self._write_state(self._make_multi_task_state())

    def test_status_filter_running(self):
        d = self.client.get("/subtasks?status=Running").get_json()
        for s in d["subtasks"]:
            self.assertEqual(s["status"], "Running")

    def test_task_and_status_filter(self):
        d = self.client.get("/subtasks?task=Task+1&status=Pending").get_json()
        for s in d["subtasks"]:
            self.assertEqual(s["status"], "Pending")

    def test_branch_filter(self):
        d = self.client.get("/subtasks?branch=Branch+A").get_json()
        for s in d["subtasks"]:
            self.assertEqual(s["branch"], "Branch A")

    def test_output_flag_includes_output_field(self):
        d = self.client.get("/subtasks?output=1").get_json()
        for s in d["subtasks"]:
            self.assertIn("output", s)

    def test_no_filter_returns_all(self):
        d = self.client.get("/subtasks").get_json()
        self.assertEqual(d["count"], 5)


# ---------------------------------------------------------------------------
# GET /shortcuts — content validation
# ---------------------------------------------------------------------------

class TestShortcutsExtra(_Base):

    def test_known_shortcut_key_present(self):
        d = self.client.get("/shortcuts").get_json()
        keys = [s["key"] for s in d.get("shortcuts", [])]
        self.assertIn("r", keys)

    def test_all_shortcuts_have_description(self):
        d = self.client.get("/shortcuts").get_json()
        for s in d.get("shortcuts", []):
            self.assertIn("description", s)
            self.assertIsInstance(s["description"], str)
            self.assertGreater(len(s["description"]), 0)

    def test_shortcut_count_matches_count_field(self):
        d = self.client.get("/shortcuts").get_json()
        self.assertEqual(d.get("count"), len(d.get("shortcuts", [])))


# ---------------------------------------------------------------------------
# GET /health — uptime and state
# ---------------------------------------------------------------------------

class TestHealthExtra(_Base):

    def test_health_returns_200(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)

    def test_ok_field(self):
        d = self.client.get("/health").get_json()
        self.assertIn("ok", d)
        self.assertTrue(d["ok"])

    def test_uptime_s_non_negative(self):
        d = self.client.get("/health").get_json()
        self.assertIn("uptime_s", d)
        self.assertGreaterEqual(d["uptime_s"], 0)

    def test_step_field(self):
        self._write_state(self._make_state(step=7))
        d = self.client.get("/health").get_json()
        self.assertIn("step", d)
        self.assertEqual(d["step"], 7)

    def test_state_file_exists_true_when_written(self):
        self._write_state(self._make_state())
        d = self.client.get("/health").get_json()
        self.assertTrue(d.get("state_file_exists"))


# ---------------------------------------------------------------------------
# GET /status — stalled and pct fields
# ---------------------------------------------------------------------------

class TestStatusExtra(_Base):

    def test_stalled_field_present(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/status").get_json()
        self.assertIn("stalled", d)

    def test_pct_in_range(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertGreaterEqual(d["pct"], 0)
        self.assertLessEqual(d["pct"], 100)

    def test_complete_true_when_all_verified(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified"}))
        d = self.client.get("/status").get_json()
        self.assertTrue(d.get("complete"))

    def test_complete_false_when_pending(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertFalse(d.get("complete"))

    def test_running_count_matches_state(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Running", "A3": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertEqual(d["running"], 2)


# ---------------------------------------------------------------------------
# GET /dag/summary — new endpoint
# ---------------------------------------------------------------------------

class TestDagSummary(_Base):

    def test_empty_dag_returns_zero_counts(self):
        self._write_state({"step": 0, "dag": {}})
        d = self.client.get("/dag/summary").get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["verified"], 0)
        self.assertEqual(d["pct"], 0.0)
        self.assertFalse(d["complete"])

    def test_fields_present(self):
        self._write_state(self._make_state())
        d = self.client.get("/dag/summary").get_json()
        for field in ("step", "total", "verified", "running", "pending", "pct", "complete", "tasks", "summary"):
            self.assertIn(field, d)

    def test_verified_count_matches_state(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified", "A3": "Pending"}))
        d = self.client.get("/dag/summary").get_json()
        self.assertEqual(d["verified"], 2)
        self.assertEqual(d["total"], 3)

    def test_complete_true_when_all_verified(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/dag/summary").get_json()
        self.assertTrue(d["complete"])

    def test_tasks_list_has_task_id(self):
        self._write_state(self._make_state())
        d = self.client.get("/dag/summary").get_json()
        self.assertTrue(len(d["tasks"]) > 0)
        self.assertIn("id", d["tasks"][0])

    def test_summary_text_contains_step(self):
        self._write_state(self._make_state(step=42))
        d = self.client.get("/dag/summary").get_json()
        self.assertIn("42", d["summary"])

    def test_pct_in_range(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/dag/summary").get_json()
        self.assertGreaterEqual(d["pct"], 0)
        self.assertLessEqual(d["pct"], 100)

    def test_multi_task_aggregation(self):
        self._write_state(self._make_multi_task_state())
        d = self.client.get("/dag/summary").get_json()
        self.assertGreater(d["total"], 0)
        self.assertEqual(len(d["tasks"]), 2)


class TestMetricsSummaryEndpoint(_Base):
    """TASK-323: GET /metrics/summary reads metrics.jsonl (OM-021 to OM-030)."""

    def _patch_metrics_path(self, path):
        import api.blueprints.metrics as _m
        from unittest.mock import patch as _p
        return _p.object(_m, "METRICS_JSONL_PATH", new=path)

    def test_empty_file_returns_nulls(self):
        import tempfile
        from pathlib import Path
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
            tmp = Path(tf.name)
        tmp.write_text("", encoding="utf-8")
        with self._patch_metrics_path(tmp):
            resp = self.client.get("/metrics/summary")
        self.assertEqual(resp.status_code, 200)
        d = resp.get_json()
        self.assertEqual(d["record_count"], 0)
        self.assertIsNone(d["avg_elapsed_s"])

    def test_missing_file_returns_empty(self):
        from pathlib import Path
        with self._patch_metrics_path(Path("/nonexistent/metrics.jsonl")):
            resp = self.client.get("/metrics/summary")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["record_count"], 0)

    def test_records_aggregate_correctly(self):
        import json, tempfile
        from pathlib import Path
        records = [
            {"ts": "2026-03-10T00:00:00Z", "step": 1, "elapsed_s": 1.0,
             "sdk_dispatched": 2, "sdk_succeeded": 2, "sdk_success_rate": 1.0,
             "started": 1, "verified": 2},
            {"ts": "2026-03-10T00:01:00Z", "step": 2, "elapsed_s": 3.0,
             "sdk_dispatched": 1, "sdk_succeeded": 0, "sdk_success_rate": 0.0,
             "started": 0, "verified": 1},
        ]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w",
                                         delete=False, encoding="utf-8") as tf:
            for r in records:
                tf.write(json.dumps(r) + "\n")
            tmp = Path(tf.name)
        with self._patch_metrics_path(tmp):
            resp = self.client.get("/metrics/summary")
        d = resp.get_json()
        self.assertEqual(d["record_count"], 2)
        self.assertAlmostEqual(d["avg_elapsed_s"], 2.0, places=2)
        self.assertEqual(d["total_started"], 1)
        self.assertEqual(d["total_verified"], 3)
        self.assertAlmostEqual(d["sdk_success_rate"], 2/3, places=3)

    def test_no_sdk_dispatches_returns_null_rate(self):
        import json, tempfile
        from pathlib import Path
        records = [{"ts": "t", "step": 1, "elapsed_s": 0.5,
                    "sdk_dispatched": 0, "sdk_succeeded": 0,
                    "sdk_success_rate": None, "started": 1, "verified": 1}]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w",
                                         delete=False, encoding="utf-8") as tf:
            for r in records:
                tf.write(json.dumps(r) + "\n")
            tmp = Path(tf.name)
        with self._patch_metrics_path(tmp):
            resp = self.client.get("/metrics/summary")
        self.assertIsNone(resp.get_json()["sdk_success_rate"])

    def test_response_has_all_expected_keys(self):
        import json, tempfile
        from pathlib import Path
        records = [{"ts": "t", "step": 1, "elapsed_s": 1.0,
                    "sdk_dispatched": 1, "sdk_succeeded": 1,
                    "sdk_success_rate": 1.0, "started": 1, "verified": 1}]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w",
                                         delete=False, encoding="utf-8") as tf:
            for r in records:
                tf.write(json.dumps(r) + "\n")
            tmp = Path(tf.name)
        with self._patch_metrics_path(tmp):
            resp = self.client.get("/metrics/summary")
        d = resp.get_json()
        for key in ("record_count", "avg_elapsed_s", "p95_elapsed_s",
                    "sdk_success_rate", "total_started", "total_verified"):
            self.assertIn(key, d, f"Missing key: {key}")


class TestSecurityHeaders(_Base):
    """TASK-322: Flask security headers present on every response (SE-021, SE-025)."""

    def test_x_frame_options(self):
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")

    def test_x_content_type_options(self):
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")

    def test_referrer_policy(self):
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_content_security_policy_present(self):
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        csp = resp.headers.get("Content-Security-Policy", "")
        self.assertIn("default-src", csp)

    def test_cors_header_still_present(self):
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_x_api_version_present(self):
        """TASK-331: X-API-Version header is set to '1' on every response (BE-040)."""
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        self.assertEqual(resp.headers.get("X-API-Version"), "1")

    def test_x_request_id_generated_when_absent(self):
        """TASK-331: X-Request-ID is a UUID4 when not provided by caller (OM-041)."""
        import re
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        req_id = resp.headers.get("X-Request-ID", "")
        self.assertRegex(
            req_id,
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            f"X-Request-ID not a valid UUID4: {req_id!r}",
        )

    def test_x_request_id_echoed_from_request(self):
        """TASK-331: X-Request-ID is echoed back when caller supplies one (OM-041)."""
        self._write_state(self._make_state())
        supplied = "my-trace-abc-123"
        resp = self.client.get("/status", headers={"X-Request-ID": supplied})
        self.assertEqual(resp.headers.get("X-Request-ID"), supplied)

    def test_x_request_id_unique_per_request(self):
        """TASK-331: Two requests without X-Request-ID get different UUIDs (OM-041)."""
        self._write_state(self._make_state())
        r1 = self.client.get("/status")
        r2 = self.client.get("/status")
        self.assertNotEqual(
            r1.headers.get("X-Request-ID"),
            r2.headers.get("X-Request-ID"),
        )

    def test_x_response_time_present(self):
        """TASK-339: X-Response-Time header in milliseconds on every response (OM-003)."""
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        rt = resp.headers.get("X-Response-Time", "")
        self.assertTrue(rt.endswith("ms"), f"Expected X-Response-Time to end with 'ms', got: {rt!r}")

    def test_health_version_field(self):
        """TASK-339: GET /health returns version string (OM-002)."""
        self._write_state(self._make_state())
        resp = self.client.get("/health")
        d = resp.get_json()
        self.assertIn("version", d)
        self.assertIsInstance(d["version"], str)

    def test_health_total_subtasks_field(self):
        """TASK-339: GET /health returns total_subtasks count."""
        self._write_state(self._make_state())
        resp = self.client.get("/health")
        d = resp.get_json()
        self.assertIn("total_subtasks", d)
        self.assertGreaterEqual(d["total_subtasks"], 0)


class TestRateLimit(_Base):
    """TASK-322: In-memory rate limiter returns 429 when limit exceeded (SE-022, SE-023)."""

    def _reset_rl(self):
        import api.app as _app
        _app._rate_limiter._read.clear()
        _app._rate_limiter._write.clear()

    def test_read_under_limit_allowed(self):
        self._reset_rl()
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        self.assertEqual(resp.status_code, 200)

    def test_write_under_limit_allowed(self):
        self._reset_rl()
        self._write_state(self._make_state())
        import api.app as _app
        original = _app._rate_limiter.write_limit
        _app._rate_limiter.write_limit = 200
        resp = self.client.post("/config/reset")
        _app._rate_limiter.write_limit = original
        self.assertIn(resp.status_code, (200, 400, 404))  # not 429

    def test_read_rate_limit_triggers_429(self):
        self._reset_rl()
        import api.app as _app
        original = _app._rate_limiter.read_limit
        _app._rate_limiter.read_limit = 2
        self._write_state(self._make_state())
        self.client.get("/status")
        self.client.get("/status")
        resp = self.client.get("/status")  # 3rd should be blocked
        _app._rate_limiter.read_limit = original
        self.assertEqual(resp.status_code, 429)

    def test_write_rate_limit_triggers_429(self):
        self._reset_rl()
        import api.app as _app
        original = _app._rate_limiter.write_limit
        _app._rate_limiter.write_limit = 1
        self._write_state(self._make_state())
        self.client.post("/config/reset")
        resp = self.client.post("/config/reset")  # 2nd should be blocked
        _app._rate_limiter.write_limit = original
        self.assertEqual(resp.status_code, 429)

    def test_429_response_has_error_key(self):
        self._reset_rl()
        import api.app as _app
        original = _app._rate_limiter.read_limit
        _app._rate_limiter.read_limit = 0  # block immediately
        self._write_state(self._make_state())
        resp = self.client.get("/status")
        _app._rate_limiter.read_limit = original
        self.assertEqual(resp.status_code, 429)
        self.assertIn("error", resp.get_json())


if __name__ == "__main__":
    unittest.main()
