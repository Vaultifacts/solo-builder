"""Prompt regression tests — TASK-364 (AI-003).

Pins the rendered output of every PromptTemplate in utils/prompt_builder.py
to known-good baselines.  Any change to a template's wording, structure, or
required variables will cause a test to fail, making prompt drift visible
before it reaches production.

Tests are grouped into:
  1. Registry integrity     — all templates registered at import time
  2. Structural invariants  — required phrases present in every render
  3. Regression snapshots   — exact rendered output for canonical inputs
  4. Required-var behaviour — missing vars raise; optional vars default to ""
  5. Convenience functions  — build_* helpers delegate to correct templates
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.prompt_builder import (
    REGISTRY,
    PromptTemplate,
    SUBTASK_EXECUTION,
    SUBTASK_VERIFICATION,
    STALL_RECOVERY,
    build_subtask_prompt,
    build_verification_prompt,
    build_stall_recovery_prompt,
)


# ---------------------------------------------------------------------------
# Canonical inputs for regression snapshots
# ---------------------------------------------------------------------------

_CTX   = "Context: Solo Builder project.\n"
_DESC  = "Implement the /login endpoint."
_OUT   = "Login endpoint implemented with JWT auth."
_SNAME = "impl-login"
_STAT  = "Running"
_STEPS = "5"


# ---------------------------------------------------------------------------
# 1. Registry integrity
# ---------------------------------------------------------------------------

class TestRegistryIntegrity(unittest.TestCase):

    def test_subtask_execution_registered(self):
        self.assertIn("subtask_execution", REGISTRY)

    def test_subtask_verification_registered(self):
        self.assertIn("subtask_verification", REGISTRY)

    def test_stall_recovery_registered(self):
        self.assertIn("stall_recovery", REGISTRY)

    def test_registry_has_exactly_three_templates(self):
        self.assertEqual(len(REGISTRY), 3)

    def test_all_registry_values_are_prompt_template(self):
        for t in REGISTRY.values():
            self.assertIsInstance(t, PromptTemplate)


# ---------------------------------------------------------------------------
# 2. Structural invariants — required phrases present in every render
# ---------------------------------------------------------------------------

class TestSubtaskExecutionStructure(unittest.TestCase):

    def _render(self, **kw):
        defaults = {"project_context": _CTX, "description": _DESC}
        defaults.update(kw)
        return SUBTASK_EXECUTION.render(**defaults)

    def test_contains_description(self):
        self.assertIn(_DESC, self._render())

    def test_contains_project_context(self):
        self.assertIn(_CTX, self._render())

    def test_complete_this_task_phrase(self):
        self.assertIn("Complete this task", self._render())

    def test_no_preamble_phrase(self):
        self.assertIn("no preamble", self._render())

    def test_task_label_present(self):
        self.assertIn("Task:", self._render())


class TestSubtaskVerificationStructure(unittest.TestCase):

    def _render(self, **kw):
        defaults = {"project_context": _CTX, "description": _DESC, "output": _OUT}
        defaults.update(kw)
        return SUBTASK_VERIFICATION.render(**defaults)

    def test_contains_description(self):
        self.assertIn(_DESC, self._render())

    def test_contains_output(self):
        self.assertIn(_OUT, self._render())

    def test_contains_project_context(self):
        self.assertIn(_CTX, self._render())

    def test_yes_no_instruction(self):
        rendered = self._render()
        self.assertIn("YES", rendered)
        self.assertIn("NO", rendered)

    def test_previously_executed_phrase(self):
        self.assertIn("previously executed", self._render())

    def test_output_was_label(self):
        self.assertIn("Output was:", self._render())


class TestStallRecoveryStructure(unittest.TestCase):

    def _render(self, **kw):
        defaults = {
            "project_context": _CTX,
            "subtask_name":    _SNAME,
            "current_status":  _STAT,
            "stall_steps":     _STEPS,
            "description":     _DESC,
        }
        defaults.update(kw)
        return STALL_RECOVERY.render(**defaults)

    def test_contains_subtask_name(self):
        self.assertIn(_SNAME, self._render())

    def test_contains_current_status(self):
        self.assertIn(_STAT, self._render())

    def test_contains_stall_steps(self):
        self.assertIn(_STEPS, self._render())

    def test_contains_description(self):
        self.assertIn(_DESC, self._render())

    def test_diagnose_phrase(self):
        self.assertIn("Diagnose", self._render())

    def test_original_description_label(self):
        self.assertIn("Original description:", self._render())

    def test_last_output_optional_empty(self):
        rendered = self._render()
        self.assertIn("Last output (if any):", rendered)


# ---------------------------------------------------------------------------
# 3. Regression snapshots — exact output for canonical inputs
# ---------------------------------------------------------------------------

class TestSubtaskExecutionSnapshot(unittest.TestCase):

    _EXPECTED = (
        "Context: Solo Builder project.\n"
        "Task: Implement the /login endpoint.\n"
        "Complete this task. Return only the result — no preamble, no explanation."
    )

    def test_exact_rendered_output(self):
        result = SUBTASK_EXECUTION.render(
            project_context=_CTX,
            description=_DESC,
        )
        self.assertEqual(result, self._EXPECTED)


class TestSubtaskVerificationSnapshot(unittest.TestCase):

    _EXPECTED = (
        "Context: Solo Builder project.\n"
        "You previously executed: Implement the /login endpoint.\n"
        "Output was:\n"
        "Login endpoint implemented with JWT auth.\n\n"
        "Did the output fully satisfy the task? "
        "Reply with exactly 'YES' or 'NO', then one sentence of explanation."
    )

    def test_exact_rendered_output(self):
        result = SUBTASK_VERIFICATION.render(
            project_context=_CTX,
            description=_DESC,
            output=_OUT,
        )
        self.assertEqual(result, self._EXPECTED)


class TestStallRecoverySnapshot(unittest.TestCase):

    _EXPECTED = (
        "Context: Solo Builder project.\n"
        "Subtask 'impl-login' has been stuck in 'Running' for 5 steps.\n"
        "Original description: Implement the /login endpoint.\n"
        "Last output (if any): \n\n"
        "Diagnose the stall and provide a corrected approach. "
        "Be concise — one paragraph maximum."
    )

    def test_exact_rendered_output_no_last_output(self):
        result = STALL_RECOVERY.render(
            project_context=_CTX,
            subtask_name=_SNAME,
            current_status=_STAT,
            stall_steps=_STEPS,
            description=_DESC,
        )
        self.assertEqual(result, self._EXPECTED)

    def test_exact_rendered_output_with_last_output(self):
        last = "Timeout after 30s."
        result = STALL_RECOVERY.render(
            project_context=_CTX,
            subtask_name=_SNAME,
            current_status=_STAT,
            stall_steps=_STEPS,
            description=_DESC,
            last_output=last,
        )
        self.assertIn(last, result)


# ---------------------------------------------------------------------------
# 4. Required-var and optional-var behaviour
# ---------------------------------------------------------------------------

class TestRequiredVarBehaviour(unittest.TestCase):

    def test_missing_required_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            SUBTASK_EXECUTION.render(project_context=_CTX)  # missing description
        self.assertIn("description", str(cm.exception))

    def test_missing_project_context_raises(self):
        with self.assertRaises(ValueError):
            SUBTASK_EXECUTION.render(description=_DESC)

    def test_optional_var_defaults_to_empty(self):
        result = STALL_RECOVERY.render(
            project_context=_CTX,
            subtask_name=_SNAME,
            current_status=_STAT,
            stall_steps=_STEPS,
            description=_DESC,
            # last_output omitted — optional
        )
        # last_output slot renders as empty string
        self.assertIn("Last output (if any): \n", result)

    def test_extra_kwargs_silently_ignored(self):
        result = SUBTASK_EXECUTION.render(
            project_context=_CTX,
            description=_DESC,
            extra_unknown_key="ignored",
        )
        self.assertNotIn("ignored", result)


class TestPlaceholderNames(unittest.TestCase):

    def test_subtask_execution_placeholders(self):
        names = SUBTASK_EXECUTION.placeholder_names
        self.assertIn("project_context", names)
        self.assertIn("description", names)

    def test_subtask_verification_placeholders(self):
        names = SUBTASK_VERIFICATION.placeholder_names
        self.assertIn("project_context", names)
        self.assertIn("description", names)
        self.assertIn("output", names)

    def test_stall_recovery_placeholders(self):
        names = STALL_RECOVERY.placeholder_names
        self.assertIn("subtask_name", names)
        self.assertIn("current_status", names)
        self.assertIn("stall_steps", names)
        self.assertIn("last_output", names)


class TestEmptyPlaceholderRejected(unittest.TestCase):

    def test_blank_placeholder_raises_on_creation(self):
        import importlib
        import solo_builder.utils.prompt_builder as pb_mod
        # Temporarily allow duplicate-free creation by using a unique name
        with self.assertRaises(ValueError) as cm:
            PromptTemplate(
                name="__test_blank__",
                template="Hello {} world",
                required_vars=[],
            )
        self.assertIn("{}", str(cm.exception))


class TestDuplicateNameRejected(unittest.TestCase):

    def test_duplicate_name_raises(self):
        with self.assertRaises(ValueError) as cm:
            PromptTemplate(
                name="subtask_execution",  # already registered
                template="Some {var}",
                required_vars=["var"],
            )
        self.assertIn("subtask_execution", str(cm.exception))


# ---------------------------------------------------------------------------
# 5. Convenience-function delegation
# ---------------------------------------------------------------------------

class TestBuildSubtaskPrompt(unittest.TestCase):

    def test_returns_same_as_direct_render(self):
        direct = SUBTASK_EXECUTION.render(project_context=_CTX, description=_DESC)
        via_fn = build_subtask_prompt(project_context=_CTX, description=_DESC)
        self.assertEqual(direct, via_fn)

    def test_result_is_string(self):
        self.assertIsInstance(build_subtask_prompt(_CTX, _DESC), str)


class TestBuildVerificationPrompt(unittest.TestCase):

    def test_returns_same_as_direct_render(self):
        direct = SUBTASK_VERIFICATION.render(
            project_context=_CTX, description=_DESC, output=_OUT
        )
        via_fn = build_verification_prompt(
            project_context=_CTX, description=_DESC, output=_OUT
        )
        self.assertEqual(direct, via_fn)


class TestBuildStallRecoveryPrompt(unittest.TestCase):

    def test_returns_same_as_direct_render(self):
        direct = STALL_RECOVERY.render(
            project_context=_CTX,
            subtask_name=_SNAME,
            current_status=_STAT,
            stall_steps=_STEPS,
            description=_DESC,
            last_output="",
        )
        via_fn = build_stall_recovery_prompt(
            project_context=_CTX,
            subtask_name=_SNAME,
            current_status=_STAT,
            stall_steps=5,
            description=_DESC,
        )
        self.assertEqual(direct, via_fn)

    def test_last_output_optional_forwarded(self):
        result = build_stall_recovery_prompt(
            project_context=_CTX,
            subtask_name=_SNAME,
            current_status=_STAT,
            stall_steps=3,
            description=_DESC,
            last_output="Timed out.",
        )
        self.assertIn("Timed out.", result)


if __name__ == "__main__":
    unittest.main()
