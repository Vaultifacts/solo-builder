"""Coverage tests for discord_bot/bot_commands.py — pure function tests.

Imports via solo_builder.discord_bot path so coverage tracks correctly.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Bootstrap discord stubs before importing bot modules
discord_stub = MagicMock()
discord_stub.Intents.default.return_value = MagicMock()
discord_stub.Client = type("FakeClient", (), {"__init__": lambda self, **kw: None})
discord_stub.Interaction = MagicMock
discord_stub.File = MagicMock
sys.modules.setdefault("discord", discord_stub)
sys.modules.setdefault("discord.app_commands", MagicMock())
sys.modules.setdefault("dotenv", MagicMock())

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("DISCORD_CHANNEL_ID", "0")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import discord_bot.bot as bot_mod
import discord_bot.bot_commands as cmd_mod

# Ensure lazy import resolves
sys.modules["solo_builder.discord_bot.bot"] = bot_mod
sys.modules["solo_builder.discord_bot.bot_commands"] = cmd_mod
sys.modules["solo_builder.discord_bot.bot_formatters"] = sys.modules["discord_bot.bot_formatters"]


def _state(subtasks=None, step=5):
    sts = subtasks or {"A1": {"status": "Running", "last_update": 0, "output": "out"}}
    return {"step": step, "dag": {"Task0": {"status": "Pending", "branches": {
        "BranchA": {"status": "Pending", "subtasks": sts}
    }}}}


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path = Path(self._tmp) / "state.json"
        self._heal_trigger = Path(self._tmp) / "heal.json"
        self._patches = [
            patch.object(bot_mod, "STATE_PATH", new=self._state_path),
            patch.object(bot_mod, "HEAL_TRIGGER", new=self._heal_trigger),
            patch.object(cmd_mod, "_bot", return_value=bot_mod),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestFormatHeal(_Base):
    def test_heal_empty_subtask(self):
        r = cmd_mod._format_heal(_state(), "")
        self.assertIn("Usage", r)

    def test_heal_not_found(self):
        r = cmd_mod._format_heal(_state(), "ZZZ")
        self.assertIn("not found", r)

    def test_heal_not_running(self):
        st = {"A1": {"status": "Verified", "last_update": 0, "output": ""}}
        r = cmd_mod._format_heal(_state(st), "A1")
        self.assertIn("Verified", r)

    def test_heal_success(self):
        r = cmd_mod._format_heal(_state(), "A1")
        self.assertIn("heal trigger", r)
        self.assertTrue(self._heal_trigger.exists())


class TestFormatResetTask(_Base):
    def test_reset_task_empty(self):
        r = cmd_mod._format_reset_task(_state(), "")
        self.assertIn("Usage", r)

    def test_reset_task_not_found(self):
        r = cmd_mod._format_reset_task(_state(), "NOPE")
        self.assertIn("not found", r)

    def test_reset_task_success(self):
        state = _state({"A1": {"status": "Running", "output": "x"},
                        "A2": {"status": "Verified", "output": "y"}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_reset_task(state, "Task0")
        self.assertIn("reset", r)
        self.assertIn("1 subtask", r)
        self.assertIn("Verified preserved", r)


class TestFormatResetBranch(_Base):
    def test_reset_branch_empty(self):
        r = cmd_mod._format_reset_branch(_state(), "", "")
        self.assertIn("Usage", r)

    def test_reset_branch_task_not_found(self):
        r = cmd_mod._format_reset_branch(_state(), "NOPE", "BranchA")
        self.assertIn("not found", r)

    def test_reset_branch_branch_not_found(self):
        r = cmd_mod._format_reset_branch(_state(), "Task0", "NOPE")
        self.assertIn("not found", r)

    def test_reset_branch_success(self):
        state = _state({"A1": {"status": "Running", "output": "x"}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_reset_branch(state, "Task0", "BranchA")
        self.assertIn("reset", r)


class TestFormatBulkReset(_Base):
    def test_bulk_reset_empty(self):
        r = cmd_mod._format_bulk_reset(_state(), [])
        self.assertIn("Usage", r)

    def test_bulk_reset_success(self):
        state = _state({"A1": {"status": "Running", "output": "x"},
                        "A2": {"status": "Verified", "output": "y"}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_bulk_reset(state, ["A1", "A2"])
        self.assertIn("Pending", r)

    def test_bulk_reset_not_found(self):
        state = _state()
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_bulk_reset(state, ["ZZZ"])
        self.assertIn("not found", r)


class TestFormatBulkVerify(_Base):
    def test_bulk_verify_empty(self):
        r = cmd_mod._format_bulk_verify(_state(), [])
        self.assertIn("Usage", r)

    def test_bulk_verify_success(self):
        state = _state({"A1": {"status": "Running", "output": "x"}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_bulk_verify(state, ["A1"])
        self.assertIn("Verified", r)

    def test_bulk_verify_already_verified(self):
        state = _state({"A1": {"status": "Verified", "output": "x"}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_bulk_verify(state, ["A1"])
        self.assertIn("skipped", r)


class TestHelpText(unittest.TestCase):
    def test_help_text_exists(self):
        self.assertIn("status", cmd_mod._HELP_TEXT)

    def test_key_map_has_entries(self):
        self.assertIn("STALL_THRESHOLD", cmd_mod._KEY_MAP)


# ---------------------------------------------------------------------------
# _handle_text_command dispatcher tests
# ---------------------------------------------------------------------------

import asyncio
from unittest.mock import AsyncMock


class _DispatchBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._sp = Path(self._tmp) / "state"
        self._sp.mkdir()
        # Patch all trigger paths (module-level globals in bot.py)
        attrs = {
            "STATE_PATH": self._sp / "state.json",
            "SETTINGS_PATH": self._sp / "settings.json",
            "TRIGGER_PATH": self._sp / "run_trigger",
            "STOP_TRIGGER": self._sp / "stop_trigger",
            "VERIFY_TRIGGER": self._sp / "verify.json",
            "DESCRIBE_TRIGGER": self._sp / "describe.json",
            "TOOLS_TRIGGER": self._sp / "tools.json",
            "RENAME_TRIGGER": self._sp / "rename.json",
            "HEAL_TRIGGER": self._sp / "heal.json",
            "ADD_TASK_TRIGGER": self._sp / "add_task.json",
            "ADD_BRANCH_TRIGGER": self._sp / "add_branch.json",
            "PRIORITY_BRANCH_TRIGGER": self._sp / "priority.json",
            "DEPENDS_TRIGGER": self._sp / "depends.json",
            "UNDEPENDS_TRIGGER": self._sp / "undepends.json",
            "RESET_TRIGGER": self._sp / "reset_trigger",
            "SNAPSHOT_TRIGGER": self._sp / "snapshot_trigger",
            "PAUSE_TRIGGER": self._sp / "pause_trigger",
            "UNDO_TRIGGER": self._sp / "undo_trigger",
            "SET_TRIGGER": self._sp / "set.json",
            "OUTPUTS_PATH": self._sp / "outputs.md",
            "SNAPSHOTS_DIR": self._sp / "snapshots",
            "STEP_PATH": self._sp / "step.txt",
        }
        (self._sp / "settings.json").write_text("{}", encoding="utf-8")
        self._patches = [patch.object(bot_mod, k, new=v) for k, v in attrs.items()]
        self._patches.append(patch.object(cmd_mod, "_bot", return_value=bot_mod))
        bot_mod._send = AsyncMock()
        bot_mod._load_state = MagicMock(return_value=_state())
        bot_mod._auto_running = MagicMock(return_value=False)
        bot_mod._read_heartbeat = MagicMock(return_value=None)
        bot_mod._auto_task = None
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _msg(self, content):
        m = MagicMock()
        m.content = content
        m.channel = MagicMock()
        m.channel.id = 123
        return m

    def _run(self, content):
        asyncio.run(cmd_mod._handle_text_command(self._msg(content)))


class TestDispatchStatus(_DispatchBase):
    def test_status(self):
        self._run("status")
        bot_mod._send.assert_called_once()

    def test_status_auto_running(self):
        bot_mod._auto_running.return_value = True
        bot_mod.PAUSE_TRIGGER.write_text("1")
        self._run("status")
        args = bot_mod._send.call_args[0]
        self.assertIn("paused", args[1])


class TestDispatchRun(_DispatchBase):
    def test_run_has_work(self):
        self._run("run")
        self.assertTrue(bot_mod.TRIGGER_PATH.exists())

    def test_run_complete(self):
        bot_mod._load_state.return_value = _state({"A1": {"status": "Verified", "last_update": 0, "output": ""}})
        self._run("run")
        args = bot_mod._send.call_args[0]
        self.assertIn("complete", args[1])


class TestDispatchVerify(_DispatchBase):
    def test_verify_usage(self):
        self._run("verify")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_verify_with_subtask(self):
        self._run("verify A1 looks good")
        self.assertTrue(bot_mod.VERIFY_TRIGGER.exists())


class TestDispatchAddTask(_DispatchBase):
    def test_add_task_usage(self):
        self._run("add_task")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_add_task_success(self):
        self._run("add_task Build OAuth flow")
        self.assertTrue(bot_mod.ADD_TASK_TRIGGER.exists())


class TestDispatchAddBranch(_DispatchBase):
    def test_add_branch_usage(self):
        self._run("add_branch")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_add_branch_success(self):
        self._run("add_branch 0 Add error handling")
        self.assertTrue(bot_mod.ADD_BRANCH_TRIGGER.exists())


class TestDispatchOutput(_DispatchBase):
    def test_output_usage(self):
        self._run("output")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_output_found(self):
        self._run("output A1")
        bot_mod._send.assert_called_once()


class TestDispatchDescribe(_DispatchBase):
    def test_describe_usage(self):
        self._run("describe A1")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_describe_success(self):
        self._run("describe A1 Implement retry logic")
        self.assertTrue(bot_mod.DESCRIBE_TRIGGER.exists())


class TestDispatchTools(_DispatchBase):
    def test_tools_usage(self):
        self._run("tools A1")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_tools_success(self):
        self._run("tools A1 Read,Glob,Grep")
        self.assertTrue(bot_mod.TOOLS_TRIGGER.exists())


class TestDispatchReset(_DispatchBase):
    def test_reset_warn(self):
        self._run("reset")
        args = bot_mod._send.call_args[0]
        self.assertIn("destroy", args[1])

    def test_reset_confirm(self):
        self._run("reset confirm")
        self.assertTrue(bot_mod.RESET_TRIGGER.exists())


class TestDispatchSimpleCommands(_DispatchBase):
    def test_undo(self):
        self._run("undo")
        self.assertTrue(bot_mod.UNDO_TRIGGER.exists())

    def test_stop(self):
        self._run("stop")
        self.assertTrue(bot_mod.STOP_TRIGGER.exists())

    def test_graph(self):
        self._run("graph")
        bot_mod._send.assert_called_once()

    def test_priority(self):
        self._run("priority")
        bot_mod._send.assert_called_once()

    def test_stalled(self):
        self._run("stalled")
        bot_mod._send.assert_called_once()

    def test_agents(self):
        self._run("agents")
        bot_mod._send.assert_called_once()

    def test_forecast(self):
        self._run("forecast")
        bot_mod._send.assert_called_once()

    def test_tasks(self):
        self._run("tasks")
        bot_mod._send.assert_called_once()

    def test_diff(self):
        self._run("diff")
        bot_mod._send.assert_called_once()

    def test_stats(self):
        self._run("stats")
        bot_mod._send.assert_called_once()

    def test_cache(self):
        self._run("cache")
        bot_mod._send.assert_called_once()

    def test_cache_clear(self):
        self._run("cache clear")
        bot_mod._send.assert_called_once()

    def test_help(self):
        self._run("help")
        args = bot_mod._send.call_args[0]
        self.assertIn("status", args[1])

    def test_help_question(self):
        self._run("?")
        bot_mod._send.assert_called_once()


class TestDispatchHistory(_DispatchBase):
    def test_history_default(self):
        self._run("history")
        bot_mod._send.assert_called_once()

    def test_history_with_n(self):
        self._run("history 5")
        bot_mod._send.assert_called_once()


class TestDispatchSearch(_DispatchBase):
    def test_search(self):
        self._run("search auth")
        bot_mod._send.assert_called_once()


class TestDispatchFilter(_DispatchBase):
    def test_filter(self):
        self._run("filter Running")
        bot_mod._send.assert_called_once()


class TestDispatchTimeline(_DispatchBase):
    def test_timeline(self):
        self._run("timeline A1")
        bot_mod._send.assert_called_once()


class TestDispatchLog(_DispatchBase):
    def test_log(self):
        self._run("log A1")
        bot_mod._send.assert_called_once()


class TestDispatchBranches(_DispatchBase):
    def test_branches(self):
        self._run("branches")
        bot_mod._send.assert_called_once()


class TestDispatchSubtasks(_DispatchBase):
    def test_subtasks(self):
        self._run("subtasks")
        bot_mod._send.assert_called_once()

    def test_subtasks_with_filters(self):
        self._run("subtasks task=Task0 status=Running")
        bot_mod._send.assert_called_once()


class TestDispatchRename(_DispatchBase):
    def test_rename_usage(self):
        self._run("rename A1")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_rename_success(self):
        self._run("rename A1 New description")
        self.assertTrue(bot_mod.RENAME_TRIGGER.exists())


class TestDispatchHeartbeat(_DispatchBase):
    def test_heartbeat_no_data(self):
        self._run("heartbeat")
        args = bot_mod._send.call_args[0]
        self.assertIn("No heartbeat", args[1])

    def test_heartbeat_with_data(self):
        bot_mod._read_heartbeat.return_value = (10, 5, 20, 8, 3, 4)
        self._run("heartbeat")
        args = bot_mod._send.call_args[0]
        self.assertIn("Step 10", args[1])


class TestDispatchSet(_DispatchBase):
    def test_set_key_value(self):
        self._run("set STALL_THRESHOLD=10")
        self.assertTrue(bot_mod.SET_TRIGGER.exists())

    def test_set_show_value(self):
        self._run("set STALL_THRESHOLD")
        bot_mod._send.assert_called_once()

    def test_set_unknown_key(self):
        self._run("set NONEXISTENT_KEY")
        args = bot_mod._send.call_args[0]
        self.assertIn("Unknown", args[1])


class TestDispatchDepends(_DispatchBase):
    def test_depends_graph(self):
        self._run("depends")
        bot_mod._send.assert_called_once()

    def test_depends_add(self):
        self._run("depends Task0 Task1")
        self.assertTrue(bot_mod.DEPENDS_TRIGGER.exists())


class TestDispatchUndepends(_DispatchBase):
    def test_undepends_usage(self):
        self._run("undepends Task0")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_undepends_success(self):
        self._run("undepends Task0 Task1")
        self.assertTrue(bot_mod.UNDEPENDS_TRIGGER.exists())


class TestDispatchPrioritizeBranch(_DispatchBase):
    def test_prioritize_usage(self):
        self._run("prioritize_branch Task0")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])

    def test_prioritize_success(self):
        self._run("prioritize_branch Task0 BranchA")
        self.assertTrue(bot_mod.PRIORITY_BRANCH_TRIGGER.exists())


class TestDispatchPause(_DispatchBase):
    def test_pause_no_auto(self):
        self._run("pause")
        args = bot_mod._send.call_args[0]
        self.assertIn("No auto", args[1])

    def test_pause_with_auto(self):
        bot_mod._auto_running.return_value = True
        self._run("pause")
        self.assertTrue(bot_mod.PAUSE_TRIGGER.exists())


class TestDispatchResume(_DispatchBase):
    def test_resume_not_paused(self):
        self._run("resume")
        args = bot_mod._send.call_args[0]
        self.assertIn("Not paused", args[1])

    def test_resume_paused(self):
        bot_mod.PAUSE_TRIGGER.write_text("1")
        self._run("resume")
        args = bot_mod._send.call_args[0]
        self.assertIn("Resumed", args[1])


class TestDispatchConfig(_DispatchBase):
    def test_config(self):
        self._run("config")
        bot_mod._send.assert_called_once()


class TestDispatchAuto(_DispatchBase):
    def test_auto_already_running(self):
        bot_mod._auto_running.return_value = True
        self._run("auto")
        args = bot_mod._send.call_args[0]
        self.assertIn("already running", args[1])

    def test_auto_start(self):
        bot_mod._run_auto = AsyncMock()
        self._run("auto 5")
        bot_mod._send.assert_called_once()


class TestDispatchSnapshot(_DispatchBase):
    def test_snapshot_no_pdf(self):
        self._run("snapshot")
        self.assertTrue(bot_mod.SNAPSHOT_TRIGGER.exists())


class TestDispatchExport(_DispatchBase):
    def test_export_no_file(self):
        self._run("export")
        args = bot_mod._send.call_args[0]
        self.assertIn("No export", args[1])


class TestDispatchHealCmd(_DispatchBase):
    def test_heal_dispatch(self):
        self._run("heal A1")
        bot_mod._send.assert_called_once()


class TestDispatchResetTask(_DispatchBase):
    def test_reset_task_dispatch(self):
        self._run("reset_task Task0")
        bot_mod._send.assert_called_once()


class TestDispatchResetBranch(_DispatchBase):
    def test_reset_branch_dispatch(self):
        self._run("reset_branch Task0 BranchA")
        bot_mod._send.assert_called_once()


class TestDispatchBulkReset(_DispatchBase):
    def test_bulk_reset_dispatch(self):
        self._run("bulk_reset A1")
        bot_mod._send.assert_called_once()


class TestDispatchBulkVerify(_DispatchBase):
    def test_bulk_verify_dispatch(self):
        self._run("bulk_verify A1")
        bot_mod._send.assert_called_once()


class TestDispatchTaskProgress(_DispatchBase):
    def test_task_progress_dispatch(self):
        self._run("task_progress Task0")
        bot_mod._send.assert_called_once()


# ---------------------------------------------------------------------------
# Edge cases for remaining uncovered lines
# ---------------------------------------------------------------------------

class TestResetTaskWriteError(_Base):
    """Lines 90-91: write state exception in reset_task."""
    def test_reset_task_write_error(self):
        state = _state({"A1": {"status": "Running", "output": "x"}})
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            r = cmd_mod._format_reset_task(state, "Task0")
        self.assertIn("Failed", r)


class TestResetBranchWriteError(_Base):
    """Lines 122-123: write state exception in reset_branch."""
    def test_reset_branch_write_error(self):
        state = _state({"A1": {"status": "Running", "output": "x"}})
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            r = cmd_mod._format_reset_branch(state, "Task0", "BranchA")
        self.assertIn("Failed", r)


class TestResetBranchVerifiedSkip(_Base):
    """Line 114: skip verified in reset_branch."""
    def test_reset_branch_skips_verified(self):
        state = _state({"A1": {"status": "Verified", "output": "x"},
                        "A2": {"status": "Running", "output": "y"}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_reset_branch(state, "Task0", "BranchA")
        self.assertIn("Verified preserved", r)


class TestBulkResetWriteError(_Base):
    """Lines 154-155: write state exception in bulk_reset."""
    def test_bulk_reset_write_error(self):
        state = _state({"A1": {"status": "Running", "output": "x"}})
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            r = cmd_mod._format_bulk_reset(state, ["A1"])
        self.assertIn("Failed", r)


class TestBulkResetNotFound(_Base):
    """Line 197: not-found names in bulk_reset."""
    def test_bulk_reset_partial_not_found(self):
        state = _state({"A1": {"status": "Running", "output": "x"}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_bulk_reset(state, ["A1", "ZZZ"])
        self.assertIn("not found", r)
        self.assertIn("ZZZ", r)


class TestBulkVerifySkipNonRunning(_Base):
    """Lines 183-185: skip_non_running in bulk_verify."""
    def test_bulk_verify_skip_non_running(self):
        state = _state({"A1": {"status": "Pending", "output": ""}})
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_bulk_verify(state, ["A1"], skip_non_running=True)
        self.assertIn("skipped", r)


class TestBulkVerifyNotFound(_Base):
    """Line 197 equivalent for bulk_verify."""
    def test_bulk_verify_not_found(self):
        state = _state()
        self._state_path.write_text("{}", encoding="utf-8")
        r = cmd_mod._format_bulk_verify(state, ["ZZZ"])
        self.assertIn("not found", r)


class TestBulkVerifyWriteError(_Base):
    """Lines 191-192: write state exception in bulk_verify."""
    def test_bulk_verify_write_error(self):
        state = _state({"A1": {"status": "Running", "output": "x"}})
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            r = cmd_mod._format_bulk_verify(state, ["A1"])
        self.assertIn("Failed", r)


class TestDispatchStatusAutoRunning(_DispatchBase):
    """Line 260: auto running but not paused."""
    def test_status_auto_running_not_paused(self):
        bot_mod._auto_running.return_value = True
        self._run("status")
        args = bot_mod._send.call_args[0]
        self.assertIn("Auto-run in progress", args[1])


class TestDispatchStopAutoRunning(_DispatchBase):
    """Line 286: cancel auto task."""
    def test_stop_cancels_auto(self):
        bot_mod._auto_running.return_value = True
        bot_mod._auto_task = MagicMock()
        self._run("stop")
        bot_mod._auto_task.cancel.assert_called_once()


class TestDispatchExportWithFile(_DispatchBase):
    """Lines 313-314: export with existing file."""
    def test_export_with_file(self):
        bot_mod.OUTPUTS_PATH.write_text("# outputs", encoding="utf-8")
        self._run("export")
        bot_mod._send.assert_called_once()


class TestDispatchAddBranchEmptySpec(_DispatchBase):
    """Lines 340-341: add_branch with task but empty spec after strip."""
    def test_add_branch_empty_spec_whitespace(self):
        # "add_branch X \t" -> split(None,1) = ["X", "\t"] -> parts[1].strip() = ""
        self._run("add_branch X \t")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])


class TestDispatchOutputNotFound(_DispatchBase):
    """Line 357: output subtask not found."""
    def test_output_not_found(self):
        self._run("output ZZZ")
        args = bot_mod._send.call_args[0]
        self.assertIn("not found", args[1])


class TestDispatchOutputNoText(_DispatchBase):
    """Line 363: output found but empty."""
    def test_output_empty(self):
        bot_mod._load_state.return_value = _state({"A1": {"status": "Verified", "last_update": 0, "output": ""}})
        self._run("output A1")
        args = bot_mod._send.call_args[0]
        self.assertIn("no output", args[1])


class TestDispatchSnapshotWithPdf(_DispatchBase):
    """Lines 411-415: snapshot with existing PDF."""
    def test_snapshot_with_pdf(self):
        bot_mod.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        (bot_mod.SNAPSHOTS_DIR / "snap.pdf").write_text("fake", encoding="utf-8")
        self._run("snapshot")
        self.assertTrue(bot_mod.SNAPSHOT_TRIGGER.exists())


class TestDispatchDependsEmptyDag(_DispatchBase):
    """Lines 462-463: depends graph with empty dag."""
    def test_depends_empty_dag(self):
        bot_mod._load_state.return_value = {"dag": {}, "step": 0}
        self._run("depends")
        args = bot_mod._send.call_args[0]
        self.assertIn("No DAG", args[1])


class TestDispatchSetEmptyKey(_DispatchBase):
    """Lines 489-490: set with empty key."""
    def test_set_empty_key(self):
        self._run("set =value")
        args = bot_mod._send.call_args[0]
        self.assertIn("Usage", args[1])


class TestDispatchSetReadError(_DispatchBase):
    """Lines 504-505: set read settings exception."""
    def test_set_read_error(self):
        (self._sp / "settings.json").unlink()
        self._run("set STALL_THRESHOLD")
        args = bot_mod._send.call_args[0]
        self.assertIn("Could not read", args[1])


class TestDispatchPauseWithHeartbeat(_DispatchBase):
    """Lines 521-523: pause with heartbeat data."""
    def test_pause_with_heartbeat(self):
        bot_mod._auto_running.return_value = True
        bot_mod._read_heartbeat.return_value = (10, 5, 20, 8, 3, 4)
        self._run("pause")
        args = bot_mod._send.call_args[0]
        self.assertIn("Step 10", args[1])


class TestDispatchResumeWithHeartbeat(_DispatchBase):
    """Lines 535-537: resume with heartbeat data."""
    def test_resume_with_heartbeat(self):
        bot_mod.PAUSE_TRIGGER.write_text("1")
        bot_mod._read_heartbeat.return_value = (10, 5, 20, 8, 3, 4)
        self._run("resume")
        args = bot_mod._send.call_args[0]
        self.assertIn("Resumed", args[1])
        self.assertIn("Step 10", args[1])


class TestDispatchResumeUnlinkOSError(_DispatchBase):
    """Lines 530-531: resume with OSError on unlink."""
    def test_resume_unlink_oserror(self):
        bot_mod.PAUSE_TRIGGER.write_text("1")
        orig_unlink = Path.unlink
        def _fail_unlink(self_path, *a, **kw):
            if "pause" in str(self_path):
                raise OSError("locked")
            orig_unlink(self_path, *a, **kw)
        with patch.object(Path, "unlink", _fail_unlink):
            self._run("resume")
        args = bot_mod._send.call_args[0]
        self.assertIn("Resumed", args[1])


class TestDispatchConfigReadError(_DispatchBase):
    """Lines 550-551: config read exception."""
    def test_config_read_error(self):
        (self._sp / "settings.json").unlink()
        self._run("config")
        args = bot_mod._send.call_args[0]
        self.assertIn("Could not read", args[1])


class TestDispatchConfigWithData(_DispatchBase):
    """Line 547: config with settings data."""
    def test_config_with_settings(self):
        (self._sp / "settings.json").write_text(json.dumps({"STALL_THRESHOLD": 5}), encoding="utf-8")
        self._run("config")
        args = bot_mod._send.call_args[0]
        self.assertIn("STALL_THRESHOLD", args[1])


class TestDispatchHeartbeatAutoRunning(_DispatchBase):
    """Line 687: heartbeat with auto running."""
    def test_heartbeat_auto_running(self):
        bot_mod._read_heartbeat.return_value = (10, 5, 20, 8, 3, 4)
        bot_mod._auto_running.return_value = True
        self._run("heartbeat")
        args = bot_mod._send.call_args[0]
        self.assertIn("Auto-run", args[1])


if __name__ == "__main__":
    unittest.main()
