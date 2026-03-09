#!/usr/bin/env python3
"""
Tests for Solo Builder Flask REST API (api/app.py).

Run:
    python api/test_app.py
    python -m pytest api/test_app.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import api.app as app_module


class _Base(unittest.TestCase):
    """Shared test setup — temp state dir, Flask test client."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path = Path(self._tmp) / "state" / "solo_builder_state.json"
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path = Path(self._tmp) / "config" / "settings.json"
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            source_settings = json.loads(app_module.SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            source_settings = {
                "STALL_THRESHOLD": 5,
                "EXECUTOR_VERIFY_PROBABILITY": 0.8,
            }
        self._settings_path.write_text(
            json.dumps(source_settings, indent=4),
            encoding="utf-8",
        )
        self._trigger_path  = Path(self._tmp) / "state" / "run_trigger"
        self._verify_path   = Path(self._tmp) / "state" / "verify_trigger.json"
        self._describe_path = Path(self._tmp) / "state" / "describe_trigger.json"
        self._tools_path    = Path(self._tmp) / "state" / "tools_trigger.json"
        self._set_path      = Path(self._tmp) / "state" / "set_trigger.json"
        self._outputs_path  = Path(self._tmp) / "solo_builder_outputs.md"
        self._journal_path  = Path(self._tmp) / "journal.md"

        # Patch all module-level paths
        self._heartbeat_path          = Path(self._tmp) / "state" / "step.txt"
        self._add_task_path           = Path(self._tmp) / "state" / "add_task_trigger.json"
        self._add_branch_path         = Path(self._tmp) / "state" / "add_branch_trigger.json"
        self._priority_branch_path    = Path(self._tmp) / "state" / "prioritize_branch_trigger.json"
        self._undo_path               = Path(self._tmp) / "state" / "undo_trigger"
        self._depends_path            = Path(self._tmp) / "state" / "depends_trigger.json"
        self._undepends_path          = Path(self._tmp) / "state" / "undepends_trigger.json"
        self._reset_path              = Path(self._tmp) / "state" / "reset_trigger"
        self._snapshot_path           = Path(self._tmp) / "state" / "snapshot_trigger"
        self._pause_path              = Path(self._tmp) / "state" / "pause_trigger"
        self._dag_import_path         = Path(self._tmp) / "state" / "dag_import_trigger.json"
        self._heal_trigger_path       = Path(self._tmp) / "state" / "heal_trigger.json"
        self._cache_dir               = Path(self._tmp) / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "TRIGGER_PATH", new=self._trigger_path),
            patch.object(app_module, "VERIFY_TRIGGER", new=self._verify_path),
            patch.object(app_module, "DESCRIBE_TRIGGER", new=self._describe_path),
            patch.object(app_module, "TOOLS_TRIGGER", new=self._tools_path),
            patch.object(app_module, "SET_TRIGGER", new=self._set_path),
            patch.object(app_module, "HEARTBEAT_PATH", new=self._heartbeat_path),
            patch.object(app_module, "OUTPUTS_PATH", new=self._outputs_path),
            patch.object(app_module, "JOURNAL_PATH", new=self._journal_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "ADD_TASK_TRIGGER", new=self._add_task_path),
            patch.object(app_module, "ADD_BRANCH_TRIGGER", new=self._add_branch_path),
            patch.object(app_module, "PRIORITY_BRANCH_TRIGGER", new=self._priority_branch_path),
            patch.object(app_module, "UNDO_TRIGGER", new=self._undo_path),
            patch.object(app_module, "DEPENDS_TRIGGER", new=self._depends_path),
            patch.object(app_module, "UNDEPENDS_TRIGGER", new=self._undepends_path),
            patch.object(app_module, "RESET_TRIGGER", new=self._reset_path),
            patch.object(app_module, "SNAPSHOT_TRIGGER", new=self._snapshot_path),
            patch.object(app_module, "PAUSE_TRIGGER", new=self._pause_path),
            patch.object(app_module, "DAG_IMPORT_TRIGGER", new=self._dag_import_path),
            patch.object(app_module, "HEAL_TRIGGER", new=self._heal_trigger_path),
            patch.object(app_module, "CACHE_DIR", new=self._cache_dir),
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

    def _write_state(self, state: dict) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state), encoding="utf-8")

    def _make_state(self, subtasks: dict | None = None, step: int = 5) -> dict:
        """Build a minimal DAG state with Task 0 / Branch A."""
        sts = subtasks or {"A1": "Verified", "A2": "Pending"}
        return {
            "step": step,
            "dag": {
                "Task 0": {
                    "status": "Running",
                    "depends_on": [],
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                name: {"status": status, "output": f"output of {name}",
                                       "description": f"desc of {name}"}
                                for name, status in sts.items()
                            }
                        }
                    },
                }
            },
        }


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

