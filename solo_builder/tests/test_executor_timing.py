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


class TestFireOutcomeEdgeCases(unittest.TestCase):
    """Cover _fire_outcome() edge cases — TASK-398."""

    def test_fire_outcome_no_routing_key_returns_early(self):
        """No _aawo_routing in st_data → early return (no import, no thread)."""
        from runners.executor import _fire_outcome
        # Should not raise and should not import threading
        _fire_outcome({}, "success", 0.1, None)

    def test_fire_outcome_routing_not_dict_returns_early(self):
        """_aawo_routing is a string (not dict) → early return at isinstance check."""
        from runners.executor import _fire_outcome
        _fire_outcome({"_aawo_routing": "string_value"}, "success", 0.1, None)

    def test_fire_outcome_no_agent_id_returns_early(self):
        """line 73: routing dict exists but no agent_id → return early."""
        from runners.executor import _fire_outcome
        # routing is dict but agent_id key is absent → should exit without spawning thread
        _fire_outcome({"_aawo_routing": {}}, "success", 0.1, None)

    def test_fire_outcome_agent_id_none_returns_early(self):
        """agent_id is explicitly None → falsy check returns early."""
        from runners.executor import _fire_outcome
        _fire_outcome({"_aawo_routing": {"agent_id": None}}, "success", 0.1, None)


class TestUpdateTaskEdgeCases(unittest.TestCase):
    """Cover Executor._update_task() Running branch — lines 421-422, TASK-398."""

    def test_update_task_sets_running_when_branch_is_running(self):
        """lines 421-422: task status → Running when branch is Running (not all Verified)."""
        ex = _make_executor()
        dag = {
            "T0": {
                "status": "Pending",
                "branches": {
                    "b1": {"status": "Running"},
                    "b2": {"status": "Pending"},
                },
            }
        }
        with patch("runners.executor._write_step_metrics"):
            ex._update_task(dag, "T0")
        self.assertEqual(dag["T0"]["status"], "Running")

    def test_update_task_sets_verified_when_all_branches_verified(self):
        ex = _make_executor()
        dag = {
            "T0": {
                "status": "Running",
                "branches": {
                    "b1": {"status": "Verified"},
                    "b2": {"status": "Verified"},
                },
            }
        }
        with patch("runners.executor._write_step_metrics"):
            ex._update_task(dag, "T0")
        self.assertEqual(dag["T0"]["status"], "Verified")


