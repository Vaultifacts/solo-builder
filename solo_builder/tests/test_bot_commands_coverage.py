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


if __name__ == "__main__":
    unittest.main()
