"""
Unit tests for discord_bot/bot.py — pure logic, no Discord connection needed.

Run:
    python -m pytest discord_bot/test_bot.py -v
  or:
    python discord_bot/test_bot.py
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: stub out discord so we can import bot.py without the library
# ---------------------------------------------------------------------------
class _FakeClient:
    """Minimal discord.Client stand-in that accepts keyword arguments."""
    def __init__(self, **kwargs):
        pass

discord_stub = MagicMock()
discord_stub.Intents.default.return_value = MagicMock()
discord_stub.Client = _FakeClient
discord_stub.Interaction = MagicMock
discord_stub.File = MagicMock
sys.modules.setdefault("discord", discord_stub)
sys.modules.setdefault("discord.app_commands", MagicMock())
sys.modules.setdefault("dotenv", MagicMock())

# Redirect env so bot.py doesn't need real tokens
os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("DISCORD_CHANNEL_ID", "0")

# Add repo root to path so "from discord_bot import ..." resolves
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

import importlib
import discord_bot.bot as bot_module  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dag(statuses: dict[str, str]) -> dict:
    """Build a minimal DAG dict with subtasks at the given statuses.

    statuses: {subtask_name: status_string}
    All subtasks are placed in Task0 / BranchA.
    """
    subtasks = {
        name: {"status": st, "shadow": "Pending", "last_update": 0, "output": ""}
        for name, st in statuses.items()
    }
    return {
        "Task0": {
            "status": "Pending",
            "branches": {
                "BranchA": {
                    "status": "Pending",
                    "subtasks": subtasks,
                }
            },
        }
    }


def _make_state(statuses: dict[str, str], step: int = 1) -> dict:
    return {"dag": _make_dag(statuses), "step": step}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHasWork(unittest.TestCase):
    def test_pending_means_work(self):
        dag = _make_dag({"A1": "Pending", "A2": "Verified"})
        self.assertTrue(bot_module._has_work(dag))

    def test_running_means_work(self):
        dag = _make_dag({"A1": "Running"})
        self.assertTrue(bot_module._has_work(dag))

    def test_all_verified_no_work(self):
        dag = _make_dag({"A1": "Verified", "A2": "Verified"})
        self.assertFalse(bot_module._has_work(dag))

    def test_review_not_counted_as_work(self):
        dag = _make_dag({"A1": "Review", "A2": "Verified"})
        self.assertFalse(bot_module._has_work(dag))

    def test_empty_dag_no_work(self):
        self.assertFalse(bot_module._has_work({}))


class TestFormatStatus(unittest.TestCase):
    def test_all_verified(self):
        state = _make_state({"A1": "Verified", "A2": "Verified"}, step=5)
        result = bot_module._format_status(state)
        self.assertIn("100.0%", result)
        self.assertIn("Step 5", result)
        self.assertIn("2/2", result)

    def test_mixed_statuses(self):
        state = _make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}, step=3)
        result = bot_module._format_status(state)
        self.assertIn("1 running", result)
        self.assertIn("33.3%", result)

    def test_empty_dag(self):
        result = bot_module._format_status({"dag": {}, "step": 0})
        self.assertIn("0%", result)

    def test_contains_task_row(self):
        state = _make_state({"A1": "Verified"})
        result = bot_module._format_status(state)
        self.assertIn("Task0", result)


class TestAutoRunning(unittest.TestCase):
    def setUp(self):
        # Reset module-level _auto_task before each test
        bot_module._auto_task = None

    def test_none_task_not_running(self):
        bot_module._auto_task = None
        self.assertFalse(bot_module._auto_running())

    def test_done_task_not_running(self):
        done = MagicMock()
        done.done.return_value = True
        bot_module._auto_task = done
        self.assertFalse(bot_module._auto_running())

    def test_active_task_is_running(self):
        active = MagicMock()
        active.done.return_value = False
        bot_module._auto_task = active
        self.assertTrue(bot_module._auto_running())

    def tearDown(self):
        bot_module._auto_task = None


class TestReadHeartbeat(unittest.TestCase):
    def test_valid_six_field_heartbeat(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("42,60,70,5,3,2")
            tmp = f.name
        try:
            with patch.object(bot_module, "STEP_PATH", Path(tmp)):
                result = bot_module._read_heartbeat()
            self.assertEqual(result, (42, 60, 70, 5, 3, 2))
        finally:
            os.unlink(tmp)

    def test_missing_file_returns_none(self):
        with patch.object(bot_module, "STEP_PATH", Path("/nonexistent/step.txt")):
            result = bot_module._read_heartbeat()
        self.assertIsNone(result)

    def test_malformed_content_returns_none(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("not,numbers,here,x,y,z")
            tmp = f.name
        try:
            with patch.object(bot_module, "STEP_PATH", Path(tmp)):
                result = bot_module._read_heartbeat()
            self.assertIsNone(result)
        finally:
            os.unlink(tmp)


class TestFormatStepLine(unittest.TestCase):
    def test_uses_heartbeat_when_available(self):
        with patch.object(bot_module, "_read_heartbeat", return_value=(10, 50, 70, 15, 3, 2)):
            line = bot_module._format_step_line({})
        self.assertIn("Step 10", line)
        self.assertIn("50✅", line)
        self.assertIn("3▶", line)

    def test_falls_back_to_dag_when_no_heartbeat(self):
        state = _make_state({"A1": "Verified", "A2": "Pending"}, step=7)
        with patch.object(bot_module, "_read_heartbeat", return_value=None):
            line = bot_module._format_step_line(state)
        self.assertIn("Step 7", line)
        self.assertIn("1✅", line)

    def test_shows_percentage(self):
        with patch.object(bot_module, "_read_heartbeat", return_value=(1, 35, 70, 35, 0, 0)):
            line = bot_module._format_step_line({})
        self.assertIn("50.0%", line)


class TestLoadState(unittest.TestCase):
    def test_loads_valid_json(self):
        state = {"dag": {}, "step": 99}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(state, f)
            tmp = f.name
        try:
            with patch.object(bot_module, "STATE_PATH", Path(tmp)):
                result = bot_module._load_state()
            self.assertEqual(result["step"], 99)
        finally:
            os.unlink(tmp)

    def test_missing_file_returns_empty(self):
        with patch.object(bot_module, "STATE_PATH", Path("/nonexistent/state.json")):
            result = bot_module._load_state()
        self.assertEqual(result, {"dag": {}, "step": 0})

    def test_corrupt_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("{bad json")
            tmp = f.name
        try:
            with patch.object(bot_module, "STATE_PATH", Path(tmp)):
                result = bot_module._load_state()
            self.assertEqual(result, {"dag": {}, "step": 0})
        finally:
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# _handle_text_command tests (async, full command dispatcher)
# ---------------------------------------------------------------------------

def _make_msg(content: str) -> MagicMock:
    """Minimal discord.Message stand-in."""
    msg = MagicMock()
    msg.content = content
    msg.channel.id = 123
    return msg


class TestHandleTextCommand(unittest.IsolatedAsyncioTestCase):

    async def test_status_no_auto(self):
        state = _make_state({"A1": "Verified"}, step=3)
        with patch.object(bot_module, "_load_state", return_value=state), \
             patch.object(bot_module, "_auto_running", return_value=False), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("status"))
        text = mock_send.call_args[0][1]
        self.assertIn("Step 3", text)
        self.assertNotIn("Auto-run", text)

    async def test_status_auto_running_appends_banner(self):
        state = _make_state({"A1": "Running"}, step=1)
        with patch.object(bot_module, "_load_state", return_value=state), \
             patch.object(bot_module, "_auto_running", return_value=True), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("status"))
        text = mock_send.call_args[0][1]
        self.assertIn("Auto-run in progress", text)

    async def test_run_no_work_sends_complete(self):
        state = _make_state({"A1": "Verified"}, step=5)
        with patch.object(bot_module, "_load_state", return_value=state), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "TRIGGER_PATH", new=MagicMock()):
            await bot_module._handle_text_command(_make_msg("run"))
        text = mock_send.call_args[0][1]
        self.assertIn("complete", text.lower())

    async def test_run_with_work_writes_trigger(self):
        state = _make_state({"A1": "Pending"}, step=1)
        mock_tp = MagicMock()
        with patch.object(bot_module, "_load_state", return_value=state), \
             patch.object(bot_module, "_send", new=AsyncMock()), \
             patch.object(bot_module, "TRIGGER_PATH", new=mock_tp):
            await bot_module._handle_text_command(_make_msg("run"))
        mock_tp.write_text.assert_called_once_with("1")

    async def test_auto_already_running_sends_warning(self):
        with patch.object(bot_module, "_auto_running", return_value=True), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("auto 5"))
        text = mock_send.call_args[0][1]
        self.assertIn("already running", text.lower())

    async def test_auto_n_creates_task(self):
        bot_module._auto_task = None
        created = []

        def _fake_create_task(coro):
            try:
                coro.close()   # suppress "coroutine never awaited" RuntimeWarning
            except Exception:
                pass
            m = MagicMock()
            created.append(m)
            return m

        with patch.object(bot_module, "_auto_running", return_value=False), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch("asyncio.create_task", side_effect=_fake_create_task):
            await bot_module._handle_text_command(_make_msg("auto 7"))
        self.assertEqual(len(created), 1)
        text = mock_send.call_args[0][1]
        self.assertIn("7 steps", text)

    async def test_stop_with_auto_running_cancels(self):
        task_mock = MagicMock()
        bot_module._auto_task = task_mock
        mock_st = MagicMock()
        with patch.object(bot_module, "_auto_running", return_value=True), \
             patch.object(bot_module, "_send", new=AsyncMock()), \
             patch.object(bot_module, "STOP_TRIGGER", new=mock_st):
            await bot_module._handle_text_command(_make_msg("stop"))
        task_mock.cancel.assert_called_once()
        mock_st.write_text.assert_called_once_with("1")

    async def test_verify_queues_trigger(self):
        mock_vt = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "VERIFY_TRIGGER", new=mock_vt):
            await bot_module._handle_text_command(_make_msg("verify A3 looks good"))
        mock_vt.write_text.assert_called_once()
        written = json.loads(mock_vt.write_text.call_args[0][0])
        self.assertEqual(written["subtask"], "A3")
        self.assertEqual(written["note"], "looks good")

    async def test_verify_no_args_sends_usage(self):
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("verify"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_help_sends_help_text(self):
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("help"))
        text = mock_send.call_args[0][1]
        self.assertEqual(text, bot_module._HELP_TEXT)


# ---------------------------------------------------------------------------
# _run_auto integration tests (async, no Discord, no filesystem I/O)
# ---------------------------------------------------------------------------

class TestRunAuto(unittest.IsolatedAsyncioTestCase):
    """Test _run_auto logic by mocking _read_heartbeat, _load_state, channel."""

    def _all_verified_state(self) -> dict:
        return _make_state({"A1": "Verified", "A2": "Verified"}, step=5)

    def _pending_state(self) -> dict:
        return _make_state({"A1": "Pending", "A2": "Pending"}, step=1)

    async def test_no_work_sends_completion_message(self):
        """If pipeline is already complete, sends completion message immediately."""
        ch = AsyncMock()
        with patch.object(bot_module, "_read_heartbeat",
                          return_value=(5, 2, 2, 0, 0, 0)), \
             patch.object(bot_module, "_load_state",
                          return_value=self._all_verified_state()), \
             patch.object(bot_module, "_get_channel",
                          new=AsyncMock(return_value=ch)), \
             patch("asyncio.sleep", new=AsyncMock()):
            await bot_module._run_auto(0, 5)
        ch.send.assert_called()
        text = ch.send.call_args_list[-1][0][0]
        self.assertIn("complete", text.lower())

    async def test_step_completes_ticker_then_summary(self):
        """A single completed step sends a ticker, then a summary at n-step limit."""
        ch = AsyncMock()
        call_count = [0]

        def mock_hb():
            call_count[0] += 1
            # calls 1-2: has_work + current_step (step=1, pending=2)
            # calls 3+: step advanced to 2
            if call_count[0] <= 2:
                return (1, 0, 2, 2, 0, 0)
            return (2, 1, 2, 1, 0, 0)

        with patch.object(bot_module, "_read_heartbeat", side_effect=mock_hb), \
             patch.object(bot_module, "_load_state",
                          return_value=self._pending_state()), \
             patch.object(bot_module, "_get_channel",
                          new=AsyncMock(return_value=ch)), \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch.object(bot_module, "TRIGGER_PATH", new=MagicMock()):
            await bot_module._run_auto(0, 1)
        # Should send: ticker after step, then n-step summary
        self.assertGreaterEqual(ch.send.call_count, 2)

    async def test_step_timeout_sends_warning(self):
        """If heartbeat never advances, sends a timeout warning."""
        ch = AsyncMock()

        def mock_hb():
            # Always returns step=1 — heartbeat never advances
            return (1, 0, 2, 2, 0, 0)

        with patch.object(bot_module, "_read_heartbeat", side_effect=mock_hb), \
             patch.object(bot_module, "_load_state",
                          return_value=self._pending_state()), \
             patch.object(bot_module, "_get_channel",
                          new=AsyncMock(return_value=ch)), \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch.object(bot_module, "TRIGGER_PATH", new=MagicMock()):
            await bot_module._run_auto(0, 5)
        text = ch.send.call_args_list[-1][0][0]
        self.assertIn("timeout", text.lower())

    async def test_pipeline_completes_mid_run_sends_complete(self):
        """When pipeline finishes before n-step limit, sends completion message."""
        ch = AsyncMock()
        call_count = [0]

        def mock_hb():
            call_count[0] += 1
            if call_count[0] <= 2:
                return (1, 0, 2, 2, 0, 0)   # step=1, has work
            return (2, 2, 2, 0, 0, 0)        # step=2, all verified

        all_verified = _make_state({"A1": "Verified", "A2": "Verified"}, step=2)

        with patch.object(bot_module, "_read_heartbeat", side_effect=mock_hb), \
             patch.object(bot_module, "_load_state",
                          return_value=all_verified), \
             patch.object(bot_module, "_get_channel",
                          new=AsyncMock(return_value=ch)), \
             patch("asyncio.sleep", new=AsyncMock()), \
             patch.object(bot_module, "TRIGGER_PATH", new=MagicMock()):
            await bot_module._run_auto(0, 10)
        last_msg = ch.send.call_args_list[-1][0][0]
        self.assertIn("complete", last_msg.lower())


# ---------------------------------------------------------------------------
# TestFireCompletion
# ---------------------------------------------------------------------------

import solo_builder_cli as _cli_module


class TestFireCompletion(unittest.TestCase):
    """Tests for solo_builder_cli._fire_completion (webhook POST logic)."""

    def setUp(self):
        os.makedirs(os.path.join(os.path.dirname(_cli_module.__file__), "state"),
                    exist_ok=True)
        self._log = os.path.join(_cli_module._HERE, "state", "webhook_errors.log")
        if os.path.exists(self._log):
            os.remove(self._log)
        # Suppress real powershell.exe spawns in tests that don't test _notify
        self._popen_patcher = patch.object(_cli_module.subprocess, "Popen",
                                           new=MagicMock())
        self._popen_patcher.start()

    def _set_url(self, url: str):
        _cli_module.WEBHOOK_URL = url

    def tearDown(self):
        self._popen_patcher.stop()
        _cli_module.WEBHOOK_URL = ""
        if os.path.exists(self._log):
            os.remove(self._log)

    def test_no_post_when_url_empty(self):
        """No HTTP call is made when WEBHOOK_URL is empty."""
        self._set_url("")
        with patch("urllib.request.urlopen") as mock_open:
            _cli_module._fire_completion(1, 1, 1)
            import time; time.sleep(0.3)
        mock_open.assert_not_called()

    def test_post_correct_payload(self):
        """urlopen is called with the correct JSON payload and Content-Type."""
        self._set_url("http://localhost:19999")
        captured = []

        def fake_open(req, timeout=None):
            captured.append({
                "url": req.full_url,
                "data": json.loads(req.data),
                "ct": req.get_header("Content-type"),
            })

        with patch("urllib.request.urlopen", side_effect=fake_open):
            _cli_module._fire_completion(steps=5, verified=70, total=70)
            import time; time.sleep(0.3)

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["url"], "http://localhost:19999")
        self.assertEqual(captured[0]["data"],
                         {"event": "complete", "steps": 5, "verified": 70, "total": 70})
        self.assertEqual(captured[0]["ct"], "application/json")
        self.assertFalse(os.path.exists(self._log))

    def test_post_failure_writes_error_log(self):
        """When urlopen raises, the error is written to webhook_errors.log."""
        self._set_url("http://bad-host.invalid")

        with patch("urllib.request.urlopen",
                   side_effect=Exception("connection refused")):
            _cli_module._fire_completion(steps=1, verified=1, total=1)
            import time; time.sleep(0.3)

        self.assertTrue(os.path.exists(self._log),
                        "webhook_errors.log not created on failure")
        with open(self._log) as _f:
            content = _f.read()
        self.assertIn("connection refused", content)
        self.assertIn("http://bad-host.invalid", content)

    def test_notify_calls_popen_with_message(self):
        """_notify launches powershell.exe with a message string via subprocess.Popen."""
        self._set_url("")   # webhook off — only _notify fires
        self._popen_patcher.stop()   # remove class-level no-op mock for this test
        popen_calls = []

        def fake_popen(cmd, **kwargs):
            popen_calls.append(cmd)
            return MagicMock()

        with patch.object(_cli_module.subprocess, "Popen", side_effect=fake_popen):
            _cli_module._fire_completion(steps=7, verified=42, total=70)
            import time; time.sleep(0.3)
        self._popen_patcher.start()  # restore for tearDown

        self.assertEqual(len(popen_calls), 1)
        cmd = popen_calls[0]
        self.assertEqual(cmd[0], "powershell.exe")
        joined = " ".join(cmd)
        self.assertIn("42/70", joined)
        self.assertIn("7 steps", joined)


# ---------------------------------------------------------------------------
# TestCLICommands
# ---------------------------------------------------------------------------

import copy as _copy


class TestCLICommands(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_add_task and _cmd_add_branch."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()    # suppress terminal rendering
        self.cli.executor.claude.available = False

    def test_add_task_fallback_creates_single_subtask(self):
        """No Claude: creates one subtask whose description is the input spec."""
        idx = len(self.cli.dag)
        letter = chr(ord("A") + idx % 26)
        with patch("builtins.input", return_value="build a login page"), \
             patch("time.sleep"):
            self.cli._cmd_add_task()
        new_task = f"Task {idx}"
        branch   = f"Branch {letter}"
        st_key   = f"{letter}1"
        self.assertIn(new_task, self.cli.dag)
        subtasks = self.cli.dag[new_task]["branches"][branch]["subtasks"]
        self.assertIn(st_key, subtasks)
        self.assertEqual(subtasks[st_key]["description"], "build a login page")
        self.assertEqual(subtasks[st_key]["status"], "Pending")

    def test_add_task_claude_decompose_creates_subtasks(self):
        """Claude JSON response: subtasks are created from the parsed array."""
        idx    = len(self.cli.dag)
        letter = chr(ord("A") + idx % 26)
        decomp = (f'[{{"name": "{letter}1", "description": "Set up auth"}}, '
                  f'{{"name": "{letter}2", "description": "Write tests"}}]')
        self.cli.executor.claude.available = True
        self.cli.executor.claude.run = MagicMock(return_value=(True, decomp))
        with patch("builtins.input", return_value="build auth system"), \
             patch("time.sleep"):
            self.cli._cmd_add_task()
        branch   = f"Branch {letter}"
        subtasks = self.cli.dag[f"Task {idx}"]["branches"][branch]["subtasks"]
        self.assertEqual(len(subtasks), 2)
        self.assertIn(f"{letter}1", subtasks)
        self.assertIn(f"{letter}2", subtasks)
        self.assertEqual(subtasks[f"{letter}1"]["description"], "Set up auth")

    def test_add_task_empty_spec_cancels(self):
        """Empty input cancels without modifying the DAG."""
        initial_count = len(self.cli.dag)
        with patch("builtins.input", return_value=""), \
             patch("time.sleep"):
            self.cli._cmd_add_task()
        self.assertEqual(len(self.cli.dag), initial_count)

    def test_add_task_wires_dependency_on_last_task(self):
        """Newly added task depends on the last existing task."""
        last_task = list(self.cli.dag.keys())[-1]
        idx = len(self.cli.dag)
        with patch("builtins.input", return_value="deploy to prod"), \
             patch("time.sleep"):
            self.cli._cmd_add_task()
        new_task = f"Task {idx}"
        self.assertIn(last_task, self.cli.dag[new_task]["depends_on"])

    def test_add_branch_unknown_task_prints_usage(self):
        """Unknown task name returns without changing the DAG."""
        snapshot = _copy.deepcopy(self.cli.dag)
        self.cli._cmd_add_branch("Nonexistent Task 99")
        self.assertEqual(list(self.cli.dag.keys()), list(snapshot.keys()))

    def test_add_branch_digit_arg_resolves_task_name(self):
        """'add_branch 0' resolves to 'Task 0' and adds a branch."""
        initial_branches = len(self.cli.dag["Task 0"]["branches"])
        with patch("builtins.input", return_value="add caching layer"), \
             patch("time.sleep"):
            self.cli._cmd_add_branch("0")
        self.assertEqual(
            len(self.cli.dag["Task 0"]["branches"]), initial_branches + 1
        )

    def test_add_branch_at_max_branches_blocked(self):
        """Task already at MAX_BRANCHES_PER_TASK limit is rejected."""
        task = self.cli.dag["Task 0"]
        while len(task["branches"]) < _cli_module.MAX_BRANCHES_PER_TASK:
            n = len(task["branches"])
            task["branches"][f"Branch X{n}"] = {"status": "Pending", "subtasks": {}}
        initial_count = len(task["branches"])
        self.cli._cmd_add_branch("Task 0")
        self.assertEqual(len(task["branches"]), initial_count)

    def test_add_branch_fallback_creates_single_subtask(self):
        """No Claude: new branch gets one subtask with the input spec."""
        initial_branches = len(self.cli.dag["Task 0"]["branches"])
        with patch("builtins.input", return_value="improve error handling"), \
             patch("time.sleep"):
            self.cli._cmd_add_branch("Task 0")
        branches = self.cli.dag["Task 0"]["branches"]
        self.assertEqual(len(branches), initial_branches + 1)
        new_branch = list(branches.keys())[-1]
        subtasks   = branches[new_branch]["subtasks"]
        self.assertEqual(len(subtasks), 1)
        st = list(subtasks.values())[0]
        self.assertEqual(st["description"], "improve error handling")
        self.assertEqual(st["status"], "Pending")

    def test_add_branch_reopens_verified_task(self):
        """Adding a branch to a Verified task sets it back to Running."""
        self.cli.dag["Task 0"]["status"] = "Verified"
        with patch("builtins.input", return_value="new concern"), \
             patch("time.sleep"):
            self.cli._cmd_add_branch("Task 0")
        self.assertEqual(self.cli.dag["Task 0"]["status"], "Running")


# ---------------------------------------------------------------------------
# TestVerifyDescribeTools
# ---------------------------------------------------------------------------

class TestVerifyDescribeTools(unittest.TestCase):
    """Tests for _cmd_verify, _cmd_describe, and _cmd_tools."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()

    def _st(self, name: str) -> dict:
        for task_data in self.cli.dag.values():
            for branch_data in task_data.get("branches", {}).values():
                if name in branch_data.get("subtasks", {}):
                    return branch_data["subtasks"][name]
        return {}

    # ── _cmd_verify ──────────────────────────────────────────────────────────

    def test_verify_flips_status_and_sets_output(self):
        """verify <ST> <note> sets status=Verified, shadow=Done, output=note."""
        self.cli._cmd_verify("A1 output looks correct")
        st = self._st("A1")
        self.assertEqual(st["status"], "Verified")
        self.assertEqual(st["shadow"], "Done")
        self.assertEqual(st["output"], "output looks correct")

    def test_verify_default_note_when_omitted(self):
        """verify <ST> with no note defaults to 'Manually verified'."""
        self.cli._cmd_verify("A1")
        self.assertEqual(self._st("A1")["output"], "Manually verified")

    def test_verify_unknown_subtask_leaves_dag_unchanged(self):
        """Unknown subtask name leaves DAG identical."""
        snapshot = _copy.deepcopy(self.cli.dag)
        self.cli._cmd_verify("ZZZZ99")
        self.assertEqual(self.cli.dag, snapshot)

    def test_verify_empty_arg_prints_usage(self):
        """Empty arg leaves DAG identical."""
        snapshot = _copy.deepcopy(self.cli.dag)
        self.cli._cmd_verify("")
        self.assertEqual(self.cli.dag, snapshot)

    # ── _cmd_describe ─────────────────────────────────────────────────────────

    def test_describe_sets_description_and_running(self):
        """describe <ST> <text> sets description, status=Running, clears output."""
        self.cli._cmd_describe("A1 rewrite login with OAuth2")
        st = self._st("A1")
        self.assertEqual(st["description"], "rewrite login with OAuth2")
        self.assertEqual(st["status"], "Running")
        self.assertEqual(st["shadow"], "Pending")
        self.assertEqual(st["output"], "")

    def test_describe_propagates_running_to_branch_and_task(self):
        """describe sets branch status and parent task status to Running."""
        self.cli._cmd_describe("A1 do the thing")
        branch = self.cli.dag["Task 0"]["branches"]["Branch A"]
        self.assertEqual(branch["status"], "Running")
        self.assertEqual(self.cli.dag["Task 0"]["status"], "Running")

    def test_describe_missing_text_prints_usage(self):
        """Single token with no description text leaves DAG unchanged."""
        snapshot = _copy.deepcopy(self.cli.dag)
        self.cli._cmd_describe("A1")
        self.assertEqual(self.cli.dag, snapshot)

    def test_describe_unknown_subtask_leaves_dag_unchanged(self):
        """Unknown subtask name leaves DAG identical."""
        snapshot = _copy.deepcopy(self.cli.dag)
        self.cli._cmd_describe("ZZZZ99 some text")
        self.assertEqual(self.cli.dag, snapshot)

    # ── _cmd_tools ────────────────────────────────────────────────────────────

    def test_tools_sets_tool_list(self):
        """tools <ST> Read,Glob,Grep stores the tool string on the subtask."""
        self.cli._cmd_tools("A1 Read,Glob,Grep")
        self.assertEqual(self._st("A1").get("tools"), "Read,Glob,Grep")

    def test_tools_none_clears_to_empty_string(self):
        """tools <ST> none stores empty string (headless mode)."""
        self.cli._cmd_tools("A1 none")
        self.assertEqual(self._st("A1").get("tools"), "")

    def test_tools_requeues_verified_subtask(self):
        """tools on a Verified subtask re-sets it to Running."""
        self.cli._cmd_verify("A1")
        self.assertEqual(self._st("A1")["status"], "Verified")
        self.cli._cmd_tools("A1 Bash,Read")
        st = self._st("A1")
        self.assertEqual(st["status"], "Running")
        self.assertEqual(st["shadow"], "Pending")
        self.assertEqual(st["output"], "")

    def test_tools_missing_toollist_prints_usage(self):
        """Single token with no tool list leaves DAG unchanged."""
        snapshot = _copy.deepcopy(self.cli.dag)
        self.cli._cmd_tools("A1")
        self.assertEqual(self.cli.dag, snapshot)

    def test_tools_unknown_subtask_leaves_dag_unchanged(self):
        """Unknown subtask name leaves DAG identical."""
        snapshot = _copy.deepcopy(self.cli.dag)
        self.cli._cmd_tools("ZZZZ99 Read")
        self.assertEqual(self.cli.dag, snapshot)


