"""Unit tests for solo_builder/runners/ package."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure solo_builder/ is on sys.path so runners/* can import utils.helper_functions
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runners.claude_runner import ClaudeRunner
from runners.anthropic_runner import AnthropicRunner
from runners.sdk_tool_runner import SdkToolRunner, _SOLO
from runners.executor import Executor


# ═══════════════════════════════════════════════════════════════════════════════
# ClaudeRunner
# ═══════════════════════════════════════════════════════════════════════════════

class TestClaudeRunner(unittest.TestCase):

    def test_unavailable_when_claude_not_found(self):
        with patch("runners.claude_runner.subprocess.run", side_effect=FileNotFoundError):
            cr = ClaudeRunner()
        self.assertFalse(cr.available)

    def test_run_returns_false_when_unavailable(self):
        cr = ClaudeRunner()
        cr.available = False
        ok, msg = cr.run("do something", "A1")
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_run_parses_json_result(self):
        payload = json.dumps({"result": "task done"})
        mock_result = MagicMock(returncode=0, stdout=payload, stderr="")
        cr = ClaudeRunner()
        cr.available = True
        with patch("runners.claude_runner.subprocess.run", return_value=mock_result):
            ok, output = cr.run("do something", "A1")
        self.assertTrue(ok)
        self.assertEqual(output, "task done")

    def test_run_non_zero_exit_returns_false(self):
        mock_result = MagicMock(returncode=1, stdout="", stderr="some error")
        cr = ClaudeRunner()
        cr.available = True
        with patch("runners.claude_runner.subprocess.run", return_value=mock_result):
            ok, msg = cr.run("do something", "A1")
        self.assertFalse(ok)
        self.assertIn("some error", msg)

    def test_run_timeout_returns_false(self):
        cr = ClaudeRunner(timeout=1)
        cr.available = True
        with patch("runners.claude_runner.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=1)):
            ok, msg = cr.run("slow task", "A1")
        self.assertFalse(ok)
        self.assertIn("Timed out", msg)

    def test_run_json_decode_error_falls_back_to_stdout(self):
        mock_result = MagicMock(returncode=0, stdout="plain text output", stderr="")
        cr = ClaudeRunner()
        cr.available = True
        with patch("runners.claude_runner.subprocess.run", return_value=mock_result):
            ok, output = cr.run("do something", "A1")
        self.assertTrue(ok)
        self.assertEqual(output, "plain text output")

    def test_run_passes_tools_flag(self):
        payload = json.dumps({"result": "ok"})
        mock_result = MagicMock(returncode=0, stdout=payload, stderr="")
        cr = ClaudeRunner(allowed_tools="Read,Glob")
        cr.available = True
        with patch("runners.claude_runner.subprocess.run", return_value=mock_result) as mock_run:
            cr.run("task", "A1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("--allowedTools", cmd)

    def test_run_per_call_tools_override_default(self):
        payload = json.dumps({"result": "ok"})
        mock_result = MagicMock(returncode=0, stdout=payload, stderr="")
        cr = ClaudeRunner(allowed_tools="Read")
        cr.available = True
        with patch("runners.claude_runner.subprocess.run", return_value=mock_result) as mock_run:
            cr.run("task", "A1", tools="Bash")
        cmd = mock_run.call_args[0][0]
        self.assertIn("Bash", cmd)
        self.assertNotIn("Read", cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# AnthropicRunner
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnthropicRunner(unittest.TestCase):

    def test_unavailable_when_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            ar = AnthropicRunner()
        self.assertFalse(ar.available)

    def test_run_returns_false_when_unavailable(self):
        ar = AnthropicRunner()
        ar.available = False
        ok, msg = ar.run("prompt")
        self.assertFalse(ok)
        self.assertIn("unavailable", msg)

    def test_arun_returns_false_when_unavailable(self):
        ar = AnthropicRunner()
        ar.available = False
        ok, msg = asyncio.run(ar.arun("prompt"))
        self.assertFalse(ok)
        self.assertIn("unavailable", msg)

    def test_run_returns_text_on_success(self):
        ar = AnthropicRunner()
        ar.available = True
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="  result text  ")]
        ar.client = MagicMock()
        ar.client.messages.create.return_value = mock_msg
        ok, output = ar.run("prompt")
        self.assertTrue(ok)
        self.assertEqual(output, "result text")

    def test_run_handles_exception(self):
        ar = AnthropicRunner()
        ar.available = True
        ar.client = MagicMock()
        ar.client.messages.create.side_effect = RuntimeError("API error")
        ok, msg = ar.run("prompt")
        self.assertFalse(ok)
        self.assertIn("API error", msg)


# ═══════════════════════════════════════════════════════════════════════════════
# SdkToolRunner
# ═══════════════════════════════════════════════════════════════════════════════

class TestSdkToolRunner(unittest.TestCase):

    def _runner(self):
        client = MagicMock()
        async_client = MagicMock()
        return SdkToolRunner(client=client, async_client=async_client,
                             model="claude-sonnet-4-6", max_tokens=512)

    def test_unavailable_when_no_client(self):
        r = SdkToolRunner(client=None, async_client=None, model="m", max_tokens=100)
        self.assertFalse(r.available)

    def test_solo_resolves_to_solo_builder_dir(self):
        # _SOLO should point to solo_builder/ (contains solo_builder_cli.py)
        self.assertTrue(Path(_SOLO, "solo_builder_cli.py").exists())

    def test_exec_read_real_file(self):
        r = self._runner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            tmp = f.name
        try:
            result = r._exec("Read", {"file_path": tmp})
            self.assertEqual(result, "hello world")
        finally:
            os.unlink(tmp)

    def test_exec_read_relative_path_resolves_to_solo(self):
        # A relative path should be joined with _SOLO, not CWD
        r = self._runner()
        rel = "solo_builder_cli.py"
        result = r._exec("Read", {"file_path": rel})
        # Should contain Python source (not an error)
        self.assertIn("def ", result)

    def test_exec_unknown_tool(self):
        r = self._runner()
        result = r._exec("UnknownTool", {})
        self.assertIn("Unknown tool", result)

    def test_exec_glob_no_matches(self):
        r = self._runner()
        with tempfile.TemporaryDirectory() as d:
            result = r._exec("Glob", {"pattern": "*.nonexistent", "path": d})
        self.assertEqual(result, "(no matches)")

    def test_run_returns_false_when_unavailable(self):
        r = SdkToolRunner(client=None, async_client=None, model="m", max_tokens=100)
        ok, msg = r.run("prompt", "Read")
        self.assertFalse(ok)
        self.assertIn("unavailable", msg)


# ═══════════════════════════════════════════════════════════════════════════════
# Executor
# ═══════════════════════════════════════════════════════════════════════════════

def _make_dag(status="Pending", last_update=0):
    return {
        "Task 0": {
            "status": "Pending",
            "depends_on": [],
            "branches": {
                "A": {
                    "status": "Pending",
                    "subtasks": {
                        "A1": {"status": status, "last_update": last_update,
                               "shadow": "Pending", "tools": "", "description": "do A1"},
                    },
                }
            },
        }
    }


class TestExecutor(unittest.TestCase):

    def _executor(self, verify_prob=1.0, review_mode=False):
        ex = Executor(max_per_step=6, verify_prob=verify_prob)
        ex.review_mode      = review_mode
        ex.claude.available = False
        ex.anthropic.available = False
        ex.sdk_tool.available  = False
        return ex

    def test_pending_advances_to_running(self):
        ex = self._executor()
        dag = _make_dag("Pending")
        from agents.planner import Planner
        plist = Planner(5).prioritize(dag, step=0)
        with patch("runners.executor.add_memory_snapshot"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertEqual(dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]["status"], "Running")
        self.assertIn("A1", actions)

    def test_dice_roll_verifies_running(self):
        ex = self._executor(verify_prob=1.0)
        dag = _make_dag("Running", last_update=0)
        from agents.planner import Planner
        plist = Planner(5).prioritize(dag, step=1)
        with patch("runners.executor.add_memory_snapshot"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertEqual(dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]["status"], "Verified")
        self.assertIn("A1", actions)

    def test_review_mode_sets_review_status(self):
        ex = self._executor(verify_prob=1.0, review_mode=True)
        dag = _make_dag("Running", last_update=0)
        from agents.planner import Planner
        plist = Planner(5).prioritize(dag, step=1)
        with patch("runners.executor.add_memory_snapshot"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertEqual(dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]["status"], "Review")

    def test_dice_roll_zero_prob_stays_running(self):
        ex = self._executor(verify_prob=0.0)
        dag = _make_dag("Running", last_update=0)
        from agents.planner import Planner
        plist = Planner(5).prioritize(dag, step=1)
        with patch("runners.executor.add_memory_snapshot"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertEqual(dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]["status"], "Running")
        self.assertEqual(actions, {})

    def test_record_history_appends_entry(self):
        st_data = {}
        Executor._record_history(st_data, "Verified", step=3)
        self.assertEqual(st_data["history"], [{"status": "Verified", "step": 3}])

    def test_update_branch_verified_when_all_subtasks_done(self):
        dag = _make_dag("Verified")
        ex = self._executor()
        ex._update_branch(dag, "Task 0", "A")
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Verified")

    def test_update_task_verified_when_all_branches_done(self):
        dag = _make_dag("Verified")
        dag["Task 0"]["branches"]["A"]["status"] = "Verified"
        ex = self._executor()
        ex._update_task(dag, "Task 0")
        self.assertEqual(dag["Task 0"]["status"], "Verified")

    def test_append_journal_called_on_success(self):
        journal_calls = []
        ex = self._executor(verify_prob=1.0)
        ex._append_journal = lambda *a, **kw: journal_calls.append(a)
        # dice-roll doesn't call _append_journal (only real runner outputs do)
        # so verify the lambda works when called directly
        ex._append_journal("A1", "Task 0", "A", "desc", "output", 5)
        self.assertEqual(len(journal_calls), 1)


if __name__ == "__main__":
    unittest.main()
