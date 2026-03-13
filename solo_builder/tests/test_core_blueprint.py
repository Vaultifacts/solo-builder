"""Tests for core blueprint — GET /, /status, /heartbeat, /health."""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import time
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
        self._heartbeat_path = sp / "step.txt"

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "HEARTBEAT_PATH", new=self._heartbeat_path),
            patch.object(app_module, "CACHE_DIR", new=Path(self._tmp) / "cache"),
            patch.object(app_module, "_APP_START_TIME", new=time.time()),
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


class TestStatusEndpoint(_Base):
    def test_status_empty_dag(self):
        self._write_state({"dag": {}, "step": 0})
        r = self.client.get("/status")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["total"], 0)
        self.assertTrue(d["complete"])

    def test_status_with_subtasks(self):
        self._write_state({"step": 10, "dag": {
            "TASK-1": {"branches": {"main": {"subtasks": {
                "ST-1": {"status": "Verified"},
                "ST-2": {"status": "Running", "last_update": 3},
                "ST-3": {"status": "Review"},
                "ST-4": {"status": "Pending"},
            }}}},
        }})
        r = self.client.get("/status")
        d = r.get_json()
        self.assertEqual(d["total"], 4)
        self.assertEqual(d["verified"], 1)
        self.assertEqual(d["running"], 1)
        self.assertEqual(d["review"], 1)
        self.assertEqual(d["stalled"], 1)
        self.assertEqual(d["pending"], 1)
        self.assertEqual(len(d["stalled_by_branch"]), 1)

    def test_status_custom_threshold(self):
        self._settings_path.write_text(json.dumps({"STALL_THRESHOLD": 100}), encoding="utf-8")
        self._write_state({"step": 10, "dag": {
            "TASK-1": {"branches": {"main": {"subtasks": {
                "ST-1": {"status": "Running", "last_update": 5},
            }}}},
        }})
        r = self.client.get("/status")
        d = r.get_json()
        self.assertEqual(d["stalled"], 0)

    def test_status_missing_state(self):
        r = self.client.get("/status")
        d = r.get_json()
        self.assertEqual(d["total"], 0)


class TestHeartbeatEndpoint(_Base):
    def test_heartbeat_no_file(self):
        r = self.client.get("/heartbeat")
        d = r.get_json()
        self.assertEqual(d["step"], 0)

    def test_heartbeat_with_data(self):
        self._heartbeat_path.write_text("42,10,20,5,3,2", encoding="utf-8")
        r = self.client.get("/heartbeat")
        d = r.get_json()
        self.assertEqual(d["step"], 42)
        self.assertEqual(d["verified"], 10)
        self.assertEqual(d["total"], 20)
        self.assertEqual(d["pending"], 5)
        self.assertEqual(d["running"], 3)
        self.assertEqual(d["review"], 2)

    def test_heartbeat_five_fields(self):
        self._heartbeat_path.write_text("10,5,15,3,2", encoding="utf-8")
        r = self.client.get("/heartbeat")
        d = r.get_json()
        self.assertEqual(d["review"], 0)

    def test_heartbeat_corrupt_data(self):
        self._heartbeat_path.write_text("not,a,number", encoding="utf-8")
        r = self.client.get("/heartbeat")
        d = r.get_json()
        self.assertEqual(d["step"], 0)


class TestHealthEndpoint(_Base):
    def test_health_basic(self):
        self._write_state({"step": 5, "dag": {
            "TASK-1": {"branches": {"main": {"subtasks": {"ST-1": {"status": "Pending"}}}}},
        }})
        r = self.client.get("/health")
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertIn("version", d)
        self.assertEqual(d["step"], 5)
        self.assertTrue(d["state_file_exists"])
        self.assertEqual(d["total_subtasks"], 1)
        self.assertIn("uptime_s", d)

    def test_health_no_state_file(self):
        r = self.client.get("/health")
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["total_subtasks"], 0)


class TestDashboardRoot(_Base):
    def test_root_returns_html(self):
        self._write_state({"dag": {}, "step": 0})
        r = self.client.get("/")
        self.assertIn(r.status_code, (200, 304))


if __name__ == "__main__":
    unittest.main()
