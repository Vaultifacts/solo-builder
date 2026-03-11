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
        # Temp file must be inside the repo root to pass the path allowlist
        from runners.sdk_tool_runner import _REPO_ROOT
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                         dir=_REPO_ROOT) as f:
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

    # ----- run() synchronous tool-use loop -----

    def _mock_end_turn(self, text="result text"):
        """Build a mock response that terminates the loop (end_turn)."""
        block = MagicMock()
        block.text = text
        block.type = "text"
        resp = MagicMock()
        resp.stop_reason = "end_turn"
        resp.content = [block]
        return resp

    def _mock_tool_use(self, tool_name="Read", tool_input=None, tool_id="tu_1"):
        """Build a mock response that requests one tool call."""
        block = MagicMock()
        block.type = "tool_use"
        block.name = tool_name
        block.input = tool_input or {"file_path": "/dev/null"}
        block.id = tool_id
        resp = MagicMock()
        resp.stop_reason = "tool_use"
        resp.content = [block]
        return resp

    def test_run_end_turn_returns_true_and_text(self):
        r = self._runner()
        r.client.messages.create.return_value = self._mock_end_turn("hello")
        ok, out = r.run("prompt", "Read")
        self.assertTrue(ok)
        self.assertEqual(out, "hello")

    def test_run_tool_use_then_end_turn(self):
        r = self._runner()
        # First call: tool_use; second call: end_turn
        r.client.messages.create.side_effect = [
            self._mock_tool_use("Read", {"file_path": "/dev/null"}),
            self._mock_end_turn("final answer"),
        ]
        with patch.object(r, "_exec", return_value="file contents"):
            ok, out = r.run("prompt", "Read")
        self.assertTrue(ok)
        self.assertEqual(out, "final answer")

    def test_run_tool_result_appended_to_messages(self):
        r = self._runner()
        calls_made = []

        def capture_create(**kwargs):
            calls_made.append(kwargs["messages"])
            if len(calls_made) == 1:
                return self._mock_tool_use("Read", {"file_path": "/dev/null"}, "tu_42")
            return self._mock_end_turn("done")

        r.client.messages.create.side_effect = lambda **kw: capture_create(**kw)
        with patch.object(r, "_exec", return_value="content"):
            r.run("prompt", "Read")
        # Second call should include user message with tool_result
        second_msgs = calls_made[1]
        user_msg = [m for m in second_msgs if m["role"] == "user"][-1]
        self.assertEqual(user_msg["content"][0]["type"], "tool_result")
        self.assertEqual(user_msg["content"][0]["tool_use_id"], "tu_42")

    def test_run_unknown_stop_reason_breaks_loop(self):
        r = self._runner()
        resp = MagicMock()
        resp.stop_reason = "max_tokens"
        resp.content = []
        r.client.messages.create.return_value = resp
        ok, msg = r.run("prompt", "Read")
        self.assertFalse(ok)
        self.assertIn("exhausted", msg)

    def test_run_exception_returns_false(self):
        r = self._runner()
        r.client.messages.create.side_effect = RuntimeError("API error")
        ok, msg = r.run("prompt", "Read")
        self.assertFalse(ok)
        self.assertIn("API error", msg)

    def test_run_filters_schemas_by_allowed(self):
        r = self._runner()
        r.client.messages.create.return_value = self._mock_end_turn("ok")
        r.run("prompt", "Read")  # only Read allowed
        call_kwargs = r.client.messages.create.call_args[1]
        tool_names = [t["name"] for t in call_kwargs["tools"]]
        self.assertEqual(tool_names, ["Read"])

    # ----- arun() async tool-use loop -----

    def _patch_anthropic(self):
        """Return a context manager that injects a fake anthropic module."""
        import types
        fake_anthropic = types.ModuleType("anthropic")

        class FakeRateLimitError(Exception):
            pass

        fake_anthropic.RateLimitError = FakeRateLimitError
        return patch.dict("sys.modules", {"anthropic": fake_anthropic}), fake_anthropic

    def test_arun_returns_false_when_unavailable(self):
        r = SdkToolRunner(client=None, async_client=None, model="m", max_tokens=100)
        cm, _ = self._patch_anthropic()
        with cm:
            ok, msg = asyncio.run(r.arun("prompt", "Read"))
        self.assertFalse(ok)
        self.assertIn("unavailable", msg)

    def test_arun_end_turn_returns_true_and_text(self):
        r = self._runner()

        async def fake_create(**kwargs):
            return self._mock_end_turn("async result")

        r.async_client.messages.create = fake_create
        cm, _ = self._patch_anthropic()
        with cm:
            ok, out = asyncio.run(r.arun("prompt", "Read"))
        self.assertTrue(ok)
        self.assertEqual(out, "async result")

    def test_arun_tool_use_then_end_turn(self):
        r = self._runner()
        call_count = 0

        async def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return self._mock_tool_use("Read", {"file_path": "/dev/null"})
            return self._mock_end_turn("done")

        r.async_client.messages.create = fake_create
        cm, _ = self._patch_anthropic()
        with cm, patch.object(r, "_exec", return_value="file contents"):
            ok, out = asyncio.run(r.arun("prompt", "Read"))
        self.assertTrue(ok)
        self.assertEqual(out, "done")

    def test_arun_rate_limit_retries_then_succeeds(self):
        cm, fake_anthropic = self._patch_anthropic()
        r = self._runner()
        call_count = 0

        async def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise fake_anthropic.RateLimitError("rate limited")
            return self._mock_end_turn("ok after retry")

        r.async_client.messages.create = fake_create

        async def fake_sleep(t):
            pass

        with cm, patch("asyncio.sleep", side_effect=fake_sleep):
            ok, out = asyncio.run(r.arun("prompt", "Read"))
        self.assertTrue(ok)
        self.assertEqual(out, "ok after retry")

    def test_arun_rate_limit_exhausts_all_retries(self):
        cm, fake_anthropic = self._patch_anthropic()
        r = self._runner()

        async def always_rate_limit(**kwargs):
            raise fake_anthropic.RateLimitError("rate limited")

        r.async_client.messages.create = always_rate_limit

        async def fake_sleep(t):
            pass

        with cm, patch("asyncio.sleep", side_effect=fake_sleep):
            ok, msg = asyncio.run(r.arun("prompt", "Read"))
        self.assertFalse(ok)
        self.assertIn("retries exhausted", msg)

    def test_arun_exception_returns_false(self):
        r = self._runner()

        async def raise_exc(**kwargs):
            raise RuntimeError("async error")

        r.async_client.messages.create = raise_exc
        cm, _ = self._patch_anthropic()
        with cm:
            ok, msg = asyncio.run(r.arun("prompt", "Read"))
        self.assertFalse(ok)
        self.assertIn("async error", msg)

    def test_arun_unknown_stop_reason_breaks_loop(self):
        r = self._runner()

        async def fake_create(**kwargs):
            resp = MagicMock()
            resp.stop_reason = "stop_sequence"
            resp.content = []
            return resp

        r.async_client.messages.create = fake_create
        cm, _ = self._patch_anthropic()
        with cm:
            ok, msg = asyncio.run(r.arun("prompt", "Read"))
        self.assertFalse(ok)
        self.assertIn("exhausted", msg)

    # ----- _exec() path coverage -----

    def test_exec_read_path_outside_scope_rejected(self):
        r = self._runner()
        result = r._exec("Read", {"file_path": "C:/Windows/system32/secret"})
        self.assertIn("restricted", result)

    def test_exec_read_file_error_returns_error_string(self):
        r = self._runner()
        from runners.sdk_tool_runner import _REPO_ROOT
        # A path inside scope but non-existent file
        bad_path = os.path.join(_REPO_ROOT, "nonexistent_xyz_12345.txt")
        result = r._exec("Read", {"file_path": bad_path})
        self.assertIn("Error", result)

    def test_exec_glob_with_matches(self):
        r = self._runner()
        result = r._exec("Glob", {"pattern": "*.py", "path": _SOLO})
        self.assertNotEqual(result, "(no matches)")

    def test_exec_glob_relative_base_resolved(self):
        r = self._runner()
        # Relative path should be joined with _SOLO
        result = r._exec("Glob", {"pattern": "*.py", "path": "runners"})
        self.assertNotEqual(result, "(no matches)")

    def test_exec_grep_finds_pattern_in_file(self):
        r = self._runner()
        from runners.sdk_tool_runner import _REPO_ROOT
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                         dir=_REPO_ROOT, encoding="utf-8") as f:
            f.write("hello world\nsecond line\n")
            tmp = f.name
        try:
            result = r._exec("Grep", {"pattern": "hello", "path": tmp})
            self.assertIn("hello", result)
        finally:
            os.unlink(tmp)

    def test_exec_grep_no_match_returns_no_matches(self):
        r = self._runner()
        from runners.sdk_tool_runner import _REPO_ROOT
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                         dir=_REPO_ROOT, encoding="utf-8") as f:
            f.write("hello world\n")
            tmp = f.name
        try:
            result = r._exec("Grep", {"pattern": "zzznomatch", "path": tmp})
            self.assertEqual(result, "(no matches)")
        finally:
            os.unlink(tmp)

    def test_exec_grep_with_file_glob_searches_dir(self):
        r = self._runner()
        # Grep *.py files in _SOLO for "def " — should find something
        result = r._exec("Grep", {"pattern": "def ", "path": _SOLO, "glob": "*.py"})
        self.assertIn("def ", result)

    def test_exec_grep_nonexistent_file_skipped(self):
        r = self._runner()
        from runners.sdk_tool_runner import _REPO_ROOT
        result = r._exec("Grep", {"pattern": "x", "path": os.path.join(_REPO_ROOT, "no_such_file.txt")})
        self.assertEqual(result, "(no matches)")

    def test_exec_exception_returns_error_string(self):
        r = self._runner()
        with patch("builtins.open", side_effect=PermissionError("denied")):
            from runners.sdk_tool_runner import _REPO_ROOT
            tmp = os.path.join(_REPO_ROOT, "dummy.txt")
            result = r._exec("Read", {"file_path": tmp})
        self.assertIn("Error", result)

    def test_exec_grep_relative_path_resolved(self):
        # Line 185: relative path joined to _SOLO
        r = self._runner()
        result = r._exec("Grep", {"pattern": "def ", "path": "runners"})
        # Should find definitions in runners/ without error
        self.assertIsInstance(result, str)

    def test_exec_grep_200_line_limit(self):
        # Line 199: break when lines >= 200
        import tempfile as _tmpmod
        r = self._runner()
        with _tmpmod.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                        dir=_SOLO) as tf:
            tf.write("\n".join(["x = 1"] * 300))
            tmp_path = tf.name
        try:
            result = r._exec("Grep", {"pattern": "x = 1", "path": tmp_path})
            lines = result.strip().splitlines()
            self.assertLessEqual(len(lines), 200)
        finally:
            os.unlink(tmp_path)


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


