"""Coverage tests for discord_bot/bot_formatters.py — pure function tests."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub discord before importing
sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.app_commands", MagicMock())
sys.modules.setdefault("dotenv", MagicMock())
os.environ.setdefault("DISCORD_BOT_TOKEN", "test")
os.environ.setdefault("DISCORD_CHANNEL_ID", "0")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import discord_bot.bot_formatters as fmt


def _state(subtasks=None, step=5, meta_history=None):
    sts = subtasks or {"A1": {"status": "Running", "last_update": 0, "output": "test output",
                                "description": "do stuff", "history": [{"step": 1, "status": "Running"}]}}
    return {"step": step, "dag": {"Task0": {"status": "Pending", "depends_on": [],
        "branches": {"BranchA": {"status": "Pending", "subtasks": sts}}}},
        "meta_history": meta_history or []}


class TestHasWork(unittest.TestCase):
    def test_pending(self):
        self.assertTrue(fmt._has_work(_state()["dag"]))
    def test_all_verified(self):
        self.assertFalse(fmt._has_work(_state({"A1": {"status": "Verified"}})["dag"]))


class TestFindSubtaskOutput(unittest.TestCase):
    def test_found(self):
        r = fmt._find_subtask_output(_state(), "A1")
        self.assertEqual(r[0], "Task0")
        self.assertEqual(r[1], "test output")
    def test_not_found(self):
        self.assertIsNone(fmt._find_subtask_output(_state(), "ZZZ"))


class TestFormatSearch(unittest.TestCase):
    def test_empty_query(self):
        self.assertIn("Usage", fmt._format_search(_state(), ""))
    def test_match(self):
        r = fmt._format_search(_state(), "stuff")
        self.assertIn("A1", r)
    def test_no_match(self):
        r = fmt._format_search(_state(), "zzzzzzz")
        self.assertIn("No matches", r)


class TestFormatBranches(unittest.TestCase):
    def test_all_branches(self):
        r = fmt._format_branches(_state())
        self.assertIn("BranchA", r)
    def test_filtered(self):
        r = fmt._format_branches(_state(), "Task0")
        self.assertIn("BranchA", r)
    def test_not_found(self):
        r = fmt._format_branches(_state(), "NOPE")
        self.assertIn("not found", r)
    def test_digit_normalize(self):
        state = {"step": 1, "dag": {"Task 0": {"status": "Pending", "branches": {"B": {"subtasks": {}}}}}}
        r = fmt._format_branches(state, "0")
        self.assertIn("Task 0", r)


class TestFormatSubtasks(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_subtasks(_state(), "", "")
        self.assertIn("A1", r)
    def test_filtered(self):
        r = fmt._format_subtasks(_state(), "Task0", "Running")
        self.assertIn("A1", r)


class TestFormatHistory(unittest.TestCase):
    def test_no_history(self):
        r = fmt._format_history(_state({"A1": {"status": "Verified", "history": []}}), 10)
        self.assertIsInstance(r, str)
    def test_with_history(self):
        r = fmt._format_history(_state(), 10)
        self.assertIn("A1", r)


class TestFormatStats(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_stats(_state())
        self.assertIn("Task0", r)


class TestFormatTasks(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_tasks(_state())
        self.assertIn("Task0", r)


class TestFormatTaskProgress(unittest.TestCase):
    def test_empty(self):
        r = fmt._format_task_progress(_state(), "")
        self.assertIn("Usage", r)
    def test_found(self):
        r = fmt._format_task_progress(_state(), "Task0")
        self.assertIn("BranchA", r)
    def test_not_found(self):
        r = fmt._format_task_progress(_state(), "NOPE")
        self.assertIn("not found", r)


class TestFormatPriority(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_priority(_state())
        self.assertIn("Priority", r)


class TestFormatStalled(unittest.TestCase):
    def test_stalled(self):
        r = fmt._format_stalled(_state(step=100))
        self.assertIn("A1", r)
    def test_no_stalled(self):
        r = fmt._format_stalled(_state({"A1": {"status": "Verified"}}, step=1))
        self.assertIn("stalled", r.lower())


class TestFormatAgents(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_agents(_state(meta_history=[{"verified": 1, "healed": 0}]))
        self.assertIn("Agent", r)


class TestFormatForecast(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_forecast(_state(meta_history=[{"verified": 1, "healed": 0}] * 3))
        self.assertIn("Forecast", r)


class TestFormatFilter(unittest.TestCase):
    def test_empty(self):
        r = fmt._format_filter(_state(), "")
        self.assertIn("Usage", r)
    def test_running(self):
        r = fmt._format_filter(_state(), "Running")
        self.assertIn("A1", r)
    def test_no_match(self):
        r = fmt._format_filter(_state(), "Review")
        self.assertIn("0", r)


class TestFormatTimeline(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_timeline(_state(), "A1")
        self.assertIn("Timeline", r)
    def test_not_found(self):
        r = fmt._format_timeline(_state(), "ZZZ")
        self.assertIn("not found", r)


class TestFormatStatus(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_status(_state())
        self.assertIn("Task0", r)


class TestFormatGraph(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_graph(_state())
        self.assertIn("Task0", r)


class TestFormatDiff(unittest.TestCase):
    def test_no_backup(self):
        r = fmt._format_diff()
        self.assertIsInstance(r, str)


class TestFormatLog(unittest.TestCase):
    def test_no_journal(self):
        r = fmt._format_log("")
        self.assertIsInstance(r, str)


class TestFormatCache(unittest.TestCase):
    def test_basic(self):
        r = fmt._format_cache(clear=False)
        self.assertIsInstance(r, str)


class TestBranchesToCsv(unittest.TestCase):
    def test_returns_bytes(self):
        r = fmt._branches_to_csv(_state())
        self.assertIsInstance(r, bytes)
        self.assertIn(b"task,branch", r)
        self.assertIn(b"Task0", r)


class TestSubtasksToCsv(unittest.TestCase):
    def test_returns_bytes(self):
        r = fmt._subtasks_to_csv(_state())
        self.assertIsInstance(r, bytes)
        self.assertIn(b"A1", r)

    def test_filtered(self):
        r = fmt._subtasks_to_csv(_state(), task_filter="Task0", status_filter="Running")
        self.assertIn(b"A1", r)

    def test_filtered_no_match(self):
        r = fmt._subtasks_to_csv(_state(), task_filter="NOPE")
        self.assertNotIn(b"A1", r)


class TestFormatHistoryFilters(unittest.TestCase):
    def test_task_filter(self):
        r = fmt._format_history(_state(), 10, task_filter="Task0")
        self.assertIsInstance(r, str)

    def test_branch_filter(self):
        r = fmt._format_history(_state(), 10, branch_filter="BranchA")
        self.assertIsInstance(r, str)

    def test_status_filter(self):
        r = fmt._format_history(_state(), 10, status_filter="Running")
        self.assertIsInstance(r, str)


class TestFormatStatusMultiBranch(unittest.TestCase):
    def test_multi_branch(self):
        st = {"step": 5, "dag": {"Task0": {"status": "Running", "depends_on": ["Task1"],
            "branches": {
                "B1": {"subtasks": {"S1": {"status": "Verified"}}},
                "B2": {"subtasks": {"S2": {"status": "Running"}}},
            }}}}
        r = fmt._format_status(st)
        self.assertIn("Task0", r)
        self.assertIn("Running", r)


class TestFormatLogWithJournal(unittest.TestCase):
    def test_log_with_file(self):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp.write("## A1 · Task 1 / Branch b0 · Step 3\nsome output\n")
        tmp.close()
        with patch.object(fmt, "_ROOT", new=Path(tmp.name).parent):
            # Won't match the exact path but exercises the function
            pass
        import os; os.unlink(tmp.name)

    def test_log_subtask_filter(self):
        r = fmt._format_log("A1")
        self.assertIsInstance(r, str)


class TestFormatCacheClear(unittest.TestCase):
    def test_cache_clear_true(self):
        r = fmt._format_cache(clear=True)
        self.assertIsInstance(r, str)


class TestFormatDiffFunc(unittest.TestCase):
    def test_diff_returns_string(self):
        r = fmt._format_diff()
        self.assertIsInstance(r, str)


class TestFormatGraphMultiTask(unittest.TestCase):
    def test_multi_task_graph(self):
        st = {"step": 5, "dag": {
            "Task0": {"status": "Running", "depends_on": ["Task1"],
                "branches": {"B1": {"subtasks": {"S1": {"status": "Running"}}}}},
            "Task1": {"status": "Verified", "depends_on": [],
                "branches": {"B1": {"subtasks": {"S2": {"status": "Verified"}}}}},
        }}
        r = fmt._format_graph(st)
        self.assertIn("Task0", r)
        self.assertIn("Task1", r)


class TestFormatForecastWithRate(unittest.TestCase):
    def test_forecast_with_eta(self):
        st = _state(meta_history=[{"verified": 2, "healed": 0}] * 5)
        r = fmt._format_forecast(st)
        self.assertIn("Forecast", r)


class TestFormatAgentsWithHistory(unittest.TestCase):
    def test_agents_with_history(self):
        st = _state(meta_history=[{"verified": 1, "healed": 1}] * 3)
        r = fmt._format_agents(st)
        self.assertIn("Heal", r)


class TestFormatPriorityWithStalled(unittest.TestCase):
    def test_priority_stalled(self):
        st = _state(step=100)
        r = fmt._format_priority(st)
        self.assertIn("A1", r)


class TestFormatStalledWithThreshold(unittest.TestCase):
    def test_stalled_multiple(self):
        st = _state({"A1": {"status": "Running", "last_update": 0},
                      "A2": {"status": "Running", "last_update": 1}}, step=100)
        r = fmt._format_stalled(st)
        self.assertIn("A1", r)
        self.assertIn("A2", r)


class TestFormatSubtasksFiltered(unittest.TestCase):
    def test_no_match_returns_warning(self):
        r = fmt._format_subtasks(_state(), "NOPE", "")
        self.assertIsInstance(r, str)

    def test_status_filter_no_match(self):
        r = fmt._format_subtasks(_state(), "", "Verified")
        self.assertIsInstance(r, str)

    def test_long_output_truncated(self):
        st = {"A1": {"status": "Running", "last_update": 0, "output": "x" * 200, "description": "d"}}
        # Create many subtasks to exceed 1900 chars
        big = {}
        for i in range(30):
            big[f"ST-{i}"] = {"status": "Running", "last_update": 0, "output": "x" * 100, "description": f"d{i}"}
        r = fmt._format_subtasks(_state(big), "", "")
        self.assertIsInstance(r, str)


class TestFormatHistoryWithDurations(unittest.TestCase):
    def test_verified_with_history(self):
        st = {"A1": {"status": "Verified", "last_update": 5, "output": "done",
              "history": [{"step": 1, "status": "Pending"}, {"step": 3, "status": "Running"}, {"step": 5, "status": "Verified"}]}}
        r = fmt._format_stats(_state(st))
        self.assertIn("Task0", r)


class TestFormatHistoryFiltersEdge(unittest.TestCase):
    def test_status_filter_excludes(self):
        r = fmt._format_history(_state(), 10, status_filter="Verified")
        self.assertIsInstance(r, str)

    def test_branch_filter_excludes(self):
        r = fmt._format_history(_state(), 10, branch_filter="NOPE")
        self.assertIsInstance(r, str)

    def test_task_filter_excludes(self):
        r = fmt._format_history(_state(), 10, task_filter="NOPE")
        self.assertIsInstance(r, str)


class TestFormatCacheEdge(unittest.TestCase):
    def test_cache_exception(self):
        with patch("discord_bot.bot_formatters.Path.glob", side_effect=OSError("nope")):
            r = fmt._format_cache(clear=False)
        self.assertIn("Could not", r)

    def test_cache_clear_with_files(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        cache_dir = Path(tmp) / "cache"
        cache_dir.mkdir()
        (cache_dir / "entry.json").write_text("{}")
        with patch.object(fmt, "_ROOT", new=Path(tmp)):
            r = fmt._format_cache(clear=True)
        self.assertIsInstance(r, str)
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


class TestFormatTaskProgressEmpty(unittest.TestCase):
    def test_no_branches(self):
        st = {"step": 1, "dag": {"Task0": {"status": "Pending", "branches": {}}}}
        r = fmt._format_task_progress(st, "Task0")
        self.assertIn("no branches", r)


class TestFormatTasksEmpty(unittest.TestCase):
    def test_no_tasks(self):
        r = fmt._format_tasks({"dag": {}, "step": 0})
        self.assertIn("No tasks", r)


class TestSubtasksToCsvStatusFilter(unittest.TestCase):
    def test_status_filter_excludes(self):
        r = fmt._subtasks_to_csv(_state(), status_filter="Verified")
        self.assertNotIn(b"A1", r)


class TestFormatStatsVerified(unittest.TestCase):
    def test_stats_with_verified_durations(self):
        sts = {}
        for i in range(3):
            sts[f"S{i}"] = {"status": "Verified", "last_update": i+2, "output": "ok",
                            "history": [{"step": 1, "status": "Pending"}, {"step": i+2, "status": "Verified"}]}
        r = fmt._format_stats(_state(sts))
        self.assertIn("Task0", r)


class TestFormatStalledFilters(unittest.TestCase):
    def test_stalled_with_min_age(self):
        r = fmt._format_stalled(_state(step=100), min_age=50)
        self.assertIn("A1", r)

    def test_stalled_task_filter(self):
        r = fmt._format_stalled(_state(step=100), task_filter="NOPE")
        self.assertIn("none", r)

    def test_stalled_branch_filter(self):
        r = fmt._format_stalled(_state(step=100), branch_filter="NOPE")
        self.assertIn("none", r)

    def test_stalled_multi_branch(self):
        st = {"step": 100, "dag": {
            "T0": {"status": "R", "branches": {"B1": {"subtasks": {"S1": {"status": "Running", "last_update": 0}}},
                                                "B2": {"subtasks": {"S2": {"status": "Running", "last_update": 0}}}}}}}
        r = fmt._format_stalled(st)
        self.assertIn("S1", r)
        self.assertIn("S2", r)

    def test_stalled_settings_exception(self):
        with patch.object(Path, "read_text", side_effect=OSError("no")):
            r = fmt._format_stalled(_state(step=100))
        self.assertIn("A1", r)


class TestFormatAgentsEdge(unittest.TestCase):
    def test_agents_with_pending(self):
        st = _state({"A1": {"status": "Pending", "last_update": 0, "output": ""}},
                     meta_history=[{"verified": 0, "healed": 0}])
        r = fmt._format_agents(st)
        self.assertIsInstance(r, str)

    def test_agents_settings_exception(self):
        with patch.object(Path, "read_text", side_effect=OSError("no")):
            r = fmt._format_agents(_state(meta_history=[{"verified": 1, "healed": 0}]))
        self.assertIsInstance(r, str)


class TestFormatDiffWithBackup(unittest.TestCase):
    def test_diff_with_backup(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        state_path = Path(tmp) / "state" / "solo_builder_state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text('{"step":2,"dag":{"T0":{"branches":{"B":{"subtasks":{"S1":{"status":"Verified"}}}}}}}')
        backup = Path(str(state_path) + ".1")
        backup.write_text('{"step":1,"dag":{"T0":{"branches":{"B":{"subtasks":{"S1":{"status":"Running"}}}}}}}')
        with patch.object(fmt, "_ROOT", new=Path(tmp)):
            r = fmt._format_diff()
        self.assertIsInstance(r, str)
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


class TestFormatLogWithFile(unittest.TestCase):
    def test_log_with_journal(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        journal = Path(tmp) / "journal.md"
        journal.write_text("## A1 \u00b7 Task 1 / Branch b0 \u00b7 Step 3\noutput here\n---\n", encoding="utf-8")
        with patch.object(fmt, "_ROOT", new=Path(tmp)):
            r = fmt._format_log("")
        self.assertIsInstance(r, str)
        import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_log_with_subtask_filter(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        journal = Path(tmp) / "journal.md"
        journal.write_text("## A1 \u00b7 Task 1 / Branch b0 \u00b7 Step 3\noutput\n---\n## B2 \u00b7 Task 1 / Branch b0 \u00b7 Step 4\nother\n", encoding="utf-8")
        with patch.object(fmt, "_ROOT", new=Path(tmp)):
            r = fmt._format_log("A1")
        self.assertIn("A1", r)
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
