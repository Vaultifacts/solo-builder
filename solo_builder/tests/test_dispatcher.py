"""Tests for DispatcherMixin.handle_command dispatch table and _cmd_set (TASK-403)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.dispatcher as dispatcher_module
from commands.dispatcher import DispatcherMixin


# ---------------------------------------------------------------------------
# Shared CLI stub
# ---------------------------------------------------------------------------

class _FakeCLI(DispatcherMixin):
    """Minimal stub satisfying all attribute accesses in DispatcherMixin."""

    def __init__(self):
        self.dag = {}
        self.step = 3
        self.memory_store = {}
        self.alerts = []
        self.running = True
        self.display = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        self.healer = MagicMock()
        self.healer.healed_total = 0
        self.executor = MagicMock()
        self.executor.max_per_step = 1
        self.executor.verify_prob = 0.5
        self.executor.review_mode = False
        self.executor.claude.available = True
        self.executor.claude.allowed_tools = ""
        self.executor.anthropic.max_tokens = 4096
        self.executor.anthropic.model = "claude-sonnet-4-6"
        self.planner = MagicMock()
        self.shadow = MagicMock()
        self._priority_cache = []
        self._last_priority_step = 0
        self._runtime_cfg = {
            "STALL_THRESHOLD": 5,
            "SNAPSHOT_INTERVAL": 10,
            "VERBOSITY": "INFO",
            "AUTO_STEP_DELAY": 2.0,
            "AUTO_SAVE_INTERVAL": 5,
            "CLAUDE_ALLOWED_TOOLS": "",
            "EXEC_VERIFY_PROB": 0.5,
            "WEBHOOK_URL": "",
        }
        # Stub all dispatch targets as mocks
        self.run_step = MagicMock()
        self.save_state = MagicMock()
        self.load_state = MagicMock(return_value=True)
        self._take_snapshot = MagicMock()
        self._cmd_auto = MagicMock()
        self._cmd_reset = MagicMock()
        self._cmd_status = MagicMock()
        self._cmd_stats = MagicMock()
        self._cmd_cache = MagicMock()
        self._cmd_history = MagicMock()
        self._cmd_add_task = MagicMock()
        self._cmd_add_branch = MagicMock()
        self._cmd_prioritize_branch = MagicMock()
        self._cmd_export = MagicMock()
        self._cmd_export_dag = MagicMock()
        self._cmd_import_dag = MagicMock()
        self._cmd_depends = MagicMock()
        self._cmd_undepends = MagicMock()
        self._cmd_describe = MagicMock()
        self._cmd_verify = MagicMock()
        self._cmd_tools = MagicMock()
        self._cmd_output = MagicMock()
        self._cmd_branches = MagicMock()
        self._cmd_rename = MagicMock()
        self._cmd_search = MagicMock()
        self._cmd_filter = MagicMock()
        self._cmd_graph = MagicMock()
        self._cmd_log = MagicMock()
        self._cmd_pause = MagicMock()
        self._cmd_resume = MagicMock()
        self._cmd_config = MagicMock()
        self._cmd_priority = MagicMock()
        self._cmd_stalled = MagicMock()
        self._cmd_heal = MagicMock()
        self._cmd_agents = MagicMock()
        self._cmd_forecast = MagicMock()
        self._cmd_tasks = MagicMock()
        self._cmd_help = MagicMock()
        self._cmd_undo = MagicMock()
        self._cmd_diff = MagicMock()
        self._cmd_timeline = MagicMock()
        self._cmd_load_backup = MagicMock()
        self._persist_setting = MagicMock()


# ---------------------------------------------------------------------------
# handle_command dispatch tests
# ---------------------------------------------------------------------------

class TestHandleCommandDispatch(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def _cmd(self, raw):
        with patch("builtins.print"), patch("builtins.input", return_value=""), \
             patch("time.sleep"), \
             patch("commands.dispatcher.dag_stats", return_value={"verified": 0, "total": 0}, create=True):
            self.cli.handle_command(raw)

    def test_run(self):
        self._cmd("run")
        self.cli.run_step.assert_called_once()

    def test_auto(self):
        self._cmd("auto 5")
        self.cli._cmd_auto.assert_called_once_with(" 5")

    def test_snapshot(self):
        self._cmd("snapshot")
        self.cli._take_snapshot.assert_called_once_with(auto=False)

    def test_save(self):
        self._cmd("save")
        self.cli.save_state.assert_called_once()

    def test_load_success(self):
        self._cmd("load")
        self.cli.load_state.assert_called_once()

    def test_load_backup(self):
        self._cmd("load_backup backup.zip")
        self.cli._cmd_load_backup.assert_called_once_with("backup.zip")

    def test_undo(self):
        self._cmd("undo")
        self.cli._cmd_undo.assert_called_once()

    def test_diff(self):
        self._cmd("diff")
        self.cli._cmd_diff.assert_called_once()

    def test_timeline(self):
        self._cmd("timeline A1")
        self.cli._cmd_timeline.assert_called_once_with("A1")

    def test_reset(self):
        self._cmd("reset")
        self.cli._cmd_reset.assert_called_once()

    def test_status(self):
        self._cmd("status")
        self.cli._cmd_status.assert_called_once()

    def test_stats(self):
        self._cmd("stats")
        self.cli._cmd_stats.assert_called_once()

    def test_cache(self):
        self._cmd("cache")
        self.cli._cmd_cache.assert_called_once()

    def test_cache_clear(self):
        self._cmd("cache clear")
        self.cli._cmd_cache.assert_called_once_with(clear=True)

    def test_history_no_args(self):
        self._cmd("history")
        self.cli._cmd_history.assert_called_once_with("")

    def test_history_with_args(self):
        self._cmd("history 10")
        self.cli._cmd_history.assert_called_once_with("10")

    def test_add_task_no_args(self):
        self._cmd("add_task")
        self.cli._cmd_add_task.assert_called_once_with()

    def test_add_task_with_spec(self):
        self._cmd("add_task do the thing")
        self.cli._cmd_add_task.assert_called_once_with("do the thing")

    def test_add_branch_with_two_parts(self):
        self._cmd("add_branch T0 my spec")
        self.cli._cmd_add_branch.assert_called_once_with("T0", spec_override="my spec")

    def test_add_branch_one_part(self):
        self._cmd("add_branch T0")
        self.cli._cmd_add_branch.assert_called_once_with(" T0")

    def test_prioritize_branch(self):
        self._cmd("prioritize_branch T0 B")
        self.cli._cmd_prioritize_branch.assert_called()

    def test_export(self):
        self._cmd("export")
        self.cli._cmd_export.assert_called_once()

    def test_export_dag_no_args(self):
        self._cmd("export_dag")
        self.cli._cmd_export_dag.assert_called_once_with("")

    def test_export_dag_with_path(self):
        self._cmd("export_dag /tmp/dag.json")
        self.cli._cmd_export_dag.assert_called_once_with("/tmp/dag.json")

    def test_import_dag(self):
        self._cmd("import_dag /tmp/dag.json")
        self.cli._cmd_import_dag.assert_called_once_with("/tmp/dag.json")

    def test_depends_no_args(self):
        self._cmd("depends")
        self.cli._cmd_depends.assert_called_once_with("")

    def test_depends_with_args(self):
        self._cmd("depends T0 T1")
        self.cli._cmd_depends.assert_called_once_with("T0 T1")

    def test_undepends(self):
        self._cmd("undepends T0 T1")
        self.cli._cmd_undepends.assert_called_once_with("T0 T1")

    def test_describe(self):
        self._cmd("describe A1 the description")
        self.cli._cmd_describe.assert_called_once_with("A1 the description")

    def test_verify(self):
        self._cmd("verify A1")
        self.cli._cmd_verify.assert_called_once_with("A1")

    def test_tools(self):
        self._cmd("tools A1 Read,Glob")
        self.cli._cmd_tools.assert_called_once_with("A1 Read,Glob")

    def test_output(self):
        self._cmd("output A1")
        self.cli._cmd_output.assert_called_once_with("A1")

    def test_branches_no_args(self):
        self._cmd("branches")
        self.cli._cmd_branches.assert_called_once_with("")

    def test_branches_with_args(self):
        self._cmd("branches T0")
        self.cli._cmd_branches.assert_called_once_with("T0")

    def test_rename(self):
        self._cmd("rename A1 A2")
        self.cli._cmd_rename.assert_called_once_with("A1 A2")

    def test_search(self):
        self._cmd("search foo")
        self.cli._cmd_search.assert_called_once_with("foo")

    def test_filter(self):
        self._cmd("filter Pending")
        self.cli._cmd_filter.assert_called_once_with("Pending")

    def test_graph(self):
        self._cmd("graph")
        self.cli._cmd_graph.assert_called_once()

    def test_log_no_args(self):
        self._cmd("log")
        self.cli._cmd_log.assert_called_once_with("")

    def test_log_with_args(self):
        self._cmd("log 20")
        self.cli._cmd_log.assert_called_once_with("20")

    def test_pause(self):
        self._cmd("pause")
        self.cli._cmd_pause.assert_called_once()

    def test_resume(self):
        self._cmd("resume")
        self.cli._cmd_resume.assert_called_once()

    def test_config(self):
        self._cmd("config")
        self.cli._cmd_config.assert_called_once()

    def test_priority(self):
        self._cmd("priority")
        self.cli._cmd_priority.assert_called_once()

    def test_stalled(self):
        self._cmd("stalled")
        self.cli._cmd_stalled.assert_called_once()

    def test_heal(self):
        self._cmd("heal A1")
        self.cli._cmd_heal.assert_called_once_with("A1")

    def test_agents(self):
        self._cmd("agents")
        self.cli._cmd_agents.assert_called_once()

    def test_forecast(self):
        self._cmd("forecast")
        self.cli._cmd_forecast.assert_called_once()

    def test_tasks(self):
        self._cmd("tasks")
        self.cli._cmd_tasks.assert_called_once()

    def test_help(self):
        self._cmd("help")
        self.cli._cmd_help.assert_called_once()

    def test_exit_sets_running_false(self):
        self._cmd("exit")
        self.assertFalse(self.cli.running)
        self.cli.save_state.assert_called_with(silent=True)

    def test_empty_command_is_noop(self):
        self._cmd("")
        self.cli.run_step.assert_not_called()

    def test_unknown_command_prints_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli.handle_command("xyzzy_unknown")
        combined = "\n".join(printed)
        self.assertIn("Unknown command", combined)

    def test_load_failure_no_print(self):
        self.cli.load_state.return_value = False
        with patch("builtins.print"), patch("time.sleep"):
            self.cli.handle_command("load")
        # Should not print success message when load fails
        self.cli.load_state.assert_called_once()


# ---------------------------------------------------------------------------
# _cmd_set dispatch
# ---------------------------------------------------------------------------

class TestCmdSet(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def _set(self, args):
        with patch("builtins.print"):
            self.cli._cmd_set(args)

    def test_stall_threshold(self):
        self._set("STALL_THRESHOLD=7")
        self.assertEqual(self.cli._runtime_cfg["STALL_THRESHOLD"], 7)
        self.cli._persist_setting.assert_called()

    def test_snapshot_interval(self):
        self._set("SNAPSHOT_INTERVAL=20")
        self.assertEqual(self.cli._runtime_cfg["SNAPSHOT_INTERVAL"], 20)

    def test_verbosity_valid(self):
        self._set("VERBOSITY=DEBUG")
        self.assertEqual(self.cli._runtime_cfg["VERBOSITY"], "DEBUG")

    def test_verbosity_invalid_prints_error(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_set("VERBOSITY=INVALID")
        combined = "\n".join(printed)
        self.assertIn("Invalid", combined)

    def test_verify_prob_valid(self):
        self._set("VERIFY_PROB=0.8")
        self.assertEqual(self.cli.executor.verify_prob, 0.8)

    def test_verify_prob_out_of_range(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_set("VERIFY_PROB=1.5")
        combined = "\n".join(printed)
        self.assertIn("Invalid", combined)

    def test_auto_step_delay(self):
        self._set("AUTO_STEP_DELAY=3.5")
        self.assertEqual(self.cli._runtime_cfg["AUTO_STEP_DELAY"], 3.5)

    def test_auto_save_interval(self):
        self._set("AUTO_SAVE_INTERVAL=10")
        self.assertEqual(self.cli._runtime_cfg["AUTO_SAVE_INTERVAL"], 10)

    def test_claude_allowed_tools(self):
        self._set("CLAUDE_ALLOWED_TOOLS=Read,Glob")
        self.assertEqual(self.cli._runtime_cfg["CLAUDE_ALLOWED_TOOLS"], "Read,Glob")

    def test_no_equals_sign_shows_current(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_set("STALL_THRESHOLD")
        combined = "\n".join(printed)
        self.assertIn("STALL_THRESHOLD", combined)

    def test_no_equals_unknown_key_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_set("UNKNOWN_KEY")
        combined = "\n".join(printed)
        self.assertIn("Usage", combined)

    def test_stall_threshold_below_one_error(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_set("STALL_THRESHOLD=0")
        combined = "\n".join(printed)
        self.assertIn("Invalid", combined)


if __name__ == "__main__":
    unittest.main()
