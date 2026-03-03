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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
