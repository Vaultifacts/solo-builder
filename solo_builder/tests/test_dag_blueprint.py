"""Tests for dag blueprint — GET /dag/summary, /dag/export, POST /dag/import."""
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
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "DAG_IMPORT_TRIGGER", new=sp / "dag_import_trigger.json"),
            patch.object(app_module, "CACHE_DIR", new=Path(self._tmp) / "cache"),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def _write_state(self, state):
        self._state_path.write_text(json.dumps(state), encoding="utf-8")

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestDagSummaryEmpty(_Base):
    def test_empty_dag(self):
        self._write_state({"dag": {}, "step": 0})
        r = self.client.get("/dag/summary")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["pct"], 0)
        self.assertFalse(d["complete"])
        self.assertIn("Pipeline Summary", d["summary"])


class TestDagSummaryWithTasks(_Base):
    def test_counts_and_summary(self):
        self._write_state({"step": 5, "dag": {
            "TASK-1": {"status": "Running", "branches": {"main": {"subtasks": {
                "ST-1": {"status": "Verified"},
                "ST-2": {"status": "Running"},
                "ST-3": {"status": "Review"},
                "ST-4": {"status": "Pending"},
            }}}},
        }})
        r = self.client.get("/dag/summary")
        d = r.get_json()
        self.assertEqual(d["total"], 4)
        self.assertEqual(d["verified"], 1)
        self.assertEqual(d["running"], 1)
        self.assertEqual(d["review"], 1)
        self.assertEqual(d["pending"], 1)
        self.assertEqual(d["pct"], 25.0)
        self.assertFalse(d["complete"])
        self.assertEqual(len(d["tasks"]), 1)
        self.assertIn("TASK-1", d["summary"])

    def test_complete_dag(self):
        self._write_state({"step": 10, "dag": {
            "TASK-1": {"status": "Complete", "branches": {"main": {"subtasks": {
                "ST-1": {"status": "Verified"},
            }}}},
        }})
        r = self.client.get("/dag/summary")
        d = r.get_json()
        self.assertTrue(d["complete"])
        self.assertEqual(d["pct"], 100.0)


class TestDagSummaryNoState(_Base):
    def test_missing_state_file(self):
        r = self.client.get("/dag/summary")
        d = r.get_json()
        self.assertEqual(d["total"], 0)


class TestDagExport(_Base):
    def test_export_json(self):
        self._write_state({"step": 3, "dag": {"TASK-1": {"branches": {}}}})
        r = self.client.get("/dag/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/json", r.content_type)
        d = json.loads(r.data)
        self.assertEqual(d["exported_step"], 3)
        self.assertIn("TASK-1", d["dag"])

    def test_export_has_content_disposition(self):
        self._write_state({"step": 0, "dag": {}})
        r = self.client.get("/dag/export")
        self.assertIn("dag_export.json", r.headers.get("Content-Disposition", ""))


class TestDagImport(_Base):
    def test_import_with_dag_key(self):
        self._write_state({"step": 0, "dag": {}})
        payload = {"dag": {"TASK-1": {"branches": {}}}, "exported_step": 5}
        r = self.client.post("/dag/import", json=payload)
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["tasks"], 1)

    def test_import_raw_dag(self):
        self._write_state({"step": 0, "dag": {}})
        payload = {"TASK-1": {"branches": {}}}
        r = self.client.post("/dag/import", json=payload)
        self.assertEqual(r.status_code, 202)

    def test_import_empty_body(self):
        r = self.client.post("/dag/import", data="", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_import_non_dict(self):
        r = self.client.post("/dag/import", json=[1, 2, 3])
        self.assertEqual(r.status_code, 400)

    def test_import_invalid_task_no_branches(self):
        payload = {"TASK-1": {"no_branches_key": {}}}
        r = self.client.post("/dag/import", json=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn("branches", r.get_json()["error"])

    def test_import_task_not_dict(self):
        payload = {"TASK-1": "not a dict"}
        r = self.client.post("/dag/import", json=payload)
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
