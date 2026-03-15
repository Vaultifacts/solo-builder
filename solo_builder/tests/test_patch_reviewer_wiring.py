"""Tests for PatchReviewer wiring in executor and TriggerRegistry refactor."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestPatchReviewerExecutorWiring(unittest.TestCase):
    """Executor instantiates PatchReviewer and calls review_step after each step."""

    def _make_executor(self):
        from runners.executor import Executor
        return Executor(max_per_step=2, verify_prob=0.0)

    def test_executor_has_patch_reviewer(self):
        from runners.executor import Executor
        from agents.patch_reviewer import PatchReviewer
        e = Executor(max_per_step=1, verify_prob=0.0)
        self.assertIsInstance(e._patch_reviewer, PatchReviewer)

    def test_review_step_called_when_actions_nonempty(self):
        from runners.executor import Executor
        e = Executor(max_per_step=2, verify_prob=1.0)
        call_args = []
        original_review = e._patch_reviewer.review_step

        def capture(*a, **kw):
            call_args.append(a)
            return original_review(*a, **kw)

        e._patch_reviewer.review_step = capture

        dag = {
            "T1": {
                "status": "Running",
                "branches": {
                    "B1": {
                        "status": "Running",
                        "subtasks": {
                            "S1": {"status": "Running", "description": "do thing"},
                        },
                    }
                },
            }
        }
        priority = [("T1", "B1", "S1", 1)]
        with patch.object(e.anthropic, "available", False), \
             patch.object(e.sdk_tool,  "available", False), \
             patch.object(e.claude,    "available", False):
            actions = e.execute_step(dag, priority, step=1, memory_store={})

        if actions:
            self.assertTrue(len(call_args) >= 1, "review_step should have been called")

    def test_review_step_not_called_when_no_actions(self):
        from runners.executor import Executor
        e = Executor(max_per_step=0, verify_prob=0.0)
        call_count = [0]

        def mock_review(*a, **kw):
            call_count[0] += 1
            return {}

        e._patch_reviewer.review_step = mock_review
        e.execute_step({}, [], step=1, memory_store={})
        self.assertEqual(call_count[0], 0)


class TestTriggerRegistryDagImport(unittest.TestCase):
    """dag_import trigger is registered in the default registry."""

    def test_dag_import_registered(self):
        from utils.trigger_registry import get_default_registry
        reg = get_default_registry()
        self.assertIn("dag_import", reg._triggers)

    def test_dag_import_is_json(self):
        from utils.trigger_registry import get_default_registry
        reg = get_default_registry()
        self.assertEqual(reg._triggers["dag_import"].format, "json")

    def test_dag_import_filename(self):
        from utils.trigger_registry import get_default_registry
        reg = get_default_registry()
        self.assertEqual(
            reg._triggers["dag_import"].filename, "dag_import_trigger.json"
        )


class TestAutoCmdsUsesRegistry(unittest.TestCase):
    """auto_cmds.py no longer defines raw path variables; imports get_default_registry."""

    def test_no_raw_trigger_path_vars(self):
        src = (
            Path(__file__).resolve().parents[1] / "commands" / "auto_cmds.py"
        ).read_text(encoding="utf-8")
        # Old pattern should be gone
        self.assertNotIn('"run_trigger"', src)
        self.assertNotIn('"stop_trigger"', src)
        self.assertNotIn('"add_task_trigger.json"', src)

    def test_imports_get_default_registry(self):
        src = (
            Path(__file__).resolve().parents[1] / "commands" / "auto_cmds.py"
        ).read_text(encoding="utf-8")
        self.assertIn("get_default_registry", src)

    def test_uses_treg_consume(self):
        src = (
            Path(__file__).resolve().parents[1] / "commands" / "auto_cmds.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_treg.consume", src)

    def test_uses_treg_exists(self):
        src = (
            Path(__file__).resolve().parents[1] / "commands" / "auto_cmds.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_treg.exists", src)

    def test_no_json_import(self):
        src = (
            Path(__file__).resolve().parents[1] / "commands" / "auto_cmds.py"
        ).read_text(encoding="utf-8")
        # json module should no longer be directly imported
        import re
        imports = re.findall(r"^import\s+(\w+)", src, re.MULTILINE)
        self.assertNotIn("json", imports)


if __name__ == "__main__":
    unittest.main()
