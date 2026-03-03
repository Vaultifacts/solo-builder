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
        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "TRIGGER_PATH", new=self._trigger_path),
            patch.object(app_module, "VERIFY_TRIGGER", new=self._verify_path),
            patch.object(app_module, "DESCRIBE_TRIGGER", new=self._describe_path),
            patch.object(app_module, "TOOLS_TRIGGER", new=self._tools_path),
            patch.object(app_module, "SET_TRIGGER", new=self._set_path),
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
