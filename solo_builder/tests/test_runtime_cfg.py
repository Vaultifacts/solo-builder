"""Unit tests for _cmd_set / _runtime_cfg synchronization (TASK-331 / TD-ARCH-001 Phase 2c).

Verifies that calling _cmd_set(key=value) updates self._runtime_cfg and the
appropriate live object attributes (executor, healer, etc.).
"""
import sys
import types
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commands.dispatcher import DispatcherMixin


# ── Minimal host object that satisfies all _cmd_set attribute accesses ────────

def _make_host():
    """Return a minimal DispatcherMixin instance wired with fake sub-objects."""
    host = DispatcherMixin.__new__(DispatcherMixin)

    host._runtime_cfg = {
        "STALL_THRESHOLD":     5,
        "SNAPSHOT_INTERVAL":   10,
        "VERBOSITY":           "INFO",
        "EXEC_VERIFY_PROB":    0.8,
        "AUTO_STEP_DELAY":     0.4,
        "AUTO_SAVE_INTERVAL":  5,
        "CLAUDE_ALLOWED_TOOLS": "",
        "WEBHOOK_URL":         "",
    }

    executor = MagicMock()
    executor.verify_prob = 0.8
    executor.review_mode = False
    executor.anthropic.max_tokens = 4096
    executor.anthropic.model = "claude-sonnet-4-6"
    executor.claude.available = True
    executor.claude.allowed_tools = ""
    host.executor = executor

    host.healer  = MagicMock()
    host.planner = MagicMock()
    host.display = MagicMock()
    host.dag         = {}
    host.memory_store = {}
    host.step        = 0
    host.alerts      = []
    host.meta        = MagicMock()
    host.meta.forecast.return_value = "N/A"

    host._persist_setting = MagicMock()

    return host


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRuntimeCfgSync(unittest.TestCase):
    """Each test calls _cmd_set and asserts _runtime_cfg is updated."""

    def setUp(self):
        self.host = _make_host()

    def _set(self, args: str):
        with patch("sys.stdout", new_callable=StringIO):
            self.host._cmd_set(args)

    def test_stall_threshold_updates_runtime_cfg_and_objects(self):
        self._set("STALL_THRESHOLD=20")
        self.assertEqual(self.host._runtime_cfg["STALL_THRESHOLD"], 20)
        self.assertEqual(self.host.healer.stall_threshold, 20)
        self.assertEqual(self.host.planner.stall_threshold, 20)
        self.assertEqual(self.host.display.stall_threshold, 20)
        self.host._persist_setting.assert_called_with("STALL_THRESHOLD", 20)

    def test_snapshot_interval_updates_runtime_cfg(self):
        self._set("SNAPSHOT_INTERVAL=25")
        self.assertEqual(self.host._runtime_cfg["SNAPSHOT_INTERVAL"], 25)
        self.host._persist_setting.assert_called_with("SNAPSHOT_INTERVAL", 25)

    def test_verbosity_updates_runtime_cfg(self):
        self._set("VERBOSITY=DEBUG")
        self.assertEqual(self.host._runtime_cfg["VERBOSITY"], "DEBUG")
        self.host._persist_setting.assert_called_with("VERBOSITY", "DEBUG")

    def test_verify_prob_updates_runtime_cfg_and_executor(self):
        self._set("VERIFY_PROB=0.5")
        self.assertEqual(self.host._runtime_cfg["EXEC_VERIFY_PROB"], 0.5)
        self.assertEqual(self.host.executor.verify_prob, 0.5)
        self.host._persist_setting.assert_called_with("EXECUTOR_VERIFY_PROBABILITY", 0.5)

    def test_auto_step_delay_updates_runtime_cfg(self):
        self._set("AUTO_STEP_DELAY=1.5")
        self.assertAlmostEqual(self.host._runtime_cfg["AUTO_STEP_DELAY"], 1.5)
        self.host._persist_setting.assert_called_with("AUTO_STEP_DELAY", 1.5)

    def test_auto_save_interval_updates_runtime_cfg(self):
        self._set("AUTO_SAVE_INTERVAL=10")
        self.assertEqual(self.host._runtime_cfg["AUTO_SAVE_INTERVAL"], 10)
        self.host._persist_setting.assert_called_with("AUTO_SAVE_INTERVAL", 10)

    def test_claude_allowed_tools_updates_runtime_cfg_and_executor(self):
        self._set("CLAUDE_ALLOWED_TOOLS=read,write")
        self.assertEqual(self.host._runtime_cfg["CLAUDE_ALLOWED_TOOLS"], "read,write")
        self.assertEqual(self.host.executor.claude.allowed_tools, "read,write")
        self.host._persist_setting.assert_called_with("CLAUDE_ALLOWED_TOOLS", "read,write")

    def test_webhook_url_updates_runtime_cfg(self):
        fake_sb = types.ModuleType("solo_builder_cli")
        fake_sb.WEBHOOK_URL = ""
        with patch.dict(sys.modules, {"solo_builder_cli": fake_sb}):
            self._set("WEBHOOK_URL=https://example.com/hook")
        self.assertEqual(self.host._runtime_cfg["WEBHOOK_URL"], "https://example.com/hook")
        self.assertEqual(fake_sb.WEBHOOK_URL, "https://example.com/hook")
        self.host._persist_setting.assert_called_with("WEBHOOK_URL", "https://example.com/hook")


class TestRuntimeCfgValidation(unittest.TestCase):
    """Invalid values must not update _runtime_cfg."""

    def setUp(self):
        self.host = _make_host()

    def _set(self, args: str):
        with patch("sys.stdout", new_callable=StringIO):
            self.host._cmd_set(args)

    def test_stall_threshold_rejects_zero(self):
        self._set("STALL_THRESHOLD=0")
        self.assertEqual(self.host._runtime_cfg["STALL_THRESHOLD"], 5)  # unchanged

    def test_verify_prob_rejects_out_of_range(self):
        self._set("VERIFY_PROB=1.5")
        self.assertAlmostEqual(self.host._runtime_cfg["EXEC_VERIFY_PROB"], 0.8)  # unchanged

    def test_verbosity_rejects_unknown_level(self):
        self._set("VERBOSITY=TRACE")
        self.assertEqual(self.host._runtime_cfg["VERBOSITY"], "INFO")  # unchanged

    def test_no_arg_shows_current_value(self):
        out = StringIO()
        with patch("sys.stdout", out):
            self.host._cmd_set("STALL_THRESHOLD")
        self.assertIn("5", out.getvalue())

    def test_unknown_key_prints_help(self):
        out = StringIO()
        with patch("sys.stdout", out):
            self.host._cmd_set("BOGUS_KEY=value")
        self.assertIn("Unknown key", out.getvalue())


if __name__ == "__main__":
    unittest.main()