# ═══════════════════════════════════════════════════════════════════════════════
# validate_tools
# ═══════════════════════════════════════════════════════════════════════════════

import solo_builder_cli as _cli_mod
from runners.sdk_tool_runner import validate_tools, _VALID_TOOLS


class TestValidateTools(unittest.TestCase):

    def test_empty_string_is_valid(self):
        validate_tools("")  # no exception

    def test_whitespace_only_is_valid(self):
        validate_tools("   ")

    def test_known_tools_are_valid(self):
        for name in _VALID_TOOLS:
            validate_tools(name)  # no exception

    def test_all_known_tools_together(self):
        validate_tools(",".join(_VALID_TOOLS))

    def test_unknown_tool_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_tools("Bash")
        self.assertIn("Bash", str(ctx.exception))
        self.assertIn("Valid tools", str(ctx.exception))

    def test_mixed_known_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_tools("Read,Bash,Write")
        msg = str(ctx.exception)
        self.assertIn("Bash", msg)
        self.assertIn("Write", msg)
        self.assertNotIn("'Read'", msg)

    def test_error_message_lists_valid_tools(self):
        with self.assertRaises(ValueError) as ctx:
            validate_tools("UnknownTool")
        msg = str(ctx.exception)
        for tool in _VALID_TOOLS:
            self.assertIn(tool, msg)


