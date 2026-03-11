"""Tests for AutoCommandsMixin._cmd_auto (TASK-405)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.auto_cmds as ac_module
from commands.auto_cmds import AutoCommandsMixin


# ---------------------------------------------------------------------------
# Inject module globals
# ---------------------------------------------------------------------------

def _patches(tmp_dir: str) -> list:
    return [
        patch.object(ac_module, "AUTO_STEP_DELAY", new=0.0, create=True),
        patch.object(ac_module, "_HERE", new=tmp_dir, create=True),
        patch.object(ac_module, "logger", new=MagicMock(), create=True),
        patch.object(ac_module, "YELLOW", new="", create=True),
        patch.object(ac_module, "RESET", new="", create=True),
        patch.object(ac_module, "CYAN", new="", create=True),
        patch.object(ac_module, "GREEN", new="", create=True),
        patch.object(ac_module, "make_bar", new=lambda *a, **kw: "====", create=True),
        patch.object(ac_module, "dag_stats",
                     new=lambda dag: {"verified": 0, "total": 2, "running": 0},
                     create=True),
        patch.object(ac_module, "validate_dag", new=lambda dag: [], create=True),
        patch.object(ac_module, "_fire_completion", new=MagicMock(), create=True),
    ]


# ---------------------------------------------------------------------------
# Shared stub
# ---------------------------------------------------------------------------

class _FakeCLI(AutoCommandsMixin):
    def __init__(self):
        self.dag = {
            "Task 0": {
                "status": "Running",
                "depends_on": [],
                "branches": {
                    "A": {"subtasks": {"A1": {"status": "Pending", "last_update": 0}}}
                },
            }
        }
        self.step = 0
        self.memory_store = {"A": []}
        self.alerts = []
        self._runtime_cfg = {"AUTO_STEP_DELAY": 0.2}
        self.run_step = MagicMock()
        self.save_state = MagicMock()
        self.display = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        self._cmd_verify = MagicMock()
        self._cmd_add_task = MagicMock()
        self._cmd_add_branch = MagicMock()
        self._cmd_prioritize_branch = MagicMock()
        self._cmd_describe = MagicMock()
        self._cmd_rename = MagicMock()
        self._cmd_tools = MagicMock()
        self._cmd_set = MagicMock()
        self._cmd_heal = MagicMock()
        self._cmd_depends = MagicMock()
        self._cmd_undepends = MagicMock()
        self._cmd_reset = MagicMock()
        self._take_snapshot = MagicMock()
        self._cmd_undo = MagicMock()
        self.shadow = MagicMock()
        self._consume_json_trigger = MagicMock(return_value=None)
        self._last_priority_step = 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCmdAuto(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._ps = _patches(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _run(self, args=""):
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto(args)

    def test_invalid_args_prints_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_auto("xyz")
        combined = "\n".join(printed)
        self.assertIn("Usage", combined)

    def test_invalid_args_does_not_call_run_step(self):
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("xyz")
        self.cli.run_step.assert_not_called()

    def test_already_complete_prints_message(self):
        # Patch dag_stats to say all verified
        with patch.object(ac_module, "dag_stats",
                          new=lambda dag: {"verified": 2, "total": 2, "running": 0}, create=True):
            printed = []
            with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
                 patch("time.sleep"):
                self.cli._cmd_auto("")
        combined = "\n".join(printed)
        self.assertIn("complete", combined.lower())

    def test_already_complete_does_not_run_step(self):
        with patch.object(ac_module, "dag_stats",
                          new=lambda dag: {"verified": 2, "total": 2, "running": 0}, create=True):
            with patch("builtins.print"), patch("time.sleep"):
                self.cli._cmd_auto("")
        self.cli.run_step.assert_not_called()

    def test_limit_n_runs_exactly_n_steps(self):
        # dag_stats always returns 0 verified (never complete)
        self._run("3")
        self.assertEqual(self.cli.run_step.call_count, 3)

    def test_no_limit_exits_when_complete(self):
        # dag_stats returns not-complete on pre-loop check (call 1),
        # then complete after run_step (call 2) → exactly 1 run_step
        call_count = [0]
        def _stats(dag):
            call_count[0] += 1
            if call_count[0] >= 2:
                return {"verified": 2, "total": 2, "running": 0}
            return {"verified": 0, "total": 2, "running": 0}
        with patch.object(ac_module, "dag_stats", new=_stats, create=True):
            with patch("builtins.print"), patch("time.sleep"):
                self.cli._cmd_auto("")
        self.assertEqual(self.cli.run_step.call_count, 1)
        self.cli.save_state.assert_called_with(silent=True)

    def test_keyboard_interrupt_pauses(self):
        self.cli.run_step.side_effect = KeyboardInterrupt
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_auto("")
        combined = "\n".join(printed)
        self.assertIn("paused", combined.lower())

    def test_stop_trigger_stops_loop(self):
        stoptrig = os.path.join(self._tmp, "state", "stop_trigger")
        os.makedirs(os.path.dirname(stoptrig), exist_ok=True)
        # Create stop trigger so the inner wait loop stops immediately
        Path(stoptrig).write_text("stop")
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_auto("10")
        combined = "\n".join(printed)
        # Should have stopped remotely
        self.assertIn("stopped", combined.lower())

    def test_run_trigger_breaks_wait(self):
        # run_trigger inside inner wait loop skips the delay and starts next step
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        runtrig = os.path.join(self._tmp, "state", "run_trigger")
        Path(runtrig).write_text("go")
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        # Should complete normally; run_trigger was consumed
        self.assertFalse(os.path.exists(runtrig))

    def test_verify_trigger_calls_cmd_verify(self):
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        def _consume(path):
            if "verify_trigger" in path:
                return {"subtask": "A1", "note": "done"}
            return None
        self.cli._consume_json_trigger = _consume
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        self.cli._cmd_verify.assert_called()

    def test_dag_import_trigger_updates_dag(self):
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        import json as _json
        new_dag = {"Task X": {"status": "Pending", "depends_on": [], "branches": {}}}
        def _consume(path):
            if "dag_import_trigger" in path:
                return {"dag": new_dag, "exported_step": 5}
            return None
        self.cli._consume_json_trigger = _consume
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        self.assertIn("Task X", self.cli.dag)


class TestCmdAutoTriggers(unittest.TestCase):
    """Test individual trigger dispatch inside _cmd_auto inner loop."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        self._ps = _patches(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _run_one_step_with_trigger_data(self, trigger_name, data):
        """Run 2 auto steps so the inner wait loop fires after step 1."""
        def _consume(path):
            if trigger_name in path:
                return data
            return None
        self.cli._consume_json_trigger = _consume
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")

    def test_add_task_trigger(self):
        self._run_one_step_with_trigger_data("add_task_trigger", {"spec": "build the thing"})
        self.cli._cmd_add_task.assert_called_with("build the thing")

    def test_add_branch_trigger(self):
        self._run_one_step_with_trigger_data(
            "add_branch_trigger", {"task": "Task 0", "spec": "new branch spec"}
        )
        self.cli._cmd_add_branch.assert_called_with("Task 0", spec_override="new branch spec")

    def test_prioritize_branch_trigger(self):
        self._run_one_step_with_trigger_data(
            "prioritize_branch_trigger", {"task": "Task 0", "branch": "A"}
        )
        self.cli._cmd_prioritize_branch.assert_called_with("Task 0", "A")

    def test_describe_trigger(self):
        self._run_one_step_with_trigger_data(
            "describe_trigger", {"subtask": "a1", "desc": "do the thing"}
        )
        self.cli._cmd_describe.assert_called_with("A1 do the thing")

    def test_rename_trigger(self):
        self._run_one_step_with_trigger_data(
            "rename_trigger", {"subtask": "a1", "desc": "new name"}
        )
        self.cli._cmd_rename.assert_called_with("A1 new name")

    def test_tools_trigger(self):
        self._run_one_step_with_trigger_data(
            "tools_trigger", {"subtask": "a1", "tools": "Read,Glob"}
        )
        self.cli._cmd_tools.assert_called_with("A1 Read,Glob")

    def test_set_trigger(self):
        self._run_one_step_with_trigger_data(
            "set_trigger", {"key": "STALL_THRESHOLD", "value": "10"}
        )
        self.cli._cmd_set.assert_called_with("STALL_THRESHOLD=10")

    def test_heal_trigger(self):
        self._run_one_step_with_trigger_data(
            "heal_trigger", {"subtask": "a1"}
        )
        self.cli._cmd_heal.assert_called_with("A1")

    def test_depends_trigger(self):
        self._run_one_step_with_trigger_data(
            "depends_trigger", {"target": "Task 1", "dep": "Task 0"}
        )
        self.cli._cmd_depends.assert_called_with("Task 1 Task 0")

    def test_reset_trigger(self):
        rtrig = os.path.join(self._tmp, "state", "reset_trigger")
        Path(rtrig).write_text("reset")
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        self.cli._cmd_reset.assert_called_once()

    def test_snapshot_trigger(self):
        snaptrig = os.path.join(self._tmp, "state", "snapshot_trigger")
        Path(snaptrig).write_text("snap")
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        self.cli._take_snapshot.assert_called_with(auto=False)

    def test_undo_trigger(self):
        undotrig = os.path.join(self._tmp, "state", "undo_trigger")
        Path(undotrig).write_text("undo")
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        self.cli._cmd_undo.assert_called_once()


