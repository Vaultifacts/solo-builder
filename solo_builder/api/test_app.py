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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
