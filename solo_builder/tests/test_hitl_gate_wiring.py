"""Tests for HitlPolicy wiring in Executor (TASK-362, AI-026, AI-032)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.executor import Executor
from utils.hitl_policy import HitlPolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dag(status: str = "Running", tools: str = "Bash", description: str = "do stuff"):
    return {
        "T": {
            "branches": {
                "B": {
                    "subtasks": {
                        "ST": {
                            "name": "ST",
                            "status": status,
                            "tools": tools,
                            "description": description,
                            "output": "",
                            "history": [],
                        }
                    }
                }
            }
        }
    }


def _plist():
    return [("T", "B", "ST", 0)]


def _make_executor():
    ex = Executor(max_per_step=1, verify_prob=0.0)
    ex.claude.available    = False
    ex.anthropic.available = False
    ex.sdk_tool.available  = False
    return ex


# ---------------------------------------------------------------------------
# HitlPolicy loaded in __init__
# ---------------------------------------------------------------------------

class TestHitlPolicyLoadedAtInit(unittest.TestCase):

    def test_executor_has_hitl_policy_attribute(self):
        ex = _make_executor()
        self.assertTrue(hasattr(ex, "_hitl_policy"))

    def test_hitl_policy_is_hitl_policy_instance(self):
        ex = _make_executor()
        self.assertIsInstance(ex._hitl_policy, HitlPolicy)

    def test_hitl_policy_pause_tools_nonempty(self):
        ex = _make_executor()
        self.assertGreater(len(ex._hitl_policy.pause_tools), 0)


# ---------------------------------------------------------------------------
# Policy gate: block (level 3)
# ---------------------------------------------------------------------------

class TestHitlPolicyBlock(unittest.TestCase):

    def _run_with_policy(self, policy: HitlPolicy, tools: str, description: str):
        """Run execute_step with a specific policy injected."""
        ex = _make_executor()
        ex._hitl_policy = policy
        dag = _make_dag(status="Running", tools=tools, description=description)
        with patch("runners.executor._hitl_evaluate", return_value=0):
            ex.execute_step(dag, _plist(), step=1, memory_store={})
        return dag["T"]["branches"]["B"]["subtasks"]["ST"]["status"]

    def test_policy_block_keyword_keeps_running(self):
        policy = HitlPolicy(
            pause_tools=frozenset(),
            notify_tools=frozenset(),
            block_keywords=frozenset(["force-push"]),
            pause_keywords=frozenset(),
        )
        status = self._run_with_policy(policy, "Bash", "git force-push origin main")
        self.assertEqual(status, "Running")

    def test_policy_block_takes_precedence_over_gate_level_0(self):
        policy = HitlPolicy(
            pause_tools=frozenset(),
            notify_tools=frozenset(),
            block_keywords=frozenset(["drop"]),
            pause_keywords=frozenset(),
        )
        status = self._run_with_policy(policy, "Bash", "drop the table")
        self.assertEqual(status, "Running")


# ---------------------------------------------------------------------------
# Policy gate: pause (level 2) — stays Running when no TTY
# ---------------------------------------------------------------------------

class TestHitlPolicyPause(unittest.TestCase):

    def _run_no_tty(self, policy: HitlPolicy, tools: str, description: str = "do stuff"):
        ex = _make_executor()
        ex._hitl_policy = policy
        dag = _make_dag(status="Running", tools=tools, description=description)
        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            ex.execute_step(dag, _plist(), step=1, memory_store={})
        return dag["T"]["branches"]["B"]["subtasks"]["ST"]["status"]

    def test_pause_tool_in_policy_keeps_running_without_tty(self):
        policy = HitlPolicy(
            pause_tools=frozenset(["Bash"]),
            notify_tools=frozenset(),
            block_keywords=frozenset(),
            pause_keywords=frozenset(),
        )
        status = self._run_no_tty(policy, "Bash")
        self.assertEqual(status, "Running")

    def test_pause_keyword_in_policy_keeps_running_without_tty(self):
        policy = HitlPolicy(
            pause_tools=frozenset(),
            notify_tools=frozenset(),
            block_keywords=frozenset(),
            pause_keywords=frozenset(["delete"]),
        )
        status = self._run_no_tty(policy, "Read", "delete all records")
        self.assertEqual(status, "Running")


# ---------------------------------------------------------------------------
# Policy gate: notify (level 1) — proceeds but logs warning
# ---------------------------------------------------------------------------

class TestHitlPolicyNotify(unittest.TestCase):

    def test_notify_tool_logs_warning(self):
        policy = HitlPolicy(
            pause_tools=frozenset(),
            notify_tools=frozenset(["Glob"]),
            block_keywords=frozenset(),
            pause_keywords=frozenset(),
        )
        ex = _make_executor()
        ex._hitl_policy = policy
        ex.verify_prob = 1.0  # allow dice-roll verify
        ex.review_mode = False
        dag = _make_dag(status="Running", tools="Glob", description="search the repo")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor.logger") as mock_log:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            # Level-1 warning logged: hitl_notify
            warn_calls = [str(c) for c in mock_log.warning.call_args_list]
            self.assertTrue(
                any("hitl" in c for c in warn_calls),
                msg=f"Expected hitl warning, got: {warn_calls}",
            )


# ---------------------------------------------------------------------------
# Max-level merging: gate wins over policy when gate level > policy level
# ---------------------------------------------------------------------------

class TestHitlMaxLevelMerge(unittest.TestCase):

    def test_gate_block_wins_when_higher_than_policy(self):
        """hitl_gate returns 3 (block); policy returns 0 — subtask blocked."""
        policy = HitlPolicy(
            pause_tools=frozenset(),
            notify_tools=frozenset(),
            block_keywords=frozenset(),
            pause_keywords=frozenset(),
        )
        ex = _make_executor()
        ex._hitl_policy = policy
        dag = _make_dag(status="Running", tools="Bash", description="safe action")

        with patch("runners.executor._hitl_evaluate", return_value=3):
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        self.assertEqual(dag["T"]["branches"]["B"]["subtasks"]["ST"]["status"], "Running")

    def test_policy_block_wins_when_higher_than_gate(self):
        """hitl_gate returns 1 (notify); policy returns 3 (block) — subtask blocked."""
        policy = HitlPolicy(
            pause_tools=frozenset(),
            notify_tools=frozenset(),
            block_keywords=frozenset(["force-push"]),
            pause_keywords=frozenset(),
        )
        ex = _make_executor()
        ex._hitl_policy = policy
        dag = _make_dag(status="Running", tools="Read", description="git force-push origin")

        with patch("runners.executor._hitl_evaluate", return_value=1):
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        self.assertEqual(dag["T"]["branches"]["B"]["subtasks"]["ST"]["status"], "Running")

    def test_equal_levels_uses_correct_branch(self):
        """Both gate and policy return 2 (pause) — stays Running without TTY."""
        policy = HitlPolicy(
            pause_tools=frozenset(["Bash"]),
            notify_tools=frozenset(),
            block_keywords=frozenset(),
            pause_keywords=frozenset(),
        )
        ex = _make_executor()
        ex._hitl_policy = policy

        dag = _make_dag(status="Running", tools="Bash", description="do stuff")
        with patch("runners.executor._hitl_evaluate", return_value=2), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        self.assertEqual(dag["T"]["branches"]["B"]["subtasks"]["ST"]["status"], "Running")


# ---------------------------------------------------------------------------
# No-tools path: policy not invoked for tool-less subtasks
# ---------------------------------------------------------------------------

class TestHitlNoToolsPath(unittest.TestCase):

    def test_no_tools_subtask_proceeds_to_dice_roll(self):
        """Subtask with no tools bypasses HITL gate entirely — should dice-roll."""
        ex = _make_executor()
        ex.verify_prob = 1.0   # always verify on dice-roll
        ex.review_mode = False
        dag = _make_dag(status="Running", tools="", description="plain subtask")

        ex.execute_step(dag, _plist(), step=1, memory_store={})
        self.assertEqual(dag["T"]["branches"]["B"]["subtasks"]["ST"]["status"], "Verified")


# ---------------------------------------------------------------------------
# Policy-driven evaluate_with_policy integration
# ---------------------------------------------------------------------------

class TestEvaluateWithPolicyIntegration(unittest.TestCase):

    def test_evaluate_with_policy_called_during_execute_step(self):
        """Verify evaluate_with_policy is called when tools are present."""
        import runners.executor as executor_mod

        ex = _make_executor()
        # Use "Glob" — a valid SDK tool that passes _validate_tools
        dag = _make_dag(status="Running", tools="Glob", description="do stuff")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch.object(executor_mod, "_hitl_policy_evaluate",
                          wraps=executor_mod._hitl_policy_evaluate) as mock_eval:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            mock_eval.assert_called_once()

    def test_evaluate_with_policy_receives_policy_instance(self):
        import runners.executor as executor_mod

        ex = _make_executor()
        dag = _make_dag(status="Running", tools="Glob", description="do stuff")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch.object(executor_mod, "_hitl_policy_evaluate",
                          return_value=0) as mock_eval:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            args = mock_eval.call_args[0]
            self.assertIsInstance(args[0], HitlPolicy)


if __name__ == "__main__":
    unittest.main()
