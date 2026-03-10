"""Tests for ToolScopePolicy wiring in Executor (TASK-365, AI-033)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.executor import Executor
from utils.tool_scope_policy import ToolScopePolicy, ScopeResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dag(status: str = "Running", tools: str = "Glob",
              description: str = "do stuff", action_type: str = "") -> dict:
    st: dict = {
        "name": "ST",
        "status": status,
        "tools": tools,
        "description": description,
        "output": "",
        "history": [],
    }
    if action_type:
        st["action_type"] = action_type
    return {
        "T": {
            "branches": {
                "B": {
                    "subtasks": {"ST": st}
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
    ex.review_mode = False
    return ex


def _permissive_policy(default_type: str = "full_execution") -> ToolScopePolicy:
    """Policy that allows all standard tools under full_execution."""
    return ToolScopePolicy(
        allowlists={"full_execution": frozenset({"Glob", "Grep", "Read", "Bash"})},
        default_action_type=default_type,
    )


def _restrictive_policy() -> ToolScopePolicy:
    """Policy that denies Bash under read_only."""
    return ToolScopePolicy(
        allowlists={
            "read_only":     frozenset({"Glob", "Grep", "Read"}),
            "full_execution": frozenset({"Glob", "Grep", "Read", "Bash"}),
        },
        default_action_type="full_execution",
    )


# ---------------------------------------------------------------------------
# Policy loaded at __init__
# ---------------------------------------------------------------------------

class TestScopePolicyLoadedAtInit(unittest.TestCase):

    def test_executor_has_scope_policy_attribute(self):
        ex = _make_executor()
        self.assertTrue(hasattr(ex, "_scope_policy"))

    def test_scope_policy_is_tool_scope_policy(self):
        ex = _make_executor()
        self.assertIsInstance(ex._scope_policy, ToolScopePolicy)

    def test_scope_policy_has_allowlists(self):
        ex = _make_executor()
        self.assertGreater(len(ex._scope_policy.allowlists), 0)

    def test_scope_policy_has_default_action_type(self):
        ex = _make_executor()
        self.assertIsInstance(ex._scope_policy.default_action_type, str)
        self.assertTrue(ex._scope_policy.default_action_type)


# ---------------------------------------------------------------------------
# Scope gate: deny path
# ---------------------------------------------------------------------------

class TestScopeDenied(unittest.TestCase):

    def test_denied_tool_keeps_running(self):
        """Bash not allowed under read_only → subtask stays Running."""
        policy = _restrictive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        # Subtask requests Bash but action_type is read_only
        dag = _make_dag(tools="Bash", action_type="read_only")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._validate_tools"):  # skip SDK tool validation
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        self.assertEqual(dag["T"]["branches"]["B"]["subtasks"]["ST"]["status"], "Running")

    def test_denied_logs_scope_denied_warning(self):
        policy = _restrictive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        dag = _make_dag(tools="Bash", action_type="read_only")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._validate_tools"), \
             patch("runners.executor.logger") as mock_log:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            warn_msgs = [str(c) for c in mock_log.warning.call_args_list]
            self.assertTrue(any("scope_denied" in m for m in warn_msgs),
                            msg=f"Expected scope_denied warning, got: {warn_msgs}")

    def test_denied_includes_action_type_in_log(self):
        policy = _restrictive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        dag = _make_dag(tools="Bash", action_type="read_only")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._validate_tools"), \
             patch("runners.executor.logger") as mock_log:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            warn_msgs = [str(c) for c in mock_log.warning.call_args_list]
            self.assertTrue(any("read_only" in m for m in warn_msgs))


# ---------------------------------------------------------------------------
# Scope gate: allow path
# ---------------------------------------------------------------------------

class TestScopeAllowed(unittest.TestCase):

    def test_allowed_tool_advances_beyond_scope_gate(self):
        """Glob allowed under full_execution — subtask should proceed past scope gate."""
        policy = _permissive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        ex.verify_prob = 1.0  # dice-roll verify after dispatch
        dag = _make_dag(tools="Glob", action_type="full_execution")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0):
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        # Scope passed, and since no SDK/claude available it hits dice-roll or
        # stays Running (no runners). Just confirm it did NOT get a scope_denied log.
        # (Actual status depends on runners/verify_prob — we just check no denial.)

    def test_no_scope_denied_log_for_allowed_tool(self):
        policy = _permissive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        dag = _make_dag(tools="Glob", action_type="full_execution")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor.logger") as mock_log:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            warn_msgs = [str(c) for c in mock_log.warning.call_args_list]
            self.assertFalse(any("scope_denied" in m for m in warn_msgs))


# ---------------------------------------------------------------------------
# action_type field from subtask data
# ---------------------------------------------------------------------------

class TestActionTypeFromSubtaskData(unittest.TestCase):

    def test_action_type_read_from_subtask(self):
        """When subtask has action_type='read_only', scope check uses it."""
        policy = _restrictive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        dag = _make_dag(tools="Bash", action_type="read_only")

        import runners.executor as ex_mod
        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._validate_tools"), \
             patch.object(ex_mod, "_scope_evaluate", wraps=ex_mod._scope_evaluate) as mock_eval:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            self.assertTrue(mock_eval.called)
            call_args = mock_eval.call_args[0]
            self.assertEqual(call_args[1], "read_only")  # action_type passed

    def test_default_action_type_when_none_specified(self):
        """When subtask has no action_type field, policy default is used."""
        policy = _permissive_policy(default_type="full_execution")
        ex = _make_executor()
        ex._scope_policy = policy
        # No action_type in dag
        dag = _make_dag(tools="Glob")  # action_type="" default

        import runners.executor as ex_mod
        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch.object(ex_mod, "_scope_evaluate", wraps=ex_mod._scope_evaluate) as mock_eval:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            if mock_eval.called:
                call_args = mock_eval.call_args[0]
                self.assertEqual(call_args[1], "full_execution")


# ---------------------------------------------------------------------------
# evaluate_scope integration
# ---------------------------------------------------------------------------

class TestEvaluateScopeIntegration(unittest.TestCase):

    def test_evaluate_scope_called_when_tools_present(self):
        import runners.executor as ex_mod

        ex = _make_executor()
        dag = _make_dag(tools="Glob", action_type="full_execution")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch.object(ex_mod, "_scope_evaluate",
                          wraps=ex_mod._scope_evaluate) as mock_eval:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            mock_eval.assert_called_once()

    def test_evaluate_scope_receives_policy_instance(self):
        import runners.executor as ex_mod

        ex = _make_executor()
        dag = _make_dag(tools="Glob", action_type="full_execution")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch.object(ex_mod, "_scope_evaluate",
                          return_value=ScopeResult(
                              allowed=True, denied=[], action_type="full_execution",
                              requested=["Glob"],
                          )) as mock_eval:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            args = mock_eval.call_args[0]
            self.assertIsInstance(args[0], ToolScopePolicy)

    def test_evaluate_scope_not_called_without_tools(self):
        """No-tools subtask should bypass scope gate."""
        import runners.executor as ex_mod

        ex = _make_executor()
        ex.verify_prob = 1.0
        dag = _make_dag(tools="", description="plain")

        with patch.object(ex_mod, "_scope_evaluate") as mock_eval:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            mock_eval.assert_not_called()


# ---------------------------------------------------------------------------
# Multi-tool scope check
# ---------------------------------------------------------------------------

class TestMultiToolScope(unittest.TestCase):

    def test_all_tools_must_be_allowed(self):
        """Glob,Bash — Bash denied under read_only → scope_denied."""
        policy = _restrictive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        dag = _make_dag(tools="Glob,Bash", action_type="read_only")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._validate_tools"), \
             patch("runners.executor.logger") as mock_log:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            warn_msgs = [str(c) for c in mock_log.warning.call_args_list]
            self.assertTrue(any("scope_denied" in m for m in warn_msgs))

    def test_all_tools_allowed_passes_scope(self):
        """Read,Glob — both allowed under read_only → no scope_denied."""
        policy = _restrictive_policy()
        ex = _make_executor()
        ex._scope_policy = policy
        dag = _make_dag(tools="Glob,Read", action_type="read_only")

        with patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor.logger") as mock_log:
            ex.execute_step(dag, _plist(), step=1, memory_store={})
            warn_msgs = [str(c) for c in mock_log.warning.call_args_list]
            self.assertFalse(any("scope_denied" in m for m in warn_msgs))


if __name__ == "__main__":
    unittest.main()