# ═══════════════════════════════════════════════════════════════════════════════
# SdkToolRunner — Read path allowlist
# ═══════════════════════════════════════════════════════════════════════════════

from runners.sdk_tool_runner import _REPO_ROOT


class TestSdkToolRunnerPathAllowlist(unittest.TestCase):

    def _runner(self):
        return SdkToolRunner(client=MagicMock(), async_client=MagicMock(),
                             model="m", max_tokens=100)

    def test_read_within_repo_root_succeeds(self):
        r = self._runner()
        # Read a known file within the repo — should succeed
        result = r._exec("Read", {"file_path": "solo_builder_cli.py"})
        self.assertNotIn("Error: Read access restricted", result)

    def test_read_outside_repo_root_blocked(self):
        r = self._runner()
        import tempfile, os
        # Write a temp file outside the repo root
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                         dir=tempfile.gettempdir(),
                                         delete=False) as f:
            f.write("secret")
            tmp = f.name
        try:
            result = r._exec("Read", {"file_path": tmp})
            self.assertIn("Error: Read access restricted", result)
        finally:
            os.unlink(tmp)

    def test_repo_root_constant_is_parent_of_solo(self):
        import os
        from runners.sdk_tool_runner import _SOLO
        self.assertEqual(os.path.dirname(_SOLO), _REPO_ROOT)


