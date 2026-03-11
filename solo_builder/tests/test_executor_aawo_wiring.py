"""Tests for AAWO enrich_subtask wiring in Executor.execute_step."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.executor import Executor


def _make_dag(status="Running", tools="", action_type=""):
    return {
        "Task-A": {
            "branches": {
                "Branch-1": {
                    "subtasks": {
                        "ST-1": {
                            "name": "ST-1",
                            "status": status,
                            "description": "run tests for the feature",
                            "output": "",
                            "history": [],
                            "tools": tools,
                            "action_type": action_type,
                        }
                    }
                }
            }
        }
    }


def _plist():
    return [("Task-A", "Branch-1", "ST-1", 0)]


def _make_executor(aawo_repo_path=None, verify_prob=0.0):
    ex = Executor(max_per_step=1, verify_prob=verify_prob, aawo_repo_path=aawo_repo_path)
    ex.claude.available = False
    ex.anthropic.available = False
    ex.sdk_tool.available = False
    return ex


class TestExecutorAawoWiring(unittest.TestCase):

    def test_enrich_called_when_subtask_has_no_tools_and_path_set(self):
        ex = _make_executor(aawo_repo_path="/some/repo")
        dag = _make_dag(status="Running", tools="")
        with patch("utils.aawo_bridge.enrich_subtask") as mock_enrich, \
             patch("runners.executor._write_step_metrics"):
            mock_enrich.side_effect = lambda st, *a, **kw: st
            ex.execute_step(dag, _plist(), step=1, memory_store={})
        mock_enrich.assert_called_once()

    def test_enrich_not_called_when_aawo_repo_path_is_none(self):
        ex = _make_executor(aawo_repo_path=None)
        dag = _make_dag(status="Running", tools="")
        with patch("utils.aawo_bridge.enrich_subtask") as mock_enrich, \
             patch("runners.executor._write_step_metrics"):
            ex.execute_step(dag, _plist(), step=1, memory_store={})
        mock_enrich.assert_not_called()

    def test_enrich_not_called_when_subtask_already_has_tools(self):
        ex = _make_executor(aawo_repo_path="/some/repo")
        dag = _make_dag(status="Running", tools="Read,Grep,Glob")
        with patch("utils.aawo_bridge.enrich_subtask") as mock_enrich, \
             patch("runners.executor._write_step_metrics"):
            ex.execute_step(dag, _plist(), step=1, memory_store={})
        mock_enrich.assert_not_called()

    def test_aawo_routing_key_present_after_enrichment(self):
        ex = _make_executor(aawo_repo_path="/some/repo")
        dag = _make_dag(status="Running", tools="")

        def _inject_routing(st, *a, **kw):
            st["tools"] = "Read,Grep,Glob"
            st["action_type"] = "read_only"
            st["_aawo_routing"] = {"agent_id": "testing_agent", "score": 1.0, "fallback": False}
            return st

        with patch("utils.aawo_bridge.enrich_subtask", side_effect=_inject_routing), \
             patch("runners.executor._write_step_metrics"):
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertIn("_aawo_routing", st)
        self.assertEqual(st["_aawo_routing"]["agent_id"], "testing_agent")

    def test_enriched_tools_flow_through_to_tool_validation(self):
        """After AAWO enrichment, the tools string is validated (not silently dropped)."""
        ex = _make_executor(aawo_repo_path="/some/repo")
        dag = _make_dag(status="Running", tools="")

        def _inject_invalid(st, *a, **kw):
            st["tools"] = "Read,INVALID_TOOL"
            return st

        with patch("utils.aawo_bridge.enrich_subtask", side_effect=_inject_invalid), \
             patch("runners.executor._write_step_metrics"):
            # Invalid tools → executor logs error and skips the subtask (stays Running)
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        # Subtask stays Running because validation failed
        self.assertEqual(st["status"], "Running")

    def test_enrich_repo_path_passed_to_bridge(self):
        """repo_path kwarg is forwarded to enrich_subtask."""
        ex = _make_executor(aawo_repo_path="/my/git/root")
        dag = _make_dag(status="Running", tools="")
        calls = []

        def _capture(st, desc, repo_path="."):
            calls.append(repo_path)
            return st

        with patch("utils.aawo_bridge.enrich_subtask", side_effect=_capture), \
             patch("runners.executor._write_step_metrics"):
            ex.execute_step(dag, _plist(), step=1, memory_store={})

        self.assertEqual(calls, ["/my/git/root"])


if __name__ == "__main__":
    unittest.main()
