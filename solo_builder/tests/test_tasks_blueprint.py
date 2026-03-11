"""Tests for tasks blueprint — GET /tasks, /tasks/export, /tasks/<id>,
/tasks/<id>/export, /tasks/<id>/trigger, /tasks/<id>/reset,
/tasks/<id>/bulk-reset, /tasks/<id>/bulk-verify,
/tasks/<id>/progress, /tasks/<id>/branches, /tasks/<id>/subtasks,
/tasks/<id>/timeline, /graph, /priority (TASK-399)."""
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


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

def _make_dag():
    return {
        "T0": {
            "status": "Pending",
            "depends_on": [],
            "branches": {
                "b0": {
                    "subtasks": {
                        "s1": {
                            "status": "Pending",
                            "output": "",
                            "description": "first",
                            "history": [],
                            "last_update": 0,
                        },
                        "s2": {
                            "status": "Verified",
                            "output": "done",
                            "description": "second",
                            "history": [{"step": 1, "status": "Verified"}],
                            "last_update": 1,
                        },
                    }
                },
                "b1": {
                    "subtasks": {
                        "s3": {
                            "status": "Running",
                            "output": "wip",
                            "description": "third",
                            "history": [],
                            "last_update": 0,
                        }
                    }
                },
            },
        },
        "T1": {
            "status": "Verified",
            "depends_on": ["T0"],
            "branches": {
                "c0": {
                    "subtasks": {
                        "s4": {
                            "status": "Verified",
                            "output": "ok",
                            "description": "fourth",
                            "history": [],
                            "last_update": 2,
                        }
                    }
                }
            },
        },
    }


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")

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

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_state(self, dag=None, step=0):
        state = {"step": step, "dag": dag if dag is not None else _make_dag()}
        self._state_path.write_text(json.dumps(state), encoding="utf-8")


# ---------------------------------------------------------------------------
# GET /tasks
# ---------------------------------------------------------------------------

class TestListTasks(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/tasks")
        self.assertEqual(r.status_code, 200)

    def test_returns_all_tasks(self):
        self._write_state()
        data = self.client.get("/tasks").get_json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["tasks"]), 2)

    def test_task_filter(self):
        self._write_state()
        data = self.client.get("/tasks?task=T0").get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["tasks"][0]["id"], "T0")

    def test_pagination_limit(self):
        self._write_state()
        data = self.client.get("/tasks?limit=1&page=1").get_json()
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["pages"], 2)

    def test_pagination_page2(self):
        self._write_state()
        data = self.client.get("/tasks?limit=1&page=2").get_json()
        self.assertEqual(len(data["tasks"]), 1)

    def test_empty_dag_returns_zero(self):
        self._write_state(dag={})
        data = self.client.get("/tasks").get_json()
        self.assertEqual(data["total"], 0)


# ---------------------------------------------------------------------------
# GET /tasks/<id>
# ---------------------------------------------------------------------------

class TestGetTask(_Base):

    def test_returns_task_data(self):
        self._write_state()
        data = self.client.get("/tasks/T0").get_json()
        self.assertIn("branches", data)
        self.assertEqual(data["id"], "T0")

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.get("/tasks/MISSING")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /tasks/export
# ---------------------------------------------------------------------------