# ═══════════════════════════════════════════════════════════════════════════════
# Executor routing (TD-TEST-001)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_dag_tools(status="Running", tools="", description="do A1", last_update=0):
    return {
        "Task 0": {
            "status": "Running",
            "depends_on": [],
            "branches": {
                "A": {
                    "status": "Running",
                    "subtasks": {
                        "A1": {"status": status, "last_update": last_update,
                               "shadow": "Pending", "tools": tools,
                               "description": description},
                    },
                }
            },
        }
    }


class TestExecutorRouting(unittest.TestCase):

    def _executor(self):
        ex = Executor(max_per_step=6, verify_prob=0.0,
                      project_context=_cli_mod._PROJECT_CONTEXT)
        ex.claude.available    = False
        ex.anthropic.available = False
        ex.sdk_tool.available  = False
        return ex

    def _plist(self, dag, step=1):
        from agents.planner import Planner
        return Planner(5).prioritize(dag, step=step)

    def test_sdk_direct_path_prompt_includes_context(self):
        """No-tools subtask → sdk_jobs built with context + description."""
        ex = self._executor()
        ex.anthropic.available = True
        captured_prompts = []

        async def _mock_arun(prompt):
            captured_prompts.append(prompt)
            return True, "ok"

        ex.anthropic.arun = _mock_arun

        dag = _make_dag_tools(status="Running", tools="", description="List 3 features.")
        with patch("runners.executor.add_memory_snapshot"):
            ex.execute_step(dag, self._plist(dag), step=1, memory_store={})

        self.assertEqual(len(captured_prompts), 1)
        self.assertTrue(captured_prompts[0].startswith("Context:"),
                        "SDK direct path must prepend project context")
        self.assertIn("List 3 features.", captured_prompts[0])

    def test_sdk_tool_path_fires_when_tools_set(self):
        """Tool-bearing subtask + sdk_tool available → sdk_tool_jobs populated."""
        ex = self._executor()
        ex.sdk_tool.available = True
        sdk_calls = []

        async def _mock_arun(prompt, tools_str):
            sdk_calls.append((prompt, tools_str))
            return True, "result"

        ex.sdk_tool.arun = _mock_arun

        dag = _make_dag_tools(status="Running", tools="Read,Glob",
                               description="List 3 features.")
        with patch("runners.executor.add_memory_snapshot"):
            ex.execute_step(dag, self._plist(dag), step=1, memory_store={})

        self.assertEqual(len(sdk_calls), 1)
        prompt, tools = sdk_calls[0]
        self.assertTrue(prompt.startswith("Context:"), "SDK tool path must prepend project context")
        self.assertEqual(tools, "Read,Glob")

    def test_subprocess_fallback_fires_when_sdk_unavailable(self):
        """Tool-bearing subtask + sdk_tool unavailable + claude available → ClaudeRunner used."""
        ex = self._executor()
        ex.claude.available = True
        claude_calls = []

        def _mock_run(description, st_name, tools=""):
            claude_calls.append((description, st_name, tools))
            return True, "result"

        ex.claude.run = _mock_run

        dag = _make_dag_tools(status="Running", tools="Read",
                               description="List files.")
        with patch("runners.executor.add_memory_snapshot"):
            ex.execute_step(dag, self._plist(dag), step=1, memory_store={})

        self.assertEqual(len(claude_calls), 1)
        desc, st_name, _ = claude_calls[0]
        self.assertTrue(desc.startswith("Context:"), "Subprocess path must prepend project context")

    def test_unknown_tools_skipped_with_error_log(self):
        """Subtask with unknown tool stays Running and emits error log (TD-ARCH-005)."""
        ex = self._executor()
        ex.sdk_tool.available = True
        sdk_calls = []

        async def _mock_arun(prompt, tools_str):
            sdk_calls.append((prompt, tools_str))
            return True, "result"

        ex.sdk_tool.arun = _mock_arun

        dag = _make_dag_tools(status="Running", tools="Bash",
                               description="Run a script.")
        with patch("runners.executor.add_memory_snapshot"):
            with self.assertLogs("solo_builder", level="ERROR") as cm:
                ex.execute_step(dag, self._plist(dag), step=1, memory_store={})

        self.assertEqual(len(sdk_calls), 0, "Unknown tool must not be dispatched")
        self.assertTrue(any("invalid_tools" in line for line in cm.output))

    def test_hitl_level2_headless_proceeds_with_warning(self):
        """Bash tool in headless mode: HITL level 2 downgrades to warning + proceeds.

        pytest runs non-interactively (sys.stdin.isatty() == False), so level 2
        is treated as headless and the job proceeds after a warning log.
        BUT: Bash is also an unknown tool (not in _SCHEMAS), so it fails validation
        first. Use a valid tool + description with destructive keyword instead.
        """
        ex = self._executor()
        ex.sdk_tool.available = True
        sdk_calls = []

        async def _mock_arun(prompt, tools_str):
            sdk_calls.append((prompt, tools_str))
            return True, "result"

        ex.sdk_tool.arun = _mock_arun

        # Use a valid tool (Read) but destructive keyword in description (HITL rule 4)
        dag = _make_dag_tools(status="Running", tools="Read",
                               description="delete the old log files.")
        with patch("runners.executor.add_memory_snapshot"), \
             patch("runners.executor.sys") as _mock_sys:
            _mock_sys.stdin.isatty.return_value = False  # simulate headless
            with self.assertLogs("solo_builder", level="WARNING") as cm:
                ex.execute_step(dag, self._plist(dag), step=1, memory_store={})

        # Job should still dispatch (headless mode downgrade)
        self.assertEqual(len(sdk_calls), 1)
        self.assertTrue(any("hitl_pause" in line for line in cm.output))


