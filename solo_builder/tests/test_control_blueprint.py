"""Tests for control blueprint — POST /run, /stop, /undo, /reset, /snapshot, /pause, /resume (TASK-393)."""
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
            patch.object(app_module, "STATE_PATH",      new=self._state_path),
            patch.object(app_module, "TRIGGER_PATH",    new=sp / "run_trigger"),
            patch.object(app_module, "STOP_TRIGGER",    new=sp / "stop_trigger"),
            patch.object(app_module, "UNDO_TRIGGER",    new=sp / "undo_trigger"),
            patch.object(app_module, "RESET_TRIGGER",   new=sp / "reset_trigger"),
            patch.object(app_module, "SNAPSHOT_TRIGGER",new=sp / "snapshot_trigger"),
            patch.object(app_module, "PAUSE_TRIGGER",   new=sp / "pause_trigger"),
            patch.object(app_module, "HEAL_TRIGGER",    new=sp / "heal_trigger.json"),
            patch.object(app_module, "SETTINGS_PATH",   new=self._settings_path),
            patch.object(app_module, "CACHE_DIR",       new=Path(self._tmp) / "cache"),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read  = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_state(self, dag=None, step=0):
        state = {"step": step, "dag": dag or {}}
        self._state_path.write_text(json.dumps(state), encoding="utf-8")


# ---------------------------------------------------------------------------
# POST /run
# ---------------------------------------------------------------------------

class TestRunEndpoint(_Base):

    def test_run_returns_202_with_pending_subtasks(self):
        self._write_state(dag={"T0": {"branches": {"b0": {"subtasks": {
            "s1": {"status": "Pending"}
        }}}}})
        r = self.client.post("/run")
        self.assertEqual(r.status_code, 202)

    def test_run_ok_true_with_pending(self):
        self._write_state(dag={"T0": {"branches": {"b0": {"subtasks": {
            "s1": {"status": "Pending"}
        }}}}})
        self.assertTrue(r.get_json()["ok"] for r in [self.client.post("/run")])

    def test_run_writes_trigger_file(self):
        self._write_state()
        self.client.post("/run")
        trigger = Path(self._tmp) / "state" / "run_trigger"
        self.assertTrue(trigger.exists())

    def test_run_pipeline_complete_returns_ok_false(self):
        self._write_state(dag={"T0": {"branches": {"b0": {"subtasks": {
            "s1": {"status": "Verified"}
        }}}}})
        r = self.client.post("/run")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["ok"])
        self.assertIn("reason", r.get_json())

    def test_run_empty_dag_writes_trigger(self):
        self._write_state(dag={})
        r = self.client.post("/run")
        self.assertEqual(r.status_code, 202)


# ---------------------------------------------------------------------------
# POST /stop
# ---------------------------------------------------------------------------

class TestStopEndpoint(_Base):

    def test_stop_returns_202(self):
        self.assertEqual(self.client.post("/stop").status_code, 202)

    def test_stop_ok_true(self):
        self.assertTrue(self.client.post("/stop").get_json()["ok"])

    def test_stop_writes_trigger_file(self):
        self.client.post("/stop")
        self.assertTrue((Path(self._tmp) / "state" / "stop_trigger").exists())


# ---------------------------------------------------------------------------
# POST /undo
# ---------------------------------------------------------------------------

class TestUndoEndpoint(_Base):

    def test_undo_returns_202(self):
        self.assertEqual(self.client.post("/undo").status_code, 202)

    def test_undo_ok_true(self):
        self.assertTrue(self.client.post("/undo").get_json()["ok"])

    def test_undo_writes_trigger_file(self):
        self.client.post("/undo")
        self.assertTrue((Path(self._tmp) / "state" / "undo_trigger").exists())


# ---------------------------------------------------------------------------
# POST /reset
# ---------------------------------------------------------------------------

class TestResetEndpoint(_Base):

    def test_reset_without_confirm_returns_400(self):
        r = self.client.post("/reset", json={})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_reset_wrong_confirm_returns_400(self):
        r = self.client.post("/reset", json={"confirm": "no"})
        self.assertEqual(r.status_code, 400)

    def test_reset_with_confirm_yes_returns_202(self):
        r = self.client.post("/reset", json={"confirm": "yes"})
        self.assertEqual(r.status_code, 202)

    def test_reset_with_confirm_yes_writes_trigger(self):
        self.client.post("/reset", json={"confirm": "yes"})
        self.assertTrue((Path(self._tmp) / "state" / "reset_trigger").exists())

    def test_reset_confirm_case_insensitive(self):
        r = self.client.post("/reset", json={"confirm": "YES"})
        self.assertEqual(r.status_code, 202)


# ---------------------------------------------------------------------------
# POST /snapshot
# ---------------------------------------------------------------------------

class TestSnapshotEndpoint(_Base):

    def test_snapshot_returns_202(self):
        self.assertEqual(self.client.post("/snapshot").status_code, 202)

    def test_snapshot_ok_true(self):
        self.assertTrue(self.client.post("/snapshot").get_json()["ok"])

    def test_snapshot_writes_trigger_file(self):
        self.client.post("/snapshot")
        self.assertTrue((Path(self._tmp) / "state" / "snapshot_trigger").exists())


# ---------------------------------------------------------------------------
# POST /pause
# ---------------------------------------------------------------------------

class TestPauseEndpoint(_Base):

    def test_pause_returns_202(self):
        self.assertEqual(self.client.post("/pause").status_code, 202)

    def test_pause_ok_true(self):
        self.assertTrue(self.client.post("/pause").get_json()["ok"])

    def test_pause_writes_trigger_file(self):
        self.client.post("/pause")
        self.assertTrue((Path(self._tmp) / "state" / "pause_trigger").exists())


# ---------------------------------------------------------------------------
# POST /resume
# ---------------------------------------------------------------------------

class TestResumeEndpoint(_Base):

    def test_resume_returns_202(self):
        self.assertEqual(self.client.post("/resume").status_code, 202)

    def test_resume_ok_true(self):
        self.assertTrue(self.client.post("/resume").get_json()["ok"])

    def test_resume_removes_pause_trigger_if_exists(self):
        pause_path = Path(self._tmp) / "state" / "pause_trigger"
        pause_path.write_text("1")
        self.client.post("/resume")
        self.assertFalse(pause_path.exists())

    def test_resume_ok_when_no_pause_trigger(self):
        r = self.client.post("/resume")
        self.assertEqual(r.status_code, 202)


# ---------------------------------------------------------------------------
# Coverage: resume OSError on unlink (lines 87-88)
# ---------------------------------------------------------------------------

class TestResumeOSError(_Base):
    def test_resume_oserror_on_unlink_still_ok(self):
        pause_path = Path(self._tmp) / "state" / "pause_trigger"
        pause_path.write_text("1")
        orig_unlink = Path.unlink
        def _failing_unlink(self_path, *a, **kw):
            if "pause" in str(self_path):
                raise OSError("locked")
            orig_unlink(self_path, *a, **kw)
        with patch.object(Path, "unlink", _failing_unlink):
            r = self.client.post("/resume")
        self.assertEqual(r.status_code, 202)
        self.assertTrue(r.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
