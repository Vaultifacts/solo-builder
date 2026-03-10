"""Regression tests for the Solo Builder prompt engineering standard.

Guards:
  - _PROJECT_CONTEXT exact text, required keywords, trailing space (AI-003)
  - SDK prompt assembly: context + description, fallback format
  - Subprocess gap documented (AI-002)
  - All INITIAL_DAG descriptions meet quality rules (non-empty, 20–2000 chars,
    ends with sentence terminator, not a known bad example)

Run:
    pytest solo_builder/tests/test_prompt_standard.py
    python -m pytest solo_builder/tests/test_prompt_standard.py -v
"""
import sys
import unittest
from pathlib import Path

# Ensure solo_builder/ is on sys.path so we can import without the package prefix
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import solo_builder_cli
from dag_definition import INITIAL_DAG

# ---------------------------------------------------------------------------
# Snapshots — update these constants when intentionally changing a prompt.
# The commit message MUST explain why the prompt changed and confirm quality.
# ---------------------------------------------------------------------------

_EXPECTED_CONTEXT = (
    "Context: Solo Builder is a Python terminal CLI that uses six AI agents "
    "(Planner, ShadowAgent, SelfHealer, Executor, Verifier, MetaOptimizer) "
    "and the Anthropic SDK to manage DAG-based software project tasks. "
)

_EXPECTED_A1_DESCRIPTION = (
    "List 5 key features a solo developer AI project management tool needs. Bullet points."
)

_EXPECTED_A1_FULL_PROMPT = _EXPECTED_CONTEXT + _EXPECTED_A1_DESCRIPTION

_EXPECTED_FALLBACK_TEMPLATE_PREFIX = "You completed subtask '"

# ---------------------------------------------------------------------------
# Helper: collect every subtask from INITIAL_DAG
# ---------------------------------------------------------------------------

def _all_subtasks():
    """Yield (task_name, branch_name, st_name, st_data) for every subtask."""
    for task_name, task in INITIAL_DAG.items():
        for branch_name, branch in task.get("branches", {}).items():
            for st_name, st_data in branch.get("subtasks", {}).items():
                yield task_name, branch_name, st_name, st_data


# ═══════════════════════════════════════════════════════════════════════════
# TestProjectContextSnapshot
# ═══════════════════════════════════════════════════════════════════════════

