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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
