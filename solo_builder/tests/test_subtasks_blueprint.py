"""Tests for subtasks blueprint — GET /subtasks, /subtasks/export,
POST /subtasks/bulk-reset, /subtasks/bulk-verify,
GET /subtask/<id>, /subtask/<id>/output, POST /subtask/<id>/reset,
GET /timeline/<subtask>, /stalled (TASK-399)."""
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
# Shared base + helpers
# ---------------------------------------------------------------------------

def _make_dag(step=0):
    return {
        "T0": {
            "status": "Running",
            "branches": {
                "b0": {
                    "subtasks": {
                        "A1": {
                            "status": "Pending",
                            "output": "",
                            "description": "alpha",
                            "history": [],
                            "last_update": 0,
                            "tools": "",
                        },
                        "A2": {
                            "status": "Verified",
                            "output": "done",
                            "description": "beta",
                            "history": [{"step": 1, "status": "Verified"}],
                            "last_update": 1,
                            "tools": "",
                        },
                    }
                },
                "b1": {
                    "subtasks": {
                        "B1": {
                            "status": "Running",
                            "output": "wip",
                            "description": "gamma",
                            "history": [],
                            "last_update": 0,
                            "tools": "",
                        },
                        "B2": {
                            "status": "Review",
                            "output": "needs check",
                            "description": "delta",
                            "history": [],
                            "last_update": 0,
                            "tools": "",
                        },
                    }
                },
            },
        }
    }


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text(json.dumps({"STALL_THRESHOLD": 3}), encoding="utf-8")
        self._heal_trigger = sp / "heal_trigger.json"

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "HEAL_TRIGGER", new=self._heal_trigger),
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
# GET /subtasks
# ---------------------------------------------------------------------------