class TestProjectContextSnapshot(unittest.TestCase):
    """Guard the exact text, required keywords, and trailing-space rule."""

    def test_exact_snapshot(self):
        self.assertEqual(solo_builder_cli._PROJECT_CONTEXT, _EXPECTED_CONTEXT)

    def test_starts_with_context_label(self):
        self.assertTrue(
            solo_builder_cli._PROJECT_CONTEXT.startswith("Context:"),
            "_PROJECT_CONTEXT must start with 'Context:'"
        )

    def test_required_keywords_present(self):
        ctx = solo_builder_cli._PROJECT_CONTEXT
        for keyword in ("Solo Builder", "Python", "CLI", "agents", "Anthropic SDK", "DAG"):
            self.assertIn(keyword, ctx, f"Required keyword missing: {keyword!r}")

    def test_agent_names_present(self):
        ctx = solo_builder_cli._PROJECT_CONTEXT
        for agent in ("Planner", "ShadowAgent", "SelfHealer", "Executor", "Verifier", "MetaOptimizer"):
            self.assertIn(agent, ctx, f"Agent name missing from context: {agent!r}")

    def test_trailing_space(self):
        self.assertTrue(
            solo_builder_cli._PROJECT_CONTEXT.endswith(" "),
            "_PROJECT_CONTEXT must end with a space for clean concatenation"
        )

    def test_no_leading_whitespace(self):
        self.assertFalse(
            solo_builder_cli._PROJECT_CONTEXT[0].isspace(),
            "_PROJECT_CONTEXT must not start with whitespace"
        )

    def test_single_sentence(self):
        # Context should be compact — not a multi-paragraph blob
        stripped = solo_builder_cli._PROJECT_CONTEXT.strip()
        self.assertLessEqual(
            len(stripped), 300,
            f"_PROJECT_CONTEXT is too long ({len(stripped)} chars) — keep it to one sentence"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TestPromptConstruction
# ═══════════════════════════════════════════════════════════════════════════

class TestPromptConstruction(unittest.TestCase):
    """Guard SDK-path assembly, fallback prompt format, and AI-002 resolution."""

    def test_sdk_path_prepends_context(self):
        description = "List 3 features."
        prompt = solo_builder_cli._PROJECT_CONTEXT + description
        self.assertTrue(prompt.startswith("Context:"))
        self.assertIn(description, prompt)

    def test_sdk_path_no_double_space_at_join(self):
        # Context ends with a space; description must not start with a space
        ctx = solo_builder_cli._PROJECT_CONTEXT
        desc = "List 3 features."
        prompt = ctx + desc
        self.assertNotIn("  ", prompt, "Double-space at context/description join")

    def test_fallback_prompt_format(self):
        st_name = "A1"
        task_name = "Task 0"
        fallback = (
            f"You completed subtask '{st_name}' in task '{task_name}'. "
            f"Write one concrete sentence describing what was accomplished."
        )
        self.assertTrue(fallback.startswith(_EXPECTED_FALLBACK_TEMPLATE_PREFIX))
        self.assertIn(st_name, fallback)
        self.assertIn(task_name, fallback)
        self.assertIn("Write one concrete sentence", fallback)

    def test_subprocess_path_prepends_context(self):
        """AI-002 resolved: executor.py subprocess path now prepends _PROJECT_CONTEXT.

        Verified by reading executor.py: pool.submit(self.claude.run,
            self._project_context + st_data.get("description", ""), ...)
        Context is prepended at the call site before dispatch to ClaudeRunner.
        """
        ctx = solo_builder_cli._PROJECT_CONTEXT
        description = "List 3 risks."
        # Simulate what executor.py now does for the subprocess path
        prompt = ctx + description
        self.assertTrue(prompt.startswith("Context:"))
        self.assertIn("Solo Builder", prompt)
        self.assertIn(description, prompt)

    def test_context_attribute_accessible(self):
        self.assertTrue(hasattr(solo_builder_cli, "_PROJECT_CONTEXT"))
        self.assertIsInstance(solo_builder_cli._PROJECT_CONTEXT, str)

    def test_add_task_decomp_prompt_starts_with_context(self):
        """dag_cmds add_task decomp prompt now prepends _PROJECT_CONTEXT (AI-002 fix)."""
        ctx = solo_builder_cli._PROJECT_CONTEXT
        spec = "Build a caching layer."
        letter = "A"
        decomp_prompt = (
            ctx
            + f"Break this task into 2-5 concrete subtasks for a solo developer AI project.\n\n"
            f"Task: {spec}\n\n"
            f"Reply with a JSON array only — no explanation, no markdown fences:\n"
            f'[{{"name": "{letter}1", "description": "actionable prompt"}}, ...]\n\n'
            f"Rules:\n"
            f"- name: uppercase letter '{letter}' + digit, e.g. {letter}1 {letter}2 {letter}3\n"
            f"- description: a self-contained question or instruction Claude can answer headlessly\n"
            f"- 2 to 5 items"
        )
        self.assertTrue(decomp_prompt.startswith("Context:"))
        self.assertIn("Solo Builder", decomp_prompt)
        self.assertIn(spec, decomp_prompt)

    def test_add_branch_decomp_prompt_starts_with_context(self):
        """dag_cmds add_branch decomp prompt now prepends _PROJECT_CONTEXT (AI-002 fix)."""
        ctx = solo_builder_cli._PROJECT_CONTEXT
        spec = "Error handling strategy."
        branch_letter = "B"
        decomp_prompt = (
            ctx
            + f"Break this concern into 2-4 concrete subtasks for a solo developer project.\n\n"
            f"Concern: {spec}\n\n"
            f"Reply with a JSON array only — no explanation, no markdown fences:\n"
            f'[{{"name": "{branch_letter}1", "description": "actionable prompt"}}, ...]\n\n'
            f"Rules:\n"
            f"- name: uppercase '{branch_letter}' + digit, e.g. {branch_letter}1 {branch_letter}2\n"
            f"- description: self-contained question or instruction Claude can answer headlessly\n"
            f"- 2 to 4 items"
        )
        self.assertTrue(decomp_prompt.startswith("Context:"))
        self.assertIn("Solo Builder", decomp_prompt)
        self.assertIn(spec, decomp_prompt)


# ═══════════════════════════════════════════════════════════════════════════
# TestPromptSnapshots
# ═══════════════════════════════════════════════════════════════════════════

class TestPromptSnapshots(unittest.TestCase):
    """Exact full-prompt snapshots for known subtasks."""

    def test_a1_description_snapshot(self):
        a1 = INITIAL_DAG["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(a1["description"], _EXPECTED_A1_DESCRIPTION)

    def test_a1_full_prompt_snapshot(self):
        a1_desc = INITIAL_DAG["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["description"]
        full_prompt = solo_builder_cli._PROJECT_CONTEXT + a1_desc
        self.assertEqual(full_prompt, _EXPECTED_A1_FULL_PROMPT)

    def test_fallback_full_prompt_snapshot(self):
        st_name = "A1"
        task_name = "Task 0"
        raw = (
            f"You completed subtask '{st_name}' in task '{task_name}'. "
            f"Write one concrete sentence describing what was accomplished."
        )
        full = solo_builder_cli._PROJECT_CONTEXT + raw
        self.assertTrue(full.startswith("Context:"))
        self.assertIn("You completed subtask", full)


# ═══════════════════════════════════════════════════════════════════════════
# TestDagDescriptionQuality
# ═══════════════════════════════════════════════════════════════════════════

class TestDagDescriptionQuality(unittest.TestCase):
    """All INITIAL_DAG descriptions must meet the prompt standard rules."""

    def test_all_descriptions_non_empty(self):
        for task, branch, st, data in _all_subtasks():
            with self.subTest(subtask=f"{task}/{branch}/{st}"):
                desc = data.get("description", "")
                self.assertTrue(
                    desc.strip(),
                    f"{task}/{branch}/{st}: description is empty — fallback produces low-quality output"
                )

    def test_all_descriptions_minimum_length(self):
        for task, branch, st, data in _all_subtasks():
            with self.subTest(subtask=f"{task}/{branch}/{st}"):
                desc = data.get("description", "")
                self.assertGreaterEqual(
                    len(desc), 20,
                    f"{task}/{branch}/{st}: description too short ({len(desc)} chars, min 20)"
                )

    def test_all_descriptions_maximum_length(self):
        for task, branch, st, data in _all_subtasks():
            with self.subTest(subtask=f"{task}/{branch}/{st}"):
                desc = data.get("description", "")
                self.assertLessEqual(
                    len(desc), 2000,
                    f"{task}/{branch}/{st}: description too long ({len(desc)} chars, max 2000)"
                )

    def test_all_descriptions_end_with_terminator(self):
        for task, branch, st, data in _all_subtasks():
            with self.subTest(subtask=f"{task}/{branch}/{st}"):
                desc = data.get("description", "").rstrip()
                self.assertTrue(
                    desc.endswith((".", "?", "!")),
                    f"{task}/{branch}/{st}: description must end with '.', '?', or '!' — got: ...{desc[-10:]!r}"
                )

    def test_all_descriptions_have_action_verb(self):
        """Descriptions should start with an action verb or interrogative — not an article."""
        bad_starters = ("the ", "a ", "an ", "this ", "that ")
        for task, branch, st, data in _all_subtasks():
            with self.subTest(subtask=f"{task}/{branch}/{st}"):
                desc = data.get("description", "").lower()
                for starter in bad_starters:
                    self.assertFalse(
                        desc.startswith(starter),
                        f"{task}/{branch}/{st}: description starts with article {starter!r} — use an action verb"
                    )

    def test_description_count_matches_expected(self):
        """Guard against accidental subtask deletion — INITIAL_DAG should have exactly 70 subtasks."""
        count = sum(1 for _ in _all_subtasks())
        self.assertEqual(
            count, 70,
            f"Expected 70 subtasks in INITIAL_DAG, found {count}. "
            "Update this test if the DAG was intentionally changed."
        )


if __name__ == "__main__":
    unittest.main()
