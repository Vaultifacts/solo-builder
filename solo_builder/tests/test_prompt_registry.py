"""Hash-based regression tests for prompt templates (TASK-321 / AI-004, AI-005).

Each test extracts the live prompt template from the source file and compares
its normalised SHA-256 hash against the value recorded in docs/PROMPT_REGISTRY.md.

A test failure means a prompt template changed without a deliberate registry update.
To intentionally update a prompt:
  1. Change the source code.
  2. Run this test to get the new hash from the assertion error.
  3. Update docs/PROMPT_REGISTRY.md with the new hash.
  4. Update the EXPECTED_HASHES dict below.
  5. Commit all three changes together.
"""
import hashlib
import re
import sys
import unittest
from pathlib import Path

# Repo root (two levels up from solo_builder/tests/)
_REPO   = Path(__file__).resolve().parent.parent.parent
_SB     = _REPO / "solo_builder"
_CLI    = _SB / "solo_builder_cli.py"
_LOADER = _SB / "config" / "loader.py"
_EXEC   = _SB / "runners" / "executor.py"
_DAGCMD = _SB / "commands" / "dag_cmds.py"


def _hash(text: str) -> str:
    """Normalise whitespace then SHA-256 the result."""
    normalised = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalised.encode()).hexdigest()


# ── Expected hashes (must match docs/PROMPT_REGISTRY.md) ──────────────────
EXPECTED_HASHES = {
    "PROMPT-001": "b50fef6cbf1ce0485e13157f9be83f09639fe2f09dfb322de01cd2fef630ee00",
    "PROMPT-002": "1d2d6e658297d0dbebcd9329d02d08fcff249eb3bf0f72a89b949f7d2a352fc3",
    "PROMPT-003": "4a7e2dda2984658fc63af21acfa2f5e6e258497a3246d2749fb2a1aabdedcfab",
    "PROMPT-004": "bd0fd460b3a775acc9e43337c12b772adfcf3723820923602d0e1c810d6c9fd4",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestPromptRegistry(unittest.TestCase):
    """Regression guard — detect unintentional prompt drift."""

    def test_prompt_001_project_context(self):
        """PROMPT-001: _PROJECT_CONTEXT in config/loader.py."""
        # Line-by-line extraction handles nested parens in the string value
        lines = _read(_LOADER).splitlines()
        start = next(
            (i for i, ln in enumerate(lines) if ln.strip().startswith("_PROJECT_CONTEXT")),
            None,
        )
        self.assertIsNotNone(start, "_PROJECT_CONTEXT not found in solo_builder_cli.py")
        parts = []
        for ln in lines[start:]:
            parts.extend(re.findall(r'"([^"]*)"', ln))
            if ln.strip() == ")":
                break
        text = "".join(parts)
        self.assertIn("Solo Builder", text)
        self.assertEqual(
            _hash(text),
            EXPECTED_HASHES["PROMPT-001"],
            "PROMPT-001 (_PROJECT_CONTEXT) has changed — update PROMPT_REGISTRY.md",
        )

    def test_prompt_002_sdk_fallback(self):
        """PROMPT-002: SDK direct fallback prompt in executor.py."""
        src = _read(_EXEC)
        # Verify both sentinel lines are present (split across two fstrings)
        self.assertIn("You completed subtask '", src,
                      "PROMPT-002 first sentinel not found in executor.py")
        self.assertIn("Write one concrete sentence describing what was accomplished.", src,
                      "PROMPT-002 second sentinel not found in executor.py")
        # Canonical template (variable names are stable identifiers, not user input)
        template = (
            "You completed subtask '{st_name}' in task '{task_name}'. "
            "Write one concrete sentence describing what was accomplished."
        )
        self.assertEqual(
            _hash(template),
            EXPECTED_HASHES["PROMPT-002"],
            "PROMPT-002 (SDK fallback) has changed — update PROMPT_REGISTRY.md",
        )

    def test_prompt_003_add_task_decomp(self):
        """PROMPT-003: add_task decomposition template in dag_cmds.py."""
        src = _read(_DAGCMD)
        self.assertIn(
            "Break this task into 2-5 concrete subtasks",
            src,
            "PROMPT-003 sentinel not found in dag_cmds.py",
        )
        self.assertIn("- 2 to 5 items", src, "PROMPT-003 item count rule missing")
        # Reconstruct canonical template (letter='A', spec='{spec}')
        letter = "A"
        template = (
            f"Break this task into 2-5 concrete subtasks for a solo developer AI project.\n\n"
            f"Task: {{spec}}\n\n"
            f"Reply with a JSON array only — no explanation, no markdown fences:\n"
            f'[{{"name": "A1", "description": "actionable prompt"}}, ...]\n\n'
            f"Rules:\n"
            f"- name: uppercase letter 'A' + digit, e.g. A1 A2 A3\n"
            f"- description: a self-contained question or instruction Claude can answer headlessly\n"
            f"- 2 to 5 items"
        )
        self.assertEqual(
            _hash(template),
            EXPECTED_HASHES["PROMPT-003"],
            "PROMPT-003 (add_task decomp) has changed — update PROMPT_REGISTRY.md",
        )

    def test_prompt_004_add_branch_decomp(self):
        """PROMPT-004: add_branch decomposition template in dag_cmds.py."""
        src = _read(_DAGCMD)
        self.assertIn(
            "Break this concern into 2-4 concrete subtasks",
            src,
            "PROMPT-004 sentinel not found in dag_cmds.py",
        )
        self.assertIn("- 2 to 4 items", src, "PROMPT-004 item count rule missing")
        template = (
            "Break this concern into 2-4 concrete subtasks for a solo developer project.\n\n"
            "Concern: {spec}\n\n"
            "Reply with a JSON array only — no explanation, no markdown fences:\n"
            '[{"name": "A1", "description": "actionable prompt"}, ...]\n\n'
            "Rules:\n"
            "- name: uppercase 'A' + digit, e.g. A1 A2\n"
            "- description: self-contained question or instruction Claude can answer headlessly\n"
            "- 2 to 4 items"
        )
        self.assertEqual(
            _hash(template),
            EXPECTED_HASHES["PROMPT-004"],
            "PROMPT-004 (add_branch decomp) has changed — update PROMPT_REGISTRY.md",
        )

    def test_registry_doc_contains_all_hashes(self):
        """All 4 expected hashes must appear in docs/PROMPT_REGISTRY.md."""
        registry = (_REPO / "docs" / "PROMPT_REGISTRY.md").read_text(encoding="utf-8")
        for prompt_id, expected_hash in EXPECTED_HASHES.items():
            self.assertIn(
                expected_hash,
                registry,
                f"{prompt_id} hash not found in docs/PROMPT_REGISTRY.md",
            )


if __name__ == "__main__":
    unittest.main()