class TestSubtasksAll(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/subtasks")
        self.assertEqual(r.status_code, 200)

    def test_returns_all_subtasks(self):
        self._write_state()
        data = self.client.get("/subtasks").get_json()
        self.assertEqual(data["total"], 4)

    def test_task_filter(self):
        self._write_state()
        data = self.client.get("/subtasks?task=T0").get_json()
        self.assertEqual(data["total"], 4)

    def test_branch_filter(self):
        self._write_state()
        data = self.client.get("/subtasks?branch=b0").get_json()
        self.assertEqual(data["total"], 2)

    def test_status_filter(self):
        self._write_state()
        data = self.client.get("/subtasks?status=Verified").get_json()
        self.assertEqual(data["total"], 1)

    def test_name_filter(self):
        self._write_state()
        data = self.client.get("/subtasks?name=A1").get_json()
        self.assertEqual(data["total"], 1)

    def test_output_included_when_requested(self):
        self._write_state()
        data = self.client.get("/subtasks?output=1").get_json()
        any_with_output = any("output" in s for s in data["subtasks"])
        self.assertTrue(any_with_output)

    def test_pagination(self):
        self._write_state()
        data = self.client.get("/subtasks?limit=2&page=1").get_json()
        self.assertEqual(len(data["subtasks"]), 2)
        self.assertEqual(data["pages"], 2)

    def test_page2(self):
        self._write_state()
        data = self.client.get("/subtasks?limit=2&page=2").get_json()
        self.assertEqual(len(data["subtasks"]), 2)

    def test_min_age_filter_only_running(self):
        # B1 is Running with last_update=0, step=10 → age=10 >= min_age=3
        self._write_state(step=10)
        data = self.client.get("/subtasks?min_age=3").get_json()
        for st in data["subtasks"]:
            self.assertEqual(st["status"], "Running")

    def test_min_age_excludes_non_running(self):
        self._write_state(step=10)
        data = self.client.get("/subtasks?min_age=3").get_json()
        names = [s["subtask"] for s in data["subtasks"]]
        self.assertNotIn("A1", names)  # A1 is Pending, not Running

    def test_invalid_min_age_falls_back_to_zero(self):
        self._write_state()
        data = self.client.get("/subtasks?min_age=abc").get_json()
        self.assertGreater(data["total"], 0)

    def test_invalid_limit_falls_back_to_zero(self):
        self._write_state()
        data = self.client.get("/subtasks?limit=abc").get_json()
        self.assertEqual(data["limit"], 0)

    def test_invalid_page_falls_back_to_one(self):
        self._write_state()
        data = self.client.get("/subtasks?page=xyz").get_json()
        self.assertEqual(data["page"], 1)

    def test_response_has_count_field(self):
        self._write_state()
        data = self.client.get("/subtasks").get_json()
        self.assertIn("count", data)


# ---------------------------------------------------------------------------
# GET /subtasks/export
# ---------------------------------------------------------------------------

class TestSubtasksExport(_Base):

    def test_csv_default(self):
        self._write_state()
        r = self.client.get("/subtasks/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_csv_content_disposition(self):
        self._write_state()
        r = self.client.get("/subtasks/export")
        self.assertIn("subtasks.csv", r.headers.get("Content-Disposition", ""))

    def test_json_format(self):
        self._write_state()
        r = self.client.get("/subtasks/export?format=json")
        data = r.get_json()
        self.assertIn("subtasks", data)
        self.assertIn("total", data)

    def test_json_content_disposition(self):
        self._write_state()
        r = self.client.get("/subtasks/export?format=json")
        self.assertIn("subtasks.json", r.headers.get("Content-Disposition", ""))

    def test_status_filter_applied(self):
        self._write_state()
        r = self.client.get("/subtasks/export?format=json&status=Verified")
        data = r.get_json()
        self.assertEqual(data["total"], 1)

    def test_pagination_in_export(self):
        self._write_state()
        r = self.client.get("/subtasks/export?format=json&limit=2&page=1")
        data = r.get_json()
        self.assertEqual(len(data["subtasks"]), 2)

    def test_csv_contains_header(self):
        self._write_state()
        text = self.client.get("/subtasks/export").data.decode()
        self.assertIn("subtask,task,branch,status,output_length", text)


# ---------------------------------------------------------------------------
# POST /subtasks/bulk-reset
# ---------------------------------------------------------------------------

class TestSubtasksBulkReset(_Base):

    def test_returns_ok(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-reset", json={"subtasks": ["A1"]}
        ).get_json()
        self.assertTrue(data["ok"])

    def test_resets_specified_subtask(self):
        self._write_state()
        self.client.post("/subtasks/bulk-reset", json={"subtasks": ["B1"]})
        state = json.loads(self._state_path.read_text())
        b1 = state["dag"]["T0"]["branches"]["b1"]["subtasks"]["B1"]
        self.assertEqual(b1["status"], "Pending")
        self.assertEqual(b1["output"], "")

    def test_skip_verified_by_default(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-reset", json={"subtasks": ["A2"]}
        ).get_json()
        # A2 is Verified → should be skipped
        self.assertEqual(data["reset_count"], 0)
        self.assertEqual(data["skipped_count"], 1)

    def test_skip_verified_false_resets_verified(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-reset", json={"subtasks": ["A2"], "skip_verified": False}
        ).get_json()
        self.assertEqual(data["reset_count"], 1)

    def test_not_found_listed(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-reset", json={"subtasks": ["NOEXIST"]}
        ).get_json()
        self.assertIn("NOEXIST", data["not_found"])

    def test_missing_subtasks_field_returns_400(self):
        self._write_state()
        r = self.client.post("/subtasks/bulk-reset", json={})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_empty_list_returns_400(self):
        self._write_state()
        r = self.client.post("/subtasks/bulk-reset", json={"subtasks": []})
        self.assertEqual(r.status_code, 400)

    def test_write_error_returns_500(self):
        self._write_state()
        with patch.object(Path, "write_text", side_effect=OSError("fail")):
            r = self.client.post("/subtasks/bulk-reset", json={"subtasks": ["A1"]})
        self.assertEqual(r.status_code, 500)

    def test_reset_list_returned(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-reset", json={"subtasks": ["A1"]}
        ).get_json()
        self.assertIn("A1", data["reset"])


# ---------------------------------------------------------------------------
# POST /subtasks/bulk-verify
# ---------------------------------------------------------------------------

class TestSubtasksBulkVerify(_Base):

    def test_returns_ok(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-verify", json={"subtasks": ["A1"]}
        ).get_json()
        self.assertTrue(data["ok"])

    def test_advances_subtask_to_verified(self):
        self._write_state()
        self.client.post("/subtasks/bulk-verify", json={"subtasks": ["A1"]})
        state = json.loads(self._state_path.read_text())
        a1 = state["dag"]["T0"]["branches"]["b0"]["subtasks"]["A1"]
        self.assertEqual(a1["status"], "Verified")

    def test_already_verified_skipped(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-verify", json={"subtasks": ["A2"]}
        ).get_json()
        self.assertEqual(data["skipped_count"], 1)
        self.assertEqual(data["verified_count"], 0)

    def test_skip_non_running(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-verify",
            json={"subtasks": ["A1", "B1"], "skip_non_running": True},
        ).get_json()
        # A1 is Pending (skipped), B1 is Running (verified)
        self.assertEqual(data["verified_count"], 1)
        self.assertEqual(data["skipped_count"], 1)

    def test_not_found_listed(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-verify", json={"subtasks": ["NOEXIST"]}
        ).get_json()
        self.assertIn("NOEXIST", data["not_found"])

    def test_missing_subtasks_field_returns_400(self):
        self._write_state()
        r = self.client.post("/subtasks/bulk-verify", json={})
        self.assertEqual(r.status_code, 400)

    def test_empty_list_returns_400(self):
        self._write_state()
        r = self.client.post("/subtasks/bulk-verify", json={"subtasks": []})
        self.assertEqual(r.status_code, 400)

    def test_write_error_returns_500(self):
        self._write_state()
        with patch.object(Path, "write_text", side_effect=OSError("fail")):
            r = self.client.post("/subtasks/bulk-verify", json={"subtasks": ["A1"]})
        self.assertEqual(r.status_code, 500)

    def test_verified_list_returned(self):
        self._write_state()
        data = self.client.post(
            "/subtasks/bulk-verify", json={"subtasks": ["A1"]}
        ).get_json()
        self.assertIn("A1", data["verified"])


# ---------------------------------------------------------------------------
# GET /subtask/<id>
# ---------------------------------------------------------------------------

class TestGetSubtask(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/subtask/A1")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/subtask/A1").get_json()
        for key in ("subtask", "task", "branch", "status", "output", "history"):
            self.assertIn(key, data)

    def test_correct_task_and_branch(self):
        self._write_state()
        data = self.client.get("/subtask/B1").get_json()
        self.assertEqual(data["task"], "T0")
        self.assertEqual(data["branch"], "b1")

    def test_404_unknown_subtask(self):
        self._write_state()
        r = self.client.get("/subtask/MISSING")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /subtask/<id>/output
# ---------------------------------------------------------------------------

class TestGetSubtaskOutput(_Base):

    def test_returns_plain_text(self):
        self._write_state()
        r = self.client.get("/subtask/A2/output")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/plain", r.content_type)

    def test_output_content(self):
        self._write_state()
        r = self.client.get("/subtask/A2/output")
        self.assertEqual(r.data.decode(), "done")

    def test_404_unknown_subtask(self):
        self._write_state()
        r = self.client.get("/subtask/MISSING/output")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# POST /subtask/<id>/reset
# ---------------------------------------------------------------------------

class TestResetSubtask(_Base):

    def test_returns_ok(self):
        self._write_state()
        data = self.client.post("/subtask/A1/reset").get_json()
        self.assertTrue(data["ok"])

    def test_writes_heal_trigger(self):
        self._write_state()
        self.client.post("/subtask/A1/reset")
        self.assertTrue(self._heal_trigger.exists())

    def test_heal_trigger_contains_subtask_name(self):
        self._write_state()
        self.client.post("/subtask/B1/reset")
        payload = json.loads(self._heal_trigger.read_text())
        self.assertEqual(payload["subtask"], "B1")

    def test_previous_status_in_response(self):
        self._write_state()
        data = self.client.post("/subtask/B1/reset").get_json()
        self.assertEqual(data["previous_status"], "Running")

    def test_response_includes_task_and_branch(self):
        self._write_state()
        data = self.client.post("/subtask/A1/reset").get_json()
        self.assertEqual(data["task"], "T0")
        self.assertEqual(data["branch"], "b0")

    def test_404_unknown_subtask(self):
        self._write_state()
        r = self.client.post("/subtask/MISSING/reset")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /timeline/<subtask>
# ---------------------------------------------------------------------------

class TestTimeline(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/timeline/A1")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/timeline/A1").get_json()
        for key in ("subtask", "task", "branch", "status", "description", "output", "history"):
            self.assertIn(key, data)

    def test_case_insensitive_match(self):
        self._write_state()
        r = self.client.get("/timeline/a1")
        self.assertEqual(r.status_code, 200)

    def test_history_included(self):
        self._write_state()
        data = self.client.get("/timeline/A2").get_json()
        self.assertEqual(len(data["history"]), 1)

    def test_404_unknown_subtask(self):
        self._write_state()
        r = self.client.get("/timeline/MISSING")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# GET /stalled
# ---------------------------------------------------------------------------

class TestStalled(_Base):

    def test_returns_200(self):
        self._write_state(step=10)
        r = self.client.get("/stalled")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state(step=10)
        data = self.client.get("/stalled").get_json()
        for key in ("step", "threshold", "count", "stalled", "by_branch"):
            self.assertIn(key, data)

    def test_running_subtask_included_when_stale(self):
        # B1 is Running with last_update=0, step=10 → age=10 >= threshold=3
        self._write_state(step=10)
        data = self.client.get("/stalled").get_json()
        names = [s["subtask"] for s in data["stalled"]]
        self.assertIn("B1", names)

    def test_non_running_excluded(self):
        self._write_state(step=10)
        data = self.client.get("/stalled").get_json()
        for s in data["stalled"]:
            self.assertNotIn(s["subtask"], ("A1", "A2", "B2"))

    def test_min_age_override(self):
        self._write_state(step=2)
        # default threshold=3, step=2 so age=2 < 3, but min_age=1 → age=2 >= 1
        data = self.client.get("/stalled?min_age=1").get_json()
        self.assertEqual(data["threshold"], 1)

    def test_task_filter(self):
        self._write_state(step=10)
        data = self.client.get("/stalled?task=T0").get_json()
        for s in data["stalled"]:
            self.assertEqual(s["task"], "T0")

    def test_branch_filter(self):
        self._write_state(step=10)
        data = self.client.get("/stalled?branch=b0").get_json()
        # A1 (Pending) not Running, B1 in b1 filtered out
        self.assertEqual(data["count"], 0)

    def test_by_branch_grouping(self):
        self._write_state(step=10)
        data = self.client.get("/stalled").get_json()
        self.assertIsInstance(data["by_branch"], list)

    def test_stall_threshold_from_settings(self):
        self._settings_path.write_text(json.dumps({"STALL_THRESHOLD": 20}), encoding="utf-8")
        self._write_state(step=10)
        data = self.client.get("/stalled").get_json()
        # age=10 < threshold=20 → nothing stalled
        self.assertEqual(data["count"], 0)

    def test_settings_read_error_uses_default(self):
        # Missing settings file → threshold falls back to 5
        self._settings_path.unlink()
        self._write_state(step=10)
        data = self.client.get("/stalled").get_json()
        self.assertEqual(data["threshold"], 5)

    def test_invalid_min_age_param_ignored(self):
        self._write_state(step=10)
        data = self.client.get("/stalled?min_age=notanumber").get_json()
        # Falls back to settings threshold=3
        self.assertEqual(data["threshold"], 3)


if __name__ == "__main__":
    unittest.main()
