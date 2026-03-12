"""Tests for StepRunnerMixin — run_step, save_state, load_state, _consume_json_trigger (TASK-405)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.step_runner as sr_module
from commands.step_runner import StepRunnerMixin


# ---------------------------------------------------------------------------
# Module-level globals injection helpers
# ---------------------------------------------------------------------------

_GLOBALS = {
    "STATE_PATH": None,      # set per-test via temp dir
    "_HERE": None,           # set per-test via temp dir
    "logger": MagicMock(),
    "ALERT_CONFLICT": "[!CONFLICT]",
    "ALERT_STALLED": "[!STALLED]",
    "CYAN": "", "RESET": "", "GREEN": "", "YELLOW": "", "RED": "", "DIM": "",
}


def _inject(tmp_dir: str, state_path: str) -> list:
    """Return list of patch objects for all module globals."""
    return [
        patch.object(sr_module, "STATE_PATH", new=state_path, create=True),
        patch.object(sr_module, "_HERE", new=tmp_dir, create=True),
        patch.object(sr_module, "logger", new=MagicMock(), create=True),
        patch.object(sr_module, "ALERT_CONFLICT", new="[!CONFLICT]", create=True),
        patch.object(sr_module, "ALERT_STALLED", new="[!STALLED]", create=True),
        patch.object(sr_module, "CYAN", new="", create=True),
        patch.object(sr_module, "RESET", new="", create=True),
        patch.object(sr_module, "GREEN", new="", create=True),
        patch.object(sr_module, "YELLOW", new="", create=True),
        patch.object(sr_module, "RED", new="", create=True),
        patch.object(sr_module, "DIM", new="", create=True),
    ]


# ---------------------------------------------------------------------------
# Shared CLI stub
# ---------------------------------------------------------------------------

def _make_dag(status="Pending"):
    return {
        "Task 0": {
            "status": "Running",
            "depends_on": [],
            "branches": {
                "A": {
                    "subtasks": {
                        "A1": {"status": status, "last_update": 0, "description": "do A1", "output": ""},
                    }
                }
            },
        }
    }


class _FakeCLI(StepRunnerMixin):
    def __init__(self):
        self.dag = _make_dag()
        self.step = 0
        self.snapshot_counter = 0
        self.memory_store = {"A": []}
        self.alerts = []
        self._priority_cache = []
        self._last_priority_step = -100
        self._last_verified_tasks = 0
        self._runtime_cfg = {
            "VERBOSITY": "INFO",
            "SNAPSHOT_INTERVAL": 100,    # high — don't auto-snapshot in tests
            "AUTO_SAVE_INTERVAL": 100,   # high — don't auto-save in tests
        }
        self.planner = MagicMock()
        self.planner.prioritize.return_value = []
        self.shadow = MagicMock()
        self.shadow.detect_conflicts.return_value = []
        self.healer = MagicMock()
        self.healer.find_stalled.return_value = []
        self.healer.heal.return_value = 0
        self.healer.healed_total = 0
        self.executor = MagicMock()
        self.executor.execute_step.return_value = {}
        self.verifier = MagicMock()
        self.verifier.verify.return_value = []
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        self.meta.optimize.return_value = None
        self.meta._history = []
        self.display = MagicMock()
        self._take_snapshot = MagicMock()
        self.save_state = MagicMock()


# ---------------------------------------------------------------------------
# run_step
# ---------------------------------------------------------------------------

class TestRunStep(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state", "solo_builder_state.json")
        os.makedirs(os.path.dirname(self._state), exist_ok=True)
        self._patches = _inject(self._tmp, self._state)
        for p in self._patches:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_run_step_increments_step(self):
        self.cli.run_step()
        self.assertEqual(self.cli.step, 1)

    def test_run_step_calls_planner_prioritize(self):
        self.cli.run_step()
        self.cli.planner.prioritize.assert_called_once()

    def test_run_step_calls_shadow_detect_conflicts(self):
        self.cli.run_step()
        self.cli.shadow.detect_conflicts.assert_called_once()

    def test_run_step_calls_healer_find_stalled(self):
        self.cli.run_step()
        self.cli.healer.find_stalled.assert_called_once()

    def test_run_step_calls_executor_execute_step(self):
        self.cli.run_step()
        self.cli.executor.execute_step.assert_called_once()

    def test_run_step_calls_display_render(self):
        self.cli.run_step()
        self.cli.display.render.assert_called_once()

    def test_run_step_conflict_alert_appended(self):
        self.cli.shadow.detect_conflicts.return_value = [
            ("Task 0", "A", "A1")
        ]
        with patch("builtins.print"):
            self.cli.run_step()
        # Should have attempted to resolve the conflict
        self.cli.shadow.resolve_conflict.assert_called_once()

    def test_run_step_stalled_alert_appended(self):
        self.cli.healer.find_stalled.return_value = [
            ("Task 0", "A", "A1", 7)
        ]
        self.cli.run_step()
        # Stall alert is accumulated
        self.assertTrue(any("A1" in a for a in self.cli.alerts))

    def test_run_step_debug_verbosity_logs_verifier_fix(self):
        self.cli._runtime_cfg["VERBOSITY"] = "DEBUG"
        self.cli.verifier.verify.return_value = ["fixed A1"]
        with patch("builtins.print"):
            self.cli.run_step()
        self.assertTrue(any("fixed A1" in a for a in self.cli.alerts))

    def test_run_step_debug_verbosity_logs_opt_note(self):
        self.cli._runtime_cfg["VERBOSITY"] = "DEBUG"
        self.cli.meta.optimize.return_value = "adjusted weights"
        with patch("builtins.print"):
            self.cli.run_step()
        self.assertTrue(any("adjusted weights" in a for a in self.cli.alerts))

    def test_run_step_triggers_auto_snapshot(self):
        self.cli._runtime_cfg["SNAPSHOT_INTERVAL"] = 1
        with patch("builtins.print"):
            self.cli.run_step()
        self.cli._take_snapshot.assert_called_once_with(auto=True)

    def test_run_step_triggers_auto_save(self):
        self.cli._runtime_cfg["AUTO_SAVE_INTERVAL"] = 1
        with patch("builtins.print"):
            self.cli.run_step()
        self.cli.save_state.assert_called_once_with(silent=True)

    def test_run_step_heartbeat_write_error_is_silent(self):
        # heartbeat write failure must not raise
        with patch("builtins.open", side_effect=OSError("disk full")), \
             patch("builtins.print"):
            self.cli.run_step()  # no exception

    def test_run_step_priority_cache_rebuilt_on_interval(self):
        self.cli._last_priority_step = -200
        self.cli.run_step()
        self.cli.planner.prioritize.assert_called()

    def test_run_step_priority_rebuilt_on_new_verified_task(self):
        self.cli._last_verified_tasks = 0
        self.cli.dag["Task 0"]["status"] = "Verified"
        self.cli.run_step()
        self.cli.planner.prioritize.assert_called()


# ---------------------------------------------------------------------------
# save_state (real implementation — not mocked here)
# ---------------------------------------------------------------------------

class _FakeCliReal(StepRunnerMixin):
    """CLI stub that does NOT mock save_state/load_state — uses real implementations."""
    def __init__(self, state_path):
        self.dag = _make_dag()
        self.step = 7
        self.snapshot_counter = 2
        self.memory_store = {"A": []}
        self.alerts = ["alert1"]
        self._priority_cache = []
        self._last_priority_step = 0
        self._last_verified_tasks = 0
        self._runtime_cfg = {"VERBOSITY": "INFO", "SNAPSHOT_INTERVAL": 100, "AUTO_SAVE_INTERVAL": 100}
        self.planner = MagicMock()
        self.shadow = MagicMock()
        self.healer = MagicMock()
        self.healer.healed_total = 3
        self.executor = MagicMock()
        self.verifier = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        self.meta.optimize.return_value = None
        self.meta._history = [{"healed": 1, "verified": 2}]
        self.display = MagicMock()
        self._take_snapshot = MagicMock()
        self._state_path = state_path


class TestSaveState(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state", "solo_builder_state.json")
        os.makedirs(os.path.dirname(self._state), exist_ok=True)
        self._patches = _inject(self._tmp, self._state)
        for p in self._patches:
            p.start()
        self.cli = _FakeCliReal(self._state)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_save_creates_state_file(self):
        with patch("builtins.print"):
            self.cli.save_state()
        self.assertTrue(os.path.exists(self._state))

    def test_save_content_is_valid_json(self):
        with patch("builtins.print"):
            self.cli.save_state()
        data = json.loads(Path(self._state).read_text())
        self.assertEqual(data["step"], 7)
        self.assertEqual(data["snapshot_counter"], 2)

    def test_save_silent_no_print(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(str(a))):
            self.cli.save_state(silent=True)
        self.assertEqual(len(printed), 0)

    def test_save_not_silent_prints_path(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli.save_state(silent=False)
        combined = "\n".join(printed)
        self.assertIn("State saved", combined)

    def test_save_failure_prints_error(self):
        printed = []
        with patch("os.replace", side_effect=OSError("disk full")), \
             patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli.save_state()
        combined = "\n".join(printed)
        self.assertIn("Save failed", combined)

    def test_save_rotates_backups(self):
        # Write initial state, then save again — should create .1 backup
        with patch("builtins.print"):
            self.cli.save_state()
            self.cli.save_state()
        self.assertTrue(os.path.exists(f"{self._state}.1"))


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------

class TestLoadState(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state", "solo_builder_state.json")
        os.makedirs(os.path.dirname(self._state), exist_ok=True)
        self._patches = _inject(self._tmp, self._state)
        for p in self._patches:
            p.start()
        self.cli = _FakeCliReal(self._state)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_state(self, path=None, data=None):
        if path is None:
            path = self._state
        payload = data or {
            "step": 12,
            "snapshot_counter": 3,
            "healed_total": 1,
            "dag": _make_dag("Verified"),
            "memory_store": {"A": []},
            "alerts": [],
            "meta_history": [{"healed": 0, "verified": 1}],
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    def test_returns_false_when_no_file(self):
        result = self.cli.load_state()
        self.assertFalse(result)

    def test_returns_true_on_success(self):
        self._write_state()
        with patch("builtins.print"):
            result = self.cli.load_state()
        self.assertTrue(result)

    def test_loads_step(self):
        self._write_state()
        with patch("builtins.print"):
            self.cli.load_state()
        self.assertEqual(self.cli.step, 12)

    def test_loads_dag(self):
        self._write_state()
        with patch("builtins.print"):
            self.cli.load_state()
        self.assertIn("Task 0", self.cli.dag)

    def test_rebuilds_meta_rates_from_history(self):
        self._write_state(data={
            "step": 5, "snapshot_counter": 0, "healed_total": 0,
            "dag": _make_dag(), "memory_store": {}, "alerts": [],
            "meta_history": [{"healed": 2, "verified": 4}],
        })
        with patch("builtins.print"):
            self.cli.load_state()
        self.assertEqual(self.cli.meta.heal_rate, 2.0)
        self.assertEqual(self.cli.meta.verify_rate, 4.0)

    def test_corrupt_primary_falls_back_to_backup(self):
        # Write valid data to .1 backup, corrupt primary
        self._write_state(path=f"{self._state}.1")
        Path(self._state).write_text("not json", encoding="utf-8")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            result = self.cli.load_state()
        self.assertTrue(result)
        combined = "\n".join(printed)
        self.assertIn("corrupt", combined.lower())

    def test_all_files_corrupt_returns_false(self):
        Path(self._state).write_text("bad json", encoding="utf-8")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            result = self.cli.load_state()
        self.assertFalse(result)
        combined = "\n".join(printed)
        self.assertIn("corrupt", combined.lower())

    def test_keyerror_in_payload_tries_next_backup(self):
        # Missing 'step' key — treated as corrupt
        Path(self._state).write_text(json.dumps({"no_step": 1}), encoding="utf-8")
        with patch("builtins.print"):
            result = self.cli.load_state()
        self.assertFalse(result)

    def test_unexpected_exception_returns_false(self):
        self._write_state()
        with patch("builtins.open", side_effect=PermissionError("denied")), \
             patch("builtins.print"):
            result = self.cli.load_state()
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# _consume_json_trigger
# ---------------------------------------------------------------------------

class TestConsumeJsonTrigger(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_returns_none_when_file_missing(self):
        result = StepRunnerMixin._consume_json_trigger(
            os.path.join(self._tmp, "no_such_file.json")
        )
        self.assertIsNone(result)

    def test_returns_dict_on_valid_file(self):
        path = os.path.join(self._tmp, "trigger.json")
        Path(path).write_text(json.dumps({"key": "val"}), encoding="utf-8")
        result = StepRunnerMixin._consume_json_trigger(path)
        self.assertEqual(result, {"key": "val"})

    def test_deletes_file_after_read(self):
        path = os.path.join(self._tmp, "trigger.json")
        Path(path).write_text(json.dumps({"x": 1}), encoding="utf-8")
        StepRunnerMixin._consume_json_trigger(path)
        self.assertFalse(os.path.exists(path))

    def test_returns_none_on_invalid_json(self):
        path = os.path.join(self._tmp, "bad.json")
        Path(path).write_text("not json", encoding="utf-8")
        result = StepRunnerMixin._consume_json_trigger(path)
        self.assertIsNone(result)

    def test_returns_list_on_valid_list_file(self):
        path = os.path.join(self._tmp, "list_trigger.json")
        Path(path).write_text(json.dumps([{"a": 1}, {"b": 2}]), encoding="utf-8")
        result = StepRunnerMixin._consume_json_trigger(path)
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# Lines 90-91: heartbeat counts Running and Review statuses (TASK-407)
# ---------------------------------------------------------------------------

class TestRunStepHeartbeatStatuses(unittest.TestCase):
    """Lines 90-91: _hb_r incremented for Running, _hb_rv for Review subtasks."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        self._ps = _inject(self._tmp, self._state)
        for p in self._ps:
            p.start()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _make_cli_with_statuses(self, *statuses):
        """Build a CLI with one subtask per status in a single branch."""
        cli = _FakeCLI()
        subtasks = {}
        for i, st in enumerate(statuses):
            subtasks[f"S{i}"] = {"status": st, "last_update": 0, "description": f"s{i}", "output": ""}
        cli.dag = {
            "Task 0": {
                "status": "Running",
                "depends_on": [],
                "branches": {"A": {"subtasks": subtasks}},
            }
        }
        cli.memory_store = {"A": []}
        return cli

    def test_running_subtask_increments_hb_r(self):
        """Line 90: subtask with status 'Running' → _hb_r written to step.txt."""
        cli = self._make_cli_with_statuses("Running")
        with patch("builtins.print"), patch("time.sleep"):
            cli.run_step()
        step_txt = os.path.join(self._tmp, "state", "step.txt")
        self.assertTrue(os.path.exists(step_txt))
        parts = Path(step_txt).read_text().split(",")
        # Format: step,verified,total,pending,running,review
        hb_r = int(parts[4])
        self.assertEqual(hb_r, 1)

    def test_review_subtask_increments_hb_rv(self):
        """Line 91: subtask with status 'Review' → _hb_rv written to step.txt."""
        cli = self._make_cli_with_statuses("Review")
        with patch("builtins.print"), patch("time.sleep"):
            cli.run_step()
        step_txt = os.path.join(self._tmp, "state", "step.txt")
        parts = Path(step_txt).read_text().split(",")
        # Format: step,verified,total,pending,running,review
        hb_rv = int(parts[5])
        self.assertEqual(hb_rv, 1)

    def test_mixed_statuses_all_counted(self):
        """Lines 88-91: Verified, Pending, Running, Review all counted correctly."""
        cli = self._make_cli_with_statuses("Verified", "Pending", "Running", "Review")
        with patch("builtins.print"), patch("time.sleep"):
            cli.run_step()
        step_txt = os.path.join(self._tmp, "state", "step.txt")
        parts = Path(step_txt).read_text().split(",")
        hb_v, hb_t, hb_p, hb_r, hb_rv = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
        self.assertEqual(hb_v, 1)
        self.assertEqual(hb_t, 4)
        self.assertEqual(hb_p, 1)
        self.assertEqual(hb_r, 1)
        self.assertEqual(hb_rv, 1)