class TestExecuteStepMaxPerStep(unittest.TestCase):
    """Cover the max_per_step break (line 159) — TASK-398."""

    def test_max_per_step_one_limits_to_one_subtask(self):
        """max_per_step=1: only first subtask in priority list is advanced."""
        ex = _make_executor()
        ex.max_per_step = 1
        dag = {
            "T0": {"status": "Pending", "branches": {"b0": {"subtasks": {
                "s1": {"status": "Pending", "history": [], "last_update": 0},
                "s2": {"status": "Pending", "history": [], "last_update": 0},
            }}}},
        }
        plist = [("T0", "b0", "s1", 0), ("T0", "b0", "s2", 0)]
        with patch("runners.executor._write_step_metrics"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        # Only s1 should be touched
        self.assertIn("s1", actions)
        self.assertNotIn("s2", actions)


class TestWriteStepMetricsOSError(unittest.TestCase):
    """Lines 59-60: OSError in _write_step_metrics is silently swallowed."""

    def test_oserror_is_swallowed(self):
        from runners.executor import _write_step_metrics
        with patch("builtins.open", side_effect=OSError("denied")):
            # Should not raise
            _write_step_metrics(1, 0.0, 0, 0, {})


class TestFireOutcomeAgentIdFalsy(unittest.TestCase):
    """Line 73: _fire_outcome returns early when agent_id is falsy but path is set."""

    def test_empty_agent_id_returns_early(self):
        from runners.executor import _fire_outcome
        # aawo_repo_path is not None, routing is dict, but agent_id is ""
        _fire_outcome(
            {"_aawo_routing": {"agent_id": ""}},
            "success", 0.1, "/some/repo"
        )  # Must not raise or import threading

    def test_none_agent_id_with_repo_path_returns_early(self):
        from runners.executor import _fire_outcome
        _fire_outcome(
            {"_aawo_routing": {"agent_id": None}},
            "success", 0.1, "/some/repo"
        )


class TestSubprocessFallback(unittest.TestCase):
    """Lines 242-246: subprocess fallback when sdk_tool unavailable but claude available."""

    def test_subprocess_fallback_when_sdk_unavailable(self):
        ex = _make_executor()
        ex.anthropic.available = False
        ex.sdk_tool.available = False
        ex.claude.available = True
        # Give the subtask tools so it goes through the tools branch
        dag = {
            "Task-A": {"branches": {"Branch-1": {"subtasks": {
                "ST-1": {
                    "status": "Running", "output": "", "history": [],
                    "tools": "Read,Glob",
                }
            }}}}
        }
        # Mock claude.run to return a result so the job completes
        ex.claude.run = MagicMock(return_value=(True, "output here"))
        plist = [("Task-A", "Branch-1", "ST-1", 0)]
        with patch("runners.executor._write_step_metrics"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertIn("ST-1", actions)


class TestSdkToolSuccessRollUp(unittest.TestCase):
    """Line 295: _roll_up called after sdk_tool success (not review_mode)."""

    def test_sdk_tool_success_calls_roll_up(self):
        ex = _make_executor()
        ex.sdk_tool.available = True
        ex.claude.available = False
        ex.review_mode = False
        async def _ok(*a, **kw):
            return (True, "sdk tool output")
        ex.sdk_tool.arun = _ok
        dag = {
            "Task-A": {"branches": {"Branch-1": {"subtasks": {
                "ST-1": {
                    "status": "Running", "output": "", "history": [],
                    "tools": "Read",
                }
            }}}}
        }
        plist = [("Task-A", "Branch-1", "ST-1", 0)]
        _scope_result = MagicMock()
        _scope_result.allowed = True
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate", return_value=_scope_result):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertIn("ST-1", actions)
        self.assertEqual(dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]["status"], "Verified")


class TestSdkToolFailedEscalate(unittest.TestCase):
    """Lines 303-320: sdk_tool failed → escalate to subprocess or dice-roll."""

    def _dag_with_tools(self):
        return {
            "Task-A": {"branches": {"Branch-1": {"subtasks": {
                "ST-1": {
                    "status": "Running", "output": "", "history": [],
                    "tools": "Read,Glob",
                }
            }}}}
        }

    def test_sdk_tool_failed_escalates_to_claude(self):
        """Lines 305-308: SDK tool failure → add to claude_jobs when claude available."""
        ex = _make_executor()
        ex.sdk_tool.available = True
        ex.claude.available = True
        # Make sdk_tool fail
        ex.sdk_tool.arun = MagicMock()
        import asyncio as _asyncio
        async def _fail(*a, **kw):
            return (False, "tool error")
        ex.sdk_tool.arun = _fail
        dag = self._dag_with_tools()
        ex.claude.run = MagicMock(return_value=(True, "claude output"))
        plist = [("Task-A", "Branch-1", "ST-1", 0)]
        with patch("runners.executor._write_step_metrics"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertIn("ST-1", actions)

    def test_sdk_tool_failed_no_claude_dice_roll(self):
        """Lines 309-320: SDK tool failure, no claude → dice-roll verify_prob=1.0."""
        ex = _make_executor()
        ex.sdk_tool.available = True
        ex.claude.available = False
        ex.verify_prob = 1.0
        ex.review_mode = False
        async def _fail(*a, **kw):
            return (False, "tool error")
        ex.sdk_tool.arun = _fail
        dag = self._dag_with_tools()
        plist = [("Task-A", "Branch-1", "ST-1", 0)]
        _scope_result = MagicMock()
        _scope_result.allowed = True
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate", return_value=_scope_result):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertIn("ST-1", actions)


class TestSdkDirectFailed(unittest.TestCase):
    """Lines 384-394: SDK direct (anthropic) failed → dice-roll fallback."""

    def test_sdk_direct_failed_dice_roll(self):
        ex = _make_executor()
        ex.anthropic.available = True
        ex.sdk_tool.available = False
        ex.claude.available = False
        ex.verify_prob = 1.0
        # Make anthropic SDK runner return failure
        ex.anthropic.run = MagicMock(return_value=(False, "error"))
        dag = _make_dag("Running")
        # No tools on subtask so it uses anthropic direct
        plist = _plist()
        with patch("runners.executor._write_step_metrics"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertIn("ST-1", actions)
        self.assertEqual(dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]["status"], "Verified")


class TestHitlTtyGate(unittest.TestCase):
    """Lines 205-211: HITL level 2 with TTY — prompts user and blocks if denied."""

    def _dag_with_valid_tools(self):
        return {
            "Task-A": {"branches": {"Branch-1": {"subtasks": {
                "ST-1": {
                    "status": "Running", "output": "", "history": [],
                    "tools": "Read",  # "Read" is valid per _VALID_TOOLS
                }
            }}}}
        }

    def test_hitl_l2_approved(self):
        """User answers 'y' — subtask proceeds via sdk_tool after approval."""
        ex = _make_executor()
        ex.anthropic.available = False
        ex.sdk_tool.available = True
        ex.claude.available = False
        dag = self._dag_with_valid_tools()
        async def _ok(*a, **kw):
            return (True, "approved output")
        ex.sdk_tool.arun = _ok
        plist = [("Task-A", "Branch-1", "ST-1", 0)]
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor.sys.stdin") as mock_stdin, \
             patch("builtins.input", return_value="y"), \
             patch("runners.executor._hitl_evaluate", return_value=2), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0):
            mock_stdin.isatty.return_value = True
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        self.assertIn("ST-1", actions)

    def test_hitl_l2_denied(self):
        """User answers 'n' — subtask stays Running (skipped via continue)."""
        ex = _make_executor()
        ex.anthropic.available = False
        ex.sdk_tool.available = False
        ex.claude.available = False
        ex.verify_prob = 1.0
        dag = self._dag_with_valid_tools()
        plist = [("Task-A", "Branch-1", "ST-1", 0)]
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor.sys.stdin") as mock_stdin, \
             patch("builtins.input", return_value="n"), \
             patch("runners.executor._hitl_evaluate", return_value=2), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0):
            mock_stdin.isatty.return_value = True
            actions = ex.execute_step(dag, plist, step=1, memory_store={})
        # Denied → subtask stays Running, not in actions
        self.assertNotIn("ST-1", actions)


if __name__ == "__main__":
    unittest.main()
