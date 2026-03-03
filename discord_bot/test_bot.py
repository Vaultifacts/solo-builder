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
        self.assertIn("2  ▶ 0", result)

    def test_mixed_statuses(self):
        state = _make_state({"A1": "Verified", "A2": "Running", "A3": "Pending"}, step=3)
        result = bot_module._format_status(state)
        self.assertIn("1  ▶ 1", result)
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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
