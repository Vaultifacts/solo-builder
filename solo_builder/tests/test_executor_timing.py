"""Tests for step_complete timing log in Executor.execute_step — TASK-333 (OM-042)."""
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.executor import Executor


# ---------------------------------------------------------------------------
# Minimal DAG / project list helpers
# ---------------------------------------------------------------------------

def _make_dag(status="Pending"):
    return {
        "Task-A": {
            "branches": {
                "Branch-1": {
                    "subtasks": {
                        "ST-1": {
                            "name": "ST-1",
                            "status": status,
                            "output": "",
                            "history": [],
                        }
                    }
                }
            }
        }
    }


def _plist():
    # priority_list: list of (task_name, branch_name, subtask_name, priority_int)
    return [("Task-A", "Branch-1", "ST-1", 0)]


def _make_executor():
    ex = Executor(max_per_step=1, verify_prob=1.0)
    ex.claude.available = False
    ex.anthropic.available = False
    ex.sdk_tool.available = False
    return ex


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStepCompleteLog(unittest.TestCase):
    """Executor.execute_step emits a step_complete log with elapsed_ms (OM-042)."""

    def _run_step(self, status="Pending"):
        ex = _make_executor()
        dag = _make_dag(status)

        log_records: list[logging.LogRecord] = []

        class _Cap(logging.Handler):
            def emit(self, record):
                log_records.append(record)

        cap = _Cap()
        logger = logging.getLogger("solo_builder")
        logger.addHandler(cap)
        old_level = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            with patch("runners.executor._write_step_metrics"):
                ex.execute_step(dag, _plist(), step=1, memory_store={})
        finally:
            logger.removeHandler(cap)
            logger.setLevel(old_level)
        return log_records

    def test_step_complete_logged(self):
        records = self._run_step()
        msgs = [r.getMessage() for r in records]
        step_complete = [m for m in msgs if "step_complete" in m]
        self.assertTrue(step_complete,
                        f"No step_complete log found. All msgs: {msgs}")

    def test_step_complete_contains_elapsed_ms(self):
        records = self._run_step()
        msgs = [r.getMessage() for r in records if "step_complete" in r.getMessage()]
        self.assertTrue(any("elapsed_ms=" in m for m in msgs),
                        f"elapsed_ms missing from step_complete log: {msgs}")

    def test_step_complete_contains_step_number(self):
        records = self._run_step()
        msgs = [r.getMessage() for r in records if "step_complete" in r.getMessage()]
        self.assertTrue(any("step=1" in m for m in msgs),
                        f"step= missing from step_complete log: {msgs}")

    def test_step_complete_contains_actions_count(self):
        records = self._run_step()
        msgs = [r.getMessage() for r in records if "step_complete" in r.getMessage()]
        self.assertTrue(any("actions=" in m for m in msgs),
                        f"actions= missing from step_complete log: {msgs}")

    def test_elapsed_ms_is_non_negative(self):
        records = self._run_step()
        for r in records:
            msg = r.getMessage()
            if "elapsed_ms=" in msg:
                part = msg.split("elapsed_ms=")[1].split()[0]
                self.assertGreaterEqual(int(part), 0)

    def test_step_complete_is_info_level(self):
        records = self._run_step()
        step_records = [r for r in records if "step_complete" in r.getMessage()]
        self.assertTrue(step_records)
        self.assertEqual(step_records[0].levelno, logging.INFO)


if __name__ == "__main__":
    unittest.main()
