"""Tests for export_routes blueprint — GET/POST /export, GET /stats, /search, /journal (TASK-400)."""
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
            "branches": {
                "b0": {
                    "subtasks": {
                        "s1": {
                            "status": "Pending",
                            "output": "",
                            "description": "do alpha",
                            "history": [],
                        },
                        "s2": {
                            "status": "Verified",
                            "output": "result alpha",
                            "description": "do beta",
                            "history": [
                                {"step": 1, "status": "Running"},
                                {"step": 3, "status": "Verified"},
                            ],
                        },
                    }
                }
            },
        },
        "T1": {
            "status": "Verified",
            "branches": {
                "c0": {
                    "subtasks": {
                        "s3": {
                            "status": "Verified",
                            "output": "result beta",
                            "description": "do gamma",
                            "history": [
                                {"step": 2, "status": "Running"},
                                {"step": 4, "status": "Verified"},
                            ],
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
        self._outputs_path = Path(self._tmp) / "outputs" / "solo_builder_outputs.md"
        self._journal_path = Path(self._tmp) / "JOURNAL.md"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "OUTPUTS_PATH", new=self._outputs_path),
            patch.object(app_module, "JOURNAL_PATH", new=self._journal_path),
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
# GET /export
# ---------------------------------------------------------------------------

class TestGetExport(_Base):

    def test_404_when_no_outputs_file(self):
        r = self.client.get("/export")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.get_json())

    def test_200_when_outputs_file_exists(self):
        self._outputs_path.parent.mkdir(parents=True, exist_ok=True)
        self._outputs_path.write_text("# outputs", encoding="utf-8")
        r = self.client.get("/export")
        self.assertEqual(r.status_code, 200)

    def test_content_disposition_attachment(self):
        self._outputs_path.parent.mkdir(parents=True, exist_ok=True)
        self._outputs_path.write_text("# outputs", encoding="utf-8")
        r = self.client.get("/export")
        self.assertIn("attachment", r.headers.get("Content-Disposition", ""))
        self.assertIn("solo_builder_outputs.md", r.headers.get("Content-Disposition", ""))

    def test_mimetype_markdown(self):
        self._outputs_path.parent.mkdir(parents=True, exist_ok=True)
        self._outputs_path.write_text("# outputs", encoding="utf-8")
        r = self.client.get("/export")
        self.assertIn("markdown", r.content_type)


# ---------------------------------------------------------------------------
# POST /export
# ---------------------------------------------------------------------------

class TestPostExport(_Base):

    def test_404_when_no_outputs_in_state(self):
        dag = {
            "T0": {"branches": {"b0": {"subtasks": {
                "s1": {"status": "Pending", "output": "", "description": ""}
            }}}}
        }
        self._write_state(dag=dag)
        r = self.client.post("/export")
        self.assertEqual(r.status_code, 404)
        self.assertFalse(r.get_json()["ok"])

    def test_200_when_outputs_exist(self):
        self._write_state()
        r = self.client.post("/export")
        self.assertEqual(r.status_code, 200)

    def test_writes_outputs_file(self):
        self._write_state()
        self.client.post("/export")
        self.assertTrue(self._outputs_path.exists())

    def test_outputs_file_contains_subtask_name(self):
        self._write_state()
        self.client.post("/export")
        content = self._outputs_path.read_text(encoding="utf-8")
        self.assertIn("s2", content)

    def test_outputs_file_contains_description(self):
        self._write_state()
        self.client.post("/export")
        content = self._outputs_path.read_text(encoding="utf-8")
        self.assertIn("do beta", content)

    def test_subtask_with_no_output_excluded(self):
        self._write_state()
        self.client.post("/export")
        content = self._outputs_path.read_text(encoding="utf-8")
        # s1 has no output — should not appear as section header
        self.assertNotIn("## s1", content)

    def test_content_disposition_attachment(self):
        self._write_state()
        r = self.client.post("/export")
        self.assertIn("attachment", r.headers.get("Content-Disposition", ""))

    def test_empty_description_not_in_output(self):
        dag = {
            "T0": {"branches": {"b0": {"subtasks": {
                "s1": {"status": "Verified", "output": "done", "description": "", "history": []}
            }}}}
        }
        self._write_state(dag=dag)
        self.client.post("/export")
        content = self._outputs_path.read_text(encoding="utf-8")
        self.assertNotIn("Prompt:", content)


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

class TestStats(_Base):

    def test_returns_200(self):
        self._write_state()
        r = self.client.get("/stats")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        self._write_state()
        data = self.client.get("/stats").get_json()
        for key in ("tasks", "grand_verified", "grand_total", "grand_pct", "grand_avg_steps"):
            self.assertIn(key, data)

    def test_grand_totals(self):
        self._write_state()
        data = self.client.get("/stats").get_json()
        self.assertEqual(data["grand_total"], 3)
        self.assertEqual(data["grand_verified"], 2)

    def test_grand_pct(self):
        self._write_state()
        data = self.client.get("/stats").get_json()
        self.assertAlmostEqual(data["grand_pct"], 66.7, places=0)

    def test_avg_steps_computed_from_history(self):
        # s2: step 3-1=2, s3: step 4-2=2 → avg=2.0
        self._write_state()
        data = self.client.get("/stats").get_json()
        self.assertEqual(data["grand_avg_steps"], 2.0)

    def test_avg_steps_none_when_no_history(self):
        dag = {
            "T0": {"branches": {"b0": {"subtasks": {
                "s1": {"status": "Verified", "output": "done", "history": []}
            }}}}
        }
        self._write_state(dag=dag)
        data = self.client.get("/stats").get_json()
        self.assertIsNone(data["grand_avg_steps"])

    def test_per_task_breakdown(self):
        self._write_state()
        data = self.client.get("/stats").get_json()
        ids = [t["id"] for t in data["tasks"]]
        self.assertIn("T0", ids)
        self.assertIn("T1", ids)

    def test_empty_dag(self):
        self._write_state(dag={})
        data = self.client.get("/stats").get_json()
        self.assertEqual(data["grand_total"], 0)
        self.assertEqual(data["grand_pct"], 0)


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

class TestSearch(_Base):

    def test_missing_q_returns_400(self):
        self._write_state()
        r = self.client.get("/search")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json())

    def test_empty_q_returns_400(self):
        self._write_state()
        r = self.client.get("/search?q=")
        self.assertEqual(r.status_code, 400)

    def test_match_by_description(self):
        self._write_state()
        data = self.client.get("/search?q=do+alpha").get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["subtask"], "s1")

    def test_match_by_output(self):
        self._write_state()
        data = self.client.get("/search?q=result").get_json()
        self.assertGreaterEqual(data["count"], 2)

    def test_match_by_subtask_name(self):
        self._write_state()
        data = self.client.get("/search?q=s2").get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["subtask"], "s2")

    def test_no_match(self):
        self._write_state()
        data = self.client.get("/search?q=zzznomatch").get_json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])

    def test_response_includes_query(self):
        self._write_state()
        data = self.client.get("/search?q=alpha").get_json()
        self.assertEqual(data["query"], "alpha")

    def test_result_fields(self):
        self._write_state()
        data = self.client.get("/search?q=result").get_json()
        for r in data["results"]:
            for key in ("subtask", "task", "branch", "status", "description", "output"):
                self.assertIn(key, r)

    def test_case_insensitive(self):
        self._write_state()
        data = self.client.get("/search?q=ALPHA").get_json()
        self.assertGreater(data["count"], 0)


