"""Tests for solo_builder/runners/hitl_gate.py.

Covers all 6 evaluation rules and boundary cases.

Run:
    python -m unittest tests.test_hitl_gate -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.hitl_gate import evaluate, level_name, HITLBlockError


class TestEvaluateRules(unittest.TestCase):
    """One test per evaluation rule, top-to-bottom priority order."""

    # Rule 1 — Bash requires Pause (level 2)
    def test_bash_tool_returns_pause(self):
        self.assertEqual(evaluate("Bash", "Run a script."), 2)

    def test_bash_with_other_tools_still_pause(self):
        self.assertEqual(evaluate("Read,Bash,Glob", "List files."), 2)

    # Rule 2 — Write or Edit requires Pause
    def test_write_tool_returns_pause(self):
        self.assertEqual(evaluate("Write", "Write output to a file."), 2)

    def test_edit_tool_returns_pause(self):
        self.assertEqual(evaluate("Edit", "Edit the config file."), 2)

    def test_write_and_read_still_pause(self):
        self.assertEqual(evaluate("Read,Write", "Read then write."), 2)

    # Rule 3 — WebFetch/WebSearch requires Notify (level 1)
    def test_webfetch_returns_notify(self):
        self.assertEqual(evaluate("WebFetch", "Fetch the docs page."), 1)

    def test_websearch_returns_notify(self):
        self.assertEqual(evaluate("WebSearch", "Search for an API."), 1)

    def test_webfetch_with_read_returns_notify(self):
        self.assertEqual(evaluate("Read,WebFetch", "Read and fetch."), 1)

    # Rule 4 — Destructive keyword in description requires Pause
    def test_delete_keyword_returns_pause(self):
        self.assertEqual(evaluate("", "delete the old logs."), 2)

    def test_drop_keyword_returns_pause(self):
        self.assertEqual(evaluate("", "drop the temp table."), 2)

    def test_purge_keyword_returns_pause(self):
        self.assertEqual(evaluate("", "purge all cached data."), 2)

    def test_rm_rf_keyword_returns_pause(self):
        self.assertEqual(evaluate("", "run rm -rf on the temp dir."), 2)

    def test_destructive_keyword_case_insensitive(self):
        self.assertEqual(evaluate("", "DELETE the state file."), 2)

    # Rule 5 — Path traversal in description requires Pause
    def test_dotdot_path_returns_pause(self):
        self.assertEqual(evaluate("Read", "Read ../../../etc/passwd."), 2)

    def test_etc_path_returns_pause(self):
        self.assertEqual(evaluate("Read", "Read /etc/hosts."), 2)

    # Rule 6 — Safe tools (or no tools) returns Auto
    def test_no_tools_returns_auto(self):
        self.assertEqual(evaluate("", "List 3 features."), 0)

    def test_empty_tools_returns_auto(self):
        self.assertEqual(evaluate("  ", "Summarise the project."), 0)

    def test_read_only_returns_auto(self):
        self.assertEqual(evaluate("Read", "Read the config file."), 0)

    def test_glob_only_returns_auto(self):
        self.assertEqual(evaluate("Glob", "Find all Python files."), 0)

    def test_grep_only_returns_auto(self):
        self.assertEqual(evaluate("Grep", "Search for function names."), 0)

    def test_all_safe_tools_returns_auto(self):
        self.assertEqual(evaluate("Read,Glob,Grep", "Analyse codebase."), 0)


class TestRulePriority(unittest.TestCase):
    """Higher-priority rules win when multiple conditions match."""

    def test_bash_beats_webfetch(self):
        # Bash (rule 1, level 2) beats WebFetch (rule 3, level 1)
        self.assertEqual(evaluate("Bash,WebFetch", "Run and fetch."), 2)

    def test_write_beats_webfetch(self):
        self.assertEqual(evaluate("Write,WebFetch", "Write and fetch."), 2)

    def test_destructive_keyword_with_safe_tools(self):
        # Rule 4 (description) fires even if tools are safe
        self.assertEqual(evaluate("Read,Glob", "delete stale records."), 2)


class TestLevelName(unittest.TestCase):
    def test_known_levels(self):
        self.assertEqual(level_name(0), "Auto")
        self.assertEqual(level_name(1), "Notify")
        self.assertEqual(level_name(2), "Pause")
        self.assertEqual(level_name(3), "Block")

    def test_unknown_level(self):
        self.assertEqual(level_name(99), "Unknown")


class TestHITLBlockError(unittest.TestCase):
    def test_is_runtime_error(self):
        self.assertTrue(issubclass(HITLBlockError, RuntimeError))

    def test_raises_with_message(self):
        with self.assertRaises(HITLBlockError) as ctx:
            raise HITLBlockError("Blocked: Bash not permitted")
        self.assertIn("Bash", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
