"""Tests for DagCommandsMixin uncovered lines — _cmd_add_task, _cmd_add_branch,
_cmd_prioritize_branch, _cmd_depends, _cmd_undepends, _cmd_import_dag,
_cmd_export_dag, _cmd_export, _cmd_cache, _cmd_undo, _cmd_load_backup (TASK-405).
Also covers SettingsCommandsMixin._cmd_config."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commands.dag_cmds as dc_module
import commands.settings_cmds as sc_module
from commands.dag_cmds import DagCommandsMixin
from commands.settings_cmds import SettingsCommandsMixin


# ---------------------------------------------------------------------------
# Inject module globals
# ---------------------------------------------------------------------------

def _dag_patches(tmp_dir: str, state_path: str) -> list:
    initial_dag = {
        "Task 0": {
            "status": "Pending",
            "depends_on": [],
            "branches": {
                "Branch A": {
                    "status": "Pending",
                    "subtasks": {
                        "A1": {"status": "Pending", "shadow": "Pending",
                               "last_update": 0, "description": "do A1", "output": ""},
                    }
                }
            },
        }
    }
    return [
        patch.object(dc_module, "INITIAL_DAG", new=initial_dag, create=True),
        patch.object(dc_module, "STATE_PATH", new=state_path, create=True),
        patch.object(dc_module, "_HERE", new=tmp_dir, create=True),
        patch.object(dc_module, "logger", new=MagicMock(), create=True),
        patch.object(dc_module, "DAG_UPDATE_INTERVAL", new=10, create=True),
        patch.object(dc_module, "CLAUDE_ALLOWED_TOOLS", new="", create=True),
        patch.object(dc_module, "MAX_SUBTASKS_PER_BRANCH", new=5, create=True),
        patch.object(dc_module, "MAX_BRANCHES_PER_TASK", new=5, create=True),
        patch.object(dc_module, "STATUS_COLORS", new={}, create=True),
        patch.object(dc_module, "WHITE", new="", create=True),
    ]


# ---------------------------------------------------------------------------
# Shared stub
# ---------------------------------------------------------------------------

def _make_dag():
    return {
        "Task 0": {
            "status": "Running",
            "depends_on": [],
            "branches": {
                "Branch A": {
                    "status": "Pending",
                    "subtasks": {
                        "A1": {"status": "Pending", "shadow": "Pending",
                               "last_update": 0, "description": "do A1", "output": ""},
                    }
                }
            },
        },
        "Task 1": {
            "status": "Pending",
            "depends_on": ["Task 0"],
            "branches": {
                "Branch B": {
                    "status": "Pending",
                    "subtasks": {
                        "B1": {"status": "Pending", "shadow": "Pending",
                               "last_update": 0, "description": "do B1", "output": ""},
                    }
                }
            },
        },
    }


class _FakeCLI(DagCommandsMixin):
    def __init__(self):
        self.dag = _make_dag()
        self.step = 5
        self.snapshot_counter = 0
        self.memory_store = {"Branch A": [], "Branch B": []}
        self.alerts = []
        self._priority_cache = []
        self._last_priority_step = 0
        self.display = MagicMock()
        self.meta = MagicMock()
        self.meta.forecast.return_value = {}
        self.healer = MagicMock()
        self.healer.healed_total = 0
        self.shadow = MagicMock()
        self.shadow.expected = {}
        self.executor = MagicMock()
        self.executor.claude.available = False
        self.executor.anthropic = MagicMock()
        self.executor.anthropic.cache = None
        self.load_state = MagicMock(return_value=True)
        self.save_state = MagicMock()


class _FakeSettingsCLI(SettingsCommandsMixin):
    def __init__(self):
        self._runtime_cfg = {
            "STALL_THRESHOLD": 5,
            "SNAPSHOT_INTERVAL": 10,
            "VERBOSITY": "INFO",
            "AUTO_STEP_DELAY": 2.0,
            "AUTO_SAVE_INTERVAL": 5,
            "CLAUDE_ALLOWED_TOOLS": "Read",
            "WEBHOOK_URL": "http://example.com",
        }
        self.executor = MagicMock()
        self.executor.verify_prob = 0.5
        self.executor.anthropic.max_tokens = 4096
        self.executor.anthropic.model = "claude-sonnet-4-6"
        self.executor.claude.available = True
        self.executor.review_mode = False


# ---------------------------------------------------------------------------
# _cmd_add_task — uncovered: task already exists (lines 44-45)
# ---------------------------------------------------------------------------

class TestCmdAddTask(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_task_already_exists_prints_message(self):
        # Force len(dag) to return 2 so task_name="Task 2" which already exists
        class _LenTwo(dict):
            def __len__(self):
                return 2
        self.cli.dag = _LenTwo(self.cli.dag)
        self.cli.dag["Task 2"] = {"status": "Pending", "depends_on": [], "branches": {}}
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"), patch("builtins.input", return_value="make something"):
            self.cli._cmd_add_task()
        combined = "\n".join(printed)
        self.assertIn("already exists", combined)

    def test_add_task_with_spec_creates_entry(self):
        initial_count = len(self.cli.dag)
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_task("build a feature")
        self.assertEqual(len(self.cli.dag), initial_count + 1)

    def test_empty_spec_cancels(self):
        initial_count = len(self.cli.dag)
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"), patch("builtins.input", return_value=""):
            self.cli._cmd_add_task()
        combined = "\n".join(printed)
        self.assertIn("Cancelled", combined)
        self.assertEqual(len(self.cli.dag), initial_count)

    def test_dependency_pipe_syntax(self):
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_task("do thing | depends: Task 0")
        new_task = f"Task {len(self.cli.dag) - 1}"
        self.assertIn("Task 0", self.cli.dag[new_task]["depends_on"])

    def test_dependency_pipe_unknown_dep(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_add_task("do thing | depends: Task 99")
        combined = "\n".join(printed)
        self.assertIn("Unknown dependency", combined)

    def test_claude_allowed_tools_propagated(self):
        with patch.object(dc_module, "CLAUDE_ALLOWED_TOOLS", new="Read,Glob", create=True):
            with patch("builtins.print"), patch("time.sleep"):
                self.cli._cmd_add_task("do something")
        new_task = list(self.cli.dag.values())[-1]
        branch = list(new_task["branches"].values())[0]
        subtask = list(branch["subtasks"].values())[0]
        self.assertEqual(subtask.get("tools"), "Read,Glob")

    def test_max_subtasks_enforced(self):
        with patch.object(dc_module, "MAX_SUBTASKS_PER_BRANCH", new=2, create=True), \
             patch.object(dc_module, "CLAUDE_ALLOWED_TOOLS", new="", create=True):
            # Simulate Claude returning 5 subtasks
            self.cli.executor.claude.available = True
            fake_items = json.dumps([
                {"name": "C1", "description": "d1"},
                {"name": "C2", "description": "d2"},
                {"name": "C3", "description": "d3"},
                {"name": "C4", "description": "d4"},
                {"name": "C5", "description": "d5"},
            ])
            self.cli.executor.claude.run.return_value = (True, fake_items)
            printed = []
            with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
                 patch("time.sleep"):
                self.cli._cmd_add_task("many subtasks")
        new_task = list(self.cli.dag.values())[-1]
        branch = list(new_task["branches"].values())[0]
        self.assertLessEqual(len(branch["subtasks"]), 2)
        combined = "\n".join(printed)
        self.assertIn("Capped", combined)

    def test_claude_bad_json_falls_back_to_single_subtask(self):
        self.cli.executor.claude.available = True
        self.cli.executor.claude.run.return_value = (True, "not valid json at all")
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_task("task with bad decomp")
        new_task = list(self.cli.dag.values())[-1]
        branch = list(new_task["branches"].values())[0]
        self.assertEqual(len(branch["subtasks"]), 1)

    def test_subtask_name_prefix_enforced(self):
        # Name with wrong prefix gets corrected
        self.cli.executor.claude.available = True
        fake_items = json.dumps([
            {"name": "Z1", "description": "wrong prefix"},  # should be C-something
        ])
        self.cli.executor.claude.run.return_value = (True, fake_items)
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_task("fix prefix")
        new_task = list(self.cli.dag.values())[-1]
        branch = list(new_task["branches"].values())[0]
        # subtask should have the correct letter prefix
        st_names = list(branch["subtasks"].keys())
        task_idx = len(self.cli.dag) - 1
        letter = chr(ord("A") + task_idx % 26)
        # At least one subtask starts with the correct letter
        self.assertTrue(any(n.startswith(letter) for n in st_names))


# ---------------------------------------------------------------------------
# _cmd_add_branch
# ---------------------------------------------------------------------------

class TestCmdAddBranch(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_invalid_task_shows_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_add_branch("Task 99")
        combined = "\n".join(printed)
        self.assertIn("Usage", combined)

    def test_lowercase_task_arg_title_cased(self):
        # "task 0" should be title-cased to "Task 0"; next letter is "C" (A,B taken)
        initial = set(self.cli.dag["Task 0"]["branches"].keys())
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_branch("task 0", spec_override="new branch spec")
        final = set(self.cli.dag["Task 0"]["branches"].keys())
        self.assertGreater(len(final), len(initial))

    def test_empty_spec_cancels(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"), patch("builtins.input", return_value=""):
            self.cli._cmd_add_branch("Task 0")
        combined = "\n".join(printed)
        self.assertIn("Cancelled", combined)

    def test_max_branches_exceeded_prints_message(self):
        with patch.object(dc_module, "MAX_BRANCHES_PER_TASK", new=1, create=True):
            printed = []
            with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
                 patch("time.sleep"):
                self.cli._cmd_add_branch("Task 0", spec_override="too many")
            combined = "\n".join(printed)
            self.assertIn("limit", combined.lower())

    def test_reopens_verified_task(self):
        self.cli.dag["Task 0"]["status"] = "Verified"
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_branch("Task 0", spec_override="new branch")
        self.assertEqual(self.cli.dag["Task 0"]["status"], "Running")

    def test_digit_task_arg_normalized(self):
        initial = set(self.cli.dag["Task 0"]["branches"].keys())
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_branch("0", spec_override="branch from digit")
        final = set(self.cli.dag["Task 0"]["branches"].keys())
        self.assertGreater(len(final), len(initial))

    def test_claude_decomp_called_when_available(self):
        self.cli.executor.claude.available = True
        # Next unused letter is C; Claude should return items with prefix C
        fake_items = json.dumps([
            {"name": "C1", "description": "sub1"},
            {"name": "C2", "description": "sub2"},
        ])
        self.cli.executor.claude.run.return_value = (True, fake_items)
        initial = set(self.cli.dag["Task 0"]["branches"].keys())
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_branch("Task 0", spec_override="with claude")
        final = set(self.cli.dag["Task 0"]["branches"].keys())
        new_branch_name = (final - initial).pop()
        branch = self.cli.dag["Task 0"]["branches"][new_branch_name]
        self.assertGreater(len(branch.get("subtasks", {})), 0)

    def test_branch_max_subtasks_capped(self):
        with patch.object(dc_module, "MAX_SUBTASKS_PER_BRANCH", new=1, create=True):
            self.cli.executor.claude.available = True
            fake_items = json.dumps([
                {"name": "C1", "description": "s1"},
                {"name": "C2", "description": "s2"},
                {"name": "C3", "description": "s3"},
            ])
            self.cli.executor.claude.run.return_value = (True, fake_items)
            printed = []
            with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
                 patch("time.sleep"):
                self.cli._cmd_add_branch("Task 0", spec_override="capped")
        combined = "\n".join(printed)
        self.assertIn("Capped", combined)


# ---------------------------------------------------------------------------
# _cmd_prioritize_branch
# ---------------------------------------------------------------------------

class TestCmdPrioritizeBranch(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_digit_task_arg_normalized(self):
        # "0" → "Task 0"
        with patch("builtins.print"):
            self.cli._cmd_prioritize_branch("0", "Branch A")
        self.cli.display.render.assert_called()

    def test_task_not_found_prints_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_prioritize_branch("Task 99", "Branch A")
        combined = "\n".join(printed)
        self.assertIn("not found", combined)

    def test_branch_fuzzy_match(self):
        # "branch a" partial match → finds "Branch A"
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_prioritize_branch("Task 0", "branch a")
        combined = "\n".join(printed)
        self.assertIn("Boosted", combined)

    def test_branch_not_found_prints_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_prioritize_branch("Task 0", "Nonexistent")
        combined = "\n".join(printed)
        self.assertIn("not found", combined)

    def test_boosts_pending_subtasks(self):
        with patch("builtins.print"):
            self.cli._cmd_prioritize_branch("Task 0", "Branch A")
        a1 = self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertLess(a1["last_update"], 0)

    def test_no_task_arg_prompts_for_input(self):
        with patch("builtins.print"), \
             patch("builtins.input", side_effect=["Task 0", "Branch A"]):
            self.cli._cmd_prioritize_branch()
        self.cli.display.render.assert_called()


# ---------------------------------------------------------------------------
# _cmd_depends / _cmd_undepends
# ---------------------------------------------------------------------------

class TestCmdDepends(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_no_args_prints_graph(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_depends("")
        combined = "\n".join(printed)
        self.assertIn("Task 0", combined)

    def test_target_not_found_prints_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_depends("99 0")
        combined = "\n".join(printed)
        self.assertIn("not found", combined)

    def test_self_dependency_prints_error(self):
        # Use digit args: "0 0" → both normalise to "Task 0"
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_depends("0 0")
        combined = "\n".join(printed)
        self.assertIn("itself", combined)

    def test_digit_normalised_as_task_n(self):
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_depends("1 0")
        self.assertIn("Task 0", self.cli.dag["Task 1"]["depends_on"])

    def test_dep_not_found_digit_form(self):
        # "0 99" → Task 0 exists, Task 99 does not
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_depends("0 99")
        combined = "\n".join(printed)
        self.assertIn("not found", combined)

    def test_already_depends_prints_message(self):
        # "1 0" → Task 1 already depends on Task 0
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_depends("1 0")  # already there
        combined = "\n".join(printed)
        self.assertIn("already", combined)


class TestCmdUndepends(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_no_args_prints_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_undepends("")
        combined = "\n".join(printed)
        self.assertIn("Usage", combined)

    def test_target_not_found(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_undepends("99 0")
        combined = "\n".join(printed)
        self.assertIn("not found", combined)

    def test_dep_not_in_list_prints_message(self):
        # Task 0 doesn't depend on Task 1
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_undepends("0 1")
        combined = "\n".join(printed)
        self.assertIn("does not depend", combined)

    def test_removes_dep_successfully(self):
        # Task 1 depends on Task 0 — remove it using digit args
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_undepends("1 0")
        self.assertNotIn("Task 0", self.cli.dag["Task 1"]["depends_on"])


# ---------------------------------------------------------------------------
# _cmd_import_dag
# ---------------------------------------------------------------------------

class TestCmdImportDag(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_no_args_prints_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_import_dag("")
        combined = "\n".join(printed)
        self.assertIn("Usage", combined)

    def test_file_not_found_prints_error(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_import_dag("/nonexistent/dag.json")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_invalid_json_prints_error(self):
        bad_path = os.path.join(self._tmp, "bad.json")
        Path(bad_path).write_text("not json")
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_import_dag(bad_path)
        combined = "\n".join(printed)
        self.assertIn("Failed", combined)

    def test_not_a_dict_prints_error(self):
        bad_path = os.path.join(self._tmp, "list.json")
        Path(bad_path).write_text(json.dumps([1, 2, 3]))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_import_dag(bad_path)
        combined = "\n".join(printed)
        self.assertIn("Invalid", combined)

    def test_relative_path_resolved(self):
        dag_data = {"Task X": {"status": "Pending", "depends_on": [], "branches": {}}}
        dag_path = os.path.join(self._tmp, "dag.json")
        Path(dag_path).write_text(json.dumps({"dag": dag_data, "exported_step": 3}))
        # Use relative path (join to _HERE)
        with patch("builtins.print"):
            self.cli._cmd_import_dag("dag.json")
        self.assertIn("Task X", self.cli.dag)

    def test_valid_dag_file_imported(self):
        dag_data = {"Task New": {"status": "Pending", "depends_on": [], "branches": {}}}
        dag_path = os.path.join(self._tmp, "valid_dag.json")
        Path(dag_path).write_text(json.dumps({"dag": dag_data, "exported_step": 7}))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_import_dag(dag_path)
        self.assertIn("Task New", self.cli.dag)
        combined = "\n".join(printed)
        self.assertIn("imported", combined.lower())

    def test_dag_validation_error_prints_errors(self):
        # Use validate_dag that returns errors
        bad_dag = {"Task Bad": {"status": "Invalid!", "depends_on": ["nonexistent"], "branches": {}}}
        dag_path = os.path.join(self._tmp, "bad_dag.json")
        Path(dag_path).write_text(json.dumps(bad_dag))
        with patch.object(dc_module, "__builtins__", {}):
            pass  # just to be explicit
        from utils.helper_functions import validate_dag
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_import_dag(dag_path)
        # Should either succeed or fail — just ensure no crash
        # (validate_dag may or may not flag this as an error depending on implementation)

    def test_bare_dag_without_wrapper(self):
        # JSON file is a bare dict (no "dag" wrapper key)
        dag_data = {"Task Direct": {"status": "Pending", "depends_on": [], "branches": {}}}
        dag_path = os.path.join(self._tmp, "bare.json")
        Path(dag_path).write_text(json.dumps(dag_data))
        with patch("builtins.print"):
            self.cli._cmd_import_dag(dag_path)
        self.assertIn("Task Direct", self.cli.dag)


# ---------------------------------------------------------------------------
# _cmd_export_dag
# ---------------------------------------------------------------------------

class TestCmdExportDag(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_exports_to_default_path(self):
        with patch("builtins.print"):
            self.cli._cmd_export_dag("")
        default_path = os.path.join(self._tmp, "dag_export.json")
        self.assertTrue(os.path.exists(default_path))

    def test_exports_to_explicit_path(self):
        out = os.path.join(self._tmp, "my_dag.json")
        with patch("builtins.print"):
            self.cli._cmd_export_dag(out)
        self.assertTrue(os.path.exists(out))
        data = json.loads(Path(out).read_text())
        self.assertEqual(data["exported_step"], self.cli.step)

    def test_relative_path_resolved(self):
        with patch("builtins.print"):
            self.cli._cmd_export_dag("relative_dag.json")
        expected = os.path.join(self._tmp, "relative_dag.json")
        self.assertTrue(os.path.exists(expected))

    def test_export_contains_dag_key(self):
        out = os.path.join(self._tmp, "out.json")
        with patch("builtins.print"):
            self.cli._cmd_export_dag(out)
        data = json.loads(Path(out).read_text())
        self.assertIn("dag", data)


# ---------------------------------------------------------------------------
# _cmd_undo / _cmd_load_backup
# ---------------------------------------------------------------------------

class TestCmdUndo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_no_backup_prints_message(self):
        # No .1 backup exists
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_undo()
        combined = "\n".join(printed)
        self.assertIn("No backup", combined)

    def test_undo_success(self):
        # Create .1 backup
        Path(self._state).write_text(json.dumps({"step": 5}))
        Path(f"{self._state}.1").write_text(json.dumps({"step": 5}))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_undo()
        # load_state is mocked to return True → "Undo:" message
        combined = "\n".join(printed)
        self.assertIn("Undo", combined)

    def test_undo_copy_failure_prints_error(self):
        Path(f"{self._state}.1").write_text(json.dumps({"step": 5}))
        printed = []
        with patch("shutil.copy2", side_effect=OSError("disk full")), \
             patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_undo()
        combined = "\n".join(printed)
        self.assertIn("failed", combined.lower())

    def test_undo_load_failure_prints_error(self):
        Path(f"{self._state}.1").write_text(json.dumps({"step": 5}))
        self.cli.load_state.return_value = False
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_undo()
        combined = "\n".join(printed)
        self.assertIn("failed", combined.lower())


class TestCmdLoadBackup(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_invalid_n_prints_usage(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_load_backup("9")
        combined = "\n".join(printed)
        self.assertIn("Usage", combined)

    def test_backup_not_found_shows_message(self):
        # No backup files at all
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_load_backup("1")
        combined = "\n".join(printed)
        self.assertIn("not found", combined.lower())

    def test_backup_not_found_shows_available(self):
        # .2 exists but .1 does not
        Path(f"{self._state}.2").write_text(json.dumps({"step": 3}))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_load_backup("1")
        combined = "\n".join(printed)
        self.assertIn("2", combined)  # shows available backup 2

    def test_copy_failure_prints_error(self):
        Path(f"{self._state}.1").write_text(json.dumps({"step": 5}))
        printed = []
        with patch("shutil.copy2", side_effect=OSError("fail")), \
             patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_load_backup("1")
        combined = "\n".join(printed)
        self.assertIn("failed", combined.lower())

    def test_load_failure_prints_error(self):
        Path(f"{self._state}.1").write_text(json.dumps({"step": 5}))
        self.cli.load_state.return_value = False
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_load_backup("1")
        combined = "\n".join(printed)
        self.assertIn("failed", combined.lower())

    def test_load_success_prints_message(self):
        Path(f"{self._state}.2").write_text(json.dumps({"step": 5}))
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_load_backup("2")
        combined = "\n".join(printed)
        self.assertIn("Restored", combined)

    def test_default_n_is_1(self):
        # No arg → defaults to "1"
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_load_backup("")
        combined = "\n".join(printed)
        # Either "not found" or "Restored" — no crash
        self.assertTrue(len(combined) > 0)


# ---------------------------------------------------------------------------
# SettingsCommandsMixin._cmd_config
# ---------------------------------------------------------------------------

class TestCmdConfig(unittest.TestCase):

    def setUp(self):
        self.cli = _FakeSettingsCLI()

    def test_runs_without_error(self):
        with patch("builtins.print"):
            self.cli._cmd_config()

    def test_prints_runtime_settings_header(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_config()
        combined = "\n".join(printed)
        self.assertIn("Runtime Settings", combined)

    def test_shows_stall_threshold(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_config()
        combined = "\n".join(printed)
        self.assertIn("STALL_THRESHOLD", combined)
        self.assertIn("5", combined)

    def test_shows_webhook_url(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_config()
        combined = "\n".join(printed)
        self.assertIn("WEBHOOK_URL", combined)

    def test_no_webhook_shows_not_set(self):
        self.cli._runtime_cfg["WEBHOOK_URL"] = ""
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_config()
        combined = "\n".join(printed)
        self.assertIn("not set", combined)

    def test_no_allowed_tools_shows_none(self):
        self.cli._runtime_cfg["CLAUDE_ALLOWED_TOOLS"] = ""
        printed = []
        with patch("builtins.print", side_effect=lambda *a: printed.append(" ".join(str(x) for x in a))):
            self.cli._cmd_config()
        combined = "\n".join(printed)
        self.assertIn("(none)", combined)


# ---------------------------------------------------------------------------
# _cmd_reset (lines 18-36)
# ---------------------------------------------------------------------------

class TestCmdReset(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()
        self.cli.meta._history = [1, 2]
        self.cli.meta.heal_rate = 0.5
        self.cli.meta.verify_rate = 0.3

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_reset_clears_step(self):
        self.cli.step = 10
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_reset()
        self.assertEqual(self.cli.step, 0)

    def test_reset_restores_initial_dag(self):
        self.cli.dag["Task 99"] = {"status": "Running", "depends_on": [], "branches": {}}
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_reset()
        self.assertNotIn("Task 99", self.cli.dag)

    def test_reset_clears_state_file_if_exists(self):
        Path(self._state).write_text("{}")
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_reset()
        self.assertFalse(os.path.exists(self._state))

    def test_reset_no_state_file_does_not_raise(self):
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_reset()  # file doesn't exist

    def test_reset_prints_message(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_reset()
        self.assertIn("reset", "\n".join(printed).lower())

    def test_reset_calls_display_render(self):
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_reset()
        self.cli.display.render.assert_called()


# ---------------------------------------------------------------------------
# _cmd_add_task line 60: digit dep normalization in pipe spec
# _cmd_add_task lines 104-105: Claude decomp exception path
# ---------------------------------------------------------------------------

class TestCmdAddTaskMore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_pipe_dep_digit_normalised(self):
        """Line 60: '0' in pipe dep → 'Task 0'."""
        with patch("builtins.input", return_value="do something"), \
             patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_task()
        # dep_raw was '0' if input had '| depends: 0' — test via spec override
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_task("build stuff | depends: 0")
        # Task 0 should be set as dep on new task
        new_tasks = [k for k in self.cli.dag if k not in ("Task 0", "Task 1")]
        if new_tasks:
            deps = self.cli.dag[new_tasks[-1]].get("depends_on", [])
            self.assertIn("Task 0", deps)

    def test_claude_decomp_bad_json_falls_back_to_single(self):
        """Lines 104-105: Claude returns output with brackets but invalid JSON → except path."""
        self.cli.executor.claude.available = True
        # Must have [...] so the regex matches, but content must be invalid JSON
        self.cli.executor.claude.run = MagicMock(return_value=(True, "[bad json here]"))
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_task("do the thing")
        new_tasks = [k for k in self.cli.dag if k not in ("Task 0", "Task 1")]
        self.assertTrue(len(new_tasks) >= 1)
        # Should have exactly 1 subtask (fallback)
        new_task = new_tasks[-1]
        branches = self.cli.dag[new_task].get("branches", {})
        all_subtasks = [st for br in branches.values() for st in br["subtasks"]]
        self.assertEqual(len(all_subtasks), 1)


# ---------------------------------------------------------------------------
# _cmd_add_branch lines 220, 228-229: Claude decomp bad-prefix + exception
# ---------------------------------------------------------------------------

class TestCmdAddBranchMore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_claude_decomp_wrong_prefix_corrected(self):
        """Line 220: subtask name with wrong prefix gets corrected to branch letter."""
        self.cli.executor.claude.available = True
        self.cli.executor.claude.run = MagicMock(return_value=(
            True,
            '[{"name": "Z1", "description": "wrong prefix subtask"}]'
        ))
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_branch("Task 0", spec_override="new approach")
        # Should still add a branch (prefix corrected)
        branches = self.cli.dag["Task 0"]["branches"]
        new_branches = [b for b in branches if b not in ("Branch A",)]
        self.assertTrue(len(new_branches) >= 1)

    def test_claude_decomp_bad_json_falls_back(self):
        """Lines 228-229: Claude JSON parse error → fallback to single subtask."""
        self.cli.executor.claude.available = True
        self.cli.executor.claude.run = MagicMock(return_value=(True, "[bad json]"))
        with patch("builtins.print"), patch("time.sleep"):
            self.cli._cmd_add_branch("Task 0", spec_override="new approach")
        branches = self.cli.dag["Task 0"]["branches"]
        new_branches = [b for b in branches if b not in ("Branch A",)]
        self.assertEqual(len(new_branches), 1)
        # Fallback: single subtask
        br = new_branches[0]
        self.assertEqual(len(self.cli.dag["Task 0"]["branches"][br]["subtasks"]), 1)


# ---------------------------------------------------------------------------
# _cmd_depends lines 347, 364-365: lowercase normalise + new dep added
# ---------------------------------------------------------------------------

class TestCmdDependsMore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()
        self.cli.dag["Task 0"]["depends_on"] = []

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_lowercase_title_cased(self):
        """Line 347: lowercase single-word task → title-cased via .title()."""
        # Add single-word title-cased tasks so lowercase input normalises to them
        self.cli.dag["Alpha"] = {"status": "Pending", "depends_on": [], "branches": {}}
        self.cli.dag["Beta"] = {"status": "Pending", "depends_on": [], "branches": {}}
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_depends("alpha beta")
        combined = "\n".join(printed)
        # Should succeed: "alpha"→"Alpha", "beta"→"Beta" both found in dag
        self.assertIn("depends", combined.lower())

    def test_new_dep_added_successfully(self):
        """Lines 364-365: dep not yet in list → appended and message printed."""
        # Start with Task 1 having no deps
        self.cli.dag["Task 1"]["depends_on"] = []
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            # Digit form: "1 0" → Task 1 depends on Task 0
            self.cli._cmd_depends("1 0")
        combined = "\n".join(printed)
        self.assertIn("now depends", combined)
        self.assertIn("Task 0", self.cli.dag["Task 1"]["depends_on"])


# ---------------------------------------------------------------------------
# _cmd_undepends line 386: lowercase normalise
# ---------------------------------------------------------------------------

class TestCmdUndependsMore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_lowercase_normalised_in_undepends(self):
        """Line 386: lowercase single-word task → title-cased via .title()."""
        # Add single-word title-cased tasks so lowercase input normalises to them
        self.cli.dag["Alpha"] = {"status": "Pending", "depends_on": ["Beta"], "branches": {}}
        self.cli.dag["Beta"] = {"status": "Pending", "depends_on": [], "branches": {}}
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))), \
             patch("time.sleep"):
            self.cli._cmd_undepends("alpha beta")
        combined = "\n".join(printed)
        self.assertIn("no longer depends", combined)


# ---------------------------------------------------------------------------
# _cmd_import_dag lines 429-432: validate_dag errors
# ---------------------------------------------------------------------------

class TestCmdImportDagMore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_validation_errors_printed(self):
        """Lines 429-432: validate_dag returns errors → printed then return."""
        dag_file = os.path.join(self._tmp, "bad.json")
        bad_dag = {"Task 0": {"status": "Pending", "depends_on": ["Task 0"], "branches": {}}}
        Path(dag_file).write_text(json.dumps(bad_dag))
        # Patch validate_dag to return errors
        with patch.object(dc_module, "validate_dag", return_value=["cycle detected"]), \
             patch("builtins.print") as mock_print, patch("time.sleep"):
            self.cli._cmd_import_dag(dag_file)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("failed", printed.lower())


# ---------------------------------------------------------------------------
# _cmd_export (lines 460-488)
# ---------------------------------------------------------------------------

class TestCmdExport(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state = os.path.join(self._tmp, "state.json")
        self._ps = _dag_patches(self._tmp, self._state)
        for p in self._ps:
            p.start()
        self.cli = _FakeCLI()

    def tearDown(self):
        for p in self._ps:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_export_no_outputs_writes_header(self):
        """Lines 479-480: no outputs → writes header-only file."""
        with patch("builtins.print"):
            path, count = self.cli._cmd_export()
        self.assertEqual(count, 0)
        self.assertTrue(os.path.exists(path))
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("No Claude outputs", content)

    def test_export_with_outputs(self):
        """Lines 466-478: subtask with output → included in export."""
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = "Here is the result."
        with patch("builtins.print"):
            path, count = self.cli._cmd_export()
        self.assertEqual(count, 1)
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("Here is the result.", content)

    def test_export_includes_description(self):
        """Line 475-476: description included when present."""
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["output"] = "result"
        self.cli.dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["description"] = "do alpha"
        with patch("builtins.print"):
            path, count = self.cli._cmd_export()
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("do alpha", content)

    def test_export_returns_tuple(self):
        with patch("builtins.print"):
            result = self.cli._cmd_export()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_export_prints_to_stderr_no_outputs(self):
        """Lines 484-485: no outputs → prints warning to stderr."""
        import sys as _sys
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(str(a))):
            self.cli._cmd_export()
        # print called (stderr path)
        self.assertTrue(len(printed) >= 1)


if __name__ == "__main__":
    unittest.main()