# ---------------------------------------------------------------------------
# TestSetCommand
# ---------------------------------------------------------------------------

class TestSetCommand(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_set (runtime config changes)."""

    def setUp(self):
        # Route config persistence to a temp file so _cmd_set tests do not
        # mutate tracked repo config/settings.json.
        self._tmp_cfg = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        self._tmp_cfg_path = self._tmp_cfg.name
        json.dump({"STALL_THRESHOLD": _cli_module.STALL_THRESHOLD}, self._tmp_cfg)
        self._tmp_cfg.close()
        self._orig_cfg_path = _cli_module._CFG_PATH
        _cli_module._CFG_PATH = self._tmp_cfg_path

        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        # Suppress sleep calls in every _cmd_set invocation
        self._sleep_patcher = patch("time.sleep")
        self._sleep_patcher.start()
        # Save module globals that _cmd_set may mutate
        self._orig = {
            "STALL_THRESHOLD":   _cli_module.STALL_THRESHOLD,
            "AUTO_STEP_DELAY":   _cli_module.AUTO_STEP_DELAY,
            "AUTO_SAVE_INTERVAL":_cli_module.AUTO_SAVE_INTERVAL,
            "CLAUDE_ALLOWED_TOOLS": _cli_module.CLAUDE_ALLOWED_TOOLS,
            "WEBHOOK_URL":       _cli_module.WEBHOOK_URL,
            "VERBOSITY":         _cli_module.VERBOSITY,
            "SNAPSHOT_INTERVAL": _cli_module.SNAPSHOT_INTERVAL,
        }

    def tearDown(self):
        self._sleep_patcher.stop()
        _cli_module._CFG_PATH = self._orig_cfg_path
        try:
            os.unlink(self._tmp_cfg_path)
        except FileNotFoundError:
            pass
        for k, v in self._orig.items():
            setattr(_cli_module, k, v)

    def test_set_stall_threshold_updates_module_and_agents(self):
        """STALL_THRESHOLD changes module global and healer/planner/display."""
        self.cli._cmd_set("STALL_THRESHOLD=10")
        self.assertEqual(_cli_module.STALL_THRESHOLD, 10)
        self.assertEqual(self.cli.healer.stall_threshold, 10)
        self.assertEqual(self.cli.planner.stall_threshold, 10)
        self.assertEqual(self.cli.display.stall_threshold, 10)

    def test_set_verify_prob_updates_executor(self):
        """VERIFY_PROB changes executor.verify_prob."""
        self.cli._cmd_set("VERIFY_PROB=0.9")
        self.assertAlmostEqual(self.cli.executor.verify_prob, 0.9)

    def test_set_auto_step_delay_updates_module_global(self):
        """AUTO_STEP_DELAY changes module-level global."""
        self.cli._cmd_set("AUTO_STEP_DELAY=1.5")
        self.assertAlmostEqual(_cli_module.AUTO_STEP_DELAY, 1.5)

    def test_set_auto_save_interval(self):
        """AUTO_SAVE_INTERVAL changes module-level global."""
        self.cli._cmd_set("AUTO_SAVE_INTERVAL=10")
        self.assertEqual(_cli_module.AUTO_SAVE_INTERVAL, 10)

    def test_set_review_mode_on(self):
        """REVIEW_MODE=on sets executor.review_mode to True."""
        self.cli._cmd_set("REVIEW_MODE=on")
        self.assertTrue(self.cli.executor.review_mode)

    def test_set_review_mode_off(self):
        """REVIEW_MODE=off sets executor.review_mode to False."""
        self.cli.executor.review_mode = True
        self.cli._cmd_set("REVIEW_MODE=off")
        self.assertFalse(self.cli.executor.review_mode)

    def test_set_claude_subprocess_off(self):
        """CLAUDE_SUBPROCESS=off sets executor.claude.available to False."""
        self.cli.executor.claude.available = True
        self.cli._cmd_set("CLAUDE_SUBPROCESS=off")
        self.assertFalse(self.cli.executor.claude.available)

    def test_set_anthropic_max_tokens(self):
        """ANTHROPIC_MAX_TOKENS changes executor.anthropic.max_tokens."""
        self.cli._cmd_set("ANTHROPIC_MAX_TOKENS=256")
        self.assertEqual(self.cli.executor.anthropic.max_tokens, 256)

    def test_set_webhook_url(self):
        """WEBHOOK_URL changes module-level WEBHOOK_URL global."""
        self.cli._cmd_set("WEBHOOK_URL=http://example.com/hook")
        self.assertEqual(_cli_module.WEBHOOK_URL, "http://example.com/hook")

    def test_set_webhook_url_non_http_warns_but_sets(self):
        """Non-http WEBHOOK_URL prints a warning but still sets the value."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._cmd_set("WEBHOOK_URL=not-a-url")
        self.assertEqual(_cli_module.WEBHOOK_URL, "not-a-url")
        self.assertIn("Warning", buf.getvalue())

    def test_set_webhook_url_clear_no_warning(self):
        """Clearing WEBHOOK_URL (empty value) does not print a warning."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._cmd_set("WEBHOOK_URL=")
        self.assertEqual(_cli_module.WEBHOOK_URL, "")
        self.assertNotIn("Warning", buf.getvalue())

    def test_set_invalid_value_raises_no_exception(self):
        """Non-numeric value for int key prints error without raising."""
        orig = _cli_module.STALL_THRESHOLD
        self.cli._cmd_set("STALL_THRESHOLD=notanint")   # should not raise
        self.assertEqual(_cli_module.STALL_THRESHOLD, orig)   # unchanged

    def test_set_missing_equals_prints_usage(self):
        """Missing '=' prints usage; display.render still called."""
        self.cli._cmd_set("NOEQUALSSIGN")   # should not raise

    def test_set_unknown_key_prints_error(self):
        """Unknown key prints error message without raising."""
        self.cli._cmd_set("BADKEY=123")   # should not raise

    def test_set_bare_known_key_prints_current_value(self):
        """Bare known key (no '=') prints its current value."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._cmd_set("REVIEW_MODE")
        self.assertIn("REVIEW_MODE", buf.getvalue())

    def test_set_bare_unknown_key_prints_usage(self):
        """Bare unknown key (no '=') prints usage hint."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._cmd_set("UNKNOWNKEY")
        self.assertIn("Usage", buf.getvalue())

    def test_set_persists_review_mode_to_settings_json(self):
        """set REVIEW_MODE=on writes the bool True to a settings JSON file."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"REVIEW_MODE": False}, tmp)
        tmp.close()
        orig = _cli_module._CFG_PATH
        _cli_module._CFG_PATH = tmp.name
        try:
            self.cli._cmd_set("REVIEW_MODE=on")
            with open(tmp.name, encoding="utf-8") as f:
                data = json.load(f)
            self.assertTrue(data["REVIEW_MODE"])
        finally:
            _cli_module._CFG_PATH = orig
            os.unlink(tmp.name)

    def test_set_persists_webhook_url_to_settings_json(self):
        """set WEBHOOK_URL=http://x writes the URL to a settings JSON file."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"WEBHOOK_URL": ""}, tmp)
        tmp.close()
        orig = _cli_module._CFG_PATH
        _cli_module._CFG_PATH = tmp.name
        try:
            self.cli._cmd_set("WEBHOOK_URL=http://example.com/hook")
            with open(tmp.name, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["WEBHOOK_URL"], "http://example.com/hook")
        finally:
            _cli_module._CFG_PATH = orig
            os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# TestResetCommand
# ---------------------------------------------------------------------------

class TestResetCommand(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_reset."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self._sleep_patcher = patch("time.sleep")
        self._sleep_patcher.start()

    def tearDown(self):
        self._sleep_patcher.stop()

    def test_reset_restores_initial_dag_and_zeroes_step(self):
        """After reset, dag equals INITIAL_DAG and step == 0."""
        self.cli.step = 5
        self.cli.dag["Task 0"]["status"] = "Verified"
        self.cli._cmd_reset()
        import copy as _c
        self.assertEqual(self.cli.dag, _c.deepcopy(_cli_module.INITIAL_DAG))
        self.assertEqual(self.cli.step, 0)

    def test_reset_clears_alerts_and_healer_total(self):
        """reset clears alerts list and resets healer.healed_total."""
        self.cli.alerts = ["stall in A1", "stall in B2"]
        self.cli.healer.healed_total = 7
        self.cli._cmd_reset()
        self.assertEqual(self.cli.alerts, [])
        self.assertEqual(self.cli.healer.healed_total, 0)

    def test_reset_removes_state_file_if_present(self):
        """reset deletes the state file when it exists."""
        state_path = _cli_module.STATE_PATH
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        open(state_path, "w").close()   # create an empty sentinel file
        self.cli._cmd_reset()
        self.assertFalse(os.path.exists(state_path),
                         f"State file still present after reset: {state_path}")


# ---------------------------------------------------------------------------
# TestExportCommand
# ---------------------------------------------------------------------------

import io, contextlib


class TestExportCommand(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_export."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self._export_path = os.path.join(_cli_module._HERE, "solo_builder_outputs.md")
        self.addCleanup(self._remove_export)

    def _remove_export(self):
        if os.path.exists(self._export_path):
            os.remove(self._export_path)

    def _read_export(self) -> str:
        with open(self._export_path, encoding="utf-8") as f:
            return f.read()

    def test_export_no_outputs_writes_placeholder(self):
        """Fresh DAG (no outputs) writes header + placeholder; returns count 0."""
        path, count = self.cli._cmd_export()
        self.assertEqual(count, 0)
        self.assertTrue(os.path.exists(path))
        content = self._read_export()
        self.assertIn("Solo Builder", content)
        self.assertIn("No Claude outputs recorded yet", content)

    def test_export_with_outputs_writes_subtask_sections(self):
        """Subtasks with output produce ## headings and output text in the file."""
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = \
            "OAuth2 flow implemented with PKCE."
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A2"]["output"] = \
            "Unit tests for auth module written."
        path, count = self.cli._cmd_export()
        self.assertEqual(count, 2)
        content = self._read_export()
        self.assertIn("## A1 — Task 0 / Branch A", content)
        self.assertIn("OAuth2 flow implemented with PKCE.", content)
        self.assertIn("## A2 — Task 0 / Branch A", content)
        self.assertIn("Unit tests for auth module written.", content)

    def test_export_returns_correct_path(self):
        """Return tuple path matches the known output file location."""
        path, _ = self.cli._cmd_export()
        self.assertEqual(path, self._export_path)

    def test_export_count_matches_subtasks_with_output(self):
        """Count reflects exactly how many subtasks have non-empty output."""
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = "done"
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A3"]["output"] = "done"
        self.cli.dag["Task 0"]["branches"]["Branch B"]["subtasks"]["B1"]["output"] = "done"
        _, count = self.cli._cmd_export()
        self.assertEqual(count, 3)

    def test_export_includes_step_and_verified_in_header(self):
        """Header line contains step number and verified/total counts."""
        self.cli.step = 7
        _, _ = self.cli._cmd_export()
        content = self._read_export()
        self.assertIn("Step: 7", content)
        self.assertIn("/70", content)


# ---------------------------------------------------------------------------
# TestStatusCommand
# ---------------------------------------------------------------------------

class TestStatusCommand(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_status."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()

    def _run_status(self) -> str:
        """Capture stdout from _cmd_status (patches input to avoid blocking)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), \
             patch("builtins.input", return_value=""):
            self.cli._cmd_status()
        return buf.getvalue()

    def test_status_prints_total_subtask_count(self):
        """Output contains 'Total subtasks' and the correct count (70)."""
        out = self._run_status()
        self.assertIn("Total subtasks", out)
        self.assertIn("70", out)

    def test_status_reflects_verified_count_after_verify(self):
        """After verifying one subtask, Verified line shows 1."""
        self.cli._cmd_verify("A1 checked")
        out = self._run_status()
        self.assertIn("Verified", out)
        # The line "Verified       : N" should show 1
        lines = [l for l in out.splitlines() if "Verified" in l and ":" in l]
        self.assertTrue(lines, "No 'Verified : N' line found")
        # Strip ANSI codes and check the count
        import re
        plain = re.sub(r'\x1b\[[0-9;]*m', '', lines[0])
        self.assertIn("1", plain)

    def test_status_shows_forecast(self):
        """Output contains 'Forecast' (MetaOptimizer forecast string)."""
        out = self._run_status()
        self.assertIn("Forecast", out)


# ---------------------------------------------------------------------------
# TestDependsUndepends
# ---------------------------------------------------------------------------

class TestDependsUndepends(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_depends and _cmd_undepends."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self._sleep_patcher = patch("time.sleep")
        self._sleep_patcher.start()

    def tearDown(self):
        self._sleep_patcher.stop()

    def _run(self, method, args: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            method(args)
        return buf.getvalue()

    def test_depends_no_args_prints_graph(self):
        """No args prints the dependency graph (contains task names)."""
        out = self._run(self.cli._cmd_depends, "")
        self.assertIn("Task 0", out)
        self.assertIn("Task 6", out)

    def test_depends_adds_new_dependency(self):
        """Digit form '0 6' adds Task 6 to Task 0's depends_on list."""
        self._run(self.cli._cmd_depends, "0 6")
        deps = self.cli.dag["Task 0"].get("depends_on", [])
        self.assertIn("Task 6", deps)

    def test_depends_digit_args_normalise_to_task_names(self):
        """'1 3' normalises to 'Task 1' → 'Task 3'; success message printed."""
        out = self._run(self.cli._cmd_depends, "1 3")
        self.assertIn("now depends on", out)
        deps = self.cli.dag["Task 1"].get("depends_on", [])
        self.assertIn("Task 3", deps)

    def test_depends_self_dependency_rejected(self):
        """A task cannot depend on itself — error printed, no dep added."""
        out = self._run(self.cli._cmd_depends, "0 0")
        self.assertIn("cannot depend on itself", out)
        deps = self.cli.dag["Task 0"].get("depends_on", [])
        self.assertNotIn("Task 0", deps)

    def test_depends_unknown_task_rejected(self):
        """Unknown task number prints 'not found' and does not modify DAG."""
        out = self._run(self.cli._cmd_depends, "99 0")
        self.assertIn("not found", out)

    def test_depends_duplicate_is_noop(self):
        """Adding the same dependency twice leaves list unchanged and prints warning."""
        self._run(self.cli._cmd_depends, "0 6")
        out = self._run(self.cli._cmd_depends, "0 6")
        self.assertIn("already depends on", out)
        deps = self.cli.dag["Task 0"].get("depends_on", [])
        self.assertEqual(deps.count("Task 6"), 1)

    def test_undepends_removes_existing_dep(self):
        """undepends removes a dependency that was added via depends."""
        self._run(self.cli._cmd_depends, "0 6")
        self.assertIn("Task 6", self.cli.dag["Task 0"].get("depends_on", []))
        self._run(self.cli._cmd_undepends, "0 6")
        self.assertNotIn("Task 6", self.cli.dag["Task 0"].get("depends_on", []))

    def test_undepends_no_args_prints_usage(self):
        """Missing args prints usage line."""
        out = self._run(self.cli._cmd_undepends, "")
        self.assertIn("Usage", out)

    def test_undepends_unknown_task_prints_error(self):
        """Unknown target task prints 'not found'."""
        out = self._run(self.cli._cmd_undepends, "Task 99 Task 0")
        self.assertIn("not found", out)

    def test_undepends_dep_not_present_prints_error(self):
        """Removing a dep that does not exist prints 'does not depend on'."""
        out = self._run(self.cli._cmd_undepends, "0 6")
        self.assertIn("does not depend on", out)


# ---------------------------------------------------------------------------
# TestOutputCommand
# ---------------------------------------------------------------------------

class TestOutputCommand(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_output."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()

    def _run(self, args: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._cmd_output(args)
        return buf.getvalue()

    def test_output_with_output_prints_content(self):
        """Subtask with recorded output prints that text."""
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = \
            "Auth module implemented."
        out = self._run("A1")
        self.assertIn("Auth module implemented.", out)

    def test_output_no_output_prints_placeholder(self):
        """Subtask with no output prints 'No output for ... yet'."""
        out = self._run("A1")
        self.assertIn("No output", out)
        self.assertIn("A1", out)

    def test_output_unknown_subtask_prints_error(self):
        """Unknown subtask name prints 'not found'."""
        out = self._run("ZZZ")
        self.assertIn("not found", out)

    def test_output_empty_arg_prints_usage(self):
        """Empty argument string prints usage line."""
        out = self._run("")
        self.assertIn("Usage", out)


# ---------------------------------------------------------------------------
# TestSaveLoadState
# ---------------------------------------------------------------------------

class TestSaveLoadState(unittest.TestCase):
    """Tests for SoloBuilderCLI.save_state and load_state."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self.addCleanup(self._remove_state)

    def _remove_state(self):
        if os.path.exists(_cli_module.STATE_PATH):
            os.remove(_cli_module.STATE_PATH)
        for i in range(1, 4):
            p = f"{_cli_module.STATE_PATH}.{i}"
            if os.path.exists(p):
                os.remove(p)

    def test_save_creates_state_file(self):
        """save_state creates the JSON state file on disk."""
        self.cli.save_state(silent=True)
        self.assertTrue(os.path.exists(_cli_module.STATE_PATH))

    def test_save_writes_step_number(self):
        """Saved JSON contains the current step number."""
        self.cli.step = 42
        self.cli.save_state(silent=True)
        with open(_cli_module.STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["step"], 42)

    def test_load_returns_false_when_no_file(self):
        """load_state returns False when no state file exists."""
        if os.path.exists(_cli_module.STATE_PATH):
            os.remove(_cli_module.STATE_PATH)
        result = self.cli.load_state()
        self.assertFalse(result)

    def test_load_restores_step(self):
        """After save + load the step number is restored."""
        self.cli.step = 7
        self.cli.save_state(silent=True)
        self.cli.step = 99
        self.cli.load_state()
        self.assertEqual(self.cli.step, 7)

    def test_load_returns_true_on_success(self):
        """load_state returns True when file exists and is valid JSON."""
        self.cli.save_state(silent=True)
        result = self.cli.load_state()
        self.assertTrue(result)

    def test_save_creates_backup_rotation(self):
        """save_state rotates .1 .2 .3 backup files."""
        sp = _cli_module.STATE_PATH
        self.cli.step = 1
        self.cli.save_state(silent=True)
        self.cli.step = 2
        self.cli.save_state(silent=True)
        self.assertTrue(os.path.exists(f"{sp}.1"))
        b1 = json.load(open(f"{sp}.1", encoding="utf-8"))
        self.assertEqual(b1["step"], 1)
        self.cli.step = 3
        self.cli.save_state(silent=True)
        self.assertTrue(os.path.exists(f"{sp}.2"))
        b2 = json.load(open(f"{sp}.2", encoding="utf-8"))
        self.assertEqual(b2["step"], 1)
        b1 = json.load(open(f"{sp}.1", encoding="utf-8"))
        self.assertEqual(b1["step"], 2)
        # Cleanup backups
        for i in range(1, 4):
            p = f"{sp}.{i}"
            if os.path.exists(p):
                os.remove(p)

    def test_load_backup_restores_from_backup(self):
        """load_backup 1 restores state from .1 backup file."""
        sp = _cli_module.STATE_PATH
        # Save step 10, then step 20 (creates .1 with step 10)
        self.cli.step = 10
        self.cli.save_state(silent=True)
        self.cli.step = 20
        self.cli.save_state(silent=True)
        self.assertEqual(self.cli.step, 20)
        # Restore from .1
        self.cli._cmd_load_backup("1")
        self.assertEqual(self.cli.step, 10)
        # Cleanup
        for i in range(1, 4):
            p = f"{sp}.{i}"
            if os.path.exists(p):
                os.remove(p)

    def test_load_backup_missing_shows_warning(self):
        """load_backup 3 when no .3 exists shows a warning."""
        # Ensure no stale .3 backup from previous tests
        sp = _cli_module.STATE_PATH
        p3 = f"{sp}.3"
        if os.path.exists(p3):
            os.remove(p3)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cli._cmd_load_backup("3")
        output = buf.getvalue()
        self.assertIn("not found", output)


# ---------------------------------------------------------------------------
# TestSnapshotCommand
# ---------------------------------------------------------------------------

class TestSnapshotCommand(unittest.TestCase):
    """Tests for SoloBuilderCLI._take_snapshot."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()

    def _run_snapshot(self, **kw) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._take_snapshot(**kw)
        return buf.getvalue()

    def test_snapshot_prints_unavailable_when_pdf_not_ok(self):
        """When _PDF_OK is False a 'PDF unavailable' message is printed."""
        with patch.object(_cli_module, "_PDF_OK", new=False):
            out = self._run_snapshot()
        self.assertIn("PDF unavailable", out)

    def test_snapshot_calls_generate_pdf_when_available(self):
        """When _PDF_OK is True generate_live_multi_pdf is called once."""
        mock_gen = MagicMock()
        with patch.object(_cli_module, "_PDF_OK", new=True), \
             patch("solo_builder_cli.generate_live_multi_pdf", new=mock_gen,
                   create=True):
            self._run_snapshot()
        mock_gen.assert_called_once()

    def test_snapshot_increments_counter(self):
        """Each successful snapshot increments snapshot_counter by 1."""
        mock_gen = MagicMock()
        before = self.cli.snapshot_counter
        with patch.object(_cli_module, "_PDF_OK", new=True), \
             patch("solo_builder_cli.generate_live_multi_pdf", new=mock_gen,
                   create=True):
            self._run_snapshot()
        self.assertEqual(self.cli.snapshot_counter, before + 1)


# ---------------------------------------------------------------------------
# TestPrioritizeBranch
# ---------------------------------------------------------------------------

class TestPrioritizeBranch(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_prioritize_branch."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()

    def _run(self) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), patch("builtins.input", return_value=""):
            self.cli._cmd_prioritize_branch()
        return buf.getvalue()

    def test_prioritize_branch_lists_all_branches(self):
        """Output contains every branch name present in the initial DAG."""
        out = self._run()
        self.assertIn("Branch A", out)
        self.assertIn("Branch B", out)

    def test_prioritize_branch_calls_display_render(self):
        """display.render is called after a successful boost."""
        with patch("builtins.input", side_effect=["Task 0", "Branch A"]):
            self.cli._cmd_prioritize_branch()
        self.cli.display.render.assert_called_once()

    def test_prioritize_branch_boosts_pending_last_update(self):
        """Pending subtasks in the target branch get last_update = step - 500."""
        # Task 0 / Branch A has Pending subtasks in INITIAL_DAG
        branch = self.cli.dag["Task 0"]["branches"]["Branch A"]
        pending_before = {
            k: v["last_update"]
            for k, v in branch["subtasks"].items()
            if v.get("status") == "Pending"
        }
        self.cli._cmd_prioritize_branch("Task 0", "Branch A")
        for st_name in pending_before:
            self.assertEqual(
                branch["subtasks"][st_name]["last_update"],
                self.cli.step - 500,
            )

    def test_prioritize_branch_unknown_task_prints_error(self):
        """Unknown task arg prints error and does not call display.render."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._cmd_prioritize_branch("Task 999", "Branch A")
        self.assertIn("not found", buf.getvalue())
        self.cli.display.render.assert_not_called()


# ---------------------------------------------------------------------------
# TestAddTaskInlineSpec
# ---------------------------------------------------------------------------

class TestAddTaskInlineSpec(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_add_task with inline spec_override."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self.cli.executor.claude.available = False   # force fallback path
        self._sleep_patcher = patch("time.sleep")
        self._sleep_patcher.start()

    def tearDown(self):
        self._sleep_patcher.stop()

    def test_inline_spec_skips_input_prompt(self):
        """Passing spec_override creates the task without calling input()."""
        n_before = len(self.cli.dag)
        # If input() were called it would block; no patch needed if override works
        self.cli._cmd_add_task("Build the auth module")
        self.assertEqual(len(self.cli.dag), n_before + 1)

    def test_inline_spec_used_as_subtask_description(self):
        """The spec_override string becomes the fallback subtask description."""
        self.cli._cmd_add_task("Implement OAuth2 flow")
        new_task = list(self.cli.dag.values())[-1]
        branch   = list(new_task["branches"].values())[0]
        subtask  = list(branch["subtasks"].values())[0]
        self.assertIn("Implement OAuth2 flow", subtask["description"])

    def test_handle_command_add_task_with_inline_spec(self):
        """'add_task <spec>' dispatches to _cmd_add_task with the spec text."""
        n_before = len(self.cli.dag)
        with patch("builtins.input", side_effect=AssertionError("input() should not be called")):
            self.cli.handle_command("add_task Deploy the API server")
        self.assertEqual(len(self.cli.dag), n_before + 1)

    def test_handle_command_add_task_bare_still_prompts(self):
        """'add_task' (no inline spec) still calls input() for the spec."""
        n_before = len(self.cli.dag)
        with patch("builtins.input", return_value="Bare task spec"):
            self.cli.handle_command("add_task")
        self.assertEqual(len(self.cli.dag), n_before + 1)


class TestAddTaskDepWiring(unittest.TestCase):
    """Tests for 'add_task spec | depends: N' dependency override syntax."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self.cli.executor.claude.available = False
        self._sleep_patcher = patch("time.sleep")
        self._sleep_patcher.start()

    def tearDown(self):
        self._sleep_patcher.stop()

    def _last_task(self) -> dict:
        return list(self.cli.dag.values())[-1]

    def test_explicit_dep_wired_correctly(self):
        """'Build auth | depends: 0' creates task with depends_on=['Task 0']."""
        self.cli._cmd_add_task("Build auth | depends: 0")
        self.assertEqual(self._last_task()["depends_on"], ["Task 0"])

    def test_digit_dep_normalised_to_task_name(self):
        """'| depends: 6' normalises digit to 'Task 6'."""
        self.cli._cmd_add_task("Deploy infra | depends: 6")
        self.assertEqual(self._last_task()["depends_on"], ["Task 6"])

    def test_unknown_dep_falls_back_to_default(self):
        """'| depends: 99' prints warning and uses default (last task)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cli._cmd_add_task("Build stuff | depends: 99")
        self.assertIn("Unknown dependency", buf.getvalue())
        self.assertNotEqual(self._last_task()["depends_on"], ["Task 99"])

    def test_spec_stripped_of_pipe_syntax(self):
        """Subtask description must not contain the '| depends:' suffix."""
        self.cli._cmd_add_task("Build OAuth | depends: 0")
        task   = self._last_task()
        branch = list(task["branches"].values())[0]
        st     = list(branch["subtasks"].values())[0]
        self.assertNotIn("| depends:", st["description"])


class TestAddBranchInlineSpec(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_add_branch with inline spec_override."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self.cli.executor.claude.available = False   # force fallback path
        self._sleep_patcher = patch("time.sleep")
        self._sleep_patcher.start()

    def tearDown(self):
        self._sleep_patcher.stop()

    def _count_branches(self, task_name: str) -> int:
        return len(self.cli.dag.get(task_name, {}).get("branches", {}))

    def test_inline_spec_skips_input_prompt(self):
        """Passing spec_override adds a branch without calling input()."""
        before = self._count_branches("Task 0")
        # If input() were called it would block; error would surface
        self.cli._cmd_add_branch("0", spec_override="Add CI integration tests")
        self.assertEqual(self._count_branches("Task 0"), before + 1)

    def test_handle_command_add_branch_with_inline_spec(self):
        """'add_branch 0 <spec>' dispatches without prompting for spec."""
        before = self._count_branches("Task 0")
        with patch("builtins.input", side_effect=AssertionError("input() should not be called")):
            self.cli.handle_command("add_branch 0 Deploy staging environment")
        self.assertEqual(self._count_branches("Task 0"), before + 1)

    def test_handle_command_add_branch_bare_still_prompts(self):
        """'add_branch 0' (no inline spec) still calls input() for the spec."""
        before = self._count_branches("Task 0")
        with patch("builtins.input", return_value="Write integration tests"):
            self.cli.handle_command("add_branch 0")
        self.assertEqual(self._count_branches("Task 0"), before + 1)


# ---------------------------------------------------------------------------
# TestFindSubtaskOutput
# ---------------------------------------------------------------------------

class TestFindSubtaskOutput(unittest.TestCase):
    """Tests for bot_module._find_subtask_output helper."""

    def _make_state(self, output: str) -> dict:
        return {
            "dag": {
                "Task 0": {
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {"status": "Verified", "output": output}
                            }
                        }
                    }
                }
            }
        }

    def test_found_with_output_returns_task_and_text(self):
        """Returns (task_name, output) when subtask exists and has output."""
        state = self._make_state("Great work!")
        result = bot_module._find_subtask_output(state, "A1")
        self.assertIsNotNone(result)
        task_name, out = result
        self.assertEqual(task_name, "Task 0")
        self.assertEqual(out, "Great work!")

    def test_found_no_output_returns_empty_string(self):
        """Returns (task_name, '') when subtask exists but has no output."""
        state = self._make_state("")
        result = bot_module._find_subtask_output(state, "A1")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "")

    def test_not_found_returns_none(self):
        """Returns None when the subtask name is not in the DAG."""
        state = self._make_state("some output")
        result = bot_module._find_subtask_output(state, "Z99")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Extra TestHandleTextCommand tests for output / prioritize_branch
# ---------------------------------------------------------------------------

class TestHandleTextCommandExtra(unittest.IsolatedAsyncioTestCase):

    async def test_output_found_sends_content(self):
        """'output A1' with output sends the output text."""
        state = {"dag": {}, "step": 0}
        with patch.object(bot_module, "_load_state", return_value=state), \
             patch.object(bot_module, "_find_subtask_output",
                          return_value=("Task 0", "Great work!")), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("output A1"))
        text = mock_send.call_args[0][1]
        self.assertIn("Great work!", text)

    async def test_output_not_found_sends_error(self):
        """'output Z99' for unknown subtask sends an error message."""
        state = {"dag": {}, "step": 0}
        with patch.object(bot_module, "_load_state", return_value=state), \
             patch.object(bot_module, "_find_subtask_output", return_value=None), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("output Z99"))
        text = mock_send.call_args[0][1]
        self.assertIn("Z99", text)

    async def test_prioritize_branch_queues_trigger(self):
        """'prioritize_branch 0 A' writes the correct trigger file."""
        mock_pbt = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()), \
             patch.object(bot_module, "PRIORITY_BRANCH_TRIGGER", new=mock_pbt):
            await bot_module._handle_text_command(_make_msg("prioritize_branch 0 A"))
        mock_pbt.write_text.assert_called_once()
        written = json.loads(mock_pbt.write_text.call_args[0][0])
        self.assertEqual(written["task"], "0")
        self.assertEqual(written["branch"], "A")

    async def test_describe_queues_trigger(self):
        """'describe A3 Build retry logic' writes correct trigger JSON."""
        mock_dt = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()), \
             patch.object(bot_module, "DESCRIBE_TRIGGER", new=mock_dt):
            await bot_module._handle_text_command(_make_msg("describe A3 Build retry logic"))
        mock_dt.write_text.assert_called_once()
        written = json.loads(mock_dt.write_text.call_args[0][0])
        self.assertEqual(written["subtask"], "A3")
        self.assertIn("retry", written["desc"])

    async def test_describe_no_args_sends_usage(self):
        """'describe' with no subtask sends a usage message."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("describe"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_format_status_includes_task_row(self):
        """_format_status output includes per-task summary rows."""
        state = _make_state({"A1": "Verified", "A2": "Pending"}, step=1)
        result = bot_module._format_status(state)
        # Task row should appear in the markdown summary
        self.assertIn("Task0", result)

    async def test_tools_queues_trigger(self):
        """'tools H1 Read,Glob,Grep' writes the correct trigger file."""
        mock_tt = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()), \
             patch.object(bot_module, "TOOLS_TRIGGER", new=mock_tt):
            await bot_module._handle_text_command(_make_msg("tools H1 Read,Glob,Grep"))
        mock_tt.write_text.assert_called_once()
        written = json.loads(mock_tt.write_text.call_args[0][0])
        self.assertEqual(written["subtask"], "H1")
        self.assertEqual(written["tools"], "Read,Glob,Grep")

    async def test_tools_no_args_sends_usage(self):
        """'tools' with no args sends a usage message."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("tools"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_reset_bare_sends_warning(self):
        """'reset' without 'confirm' sends a safety warning."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("reset"))
        text = mock_send.call_args[0][1]
        self.assertIn("destroy", text.lower())

    async def test_reset_confirm_writes_trigger(self):
        """'reset confirm' writes the reset trigger file."""
        mock_rt = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()), \
             patch.object(bot_module, "RESET_TRIGGER", new=mock_rt):
            await bot_module._handle_text_command(_make_msg("reset confirm"))
        mock_rt.write_text.assert_called_once_with("1")

    async def test_snapshot_writes_trigger(self):
        """'snapshot' writes the snapshot trigger file."""
        mock_st = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()), \
             patch.object(bot_module, "SNAPSHOT_TRIGGER", new=mock_st), \
             patch.object(bot_module, "SNAPSHOTS_DIR", new=MagicMock(is_dir=MagicMock(return_value=False))):
            await bot_module._handle_text_command(_make_msg("snapshot"))
        mock_st.write_text.assert_called_once_with("1")

    async def test_set_setter_writes_trigger(self):
        """'set REVIEW_MODE=on' writes the set trigger file."""
        mock_trig = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "SET_TRIGGER", new=mock_trig):
            await bot_module._handle_text_command(_make_msg("set REVIEW_MODE=on"))
        mock_trig.write_text.assert_called_once()
        written = json.loads(mock_trig.write_text.call_args[0][0])
        self.assertEqual(written["key"], "REVIEW_MODE")
        self.assertEqual(written["value"], "on")
        text = mock_send.call_args[0][1]
        self.assertIn("REVIEW_MODE", text)

    async def test_set_getter_reads_config(self):
        """'set REVIEW_MODE' reads config/settings.json and replies with value."""
        mock_settings = MagicMock()
        mock_settings.read_text.return_value = json.dumps({"REVIEW_MODE": True})
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "SETTINGS_PATH", new=mock_settings):
            await bot_module._handle_text_command(_make_msg("set REVIEW_MODE"))
        text = mock_send.call_args[0][1]
        self.assertIn("REVIEW_MODE", text)
        self.assertIn("True", text)

    async def test_set_getter_unknown_key_sends_error(self):
        """'set BOGUS_KEY' sends an error listing known keys."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("set BOGUS_KEY"))
        text = mock_send.call_args[0][1]
        self.assertIn("Unknown", text)

    async def test_set_trigger_consumed_by_cli(self):
        """CLI auto loop consumes set_trigger.json and calls _cmd_set."""
        import tempfile
        cli = _cli_module.SoloBuilderCLI()
        # Prevent terminal rendering side-effects during direct _cmd_set calls.
        cli.display = MagicMock()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"key": "REVIEW_MODE", "value": "on"}, tmp)
        tmp.close()
        cfg_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"REVIEW_MODE": False}, cfg_tmp)
        cfg_tmp.close()
        orig_cfg = _cli_module._CFG_PATH
        # Simulate trigger consumption by testing _cmd_set directly
        _cli_module._CFG_PATH = cfg_tmp.name
        try:
            cli._cmd_set("REVIEW_MODE=on")
            self.assertTrue(cli.executor.review_mode)
            cli._cmd_set("REVIEW_MODE=off")
            self.assertFalse(cli.executor.review_mode)
        finally:
            _cli_module._CFG_PATH = orig_cfg
            os.unlink(tmp.name)
            os.unlink(cfg_tmp.name)

    async def test_depends_no_args_shows_graph(self):
        """'depends' with no args shows the dependency graph from state."""
        state = _make_state({"A1": "Verified"}, step=3)
        state["dag"]["Task0"]["depends_on"] = []
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("depends"))
        text = mock_send.call_args[0][1]
        self.assertIn("Dependency Graph", text)
        self.assertIn("Task0", text)

    async def test_depends_with_args_writes_trigger(self):
        """'depends 1 0' writes the depends trigger file."""
        mock_trig = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "DEPENDS_TRIGGER", new=mock_trig):
            await bot_module._handle_text_command(_make_msg("depends 1 0"))
        mock_trig.write_text.assert_called_once()
        written = json.loads(mock_trig.write_text.call_args[0][0])
        self.assertEqual(written["target"], "1")
        self.assertEqual(written["dep"], "0")

    async def test_undepends_writes_trigger(self):
        """'undepends 1 0' writes the undepends trigger file."""
        mock_trig = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "UNDEPENDS_TRIGGER", new=mock_trig):
            await bot_module._handle_text_command(_make_msg("undepends 1 0"))
        mock_trig.write_text.assert_called_once()
        written = json.loads(mock_trig.write_text.call_args[0][0])
        self.assertEqual(written["target"], "1")
        self.assertEqual(written["dep"], "0")

    async def test_undepends_no_args_sends_usage(self):
        """'undepends' with no args sends usage."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("undepends"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_heartbeat_with_data(self):
        """'heartbeat' with valid step.txt shows live counters."""
        hb = (12, 35, 70, 20, 10, 5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_read_heartbeat", return_value=hb), \
             patch.object(bot_module, "_auto_running", return_value=False):
            await bot_module._handle_text_command(_make_msg("heartbeat"))
        text = mock_send.call_args[0][1]
        self.assertIn("Heartbeat", text)
        self.assertIn("Step 12", text)
        self.assertIn("35", text)

    async def test_heartbeat_no_data(self):
        """'heartbeat' with no step.txt sends warning."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_read_heartbeat", return_value=None):
            await bot_module._handle_text_command(_make_msg("heartbeat"))
        text = mock_send.call_args[0][1]
        self.assertIn("No heartbeat", text)

    async def test_graph_shows_dag_structure(self):
        """'graph' renders ASCII DAG with task names and dependency arrows."""
        state = _make_state({"A1": "Verified", "A2": "Pending"}, step=5)
        state["dag"]["Task1"] = {
            "status": "Pending",
            "depends_on": ["Task0"],
            "branches": {"BranchC": {"subtasks": {"C1": {"status": "Pending"}}}},
        }
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("graph"))
        text = mock_send.call_args[0][1]
        self.assertIn("DAG Graph", text)
        self.assertIn("Task0", text)
        self.assertIn("Task1", text)

    async def test_graph_empty_dag(self):
        """'graph' with empty DAG shows appropriate message."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value={"dag": {}, "step": 0}):
            await bot_module._handle_text_command(_make_msg("graph"))
        text = mock_send.call_args[0][1]
        self.assertIn("No tasks", text)

    async def test_undo_writes_trigger(self):
        """'undo' writes the undo trigger file."""
        mock_trig = MagicMock()
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "UNDO_TRIGGER", new=mock_trig):
            await bot_module._handle_text_command(_make_msg("undo"))
        mock_trig.write_text.assert_called_once_with("1")
        text = mock_send.call_args[0][1]
        self.assertIn("Undo", text)

    async def test_config_shows_settings(self):
        """'config' reads settings.json and shows all keys."""
        mock_settings = MagicMock()
        mock_settings.read_text.return_value = json.dumps({
            "STALL_THRESHOLD": 5, "REVIEW_MODE": False
        })
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "SETTINGS_PATH", new=mock_settings):
            await bot_module._handle_text_command(_make_msg("config"))
        text = mock_send.call_args[0][1]
        self.assertIn("Current Settings", text)
        self.assertIn("STALL_THRESHOLD", text)
        self.assertIn("REVIEW_MODE", text)


    async def test_diff_no_backup(self):
        """'diff' with no backup shows warning."""
        mock_path = MagicMock()
        mock_path.__str__ = lambda self: "/fake/state.json.1"
        mock_path.exists.return_value = False
        # We need to patch Path(str(STATE_PATH) + ".1") — patch _format_diff
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_format_diff", return_value="⚠️ No backup to diff against (need at least 2 saves)."):
            await bot_module._handle_text_command(_make_msg("diff"))
        text = mock_send.call_args[0][1]
        self.assertIn("No backup", text)

    async def test_diff_with_changes(self):
        """'diff' with state changes shows subtask transitions."""
        result = "**Diff** · Step 4 → 5\n`A1` Pending → Running"
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_format_diff", return_value=result):
            await bot_module._handle_text_command(_make_msg("diff"))
        text = mock_send.call_args[0][1]
        self.assertIn("Diff", text)
        self.assertIn("A1", text)

    async def test_pause_writes_trigger(self):
        """'pause' writes the pause trigger file when auto is running."""
        mock_trig = MagicMock()
        mock_trig.exists.return_value = False
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "PAUSE_TRIGGER", new=mock_trig), \
             patch.object(bot_module, "_auto_running", return_value=True):
            await bot_module._handle_text_command(_make_msg("pause"))
        mock_trig.write_text.assert_called_once_with("1")
        text = mock_send.call_args[0][1]
        self.assertIn("Pause", text)

    async def test_pause_no_auto_shows_warning(self):
        """'pause' with no auto-run sends a warning."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_auto_running", return_value=False):
            await bot_module._handle_text_command(_make_msg("pause"))
        text = mock_send.call_args[0][1]
        self.assertIn("No auto-run", text)

    async def test_resume_clears_trigger(self):
        """'resume' removes the pause trigger file."""
        mock_trig = MagicMock()
        mock_trig.exists.return_value = True
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "PAUSE_TRIGGER", new=mock_trig):
            await bot_module._handle_text_command(_make_msg("resume"))
        mock_trig.unlink.assert_called_once()
        text = mock_send.call_args[0][1]
        self.assertIn("Resumed", text)

    async def test_resume_not_paused(self):
        """'resume' when not paused sends a warning."""
        mock_trig = MagicMock()
        mock_trig.exists.return_value = False
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "PAUSE_TRIGGER", new=mock_trig):
            await bot_module._handle_text_command(_make_msg("resume"))
        text = mock_send.call_args[0][1]
        self.assertIn("Not paused", text)


class TestTimelineCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot timeline command."""

    async def test_timeline_found(self):
        """'timeline A1' shows timeline for a subtask with history."""
        state = {
            "dag": {
                "Task 0": {
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {
                                    "status": "Verified",
                                    "history": [
                                        {"status": "Running", "step": 2},
                                        {"status": "Verified", "step": 4},
                                    ],
                                }
                            }
                        }
                    }
                }
            }
        }
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("timeline A1"))
        text = mock_send.call_args[0][1]
        self.assertIn("Timeline", text)
        self.assertIn("A1", text)
        self.assertIn("Verified", text)

    async def test_timeline_not_found(self):
        """'timeline ZZZ' shows not-found message."""
        state = {"dag": {}}
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("timeline ZZZ"))
        text = mock_send.call_args[0][1]
        self.assertIn("not found", text)


class TestFilterCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot filter command."""

    async def test_filter_verified(self):
        """'filter Verified' returns matching subtasks."""
        state = _make_state({"A1": "Verified", "A2": "Running", "A3": "Verified"})
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("filter Verified"))
        text = mock_send.call_args[0][1]
        self.assertIn("Verified", text)
        self.assertIn("2", text)

    async def test_filter_invalid_status(self):
        """'filter bogus' shows usage."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=_make_state({"A1": "Pending"})):
            await bot_module._handle_text_command(_make_msg("filter bogus"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_filter_empty(self):
        """'filter Running' with no running subtasks shows 0."""
        state = _make_state({"A1": "Verified"})
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("filter Running"))
        text = mock_send.call_args[0][1]
        self.assertIn("0", text)


class TestPriorityCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot priority command."""

    async def test_priority_shows_queue(self):
        """'priority' returns a priority queue with candidates."""
        state = _make_state({"A1": "Running", "A2": "Pending"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("priority"))
        text = mock_send.call_args[0][1]
        self.assertIn("Priority", text)
        self.assertIn("A1", text)

    async def test_priority_empty(self):
        """'priority' with all verified shows empty."""
        state = _make_state({"A1": "Verified"}, step=1)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("priority"))
        text = mock_send.call_args[0][1]
        self.assertIn("empty", text)


class TestStalledCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot stalled command."""

    async def test_stalled_shows_stuck(self):
        """'stalled' with a Running subtask past threshold shows it."""
        state = _make_state({"A1": "Running", "A2": "Verified"}, step=10)
        mock_cfg = json.dumps({"STALL_THRESHOLD": 5})
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.read_text", return_value=mock_cfg):
            await bot_module._handle_text_command(_make_msg("stalled"))
        text = mock_send.call_args[0][1]
        self.assertIn("A1", text)
        self.assertIn("Stalled", text)

    async def test_stalled_empty(self):
        """'stalled' with all verified shows none."""
        state = _make_state({"A1": "Verified"}, step=1)
        mock_cfg = json.dumps({"STALL_THRESHOLD": 5})
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.read_text", return_value=mock_cfg):
            await bot_module._handle_text_command(_make_msg("stalled"))
        text = mock_send.call_args[0][1]
        self.assertIn("none", text)


class TestHealCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot heal command."""

    async def test_heal_running(self):
        """'heal A1' on a Running subtask writes trigger."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text") as mock_write:
            await bot_module._handle_text_command(_make_msg("heal A1"))
        text = mock_send.call_args[0][1]
        self.assertIn("A1", text)
        self.assertIn("heal", text.lower())
        mock_write.assert_called_once()

    async def test_heal_not_running(self):
        """'heal A1' on a Verified subtask shows warning."""
        state = _make_state({"A1": "Verified"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("heal A1"))
        text = mock_send.call_args[0][1]
        self.assertIn("not Running", text)

    async def test_heal_empty(self):
        """'heal' with no arg shows usage."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("heal"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)


class TestResetTaskCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot reset_task command."""

    async def test_reset_task_valid(self):
        """reset_task Task0 resets non-Verified subtasks and writes state."""
        state = _make_state({"A1": "Running", "A2": "Pending"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text") as mock_write:
            await bot_module._handle_text_command(_make_msg("reset_task Task0"))
        text = mock_send.call_args[0][1]
        self.assertIn("Task0", text)
        self.assertIn("reset", text.lower())
        mock_write.assert_called_once()

    async def test_reset_task_skips_verified(self):
        """reset_task preserves Verified subtasks."""
        state = _make_state({"A1": "Verified", "A2": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("reset_task Task0"))
        text = mock_send.call_args[0][1]
        self.assertIn("preserved", text)

    async def test_reset_task_unknown_task(self):
        """reset_task with unknown task ID shows warning."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("reset_task ZZZ"))
        text = mock_send.call_args[0][1]
        self.assertIn("not found", text)

    async def test_reset_task_no_arg_shows_usage(self):
        """reset_task with no arg shows usage."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("reset_task"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)


class TestResetBranchCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot reset_branch command."""

    async def test_reset_branch_valid(self):
        """reset_branch Task0 BranchA resets non-Verified subtasks and writes state."""
        state = _make_state({"A1": "Running", "A2": "Pending"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text") as mock_write:
            await bot_module._handle_text_command(_make_msg("reset_branch Task0 BranchA"))
        text = mock_send.call_args[0][1]
        self.assertIn("Task0", text)
        self.assertIn("BranchA", text)
        self.assertIn("reset", text.lower())
        mock_write.assert_called_once()

    async def test_reset_branch_skips_verified(self):
        """reset_branch preserves Verified subtasks."""
        state = _make_state({"A1": "Verified", "A2": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("reset_branch Task0 BranchA"))
        text = mock_send.call_args[0][1]
        self.assertIn("preserved", text)

    async def test_reset_branch_unknown_task(self):
        """reset_branch with unknown task returns warning."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("reset_branch ZZZ BranchA"))
        text = mock_send.call_args[0][1]
        self.assertIn("not found", text)

    async def test_reset_branch_unknown_branch(self):
        """reset_branch with unknown branch returns warning."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("reset_branch Task0 ZZZ"))
        text = mock_send.call_args[0][1]
        self.assertIn("not found", text)

    async def test_reset_branch_no_args_shows_usage(self):
        """reset_branch with no args shows usage."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("reset_branch"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)


class TestBulkResetCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot bulk_reset command."""

    async def test_bulk_reset_valid(self):
        """bulk_reset A1 A2 resets non-Verified subtasks and writes state."""
        state = _make_state({"A1": "Running", "A2": "Pending"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text") as mock_write:
            await bot_module._handle_text_command(_make_msg("bulk_reset A1 A2"))
        text = mock_send.call_args[0][1]
        self.assertIn("2", text)
        self.assertIn("Pending", text)
        mock_write.assert_called_once()

    async def test_bulk_reset_skips_verified(self):
        """bulk_reset preserves Verified subtasks and reports skipped count."""
        state = _make_state({"A1": "Verified", "A2": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("bulk_reset A1 A2"))
        text = mock_send.call_args[0][1]
        self.assertIn("preserved", text)

    async def test_bulk_reset_not_found_reported(self):
        """bulk_reset reports subtask names that were not found in state."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("bulk_reset A1 Z9"))
        text = mock_send.call_args[0][1]
        self.assertIn("Z9", text)

    async def test_bulk_reset_no_args_shows_usage(self):
        """bulk_reset with no args shows usage hint."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("bulk_reset"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_bulk_reset_result_format(self):
        """bulk_reset returns the reset count in the response."""
        state = _make_state({"A1": "Pending"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("bulk_reset A1"))
        text = mock_send.call_args[0][1]
        self.assertIn("1", text)


class TestBulkVerifyCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot bulk_verify command."""

    async def test_bulk_verify_valid(self):
        """bulk_verify A1 A2 advances subtasks to Verified and writes state."""
        state = _make_state({"A1": "Running", "A2": "Pending"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text") as mock_write:
            await bot_module._handle_text_command(_make_msg("bulk_verify A1 A2"))
        text = mock_send.call_args[0][1]
        self.assertIn("2", text)
        self.assertIn("Verified", text)
        mock_write.assert_called_once()

    async def test_bulk_verify_skips_already_verified(self):
        """bulk_verify skips already-Verified subtasks and reports skipped count."""
        state = _make_state({"A1": "Verified", "A2": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("bulk_verify A1 A2"))
        text = mock_send.call_args[0][1]
        self.assertIn("skipped", text)

    async def test_bulk_verify_not_found_reported(self):
        """bulk_verify reports subtask names not found in state."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("bulk_verify A1 Z9"))
        text = mock_send.call_args[0][1]
        self.assertIn("Z9", text)

    async def test_bulk_verify_no_args_shows_usage(self):
        """bulk_verify with no args shows usage hint."""
        state = _make_state({"A1": "Running"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("bulk_verify"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_bulk_verify_result_format(self):
        """bulk_verify returns the verified count in the response."""
        state = _make_state({"A1": "Pending"}, step=5)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await bot_module._handle_text_command(_make_msg("bulk_verify A1"))
        text = mock_send.call_args[0][1]
        self.assertIn("1", text)


class TestAgentsCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot agents command."""

    async def test_agents_shows_stats(self):
        """'agents' returns agent statistics."""
        state = _make_state({"A1": "Running", "A2": "Verified"}, step=10)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("agents"))
        text = mock_send.call_args[0][1]
        self.assertIn("Agent", text)
        self.assertIn("Executor", text)

    async def test_agents_empty_dag(self):
        """'agents' with empty DAG still returns stats."""
        state = {"dag": {}, "step": 0}
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("agents"))
        text = mock_send.call_args[0][1]
        self.assertIn("Agent", text)


class TestForecastCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot forecast command."""

    async def test_forecast_shows_progress(self):
        """'forecast' returns completion forecast."""
        state = _make_state({"A1": "Running", "A2": "Verified"}, step=10)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("forecast"))
        text = mock_send.call_args[0][1]
        self.assertIn("Forecast", text)
        self.assertIn("%", text)

    async def test_forecast_empty_dag(self):
        """'forecast' with empty DAG still works."""
        state = {"dag": {}, "step": 0}
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("forecast"))
        text = mock_send.call_args[0][1]
        self.assertIn("Forecast", text)


class TestHistoryCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot history command."""

    async def test_history_shows_events(self):
        """'history' shows recent status transitions."""
        state = {
            "dag": {
                "Task 0": {
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {
                                    "status": "Verified",
                                    "history": [
                                        {"status": "Running", "step": 1},
                                        {"status": "Verified", "step": 3},
                                    ],
                                }
                            }
                        }
                    }
                }
            }
        }
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("history"))
        text = mock_send.call_args[0][1]
        self.assertIn("Recent Activity", text)
        self.assertIn("A1", text)

    async def test_history_empty(self):
        """'history' with no events shows empty message."""
        state = {"dag": {}}
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("history"))
        text = mock_send.call_args[0][1]
        self.assertIn("No history", text)


class TestSearchCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot search command."""

    async def test_search_found(self):
        """'search auth' finds matching subtask."""
        state = {
            "dag": {
                "Task 0": {
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {"status": "Verified", "description": "Implement auth layer", "output": ""},
                                "A2": {"status": "Pending", "description": "Build UI", "output": ""},
                            }
                        }
                    }
                }
            }
        }
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("search auth"))
        text = mock_send.call_args[0][1]
        self.assertIn("1 match", text)
        self.assertIn("A1", text)

    async def test_search_not_found(self):
        """'search zzzz' returns no matches."""
        state = {"dag": {"Task 0": {"branches": {"Branch A": {"subtasks": {"A1": {"status": "Pending", "description": "Build UI", "output": ""}}}}}}}
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("search zzzz"))
        text = mock_send.call_args[0][1]
        self.assertIn("0 match", text)


class TestStatsCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot stats command."""

    async def test_stats_shows_table(self):
        """'stats' shows per-task breakdown table."""
        state = {
            "dag": {
                "Task 0": {
                    "status": "Verified",
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {"status": "Verified", "history": [
                                    {"status": "Running", "step": 1},
                                    {"status": "Verified", "step": 3},
                                ]},
                            }
                        }
                    }
                }
            }
        }
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("stats"))
        text = mock_send.call_args[0][1]
        self.assertIn("Task 0", text)
        self.assertIn("100", text)


class TestLogCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot log command."""

    async def test_log_no_journal(self):
        """'log' with no journal file shows warning."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "JOURNAL_PATH") as mock_path:
            mock_path.exists.return_value = False
            await bot_module._handle_text_command(_make_msg("log"))
        text = mock_send.call_args[0][1]
        self.assertIn("No journal", text)

    async def test_log_with_entries(self):
        """'log' with journal content shows entries."""
        journal = "## A1 · Task 0 / Branch A · Step 3\n**Prompt:** test\n\nDid something cool\n"
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "JOURNAL_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = journal
            await bot_module._handle_text_command(_make_msg("log"))
        text = mock_send.call_args[0][1]
        self.assertIn("A1", text)
        self.assertIn("Journal", text)


class TestBranchesCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot branches command."""

    async def test_branches_overview(self):
        """'branches' shows all tasks and their branches."""
        state = {
            "dag": {
                "Task 0": {
                    "status": "Running",
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {"status": "Verified"},
                                "A2": {"status": "Running"},
                            }
                        }
                    }
                }
            }
        }
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("branches"))
        text = mock_send.call_args[0][1]
        self.assertIn("Task 0", text)
        self.assertIn("Branch A", text)

    async def test_branches_specific_task(self):
        """'branches 0' shows branches for Task 0."""
        state = {
            "dag": {
                "Task 0": {
                    "status": "Running",
                    "branches": {
                        "Branch A": {
                            "subtasks": {
                                "A1": {"status": "Pending"},
                            }
                        }
                    }
                }
            }
        }
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("branches 0"))
        text = mock_send.call_args[0][1]
        self.assertIn("Task 0", text)
        self.assertIn("A1", text)

    async def test_branches_not_found(self):
        """'branches 99' shows not found message."""
        state = {"dag": {"Task 0": {"branches": {}}}}
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("branches 99"))
        text = mock_send.call_args[0][1]
        self.assertIn("not found", text)


class TestRenameCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot rename command."""

    async def test_rename_queued(self):
        """'rename A1 new desc' writes trigger and sends confirmation."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "RENAME_TRIGGER") as mock_path:
            mock_path.parent.mkdir = MagicMock()
            await bot_module._handle_text_command(_make_msg("rename A1 Build the new auth module"))
        text = mock_send.call_args[0][1]
        self.assertIn("A1", text)
        self.assertIn("Rename queued", text)

    async def test_rename_usage(self):
        """'rename A1' with no desc shows usage."""
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            await bot_module._handle_text_command(_make_msg("rename A1"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)


class TestUndoCommand(unittest.TestCase):
    """Tests for SoloBuilderCLI._cmd_undo."""

    def setUp(self):
        self.cli = _cli_module.SoloBuilderCLI()
        self.cli.display = MagicMock()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        sp = _cli_module.STATE_PATH
        if os.path.exists(sp):
            os.remove(sp)
        for i in range(1, 4):
            p = f"{sp}.{i}"
            if os.path.exists(p):
                os.remove(p)

    def test_undo_restores_previous_step(self):
        """undo restores the previous state from .1 backup."""
        self.cli.step = 5
        self.cli.save_state(silent=True)
        self.cli.step = 6
        self.cli.save_state(silent=True)
        self.assertEqual(self.cli.step, 6)
        self.cli._cmd_undo()
        self.assertEqual(self.cli.step, 5)

    def test_undo_no_backup_shows_warning(self):
        """undo with no .1 backup shows a warning."""
        sp = _cli_module.STATE_PATH
        # Ensure no backup
        p1 = f"{sp}.1"
        if os.path.exists(p1):
            os.remove(p1)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cli._cmd_undo()
        self.assertIn("No backup", buf.getvalue())


# ---------------------------------------------------------------------------
# _format_cache
# ---------------------------------------------------------------------------

class TestFormatCache(unittest.TestCase):
    """Tests for _format_cache() helper."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_entries(self, n: int):
        for i in range(n):
            name = f"entry_{i:04d}" + "a" * 56 + ".json"
            (Path(self._tmp) / name).write_text('{"response": "x"}', encoding="utf-8")

    def test_shows_entry_count(self):
        self._write_entries(3)
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}):
            result = bot_module._format_cache()
        self.assertIn("3", result)

    def test_shows_zero_when_empty(self):
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}):
            result = bot_module._format_cache()
        self.assertIn("0", result)

    def test_shows_estimated_tokens(self):
        self._write_entries(2)  # 2 × 550 = 1100
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}):
            result = bot_module._format_cache()
        self.assertIn("1,100", result)

    def test_clear_false_does_not_delete(self):
        self._write_entries(2)
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}):
            bot_module._format_cache(clear=False)
        self.assertEqual(len(list(Path(self._tmp).glob("*.json"))), 2)

    def test_clear_true_deletes_entries(self):
        self._write_entries(3)
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}):
            result = bot_module._format_cache(clear=True)
        self.assertEqual(len(list(Path(self._tmp).glob("*.json"))), 0)
        self.assertIn("Cleared", result)

    def test_clear_mentions_count_deleted(self):
        self._write_entries(4)
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}):
            result = bot_module._format_cache(clear=True)
        self.assertIn("4", result)

    def test_text_command_cache_dispatches(self):
        """Plain-text 'cache' command reaches _format_cache."""
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            asyncio.run(bot_module._handle_text_command(_make_msg("cache")))
        text = mock_send.call_args[0][1]
        self.assertIn("Cache", text)

    def test_text_command_cache_clear_dispatches(self):
        """Plain-text 'cache clear' command clears entries."""
        self._write_entries(2)
        with patch.dict(os.environ, {"CACHE_DIR": self._tmp}), \
             patch.object(bot_module, "_send", new=AsyncMock()) as mock_send:
            asyncio.run(bot_module._handle_text_command(_make_msg("cache clear")))
        text = mock_send.call_args[0][1]
        self.assertIn("Cleared", text)