class TestGetStatus(_Base):

    def test_empty_state_returns_zeros(self):
        r = self.client.get("/status")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["verified"], 0)

    def test_status_reflects_dag(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertEqual(d["total"], 3)
        self.assertEqual(d["verified"], 1)
        self.assertEqual(d["running"], 1)
        self.assertEqual(d["pending"], 1)
        self.assertAlmostEqual(d["pct"], 33.3, places=0)

    def test_complete_flag(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified"}))
        d = self.client.get("/status").get_json()
        self.assertTrue(d["complete"])

    def test_status_has_stalled_key(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/status").get_json()
        self.assertIn("stalled", d)

    def test_stalled_zero_when_no_running(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/status").get_json()
        self.assertEqual(d["stalled"], 0)

    def test_status_includes_review_field(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertIn("review", d)
        self.assertEqual(d["review"], 1)

    def test_review_not_counted_in_pending(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertEqual(d["pending"], 1)
        self.assertEqual(d["review"], 1)

    def test_pending_sum_to_total(self):
        self._write_state(self._make_state(
            {"A1": "Verified", "A2": "Running", "A3": "Review", "A4": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertEqual(
            d["verified"] + d["running"] + d["review"] + d["pending"],
            d["total"]
        )

    def test_stalled_by_branch_key_present(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/status").get_json()
        self.assertIn("stalled_by_branch", d)

    def test_stalled_by_branch_empty_when_no_stall(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/status").get_json()
        self.assertEqual(d["stalled_by_branch"], [])

    def _set_threshold_in_settings(self, n: int) -> None:
        cfg = json.loads(self._settings_path.read_text(encoding="utf-8"))
        cfg["STALL_THRESHOLD"] = n
        self._settings_path.write_text(json.dumps(cfg), encoding="utf-8")

    def test_stalled_by_branch_populated_when_stalled(self):
        # threshold=5, step=10, last_update=0 → age=10 ≥ 5 → stalled
        self._set_threshold_in_settings(5)
        state = self._make_state({"A1": "Running"}, step=10)
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["last_update"] = 0
        self._write_state(state)
        d = self.client.get("/status").get_json()
        self.assertEqual(len(d["stalled_by_branch"]), 1)
        entry = d["stalled_by_branch"][0]
        self.assertEqual(entry["task"], "Task 0")
        self.assertEqual(entry["branch"], "Branch A")
        self.assertEqual(entry["count"], 1)

    def test_stalled_by_branch_count_matches_stalled_total(self):
        self._set_threshold_in_settings(5)
        state = self._make_state({"A1": "Running", "A2": "Running"}, step=10)
        for k in ("A1", "A2"):
            state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"][k]["last_update"] = 0
        self._write_state(state)
        d = self.client.get("/status").get_json()
        branch_total = sum(e["count"] for e in d["stalled_by_branch"])
        self.assertEqual(branch_total, d["stalled"])

    def test_stalled_by_branch_not_stalled_not_included(self):
        # threshold=5, last_update=9, step=10 → age=1 < 5 → not stalled
        self._set_threshold_in_settings(5)
        state = self._make_state({"A1": "Running"}, step=10)
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["last_update"] = 9
        self._write_state(state)
        d = self.client.get("/status").get_json()
        self.assertEqual(d["stalled_by_branch"], [])

    def test_stalled_by_branch_sorted_desc(self):
        # Two tasks: Task A has 2 stalled, Task B has 1 — Task A must come first
        self._set_threshold_in_settings(5)
        state = {
            "step": 10,
            "dag": {
                "Task A": {"status": "Running", "depends_on": [], "branches": {
                    "Br A": {"subtasks": {
                        "SA1": {"status": "Running", "output": "", "last_update": 0},
                        "SA2": {"status": "Running", "output": "", "last_update": 0},
                    }},
                }},
                "Task B": {"status": "Running", "depends_on": [], "branches": {
                    "Br B": {"subtasks": {
                        "SB1": {"status": "Running", "output": "", "last_update": 0},
                    }},
                }},
            },
        }
        self._write_state(state)
        d = self.client.get("/status").get_json()
        counts = [e["count"] for e in d["stalled_by_branch"]]
        self.assertEqual(counts, sorted(counts, reverse=True))
        self.assertEqual(d["stalled_by_branch"][0]["count"], 2)


# ---------------------------------------------------------------------------
# GET /history/count
# ---------------------------------------------------------------------------

class TestHistoryCount(_Base):

    def _state_with_mixed(self):
        state = self._make_state({"A1": "Verified", "A2": "Pending"})
        br = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        br["A1"]["history"] = [{"status": "Verified", "step": 1}, {"status": "Verified", "step": 3}]
        br["A2"]["history"] = [{"status": "Running",  "step": 2}]
        return state

    def test_count_status(self):
        r = self.client.get("/history/count")
        self.assertEqual(r.status_code, 200)

    def test_count_has_keys(self):
        d = self.client.get("/history/count").get_json()
        self.assertIn("total", d)
        self.assertIn("filtered", d)

    def test_count_empty(self):
        d = self.client.get("/history/count").get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["filtered"], 0)

    def test_count_total(self):
        self._write_state(self._state_with_mixed())
        d = self.client.get("/history/count").get_json()
        self.assertEqual(d["total"], 3)

    def test_count_filtered_by_status(self):
        self._write_state(self._state_with_mixed())
        d = self.client.get("/history/count?status=Verified").get_json()
        self.assertEqual(d["total"], 3)
        self.assertEqual(d["filtered"], 2)

    def test_count_filtered_by_subtask(self):
        self._write_state(self._state_with_mixed())
        d = self.client.get("/history/count?subtask=A2").get_json()
        self.assertEqual(d["filtered"], 1)

    def test_count_since_applies(self):
        self._write_state(self._state_with_mixed())
        d = self.client.get("/history/count?since=2").get_json()
        # step>2 = only step 3 (A1 Verified)
        self.assertEqual(d["filtered"], 1)

    def test_count_has_by_status(self):
        d = self.client.get("/history/count").get_json()
        self.assertIn("by_status", d)
        self.assertIsInstance(d["by_status"], dict)

    def test_count_by_status_review(self):
        state = self._make_state({"A1": "Review", "A2": "Verified"})
        br = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        br["A1"]["history"] = [{"status": "Review", "step": 1}]
        br["A2"]["history"] = [{"status": "Verified", "step": 2}, {"status": "Review", "step": 1}]
        self._write_state(state)
        d = self.client.get("/history/count").get_json()
        self.assertEqual(d["by_status"].get("Review"), 2)
        self.assertEqual(d["by_status"].get("Verified"), 1)

    def test_count_by_status_excludes_zero(self):
        # absent status keys are simply not present (no zero-padding)
        self._write_state(self._state_with_mixed())
        d = self.client.get("/history/count").get_json()
        self.assertNotIn("Review", d["by_status"])


# ---------------------------------------------------------------------------
# GET /tasks
# ---------------------------------------------------------------------------

class TestGetTasks(_Base):

    def test_lists_all_tasks(self):
        self._write_state(self._make_state())
        d = self.client.get("/tasks").get_json()
        self.assertEqual(len(d["tasks"]), 1)
        self.assertEqual(d["tasks"][0]["id"], "Task 0")

    def test_empty_dag_returns_empty_list(self):
        d = self.client.get("/tasks").get_json()
        self.assertEqual(d["tasks"], [])

    def test_task_filter_substring_match(self):
        self._write_state(self._make_state())
        d = self.client.get("/tasks?task=task+0").get_json()
        self.assertEqual(len(d["tasks"]), 1)

    def test_task_filter_no_match_returns_empty(self):
        self._write_state(self._make_state())
        d = self.client.get("/tasks?task=xyzzy").get_json()
        self.assertEqual(d["tasks"], [])

    def test_summary_includes_pct(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/tasks").get_json()
        task = d["tasks"][0]
        self.assertIn("pct", task)
        self.assertAlmostEqual(task["pct"], 50.0)

    def test_summary_pct_zero_when_no_subtasks(self):
        state = {"dag": {"Task 0": {"branches": {}, "status": "Pending"}}, "step": 0}
        self._write_state(state)
        d = self.client.get("/tasks").get_json()
        self.assertEqual(d["tasks"][0]["pct"], 0.0)

    def test_summary_includes_review_subtasks(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Running"}))
        d = self.client.get("/tasks").get_json()
        task = d["tasks"][0]
        self.assertIn("review_subtasks", task)
        self.assertEqual(task["review_subtasks"], 1)

    def test_summary_review_subtasks_zero_when_none(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks").get_json()
        self.assertEqual(d["tasks"][0]["review_subtasks"], 0)

    def test_review_subtasks_summed_across_branches(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Running", "depends_on": [],
            "branches": {
                "Branch A": {"subtasks": {"A1": {"status": "Review", "output": ""}}},
                "Branch B": {"subtasks": {"B1": {"status": "Review", "output": ""}}},
            }}}}
        self._write_state(state)
        task = self.client.get("/tasks").get_json()["tasks"][0]
        self.assertEqual(task["review_subtasks"], 2)

    def test_review_subtasks_not_counted_in_pct(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Pending"}))
        task = self.client.get("/tasks").get_json()["tasks"][0]
        self.assertEqual(task["pct"], 0.0)

    def test_review_subtasks_separate_from_running(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Running"}))
        task = self.client.get("/tasks").get_json()["tasks"][0]
        self.assertEqual(task["review_subtasks"], 1)
        self.assertEqual(task["running_subtasks"], 1)

    def test_response_has_pagination_keys(self):
        self._write_state(self._make_state())
        d = self.client.get("/tasks").get_json()
        for key in ("tasks", "total", "page", "pages"):
            self.assertIn(key, d)

    def _multi_task_state(self, n=5):
        dag = {}
        for i in range(n):
            dag[f"Task {i}"] = {"status": "Pending", "depends_on": [],
                                 "branches": {"B": {"subtasks": {f"S{i}": {"status": "Pending"}}}}}
        return {"step": 0, "dag": dag}

    def test_limit_restricts_tasks(self):
        self._write_state(self._multi_task_state(5))
        d = self.client.get("/tasks?limit=2").get_json()
        self.assertEqual(len(d["tasks"]), 2)

    def test_total_is_all_tasks(self):
        self._write_state(self._multi_task_state(5))
        d = self.client.get("/tasks?limit=2").get_json()
        self.assertEqual(d["total"], 5)

    def test_pages_calculated_correctly(self):
        self._write_state(self._multi_task_state(5))
        d = self.client.get("/tasks?limit=2").get_json()
        self.assertEqual(d["pages"], 3)  # ceil(5/2)

    def test_page_two_returns_next_tasks(self):
        self._write_state(self._multi_task_state(5))
        d1 = self.client.get("/tasks?limit=2&page=1").get_json()
        d2 = self.client.get("/tasks?limit=2&page=2").get_json()
        ids1 = {t["id"] for t in d1["tasks"]}
        ids2 = {t["id"] for t in d2["tasks"]}
        self.assertEqual(len(ids2), 2)
        self.assertTrue(ids1.isdisjoint(ids2))

    def test_limit_zero_returns_all(self):
        self._write_state(self._multi_task_state(5))
        d = self.client.get("/tasks?limit=0").get_json()
        self.assertEqual(len(d["tasks"]), 5)
        self.assertEqual(d["pages"], 1)


# ---------------------------------------------------------------------------
# GET /tasks/<id>
# ---------------------------------------------------------------------------

class TestGetTaskDetail(_Base):

    def test_returns_task_branches(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/Task 0")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("Branch A", d["branches"])

    def test_unknown_task_returns_404(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/Task 99")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /dag/summary
# ---------------------------------------------------------------------------

class TestDagSummary(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.get("/dag/summary")
        self.assertEqual(r.status_code, 200)

    def test_review_in_top_level(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Pending"}))
        d = self.client.get("/dag/summary").get_json()
        self.assertIn("review", d)
        self.assertEqual(d["review"], 1)

    def test_review_in_task_row(self):
        self._write_state(self._make_state({"A1": "Review"}))
        d = self.client.get("/dag/summary").get_json()
        task_row = d["tasks"][0]
        self.assertIn("review", task_row)
        self.assertEqual(task_row["review"], 1)

    def test_review_not_counted_in_pending(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Pending"}))
        d = self.client.get("/dag/summary").get_json()
        self.assertEqual(d["pending"], 1)
        self.assertEqual(d["review"], 1)

    def test_summary_text_includes_review(self):
        self._write_state(self._make_state({"A1": "Review"}))
        d = self.client.get("/dag/summary").get_json()
        self.assertIn("review", d["summary"])


# ---------------------------------------------------------------------------
# POST /run
# ---------------------------------------------------------------------------

class TestPostRun(_Base):

    def test_run_writes_trigger_file(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        r = self.client.post("/run")
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertTrue(self._trigger_path.exists())

    def test_run_complete_pipeline_returns_ok_false(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.post("/run")
        d = r.get_json()
        self.assertFalse(d["ok"])
        self.assertIn("complete", d["reason"])


# ---------------------------------------------------------------------------
# POST /verify
# ---------------------------------------------------------------------------

class TestPostVerify(_Base):

    def test_writes_verify_trigger(self):
        r = self.client.post("/verify",
                             json={"subtask": "a3", "note": "looks good"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["subtask"], "A3")
        trigger = json.loads(self._verify_path.read_text(encoding="utf-8"))
        self.assertEqual(trigger["subtask"], "A3")

    def test_missing_subtask_returns_400(self):
        r = self.client.post("/verify", json={"note": "oops"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /describe
# ---------------------------------------------------------------------------

class TestPostDescribe(_Base):

    def test_writes_describe_trigger(self):
        r = self.client.post("/describe",
                             json={"subtask": "B2", "desc": "Implement caching"})
        self.assertEqual(r.status_code, 202)
        trigger = json.loads(self._describe_path.read_text(encoding="utf-8"))
        self.assertEqual(trigger["subtask"], "B2")
        self.assertEqual(trigger["desc"], "Implement caching")

    def test_missing_desc_returns_400(self):
        r = self.client.post("/describe", json={"subtask": "B2"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /tools
# ---------------------------------------------------------------------------

class TestPostTools(_Base):

    def test_writes_tools_trigger(self):
        r = self.client.post("/tools",
                             json={"subtask": "C1", "tools": "Read,Glob"})
        self.assertEqual(r.status_code, 202)
        trigger = json.loads(self._tools_path.read_text(encoding="utf-8"))
        self.assertEqual(trigger["subtask"], "C1")
        self.assertEqual(trigger["tools"], "Read,Glob")

    def test_missing_tools_returns_400(self):
        r = self.client.post("/tools", json={"subtask": "C1"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /set
# ---------------------------------------------------------------------------

class TestPostSet(_Base):

    def test_writes_set_trigger(self):
        r = self.client.post("/set",
                             json={"key": "REVIEW_MODE", "value": "on"})
        self.assertEqual(r.status_code, 202)
        trigger = json.loads(self._set_path.read_text(encoding="utf-8"))
        self.assertEqual(trigger["key"], "REVIEW_MODE")
        self.assertEqual(trigger["value"], "on")

    def test_missing_value_returns_400(self):
        r = self.client.post("/set", json={"key": "REVIEW_MODE"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# GET /heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat(_Base):

    def test_missing_step_txt_returns_zeros(self):
        d = self.client.get("/heartbeat").get_json()
        self.assertEqual(d["step"], 0)
        self.assertEqual(d["total"], 0)

    def test_parses_step_txt(self):
        self._heartbeat_path.write_text("12,35,70,20,10,5")
        d = self.client.get("/heartbeat").get_json()
        self.assertEqual(d["step"], 12)
        self.assertEqual(d["verified"], 35)
        self.assertEqual(d["total"], 70)
        self.assertEqual(d["pending"], 20)
        self.assertEqual(d["running"], 10)
        self.assertEqual(d["review"], 5)

    def test_malformed_step_txt_returns_zeros(self):
        self._heartbeat_path.write_text("garbage")
        d = self.client.get("/heartbeat").get_json()
        self.assertEqual(d["step"], 0)


class TestHealth(_Base):
    """TASK-097: GET /health liveness probe."""

    def test_returns_200(self):
        self._write_state(self._make_state())
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_ok_is_true(self):
        self._write_state(self._make_state())
        d = self.client.get("/health").get_json()
        self.assertTrue(d["ok"])

    def test_required_fields(self):
        self._write_state(self._make_state())
        d = self.client.get("/health").get_json()
        for key in ("ok", "uptime_s", "step", "state_file_exists"):
            self.assertIn(key, d)

    def test_uptime_s_is_non_negative(self):
        self._write_state(self._make_state())
        d = self.client.get("/health").get_json()
        self.assertGreaterEqual(d["uptime_s"], 0)

    def test_step_reflects_state(self):
        state = self._make_state()
        state["step"] = 42
        self._write_state(state)
        d = self.client.get("/health").get_json()
        self.assertEqual(d["step"], 42)

    def test_state_file_exists_true_when_present(self):
        self._write_state(self._make_state())
        d = self.client.get("/health").get_json()
        self.assertTrue(d["state_file_exists"])

    def test_state_file_exists_false_when_missing(self):
        if self._state_path.exists():
            self._state_path.unlink()
        d = self.client.get("/health").get_json()
        self.assertFalse(d["state_file_exists"])

    def test_ok_true_even_when_state_missing(self):
        if self._state_path.exists():
            self._state_path.unlink()
        d = self.client.get("/health").get_json()
        self.assertTrue(d["ok"])


# ---------------------------------------------------------------------------
# POST /export + GET /export
# ---------------------------------------------------------------------------

class TestExport(_Base):

    def test_post_export_generates_file(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.post("/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Solo Builder", r.data)

    def test_post_export_no_outputs_returns_404(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        # Pending subtasks have output but let's clear them
        state = self._make_state({"A1": "Pending"})
        for t in state["dag"].values():
            for b in t["branches"].values():
                for s in b["subtasks"].values():
                    s["output"] = ""
        self._write_state(state)
        r = self.client.post("/export")
        self.assertEqual(r.status_code, 404)

    def test_get_export_missing_file_returns_404(self):
        r = self.client.get("/export")
        self.assertEqual(r.status_code, 404)

    def test_get_export_serves_existing_file(self):
        self._outputs_path.write_text("# Test", encoding="utf-8")
        r = self.client.get("/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Test", r.data)


# ---------------------------------------------------------------------------
# GET /journal
# ---------------------------------------------------------------------------

class TestJournal(_Base):

    def test_empty_journal_returns_empty(self):
        d = self.client.get("/journal").get_json()
        self.assertEqual(d["entries"], [])

    def test_parses_journal_entries(self):
        self._journal_path.write_text(
            "## A1 \u00b7 Task 0 / Branch A \u00b7 Step 3\n"
            "**Prompt:** test prompt\n\n"
            "Some output text here.\n"
            "---\n",
            encoding="utf-8",
        )
        d = self.client.get("/journal").get_json()
        self.assertEqual(len(d["entries"]), 1)
        self.assertEqual(d["entries"][0]["subtask"], "A1")


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

class TestStats(_Base):

    def test_stats_empty(self):
        r = self.client.get("/stats")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["tasks"], [])
        self.assertEqual(d["grand_total"], 0)

    def test_stats_with_data(self):
        state = self._make_state({"A1": "Verified", "A2": "Pending"})
        # Add history to A1
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["history"] = [{"status": "Running", "step": 1}, {"status": "Verified", "step": 3}]
        self._write_state(state)
        r = self.client.get("/stats")
        d = r.get_json()
        self.assertEqual(len(d["tasks"]), 1)
        self.assertEqual(d["tasks"][0]["verified"], 1)
        self.assertEqual(d["tasks"][0]["total"], 2)
        self.assertEqual(d["tasks"][0]["avg_steps"], 2.0)
        self.assertEqual(d["grand_verified"], 1)


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

class TestSearch(_Base):

    def test_search_missing_query(self):
        r = self.client.get("/search")
        self.assertEqual(r.status_code, 400)

    def test_search_found(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        r = self.client.get("/search?q=A1")
        d = r.get_json()
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["results"][0]["subtask"], "A1")

    def test_search_not_found(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.get("/search?q=zzzz")
        d = r.get_json()
        self.assertEqual(d["count"], 0)


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------

class TestHistory(_Base):

    def test_history_empty(self):
        r = self.client.get("/history")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["events"], [])

    def test_history_response_has_pagination_keys(self):
        r = self.client.get("/history")
        d = r.get_json()
        for key in ("events", "total", "page", "pages"):
            self.assertIn(key, d)

    def test_history_with_events(self):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["history"] = [
            {"status": "Running", "step": 2},
            {"status": "Verified", "step": 4},
        ]
        self._write_state(state)
        r = self.client.get("/history")
        d = r.get_json()
        self.assertEqual(len(d["events"]), 2)
        # Should be sorted descending by step
        self.assertEqual(d["events"][0]["step"], 4)
        self.assertEqual(d["events"][0]["subtask"], "A1")

    def test_history_respects_limit(self):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["history"] = [
            {"status": "Running", "step": 1},
            {"status": "Verified", "step": 2},
        ]
        self._write_state(state)
        r = self.client.get("/history?limit=1")
        d = r.get_json()
        self.assertEqual(len(d["events"]), 1)

    # ?since=S

    def _state_with_history_events(self, steps):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["history"] = [{"status": "Running", "step": s} for s in steps]
        return state

    def test_since_filters_events_after_step(self):
        self._write_state(self._state_with_history_events([1, 2, 3, 4, 5]))
        d = self.client.get("/history?since=3&limit=0").get_json()
        steps = [e["step"] for e in d["events"]]
        self.assertEqual(sorted(steps), [4, 5])

    def test_since_zero_returns_all_events(self):
        self._write_state(self._state_with_history_events([1, 2, 3]))
        d = self.client.get("/history?since=0&limit=0").get_json()
        self.assertEqual(len(d["events"]), 3)

    def test_since_beyond_history_returns_empty(self):
        self._write_state(self._state_with_history_events([1, 2, 3]))
        d = self.client.get("/history?since=99&limit=0").get_json()
        self.assertEqual(d["events"], [])

    def test_since_and_limit_compose(self):
        # steps 1-5; since=2 → [3,4,5]; limit=2 → [5,4] (desc)
        self._write_state(self._state_with_history_events([1, 2, 3, 4, 5]))
        d = self.client.get("/history?since=2&limit=2").get_json()
        self.assertEqual(len(d["events"]), 2)
        self.assertEqual(d["events"][0]["step"], 5)
        self.assertEqual(d["events"][1]["step"], 4)

    def test_limit_zero_returns_all(self):
        self._write_state(self._state_with_history_events([1, 2, 3, 4]))
        d = self.client.get("/history?limit=0").get_json()
        self.assertEqual(len(d["events"]), 4)

    def test_since_result_sorted_descending(self):
        self._write_state(self._state_with_history_events([1, 3, 5, 7]))
        d = self.client.get("/history?since=2&limit=0").get_json()
        steps = [e["step"] for e in d["events"]]
        self.assertEqual(steps, sorted(steps, reverse=True))

    # ?task / ?branch / ?subtask / ?status filters (TASK-059)

    def _state_with_two_subtasks(self):
        state = self._make_state({"A1": "Verified", "A2": "Pending"})
        br = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        br["A1"]["history"] = [{"status": "Verified", "step": 1}]
        br["A2"]["history"] = [{"status": "Running",  "step": 2}]
        return state

    def test_history_filter_subtask(self):
        self._write_state(self._state_with_two_subtasks())
        d = self.client.get("/history?subtask=A1&limit=0").get_json()
        self.assertTrue(all(e["subtask"] == "A1" for e in d["events"]))
        self.assertEqual(len(d["events"]), 1)

    def test_history_filter_status(self):
        self._write_state(self._state_with_two_subtasks())
        d = self.client.get("/history?status=Running&limit=0").get_json()
        self.assertEqual(len(d["events"]), 1)
        self.assertEqual(d["events"][0]["status"], "Running")

    def test_history_filter_case_insensitive(self):
        self._write_state(self._state_with_two_subtasks())
        d = self.client.get("/history?status=running&limit=0").get_json()
        self.assertEqual(len(d["events"]), 1)

    def test_history_filter_task(self):
        self._write_state(self._state_with_two_subtasks())
        d = self.client.get("/history?task=Task+0&limit=0").get_json()
        self.assertEqual(len(d["events"]), 2)

    def test_history_filter_branch(self):
        self._write_state(self._state_with_two_subtasks())
        d = self.client.get("/history?branch=Branch+A&limit=0").get_json()
        self.assertEqual(len(d["events"]), 2)

    def test_history_filter_no_match(self):
        self._write_state(self._state_with_two_subtasks())
        d = self.client.get("/history?subtask=ZZZ&limit=0").get_json()
        self.assertEqual(d["events"], [])

    def test_history_filter_composes_with_since(self):
        self._write_state(self._state_with_two_subtasks())
        # A2 step=2, A1 step=1; since=1 → only step>1 = A2
        d = self.client.get("/history?since=1&limit=0").get_json()
        self.assertEqual(len(d["events"]), 1)
        self.assertEqual(d["events"][0]["subtask"], "A2")

    # ?page=N pagination (TASK-061)

    def test_page_one_returns_first_events(self):
        self._write_state(self._state_with_history_events([1, 2, 3, 4, 5]))
        d = self.client.get("/history?limit=2&page=1").get_json()
        self.assertEqual(len(d["events"]), 2)
        self.assertEqual(d["events"][0]["step"], 5)  # newest first

    def test_page_two_returns_next_events(self):
        self._write_state(self._state_with_history_events([1, 2, 3, 4, 5]))
        d = self.client.get("/history?limit=2&page=2").get_json()
        self.assertEqual(len(d["events"]), 2)
        self.assertEqual(d["events"][0]["step"], 3)

    def test_page_beyond_last_returns_empty(self):
        self._write_state(self._state_with_history_events([1, 2, 3]))
        d = self.client.get("/history?limit=2&page=5").get_json()
        self.assertEqual(d["events"], [])

    def test_page_total_is_all_events(self):
        self._write_state(self._state_with_history_events([1, 2, 3, 4, 5]))
        d = self.client.get("/history?limit=2&page=1").get_json()
        self.assertEqual(d["total"], 5)

    def test_pages_count_is_correct(self):
        self._write_state(self._state_with_history_events([1, 2, 3, 4, 5]))
        d = self.client.get("/history?limit=2&page=1").get_json()
        self.assertEqual(d["pages"], 3)  # ceil(5/2)

    def test_page_defaults_to_one(self):
        self._write_state(self._state_with_history_events([1, 2, 3]))
        d = self.client.get("/history?limit=2").get_json()
        self.assertEqual(d["page"], 1)

    # output field (TASK-074)

    def test_history_event_has_output_field(self):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["history"] = [{"status": "Verified", "step": 1}]
        st["output"] = "hello world"
        self._write_state(state)
        d = self.client.get("/history").get_json()
        self.assertIn("output", d["events"][0])
        self.assertEqual(d["events"][0]["output"], "hello world")

    def test_history_event_output_defaults_to_empty_string(self):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["history"] = [{"status": "Verified", "step": 1}]
        st.pop("output", None)  # remove default so st_data.get("output","") returns ""
        self._write_state(state)
        d = self.client.get("/history").get_json()
        self.assertEqual(d["events"][0]["output"], "")

    def test_history_response_has_review_key(self):
        d = self.client.get("/history").get_json()
        self.assertIn("review", d)

    def test_history_review_count_correct(self):
        state = self._make_state({"A1": "Review", "A2": "Verified"})
        br = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        br["A1"]["history"] = [{"status": "Review", "step": 1}, {"status": "Review", "step": 2}]
        br["A2"]["history"] = [{"status": "Verified", "step": 3}]
        self._write_state(state)
        d = self.client.get("/history?limit=0").get_json()
        self.assertEqual(d["review"], 2)

    def test_history_review_zero_when_none(self):
        state = self._make_state({"A1": "Verified"})
        br = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        br["A1"]["history"] = [{"status": "Verified", "step": 1}]
        self._write_state(state)
        d = self.client.get("/history?limit=0").get_json()
        self.assertEqual(d["review"], 0)


# ---------------------------------------------------------------------------
# GET /history/export
# ---------------------------------------------------------------------------

class TestHistoryExport(_Base):

    def _state_with_steps(self, steps):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["history"] = [{"status": "Running", "step": s} for s in steps]
        return state

    def test_export_csv_status(self):
        self._write_state(self._make_state())
        r = self.client.get("/history/export")
        self.assertEqual(r.status_code, 200)

    def test_export_csv_content_type(self):
        self._write_state(self._make_state())
        r = self.client.get("/history/export")
        self.assertIn("text/csv", r.content_type)

    def test_export_csv_header_row(self):
        self._write_state(self._make_state())
        lines = self.client.get("/history/export").data.decode().strip().splitlines()
        self.assertEqual(lines[0], "step,subtask,task,branch,status")

    def test_export_csv_empty_has_only_header(self):
        self._write_state(self._make_state())
        lines = self.client.get("/history/export").data.decode().strip().splitlines()
        self.assertEqual(len(lines), 1)

    def test_export_csv_rows(self):
        self._write_state(self._state_with_steps([2, 5]))
        lines = self.client.get("/history/export").data.decode().strip().splitlines()
        self.assertEqual(len(lines), 3)  # header + 2 rows

    def test_export_csv_sorted_ascending(self):
        self._write_state(self._state_with_steps([5, 1, 3]))
        lines = self.client.get("/history/export").data.decode().strip().splitlines()
        steps = [int(l.split(",")[0]) for l in lines[1:]]
        self.assertEqual(steps, sorted(steps))

    def test_export_json_status(self):
        self._write_state(self._make_state())
        r = self.client.get("/history/export?format=json")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json(), list)

    def test_export_json_empty_is_list(self):
        self._write_state(self._make_state())
        self.assertEqual(self.client.get("/history/export?format=json").get_json(), [])

    def test_export_json_row_keys(self):
        self._write_state(self._state_with_steps([1]))
        rows = self.client.get("/history/export?format=json").get_json()
        self.assertEqual(len(rows), 1)
        for key in ("step", "subtask", "task", "branch", "status"):
            self.assertIn(key, rows[0])

    def test_export_since_filters(self):
        self._write_state(self._state_with_steps([1, 2, 3, 4, 5]))
        rows = self.client.get("/history/export?format=json&since=3").get_json()
        steps = [r["step"] for r in rows]
        self.assertEqual(sorted(steps), [4, 5])

    def test_export_limit_caps_rows(self):
        self._write_state(self._state_with_steps([1, 2, 3, 4, 5]))
        rows = self.client.get("/history/export?format=json&limit=2").get_json()
        self.assertEqual(len(rows), 2)

    def test_export_since_and_limit_compose(self):
        self._write_state(self._state_with_steps([1, 2, 3, 4, 5]))
        rows = self.client.get("/history/export?format=json&since=1&limit=2").get_json()
        steps = [r["step"] for r in rows]
        self.assertEqual(steps, [4, 5])

    def test_export_disposition(self):
        self._write_state(self._make_state())
        r = self.client.get("/history/export")
        self.assertIn("history.csv", r.headers.get("Content-Disposition", ""))

    # ?subtask / ?status / ?task filter params (TASK-055)

    def _state_with_mixed_history(self):
        state = self._make_state({"A1": "Verified", "A2": "Pending"})
        br = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        br["A1"]["history"] = [{"status": "Running", "step": 1}, {"status": "Verified", "step": 3}]
        br["A2"]["history"] = [{"status": "Pending", "step": 2}]
        return state

    def test_export_filter_subtask(self):
        self._write_state(self._state_with_mixed_history())
        rows = self.client.get("/history/export?format=json&subtask=A1").get_json()
        self.assertTrue(all(r["subtask"] == "A1" for r in rows))
        self.assertEqual(len(rows), 2)

    def test_export_filter_status(self):
        self._write_state(self._state_with_mixed_history())
        rows = self.client.get("/history/export?format=json&status=Running").get_json()
        self.assertTrue(all(r["status"] == "Running" for r in rows))
        self.assertEqual(len(rows), 1)

    def test_export_filter_case_insensitive(self):
        self._write_state(self._state_with_mixed_history())
        rows = self.client.get("/history/export?format=json&status=running").get_json()
        self.assertEqual(len(rows), 1)

    def test_export_filter_no_match_returns_empty(self):
        self._write_state(self._state_with_mixed_history())
        rows = self.client.get("/history/export?format=json&subtask=ZZZ").get_json()
        self.assertEqual(rows, [])

    def test_export_filter_and_since_compose(self):
        self._write_state(self._state_with_mixed_history())
        rows = self.client.get("/history/export?format=json&subtask=A1&since=1").get_json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["step"], 3)

    def test_export_csv_with_filter(self):
        self._write_state(self._state_with_mixed_history())
        r = self.client.get("/history/export?subtask=A2")
        lines = r.data.decode().strip().splitlines()
        self.assertEqual(len(lines), 2)  # header + 1 row

    # ?branch= filter (TASK-249)

    def _state_two_branches(self):
        """State with two branches, each with one subtask with history."""
        return {
            "step": 5,
            "dag": {
                "Task 0": {
                    "status": "Running", "depends_on": [],
                    "branches": {
                        "Branch A": {"subtasks": {"A1": {
                            "status": "Verified", "output": "", "description": "",
                            "history": [{"status": "Running", "step": 1},
                                        {"status": "Verified", "step": 2}],
                        }}},
                        "Branch B": {"subtasks": {"B1": {
                            "status": "Pending", "output": "", "description": "",
                            "history": [{"status": "Pending", "step": 3}],
                        }}},
                    },
                }
            },
        }

    def test_export_filter_branch_match(self):
        self._write_state(self._state_two_branches())
        rows = self.client.get("/history/export?format=json&branch=Branch+A").get_json()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["branch"] == "Branch A" for r in rows))

    def test_export_filter_branch_no_match(self):
        self._write_state(self._state_two_branches())
        rows = self.client.get("/history/export?format=json&branch=ZZZ").get_json()
        self.assertEqual(rows, [])

    def test_export_filter_branch_case_insensitive(self):
        self._write_state(self._state_two_branches())
        rows = self.client.get("/history/export?format=json&branch=branch+a").get_json()
        self.assertEqual(len(rows), 2)

    def test_export_filter_branch_and_status_compose(self):
        self._write_state(self._state_two_branches())
        rows = self.client.get(
            "/history/export?format=json&branch=Branch+A&status=Running").get_json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "Running")

    def test_export_csv_branch_filter(self):
        self._write_state(self._state_two_branches())
        r = self.client.get("/history/export?branch=Branch+B")
        lines = r.data.decode().strip().splitlines()
        self.assertEqual(len(lines), 2)  # header + 1 row


# ---------------------------------------------------------------------------
# GET /cache/export
# ---------------------------------------------------------------------------

class TestCacheExport(_Base):

    def _write_stats_n(self, n):
        import json as _json
        sessions = [{"hits": i, "misses": 1, "cumulative_hits": i, "cumulative_misses": 1, "ended_at": f"t{i}"}
                    for i in range(1, n + 1)]
        (self._cache_dir / "session_stats.json").write_text(
            _json.dumps({"cumulative_hits": n, "cumulative_misses": n, "sessions": sessions}),
            encoding="utf-8"
        )

    def test_export_csv_status(self):
        r = self.client.get("/cache/export")
        self.assertEqual(r.status_code, 200)

    def test_export_csv_content_type(self):
        r = self.client.get("/cache/export")
        self.assertIn("text/csv", r.content_type)

    def test_export_csv_disposition(self):
        r = self.client.get("/cache/export")
        self.assertIn("cache.csv", r.headers.get("Content-Disposition", ""))

    def test_export_csv_header(self):
        lines = self.client.get("/cache/export").data.decode().strip().splitlines()
        self.assertEqual(lines[0], "session,hits,misses,hit_rate,cumulative_hits,cumulative_misses,ended_at")

    def test_export_csv_empty_has_only_header(self):
        lines = self.client.get("/cache/export").data.decode().strip().splitlines()
        self.assertEqual(len(lines), 1)

    def test_export_csv_rows(self):
        self._write_stats_n(3)
        lines = self.client.get("/cache/export").data.decode().strip().splitlines()
        self.assertEqual(len(lines), 4)  # header + 3 rows

    def test_export_json_status(self):
        r = self.client.get("/cache/export?format=json")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json(), list)

    def test_export_json_empty_is_list(self):
        self.assertEqual(self.client.get("/cache/export?format=json").get_json(), [])

    def test_export_json_row_keys(self):
        self._write_stats_n(1)
        rows = self.client.get("/cache/export?format=json").get_json()
        for key in ("session", "hits", "misses", "hit_rate", "cumulative_hits", "cumulative_misses", "ended_at"):
            self.assertIn(key, rows[0])

    def test_export_since_filters(self):
        self._write_stats_n(5)
        rows = self.client.get("/cache/export?format=json&since=3").get_json()
        nums = [r["session"] for r in rows]
        self.assertEqual(nums, [4, 5])

    def test_export_limit_caps_rows(self):
        self._write_stats_n(5)
        rows = self.client.get("/cache/export?format=json&limit=2").get_json()
        self.assertEqual(len(rows), 2)

    def test_export_since_and_limit_compose(self):
        self._write_stats_n(5)
        rows = self.client.get("/cache/export?format=json&since=1&limit=2").get_json()
        nums = [r["session"] for r in rows]
        self.assertEqual(nums, [4, 5])


# ---------------------------------------------------------------------------
# GET /diff
# ---------------------------------------------------------------------------

class TestDiff(_Base):

    def test_diff_no_backup_returns_empty(self):
        self._write_state(self._make_state())
        r = self.client.get("/diff")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["changes"], [])
        self.assertIn("message", d)

    def test_diff_with_changes(self):
        # Write backup (.1) with A1=Pending
        backup = self._make_state({"A1": "Pending", "A2": "Pending"}, step=3)
        backup_path = Path(str(self._state_path) + ".1")
        backup_path.write_text(json.dumps(backup), encoding="utf-8")
        # Write current state with A1=Verified
        current = self._make_state({"A1": "Verified", "A2": "Pending"}, step=5)
        self._write_state(current)
        r = self.client.get("/diff")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(len(d["changes"]), 1)
        self.assertEqual(d["changes"][0]["subtask"], "A1")
        self.assertEqual(d["changes"][0]["old_status"], "Pending")
        self.assertEqual(d["changes"][0]["new_status"], "Verified")
        self.assertEqual(d["old_step"], 3)
        self.assertEqual(d["new_step"], 5)

    def test_diff_no_changes(self):
        state = self._make_state({"A1": "Verified"}, step=4)
        backup_path = Path(str(self._state_path) + ".1")
        backup_path.write_text(json.dumps(state), encoding="utf-8")
        self._write_state(state)
        r = self.client.get("/diff")
        d = r.get_json()
        self.assertEqual(d["changes"], [])


class TestDagDiff(_Base):
    """TASK-102: GET /dag/diff compares subtask status between step indices."""

    def _make_state_with_history(self):
        state = self._make_state()
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        st["A1"]["history"] = [
            {"step": 1, "status": "Running"},
            {"step": 3, "status": "Verified"},
        ]
        st["A2"]["history"] = [
            {"step": 2, "status": "Running"},
        ]
        return state

    def test_missing_from_returns_400(self):
        self._write_state(self._make_state())
        r = self.client.get("/dag/diff")
        self.assertEqual(r.status_code, 400)

    def test_no_changes_same_step(self):
        self._write_state(self._make_state_with_history())
        d = self.client.get("/dag/diff?from=3&to=3").get_json()
        self.assertEqual(d["changes"], [])

    def test_detects_status_change(self):
        self._write_state(self._make_state_with_history())
        d = self.client.get("/dag/diff?from=0&to=3").get_json()
        names = [c["subtask"] for c in d["changes"]]
        self.assertIn("A1", names)

    def test_change_fields(self):
        self._write_state(self._make_state_with_history())
        d = self.client.get("/dag/diff?from=0&to=3").get_json()
        change = next(c for c in d["changes"] if c["subtask"] == "A1")
        self.assertIn("from_status", change)
        self.assertIn("to_status", change)
        self.assertEqual(change["to_status"], "Verified")

    def test_returns_from_to_count(self):
        self._write_state(self._make_state_with_history())
        d = self.client.get("/dag/diff?from=0&to=5").get_json()
        self.assertEqual(d["from"], 0)
        self.assertEqual(d["to"], 5)
        self.assertIn("count", d)


# ---------------------------------------------------------------------------
# GET /branches/<task>
# ---------------------------------------------------------------------------

class TestBranches(_Base):

    def test_branches_found(self):
        state = self._make_state({"A1": "Verified", "A2": "Running"})
        self._write_state(state)
        r = self.client.get("/branches/Task 0")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["task"], "Task 0")
        self.assertEqual(d["branch_count"], 1)
        br = d["branches"][0]
        self.assertEqual(br["branch"], "Branch A")
        self.assertEqual(br["verified"], 1)
        self.assertEqual(br["running"], 1)

    def test_branches_not_found(self):
        self._write_state(self._make_state())
        r = self.client.get("/branches/Task 99")
        self.assertEqual(r.status_code, 404)

    def test_branches_subtask_list(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        r = self.client.get("/branches/Task 0")
        d = r.get_json()
        subs = d["branches"][0]["subtasks"]
        self.assertTrue(any(s["name"] == "A1" for s in subs))


# ---------------------------------------------------------------------------
# GET /branches  (TASK-085)
# ---------------------------------------------------------------------------

class TestBranchesAll(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/branches")
        self.assertEqual(r.status_code, 200)

    def test_response_has_branches_and_count(self):
        self._write_state(self._make_state())
        d = self.client.get("/branches").get_json()
        self.assertIn("branches", d)
        self.assertIn("count", d)

    def test_each_branch_has_required_fields(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/branches").get_json()
        self.assertGreater(len(d["branches"]), 0)
        br = d["branches"][0]
        for key in ("task", "branch", "total", "verified", "running", "pending", "pct"):
            self.assertIn(key, br)

    def test_counts_are_correct(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}))
        d = self.client.get("/branches").get_json()
        br = d["branches"][0]
        self.assertEqual(br["verified"], 1)
        self.assertEqual(br["running"], 1)
        self.assertEqual(br["pending"], 1)
        self.assertEqual(br["total"], 3)

    def test_task_filter(self):
        self._write_state(self._make_state())
        d = self.client.get("/branches?task=Task+0").get_json()
        self.assertTrue(all(b["task"] == "Task 0" for b in d["branches"]))

    def test_task_filter_no_match(self):
        self._write_state(self._make_state())
        d = self.client.get("/branches?task=ZZZ").get_json()
        self.assertEqual(d["branches"], [])
        self.assertEqual(d["count"], 0)

    def test_pct_calculated(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/branches").get_json()
        br = d["branches"][0]
        self.assertEqual(br["pct"], 50.0)

    def test_empty_state_returns_empty(self):
        state = {"step": 0, "dag": {}}
        self._write_state(state)
        d = self.client.get("/branches").get_json()
        self.assertEqual(d["branches"], [])

    def test_review_field_present(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Pending"}))
        d = self.client.get("/branches").get_json()
        br = d["branches"][0]
        self.assertIn("review", br)
        self.assertEqual(br["review"], 1)
        self.assertEqual(br["pending"], 1)

    def test_review_not_counted_in_pending(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Pending", "A3": "Verified"}))
        d = self.client.get("/branches").get_json()
        br = d["branches"][0]
        self.assertEqual(br["verified"] + br["running"] + br["review"] + br["pending"], br["total"])

    def test_pagination_keys_present(self):
        self._write_state(self._make_state())
        d = self.client.get("/branches").get_json()
        for key in ("total", "page", "pages"):
            self.assertIn(key, d)

    def _multi_branch_state(self, n):
        dag = {}
        for i in range(n):
            dag[f"Task {i}"] = {"status": "Pending", "depends_on": [],
                                 "branches": {f"Br {i}": {"subtasks": {f"S{i}": {"status": "Pending"}}}}}
        return {"step": 0, "dag": dag}

    def test_limit_restricts_branches(self):
        self._write_state(self._multi_branch_state(5))
        d = self.client.get("/branches?limit=2").get_json()
        self.assertEqual(len(d["branches"]), 2)
        self.assertEqual(d["total"], 5)
        self.assertEqual(d["pages"], 3)

    def test_pages_disjoint(self):
        self._write_state(self._multi_branch_state(4))
        d1 = self.client.get("/branches?limit=2&page=1").get_json()
        d2 = self.client.get("/branches?limit=2&page=2").get_json()
        names1 = {b["branch"] for b in d1["branches"]}
        names2 = {b["branch"] for b in d2["branches"]}
        self.assertTrue(names1.isdisjoint(names2))

    # ?status= server-side filter (TASK-253)

    def _multi_status_state(self):
        """State with 4 branches: one fully-verified, one running, one review, one pending."""
        return {
            "step": 0,
            "dag": {
                "Task 0": {"status": "Running", "depends_on": [], "branches": {
                    "BrV": {"subtasks": {"S1": {"status": "Verified"}}},
                    "BrR": {"subtasks": {"S2": {"status": "Running"}}},
                    "BrW": {"subtasks": {"S3": {"status": "Review"}}},
                    "BrP": {"subtasks": {"S4": {"status": "Pending"}}},
                }}
            },
        }

    def test_status_filter_verified(self):
        self._write_state(self._multi_status_state())
        d = self.client.get("/branches?status=verified").get_json()
        names = [b["branch"] for b in d["branches"]]
        self.assertEqual(names, ["BrV"])

    def test_status_filter_running(self):
        self._write_state(self._multi_status_state())
        d = self.client.get("/branches?status=running").get_json()
        names = [b["branch"] for b in d["branches"]]
        self.assertEqual(names, ["BrR"])

    def test_status_filter_review(self):
        self._write_state(self._multi_status_state())
        d = self.client.get("/branches?status=review").get_json()
        names = [b["branch"] for b in d["branches"]]
        self.assertEqual(names, ["BrW"])

    def test_status_filter_pending(self):
        self._write_state(self._multi_status_state())
        d = self.client.get("/branches?status=pending").get_json()
        names = [b["branch"] for b in d["branches"]]
        self.assertEqual(names, ["BrP"])

    def test_status_filter_no_match_returns_empty(self):
        # All branches fully-verified; running filter → empty
        state = {"step": 0, "dag": {"Task 0": {"status": "Running", "depends_on": [],
            "branches": {"BrV": {"subtasks": {"S1": {"status": "Verified"}}}}}}}
        self._write_state(state)
        d = self.client.get("/branches?status=running").get_json()
        self.assertEqual(d["branches"], [])
        self.assertEqual(d["total"], 0)

    def test_status_filter_composes_with_pagination(self):
        # 3 running branches; limit=2 → page 1 has 2, total=3
        dag = {"Task 0": {"status": "Running", "depends_on": [], "branches": {
            f"Br{i}": {"subtasks": {f"S{i}": {"status": "Running"}}} for i in range(3)
        }}}
        self._write_state({"step": 0, "dag": dag})
        d = self.client.get("/branches?status=running&limit=2&page=1").get_json()
        self.assertEqual(len(d["branches"]), 2)
        self.assertEqual(d["total"], 3)


# GET /branches/export  (TASK-258)
# ---------------------------------------------------------------------------

class TestBranchesExport(_Base):

    def _two_branch_state(self):
        return {
            "step": 0,
            "dag": {
                "Task 0": {"status": "Running", "depends_on": [], "branches": {
                    "Br A": {"subtasks": {"S1": {"status": "Verified"}, "S2": {"status": "Verified"}}},
                    "Br B": {"subtasks": {"S3": {"status": "Running"}, "S4": {"status": "Pending"}}},
                }},
            },
        }

    def test_export_csv_status(self):
        self._write_state(self._two_branch_state())
        r = self.client.get("/branches/export")
        self.assertEqual(r.status_code, 200)

    def test_export_csv_content_type(self):
        self._write_state(self._two_branch_state())
        r = self.client.get("/branches/export")
        self.assertIn("text/csv", r.content_type)

    def test_export_csv_disposition(self):
        self._write_state(self._two_branch_state())
        r = self.client.get("/branches/export")
        self.assertIn("branches.csv", r.headers.get("Content-Disposition", ""))

    def test_export_csv_header_row(self):
        self._write_state(self._two_branch_state())
        lines = self.client.get("/branches/export").data.decode().strip().splitlines()
        self.assertEqual(lines[0], "task,branch,total,verified,running,review,pending,pct")

    def test_export_csv_row_count(self):
        self._write_state(self._two_branch_state())
        lines = self.client.get("/branches/export").data.decode().strip().splitlines()
        self.assertEqual(len(lines), 3)  # header + 2 branches

    def test_export_json_status(self):
        self._write_state(self._two_branch_state())
        r = self.client.get("/branches/export?format=json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/json", r.content_type)

    def test_export_json_disposition(self):
        self._write_state(self._two_branch_state())
        r = self.client.get("/branches/export?format=json")
        self.assertIn("branches.json", r.headers.get("Content-Disposition", ""))

    def test_export_json_has_branches_key(self):
        self._write_state(self._two_branch_state())
        d = self.client.get("/branches/export?format=json").get_json()
        self.assertIn("branches", d)
        self.assertIn("total", d)
        self.assertEqual(d["total"], 2)

    def test_export_json_row_fields(self):
        self._write_state(self._two_branch_state())
        rows = self.client.get("/branches/export?format=json").get_json()["branches"]
        for key in ("task", "branch", "total", "verified", "running", "review", "pending", "pct"):
            self.assertIn(key, rows[0])

    def test_export_status_filter_verified(self):
        self._write_state(self._two_branch_state())
        rows = self.client.get("/branches/export?format=json&status=verified").get_json()["branches"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["branch"], "Br A")

    def test_export_status_filter_running(self):
        self._write_state(self._two_branch_state())
        rows = self.client.get("/branches/export?format=json&status=running").get_json()["branches"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["branch"], "Br B")

    def test_export_task_filter(self):
        self._write_state(self._two_branch_state())
        rows = self.client.get("/branches/export?format=json&task=Task+0").get_json()["branches"]
        self.assertEqual(len(rows), 2)

    def test_export_task_filter_no_match(self):
        self._write_state(self._two_branch_state())
        rows = self.client.get("/branches/export?format=json&task=ZZZ").get_json()["branches"]
        self.assertEqual(rows, [])

    def test_export_empty_state_csv(self):
        self._write_state({"step": 0, "dag": {}})
        lines = self.client.get("/branches/export").data.decode().strip().splitlines()
        self.assertEqual(len(lines), 1)  # header only


# POST /branches/<task>/reset
# ---------------------------------------------------------------------------

class TestBranchReset(_Base):

    def test_reset_valid_branch_returns_ok(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        r = self.client.post("/branches/Task 0/reset",
                             json={"branch": "Branch A"})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["task"], "Task 0")
        self.assertEqual(d["branch"], "Branch A")

    def test_reset_missing_branch_field_returns_400(self):
        self._write_state(self._make_state())
        r = self.client.post("/branches/Task 0/reset", json={})
        self.assertEqual(r.status_code, 400)

    def test_reset_invalid_task_returns_404(self):
        self._write_state(self._make_state())
        r = self.client.post("/branches/Task 999/reset",
                             json={"branch": "Branch A"})
        self.assertEqual(r.status_code, 404)

    def test_reset_invalid_branch_returns_404(self):
        self._write_state(self._make_state())
        r = self.client.post("/branches/Task 0/reset",
                             json={"branch": "Branch ZZZ"})
        self.assertEqual(r.status_code, 404)

    def test_reset_counts_reset_subtasks(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/branches/Task 0/reset",
                             json={"branch": "Branch A"}).get_json()
        self.assertEqual(d["reset_count"], 2)

    def test_reset_skips_verified(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.post("/branches/Task 0/reset",
                             json={"branch": "Branch A"}).get_json()
        self.assertEqual(d["reset_count"], 1)
        self.assertEqual(d["skipped_count"], 1)

    def test_reset_sets_subtasks_to_pending(self):
        self._write_state(self._make_state({"A1": "Running"}))
        self.client.post("/branches/Task 0/reset", json={"branch": "Branch A"})
        state = json.loads(self._state_path.read_text())
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Pending")


# ---------------------------------------------------------------------------
# GET /subtasks  (TASK-087)
# ---------------------------------------------------------------------------

class TestSubtasksAll(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/subtasks")
        self.assertEqual(r.status_code, 200)

    def test_response_has_subtasks_and_count(self):
        self._write_state(self._make_state())
        d = self.client.get("/subtasks").get_json()
        self.assertIn("subtasks", d)
        self.assertIn("count", d)

    def test_each_subtask_has_required_fields(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks").get_json()
        self.assertGreater(len(d["subtasks"]), 0)
        st = d["subtasks"][0]
        for key in ("subtask", "task", "branch", "status", "output_length"):
            self.assertIn(key, st)

    def test_output_not_included_by_default(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks").get_json()
        self.assertNotIn("output", d["subtasks"][0])

    def test_output_included_with_param(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks?output=1").get_json()
        self.assertIn("output", d["subtasks"][0])

    def test_status_filter(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}))
        d = self.client.get("/subtasks?status=Verified").get_json()
        self.assertTrue(all(s["status"] == "Verified" for s in d["subtasks"]))

    def test_task_filter(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks?task=Task+0").get_json()
        self.assertTrue(all(s["task"] == "Task 0" for s in d["subtasks"]))

    def test_task_filter_no_match(self):
        self._write_state(self._make_state())
        d = self.client.get("/subtasks?task=ZZZ").get_json()
        self.assertEqual(d["subtasks"], [])

    def test_branch_filter(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks?branch=Branch+A").get_json()
        self.assertTrue(all(s["branch"] == "Branch A" for s in d["subtasks"]))

    def test_output_length_reflects_content(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = "hello"
        self._write_state(state)
        d = self.client.get("/subtasks").get_json()
        st = next(s for s in d["subtasks"] if s["subtask"] == "A1")
        self.assertEqual(st["output_length"], 5)

    # ?name= filter (TASK-251)

    def test_name_filter_exact_match(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/subtasks?name=A1").get_json()
        names = [s["subtask"] for s in d["subtasks"]]
        self.assertEqual(names, ["A1"])

    def test_name_filter_substring_match(self):
        self._write_state(self._make_state({"Alpha": "Pending", "Beta": "Pending"}))
        d = self.client.get("/subtasks?name=lph").get_json()
        names = [s["subtask"] for s in d["subtasks"]]
        self.assertIn("Alpha", names)
        self.assertNotIn("Beta", names)

    def test_name_filter_no_match_returns_empty(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks?name=ZZZ").get_json()
        self.assertEqual(d["subtasks"], [])

    def test_name_filter_case_insensitive(self):
        self._write_state(self._make_state({"Alpha": "Pending"}))
        d = self.client.get("/subtasks?name=alpha").get_json()
        names = [s["subtask"] for s in d["subtasks"]]
        self.assertIn("Alpha", names)

    def test_name_filter_composes_with_status(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified"}))
        d = self.client.get("/subtasks?name=A1&status=Verified").get_json()
        names = [s["subtask"] for s in d["subtasks"]]
        self.assertEqual(names, ["A1"])


# ---------------------------------------------------------------------------
# GET /subtasks — pagination (TASK-138)
# ---------------------------------------------------------------------------

class TestSubtasksPagination(_Base):

    def _state_with_n(self, n):
        """State with n subtasks: A1..An all Pending."""
        subtasks = {f"A{i}": {"status": "Pending", "output": "", "last_update": 0}
                    for i in range(1, n + 1)}
        state = {"dag": {"Task 0": {"status": "Pending", "branches": {
            "Branch A": {"status": "Pending", "subtasks": subtasks}
        }}}, "step": 0}
        return state

    def test_no_pagination_returns_all(self):
        self._write_state(self._state_with_n(5))
        d = self.client.get("/subtasks").get_json()
        self.assertEqual(d["total"], 5)
        self.assertEqual(d["count"], 5)

    def test_limit_returns_page_slice(self):
        self._write_state(self._state_with_n(10))
        d = self.client.get("/subtasks?limit=3&page=1").get_json()
        self.assertEqual(d["count"], 3)
        self.assertEqual(d["total"], 10)

    def test_page_2_returns_next_slice(self):
        self._write_state(self._state_with_n(10))
        d = self.client.get("/subtasks?limit=3&page=2").get_json()
        self.assertEqual(d["count"], 3)

    def test_last_page_returns_remainder(self):
        self._write_state(self._state_with_n(7))
        d = self.client.get("/subtasks?limit=3&page=3").get_json()
        self.assertEqual(d["count"], 1)

    def test_pages_field_correct(self):
        self._write_state(self._state_with_n(10))
        d = self.client.get("/subtasks?limit=3").get_json()
        self.assertEqual(d["pages"], 4)  # ceil(10/3)

    def test_no_limit_pages_is_one(self):
        self._write_state(self._state_with_n(5))
        d = self.client.get("/subtasks").get_json()
        self.assertEqual(d["pages"], 1)

    def test_invalid_limit_treated_as_zero(self):
        self._write_state(self._state_with_n(5))
        d = self.client.get("/subtasks?limit=abc").get_json()
        self.assertEqual(d["count"], 5)

    def test_response_has_page_and_limit_fields(self):
        self._write_state(self._state_with_n(5))
        d = self.client.get("/subtasks?limit=2&page=1").get_json()
        self.assertIn("page", d)
        self.assertIn("limit", d)

    def test_pages_disjoint(self):
        self._write_state(self._state_with_n(6))
        d1 = self.client.get("/subtasks?limit=3&page=1").get_json()
        d2 = self.client.get("/subtasks?limit=3&page=2").get_json()
        names1 = {s["subtask"] for s in d1["subtasks"]}
        names2 = {s["subtask"] for s in d2["subtasks"]}
        self.assertTrue(names1.isdisjoint(names2))
        self.assertEqual(len(names1) + len(names2), 6)


# ---------------------------------------------------------------------------
# GET /subtasks/export  (TASK-088)
# ---------------------------------------------------------------------------

class TestSubtasksExport(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/subtasks/export")
        self.assertEqual(r.status_code, 200)

    def test_default_is_csv(self):
        self._write_state(self._make_state())
        r = self.client.get("/subtasks/export")
        self.assertIn("text/csv", r.content_type)

    def test_csv_has_header(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.get("/subtasks/export")
        text = r.data.decode("utf-8")
        self.assertIn("subtask", text)
        self.assertIn("status", text)

    def test_json_format(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.get("/subtasks/export?format=json")
        self.assertIn("application/json", r.content_type)
        d = r.get_json()
        self.assertIn("subtasks", d)
        self.assertIsInstance(d["subtasks"], list)

    def test_json_has_required_fields(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks/export?format=json").get_json()["subtasks"]
        self.assertGreater(len(d), 0)
        row = d[0]
        for key in ("subtask", "task", "branch", "status", "output_length"):
            self.assertIn(key, row)

    def test_status_filter(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/subtasks/export?format=json&status=Verified").get_json()["subtasks"]
        self.assertTrue(all(r["status"] == "Verified" for r in d))

    def test_task_filter(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks/export?format=json&task=Task+0").get_json()["subtasks"]
        self.assertTrue(all(r["task"] == "Task 0" for r in d))

    def test_branch_filter(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks/export?format=json&branch=Branch+A").get_json()["subtasks"]
        self.assertTrue(all(r["branch"] == "Branch A" for r in d))

    def test_attachment_header_csv(self):
        self._write_state(self._make_state())
        r = self.client.get("/subtasks/export")
        self.assertIn("subtasks.csv", r.headers.get("Content-Disposition", ""))

    def test_attachment_header_json(self):
        self._write_state(self._make_state())
        r = self.client.get("/subtasks/export?format=json")
        self.assertIn("subtasks.json", r.headers.get("Content-Disposition", ""))

    # ?name= filter (TASK-251)

    def test_export_name_filter_match(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/subtasks/export?format=json&name=A1").get_json()["subtasks"]
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["subtask"], "A1")

    def test_export_name_filter_no_match(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/subtasks/export?format=json&name=ZZZ").get_json()["subtasks"]
        self.assertEqual(d, [])

    def test_export_name_filter_case_insensitive(self):
        self._write_state(self._make_state({"Alpha": "Pending"}))
        d = self.client.get("/subtasks/export?format=json&name=alpha").get_json()["subtasks"]
        self.assertEqual(len(d), 1)

    def test_export_csv_name_filter(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        r = self.client.get("/subtasks/export?name=A2")
        lines = r.data.decode().strip().splitlines()
        self.assertEqual(len(lines), 2)  # header + 1 row

    def test_export_name_and_status_compose(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/subtasks/export?format=json&name=A&status=Running").get_json()["subtasks"]
        names = [r["subtask"] for r in d]
        self.assertIn("A2", names)
        self.assertNotIn("A1", names)


# ---------------------------------------------------------------------------
# GET /subtasks/export pagination  (TASK-142)
# ---------------------------------------------------------------------------

class TestSubtasksExportPagination(_Base):

    def _state_with_n(self, n):
        subtasks = {f"A{i}": {"status": "Pending", "output": "", "last_update": 0}
                    for i in range(1, n + 1)}
        state = {"dag": {"Task 0": {"status": "Pending", "branches": {
            "Branch A": {"status": "Pending", "subtasks": subtasks}
        }}}, "step": 0}
        return state

    def test_csv_no_pagination_returns_all(self):
        self._write_state(self._state_with_n(5))
        r = self.client.get("/subtasks/export")
        lines = r.data.decode().strip().split("\n")
        self.assertEqual(len(lines), 6)  # header + 5 rows

    def test_csv_limit_returns_slice(self):
        self._write_state(self._state_with_n(10))
        r = self.client.get("/subtasks/export?limit=3&page=1")
        lines = r.data.decode().strip().split("\n")
        self.assertEqual(len(lines), 4)  # header + 3 rows

    def test_json_no_pagination_has_subtasks_list(self):
        self._write_state(self._state_with_n(5))
        d = self.client.get("/subtasks/export?format=json").get_json()
        self.assertIn("subtasks", d)
        self.assertEqual(len(d["subtasks"]), 5)

    def test_json_pagination_total_and_pages(self):
        self._write_state(self._state_with_n(10))
        d = self.client.get("/subtasks/export?format=json&limit=3&page=1").get_json()
        self.assertEqual(d["total"], 10)
        self.assertEqual(d["pages"], 4)
        self.assertEqual(len(d["subtasks"]), 3)

    def test_json_page_2(self):
        self._write_state(self._state_with_n(10))
        d = self.client.get("/subtasks/export?format=json&limit=3&page=2").get_json()
        self.assertEqual(len(d["subtasks"]), 3)
        self.assertEqual(d["page"], 2)

    def test_invalid_limit_falls_back_to_all(self):
        self._write_state(self._state_with_n(5))
        d = self.client.get("/subtasks/export?format=json&limit=abc").get_json()
        self.assertEqual(len(d["subtasks"]), 5)


# ---------------------------------------------------------------------------
# GET /timeline enhanced  (TASK-090)
# ---------------------------------------------------------------------------

class TestTimelineEnhanced(_Base):

    def test_timeline_has_last_update(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["last_update"] = 7
        self._write_state(state)
        d = self.client.get("/timeline/A1").get_json()
        self.assertIn("last_update", d)
        self.assertEqual(d["last_update"], 7)

    def test_timeline_last_update_none_when_absent(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"].pop("last_update", None)
        self._write_state(state)
        d = self.client.get("/timeline/A1").get_json()
        self.assertIn("last_update", d)
        self.assertIsNone(d["last_update"])


# ---------------------------------------------------------------------------
# POST /rename
# ---------------------------------------------------------------------------

class TestRename(_Base):

    def test_rename_writes_trigger(self):
        r = self.client.post("/rename", json={"subtask": "A1", "desc": "New description"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["subtask"], "A1")

    def test_rename_missing_subtask(self):
        r = self.client.post("/rename", json={"desc": "New description"})
        self.assertEqual(r.status_code, 400)

    def test_rename_missing_desc(self):
        r = self.client.post("/rename", json={"subtask": "A1"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# GET /timeline/<subtask>
# ---------------------------------------------------------------------------

class TestTimeline(_Base):

    def test_timeline_found(self):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["description"] = "Test the auth module"
        st["output"] = "Auth module tested OK"
        st["history"] = [
            {"status": "Running", "step": 1},
            {"status": "Verified", "step": 3},
        ]
        self._write_state(state)
        r = self.client.get("/timeline/A1")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["subtask"], "A1")
        self.assertEqual(d["task"], "Task 0")
        self.assertEqual(d["status"], "Verified")
        self.assertEqual(len(d["history"]), 2)
        self.assertEqual(d["description"], "Test the auth module")
        self.assertEqual(d["output"], "Auth module tested OK")

    def test_timeline_not_found(self):
        self._write_state(self._make_state())
        r = self.client.get("/timeline/ZZZZ")
        self.assertEqual(r.status_code, 404)

    def test_timeline_case_insensitive(self):
        self._write_state(self._make_state({"A1": "Running"}))
        r = self.client.get("/timeline/a1")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["subtask"], "A1")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig(_Base):

    def test_returns_settings(self):
        r = self.client.get("/config")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIsInstance(d, dict)

    def test_has_expected_keys(self):
        r = self.client.get("/config")
        d = r.get_json()
        self.assertIn("STALL_THRESHOLD", d)
        self.assertIn("EXECUTOR_VERIFY_PROBABILITY", d)

    def test_post_updates_setting(self):
        r = self.client.post("/config", json={"STALL_THRESHOLD": 99})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("ok"))
        self.assertEqual(d.get("STALL_THRESHOLD"), 99)

    def test_post_unknown_key_rejected(self):
        r = self.client.post("/config", json={"BOGUS_KEY_XYZ": 1})
        self.assertEqual(r.status_code, 400)
        d = r.get_json()
        self.assertIn("Unknown key", d.get("reason", ""))

    def test_post_empty_body_rejected(self):
        r = self.client.post("/config", json={})
        self.assertEqual(r.status_code, 400)


class TestConfigReset(_Base):
    """TASK-095: POST /config/reset restores compiled-in defaults."""

    def test_returns_200_and_ok(self):
        r = self.client.post("/config/reset")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("ok"))
        self.assertTrue(d.get("restored"))

    def test_config_key_in_response(self):
        d = self.client.post("/config/reset").get_json()
        self.assertIn("config", d)
        self.assertIn("STALL_THRESHOLD", d["config"])

    def test_defaults_written_to_settings(self):
        # Change a value, then reset, then read back
        self.client.post("/config", json={"STALL_THRESHOLD": 99})
        self.client.post("/config/reset")
        d = self.client.get("/config").get_json()
        self.assertEqual(d.get("STALL_THRESHOLD"), 5)

    def test_missing_settings_file_returns_409(self):
        import os
        backup = self._settings_path.read_bytes()
        self._settings_path.unlink()
        try:
            r = self.client.post("/config/reset")
            self.assertEqual(r.status_code, 409)
        finally:
            self._settings_path.write_bytes(backup)


class TestConfigExport(_Base):
    """TASK-124: GET /config/export downloads settings.json as attachment."""

    def test_returns_200(self):
        r = self.client.get("/config/export")
        self.assertEqual(r.status_code, 200)

    def test_content_disposition_attachment(self):
        r = self.client.get("/config/export")
        cd = r.headers.get("Content-Disposition", "")
        self.assertIn("attachment", cd)
        self.assertIn("settings.json", cd)

    def test_content_type_json(self):
        r = self.client.get("/config/export")
        self.assertIn("application/json", r.content_type)

    def test_body_is_valid_json(self):
        import json as _json
        r = self.client.get("/config/export")
        d = _json.loads(r.data)
        self.assertIsInstance(d, dict)

    def test_missing_settings_returns_404(self):
        backup = self._settings_path.read_bytes()
        self._settings_path.unlink()
        try:
            r = self.client.get("/config/export")
            self.assertEqual(r.status_code, 404)
        finally:
            self._settings_path.write_bytes(backup)


class TestShortcuts(_Base):
    """TASK-096: GET /shortcuts returns keyboard shortcut list."""

    def test_returns_200(self):
        self.assertEqual(self.client.get("/shortcuts").status_code, 200)

    def test_has_shortcuts_list(self):
        d = self.client.get("/shortcuts").get_json()
        self.assertIn("shortcuts", d)
        self.assertIsInstance(d["shortcuts"], list)

    def test_has_count(self):
        d = self.client.get("/shortcuts").get_json()
        self.assertIn("count", d)
        self.assertEqual(d["count"], len(d["shortcuts"]))

    def test_each_shortcut_has_key_and_description(self):
        shortcuts = self.client.get("/shortcuts").get_json()["shortcuts"]
        for s in shortcuts:
            self.assertIn("key", s)
            self.assertIn("description", s)

    def test_includes_common_keys(self):
        keys = {s["key"] for s in self.client.get("/shortcuts").get_json()["shortcuts"]}
        for expected in ("j", "k", "r", "p", "?", "Esc"):
            self.assertIn(expected, keys)

    def test_includes_b_branches_shortcut(self):
        keys = {s["key"] for s in self.client.get("/shortcuts").get_json()["shortcuts"]}
        self.assertIn("b", keys)

    def test_b_shortcut_description_mentions_branches(self):
        shortcuts = self.client.get("/shortcuts").get_json()["shortcuts"]
        b_entry = next((s for s in shortcuts if s["key"] == "b"), None)
        self.assertIsNotNone(b_entry)
        self.assertIn("ranch", b_entry["description"])

    def test_includes_s_subtasks_shortcut(self):
        keys = {s["key"] for s in self.client.get("/shortcuts").get_json()["shortcuts"]}
        self.assertIn("s", keys)

    def test_s_shortcut_description_mentions_subtasks(self):
        shortcuts = self.client.get("/shortcuts").get_json()["shortcuts"]
        s_entry = next((s for s in shortcuts if s["key"] == "s"), None)
        self.assertIsNotNone(s_entry)
        self.assertIn("ubtask", s_entry["description"])

    def test_includes_h_history_shortcut(self):
        keys = {s["key"] for s in self.client.get("/shortcuts").get_json()["shortcuts"]}
        self.assertIn("h", keys)

    def test_h_shortcut_description_mentions_history(self):
        shortcuts = self.client.get("/shortcuts").get_json()["shortcuts"]
        h_entry = next((s for s in shortcuts if s["key"] == "h"), None)
        self.assertIsNotNone(h_entry)
        self.assertIn("istory", h_entry["description"])


# Graph
# ---------------------------------------------------------------------------

class TestGraph(_Base):

    def setUp(self):
        super().setUp()
        self._write_state(self._make_state())

    def test_returns_nodes(self):
        r = self.client.get("/graph")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("nodes", d)
        self.assertIsInstance(d["nodes"], list)
        self.assertGreater(len(d["nodes"]), 0)

    def test_has_text(self):
        r = self.client.get("/graph")
        d = r.get_json()
        self.assertIn("text", d)
        self.assertIn("Task 0", d["text"])

    def test_node_structure(self):
        r = self.client.get("/graph")
        d = r.get_json()
        node = d["nodes"][0]
        self.assertIn("task", node)
        self.assertIn("status", node)
        self.assertIn("verified", node)
        self.assertIn("total", node)
        self.assertIn("depends_on", node)


# Stop
# ---------------------------------------------------------------------------

class TestStop(_Base):

    def test_stop_writes_trigger(self):
        r = self.client.post("/stop")
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d.get("ok"))


# Priority
# ---------------------------------------------------------------------------

class TestPriority(_Base):

    def setUp(self):
        super().setUp()
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending", "A3": "Verified"}))

    def test_returns_queue(self):
        r = self.client.get("/priority")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("queue", d)
        self.assertIn("count", d)
        self.assertGreater(d["count"], 0)

    def test_queue_sorted_by_risk(self):
        r = self.client.get("/priority")
        d = r.get_json()
        risks = [c["risk"] for c in d["queue"]]
        self.assertEqual(risks, sorted(risks, reverse=True))

    def test_verified_excluded(self):
        r = self.client.get("/priority")
        d = r.get_json()
        names = [c["subtask"] for c in d["queue"]]
        self.assertNotIn("A3", names)


# Stalled
# ---------------------------------------------------------------------------

class TestStalled(_Base):

    def setUp(self):
        super().setUp()
        self._write_state(self._make_state(
            {"A1": "Running", "A2": "Running", "A3": "Verified"}
        ))

    def test_returns_stalled(self):
        r = self.client.get("/stalled")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("stalled", d)
        self.assertIn("threshold", d)

    def test_stalled_sorted_by_age(self):
        r = self.client.get("/stalled")
        d = r.get_json()
        ages = [s["age"] for s in d["stalled"]]
        self.assertEqual(ages, sorted(ages, reverse=True))

    def test_verified_not_stalled(self):
        r = self.client.get("/stalled")
        d = r.get_json()
        names = [s["subtask"] for s in d["stalled"]]
        self.assertNotIn("A3", names)

    def test_review_not_stalled(self):
        self._write_state(self._make_state({"A1": "Review", "A2": "Running"}))
        r = self.client.get("/stalled")
        d = r.get_json()
        names = [s["subtask"] for s in d["stalled"]]
        self.assertNotIn("A1", names)

    def test_pending_not_stalled(self):
        self._write_state(self._make_state({"A1": "Pending", "A2": "Running"}))
        r = self.client.get("/stalled")
        d = r.get_json()
        names = [s["subtask"] for s in d["stalled"]]
        self.assertNotIn("A1", names)

    def test_review_only_state_stalled_count_zero(self):
        # All subtasks in Review — none should be stalled
        self._write_state(self._make_state({"A1": "Review", "A2": "Review"}))
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["count"], 0)
        self.assertEqual(d["stalled"], [])

    def test_review_count_field_excludes_review(self):
        # Running (stalled) + Review — count must equal len(stalled)
        self._write_state(self._make_state({"A1": "Running", "A2": "Review"}))
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["count"], len(d["stalled"]))
        names = [s["subtask"] for s in d["stalled"]]
        self.assertNotIn("A2", names)

    def test_multiple_review_none_in_stalled(self):
        state = self._make_state({"A1": "Review", "A2": "Review", "A3": "Running"})
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        names = [s["subtask"] for s in d["stalled"]]
        self.assertNotIn("A1", names)
        self.assertNotIn("A2", names)

    # -- Boundary tests ---------------------------------------------------

    def _make_state_lu(self, subtasks_lu: dict, step: int = 5) -> dict:
        """Build a DAG state with explicit last_update per subtask.

        subtasks_lu: {name: (status, last_update)}
        """
        sts = {
            name: {"status": st, "output": "", "description": "", "last_update": lu}
            for name, (st, lu) in subtasks_lu.items()
        }
        return {"step": step, "dag": {"Task 0": {"status": "Running", "depends_on": [],
                "branches": {"Branch A": {"subtasks": sts}}}}}

    def _set_threshold(self, n: int) -> None:
        cfg = json.loads(self._settings_path.read_text(encoding="utf-8"))
        cfg["STALL_THRESHOLD"] = n
        self._settings_path.write_text(json.dumps(cfg), encoding="utf-8")

    def test_stall_boundary_exactly_at_threshold(self):
        # age == threshold → must appear as stalled
        self._set_threshold(5)
        state = self._make_state_lu({"S1": ("Running", 0)}, step=5)
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["threshold"], 5)
        names = [s["subtask"] for s in d["stalled"]]
        self.assertIn("S1", names)

    def test_stall_boundary_one_below_threshold(self):
        # age == threshold - 1 → must NOT be stalled
        self._set_threshold(5)
        state = self._make_state_lu({"S1": ("Running", 0)}, step=4)
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["count"], 0)

    def test_custom_threshold_via_settings(self):
        # STALL_THRESHOLD=3 in settings; step=3, last_update=0 → age=3 → stalled
        cfg = json.loads(self._settings_path.read_text(encoding="utf-8"))
        cfg["STALL_THRESHOLD"] = 3
        self._settings_path.write_text(json.dumps(cfg), encoding="utf-8")
        state = self._make_state_lu({"S1": ("Running", 0)}, step=3)
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["threshold"], 3)
        names = [s["subtask"] for s in d["stalled"]]
        self.assertIn("S1", names)

    def test_high_threshold_fresh_running_not_stalled(self):
        # STALL_THRESHOLD=10; age=5 → NOT stalled
        cfg = json.loads(self._settings_path.read_text(encoding="utf-8"))
        cfg["STALL_THRESHOLD"] = 10
        self._settings_path.write_text(json.dumps(cfg), encoding="utf-8")
        state = self._make_state_lu({"S1": ("Running", 0)}, step=5)
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["count"], 0)

    def test_multiple_stalled_sorted_descending_by_age(self):
        # S1 age=10, S2 age=5, S3 age=7 — all above threshold=5 → order: S1, S3, S2
        self._set_threshold(5)
        state = self._make_state_lu(
            {"S1": ("Running", 0), "S2": ("Running", 5), "S3": ("Running", 3)}, step=10)
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        ages = [s["age"] for s in d["stalled"]]
        self.assertEqual(ages, sorted(ages, reverse=True))
        self.assertEqual(d["count"], 3)

    def test_status_stalled_count_matches_stalled_endpoint(self):
        # /status stalled and /stalled count must agree
        self._set_threshold(5)
        state = self._make_state_lu(
            {"S1": ("Running", 0), "S2": ("Pending", 0), "S3": ("Verified", 0)}, step=5)
        self._write_state(state)
        status_d  = self.client.get("/status").get_json()
        stalled_d = self.client.get("/stalled").get_json()
        self.assertEqual(status_d["stalled"], stalled_d["count"])

    def test_mixed_statuses_only_stalled_running_returned(self):
        # Running (stalled), Running (fresh), Verified, Pending, Review — only stalled Running
        self._set_threshold(5)
        state = self._make_state_lu(
            {"S1": ("Running", 0), "S2": ("Running", 4),
             "S3": ("Verified", 0), "S4": ("Pending", 0), "S5": ("Review", 0)},
            step=5)
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        names = [s["subtask"] for s in d["stalled"]]
        self.assertIn("S1", names)     # age=5, stalled
        self.assertNotIn("S2", names)  # age=1, fresh
        self.assertNotIn("S3", names)
        self.assertNotIn("S4", names)
        self.assertNotIn("S5", names)

    # -- Multi-task / multi-branch cross-detection (TASK-254) -------------

    def _make_multi_task_state(self, threshold=5):
        """Two tasks, two branches each, each with one Running subtask at last_update=0.
        step=threshold so all Running subtasks are exactly at the stall boundary.
        """
        return {
            "step": threshold,
            "dag": {
                "Task A": {
                    "status": "Running", "depends_on": [],
                    "branches": {
                        "Br A1": {"subtasks": {"SA1": {"status": "Running",
                                                        "output": "", "last_update": 0}}},
                        "Br A2": {"subtasks": {"SA2": {"status": "Running",
                                                        "output": "", "last_update": 0}}},
                    },
                },
                "Task B": {
                    "status": "Running", "depends_on": [],
                    "branches": {
                        "Br B1": {"subtasks": {"SB1": {"status": "Running",
                                                        "output": "", "last_update": 0}}},
                        "Br B2": {"subtasks": {"SB2": {"status": "Verified",
                                                        "output": "", "last_update": 0}}},
                    },
                },
            },
        }

    def test_multi_task_stalled_count(self):
        # 3 Running stalled + 1 Verified → stalled count = 3
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["count"], 3)

    def test_multi_task_stalled_subtask_names(self):
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        d = self.client.get("/stalled").get_json()
        names = {s["subtask"] for s in d["stalled"]}
        self.assertIn("SA1", names)
        self.assertIn("SA2", names)
        self.assertIn("SB1", names)
        self.assertNotIn("SB2", names)  # Verified, not stalled

    def test_multi_task_stalled_task_field(self):
        # Each entry must carry its correct task name
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        d = self.client.get("/stalled").get_json()
        by_subtask = {s["subtask"]: s["task"] for s in d["stalled"]}
        self.assertEqual(by_subtask.get("SA1"), "Task A")
        self.assertEqual(by_subtask.get("SA2"), "Task A")
        self.assertEqual(by_subtask.get("SB1"), "Task B")

    def test_multi_task_stalled_branch_field(self):
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        d = self.client.get("/stalled").get_json()
        by_subtask = {s["subtask"]: s["branch"] for s in d["stalled"]}
        self.assertEqual(by_subtask.get("SA1"), "Br A1")
        self.assertEqual(by_subtask.get("SB1"), "Br B1")

    def test_multi_task_status_stalled_matches_stalled_endpoint(self):
        # /status.stalled must equal /stalled.count across multi-task state
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        status_d  = self.client.get("/status").get_json()
        stalled_d = self.client.get("/stalled").get_json()
        self.assertEqual(status_d["stalled"], stalled_d["count"])

    def test_multi_task_partial_stall_only_above_threshold(self):
        # Mix: some at step=5 (stalled), some at step=4 (fresh); threshold=5
        self._set_threshold(5)
        state = {
            "step": 5,
            "dag": {
                "Task A": {"status": "Running", "depends_on": [], "branches": {
                    "Br A": {"subtasks": {
                        "Stalled": {"status": "Running", "output": "", "last_update": 0},
                        "Fresh":   {"status": "Running", "output": "", "last_update": 1},
                    }},
                }},
            },
        }
        self._write_state(state)
        d = self.client.get("/stalled").get_json()
        names = [s["subtask"] for s in d["stalled"]]
        self.assertIn("Stalled", names)
        self.assertNotIn("Fresh", names)

    # -- by_branch grouping (TASK-268) ------------------------------------

    def test_by_branch_key_present(self):
        d = self.client.get("/stalled").get_json()
        self.assertIn("by_branch", d)

    def test_by_branch_empty_when_no_stall(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/stalled").get_json()
        self.assertEqual(d["by_branch"], [])

    def test_by_branch_populated_from_multi_task(self):
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        d = self.client.get("/stalled").get_json()
        self.assertGreater(len(d["by_branch"]), 0)
        entry = d["by_branch"][0]
        self.assertIn("task", entry)
        self.assertIn("branch", entry)
        self.assertIn("count", entry)

    def test_by_branch_count_sum_equals_total(self):
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        d = self.client.get("/stalled").get_json()
        self.assertEqual(sum(e["count"] for e in d["by_branch"]), d["count"])

    def test_by_branch_sorted_desc(self):
        self._set_threshold(5)
        self._write_state(self._make_multi_task_state(threshold=5))
        d = self.client.get("/stalled").get_json()
        counts = [e["count"] for e in d["by_branch"]]
        self.assertEqual(counts, sorted(counts, reverse=True))


# Heal
# ---------------------------------------------------------------------------

class TestHeal(_Base):

    def test_heal_writes_trigger(self):
        r = self.client.post("/heal", json={"subtask": "A1"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d.get("ok"))
        self.assertEqual(d["subtask"], "A1")

    def test_heal_missing_subtask(self):
        r = self.client.post("/heal", json={})
        self.assertEqual(r.status_code, 400)
        d = r.get_json()
        self.assertFalse(d.get("ok"))


# Agents
# ---------------------------------------------------------------------------

class TestAgents(_Base):

    def setUp(self):
        super().setUp()
        self._write_state(self._make_state({"A1": "Running", "A2": "Verified"}))

    def test_returns_agents(self):
        r = self.client.get("/agents")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("planner", d)
        self.assertIn("executor", d)
        self.assertIn("healer", d)
        self.assertIn("meta", d)
        self.assertIn("forecast", d)

    def test_forecast_fields(self):
        r = self.client.get("/agents")
        d = r.get_json()
        f = d["forecast"]
        self.assertIn("total", f)
        self.assertIn("verified", f)
        self.assertIn("pct", f)
        self.assertGreater(f["total"], 0)

    def test_healer_fields(self):
        r = self.client.get("/agents")
        d = r.get_json()
        h = d["healer"]
        self.assertIn("healed_total", h)
        self.assertIn("threshold", h)
        self.assertIn("currently_stalled", h)


# Forecast
# ---------------------------------------------------------------------------

class TestForecast(_Base):

    def setUp(self):
        super().setUp()
        self._write_state(self._make_state({"A1": "Running", "A2": "Verified", "A3": "Pending"}))

    def test_returns_forecast(self):
        r = self.client.get("/forecast")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("total", d)
        self.assertIn("verified", d)
        self.assertIn("pct", d)
        self.assertIn("remaining", d)

    def test_breakdown_counts(self):
        r = self.client.get("/forecast")
        d = r.get_json()
        self.assertEqual(d["verified"] + d["running"] + d["pending"] + d["review"], d["total"])

    def test_has_rates(self):
        r = self.client.get("/forecast")
        d = r.get_json()
        self.assertIn("verify_rate", d)
        self.assertIn("heal_rate", d)


# Error handlers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# POST /add_task
# ---------------------------------------------------------------------------

class TestAddTask(_Base):

    def test_add_task_queues_trigger(self):
        r = self.client.post("/add_task", json={"spec": "Build auth module"})
        self.assertEqual(r.status_code, 202)
        self.assertTrue(self._add_task_path.exists())
        payload = json.loads(self._add_task_path.read_text())
        self.assertEqual(payload["spec"], "Build auth module")

    def test_add_task_missing_spec_returns_400(self):
        r = self.client.post("/add_task", json={})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /add_branch
# ---------------------------------------------------------------------------

class TestAddBranch(_Base):

    def test_add_branch_queues_trigger(self):
        r = self.client.post("/add_branch", json={"task": "0", "spec": "Deploy to staging"})
        self.assertEqual(r.status_code, 202)
        payload = json.loads(self._add_branch_path.read_text())
        self.assertEqual(payload["task"], "0")
        self.assertEqual(payload["spec"], "Deploy to staging")

    def test_add_branch_missing_fields_returns_400(self):
        r = self.client.post("/add_branch", json={"task": "0"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /prioritize_branch
# ---------------------------------------------------------------------------

class TestPrioritizeBranch(_Base):

    def test_prioritize_branch_queues_trigger(self):
        r = self.client.post("/prioritize_branch", json={"task": "0", "branch": "A"})
        self.assertEqual(r.status_code, 202)
        payload = json.loads(self._priority_branch_path.read_text())
        self.assertEqual(payload["task"], "0")
        self.assertEqual(payload["branch"], "A")

    def test_prioritize_branch_missing_returns_400(self):
        r = self.client.post("/prioritize_branch", json={"task": "0"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /undo
# ---------------------------------------------------------------------------

class TestUndo(_Base):

    def test_undo_writes_trigger(self):
        r = self.client.post("/undo")
        self.assertEqual(r.status_code, 202)
        self.assertTrue(self._undo_path.exists())

    def test_undo_returns_ok(self):
        r = self.client.post("/undo")
        self.assertTrue(r.get_json()["ok"])


# ---------------------------------------------------------------------------
# POST /depends + POST /undepends
# ---------------------------------------------------------------------------

class TestDepends(_Base):

    def test_depends_queues_trigger(self):
        r = self.client.post("/depends", json={"target": "1", "dep": "0"})
        self.assertEqual(r.status_code, 202)
        payload = json.loads(self._depends_path.read_text())
        self.assertEqual(payload["target"], "1")
        self.assertEqual(payload["dep"], "0")

    def test_depends_missing_fields_returns_400(self):
        r = self.client.post("/depends", json={"target": "1"})
        self.assertEqual(r.status_code, 400)


class TestUndepends(_Base):

    def test_undepends_queues_trigger(self):
        r = self.client.post("/undepends", json={"target": "1", "dep": "0"})
        self.assertEqual(r.status_code, 202)
        payload = json.loads(self._undepends_path.read_text())
        self.assertEqual(payload["target"], "1")

    def test_undepends_missing_returns_400(self):
        r = self.client.post("/undepends", json={})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /reset
# ---------------------------------------------------------------------------

class TestReset(_Base):

    def test_reset_without_confirm_returns_400(self):
        r = self.client.post("/reset", json={})
        self.assertEqual(r.status_code, 400)

    def test_reset_with_confirm_writes_trigger(self):
        r = self.client.post("/reset", json={"confirm": "yes"})
        self.assertEqual(r.status_code, 202)
        self.assertTrue(self._reset_path.exists())

    def test_reset_wrong_confirm_returns_400(self):
        r = self.client.post("/reset", json={"confirm": "no"})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /snapshot
# ---------------------------------------------------------------------------

class TestSnapshot(_Base):

    def test_snapshot_writes_trigger(self):
        r = self.client.post("/snapshot")
        self.assertEqual(r.status_code, 202)
        self.assertTrue(self._snapshot_path.exists())


# ---------------------------------------------------------------------------
# POST /pause + POST /resume
# ---------------------------------------------------------------------------

class TestPauseResume(_Base):

    def test_pause_writes_trigger(self):
        r = self.client.post("/pause")
        self.assertEqual(r.status_code, 202)
        self.assertTrue(self._pause_path.exists())

    def test_resume_removes_trigger(self):
        self._pause_path.parent.mkdir(exist_ok=True)
        self._pause_path.write_text("1")
        r = self.client.post("/resume")
        self.assertEqual(r.status_code, 202)
        self.assertFalse(self._pause_path.exists())

    def test_resume_when_not_paused_returns_ok(self):
        r = self.client.post("/resume")
        self.assertEqual(r.status_code, 202)
        self.assertTrue(r.get_json()["ok"])


# ---------------------------------------------------------------------------
# GET /  (dashboard HTML)
# ---------------------------------------------------------------------------

class TestGetRoot(_Base):

    def test_get_root_returns_200(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_get_root_returns_html(self):
        r = self.client.get("/")
        content_type = r.headers.get("Content-Type", "")
        self.assertIn("html", content_type.lower())


# ---------------------------------------------------------------------------
# POST /tasks/<id>/trigger
# ---------------------------------------------------------------------------

class TestPostTaskTrigger(_Base):

    def test_post_task_trigger_valid_task(self):
        self._write_state(self._make_state({"A1": "Pending", "A2": "Verified"}))
        r = self.client.post("/tasks/Task 0/trigger")
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["accepted"])
        self.assertIn("pending_count", d)

    def test_post_task_trigger_invalid_task(self):
        self._write_state(self._make_state())
        r = self.client.post("/tasks/Task 999/trigger")
        self.assertEqual(r.status_code, 404)

    def test_post_task_trigger_counts_non_verified(self):
        # endpoint counts subtasks not in (Verified, Running) — only Pending/Review
        self._write_state(self._make_state({"A1": "Pending", "A2": "Verified", "A3": "Running"}))
        d = self.client.post("/tasks/Task 0/trigger").get_json()
        self.assertEqual(d["pending_count"], 1)


class TestDagExport(_Base):

    def test_get_dag_export_returns_json(self):
        self._write_state(self._make_state())
        r = self.client.get("/dag/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/json", r.content_type)

    def test_get_dag_export_contains_dag(self):
        self._write_state(self._make_state())
        d = self.client.get("/dag/export").get_json()
        self.assertIn("dag", d)
        self.assertIn("Task 0", d["dag"])

    def test_get_dag_export_contains_step(self):
        self._write_state(self._make_state(step=7))
        d = self.client.get("/dag/export").get_json()
        self.assertEqual(d["exported_step"], 7)

    def test_get_dag_export_attachment_header(self):
        self._write_state(self._make_state())
        r = self.client.get("/dag/export")
        self.assertIn("dag_export.json", r.headers.get("Content-Disposition", ""))

    def test_get_dag_export_no_state(self):
        # No state file — should still return something (empty dag)
        r = self.client.get("/dag/export")
        self.assertEqual(r.status_code, 200)

    # /tasks/export alias (TASK-082)

    def test_tasks_export_alias_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/export")
        self.assertEqual(r.status_code, 200)

    def test_tasks_export_returns_summary_not_dag(self):
        # /tasks/export (TASK-143) is a task-summary endpoint, not an alias for /dag/export
        self._write_state(self._make_state())
        d = self.client.get("/tasks/export?format=json").get_json()
        self.assertIn("tasks", d)
        self.assertIn("count", d)
        self.assertIsInstance(d["tasks"], list)



class TestDagImport(_Base):

    def _minimal_dag(self):
        return {
            "Task 0": {
                "status": "Pending",
                "depends_on": [],
                "branches": {
                    "Branch A": {
                        "subtasks": {
                            "A1": {"status": "Pending", "output": "", "description": "test"}
                        }
                    }
                },
            }
        }

    def test_post_dag_import_returns_202(self):
        r = self.client.post("/dag/import", json={"dag": self._minimal_dag()})
        self.assertEqual(r.status_code, 202)

    def test_post_dag_import_writes_trigger(self):
        self.client.post("/dag/import", json={"dag": self._minimal_dag()})
        self.assertTrue(self._dag_import_path.exists())

    def test_post_dag_import_trigger_contains_dag(self):
        self.client.post("/dag/import", json={"dag": self._minimal_dag()})
        data = json.loads(self._dag_import_path.read_text())
        self.assertIn("dag", data)
        self.assertIn("Task 0", data["dag"])

    def test_post_dag_import_accepts_raw_dag(self):
        # Body without "dag" wrapper — top-level task keys
        r = self.client.post("/dag/import", json=self._minimal_dag())
        self.assertEqual(r.status_code, 202)

    def test_post_dag_import_missing_branches_returns_400(self):
        bad = {"Task 0": {"status": "Pending"}}   # no "branches" key
        r = self.client.post("/dag/import", json={"dag": bad})
        self.assertEqual(r.status_code, 400)

    def test_post_dag_import_empty_body_returns_400(self):
        r = self.client.post("/dag/import", data="not json",
                             content_type="application/json")
        self.assertIn(r.status_code, [400, 422])

    def test_post_dag_import_response_has_task_count(self):
        d = self.client.post("/dag/import", json={"dag": self._minimal_dag()}).get_json()
        self.assertEqual(d["tasks"], 1)


class TestMetrics(_Base):

    def test_get_metrics_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)

    def test_get_metrics_has_required_keys(self):
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        self.assertIn("step", d)
        self.assertIn("summary", d)
        self.assertIn("history", d)
        self.assertIn("total_healed", d)

    def test_get_metrics_summary_keys(self):
        self._write_state(self._make_state())
        s = self.client.get("/metrics").get_json()["summary"]
        for key in ("total_steps", "total_verifies", "avg_verified_per_step",
                    "peak_verified_per_step", "steps_with_heals"):
            self.assertIn(key, s)

    def test_get_metrics_empty_history(self):
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        self.assertIsInstance(d["history"], list)
        self.assertEqual(d["summary"]["total_steps"], 0)

    def test_get_metrics_with_history(self):
        state = self._make_state()
        state["meta_history"] = [
            {"verified": 2, "healed": 0},
            {"verified": 3, "healed": 1},
            {"verified": 1, "healed": 0},
        ]
        self._write_state(state)
        d = self.client.get("/metrics").get_json()
        self.assertEqual(d["summary"]["total_steps"], 3)
        self.assertEqual(d["summary"]["total_verifies"], 6)
        self.assertEqual(d["summary"]["peak_verified_per_step"], 3)
        self.assertEqual(d["summary"]["steps_with_heals"], 1)
        self.assertAlmostEqual(d["summary"]["avg_verified_per_step"], 2.0)

    def test_get_metrics_history_has_cumulative(self):
        state = self._make_state()
        state["meta_history"] = [{"verified": 2, "healed": 0}, {"verified": 3, "healed": 0}]
        self._write_state(state)
        hist = self.client.get("/metrics").get_json()["history"]
        self.assertEqual(hist[0]["cumulative"], 2)
        self.assertEqual(hist[1]["cumulative"], 5)


class TestMetricsHealth(_Base):
    """TASK-091: GET /metrics health summary fields."""

    def test_health_fields_present(self):
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        for key in ("total", "verified", "pending", "running", "review", "stalled", "pct"):
            self.assertIn(key, d)

    def test_elapsed_s_and_steps_per_min_present(self):
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        self.assertIn("elapsed_s", d)
        self.assertIn("steps_per_min", d)

    def test_health_counts_match_dag(self):
        state = self._make_state()
        self._write_state(state)
        d = self.client.get("/metrics").get_json()
        # _make_state creates subtasks with mixed statuses; total must be positive
        self.assertGreater(d["total"], 0)
        self.assertEqual(d["verified"] + d["pending"] + d["running"] + d["review"], d["total"])

    def test_pct_is_float(self):
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        self.assertIsInstance(d["pct"], float)

    def test_stalled_zero_when_no_running(self):
        state = self._make_state()
        # Force all subtasks to Pending
        for t in state["dag"].values():
            for b in t["branches"].values():
                for s in b["subtasks"].values():
                    s["status"] = "Pending"
        self._write_state(state)
        d = self.client.get("/metrics").get_json()
        self.assertEqual(d["stalled"], 0)

    def test_analytics_still_present(self):
        """Backward-compat: existing analytics fields still returned."""
        self._write_state(self._make_state())
        d = self.client.get("/metrics").get_json()
        self.assertIn("summary", d)
        self.assertIn("history", d)
        self.assertIn("total_healed", d)

    def test_review_count_correct(self):
        state = self._make_state({"A1": "Review", "A2": "Review", "A3": "Pending"})
        self._write_state(state)
        d = self.client.get("/metrics").get_json()
        self.assertEqual(d["review"], 2)

    def test_review_not_counted_in_pending(self):
        state = self._make_state({"A1": "Review", "A2": "Pending"})
        self._write_state(state)
        d = self.client.get("/metrics").get_json()
        self.assertEqual(d["review"], 1)
        self.assertEqual(d["pending"], 1)


class TestErrorHandlers(_Base):

    def test_404_returns_json(self):
        r = self.client.get("/nonexistent")
        self.assertEqual(r.status_code, 404)
        d = r.get_json()
        self.assertIn("error", d)

    def test_cors_headers_present(self):
        r = self.client.get("/status")
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")


# ---------------------------------------------------------------------------
# GET /cache  /  DELETE /cache
# ---------------------------------------------------------------------------

class TestCache(_Base):

    def _write_entries(self, n: int) -> None:
        for i in range(n):
            (self._cache_dir / f"entry_{i:04d}.json").write_text(
                '{"response": "x"}', encoding="utf-8"
            )

    # GET /cache

    def _write_stats(self, hits: int, misses: int) -> None:
        import json as _json
        data = {"cumulative_hits": hits, "cumulative_misses": misses}
        (self._cache_dir / "session_stats.json").write_text(
            _json.dumps(data), encoding="utf-8"
        )

    # GET /cache

    def test_get_cache_empty(self):
        r = self.client.get("/cache")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["entries"], 0)
        self.assertEqual(d["estimated_tokens_held"], 0)
        self.assertIn("cache_dir", d)

    def test_get_cache_counts_entries(self):
        self._write_entries(3)
        r = self.client.get("/cache")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["entries"], 3)

    def test_get_cache_estimated_tokens(self):
        self._write_entries(2)  # 2 × 550 = 1100
        r = self.client.get("/cache")
        d = r.get_json()
        self.assertEqual(d["estimated_tokens_held"], 1100)

    def test_get_cache_reports_directory(self):
        r = self.client.get("/cache")
        d = r.get_json()
        self.assertIn("cache_dir", d)
        self.assertIsInstance(d["cache_dir"], str)

    def test_get_cache_cumulative_fields_present(self):
        r = self.client.get("/cache")
        d = r.get_json()
        self.assertIn("cumulative_hits", d)
        self.assertIn("cumulative_misses", d)
        self.assertIn("cumulative_total", d)

    def test_get_cache_cumulative_values_from_stats_file(self):
        self._write_stats(hits=7, misses=3)
        r = self.client.get("/cache")
        d = r.get_json()
        self.assertEqual(d["cumulative_hits"], 7)
        self.assertEqual(d["cumulative_misses"], 3)
        self.assertEqual(d["cumulative_total"], 10)
        self.assertEqual(d["cumulative_hit_rate"], 70.0)

    def test_get_cache_hit_rate_none_when_no_stats(self):
        r = self.client.get("/cache")
        d = r.get_json()
        self.assertIsNone(d["cumulative_hit_rate"])

    def test_get_cache_excludes_stats_file_from_entry_count(self):
        self._write_entries(2)
        self._write_stats(hits=1, misses=0)
        r = self.client.get("/cache")
        d = r.get_json()
        self.assertEqual(d["entries"], 2)  # session_stats.json not counted

    # DELETE /cache

    def test_delete_cache_empty_returns_zero(self):
        r = self.client.delete("/cache")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["deleted"], 0)

    def test_delete_cache_removes_entries(self):
        self._write_entries(4)
        r = self.client.delete("/cache")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["deleted"], 4)
        remaining = [f for f in self._cache_dir.glob("*.json") if f.name != "session_stats.json"]
        self.assertEqual(len(remaining), 0)

    def test_delete_cache_preserves_session_stats(self):
        self._write_entries(3)
        self._write_stats(hits=5, misses=2)
        self.client.delete("/cache")
        self.assertTrue((self._cache_dir / "session_stats.json").exists())

    def test_delete_cache_subsequent_get_shows_zero(self):
        self._write_entries(2)
        self.client.delete("/cache")
        r = self.client.get("/cache")
        self.assertEqual(r.get_json()["entries"], 0)

    def test_delete_cache_missing_dir_returns_ok(self):
        import shutil
        shutil.rmtree(self._cache_dir, ignore_errors=True)
        r = self.client.delete("/cache")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])


# ---------------------------------------------------------------------------
# /metrics/export
# ---------------------------------------------------------------------------

class TestMetricsExport(_Base):

    def test_export_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export")
        self.assertEqual(r.status_code, 200)

    def test_export_content_type_is_csv(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export")
        self.assertIn("text/csv", r.content_type)

    def test_export_content_disposition(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export")
        self.assertIn("metrics.csv", r.headers.get("Content-Disposition", ""))

    def test_export_header_row(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export")
        first_line = r.data.decode("utf-8").splitlines()[0]
        self.assertEqual(first_line, "step_index,verified,healed,cumulative")

    def test_export_empty_history_has_only_header(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export")
        lines = r.data.decode("utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)  # header only

    def test_export_rows_match_history(self):
        state = self._make_state()
        state["meta_history"] = [
            {"verified": 2, "healed": 0},
            {"verified": 3, "healed": 1},
        ]
        self._write_state(state)
        r = self.client.get("/metrics/export")
        lines = r.data.decode("utf-8").strip().splitlines()
        self.assertEqual(lines[1], "1,2,0,2")
        self.assertEqual(lines[2], "2,3,1,5")

    def test_export_cumulative_is_running_total(self):
        state = self._make_state()
        state["meta_history"] = [
            {"verified": 1, "healed": 0},
            {"verified": 4, "healed": 0},
            {"verified": 2, "healed": 0},
        ]
        self._write_state(state)
        r = self.client.get("/metrics/export")
        lines = r.data.decode("utf-8").strip().splitlines()
        cumulatives = [line.split(",")[3] for line in lines[1:]]
        self.assertEqual(cumulatives, ["1", "5", "7"])

    # ?format=json

    def test_export_json_returns_200(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export?format=json")
        self.assertEqual(r.status_code, 200)

    def test_export_json_content_type(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export?format=json")
        self.assertIn("application/json", r.content_type)

    def test_export_json_returns_list(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export?format=json")
        self.assertIsInstance(r.get_json(), list)

    def test_export_json_empty_history_is_empty_list(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export?format=json")
        self.assertEqual(r.get_json(), [])

    def test_export_json_row_keys(self):
        state = self._make_state()
        state["meta_history"] = [{"verified": 2, "healed": 1}]
        self._write_state(state)
        rows = self.client.get("/metrics/export?format=json").get_json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], {"step_index": 1, "verified": 2, "healed": 1, "cumulative": 2})

    def test_export_json_cumulative_matches_csv(self):
        state = self._make_state()
        state["meta_history"] = [
            {"verified": 3, "healed": 0},
            {"verified": 2, "healed": 1},
        ]
        self._write_state(state)
        rows = self.client.get("/metrics/export?format=json").get_json()
        self.assertEqual(rows[0]["cumulative"], 3)
        self.assertEqual(rows[1]["cumulative"], 5)

    def test_export_csv_still_works_with_format_csv(self):
        self._write_state(self._make_state())
        r = self.client.get("/metrics/export?format=csv")
        self.assertIn("text/csv", r.content_type)

    # ?limit=N

    def _state_with_history(self, n: int):
        state = self._make_state()
        state["meta_history"] = [{"verified": i + 1, "healed": 0} for i in range(n)]
        return state

    def test_limit_caps_csv_rows(self):
        self._write_state(self._state_with_history(5))
        r = self.client.get("/metrics/export?limit=2")
        lines = r.data.decode("utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)  # header + 2 data rows

    def test_limit_returns_most_recent_rows(self):
        self._write_state(self._state_with_history(5))
        rows = self.client.get("/metrics/export?format=json&limit=2").get_json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["step_index"], 4)
        self.assertEqual(rows[1]["step_index"], 5)

    def test_limit_zero_returns_all_rows(self):
        self._write_state(self._state_with_history(4))
        rows = self.client.get("/metrics/export?format=json&limit=0").get_json()
        self.assertEqual(len(rows), 4)

    def test_limit_larger_than_history_returns_all(self):
        self._write_state(self._state_with_history(3))
        rows = self.client.get("/metrics/export?format=json&limit=100").get_json()
        self.assertEqual(len(rows), 3)

    def test_limit_cumulative_preserved_correctly(self):
        # cumulative is computed over all rows before slicing
        self._write_state(self._state_with_history(3))  # verified: 1, 2, 3 → cum: 1, 3, 6
        rows = self.client.get("/metrics/export?format=json&limit=1").get_json()
        self.assertEqual(rows[0]["cumulative"], 6)  # last row's cumulative = 1+2+3

    # ?since=S

    def test_since_filters_rows_after_step(self):
        self._write_state(self._state_with_history(5))
        rows = self.client.get("/metrics/export?format=json&since=3").get_json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["step_index"], 4)
        self.assertEqual(rows[1]["step_index"], 5)

    def test_since_zero_returns_all(self):
        self._write_state(self._state_with_history(4))
        rows = self.client.get("/metrics/export?format=json&since=0").get_json()
        self.assertEqual(len(rows), 4)

    def test_since_beyond_history_returns_empty(self):
        self._write_state(self._state_with_history(3))
        rows = self.client.get("/metrics/export?format=json&since=99").get_json()
        self.assertEqual(rows, [])

    def test_since_and_limit_compose(self):
        # 5 rows: step_index 1-5; since=2 → [3,4,5]; limit=2 → [4,5]
        self._write_state(self._state_with_history(5))
        rows = self.client.get("/metrics/export?format=json&since=2&limit=2").get_json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["step_index"], 4)
        self.assertEqual(rows[1]["step_index"], 5)

    def test_since_works_with_csv(self):
        self._write_state(self._state_with_history(4))
        r = self.client.get("/metrics/export?since=2")
        lines = r.data.decode("utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)  # header + rows 3 and 4


# ---------------------------------------------------------------------------
# /run/history
# ---------------------------------------------------------------------------

class TestRunHistory(_Base):
    """TASK-100: GET /run/history step execution log."""

    def test_returns_200(self):
        self._write_state(self._make_state())
        self.assertEqual(self.client.get("/run/history").status_code, 200)

    def test_has_records_and_count(self):
        self._write_state(self._make_state())
        d = self.client.get("/run/history").get_json()
        self.assertIn("records", d)
        self.assertIn("count", d)
        self.assertIn("total_steps", d)

    def test_empty_history_returns_empty_records(self):
        self._write_state(self._make_state())
        d = self.client.get("/run/history").get_json()
        self.assertEqual(d["records"], [])
        self.assertEqual(d["count"], 0)

    def test_records_match_meta_history(self):
        state = self._make_state()
        state["meta_history"] = [{"verified": 2, "healed": 0}, {"verified": 3, "healed": 1}]
        self._write_state(state)
        d = self.client.get("/run/history").get_json()
        self.assertEqual(d["count"], 2)
        self.assertEqual(d["records"][0]["step_index"], 1)
        self.assertEqual(d["records"][1]["verified"], 3)

    def test_limit_param(self):
        state = self._make_state()
        state["meta_history"] = [{"verified": i, "healed": 0} for i in range(5)]
        self._write_state(state)
        d = self.client.get("/run/history?limit=2").get_json()
        self.assertEqual(d["count"], 2)

    def test_since_param(self):
        state = self._make_state()
        state["meta_history"] = [{"verified": i, "healed": 0} for i in range(4)]
        self._write_state(state)
        d = self.client.get("/run/history?since=2").get_json()
        for r in d["records"]:
            self.assertGreater(r["step_index"], 2)


# ---------------------------------------------------------------------------
# /cache/history
# ---------------------------------------------------------------------------

class TestCacheHistory(_Base):

    def _write_stats(self, data: dict) -> None:
        import json as _json
        (self._cache_dir / "session_stats.json").write_text(
            _json.dumps(data), encoding="utf-8"
        )

    def test_history_missing_file_returns_empty(self):
        r = self.client.get("/cache/history")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["sessions"], [])
        self.assertEqual(d["cumulative_hits"], 0)
        self.assertEqual(d["cumulative_misses"], 0)

    def test_history_no_sessions_key_returns_empty_list(self):
        self._write_stats({"cumulative_hits": 5, "cumulative_misses": 1})
        d = self.client.get("/cache/history").get_json()
        self.assertEqual(d["sessions"], [])

    def test_history_returns_cumulative_totals(self):
        self._write_stats({"cumulative_hits": 7, "cumulative_misses": 3, "sessions": []})
        d = self.client.get("/cache/history").get_json()
        self.assertEqual(d["cumulative_hits"], 7)
        self.assertEqual(d["cumulative_misses"], 3)

    def test_history_session_count(self):
        self._write_stats({"cumulative_hits": 2, "cumulative_misses": 1, "sessions": [
            {"hits": 1, "misses": 0, "cumulative_hits": 1, "cumulative_misses": 0, "ended_at": "t1"},
            {"hits": 1, "misses": 1, "cumulative_hits": 2, "cumulative_misses": 1, "ended_at": "t2"},
        ]})
        d = self.client.get("/cache/history").get_json()
        self.assertEqual(len(d["sessions"]), 2)

    def test_history_session_index_is_1_based(self):
        self._write_stats({"cumulative_hits": 1, "cumulative_misses": 0, "sessions": [
            {"hits": 1, "misses": 0, "cumulative_hits": 1, "cumulative_misses": 0, "ended_at": "t"}
        ]})
        d = self.client.get("/cache/history").get_json()
        self.assertEqual(d["sessions"][0]["session"], 1)

    def test_history_hit_rate_computed(self):
        self._write_stats({"cumulative_hits": 3, "cumulative_misses": 1, "sessions": [
            {"hits": 3, "misses": 1, "cumulative_hits": 3, "cumulative_misses": 1, "ended_at": "t"}
        ]})
        d = self.client.get("/cache/history").get_json()
        self.assertEqual(d["sessions"][0]["hit_rate"], 75.0)

    def test_history_hit_rate_none_when_no_activity(self):
        self._write_stats({"cumulative_hits": 0, "cumulative_misses": 0, "sessions": [
            {"hits": 0, "misses": 0, "cumulative_hits": 0, "cumulative_misses": 0, "ended_at": "t"}
        ]})
        d = self.client.get("/cache/history").get_json()
        self.assertIsNone(d["sessions"][0]["hit_rate"])

    def test_history_session_has_ended_at(self):
        self._write_stats({"cumulative_hits": 1, "cumulative_misses": 0, "sessions": [
            {"hits": 1, "misses": 0, "cumulative_hits": 1, "cumulative_misses": 0, "ended_at": "2026-01-01T00:00:00Z"}
        ]})
        d = self.client.get("/cache/history").get_json()
        self.assertEqual(d["sessions"][0]["ended_at"], "2026-01-01T00:00:00Z")

    # ?since=S

    def _write_stats_n(self, n):
        sessions = [{"hits": i, "misses": 0, "cumulative_hits": i, "cumulative_misses": 0, "ended_at": f"t{i}"}
                    for i in range(1, n + 1)]
        self._write_stats({"cumulative_hits": n, "cumulative_misses": 0, "sessions": sessions})

    def test_since_filters_sessions_after_index(self):
        self._write_stats_n(5)
        d = self.client.get("/cache/history?since=3").get_json()
        nums = [s["session"] for s in d["sessions"]]
        self.assertEqual(nums, [4, 5])

    def test_since_zero_returns_all_sessions(self):
        self._write_stats_n(4)
        d = self.client.get("/cache/history?since=0").get_json()
        self.assertEqual(len(d["sessions"]), 4)

    def test_since_beyond_count_returns_empty(self):
        self._write_stats_n(3)
        d = self.client.get("/cache/history?since=99").get_json()
        self.assertEqual(d["sessions"], [])

    def test_since_cumulative_totals_unaffected(self):
        self._write_stats_n(4)
        d = self.client.get("/cache/history?since=2").get_json()
        self.assertEqual(d["cumulative_hits"], 4)
        self.assertEqual(d["sessions"][0]["session"], 3)

    def test_since_no_param_returns_all(self):
        self._write_stats_n(3)
        d = self.client.get("/cache/history").get_json()
        self.assertEqual(len(d["sessions"]), 3)


# ---------------------------------------------------------------------------
# GET /subtask/<id>  (TASK-076)
# ---------------------------------------------------------------------------

class TestGetSubtask(_Base):

    def test_returns_404_for_unknown(self):
        self._write_state(self._make_state())
        r = self.client.get("/subtask/ZZZ")
        self.assertEqual(r.status_code, 404)

    def test_returns_subtask_fields(self):
        state = self._make_state({"A1": "Verified"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st["output"] = "done"
        st["history"] = [{"step": 1, "status": "Verified"}]
        self._write_state(state)
        d = self.client.get("/subtask/A1").get_json()
        self.assertEqual(d["subtask"], "A1")
        self.assertEqual(d["task"], "Task 0")
        self.assertEqual(d["branch"], "Branch A")
        self.assertEqual(d["status"], "Verified")
        self.assertEqual(d["output"], "done")
        self.assertEqual(len(d["history"]), 1)

    def test_output_defaults_to_empty(self):
        state = self._make_state({"A1": "Pending"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st.pop("output", None)
        self._write_state(state)
        d = self.client.get("/subtask/A1").get_json()
        self.assertEqual(d["output"], "")

    def test_history_defaults_to_empty_list(self):
        state = self._make_state({"A1": "Pending"})
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        st.pop("history", None)
        self._write_state(state)
        d = self.client.get("/subtask/A1").get_json()
        self.assertEqual(d["history"], [])


class TestSubtaskReset(_Base):
    """TASK-099: POST /subtask/<id>/reset writes heal trigger and returns status."""

    def test_returns_200_for_known_subtask(self):
        self._write_state(self._make_state())
        r = self.client.post("/subtask/A1/reset")
        self.assertEqual(r.status_code, 200)

    def test_returns_ok_true(self):
        self._write_state(self._make_state())
        d = self.client.post("/subtask/A1/reset").get_json()
        self.assertTrue(d["ok"])

    def test_returns_previous_status(self):
        state = self._make_state({"A1": "Running"})
        self._write_state(state)
        d = self.client.post("/subtask/A1/reset").get_json()
        self.assertEqual(d["previous_status"], "Running")

    def test_returns_subtask_task_branch(self):
        self._write_state(self._make_state())
        d = self.client.post("/subtask/A1/reset").get_json()
        self.assertEqual(d["subtask"], "A1")
        self.assertEqual(d["task"], "Task 0")
        self.assertEqual(d["branch"], "Branch A")

    def test_writes_heal_trigger(self):
        self._write_state(self._make_state())
        self.client.post("/subtask/A1/reset")
        import json as _json
        payload = _json.loads(self._heal_trigger_path.read_text())
        self.assertEqual(payload["subtask"], "A1")

    def test_returns_404_for_unknown(self):
        self._write_state(self._make_state())
        r = self.client.post("/subtask/ZZZ/reset")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# POST /subtasks/bulk-reset  (TASK-141)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# POST /subtasks/bulk-verify  (TASK-146)
# ---------------------------------------------------------------------------

class TestSubtasksBulkVerify(_Base):

    def test_valid_verify_returns_ok(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        r = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": ["A1", "A2"]},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])

    def test_verified_count_correct(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": ["A1", "A2"]},
                             content_type="application/json").get_json()
        self.assertEqual(d["verified_count"], 2)

    def test_already_verified_skipped(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": ["A1", "A2"]},
                             content_type="application/json").get_json()
        self.assertEqual(d["skipped_count"], 1)
        self.assertEqual(d["verified_count"], 1)

    def test_skip_non_running_flag(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": ["A1", "A2"], "skip_non_running": True},
                             content_type="application/json").get_json()
        self.assertEqual(d["verified_count"], 1)  # only A1 (Running)
        self.assertEqual(d["skipped_count"], 1)   # A2 (Pending) skipped

    def test_not_found_reported(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": ["A1", "Z9"]},
                             content_type="application/json").get_json()
        self.assertIn("Z9", d["not_found"])

    def test_missing_body_returns_400(self):
        self._write_state(self._make_state())
        r = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": []},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_state_persisted(self):
        self._write_state(self._make_state({"A1": "Running"}))
        self.client.post("/subtasks/bulk-verify",
                         json={"subtasks": ["A1"]},
                         content_type="application/json")
        import json
        state = json.loads(self._state_path.read_text())
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Verified")

    def test_verified_list_returned(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": ["A1"]},
                             content_type="application/json").get_json()
        self.assertIn("A1", d["verified"])


class TestSubtasksBulkReset(_Base):

    def test_valid_reset_returns_ok(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        r = self.client.post("/subtasks/bulk-reset",
                             json={"subtasks": ["A1", "A2"]})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_reset_count_correct(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/subtasks/bulk-reset",
                             json={"subtasks": ["A1", "A2"]}).get_json()
        self.assertEqual(d["reset_count"], 2)

    def test_skips_verified_by_default(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Verified"}))
        d = self.client.post("/subtasks/bulk-reset",
                             json={"subtasks": ["A1", "A2"]}).get_json()
        self.assertEqual(d["reset_count"], 1)
        self.assertEqual(d["skipped_count"], 1)

    def test_skip_verified_false_resets_verified(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.post("/subtasks/bulk-reset",
                             json={"subtasks": ["A1"], "skip_verified": False}).get_json()
        self.assertEqual(d["reset_count"], 1)

    def test_not_found_names_returned(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/subtasks/bulk-reset",
                             json={"subtasks": ["A1", "ZZZ"]}).get_json()
        self.assertIn("ZZZ", d["not_found"])

    def test_reset_names_in_response(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/subtasks/bulk-reset",
                             json={"subtasks": ["A1"]}).get_json()
        self.assertIn("A1", d["reset"])

    def test_missing_subtasks_field_returns_400(self):
        self._write_state(self._make_state())
        r = self.client.post("/subtasks/bulk-reset", json={})
        self.assertEqual(r.status_code, 400)

    def test_empty_list_returns_400(self):
        self._write_state(self._make_state())
        r = self.client.post("/subtasks/bulk-reset", json={"subtasks": []})
        self.assertEqual(r.status_code, 400)

    def test_subtask_set_to_pending_in_state(self):
        self._write_state(self._make_state({"A1": "Running"}))
        self.client.post("/subtasks/bulk-reset", json={"subtasks": ["A1"]})
        state = json.loads(self._state_path.read_text())
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Pending")

    def test_reset_clears_output_and_shadow(self):
        state = self._make_state({"A1": "Running"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = "old"
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["shadow"] = "s"
        self._write_state(state)
        self.client.post("/subtasks/bulk-reset", json={"subtasks": ["A1"]})
        saved = json.loads(self._state_path.read_text())
        st = saved["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st.get("output", ""), "")
        self.assertNotIn("shadow", st)

    def test_reset_review_status(self):
        self._write_state(self._make_state({"A1": "Review"}))
        d = self.client.post("/subtasks/bulk-reset",
                             json={"subtasks": ["A1"]}).get_json()
        self.assertEqual(d["reset_count"], 1)


class TestSubtasksBulkVerifyExtra(_Base):

    def test_verify_review_status_advanced(self):
        self._write_state(self._make_state({"A1": "Review"}))
        d = self.client.post("/subtasks/bulk-verify",
                             json={"subtasks": ["A1"]}).get_json()
        self.assertEqual(d["verified_count"], 1)
        state = json.loads(self._state_path.read_text())
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Verified")

    def test_verify_missing_subtasks_field_returns_400(self):
        self._write_state(self._make_state())
        r = self.client.post("/subtasks/bulk-verify", json={})
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# POST /webhook  (TASK-078)
# ---------------------------------------------------------------------------

class TestWebhook(_Base):

    def test_no_webhook_url_returns_ok_false(self):
        self._write_state(self._make_state())
        # Explicitly write settings without WEBHOOK_URL
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text('{}', encoding="utf-8")
        r = self.client.post("/webhook")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertFalse(d["ok"])
        self.assertIn("reason", d)

    def test_webhook_url_set_triggers_post(self):
        from unittest.mock import patch, MagicMock
        self._write_state(self._make_state({"A1": "Verified"}))
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text('{"WEBHOOK_URL": "http://example.com/hook"}', encoding="utf-8")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            r = self.client.post("/webhook")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(d["ok"])
        self.assertTrue(d["sent"])

    def test_webhook_payload_has_required_keys(self):
        from unittest.mock import patch, MagicMock
        self._write_state(self._make_state({"A1": "Verified"}))
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text('{"WEBHOOK_URL": "http://example.com/hook"}', encoding="utf-8")
        captured = {}
        def fake_urlopen(req, timeout=10):
            import json as _json
            captured["body"] = _json.loads(req.data)
            m = MagicMock()
            m.__enter__ = lambda s: s
            m.__exit__ = MagicMock(return_value=False)
            return m
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.client.post("/webhook")
        body = captured.get("body", {})
        for key in ("event", "step", "total", "verified", "pct", "timestamp"):
            self.assertIn(key, body)
        self.assertEqual(body["event"], "complete")


# ---------------------------------------------------------------------------
# GET /subtask/<id>/output  (TASK-079)
# ---------------------------------------------------------------------------

class TestGetSubtaskOutput(_Base):

    def test_returns_404_for_unknown(self):
        self._write_state(self._make_state())
        r = self.client.get("/subtask/ZZZ/output")
        self.assertEqual(r.status_code, 404)

    def test_returns_plain_text(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = "hello\nworld"
        self._write_state(state)
        r = self.client.get("/subtask/A1/output")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/plain", r.content_type)
        self.assertEqual(r.data.decode("utf-8"), "hello\nworld")

    def test_empty_output_returns_empty_body(self):
        state = self._make_state({"A1": "Pending"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"].pop("output", None)
        self._write_state(state)
        r = self.client.get("/subtask/A1/output")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, b"")


# ---------------------------------------------------------------------------
# POST /tasks/<id>/reset
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# POST /tasks/<task_id>/bulk-verify  (TASK-149)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET /tasks/<task_id>/progress  (TASK-151)
# ---------------------------------------------------------------------------

class TestGetTaskProgress(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        r = self.client.get("/tasks/Task 0/progress")
        self.assertEqual(r.status_code, 200)

    def test_required_fields(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        for key in ("task", "status", "verified", "total", "pct", "running", "pending", "review"):
            self.assertIn(key, d)

    def test_task_field(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertEqual(d["task"], "Task 0")

    def test_counts_correct(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertEqual(d["verified"], 1)
        self.assertEqual(d["running"], 1)
        self.assertEqual(d["pending"], 1)
        self.assertEqual(d["total"], 3)

    def test_pct_correct(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertAlmostEqual(d["pct"], 50.0)

    def test_pct_zero_when_no_subtasks(self):
        state = self._make_state()
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"] = {}
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertEqual(d["pct"], 0.0)
        self.assertEqual(d["total"], 0)

    def test_404_unknown_task(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/No Such Task/progress")
        self.assertEqual(r.status_code, 404)

    def test_branches_field_present(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertIn("branches", d)
        self.assertIsInstance(d["branches"], list)

    def test_branches_field_has_branch_entry(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertEqual(len(d["branches"]), 1)
        br = d["branches"][0]
        for key in ("branch", "verified", "running", "pending", "review", "total", "pct"):
            self.assertIn(key, br)

    def test_branches_counts_correct(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        br = d["branches"][0]
        self.assertEqual(br["verified"], 1)
        self.assertEqual(br["running"], 1)
        self.assertEqual(br["total"], 2)

    def test_branches_pct_correct(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/tasks/Task 0/progress").get_json()
        br = d["branches"][0]
        self.assertAlmostEqual(br["pct"], 50.0)

    def test_multi_branch_aggregation(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["branches"]["Branch B"] = {
            "subtasks": {
                "B1": {"status": "Verified", "output": "", "description": ""},
                "B2": {"status": "Pending", "output": "", "description": ""},
            }
        }
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/progress").get_json()
        # Branch A: 1 verified/1 total; Branch B: 1 verified/2 total
        self.assertEqual(d["total"], 3)
        self.assertEqual(d["verified"], 2)
        self.assertEqual(len(d["branches"]), 2)

    def test_review_status_counted_in_response(self):
        state = self._make_state({"A1": "Review", "A2": "Pending"})
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertEqual(d["review"], 1)
        self.assertEqual(d["branches"][0]["review"], 1)

    def test_no_branches_returns_empty_branches_list(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [], "branches": {}}}}
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/progress").get_json()
        self.assertEqual(d["branches"], [])
        self.assertEqual(d["total"], 0)


class TestPostTaskBulkVerify(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        r = self.client.post("/tasks/Task 0/bulk-verify")
        self.assertEqual(r.status_code, 200)

    def test_returns_ok(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertTrue(d["ok"])

    def test_verified_count_correct(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertEqual(d["verified_count"], 2)

    def test_already_verified_skipped(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertEqual(d["skipped_count"], 1)
        self.assertEqual(d["verified_count"], 1)

    def test_skip_non_running_flag(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/tasks/Task 0/bulk-verify",
                             json={"skip_non_running": True},
                             content_type="application/json").get_json()
        self.assertEqual(d["verified_count"], 1)
        self.assertEqual(d["skipped_count"], 1)

    def test_state_persisted(self):
        self._write_state(self._make_state({"A1": "Running"}))
        self.client.post("/tasks/Task 0/bulk-verify")
        import json as _json
        state = _json.loads(self._state_path.read_text())
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Verified")

    def test_task_status_set_verified(self):
        self._write_state(self._make_state({"A1": "Running"}))
        self.client.post("/tasks/Task 0/bulk-verify")
        import json as _json
        state = _json.loads(self._state_path.read_text())
        self.assertEqual(state["dag"]["Task 0"]["status"], "Verified")

    def test_404_for_unknown_task(self):
        self._write_state(self._make_state())
        r = self.client.post("/tasks/No Such Task/bulk-verify")
        self.assertEqual(r.status_code, 404)

    def test_task_field_in_response(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertEqual(d["task"], "Task 0")

    def test_all_already_verified_returns_zero_verified(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Verified"}))
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertEqual(d["verified_count"], 0)
        self.assertEqual(d["skipped_count"], 2)

    def test_all_verified_does_not_change_task_status(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["status"] = "Running"
        self._write_state(state)
        self.client.post("/tasks/Task 0/bulk-verify")
        import json as _json
        s = _json.loads(self._state_path.read_text())
        self.assertEqual(s["dag"]["Task 0"]["status"], "Running")

    def test_empty_subtasks_returns_zero_counts(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [],
                 "branches": {"Branch A": {"subtasks": {}}}}}}
        self._write_state(state)
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertEqual(d["verified_count"], 0)
        self.assertEqual(d["skipped_count"], 0)

    def test_no_branches_returns_zero_counts(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [], "branches": {}}}}
        self._write_state(state)
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertEqual(d["verified_count"], 0)
        self.assertEqual(d["skipped_count"], 0)

    def test_review_subtask_verified_by_default(self):
        self._write_state(self._make_state({"A1": "Review"}))
        d = self.client.post("/tasks/Task 0/bulk-verify").get_json()
        self.assertEqual(d["verified_count"], 1)

    def test_pending_skipped_with_skip_non_running_flag(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        d = self.client.post("/tasks/Task 0/bulk-verify",
                             json={"skip_non_running": True},
                             content_type="application/json").get_json()
        self.assertEqual(d["verified_count"], 0)
        self.assertEqual(d["skipped_count"], 1)


class TestPostTaskReset(_Base):

    def test_reset_valid_task_returns_ok(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        r = self.client.post("/tasks/Task 0/reset")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["task"], "Task 0")

    def test_reset_invalid_task_returns_404(self):
        self._write_state(self._make_state())
        r = self.client.post("/tasks/Task 999/reset")
        self.assertEqual(r.status_code, 404)

    def test_reset_counts_reset_subtasks(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/tasks/Task 0/reset").get_json()
        self.assertEqual(d["reset_count"], 2)

    def test_reset_skips_verified_subtasks(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Verified"}))
        d = self.client.post("/tasks/Task 0/reset").get_json()
        self.assertEqual(d["reset_count"], 1)
        self.assertEqual(d["skipped_count"], 1)

    def test_reset_sets_subtasks_to_pending(self):
        self._write_state(self._make_state({"A1": "Running"}))
        self.client.post("/tasks/Task 0/reset")
        state = json.loads(self._state_path.read_text())
        st = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Pending")

    def test_reset_clears_output(self):
        state = self._make_state({"A1": "Running"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = "old output"
        self._write_state(state)
        self.client.post("/tasks/Task 0/reset")
        new_state = json.loads(self._state_path.read_text())
        st = new_state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st.get("output", ""), "")


class TestPostTaskBulkReset(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        r = self.client.post("/tasks/Task 0/bulk-reset")
        self.assertEqual(r.status_code, 200)

    def test_returns_ok(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/tasks/Task 0/bulk-reset").get_json()
        self.assertTrue(d["ok"])

    def test_404_for_unknown_task(self):
        self._write_state(self._make_state())
        r = self.client.post("/tasks/No Such Task/bulk-reset")
        self.assertEqual(r.status_code, 404)

    def test_reset_count_correct(self):
        self._write_state(self._make_state({"A1": "Running", "A2": "Pending"}))
        d = self.client.post("/tasks/Task 0/bulk-reset").get_json()
        self.assertEqual(d["reset_count"], 2)

    def test_verified_skipped_by_default(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.post("/tasks/Task 0/bulk-reset").get_json()
        self.assertEqual(d["reset_count"], 1)
        self.assertEqual(d["skipped_count"], 1)

    def test_include_verified_flag_resets_all(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.post("/tasks/Task 0/bulk-reset",
                             json={"include_verified": True},
                             content_type="application/json").get_json()
        self.assertEqual(d["reset_count"], 2)
        self.assertEqual(d["skipped_count"], 0)

    def test_task_field_in_response(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.post("/tasks/Task 0/bulk-reset").get_json()
        self.assertEqual(d["task"], "Task 0")

    def test_state_persisted(self):
        self._write_state(self._make_state({"A1": "Running"}))
        self.client.post("/tasks/Task 0/bulk-reset")
        s = json.loads(self._state_path.read_text())
        st = s["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Pending")

    def test_task_status_set_pending_when_reset(self):
        state = self._make_state({"A1": "Running"})
        state["dag"]["Task 0"]["status"] = "Running"
        self._write_state(state)
        self.client.post("/tasks/Task 0/bulk-reset")
        s = json.loads(self._state_path.read_text())
        self.assertEqual(s["dag"]["Task 0"]["status"], "Pending")

    def test_all_verified_no_change_to_task_status(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["status"] = "Verified"
        self._write_state(state)
        self.client.post("/tasks/Task 0/bulk-reset")
        s = json.loads(self._state_path.read_text())
        self.assertEqual(s["dag"]["Task 0"]["status"], "Verified")

    def test_all_verified_include_verified_resets_all(self):
        state = self._make_state({"A1": "Verified", "A2": "Verified"})
        state["dag"]["Task 0"]["status"] = "Verified"
        self._write_state(state)
        d = self.client.post("/tasks/Task 0/bulk-reset",
                             json={"include_verified": True},
                             content_type="application/json").get_json()
        self.assertEqual(d["reset_count"], 2)
        self.assertEqual(d["skipped_count"], 0)

    def test_empty_task_no_branches_returns_zero_counts(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [], "branches": {}}}}
        self._write_state(state)
        d = self.client.post("/tasks/Task 0/bulk-reset").get_json()
        self.assertEqual(d["reset_count"], 0)
        self.assertEqual(d["skipped_count"], 0)

    def test_task_with_branch_but_no_subtasks_returns_zero_counts(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [],
                 "branches": {"Branch A": {"subtasks": {}}}}}}
        self._write_state(state)
        d = self.client.post("/tasks/Task 0/bulk-reset").get_json()
        self.assertEqual(d["reset_count"], 0)
        self.assertEqual(d["skipped_count"], 0)


# ---------------------------------------------------------------------------
# GET /tasks/<id>/timeline  (TASK-139)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET /tasks/<task_id>/subtasks  (TASK-145)
# ---------------------------------------------------------------------------

class TestGetTaskSubtasks(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        r = self.client.get("/tasks/Task 0/subtasks")
        self.assertEqual(r.status_code, 200)

    def test_returns_json_envelope(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/subtasks").get_json()
        for key in ("task", "subtasks", "count", "total", "page", "limit", "pages"):
            self.assertIn(key, d)

    def test_task_field_matches(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/subtasks").get_json()
        self.assertEqual(d["task"], "Task 0")

    def test_subtask_fields(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/subtasks").get_json()
        self.assertGreater(len(d["subtasks"]), 0)
        row = d["subtasks"][0]
        for key in ("subtask", "branch", "status", "output_length"):
            self.assertIn(key, row)

    def test_status_filter(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/tasks/Task 0/subtasks?status=Verified").get_json()
        self.assertTrue(all(r["status"] == "Verified" for r in d["subtasks"]))

    def test_branch_filter(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/subtasks?branch=Branch+A").get_json()
        self.assertTrue(all(r["branch"] == "Branch A" for r in d["subtasks"]))

    def test_output_included_when_requested(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/subtasks?output=1").get_json()
        self.assertIn("output", d["subtasks"][0])

    def test_404_for_unknown_task(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/No Such Task/subtasks")
        self.assertEqual(r.status_code, 404)

    def test_pagination(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/tasks/Task 0/subtasks?limit=1&page=1").get_json()
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["limit"], 1)
        self.assertGreaterEqual(d["pages"], 1)

    def test_empty_subtasks_returns_zero_count(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [],
                 "branches": {"Branch A": {"subtasks": {}}}}}}
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/subtasks").get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["count"], 0)
        self.assertEqual(d["subtasks"], [])

    def test_task_with_no_branches_returns_zero(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [], "branches": {}}}}
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/subtasks").get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["subtasks"], [])

    def test_pagination_page_beyond_last_returns_empty(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/tasks/Task 0/subtasks?limit=1&page=99").get_json()
        self.assertEqual(d["count"], 0)
        self.assertEqual(d["total"], 2)
        self.assertEqual(d["subtasks"], [])

    def test_pagination_zero_total_pages_is_one(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [],
                 "branches": {"Branch A": {"subtasks": {}}}}}}
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/subtasks?limit=5&page=1").get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["pages"], 1)

    def test_status_filter_no_match_returns_empty(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/subtasks?status=Running").get_json()
        self.assertEqual(d["count"], 0)
        self.assertEqual(d["subtasks"], [])

    def test_no_limit_pages_always_one(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending", "A3": "Running"}))
        d = self.client.get("/tasks/Task 0/subtasks").get_json()
        self.assertEqual(d["pages"], 1)
        self.assertEqual(d["count"], d["total"])


class TestGetTaskBranches(_Base):

    def test_returns_200(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.get("/tasks/Task 0/branches")
        self.assertEqual(r.status_code, 200)

    def test_404_for_unknown_task(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/No Such Task/branches")
        self.assertEqual(r.status_code, 404)

    def test_returns_envelope(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/branches").get_json()
        for key in ("task", "branches", "count", "total", "page", "limit", "pages"):
            self.assertIn(key, d)

    def test_task_field_matches(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/branches").get_json()
        self.assertEqual(d["task"], "Task 0")

    def test_branch_fields(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Running"}))
        d = self.client.get("/tasks/Task 0/branches").get_json()
        self.assertGreater(len(d["branches"]), 0)
        br = d["branches"][0]
        for key in ("branch", "subtask_count", "verified", "running", "pending", "pct", "status"):
            self.assertIn(key, br)

    def test_verified_count_correct(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/tasks/Task 0/branches").get_json()
        br = d["branches"][0]
        self.assertEqual(br["verified"], 1)
        self.assertEqual(br["pending"], 1)
        self.assertEqual(br["subtask_count"], 2)

    def test_status_filter(self):
        self._write_state(self._make_state({"A1": "Running"}))
        d = self.client.get("/tasks/Task 0/branches?status=Running").get_json()
        self.assertEqual(d["count"], 1)

    def test_status_filter_no_match(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        d = self.client.get("/tasks/Task 0/branches?status=Running").get_json()
        self.assertEqual(d["count"], 0)

    def test_no_branches_returns_zero(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [], "branches": {}}}}
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/branches").get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["branches"], [])

    def test_pagination(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/branches?limit=1&page=1").get_json()
        self.assertEqual(d["count"], 1)
        self.assertGreaterEqual(d["pages"], 1)

    def test_pct_computed(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/tasks/Task 0/branches").get_json()
        br = d["branches"][0]
        self.assertEqual(br["pct"], 50.0)


class TestGetTaskTimeline(_Base):

    def test_timeline_returns_200(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        r = self.client.get("/tasks/Task 0/timeline")
        self.assertEqual(r.status_code, 200)

    def test_timeline_unknown_task_returns_404(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/Task 999/timeline")
        self.assertEqual(r.status_code, 404)

    def test_timeline_has_task_field(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        self.assertEqual(d["task"], "Task 0")

    def test_timeline_has_subtasks_list(self):
        self._write_state(self._make_state({"A1": "Pending", "A2": "Verified"}))
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        self.assertIsInstance(d["subtasks"], list)
        self.assertEqual(d["count"], 2)

    def test_timeline_subtask_fields(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        st = d["subtasks"][0]
        for key in ("subtask", "branch", "status", "history", "last_update"):
            self.assertIn(key, st)

    def test_timeline_has_step_field(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        self.assertIn("step", d)

    def test_timeline_sorted_by_last_update(self):
        state = self._make_state({"A1": "Pending", "A2": "Pending"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["last_update"] = 10
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A2"]["last_update"] = 5
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        updates = [st["last_update"] for st in d["subtasks"]]
        self.assertEqual(updates, sorted(updates))

    def test_timeline_no_branches_returns_empty_list(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "depends_on": [], "branches": {}}}}
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        self.assertEqual(d["subtasks"], [])
        self.assertEqual(d["count"], 0)

    def test_timeline_history_entries_present(self):
        state = self._make_state({"A1": "Verified"})
        state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["history"] = [
            {"step": 1, "status": "Running"},
            {"step": 2, "status": "Verified"},
        ]
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        hist = d["subtasks"][0]["history"]
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0]["status"], "Running")

    def test_timeline_multi_branch_count(self):
        state = self._make_state({"A1": "Verified", "A2": "Pending"})
        state["dag"]["Task 0"]["branches"]["Branch B"] = {
            "subtasks": {"B1": {"status": "Running", "output": "", "description": "desc B1"}}
        }
        self._write_state(state)
        d = self.client.get("/tasks/Task 0/timeline").get_json()
        self.assertEqual(d["count"], 3)
        branches = {st["branch"] for st in d["subtasks"]}
        self.assertIn("Branch B", branches)


# ---------------------------------------------------------------------------
# GET /tasks/export  (TASK-143)
# ---------------------------------------------------------------------------

class TestGetTasksExportAll(_Base):

    def test_csv_returns_200(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        r = self.client.get("/tasks/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_csv_has_header(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        text = self.client.get("/tasks/export").data.decode()
        self.assertIn("task,status,verified,total,pct", text)

    def test_csv_has_task_row(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        text = self.client.get("/tasks/export").data.decode()
        self.assertIn("Task 0", text)

    def test_json_format(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/export?format=json").get_json()
        self.assertIn("tasks", d)
        self.assertIn("count", d)

    def test_json_row_fields(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        d = self.client.get("/tasks/export?format=json").get_json()
        row = d["tasks"][0]
        for key in ("task", "status", "verified", "total", "pct"):
            self.assertIn(key, row)

    def test_json_verified_count(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        d = self.client.get("/tasks/export?format=json").get_json()
        row = d["tasks"][0]
        self.assertEqual(row["verified"], 1)
        self.assertEqual(row["total"], 2)

    def test_csv_attachment_header(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        r = self.client.get("/tasks/export")
        self.assertIn("attachment", r.headers.get("Content-Disposition", ""))


# ---------------------------------------------------------------------------
# GET /tasks/<id>/export
# ---------------------------------------------------------------------------

class TestGetTaskExport(_Base):

    def test_export_csv_default_returns_200(self):
        self._write_state(self._make_state({"A1": "Verified", "A2": "Pending"}))
        r = self.client.get("/tasks/Task 0/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_export_csv_contains_header(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.get("/tasks/Task 0/export")
        text = r.data.decode()
        self.assertIn("subtask,branch,status", text)

    def test_export_csv_contains_subtask_row(self):
        self._write_state(self._make_state({"A1": "Verified"}))
        r = self.client.get("/tasks/Task 0/export")
        text = r.data.decode()
        self.assertIn("A1", text)
        self.assertIn("Verified", text)

    def test_export_json_format(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        r = self.client.get("/tasks/Task 0/export?format=json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["task"], "Task 0")
        self.assertIsInstance(d["subtasks"], list)

    def test_export_json_subtask_fields(self):
        self._write_state(self._make_state({"A1": "Running"}))
        r = self.client.get("/tasks/Task 0/export?format=json")
        row = r.get_json()["subtasks"][0]
        self.assertIn("subtask", row)
        self.assertIn("branch", row)
        self.assertIn("status", row)
        self.assertIn("output_length", row)

    def test_export_unknown_task_returns_404(self):
        self._write_state(self._make_state())
        r = self.client.get("/tasks/Task 999/export")
        self.assertEqual(r.status_code, 404)

    def test_export_csv_attachment_header(self):
        self._write_state(self._make_state({"A1": "Pending"}))
        r = self.client.get("/tasks/Task 0/export")
        self.assertIn("attachment", r.headers.get("Content-Disposition", ""))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
