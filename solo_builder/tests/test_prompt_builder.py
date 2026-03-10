"""Tests for solo_builder/utils/prompt_builder.py — TASK-337 (AI-002)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.prompt_builder import (
    PromptTemplate,
    REGISTRY,
    SUBTASK_EXECUTION,
    SUBTASK_VERIFICATION,
    STALL_RECOVERY,
    build_subtask_prompt,
    build_verification_prompt,
    build_stall_recovery_prompt,
)


class TestPromptTemplate(unittest.TestCase):

    def _make(self, name: str, **kwargs) -> PromptTemplate:
        """Create a PromptTemplate that auto-cleans from the registry."""
        pt = PromptTemplate(name=name, **kwargs)
        self.addCleanup(REGISTRY.pop, name, None)
        return pt

    # ------------------------------------------------------------------
    # Construction validation
    # ------------------------------------------------------------------
    def test_rejects_empty_placeholder(self):
        with self.assertRaises(ValueError):
            self._make("bad", template="Hello {}!")

    def test_rejects_duplicate_name(self):
        self._make("dup-test", template="Hello {name}!", required_vars=["name"])
        with self.assertRaises(ValueError):
            self._make("dup-test", template="World {name}!", required_vars=["name"])

    def test_registered_on_creation(self):
        self._make("reg-test", template="Hi {name}!", required_vars=["name"])
        self.assertIn("reg-test", REGISTRY)

    # ------------------------------------------------------------------
    # render()
    # ------------------------------------------------------------------
    def test_render_required_vars(self):
        pt = self._make("r-test", template="{a} and {b}", required_vars=["a", "b"])
        self.assertEqual(pt.render(a="X", b="Y"), "X and Y")

    def test_render_missing_required_raises(self):
        pt = self._make("m-test", template="{a}", required_vars=["a"])
        with self.assertRaises(ValueError):
            pt.render()

    def test_render_optional_defaults_empty(self):
        pt = self._make("o-test", template="{a}{b}", required_vars=["a"], optional_vars=["b"])
        self.assertEqual(pt.render(a="X"), "X")

    def test_render_optional_can_be_supplied(self):
        pt = self._make("os-test", template="{a}{b}", required_vars=["a"], optional_vars=["b"])
        self.assertEqual(pt.render(a="X", b="Y"), "XY")

    def test_render_extra_kwargs_ignored(self):
        pt = self._make("ex-test", template="{a}", required_vars=["a"])
        result = pt.render(a="A", unused="ignored")
        self.assertEqual(result, "A")

    # ------------------------------------------------------------------
    # placeholder_names
    # ------------------------------------------------------------------
    def test_placeholder_names(self):
        pt = self._make("ph-test", template="{x} + {y}", required_vars=["x", "y"])
        self.assertEqual(pt.placeholder_names, {"x", "y"})


class TestStandardTemplates(unittest.TestCase):
    """Regression tests — verify the registered standard templates are unchanged."""

    def test_subtask_execution_in_registry(self):
        self.assertIn("subtask_execution", REGISTRY)

    def test_subtask_verification_in_registry(self):
        self.assertIn("subtask_verification", REGISTRY)

    def test_stall_recovery_in_registry(self):
        self.assertIn("stall_recovery", REGISTRY)

    def test_subtask_execution_required_vars(self):
        self.assertIn("project_context", SUBTASK_EXECUTION.required_vars)
        self.assertIn("description", SUBTASK_EXECUTION.required_vars)

    def test_subtask_verification_required_vars(self):
        self.assertIn("output", SUBTASK_VERIFICATION.required_vars)

    def test_stall_recovery_optional_last_output(self):
        self.assertIn("last_output", STALL_RECOVERY.optional_vars)


class TestConvenienceFunctions(unittest.TestCase):

    _CTX = "Context: Solo Builder project. "

    def test_build_subtask_prompt_contains_context(self):
        result = build_subtask_prompt(self._CTX, "Do something.")
        self.assertIn(self._CTX, result)

    def test_build_subtask_prompt_contains_description(self):
        result = build_subtask_prompt(self._CTX, "Do something.")
        self.assertIn("Do something.", result)

    def test_build_verification_prompt_contains_output(self):
        result = build_verification_prompt(self._CTX, "task", "the output")
        self.assertIn("the output", result)

    def test_build_stall_recovery_prompt_contains_steps(self):
        result = build_stall_recovery_prompt(
            self._CTX, "ST-1", "Running", 15, "Do X")
        self.assertIn("15", result)

    def test_build_stall_recovery_optional_last_output_empty(self):
        result = build_stall_recovery_prompt(
            self._CTX, "ST-1", "Running", 5, "Do X")
        # Should not error; last_output defaults to ""
        self.assertIn("ST-1", result)


if __name__ == "__main__":
    unittest.main()
