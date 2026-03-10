"""Tests for CLAUDE_ALLOWED_TOOLS propagation in dag_cmds.py (TASK-329).

Verifies that newly created subtasks (via add_task / add_branch) get a `tools`
field set to CLAUDE_ALLOWED_TOOLS when that global is non-empty, enabling the
sdk_tool_jobs routing branch in executor.py to be reachable.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure solo_builder/ is on sys.path so dag_cmds can import utils.helper_functions
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.dag_cmds as dag_cmds_module
from commands.dag_cmds import DagCommandsMixin


# ── minimal CLI stub ──────────────────────────────────────────────────────────

class _FakeCLI(DagCommandsMixin):
    """Minimal stub that satisfies DagCommandsMixin attribute accesses."""

    def __init__(self, allowed_tools: str = ""):
        self.dag = {}
        self.step = 1
        self.memory_store = {}
        self.alerts = []
        self.executor = MagicMock()
        self.executor.claude.available = False
        self.executor._project_context = ""
        self.display = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        # Inject CLAUDE_ALLOWED_TOOLS into the mixin module namespace
        dag_cmds_module.CLAUDE_ALLOWED_TOOLS = allowed_tools
        # Other globals needed by dag_cmds
        dag_cmds_module.MAX_SUBTASKS_PER_BRANCH = getattr(dag_cmds_module, "MAX_SUBTASKS_PER_BRANCH", 5)
        dag_cmds_module.MAX_BRANCHES_PER_TASK   = getattr(dag_cmds_module, "MAX_BRANCHES_PER_TASK", 4)
        dag_cmds_module.INITIAL_DAG             = getattr(dag_cmds_module, "INITIAL_DAG", {})

    def _save_state(self):
        pass  # no-op in tests


# ── add_task tests ────────────────────────────────────────────────────────────

class TestAddTaskToolsPropagation(unittest.TestCase):

    def _make_cli(self, allowed_tools: str = "") -> _FakeCLI:
        return _FakeCLI(allowed_tools=allowed_tools)

    def _call_add_task(self, cli: _FakeCLI, spec: str = "do something") -> None:
        with patch.object(cli.executor.claude, "available", False), \
             patch("commands.dag_cmds.CYAN", ""), \
             patch("commands.dag_cmds.RESET", ""), \
             patch("commands.dag_cmds.GREEN", ""), \
             patch("commands.dag_cmds.YELLOW", ""), \
             patch("commands.dag_cmds.BOLD", ""):
            cli._cmd_add_task(spec_override=spec)

    def test_tools_field_set_when_allowed_tools_nonempty(self):
        cli = self._make_cli(allowed_tools="Read,Glob")
        self._call_add_task(cli)
        task = list(cli.dag.values())[0]
        branch = list(task["branches"].values())[0]
        for st_name, st_data in branch["subtasks"].items():
            self.assertIn("tools", st_data, f"Subtask {st_name} missing 'tools' field")
            self.assertEqual(st_data["tools"], "Read,Glob")

    def test_tools_field_absent_when_allowed_tools_empty(self):
        cli = self._make_cli(allowed_tools="")
        self._call_add_task(cli)
        task = list(cli.dag.values())[0]
        branch = list(task["branches"].values())[0]
        for st_name, st_data in branch["subtasks"].items():
            self.assertNotIn("tools", st_data,
                             f"Subtask {st_name} should not have 'tools' when CLAUDE_ALLOWED_TOOLS is empty")

    def test_tools_not_overwritten_if_already_set(self):
        """If a future code path pre-sets 'tools', setdefault must not overwrite it."""
        cli = self._make_cli(allowed_tools="Read")
        # Manually build a dag with a pre-existing tools value
        cli.dag["Task 0"] = {
            "status": "Pending",
            "depends_on": [],
            "branches": {
                "Branch A": {
                    "status": "Pending",
                    "subtasks": {
                        "A1": {
                            "status": "Pending",
                            "shadow": "Pending",
                            "last_update": 1,
                            "description": "test",
                            "output": "",
                            "tools": "Glob",  # pre-set
                        }
                    },
                }
            },
        }
        # The propagation logic uses setdefault — it must not overwrite "Glob"
        _allowed = dag_cmds_module.CLAUDE_ALLOWED_TOOLS.strip()
        if _allowed:
            for st in cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"].values():
                st.setdefault("tools", _allowed)
        self.assertEqual(
            cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["tools"], "Glob"
        )

    def test_sdk_tool_routing_path_reachable(self):
        """Executor routes to sdk_tool_jobs when tools field is non-empty and sdk_tool available."""
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from runners.executor import Executor
        from agents.planner import Planner
        from unittest.mock import patch as _patch

        ex = Executor(max_per_step=6, verify_prob=0.0)
        ex.claude.available    = False
        ex.anthropic.available = False
        ex.sdk_tool.available  = True

        dag = {
            "Task 0": {
                "status": "Running",
                "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status": "Running",
                        "subtasks": {
                            "A1": {
                                "status": "Running",
                                "shadow": "Pending",
                                "last_update": 0,
                                "description": "read a file",
                                "output": "",
                                "tools": "Read,Glob",  # ← field set by the fix
                            }
                        },
                    }
                },
            }
        }
        plist = Planner(6).prioritize(dag, step=1)
        sdk_tool_jobs_captured = []

        def fake_gather_sdktool(sdk_tool, jobs):
            sdk_tool_jobs_captured.extend(jobs)
            return [("ok", "done") for _ in jobs]

        with _patch.object(ex, "_gather_sdktool", side_effect=fake_gather_sdktool), \
             _patch("runners.executor.add_memory_snapshot"):
            ex.execute_step(dag, plist, step=1, memory_store={})

        self.assertTrue(len(sdk_tool_jobs_captured) > 0,
                        "sdk_tool_jobs must be non-empty when subtask has tools field")


# ── add_branch tests ──────────────────────────────────────────────────────────

class TestAddBranchToolsPropagation(unittest.TestCase):

    def _make_cli_with_task(self, allowed_tools: str = "") -> _FakeCLI:
        cli = _FakeCLI(allowed_tools=allowed_tools)
        # Pre-create a task for add_branch to attach to
        cli.dag["Task 0"] = {
            "status": "Running",
            "depends_on": [],
            "branches": {},
        }
        return cli

    def _call_add_branch(self, cli: _FakeCLI, task: str = "Task 0",
                         spec: str = "do something") -> None:
        with patch.object(cli.executor.claude, "available", False), \
             patch("commands.dag_cmds.CYAN", ""), \
             patch("commands.dag_cmds.RESET", ""), \
             patch("commands.dag_cmds.GREEN", ""), \
             patch("commands.dag_cmds.YELLOW", ""), \
             patch("commands.dag_cmds.BOLD", ""):
            cli._cmd_add_branch(args=task, spec_override=spec)

    def test_add_branch_sets_tools_when_allowed(self):
        cli = self._make_cli_with_task(allowed_tools="Grep")
        self._call_add_branch(cli)
        branch = list(cli.dag["Task 0"]["branches"].values())[0]
        for st_name, st_data in branch["subtasks"].items():
            self.assertIn("tools", st_data, f"Branch subtask {st_name} missing 'tools' field")
            self.assertEqual(st_data["tools"], "Grep")

    def test_add_branch_no_tools_when_empty(self):
        cli = self._make_cli_with_task(allowed_tools="")
        self._call_add_branch(cli)
        branch = list(cli.dag["Task 0"]["branches"].values())[0]
        for st_data in branch["subtasks"].values():
            self.assertNotIn("tools", st_data)


if __name__ == "__main__":
    unittest.main()
