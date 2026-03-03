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
        self._trigger_path  = Path(self._tmp) / "state" / "run_trigger"
        self._verify_path   = Path(self._tmp) / "state" / "verify_trigger.json"
        self._describe_path = Path(self._tmp) / "state" / "describe_trigger.json"
        self._tools_path    = Path(self._tmp) / "state" / "tools_trigger.json"
        self._set_path      = Path(self._tmp) / "state" / "set_trigger.json"
        self._outputs_path  = Path(self._tmp) / "solo_builder_outputs.md"
        self._journal_path  = Path(self._tmp) / "journal.md"

        # Patch all module-level paths
        self._heartbeat_path = Path(self._tmp) / "state" / "step.txt"

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


# Error handlers
# ---------------------------------------------------------------------------

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