class TestCmdAutoOSErrorPaths(unittest.TestCase):
    """Cover the `except OSError: pass` branches inside the inner wait loop (lines 93-94,
    179-180, 185-186, 191-192, 208-209)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        self._ps = _patches(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _run(self, args="2"):
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto(args)

    def test_stop_trigger_remove_oserror_is_silenced(self):
        """Lines 93-94: os.remove(stop_trigger) raising OSError is swallowed."""
        stoptrig = os.path.join(self._tmp, "state", "stop_trigger")
        Path(stoptrig).write_text("stop")
        real_remove = os.remove
        def _bad_remove(p):
            if "stop_trigger" in p:
                raise OSError("denied")
            real_remove(p)
        with patch("os.remove", side_effect=_bad_remove):
            self._run()  # must not raise

    def test_reset_trigger_remove_oserror_is_silenced(self):
        """Lines 179-180: os.remove(reset_trigger) raising OSError is swallowed."""
        rtrig = os.path.join(self._tmp, "state", "reset_trigger")
        Path(rtrig).write_text("reset")
        real_remove = os.remove
        def _bad_remove(p):
            if "reset_trigger" in p:
                raise OSError("denied")
            real_remove(p)
        with patch("os.remove", side_effect=_bad_remove):
            self._run()
        self.cli._cmd_reset.assert_called()

    def test_snapshot_trigger_remove_oserror_is_silenced(self):
        """Lines 185-186: os.remove(snapshot_trigger) raising OSError is swallowed."""
        snaptrig = os.path.join(self._tmp, "state", "snapshot_trigger")
        Path(snaptrig).write_text("snap")
        real_remove = os.remove
        def _bad_remove(p):
            if "snapshot_trigger" in p:
                raise OSError("denied")
            real_remove(p)
        with patch("os.remove", side_effect=_bad_remove):
            self._run()
        self.cli._take_snapshot.assert_called()

    def test_undo_trigger_remove_oserror_is_silenced(self):
        """Lines 191-192: os.remove(undo_trigger) raising OSError is swallowed."""
        undotrig = os.path.join(self._tmp, "state", "undo_trigger")
        Path(undotrig).write_text("undo")
        real_remove = os.remove
        def _bad_remove(p):
            if "undo_trigger" in p:
                raise OSError("denied")
            real_remove(p)
        with patch("os.remove", side_effect=_bad_remove):
            self._run()
        self.cli._cmd_undo.assert_called()

    def test_run_trigger_remove_oserror_is_silenced(self):
        """Lines 208-209: os.remove(run_trigger) raising OSError is swallowed."""
        runtrig = os.path.join(self._tmp, "state", "run_trigger")
        Path(runtrig).write_text("go")
        real_remove = os.remove
        def _bad_remove(p):
            if "run_trigger" in p:
                raise OSError("denied")
            real_remove(p)
        with patch("os.remove", side_effect=_bad_remove):
            self._run()  # must not raise


class TestCmdAutoUndepends(unittest.TestCase):
    """Cover lines 165-175: undepends_trigger JSON file."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        self._ps = _patches(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_undepends_trigger_calls_cmd_undepends(self):
        import json as _json
        undeptrig = os.path.join(self._tmp, "state", "undepends_trigger.json")
        Path(undeptrig).write_text(_json.dumps({"target": "Task 1", "dep": "Task 0"}))
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        self.cli._cmd_undepends.assert_called_with("Task 1 Task 0")

    def test_undepends_trigger_bad_json_silenced(self):
        """Lines 174-175: bad JSON is caught and swallowed."""
        undeptrig = os.path.join(self._tmp, "state", "undepends_trigger.json")
        Path(undeptrig).write_text("{bad json}")
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_auto("2")
        self.cli._cmd_undepends.assert_not_called()