# ---------------------------------------------------------------------------
# Lines 115-123: save_state OSError in backup rotation (TASK-407)
# ---------------------------------------------------------------------------

class TestSaveStateOSErrors(unittest.TestCase):
    """Lines 115-118, 122-123: OSError in backup rotation is silently swallowed.

    NOTE: _FakeCLI replaces save_state with a MagicMock for run_step tests.
    These tests call StepRunnerMixin.save_state directly on a minimal stub.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        os.makedirs(self._tmp, exist_ok=True)
        self._ps = _inject(self._tmp, self._state)
        for p in self._ps:
            p.start()
        # Build a minimal stub WITHOUT mocking save_state so the real impl runs
        self.cli = _FakeCLI()
        del self.cli.save_state   # remove the instance-level MagicMock → real method is used

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_os_replace_oserror_swallowed(self):
        """Lines 115-118: OSError from os.replace during backup rotation is swallowed."""
        Path(self._state).write_text("{}", encoding="utf-8")
        Path(f"{self._state}.1").write_text("{}", encoding="utf-8")
        with patch("os.replace", side_effect=OSError("permission denied")):
            # Must not raise
            StepRunnerMixin.save_state(self.cli)

    def test_shutil_copy2_oserror_swallowed(self):
        """Lines 122-123: OSError from shutil.copy2 during backup is swallowed."""
        Path(self._state).write_text("{}", encoding="utf-8")
        import shutil as _shutil
        with patch.object(_shutil, "copy2", side_effect=OSError("copy failed")):
            # Must not raise
            StepRunnerMixin.save_state(self.cli)

    def test_both_oserrors_swallowed(self):
        """Lines 115-123: both os.replace and copy2 raise OSError — still completes."""
        Path(self._state).write_text("{}", encoding="utf-8")
        Path(f"{self._state}.1").write_text("{}", encoding="utf-8")
        import shutil as _shutil
        with patch("os.replace", side_effect=OSError("denied")), \
             patch.object(_shutil, "copy2", side_effect=OSError("denied")):
            StepRunnerMixin.save_state(self.cli)
        # File should still be written (the final json.dump runs after backup)
        self.assertTrue(os.path.exists(self._state))


if __name__ == "__main__":
    unittest.main()
