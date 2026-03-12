"""Tests for SubtaskCommandsMixin — _find_subtask, _cmd_describe, _cmd_verify,
_cmd_tools, _cmd_rename, _cmd_heal, _cmd_pause, _cmd_resume (TASK-406)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.subtask_cmds as sc_module
from commands.subtask_cmds import SubtaskCommandsMixin


# ---------------------------------------------------------------------------
# Module-level globals injection
# ---------------------------------------------------------------------------

def _inject(tmp_dir: str) -> list:
    return [
        patch.object(sc_module, "os", new=os, create=True),
        patch.object(sc_module, "_HERE", new=tmp_dir, create=True),
        patch.object(sc_module, "add_memory_snapshot",
                     new=lambda store, branch, key, step: None, create=True),
    ]


# ---------------------------------------------------------------------------
# Shared CLI stub
# ---------------------------------------------------------------------------

def _st(status="Pending", description=""):
    return {
        "status": status,
        "output": "",
        "description": description,
        "shadow": "Pending",
        "history": [],
        "last_update": 0,
    }


class _FakeCLI(SubtaskCommandsMixin):
    def __init__(self):
        self.dag = {
            "Task 0": {
                "status": "Running",
                "depends_on": [],
                "branches": {
                    "A": {
                        "status": "Running",
                        "subtasks": {
                            "A1": _st("Pending", "do alpha"),
                            "A2": _st("Running", "do beta"),
                            "A3": _st("Verified", "do gamma"),
                        }
                    }
                },
            }
        }
        self.step = 5
        self.memory_store = {"A": []}
        self.alerts = []
        self.display = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        self.executor = MagicMock()
        self.healer = MagicMock()
        self.healer.healed_total = 0


# ---------------------------------------------------------------------------
# _find_subtask
# ---------------------------------------------------------------------------

class TestFindSubtask(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_returns_none_when_not_found(self):
        self.assertIsNone(self.cli._find_subtask("ZZ"))

    def test_returns_tuple_when_found(self):
        result = self.cli._find_subtask("A1")
        self.assertIsNotNone(result)
        task_name, task_data, branch_name, branch_data, st = result
        self.assertEqual(task_name, "Task 0")
        self.assertEqual(branch_name, "A")

    def test_last_match_wins_on_collision(self):
        """If two tasks share a subtask name, last one wins."""
        self.cli.dag["Task 1"] = {
            "status": "Pending", "depends_on": [],
            "branches": {"B": {"status": "Pending", "subtasks": {
                "A1": _st("Verified", "collision winner")
            }}}
        }
        result = self.cli._find_subtask("A1")
        task_name, _, _, _, st = result
        self.assertEqual(task_name, "Task 1")


# ---------------------------------------------------------------------------
# _cmd_describe
# ---------------------------------------------------------------------------

class TestCmdDescribe(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_no_args_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_describe("")
        self.assertIn("Usage", "\n".join(printed))

    def test_not_found_prints_warning(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_describe("ZZ do something")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_sets_description_and_status(self):
        with patch("builtins.print"):
            self.cli._cmd_describe("A1 new desc")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertEqual(st["description"], "new desc")
        self.assertEqual(st["status"], "Running")

    def test_calls_display_render(self):
        with patch("builtins.print"):
            self.cli._cmd_describe("A1 test desc")
        self.cli.display.render.assert_called_once()


# ---------------------------------------------------------------------------
# _cmd_verify
# ---------------------------------------------------------------------------

class TestCmdVerify(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_empty_args_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_verify("")
        self.assertIn("Usage", "\n".join(printed))

    def test_not_found_prints_warning(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_verify("ZZ")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_sets_status_verified(self):
        with patch("builtins.print"):
            self.cli._cmd_verify("A1")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Verified")

    def test_uses_custom_note(self):
        with patch("builtins.print"):
            self.cli._cmd_verify("A1 my custom note")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertEqual(st["output"], "my custom note")

    def test_default_note(self):
        with patch("builtins.print"):
            self.cli._cmd_verify("A1")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertIn("Manually", st["output"])

    def test_calls_roll_up(self):
        with patch("builtins.print"):
            self.cli._cmd_verify("A1")
        self.cli.executor._roll_up.assert_called_once_with(
            self.cli.dag, "Task 0", "A"
        )

    def test_appends_history(self):
        with patch("builtins.print"):
            self.cli._cmd_verify("A1")
        history = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "Verified")


# ---------------------------------------------------------------------------
# _cmd_tools
# ---------------------------------------------------------------------------

class TestCmdTools(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_no_args_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_tools("")
        self.assertIn("Usage", "\n".join(printed))

    def test_not_found_prints_warning(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_tools("ZZ Read")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_sets_tools(self):
        with patch("builtins.print"):
            self.cli._cmd_tools("A1 Read,Glob")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertEqual(st["tools"], "Read,Glob")

    def test_none_clears_tools(self):
        with patch("builtins.print"):
            self.cli._cmd_tools("A1 none")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertEqual(st["tools"], "")

    def test_unknown_tool_warns(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_tools("A1 FakeTool")
        combined = "\n".join(printed)
        self.assertIn("unrecognised", combined.lower())

    def test_verified_subtask_re_queued(self):
        with patch("builtins.print"):
            self.cli._cmd_tools("A3 Read")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A3"]
        self.assertEqual(st["status"], "Running")


# ---------------------------------------------------------------------------
# _cmd_rename
# ---------------------------------------------------------------------------

class TestCmdRename(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_empty_arg_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_rename("")
        self.assertIn("Usage", "\n".join(printed))

    def test_no_description_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_rename("A1")
        self.assertIn("Usage", "\n".join(printed))

    def test_not_found_prints_warning(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_rename("ZZ new name")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_sets_new_description(self):
        with patch("builtins.print"):
            self.cli._cmd_rename("A1 renamed thing")
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertEqual(st["description"], "renamed thing")

    def test_prints_old_description_when_present(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_rename("A1 new name")
        combined = "\n".join(printed)
        # Old description was "do alpha"
        self.assertIn("do alpha", combined)


# ---------------------------------------------------------------------------
# _cmd_heal
# ---------------------------------------------------------------------------

class TestCmdHeal(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._ps = _inject(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_empty_arg_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_heal("")
        self.assertIn("Usage", "\n".join(printed))

    def test_not_found_prints_warning(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_heal("ZZ")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_non_running_subtask_shows_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_heal("A1")  # A1 is Pending, not Running
        combined = "\n".join(printed)
        self.assertIn("not Running", combined)

    def test_resets_running_to_pending(self):
        with patch("builtins.print"):
            self.cli._cmd_heal("A2")  # A2 is Running
        st = self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A2"]
        self.assertEqual(st["status"], "Pending")

    def test_increments_healer_count(self):
        with patch("builtins.print"):
            self.cli._cmd_heal("A2")
        self.assertEqual(self.cli.healer.healed_total, 1)

    def test_calls_display_render(self):
        with patch("builtins.print"):
            self.cli._cmd_heal("A2")
        self.cli.display.render.assert_called_once()


# ---------------------------------------------------------------------------
# _cmd_pause
# ---------------------------------------------------------------------------

class TestCmdPause(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._ps = _inject(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_creates_pause_trigger(self):
        with patch("builtins.print"):
            self.cli._cmd_pause()
        p = os.path.join(self._tmp, "state", "pause_trigger")
        self.assertTrue(os.path.exists(p))

    def test_already_paused_prints_message(self):
        state_dir = os.path.join(self._tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        Path(os.path.join(state_dir, "pause_trigger")).write_text("1")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_pause()
        self.assertIn("Already paused", "\n".join(printed))


# ---------------------------------------------------------------------------
# _cmd_resume
# ---------------------------------------------------------------------------

class TestCmdResume(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._ps = _inject(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_not_paused_prints_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_resume()
        self.assertIn("Not paused", "\n".join(printed))

    def test_removes_pause_trigger(self):
        state_dir = os.path.join(self._tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        p = os.path.join(state_dir, "pause_trigger")
        Path(p).write_text("1")
        with patch("builtins.print"):
            self.cli._cmd_resume()
        self.assertFalse(os.path.exists(p))

    def test_prints_resumed_message(self):
        state_dir = os.path.join(self._tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        Path(os.path.join(state_dir, "pause_trigger")).write_text("1")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_resume()
        self.assertIn("Resumed", "\n".join(printed))


# ---------------------------------------------------------------------------
# _cmd_resume lines 181-182: OSError on os.remove swallowed (TASK-407)
# ---------------------------------------------------------------------------

class TestCmdResumeOSError(unittest.TestCase):
    """Lines 181-182: OSError when removing pause_trigger is silently swallowed."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._ps = _inject(self._tmp)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_oserror_on_remove_swallowed(self):
        """Lines 181-182: os.remove raises OSError → swallowed, 'Resumed' still printed."""
        state_dir = os.path.join(self._tmp, "state")
        os.makedirs(state_dir, exist_ok=True)
        trigger = os.path.join(state_dir, "pause_trigger")
        Path(trigger).write_text("1")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("os.remove", side_effect=OSError("locked")):
            self.cli._cmd_resume()
        self.assertIn("Resumed", "\n".join(printed))


if __name__ == "__main__":
    unittest.main()