class TestCmdAutoPauseGate(unittest.TestCase):
    """Cover lines 99-105: pause gate in inner wait loop."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self._tmp, "state"), exist_ok=True)
        self._ps = _patches(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_pause_gate_prints_paused_message(self):
        """Lines 99-101: pause_trigger present → prints 'paused remotely' and waits."""
        pausetrig = os.path.join(self._tmp, "state", "pause_trigger")
        stoptrig = os.path.join(self._tmp, "state", "stop_trigger")
        Path(pausetrig).write_text("1")
        # Pause while loop: iteration 1 returns True, iteration 2 creates stop_trigger
        # (covers line 105), iteration 3 returns False (exits pause while)
        call_count = [0]
        real_exists = os.path.exists
        def _exists(p):
            if "pause_trigger" in p:
                call_count[0] += 1
                if call_count[0] == 2:
                    # Create stop_trigger so line 104-105 fires on this iteration
                    Path(stoptrig).write_text("stop")
                return call_count[0] <= 2  # True for first 2 checks, False after
            return real_exists(p)
        printed = []
        with patch("os.path.exists", side_effect=_exists), \
             patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_auto("2")
        combined = "\n".join(printed)
        self.assertIn("paused", combined.lower())


if __name__ == "__main__":
    unittest.main()