class TestExportAllTasks(_Base):

    def test_csv_format_default(self):
        self._write_state()
        r = self.client.get("/tasks/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)
        self.assertIn("tasks.csv", r.headers.get("Content-Disposition", ""))

    def test_json_format(self):
        self._write_state()
        r = self.client.get("/tasks/export?format=json")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("tasks", data)
        self.assertIn("count", data)

    def test_csv_contains_header(self):
        self._write_state()
        r = self.client.get("/tasks/export")
        text = r.data.decode()
        self.assertIn("task,status,verified,total,pct", text)

    def test_empty_dag_csv(self):
        self._write_state(dag={})
        r = self.client.get("/tasks/export")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# GET /tasks/<id>/export
# ---------------------------------------------------------------------------

class TestExportTask(_Base):

    def test_csv_format(self):
        self._write_state()
        r = self.client.get("/tasks/T0/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_json_format(self):
        self._write_state()
        r = self.client.get("/tasks/T0/export?format=json")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["task"], "T0")
        self.assertIn("subtasks", data)

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.get("/tasks/MISSING/export")
        self.assertEqual(r.status_code, 404)

    def test_content_disposition_has_task_id(self):
        self._write_state()
        r = self.client.get("/tasks/T0/export")
        self.assertIn("T0", r.headers.get("Content-Disposition", ""))


# ---------------------------------------------------------------------------
# POST /tasks/<id>/trigger
# ---------------------------------------------------------------------------

class TestTriggerTask(_Base):

    def test_returns_202(self):
        self._write_state()
        r = self.client.post("/tasks/T0/trigger")
        self.assertEqual(r.status_code, 202)

    def test_returns_accepted_true(self):
        self._write_state()
        data = self.client.post("/tasks/T0/trigger").get_json()
        self.assertTrue(data["accepted"])

    def test_pending_subtasks_listed(self):
        self._write_state()
        data = self.client.post("/tasks/T0/trigger").get_json()
        # s1 is Pending (s2 is Verified, s3 is Running — both excluded)
        self.assertEqual(data["pending_count"], 1)
        self.assertIn("b0/s1", data["pending_subtasks"])

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.post("/tasks/MISSING/trigger")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# POST /tasks/<id>/reset
# ---------------------------------------------------------------------------

class TestResetTask(_Base):

    def test_returns_200_and_ok(self):
        self._write_state()
        data = self.client.post("/tasks/T0/reset").get_json()
        self.assertTrue(data["ok"])

    def test_non_verified_subtasks_reset(self):
        self._write_state()
        self.client.post("/tasks/T0/reset")
        state = json.loads(self._state_path.read_text())
        # s1 (Pending) and s3 (Running) become Pending; s2 (Verified) stays
        s1 = state["dag"]["T0"]["branches"]["b0"]["subtasks"]["s1"]
        s3 = state["dag"]["T0"]["branches"]["b1"]["subtasks"]["s3"]
        self.assertEqual(s1["status"], "Pending")
        self.assertEqual(s3["status"], "Pending")

    def test_verified_subtasks_skipped(self):
        self._write_state()
        data = self.client.post("/tasks/T0/reset").get_json()
        # s2 in T0 is Verified; s4 in T1 (different task)
        self.assertGreaterEqual(data["skipped_count"], 1)

    def test_reset_count_correct(self):
        self._write_state()
        data = self.client.post("/tasks/T0/reset").get_json()
        # s1 (Pending) + s3 (Running) = 2 resets
        self.assertEqual(data["reset_count"], 2)

    def test_output_cleared_after_reset(self):
        self._write_state()
        self.client.post("/tasks/T0/reset")
        state = json.loads(self._state_path.read_text())
        s3 = state["dag"]["T0"]["branches"]["b1"]["subtasks"]["s3"]
        self.assertEqual(s3["output"], "")

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.post("/tasks/MISSING/reset")
        self.assertEqual(r.status_code, 404)

    def test_write_error_returns_500(self):
        self._write_state()
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            r = self.client.post("/tasks/T0/reset")
        self.assertEqual(r.status_code, 500)
        self.assertFalse(r.get_json()["ok"])


# ---------------------------------------------------------------------------
# POST /tasks/<id>/bulk-reset
# ---------------------------------------------------------------------------

class TestBulkResetTask(_Base):

    def test_returns_ok(self):
        self._write_state()
        data = self.client.post("/tasks/T0/bulk-reset", json={}).get_json()
        self.assertTrue(data["ok"])

    def test_skip_verified_by_default(self):
        self._write_state()
        data = self.client.post("/tasks/T0/bulk-reset", json={}).get_json()
        # s2 is Verified, should be skipped
        self.assertGreaterEqual(data["skipped_count"], 1)

    def test_include_verified_resets_all(self):
        self._write_state()
        data = self.client.post(
            "/tasks/T0/bulk-reset", json={"include_verified": True}
        ).get_json()
        self.assertEqual(data["skipped_count"], 0)

    def test_task_status_set_pending_when_resets_occur(self):
        self._write_state()
        self.client.post("/tasks/T0/bulk-reset", json={})
        state = json.loads(self._state_path.read_text())
        self.assertEqual(state["dag"]["T0"]["status"], "Pending")

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.post("/tasks/MISSING/bulk-reset", json={})
        self.assertEqual(r.status_code, 404)

    def test_write_error_returns_500(self):
        self._write_state()
        with patch.object(Path, "write_text", side_effect=OSError("fail")):
            r = self.client.post("/tasks/T0/bulk-reset", json={})
        self.assertEqual(r.status_code, 500)


# ---------------------------------------------------------------------------
# POST /tasks/<id>/bulk-verify
# ---------------------------------------------------------------------------

class TestBulkVerifyTask(_Base):

    def test_returns_ok(self):
        self._write_state()
        data = self.client.post("/tasks/T0/bulk-verify", json={}).get_json()
        self.assertTrue(data["ok"])

    def test_non_verified_subtasks_advanced(self):
        self._write_state()
        data = self.client.post("/tasks/T0/bulk-verify", json={}).get_json()
        self.assertGreater(data["verified_count"], 0)

    def test_already_verified_skipped(self):
        self._write_state()
        data = self.client.post("/tasks/T0/bulk-verify", json={}).get_json()
        # s2 is already Verified
        self.assertGreaterEqual(data["skipped_count"], 1)

    def test_skip_non_running(self):
        self._write_state()
        data = self.client.post(
            "/tasks/T0/bulk-verify", json={"skip_non_running": True}
        ).get_json()
        # Only s3 (Running) should be verified; s1 (Pending) skipped
        self.assertEqual(data["verified_count"], 1)

    def test_task_status_set_verified_when_all_done(self):
        self._write_state()
        self.client.post("/tasks/T0/bulk-verify", json={})
        state = json.loads(self._state_path.read_text())
        self.assertEqual(state["dag"]["T0"]["status"], "Verified")

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.post("/tasks/MISSING/bulk-verify", json={})
        self.assertEqual(r.status_code, 404)

    def test_write_error_returns_500(self):
        self._write_state()
        with patch.object(Path, "write_text", side_effect=OSError("fail")):
            r = self.client.post("/tasks/T0/bulk-verify", json={})
        self.assertEqual(r.status_code, 500)


# ---------------------------------------------------------------------------
# GET /tasks/<id>/progress
# ---------------------------------------------------------------------------

class TestTaskProgress(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/tasks/T0/progress")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/tasks/T0/progress").get_json()
        for key in ("task", "status", "verified", "total", "pct", "running", "pending", "branches"):
            self.assertIn(key, data)

    def test_branch_rows_included(self):
        self._write_state()
        data = self.client.get("/tasks/T0/progress").get_json()
        self.assertGreaterEqual(len(data["branches"]), 2)

    def test_verified_count(self):
        self._write_state()
        data = self.client.get("/tasks/T0/progress").get_json()
        self.assertEqual(data["verified"], 1)  # only s2

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.get("/tasks/MISSING/progress")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /tasks/<id>/branches
# ---------------------------------------------------------------------------

class TestTaskBranches(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/tasks/T0/branches")
        self.assertEqual(r.status_code, 200)

    def test_branch_count(self):
        self._write_state()
        data = self.client.get("/tasks/T0/branches").get_json()
        self.assertEqual(data["total"], 2)

    def test_status_filter(self):
        self._write_state()
        # b0 has Pending; b1 has Running → dominant is Running
        data = self.client.get("/tasks/T0/branches?status=running").get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["branches"][0]["branch"], "b1")

    def test_pagination(self):
        self._write_state()
        data = self.client.get("/tasks/T0/branches?limit=1&page=1").get_json()
        self.assertEqual(len(data["branches"]), 1)
        self.assertEqual(data["pages"], 2)

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.get("/tasks/MISSING/branches")
        self.assertEqual(r.status_code, 404)

    def test_invalid_limit_falls_back_to_zero(self):
        self._write_state()
        data = self.client.get("/tasks/T0/branches?limit=abc").get_json()
        self.assertEqual(data["limit"], 0)

    def test_dominant_status_verified_when_all_verified(self):
        dag = {
            "T2": {
                "status": "Verified",
                "branches": {
                    "bv": {"subtasks": {"sv1": {"status": "Verified"}}}
                },
            }
        }
        self._write_state(dag=dag)
        data = self.client.get("/tasks/T2/branches").get_json()
        self.assertEqual(data["branches"][0]["status"], "Verified")

    def test_dominant_status_review_when_review_present(self):
        dag = {
            "TR": {
                "status": "Running",
                "branches": {
                    "br": {"subtasks": {
                        "r1": {"status": "Review"},
                        "r2": {"status": "Pending"},
                    }}
                },
            }
        }
        self._write_state(dag=dag)
        data = self.client.get("/tasks/TR/branches").get_json()
        self.assertEqual(data["branches"][0]["status"], "Review")


# ---------------------------------------------------------------------------
# GET /tasks/<id>/subtasks
# ---------------------------------------------------------------------------

class TestTaskSubtasks(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/tasks/T0/subtasks")
        self.assertEqual(r.status_code, 200)

    def test_returns_all_subtasks(self):
        self._write_state()
        data = self.client.get("/tasks/T0/subtasks").get_json()
        self.assertEqual(data["total"], 3)

    def test_branch_filter(self):
        self._write_state()
        data = self.client.get("/tasks/T0/subtasks?branch=b0").get_json()
        self.assertEqual(data["total"], 2)

    def test_status_filter(self):
        self._write_state()
        data = self.client.get("/tasks/T0/subtasks?status=Verified").get_json()
        self.assertEqual(data["total"], 1)

    def test_output_included_when_requested(self):
        self._write_state()
        data = self.client.get("/tasks/T0/subtasks?output=1").get_json()
        any_with_output = any("output" in s for s in data["subtasks"])
        self.assertTrue(any_with_output)

    def test_pagination(self):
        self._write_state()
        data = self.client.get("/tasks/T0/subtasks?limit=1&page=2").get_json()
        self.assertEqual(len(data["subtasks"]), 1)

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.get("/tasks/MISSING/subtasks")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /tasks/<id>/timeline
# ---------------------------------------------------------------------------

class TestTaskTimeline(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/tasks/T0/timeline")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/tasks/T0/timeline").get_json()
        self.assertIn("subtasks", data)
        self.assertIn("step", data)
        self.assertIn("count", data)

    def test_subtasks_sorted_by_last_update(self):
        self._write_state()
        data = self.client.get("/tasks/T0/timeline").get_json()
        updates = [s["last_update"] for s in data["subtasks"]]
        self.assertEqual(updates, sorted(updates))

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.get("/tasks/MISSING/timeline")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /graph
# ---------------------------------------------------------------------------

class TestGraph(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/graph")
        self.assertEqual(r.status_code, 200)

    def test_response_has_nodes_and_text(self):
        self._write_state()
        data = self.client.get("/graph").get_json()
        self.assertIn("nodes", data)
        self.assertIn("text", data)

    def test_empty_dag_returns_no_tasks_message(self):
        self._write_state(dag={})
        data = self.client.get("/graph").get_json()
        self.assertIn("No tasks", data["text"])

    def test_nodes_contain_task_names(self):
        self._write_state()
        data = self.client.get("/graph").get_json()
        names = [n["task"] for n in data["nodes"]]
        self.assertIn("T0", names)
        self.assertIn("T1", names)

    def test_text_includes_depends_on(self):
        self._write_state()
        data = self.client.get("/graph").get_json()
        self.assertIn("T0", data["text"])


# ---------------------------------------------------------------------------
# GET /priority
# ---------------------------------------------------------------------------

class TestPriority(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/priority")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/priority").get_json()
        self.assertIn("step", data)
        self.assertIn("count", data)
        self.assertIn("queue", data)

    def test_only_pending_or_running_included(self):
        self._write_state(step=5)
        data = self.client.get("/priority").get_json()
        for item in data["queue"]:
            self.assertIn(item["status"], ("Pending", "Running"))

    def test_deps_not_met_excluded(self):
        # T1 depends_on T0 which is not Verified
        self._write_state()
        data = self.client.get("/priority").get_json()
        tasks_in_queue = {item["task"] for item in data["queue"]}
        # T1 depends on T0 (Pending) → T1 subtasks not in queue
        self.assertNotIn("T1", tasks_in_queue)

    def test_queue_sorted_by_risk_desc(self):
        self._write_state(step=10)
        data = self.client.get("/priority").get_json()
        risks = [item["risk"] for item in data["queue"]]
        self.assertEqual(risks, sorted(risks, reverse=True))


if __name__ == "__main__":
    unittest.main()