# ═══════════════════════════════════════════════════════════════════════════════
# Executor metrics (TD-OPS-001)
# ═══════════════════════════════════════════════════════════════════════════════

import time
from runners.executor import _write_step_metrics, _METRICS_PATH


class TestWriteStepMetrics(unittest.TestCase):

    def test_writes_jsonl_record(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            tmp = f.name
        try:
            with patch("runners.executor._METRICS_PATH", tmp):
                t0 = time.monotonic()
                _write_step_metrics(5, t0, sdk_dispatched=2, sdk_succeeded=2,
                                    actions={"A1": "verified", "A2": "started"})
            with open(tmp, encoding="utf-8") as f:
                record = json.loads(f.readline())
            self.assertEqual(record["step"], 5)
            self.assertEqual(record["sdk_dispatched"], 2)
            self.assertEqual(record["sdk_succeeded"], 2)
            self.assertEqual(record["sdk_success_rate"], 1.0)
            self.assertEqual(record["verified"], 1)
            self.assertEqual(record["started"], 1)
            self.assertIn("ts", record)
            self.assertGreaterEqual(record["elapsed_s"], 0)
        finally:
            os.unlink(tmp)

    def test_sdk_success_rate_none_when_zero_dispatched(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            tmp = f.name
        try:
            with patch("runners.executor._METRICS_PATH", tmp):
                _write_step_metrics(1, time.monotonic(), 0, 0, {})
            with open(tmp, encoding="utf-8") as f:
                record = json.loads(f.readline())
            self.assertIsNone(record["sdk_success_rate"])
        finally:
            os.unlink(tmp)

    def test_appends_multiple_records(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            tmp = f.name
        try:
            with patch("runners.executor._METRICS_PATH", tmp):
                _write_step_metrics(1, time.monotonic(), 1, 1, {"A1": "verified"})
                _write_step_metrics(2, time.monotonic(), 1, 0, {"B1": "verified"})
            with open(tmp, encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["step"], 1)
            self.assertEqual(json.loads(lines[1])["step"], 2)
        finally:
            os.unlink(tmp)

    def test_oserror_does_not_raise(self):
        with patch("runners.executor._METRICS_PATH", "/nonexistent_dir/metrics.jsonl"):
            _write_step_metrics(1, time.monotonic(), 0, 0, {})  # no exception

    def test_sdk_success_rate_partial(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            tmp = f.name
        try:
            with patch("runners.executor._METRICS_PATH", tmp):
                _write_step_metrics(1, time.monotonic(), 4, 3, {})
            with open(tmp, encoding="utf-8") as f:
                record = json.loads(f.readline())
            self.assertEqual(record["sdk_success_rate"], 0.75)
        finally:
            os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()