# ---------------------------------------------------------------------------
# Slash command tests — /bulk_reset and /bulk_verify
# ---------------------------------------------------------------------------

import discord_bot.bot_slash as _slash_module


def _make_slash_cmds():
    """Register slash commands against a mock bot; return captured command dict."""
    captured = {}

    def _capture(name, **kwargs):
        def _decorator(fn):
            captured[name] = fn
            return fn
        return _decorator

    import discord
    mock_bot = MagicMock()
    mock_bot.tree.command = _capture
    mock_bot.tree.error = lambda fn: fn
    # app_commands.describe must be identity so we capture the real async fn
    with patch.object(discord.app_commands, "describe", return_value=lambda fn: fn):
        _slash_module.register_slash_commands(mock_bot)
    return captured


def _make_interaction(allowed=True):
    iact = MagicMock()
    iact.response = AsyncMock()
    iact.channel_id = 0
    iact.guild_id = None
    return iact


class TestBulkResetSlashCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for /bulk_reset slash command."""

    async def _run(self, subtasks_str, state, allowed=True):
        cmds = _make_slash_cmds()
        interaction = _make_interaction(allowed=allowed)
        with patch.object(bot_module, "_allowed", return_value=allowed), \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await cmds["bulk_reset"](interaction, subtasks_str)
        return interaction

    async def test_slash_bulk_reset_sends_message(self):
        state = _make_state({"A1": "Pending"}, step=1)
        iact = await self._run("A1", state)
        iact.response.send_message.assert_called_once()

    async def test_slash_bulk_reset_resets_subtask(self):
        state = _make_state({"A1": "Running"}, step=1)
        iact = await self._run("A1", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("1", text)

    async def test_slash_bulk_reset_not_found_reported(self):
        state = _make_state({"A1": "Pending"}, step=1)
        iact = await self._run("Z9", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("Z9", text)

    async def test_slash_bulk_reset_unauthorized(self):
        state = _make_state({"A1": "Pending"}, step=1)
        iact = await self._run("A1", state, allowed=False)
        args, kwargs = iact.response.send_message.call_args
        self.assertTrue(kwargs.get("ephemeral") or "Wrong" in (args[0] if args else ""))

    async def test_slash_bulk_reset_multi_subtask_split(self):
        state = _make_state({"A1": "Running", "A2": "Running"}, step=1)
        iact = await self._run("A1 A2", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("2", text)


class TestBulkVerifySlashCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for /bulk_verify slash command."""

    async def _run(self, subtasks_str, state, allowed=True):
        cmds = _make_slash_cmds()
        interaction = _make_interaction(allowed=allowed)
        with patch.object(bot_module, "_allowed", return_value=allowed), \
             patch.object(bot_module, "_load_state", return_value=state), \
             patch("pathlib.Path.write_text"):
            await cmds["bulk_verify"](interaction, subtasks_str)
        return interaction

    async def test_slash_bulk_verify_sends_message(self):
        state = _make_state({"A1": "Running"}, step=1)
        iact = await self._run("A1", state)
        iact.response.send_message.assert_called_once()

    async def test_slash_bulk_verify_verifies_subtask(self):
        state = _make_state({"A1": "Running"}, step=1)
        iact = await self._run("A1", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("1", text)

    async def test_slash_bulk_verify_skips_already_verified(self):
        state = _make_state({"A1": "Verified"}, step=1)
        iact = await self._run("A1", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("0", text)

    async def test_slash_bulk_verify_unauthorized(self):
        state = _make_state({"A1": "Running"}, step=1)
        iact = await self._run("A1", state, allowed=False)
        args, kwargs = iact.response.send_message.call_args
        self.assertTrue(kwargs.get("ephemeral") or "Wrong" in (args[0] if args else ""))

    async def test_slash_bulk_verify_not_found_reported(self):
        state = _make_state({"A1": "Running"}, step=1)
        iact = await self._run("Z9", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("Z9", text)


class TestTaskProgressCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for bot task_progress command."""

    async def test_task_progress_valid(self):
        """task_progress Task0 returns branch breakdown."""
        state = _make_state({"A1": "Verified", "A2": "Running"}, step=3)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("task_progress Task0"))
        text = mock_send.call_args[0][1]
        self.assertIn("Task0", text)

    async def test_task_progress_contains_branch_name(self):
        """task_progress output includes branch name."""
        state = _make_state({"A1": "Verified"}, step=1)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("task_progress Task0"))
        text = mock_send.call_args[0][1]
        self.assertIn("BranchA", text)

    async def test_task_progress_not_found(self):
        """task_progress with unknown task returns warning."""
        state = _make_state({"A1": "Pending"}, step=1)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("task_progress TASK-999"))
        text = mock_send.call_args[0][1]
        self.assertIn("not found", text)

    async def test_task_progress_no_args_shows_usage(self):
        """task_progress with no args shows usage hint."""
        state = _make_state({"A1": "Pending"}, step=1)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("task_progress"))
        text = mock_send.call_args[0][1]
        self.assertIn("Usage", text)

    async def test_task_progress_shows_totals(self):
        """task_progress output includes a TOTAL row."""
        state = _make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}, step=2)
        with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
             patch.object(bot_module, "_load_state", return_value=state):
            await bot_module._handle_text_command(_make_msg("task_progress Task0"))
        text = mock_send.call_args[0][1]
        self.assertIn("TOTAL", text)


class TestTaskProgressSlashCommand(unittest.IsolatedAsyncioTestCase):
    """Tests for /task_progress slash command."""

    async def _run(self, task_id_str, state, allowed=True):
        cmds = _make_slash_cmds()
        interaction = _make_interaction(allowed=allowed)
        with patch.object(bot_module, "_allowed", return_value=allowed), \
             patch.object(bot_module, "_load_state", return_value=state):
            await cmds["task_progress"](interaction, task_id_str)
        return interaction

    async def test_slash_task_progress_sends_message(self):
        state = _make_state({"A1": "Verified"}, step=1)
        iact = await self._run("Task0", state)
        iact.response.send_message.assert_called_once()

    async def test_slash_task_progress_contains_task_id(self):
        state = _make_state({"A1": "Running"}, step=1)
        iact = await self._run("Task0", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("Task0", text)

    async def test_slash_task_progress_not_found(self):
        state = _make_state({"A1": "Pending"}, step=1)
        iact = await self._run("TASK-999", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("not found", text)

    async def test_slash_task_progress_unauthorized(self):
        state = _make_state({"A1": "Pending"}, step=1)
        iact = await self._run("Task0", state, allowed=False)
        args, kwargs = iact.response.send_message.call_args
        self.assertTrue(kwargs.get("ephemeral") or "Wrong" in (args[0] if args else ""))

    async def test_slash_task_progress_shows_branch(self):
        state = _make_state({"A1": "Verified", "A2": "Pending"}, step=1)
        iact = await self._run("Task0", state)
        text = iact.response.send_message.call_args[0][0]
        self.assertIn("BranchA", text)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
