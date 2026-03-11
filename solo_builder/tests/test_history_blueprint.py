"""Tests for history blueprint — GET /history, /history/count, /history/export,
/diff, /dag/diff, /run/history (TASK-396)."""
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


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "STATE_PATH",   new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "CACHE_DIR",    new=Path(self._tmp) / "cache"),
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

    def _write_state(self, dag=None, step=0, meta_history=None):
        state = {"step": step, "dag": dag or {}}
        if meta_history is not None:
            state["meta_history"] = meta_history
        self._state_path.write_text(json.dumps(state), encoding="utf-8")

    def _make_dag_with_history(self):
        """DAG with two subtasks, each with history entries."""
        return {
            "T0": {"branches": {"b0": {"subtasks": {
                "s1": {
                    "status": "Verified",
                    "output": "out1",
                    "history": [
                        {"step": 1, "status": "Running"},
                        {"step": 2, "status": "Verified"},
                    ],
                },
                "s2": {
                    "status": "Review",
                    "output": "out2",
                    "history": [
                        {"step": 3, "status": "Review"},
                    ],
                },
            }}}}
        }


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------

class TestHistoryEndpoint(_Base):

    def test_history_returns_200(self):
        self._write_state()
        self.assertEqual(self.client.get("/history").status_code, 200)

    def test_history_empty_dag_returns_empty_events(self):
        self._write_state()
        data = self.client.get("/history").get_json()
        self.assertEqual(data["events"], [])
        self.assertEqual(data["total"], 0)

    def test_history_collects_events_from_history_arrays(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history").get_json()
        self.assertEqual(data["total"], 3)

    def test_history_events_sorted_by_step_descending(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history").get_json()
        steps = [e["step"] for e in data["events"]]
        self.assertEqual(steps, sorted(steps, reverse=True))

    def test_history_since_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history?since=1").get_json()
        # steps 2 and 3 only
        self.assertEqual(data["total"], 2)

    def test_history_status_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history?status=Verified").get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["events"][0]["status"], "Verified")

    def test_history_subtask_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history?subtask=s1").get_json()
        self.assertEqual(data["total"], 2)

    def test_history_task_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history?task=T0").get_json()
        self.assertEqual(data["total"], 3)

    def test_history_branch_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history?branch=b0").get_json()
        self.assertEqual(data["total"], 3)

    def test_history_branch_filter_no_match(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history?branch=nope").get_json()
        self.assertEqual(data["total"], 0)

    def test_history_pagination_page_and_pages(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history?limit=1&page=1").get_json()
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["pages"], 3)

    def test_history_review_count(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history").get_json()
        self.assertEqual(data["review"], 1)  # one Review event

    def test_history_has_page_key(self):
        self._write_state()
        data = self.client.get("/history").get_json()
        self.assertIn("page", data)
        self.assertIn("pages", data)

    def test_history_no_limit_zero_pages_is_one(self):
        self._write_state()
        data = self.client.get("/history?limit=0").get_json()
        self.assertEqual(data["pages"], 1)

    def test_history_event_has_required_fields(self):
        self._write_state(dag=self._make_dag_with_history())
        event = self.client.get("/history").get_json()["events"][0]
        for field in ("step", "subtask", "task", "branch", "status", "output"):
            self.assertIn(field, event)


# ---------------------------------------------------------------------------
# GET /history/count
# ---------------------------------------------------------------------------

class TestHistoryCountEndpoint(_Base):

    def test_history_count_returns_200(self):
        self._write_state()
        self.assertEqual(self.client.get("/history/count").status_code, 200)

    def test_history_count_empty_dag(self):
        self._write_state()
        data = self.client.get("/history/count").get_json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["filtered"], 0)

    def test_history_count_total_matches_all_history_entries(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/count").get_json()
        self.assertEqual(data["total"], 3)

    def test_history_count_filtered_by_status(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/count?status=Running").get_json()
        self.assertEqual(data["filtered"], 1)

    def test_history_count_by_status_breakdown(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/count").get_json()
        self.assertIn("by_status", data)
        self.assertEqual(data["by_status"].get("Verified"), 1)
        self.assertEqual(data["by_status"].get("Running"), 1)
        self.assertEqual(data["by_status"].get("Review"), 1)

    def test_history_count_since_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/count?since=2").get_json()
        self.assertEqual(data["filtered"], 1)  # only step 3

    def test_history_count_subtask_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/count?subtask=s2").get_json()
        self.assertEqual(data["filtered"], 1)


# ---------------------------------------------------------------------------
# GET /history/export
# ---------------------------------------------------------------------------

class TestHistoryExportEndpoint(_Base):

    def test_history_export_default_csv(self):
        self._write_state()
        r = self.client.get("/history/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_history_export_csv_has_header(self):
        self._write_state()
        text = self.client.get("/history/export").data.decode("utf-8")
        self.assertIn("step", text)
        self.assertIn("subtask", text)

    def test_history_export_json_returns_list(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/export?format=json").get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)

    def test_history_export_json_event_fields(self):
        self._write_state(dag=self._make_dag_with_history())
        event = self.client.get("/history/export?format=json").get_json()[0]
        for f in ("step", "subtask", "task", "branch", "status"):
            self.assertIn(f, event)

    def test_history_export_since_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/export?format=json&since=1").get_json()
        self.assertTrue(all(e["step"] > 1 for e in data))

    def test_history_export_limit(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/export?format=json&limit=1").get_json()
        self.assertEqual(len(data), 1)

    def test_history_export_subtask_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/export?format=json&subtask=s1").get_json()
        self.assertEqual(len(data), 2)

    def test_history_export_status_filter(self):
        self._write_state(dag=self._make_dag_with_history())
        data = self.client.get("/history/export?format=json&status=Review").get_json()
        self.assertEqual(len(data), 1)

    def test_history_export_csv_content_disposition(self):
        self._write_state()
        r = self.client.get("/history/export")
        self.assertIn("history.csv", r.headers.get("Content-Disposition", ""))

    def test_history_export_empty_dag_csv_header_only(self):
        self._write_state()
        text = self.client.get("/history/export").data.decode("utf-8")
        lines = [l for l in text.strip().splitlines() if l]
        self.assertEqual(len(lines), 1)  # header only


# ---------------------------------------------------------------------------
# GET /diff
# ---------------------------------------------------------------------------

class TestDiffEndpoint(_Base):

    def test_diff_no_backup_returns_200(self):
        self._write_state()
        self.assertEqual(self.client.get("/diff").status_code, 200)

    def test_diff_no_backup_returns_empty_changes(self):
        self._write_state()
        data = self.client.get("/diff").get_json()
        self.assertEqual(data["changes"], [])
        self.assertIn("message", data)

    def test_diff_with_backup_detects_status_change(self):
        old_state = {"step": 1, "dag": {"T0": {"branches": {"b0": {"subtasks": {
            "s1": {"status": "Pending"}
        }}}}}}
        backup_path = Path(str(self._state_path) + ".1")
        backup_path.write_text(json.dumps(old_state), encoding="utf-8")
        new_state = {"step": 2, "dag": {"T0": {"branches": {"b0": {"subtasks": {
            "s1": {"status": "Verified", "output": "done"}
        }}}}}}
        self._state_path.write_text(json.dumps(new_state), encoding="utf-8")
        data = self.client.get("/diff").get_json()
        self.assertEqual(len(data["changes"]), 1)
        self.assertEqual(data["changes"][0]["old_status"], "Pending")
        self.assertEqual(data["changes"][0]["new_status"], "Verified")

    def test_diff_no_change_returns_empty_changes(self):
        state = {"step": 2, "dag": {"T0": {"branches": {"b0": {"subtasks": {
            "s1": {"status": "Pending"}
        }}}}}}
        backup_path = Path(str(self._state_path) + ".1")
        backup_path.write_text(json.dumps(state), encoding="utf-8")
        self._state_path.write_text(json.dumps(state), encoding="utf-8")
        data = self.client.get("/diff").get_json()
        self.assertEqual(data["changes"], [])

    def test_diff_step_numbers_in_response(self):
        old_state = {"step": 1, "dag": {}}
        backup_path = Path(str(self._state_path) + ".1")
        backup_path.write_text(json.dumps(old_state), encoding="utf-8")
        self._write_state(step=5)
        data = self.client.get("/diff").get_json()
        self.assertEqual(data["old_step"], 1)
        self.assertEqual(data["new_step"], 5)


# ---------------------------------------------------------------------------
# GET /dag/diff
# ---------------------------------------------------------------------------

class TestDagDiffEndpoint(_Base):

    def test_dag_diff_missing_from_returns_400(self):
        self._write_state()
        r = self.client.get("/dag/diff")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_dag_diff_detects_status_transition(self):
        dag = {"T0": {"branches": {"b0": {"subtasks": {
            "s1": {
                "status": "Verified",
                "history": [
                    {"step": 1, "status": "Running"},
                    {"step": 5, "status": "Verified"},
                ],
            }
        }}}}}
        self._write_state(dag=dag, step=10)
        data = self.client.get("/dag/diff?from=0&to=10").get_json()
        self.assertEqual(len(data["changes"]), 1)
        self.assertEqual(data["changes"][0]["from_status"], "Pending")
        self.assertEqual(data["changes"][0]["to_status"], "Verified")

    def test_dag_diff_no_change_returns_empty(self):
        dag = {"T0": {"branches": {"b0": {"subtasks": {
            "s1": {"status": "Verified", "history": [{"step": 1, "status": "Verified"}]}
        }}}}}
        self._write_state(dag=dag, step=10)
        data = self.client.get("/dag/diff?from=1&to=10").get_json()
        self.assertEqual(data["changes"], [])

    def test_dag_diff_returns_from_to_count(self):
        self._write_state(step=10)
        data = self.client.get("/dag/diff?from=2&to=8").get_json()
        self.assertIn("from", data)
        self.assertIn("to", data)
        self.assertIn("count", data)


# ---------------------------------------------------------------------------
# GET /run/history
# ---------------------------------------------------------------------------

class TestRunHistoryEndpoint(_Base):

    def test_run_history_returns_200(self):
        self._write_state()
        self.assertEqual(self.client.get("/run/history").status_code, 200)

    def test_run_history_empty_state(self):
        self._write_state()
        data = self.client.get("/run/history").get_json()
        self.assertEqual(data["records"], [])
        self.assertEqual(data["total_steps"], 0)

    def test_run_history_records_from_meta_history(self):
        self._write_state(meta_history=[
            {"verified": 2, "healed": 0},
            {"verified": 1, "healed": 1},
        ])
        data = self.client.get("/run/history").get_json()
        self.assertEqual(data["total_steps"], 2)
        self.assertEqual(len(data["records"]), 2)

    def test_run_history_cumulative_sums(self):
        self._write_state(meta_history=[
            {"verified": 3, "healed": 0},
            {"verified": 2, "healed": 0},
        ])
        data = self.client.get("/run/history").get_json()
        self.assertEqual(data["records"][0]["cumulative"], 3)
        self.assertEqual(data["records"][1]["cumulative"], 5)

    def test_run_history_since_filter(self):
        self._write_state(meta_history=[
            {"verified": 1, "healed": 0},
            {"verified": 1, "healed": 0},
            {"verified": 1, "healed": 0},
        ])
        data = self.client.get("/run/history?since=1").get_json()
        self.assertEqual(len(data["records"]), 2)

    def test_run_history_limit(self):
        self._write_state(meta_history=[
            {"verified": 1, "healed": 0},
            {"verified": 2, "healed": 0},
            {"verified": 3, "healed": 0},
        ])
        data = self.client.get("/run/history?limit=2").get_json()
        self.assertEqual(len(data["records"]), 2)

    def test_run_history_step_index_starts_at_one(self):
        self._write_state(meta_history=[{"verified": 0, "healed": 0}])
        data = self.client.get("/run/history").get_json()
        self.assertEqual(data["records"][0]["step_index"], 1)

    def test_run_history_has_count_key(self):
        self._write_state()
        data = self.client.get("/run/history").get_json()
        self.assertIn("count", data)


if __name__ == "__main__":
    unittest.main()
