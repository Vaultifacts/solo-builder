"""Deep coverage tests for QueryCommandsMixin — _cmd_branches, _cmd_search,
_cmd_filter, _cmd_timeline, _cmd_log, _cmd_diff, _cmd_stats, _cmd_output,
_cmd_help (TASK-406)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.query_cmds as qc_module
from commands.query_cmds import QueryCommandsMixin
from commands.subtask_cmds import SubtaskCommandsMixin


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _st(status="Pending", history=None, description="", output=""):
    return {
        "status": status,
        "output": output,
        "description": description,
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
                        "A1": _st("Pending", description="do alpha"),
                        "A2": _st("Verified", [{"step": 3, "status": "Verified"}],
                                  description="do beta", output="done"),
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


class _FakeCLI(QueryCommandsMixin, SubtaskCommandsMixin):
    def __init__(self, tmp_dir: str | None = None):
        self.dag = _make_dag()
        self.step = 5
        self.memory_store = {"A": [], "B": []}
        self.alerts = []
        self._priority_cache = [("Task 0", "A", "A1", 40)]
        self._last_priority_step = 3
        self.display = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        self.meta.verify_rate = 0.5
        self.meta.heal_rate = 0.1
        self.meta._history = []
        self.healer = MagicMock()
        self.healer.healed_total = 0
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
        self.shadow.expected = {}
        self._runtime_cfg = {
            "STALL_THRESHOLD": 5,
            "AUTO_STEP_DELAY": 2.0,
        }
        # Ensure module globals
        qc_module.STATUS_COLORS = {}
        qc_module.WHITE = ""
        if not hasattr(qc_module, "make_bar"):
            qc_module.make_bar = lambda filled, total: "[====]"
        if tmp_dir:
            self._tmp = tmp_dir
            qc_module.JOURNAL_PATH = os.path.join(tmp_dir, "JOURNAL.md")
            qc_module.STATE_PATH = os.path.join(tmp_dir, "state.json")


# ---------------------------------------------------------------------------
# _cmd_branches
# ---------------------------------------------------------------------------

class TestCmdBranches(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_no_args_shows_all_tasks(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_branches("")
        combined = "\n".join(printed)
        self.assertIn("Task 0", combined)
        self.assertIn("Task 1", combined)

    def test_no_args_shows_branch_counts(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_branches("")
        combined = "\n".join(printed)
        self.assertIn("branch", combined.lower())

    def test_digit_arg_normalised(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_branches("0")
        combined = "\n".join(printed)
        self.assertIn("Task 0", combined)

    def test_full_task_name_arg(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_branches("Task 0")
        combined = "\n".join(printed)
        self.assertIn("Task 0", combined)
        self.assertIn("A1", combined)

    def test_task_not_found(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_branches("Task 99")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_task_with_review_subtask(self):
        """Branch with Review subtask shows rv counter."""
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_branches("Task 1")
        combined = "\n".join(printed)
        self.assertIn("B1", combined)


# ---------------------------------------------------------------------------
# _cmd_search
# ---------------------------------------------------------------------------

class TestCmdSearch(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_empty_query_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_search("")
        self.assertIn("Usage", "\n".join(printed))

    def test_match_by_description(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_search("alpha")
        combined = "\n".join(printed)
        self.assertIn("A1", combined)

    def test_match_by_output(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_search("done")
        combined = "\n".join(printed)
        self.assertIn("A2", combined)

    def test_match_by_st_name(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_search("b1")
        combined = "\n".join(printed)
        self.assertIn("B1", combined)

    def test_no_matches_shows_empty_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_search("zzznomatchzzz")
        combined = "\n".join(printed)
        self.assertIn("No matches", combined)


# ---------------------------------------------------------------------------
# _cmd_filter
# ---------------------------------------------------------------------------

class TestCmdFilter(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_invalid_status_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_filter("Bogus")
        combined = "\n".join(printed)
        self.assertIn("Usage", combined)

    def test_filter_pending(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_filter("pending")
        combined = "\n".join(printed)
        self.assertIn("A1", combined)

    def test_filter_verified(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_filter("verified")
        combined = "\n".join(printed)
        self.assertIn("A2", combined)

    def test_filter_running(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_filter("running")
        combined = "\n".join(printed)
        self.assertIn("A3", combined)

    def test_filter_review(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_filter("review")
        combined = "\n".join(printed)
        self.assertIn("B1", combined)

    def test_filter_no_matches(self):
        """All subtasks set to Pending — no Review matches."""
        for task in self.cli.dag.values():
            for br in task.get("branches", {}).values():
                for st in br.get("subtasks", {}).values():
                    st["status"] = "Pending"
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_filter("review")
        combined = "\n".join(printed)
        self.assertIn("None", combined)


# ---------------------------------------------------------------------------
# _cmd_timeline
# ---------------------------------------------------------------------------

class TestCmdTimeline(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_empty_arg_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_timeline("")
        self.assertIn("Usage", "\n".join(printed))

    def test_not_found_prints_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_timeline("ZZ")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_no_history_shows_no_transitions_message(self):
        self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]["history"] = []
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_timeline("A1")
        combined = "\n".join(printed)
        self.assertIn("No transitions", combined)

    def test_with_history_shows_steps(self):
        self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A2"]["history"] = [
            {"step": 2, "status": "Running"},
            {"step": 3, "status": "Verified"},
        ]
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_timeline("A2")
        combined = "\n".join(printed)
        self.assertIn("Step 2", combined)
        self.assertIn("Step 3", combined)


# ---------------------------------------------------------------------------
# _cmd_log
# ---------------------------------------------------------------------------

class TestCmdLog(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.cli = _FakeCLI(self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_missing_journal_prints_warning(self):
        # JOURNAL_PATH points to non-existent file
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_log("")
        combined = "\n".join(printed)
        self.assertIn("No journal", combined)

    def test_read_error_prints_error(self):
        p = qc_module.JOURNAL_PATH
        Path(p).write_text("data")
        with patch("builtins.open", side_effect=PermissionError("denied")):
            printed = []
            with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
                self.cli._cmd_log("")
        combined = "\n".join(printed)
        self.assertIn("Could not read", combined)

    def test_with_journal_entries(self):
        journal = (
            "## A1 \u00b7 Task 0 / Branch A \u00b7 Step 3\n"
            "Some output here.\n\n"
            "## A2 \u00b7 Task 0 / Branch A \u00b7 Step 4\n"
            "More output.\n"
        )
        Path(qc_module.JOURNAL_PATH).write_text(journal, encoding="utf-8")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_log("")
        combined = "\n".join(printed)
        self.assertIn("A1", combined)
        self.assertIn("A2", combined)

    def test_filtered_by_subtask_name(self):
        journal = (
            "## A1 \u00b7 Task 0 / Branch A \u00b7 Step 3\n"
            "Alpha output.\n\n"
            "## A2 \u00b7 Task 0 / Branch A \u00b7 Step 4\n"
            "Beta output.\n"
        )
        Path(qc_module.JOURNAL_PATH).write_text(journal, encoding="utf-8")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_log("a1")
        combined = "\n".join(printed)
        self.assertIn("A1", combined)
        self.assertNotIn("A2", combined)

    def test_no_matching_entries_shows_empty(self):
        Path(qc_module.JOURNAL_PATH).write_text(
            "## A1 \u00b7 Task 0 / Branch A \u00b7 Step 3\nContent.\n", encoding="utf-8"
        )
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_log("ZZ")
        combined = "\n".join(printed)
        self.assertIn("No entries", combined)


# ---------------------------------------------------------------------------
# _cmd_diff
# ---------------------------------------------------------------------------

class TestCmdDiff(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.cli = _FakeCLI(self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_no_backup_prints_warning(self):
        # STATE_PATH.1 does not exist
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_diff()
        combined = "\n".join(printed)
        self.assertIn("No backup", combined)

    def test_unreadable_backup_prints_error(self):
        backup = qc_module.STATE_PATH + ".1"
        Path(backup).write_text("not json {{{")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_diff()
        combined = "\n".join(printed)
        self.assertIn("Could not read", combined)

    def test_no_changes_prints_no_changes(self):
        backup = qc_module.STATE_PATH + ".1"
        # Same DAG as current
        payload = {"step": 4, "dag": self.cli.dag}
        Path(backup).write_text(json.dumps(payload))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_diff()
        combined = "\n".join(printed)
        self.assertIn("No subtask status changes", combined)

    def test_with_changes_shows_diff(self):
        backup = qc_module.STATE_PATH + ".1"
        # Old dag has A1 as Verified; current has A1 as Pending
        old_dag = json.loads(json.dumps(self.cli.dag))  # deep copy
        old_dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]["status"] = "Verified"
        payload = {"step": 4, "dag": old_dag}
        Path(backup).write_text(json.dumps(payload))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_diff()
        combined = "\n".join(printed)
        self.assertIn("A1", combined)

    def test_review_output_preview_included(self):
        backup = qc_module.STATE_PATH + ".1"
        old_dag = json.loads(json.dumps(self.cli.dag))
        old_dag["Task 1"]["branches"]["B"]["subtasks"]["B1"]["status"] = "Running"
        # Current B1 is Review with output
        self.cli.dag["Task 1"]["branches"]["B"]["subtasks"]["B1"]["output"] = "review text here"
        payload = {"step": 3, "dag": old_dag}
        Path(backup).write_text(json.dumps(payload))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_diff()
        combined = "\n".join(printed)
        self.assertIn("B1", combined)


# ---------------------------------------------------------------------------
# _cmd_stats
# ---------------------------------------------------------------------------

class TestCmdStats(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"):
            self.cli._cmd_stats()

    def test_shows_task_names(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_stats()
        combined = "\n".join(printed)
        self.assertIn("Task 0", combined)

    def test_shows_total_row(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_stats()
        combined = "\n".join(printed)
        self.assertIn("TOTAL", combined)

    def test_empty_dag_runs(self):
        self.cli.dag = {}
        with patch("builtins.print"):
            self.cli._cmd_stats()

    def test_verified_with_history_includes_duration(self):
        """Subtask with 2-entry history contributes a duration."""
        self.cli.dag["Task 0"]["branches"]["A"]["subtasks"]["A2"]["history"] = [
            {"step": 1, "status": "Running"},
            {"step": 4, "status": "Verified"},
        ]
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_stats()
        combined = "\n".join(printed)
        self.assertIn("3.0", combined)  # 4 - 1 = 3


# ---------------------------------------------------------------------------
# _cmd_output
# ---------------------------------------------------------------------------

class TestCmdOutput(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_empty_arg_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_output("")
        self.assertIn("Usage", "\n".join(printed))

    def test_not_found_prints_warning(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_output("ZZ")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_with_output_prints_content(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_output("A2")
        combined = "\n".join(printed)
        self.assertIn("done", combined)

    def test_no_output_prints_no_output_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_output("A1")
        combined = "\n".join(printed)
        self.assertIn("No output", combined)


# ---------------------------------------------------------------------------
# _cmd_help
# ---------------------------------------------------------------------------

class TestCmdHelp(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_help()

    def test_calls_display_render(self):
        with patch("builtins.print"), patch("builtins.input", return_value=""):
            self.cli._cmd_help()
        self.cli.display.render.assert_called_once()

    def test_shows_help_text(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("builtins.input", return_value=""):
            self.cli._cmd_help()
        combined = "\n".join(printed)
        self.assertIn("auto", combined.lower())
        self.assertIn("status", combined.lower())


if __name__ == "__main__":
    unittest.main()
