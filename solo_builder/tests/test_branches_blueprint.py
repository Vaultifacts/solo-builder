"""Tests for branches blueprint — GET /branches, /branches/export,
/branches/<task_id>, POST /branches/<task_id>/reset (TASK-400)."""
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
            "status": "Running",
            "branches": {
                "b0": {
                    "subtasks": {
                        "s1": {"status": "Pending", "output": ""},
                        "s2": {"status": "Verified", "output": "done"},
                        "s3": {"status": "Running", "output": "wip"},
                    }
                },
                "b1": {
                    "subtasks": {
                        "s4": {"status": "Verified", "output": "ok"},
                        "s5": {"status": "Verified", "output": "ok"},
                    }
                },
                "b2": {
                    "subtasks": {
                        "s6": {"status": "Review", "output": "needs check"},
                    }
                },
            },
        },
        "T1": {
            "status": "Verified",
            "branches": {
                "c0": {
                    "subtasks": {
                        "s7": {"status": "Verified", "output": "done"},
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
# GET /branches
# ---------------------------------------------------------------------------

class TestBranchesAll(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/branches")
        self.assertEqual(r.status_code, 200)

    def test_returns_all_branches(self):
        self._write_state()
        data = self.client.get("/branches").get_json()
        # T0: 3 branches, T1: 1 branch = 4 total
        self.assertEqual(data["total"], 4)

    def test_task_filter(self):
        self._write_state()
        data = self.client.get("/branches?task=T0").get_json()
        self.assertEqual(data["total"], 3)
        for b in data["branches"]:
            self.assertEqual(b["task"], "T0")

    def test_status_filter_running(self):
        self._write_state()
        data = self.client.get("/branches?status=running").get_json()
        # b0 has s3=Running
        for b in data["branches"]:
            self.assertGreater(b["running"], 0)

    def test_status_filter_pending(self):
        self._write_state()
        data = self.client.get("/branches?status=pending").get_json()
        for b in data["branches"]:
            self.assertGreater(b["pending"], 0)

    def test_status_filter_review(self):
        self._write_state()
        data = self.client.get("/branches?status=review").get_json()
        for b in data["branches"]:
            self.assertGreater(b["review"], 0)

    def test_status_filter_verified(self):
        self._write_state()
        data = self.client.get("/branches?status=verified").get_json()
        # b1 (2/2 verified) and c0 (1/1 verified)
        for b in data["branches"]:
            self.assertEqual(b["verified"], b["total"])

    def test_pagination_limit(self):
        self._write_state()
        data = self.client.get("/branches?limit=2&page=1").get_json()
        self.assertEqual(len(data["branches"]), 2)
        self.assertEqual(data["pages"], 2)

    def test_pagination_page2(self):
        self._write_state()
        data = self.client.get("/branches?limit=2&page=2").get_json()
        self.assertEqual(len(data["branches"]), 2)

    def test_pct_computed(self):
        self._write_state()
        data = self.client.get("/branches").get_json()
        # b1: 2/2 verified → 100.0
        b1 = next(b for b in data["branches"] if b["branch"] == "b1")
        self.assertEqual(b1["pct"], 100.0)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/branches").get_json()
        for key in ("branches", "count", "total", "page", "pages"):
            self.assertIn(key, data)

    def test_branch_entry_keys(self):
        self._write_state()
        data = self.client.get("/branches").get_json()
        b = data["branches"][0]
        for key in ("task", "branch", "total", "verified", "running", "review", "pending", "pct"):
            self.assertIn(key, b)

    def test_review_pct_computed(self):
        self._write_state()
        data = self.client.get("/branches").get_json()
        b2 = next(b for b in data["branches"] if b["branch"] == "b2")
        self.assertEqual(b2["review"], 1)

    def test_empty_dag(self):
        self._write_state(dag={})
        data = self.client.get("/branches").get_json()
        self.assertEqual(data["total"], 0)


# ---------------------------------------------------------------------------
# GET /branches/export
# ---------------------------------------------------------------------------

class TestBranchesExport(_Base):

    def test_csv_default(self):
        self._write_state()
        r = self.client.get("/branches/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_csv_content_disposition(self):
        self._write_state()
        r = self.client.get("/branches/export")
        self.assertIn("branches.csv", r.headers.get("Content-Disposition", ""))

    def test_csv_has_header_row(self):
        self._write_state()
        text = self.client.get("/branches/export").data.decode()
        self.assertIn("task,branch,total,verified,running,review,pending,pct", text)

    def test_json_format(self):
        self._write_state()
        r = self.client.get("/branches/export?format=json")
        data = r.get_json()
        self.assertIn("branches", data)
        self.assertIn("total", data)

    def test_json_content_disposition(self):
        self._write_state()
        r = self.client.get("/branches/export?format=json")
        self.assertIn("branches.json", r.headers.get("Content-Disposition", ""))

    def test_status_filter_in_export(self):
        self._write_state()
        r = self.client.get("/branches/export?format=json&status=verified")
        data = r.get_json()
        for b in data["branches"]:
            self.assertEqual(b["verified"], b["total"])

    def test_task_filter_in_export(self):
        self._write_state()
        r = self.client.get("/branches/export?format=json&task=T1")
        data = r.get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["branches"][0]["task"], "T1")

    def test_running_status_filter(self):
        self._write_state()
        r = self.client.get("/branches/export?format=json&status=running")
        data = r.get_json()
        for b in data["branches"]:
            self.assertGreater(b["running"], 0)

    def test_review_status_filter(self):
        self._write_state()
        r = self.client.get("/branches/export?format=json&status=review")
        data = r.get_json()
        for b in data["branches"]:
            self.assertGreater(b["review"], 0)

    def test_pending_status_filter(self):
        self._write_state()
        r = self.client.get("/branches/export?format=json&status=pending")
        data = r.get_json()
        for b in data["branches"]:
            self.assertGreater(b["pending"], 0)


# ---------------------------------------------------------------------------
# GET /branches/<task_id>
# ---------------------------------------------------------------------------

class TestBranchesByTask(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/branches/T0")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/branches/T0").get_json()
        self.assertIn("task", data)
        self.assertIn("branch_count", data)
        self.assertIn("branches", data)

    def test_branch_count(self):
        self._write_state()
        data = self.client.get("/branches/T0").get_json()
        self.assertEqual(data["branch_count"], 3)

    def test_subtasks_array_included(self):
        self._write_state()
        data = self.client.get("/branches/T0").get_json()
        for br in data["branches"]:
            self.assertIn("subtasks", br)
            for st in br["subtasks"]:
                self.assertIn("name", st)
                self.assertIn("status", st)

    def test_counts_correct(self):
        self._write_state()
        data = self.client.get("/branches/T0").get_json()
        b0 = next(b for b in data["branches"] if b["branch"] == "b0")
        self.assertEqual(b0["verified"], 1)
        self.assertEqual(b0["running"], 1)
        self.assertEqual(b0["pending"], 1)

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.get("/branches/MISSING")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# POST /branches/<task_id>/reset
# ---------------------------------------------------------------------------

class TestResetBranch(_Base):

    def test_returns_ok(self):
        self._write_state()
        data = self.client.post("/branches/T0/reset", json={"branch": "b0"}).get_json()
        self.assertTrue(data["ok"])

    def test_non_verified_subtasks_reset(self):
        self._write_state()
        self.client.post("/branches/T0/reset", json={"branch": "b0"})
        state = json.loads(self._state_path.read_text())
        s1 = state["dag"]["T0"]["branches"]["b0"]["subtasks"]["s1"]
        s3 = state["dag"]["T0"]["branches"]["b0"]["subtasks"]["s3"]
        self.assertEqual(s1["status"], "Pending")
        self.assertEqual(s3["status"], "Pending")

    def test_verified_subtasks_skipped(self):
        self._write_state()
        data = self.client.post("/branches/T0/reset", json={"branch": "b0"}).get_json()
        # s2 is Verified → skipped
        self.assertEqual(data["skipped_count"], 1)

    def test_reset_count_correct(self):
        self._write_state()
        data = self.client.post("/branches/T0/reset", json={"branch": "b0"}).get_json()
        # s1 (Pending) + s3 (Running) = 2
        self.assertEqual(data["reset_count"], 2)

    def test_output_cleared(self):
        self._write_state()
        self.client.post("/branches/T0/reset", json={"branch": "b0"})
        state = json.loads(self._state_path.read_text())
        s3 = state["dag"]["T0"]["branches"]["b0"]["subtasks"]["s3"]
        self.assertEqual(s3["output"], "")

    def test_response_includes_task_and_branch(self):
        self._write_state()
        data = self.client.post("/branches/T0/reset", json={"branch": "b0"}).get_json()
        self.assertEqual(data["task"], "T0")
        self.assertEqual(data["branch"], "b0")

    def test_missing_branch_field_returns_400(self):
        self._write_state()
        r = self.client.post("/branches/T0/reset", json={})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_empty_branch_field_returns_400(self):
        self._write_state()
        r = self.client.post("/branches/T0/reset", json={"branch": ""})
        self.assertEqual(r.status_code, 400)

    def test_404_unknown_task(self):
        self._write_state()
        r = self.client.post("/branches/MISSING/reset", json={"branch": "b0"})
        self.assertEqual(r.status_code, 404)

    def test_404_unknown_branch(self):
        self._write_state()
        r = self.client.post("/branches/T0/reset", json={"branch": "NOEXIST"})
        self.assertEqual(r.status_code, 404)

    def test_write_error_returns_500(self):
        self._write_state()
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            r = self.client.post("/branches/T0/reset", json={"branch": "b0"})
        self.assertEqual(r.status_code, 500)
        self.assertFalse(r.get_json()["ok"])

    def test_all_verified_branch_resets_nothing(self):
        self._write_state()
        data = self.client.post("/branches/T0/reset", json={"branch": "b1"}).get_json()
        # b1 has s4+s5 both Verified
        self.assertEqual(data["reset_count"], 0)
        self.assertEqual(data["skipped_count"], 2)


if __name__ == "__main__":
    unittest.main()