# ---------------------------------------------------------------------------
# GET /journal
# ---------------------------------------------------------------------------

class TestJournal(_Base):

    def test_empty_entries_when_no_journal(self):
        r = self.client.get("/journal")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["entries"], [])

    def test_parses_journal_entries(self):
        content = (
            "## A1 · Task 1 / Branch b0 · Step 3\n"
            "**Prompt:** do something\n\n"
            "output text here\n"
            "---\n"
        )
        self._journal_path.write_text(content, encoding="utf-8")
        data = self.client.get("/journal").get_json()
        self.assertEqual(len(data["entries"]), 1)
        entry = data["entries"][0]
        self.assertEqual(entry["subtask"], "A1")
        self.assertEqual(entry["task"], "Task 1")
        self.assertEqual(entry["branch"], "Branch b0")
        self.assertEqual(entry["step"], 3)

    def test_prompt_stripped_from_output(self):
        content = (
            "## A1 · Task 1 / Branch b0 · Step 3\n"
            "**Prompt:** do something\n\n"
            "actual output\n"
        )
        self._journal_path.write_text(content, encoding="utf-8")
        data = self.client.get("/journal").get_json()
        self.assertNotIn("Prompt:", data["entries"][0]["output"])

    def test_non_matching_blocks_ignored(self):
        content = "# Header\nsome intro text\n\n## A1 · Task 1 / Branch b0 · Step 5\n\noutput\n"
        self._journal_path.write_text(content, encoding="utf-8")
        data = self.client.get("/journal").get_json()
        self.assertEqual(len(data["entries"]), 1)

    def test_multiple_entries_returned(self):
        blocks = []
        for i in range(5):
            blocks.append(
                f"## S{i} · Task 1 / Branch b0 · Step {i}\n\noutput {i}\n"
            )
        self._journal_path.write_text("\n".join(blocks), encoding="utf-8")
        data = self.client.get("/journal").get_json()
        self.assertEqual(len(data["entries"]), 5)

    def test_output_truncated_to_600(self):
        long_output = "x" * 1000
        content = f"## A1 · Task 1 / Branch b0 · Step 1\n\n{long_output}\n"
        self._journal_path.write_text(content, encoding="utf-8")
        data = self.client.get("/journal").get_json()
        self.assertLessEqual(len(data["entries"][0]["output"]), 600)


if __name__ == "__main__":
    unittest.main()
