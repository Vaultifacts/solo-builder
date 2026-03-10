"""Tests for utils/hitl_policy.py — TASK-338 (AI-026, AI-032)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.hitl_policy import (
    HitlPolicy,
    load_policy,
    evaluate_with_policy,
    _parse_csv,
    _DEFAULTS,
)


# ---------------------------------------------------------------------------
# _parse_csv
# ---------------------------------------------------------------------------

class TestParseCsv(unittest.TestCase):

    def test_parses_simple_csv(self):
        self.assertEqual(_parse_csv("Bash,Read,Write"), frozenset({"Bash", "Read", "Write"}))

    def test_strips_whitespace(self):
        self.assertEqual(_parse_csv(" Bash , Read "), frozenset({"Bash", "Read"}))

    def test_empty_string_returns_empty(self):
        self.assertEqual(_parse_csv(""), frozenset())


# ---------------------------------------------------------------------------
# load_policy
# ---------------------------------------------------------------------------

class TestLoadPolicy(unittest.TestCase):

    def test_loads_defaults_when_file_missing(self):
        policy = load_policy(Path("/no/such/file.json"))
        self.assertIn("Bash", policy.pause_tools)
        self.assertIn("WebFetch", policy.notify_tools)

    def test_loads_from_settings_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"HITL_PAUSE_TOOLS": "Bash", "HITL_NOTIFY_TOOLS": "WebFetch",
                   "HITL_BLOCK_KEYWORDS": "", "HITL_PAUSE_KEYWORDS": "delete"}
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps(cfg), encoding="utf-8")
            policy = load_policy(p)
        self.assertEqual(policy.pause_tools, frozenset({"Bash"}))
        self.assertIn("delete", policy.pause_keywords)

    def test_falls_back_to_default_for_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text("{}", encoding="utf-8")
            policy = load_policy(p)
        self.assertIn("Bash", policy.pause_tools)  # default used

    def test_returns_policy_on_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text("not-json", encoding="utf-8")
            policy = load_policy(p)  # should not raise
        self.assertIsInstance(policy, HitlPolicy)


# ---------------------------------------------------------------------------
# HitlPolicy.validate()
# ---------------------------------------------------------------------------

class TestHitlPolicyValidate(unittest.TestCase):

    def test_valid_policy_no_warnings(self):
        policy = load_policy(Path("/no/such/file.json"))
        warnings = policy.validate()
        self.assertEqual(warnings, [])

    def test_warns_when_bash_not_in_pause_tools(self):
        policy = HitlPolicy(pause_tools=frozenset({"Write"}),
                             notify_tools=frozenset(),
                             block_keywords=frozenset(),
                             pause_keywords=frozenset())
        warnings = policy.validate()
        self.assertTrue(any("Bash" in w for w in warnings))

    def test_warns_when_pause_tools_empty(self):
        policy = HitlPolicy(pause_tools=frozenset(),
                             notify_tools=frozenset(),
                             block_keywords=frozenset(),
                             pause_keywords=frozenset())
        warnings = policy.validate()
        self.assertTrue(any("empty" in w.lower() for w in warnings))


# ---------------------------------------------------------------------------
# evaluate_with_policy
# ---------------------------------------------------------------------------

class TestEvaluateWithPolicy(unittest.TestCase):

    def setUp(self):
        self.policy = load_policy(Path("/no/such/file.json"))

    def test_auto_for_no_tools_safe_description(self):
        self.assertEqual(evaluate_with_policy(self.policy, "", "read a file"), 0)

    def test_pause_for_bash_tool(self):
        self.assertEqual(evaluate_with_policy(self.policy, "Bash", "run tests"), 2)

    def test_pause_for_write_tool(self):
        self.assertEqual(evaluate_with_policy(self.policy, "Write", "save file"), 2)

    def test_notify_for_webfetch_tool(self):
        self.assertEqual(evaluate_with_policy(self.policy, "WebFetch", "fetch page"), 1)

    def test_pause_for_destructive_keyword(self):
        self.assertEqual(evaluate_with_policy(self.policy, "", "delete all records"), 2)

    def test_block_for_force_push(self):
        self.assertEqual(evaluate_with_policy(self.policy, "", "git force-push main"), 3)

    def test_pause_for_path_traversal(self):
        self.assertEqual(evaluate_with_policy(self.policy, "", "read ../../etc/passwd"), 2)

    def test_safe_tools_return_auto(self):
        self.assertEqual(evaluate_with_policy(self.policy, "Read,Glob,Grep", "search code"), 0)

    def test_pause_tool_beats_notify_tool(self):
        self.assertEqual(evaluate_with_policy(self.policy, "Bash,WebFetch", "run + fetch"), 2)


if __name__ == "__main__":
    unittest.main()
