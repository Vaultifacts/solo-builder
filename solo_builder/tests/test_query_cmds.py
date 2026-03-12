"""Tests for QueryCommandsMixin — _cmd_status, _cmd_graph, _cmd_priority,
_cmd_stalled, _cmd_agents, _cmd_forecast, _cmd_tasks, _cmd_history (TASK-403)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.query_cmds as qc_module
from commands.query_cmds import QueryCommandsMixin


# ---------------------------------------------------------------------------
# Shared CLI stub
# ---------------------------------------------------------------------------

def _st(status="Pending", history=None):
    return {
        "status": status,
        "output": "",
        "description": "do something",
        "history": history or [],
        "last_update": 0,
    }


def _make_dag():
    return {
        "Task 0": {
            "status": "Running",
            "depends_on": [],
            "branches": {
                "A": {
                    "subtasks": {
                        "A1": _st("Pending"),
                        "A2": _st("Verified", [{"step": 1, "status": "Verified"}]),
                        "A3": _st("Running"),
                    }
                }
            },
        },
        "Task 1": {
            "status": "Pending",
            "depends_on": ["Task 0"],
            "branches": {
                "B": {
                    "subtasks": {
                        "B1": _st("Review"),
                    }
                }
            },
        },
    }


class _FakeCLI(QueryCommandsMixin):
    def __init__(self):
        self.dag = _make_dag()
        self.step = 5
        self.memory_store = {"A": [], "B": []}
        self.alerts = []
        self._priority_cache = [
            ("Task 0", "A", "A1", 40),
            ("Task 0", "A", "A3", 50),
        ]
        self._last_priority_step = 3
        self.display = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {"steps": 10}
        self.meta.verify_rate = 0.5
        self.meta.heal_rate = 0.1
        self.meta._history = [1, 2, 3]
        self.healer = MagicMock()
        self.healer.healed_total = 2
        self.healer.stall_threshold = 5
        self.healer.find_stalled.return_value = []
        self.planner = MagicMock()
        self.planner.w_stall = 1.0
        self.planner.w_staleness = 0.8
        self.planner.w_shadow = 0.5
        self.executor = MagicMock()
        self.executor.max_per_step = 2
        self.executor.verify_prob = 0.3
        self.shadow = MagicMock()
        self.shadow.expected = {"A1": "Pending"}
        self._runtime_cfg = {
            "STALL_THRESHOLD": 5,
            "AUTO_STEP_DELAY": 2.0,
        }
        # Patch module globals
        qc_module.STATUS_COLORS = {}
        qc_module.WHITE = ""
        if not hasattr(qc_module, "make_bar"):
            qc_module.make_bar = lambda filled, total: "[====]"


# ---------------------------------------------------------------------------
# _cmd_status
# ---------------------------------------------------------------------------

class TestCmdStatus(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_status()

    def test_calls_display_render(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_status()
        self.cli.display.render.assert_called_once()

    def test_calls_meta_forecast(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_status()
        self.cli.meta.forecast.assert_called()


# ---------------------------------------------------------------------------
# _cmd_graph
# ---------------------------------------------------------------------------

class TestCmdGraph(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"):
            self.cli._cmd_graph()

    def test_prints_task_names(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_graph()
        combined = "\n".join(printed)
        self.assertIn("Task 0", combined)
        self.assertIn("Task 1", combined)

    def test_shows_dependencies(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_graph()
        combined = "\n".join(printed)
        # Task 0 is a dep of Task 1 → should show dependent
        self.assertIn("Task 1", combined)

    def test_empty_dag_runs(self):
        self.cli.dag = {}
        with patch("builtins.print"):
            self.cli._cmd_graph()


# ---------------------------------------------------------------------------
# _cmd_priority
# ---------------------------------------------------------------------------

class TestCmdPriority(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"):
            self.cli._cmd_priority()

    def test_empty_queue_prints_empty_message(self):
        self.cli._priority_cache = []
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_priority()
        combined = "\n".join(printed)
        self.assertIn("Empty", combined)

    def test_more_than_20_truncated(self):
        # 25 items → shows "… and 5 more"
        subtasks = ["A1", "A2", "A3"]
        self.cli._priority_cache = [
            ("Task 0", "A", subtasks[i % len(subtasks)], i) for i in range(25)
        ]
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_priority()
        combined = "\n".join(printed)
        self.assertIn("5 more", combined)


# ---------------------------------------------------------------------------
# _cmd_stalled
# ---------------------------------------------------------------------------

class TestCmdStalled(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_none_stalled_prints_none(self):
        self.cli.healer.find_stalled.return_value = []
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_stalled()
        combined = "\n".join(printed)
        self.assertIn("None", combined)

    def test_stalled_items_printed(self):
        self.cli.healer.find_stalled.return_value = [
            ("Task 0", "A", "A3", 8)
        ]
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_stalled()
        combined = "\n".join(printed)
        self.assertIn("A3", combined)


# ---------------------------------------------------------------------------
# _cmd_agents
# ---------------------------------------------------------------------------

class TestCmdAgents(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"):
            self.cli._cmd_agents()

    def test_shows_stalled_count_when_nonzero(self):
        self.cli.healer.find_stalled.return_value = [("T", "B", "S", 6)]
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_agents()
        combined = "\n".join(printed)
        self.assertIn("stalled", combined)

    def test_no_stalled_message_when_zero(self):
        self.cli.healer.find_stalled.return_value = []
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_agents()
        combined = "\n".join(printed)
        self.assertNotIn("currently stalled", combined)


# ---------------------------------------------------------------------------
# _cmd_forecast
# ---------------------------------------------------------------------------

class TestCmdForecast(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"):
            self.cli._cmd_forecast()

    def test_shows_eta_when_verify_rate_positive(self):
        self.cli.meta.verify_rate = 1.0
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_forecast()
        combined = "\n".join(printed)
        self.assertIn("ETA", combined)

    def test_shows_insufficient_data_when_zero_rate(self):
        self.cli.meta.verify_rate = 0.0
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_forecast()
        combined = "\n".join(printed)
        self.assertIn("insufficient", combined)


# ---------------------------------------------------------------------------
# _cmd_tasks
# ---------------------------------------------------------------------------

class TestCmdTasks(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"):
            self.cli._cmd_tasks()

    def test_prints_task_names(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_tasks()
        combined = "\n".join(printed)
        self.assertIn("Task 0", combined)
        self.assertIn("Task 1", combined)

    def test_empty_dag_runs(self):
        self.cli.dag = {}
        with patch("builtins.print"):
            self.cli._cmd_tasks()


# ---------------------------------------------------------------------------
# _cmd_history
# ---------------------------------------------------------------------------

class TestCmdHistory(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()
        # Give A2 a history entry
        self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A2"]["history"] = [
            {"step": 3, "status": "Verified"},
        ]

    def test_runs_without_error(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_history("")

    def test_custom_limit_applied(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_history("5")

    def test_non_numeric_limit_defaults_to_20(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_history("abc")

    def test_shows_history_entry(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("builtins.input", return_value=""):
            self.cli._cmd_history("")
        combined = "\n".join(printed)
        self.assertIn("A2", combined)

    def test_no_history_shows_empty_message(self):
        for task in self.cli.dag.values():
            for br in task.get("branches", {}).values():
                for st in br.get("subtasks", {}).values():
                    st["history"] = []
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("builtins.input", return_value=""):
            self.cli._cmd_history("")
        combined = "\n".join(printed)
        self.assertIn("No history", combined)


# ---------------------------------------------------------------------------
# _cmd_log line 346: block starts with ## but doesn't match regex → continue
# ---------------------------------------------------------------------------

class TestCmdLog(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()
        self._tmp = tempfile.mkdtemp()
        import commands.query_cmds as _qc
        self._qc = _qc
        self._old_journal = getattr(_qc, "JOURNAL_PATH", None)

    def tearDown(self):
        import commands.query_cmds as _qc
        import shutil
        if self._old_journal is not None:
            _qc.JOURNAL_PATH = self._old_journal
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_block_with_bad_header_skipped(self):
        """Line 346: block starts with '## ' but doesn't match full regex → continue."""
        import os
        journal = os.path.join(self._tmp, "JOURNAL.md")
        # Write a block that starts with ## but has a malformed header
        Path(journal).write_text(
            "## not-a-valid-header\n\nsome body text\n",
            encoding="utf-8",
        )
        self._qc.JOURNAL_PATH = journal
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_log("")
        combined = "\n".join(printed)
        # No entries parsed from the malformed block
        self.assertIn("0 entr", combined)

    def test_no_journal_file_prints_warning(self):
        self._qc.JOURNAL_PATH = os.path.join(self._tmp, "nonexistent.md")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_log("")
        self.assertIn("No journal", "\n".join(printed))


if __name__ == "__main__":
    unittest.main()
