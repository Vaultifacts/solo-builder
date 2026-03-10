"""Tests for solo_builder/utils/tool_scope_policy.py (TASK-341, AI-033)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from solo_builder.utils.tool_scope_policy import (
    ToolScopePolicy,
    ScopeResult,
    _parse_csv_set,
    _DEFAULT_ALLOWLISTS,
    load_scope_policy,
    evaluate_scope,
)


# ---------------------------------------------------------------------------
# _parse_csv_set
# ---------------------------------------------------------------------------

class TestParseCsvSet(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(_parse_csv_set("A,B,C"), frozenset({"A", "B", "C"}))

    def test_strips_whitespace(self):
        self.assertEqual(_parse_csv_set(" A , B , C "), frozenset({"A", "B", "C"}))

    def test_single_item(self):
        self.assertEqual(_parse_csv_set("Read"), frozenset({"Read"}))

    def test_empty_string(self):
        self.assertEqual(_parse_csv_set(""), frozenset())

    def test_trailing_comma(self):
        result = _parse_csv_set("A,B,")
        self.assertEqual(result, frozenset({"A", "B"}))


# ---------------------------------------------------------------------------
# _DEFAULT_ALLOWLISTS
# ---------------------------------------------------------------------------

class TestDefaultAllowlists(unittest.TestCase):

    def test_read_only_excludes_write(self):
        self.assertNotIn("Write", _DEFAULT_ALLOWLISTS["read_only"])
        self.assertNotIn("Edit", _DEFAULT_ALLOWLISTS["read_only"])

    def test_full_execution_includes_write(self):
        self.assertIn("Write", _DEFAULT_ALLOWLISTS["full_execution"])
        self.assertIn("Edit", _DEFAULT_ALLOWLISTS["full_execution"])
        self.assertIn("Bash", _DEFAULT_ALLOWLISTS["full_execution"])

    def test_read_only_includes_read(self):
        self.assertIn("Read", _DEFAULT_ALLOWLISTS["read_only"])

    def test_planning_excludes_write_and_bash(self):
        self.assertNotIn("Write", _DEFAULT_ALLOWLISTS["planning"])
        self.assertNotIn("Bash", _DEFAULT_ALLOWLISTS["planning"])

    def test_file_edit_excludes_bash(self):
        self.assertNotIn("Bash", _DEFAULT_ALLOWLISTS["file_edit"])
        self.assertIn("Write", _DEFAULT_ALLOWLISTS["file_edit"])

    def test_analysis_includes_web_tools(self):
        self.assertIn("WebFetch", _DEFAULT_ALLOWLISTS["analysis"])
        self.assertIn("WebSearch", _DEFAULT_ALLOWLISTS["analysis"])

    def test_verification_includes_bash(self):
        self.assertIn("Bash", _DEFAULT_ALLOWLISTS["verification"])
        self.assertNotIn("Write", _DEFAULT_ALLOWLISTS["verification"])

    def test_all_standard_action_types_present(self):
        for action in ("read_only", "analysis", "file_edit", "full_execution",
                       "verification", "planning"):
            self.assertIn(action, _DEFAULT_ALLOWLISTS)


# ---------------------------------------------------------------------------
# ToolScopePolicy
# ---------------------------------------------------------------------------

class TestToolScopePolicy(unittest.TestCase):

    def _make_policy(self, allowlists=None, default="full_execution"):
        lists = allowlists or dict(_DEFAULT_ALLOWLISTS)
        return ToolScopePolicy(allowlists=lists, default_action_type=default)

    def test_allowed_tools_returns_correct_set(self):
        policy = self._make_policy()
        self.assertEqual(policy.allowed_tools("read_only"), _DEFAULT_ALLOWLISTS["read_only"])

    def test_allowed_tools_falls_back_to_default(self):
        policy = self._make_policy(default="read_only")
        result = policy.allowed_tools("unknown_type")
        self.assertEqual(result, _DEFAULT_ALLOWLISTS["read_only"])

    def test_allowed_tools_unknown_default_returns_empty(self):
        policy = ToolScopePolicy(allowlists={}, default_action_type="nonexistent")
        result = policy.allowed_tools("also_nonexistent")
        self.assertEqual(result, frozenset())

    def test_known_action_types_sorted(self):
        policy = self._make_policy()
        types = policy.known_action_types()
        self.assertEqual(types, sorted(types))

    def test_validate_no_warnings_on_valid(self):
        policy = self._make_policy()
        self.assertEqual(policy.validate(), [])

    def test_validate_warns_on_missing_default(self):
        policy = ToolScopePolicy(
            allowlists=dict(_DEFAULT_ALLOWLISTS),
            default_action_type="nonexistent",
        )
        warnings = policy.validate()
        self.assertTrue(any("nonexistent" in w for w in warnings))

    def test_validate_warns_on_empty_allowlist(self):
        lists = {**_DEFAULT_ALLOWLISTS, "empty_type": frozenset()}
        policy = ToolScopePolicy(allowlists=lists, default_action_type="full_execution")
        warnings = policy.validate()
        self.assertTrue(any("empty_type" in w for w in warnings))

    def test_to_dict_structure(self):
        policy = self._make_policy()
        d = policy.to_dict()
        self.assertIn("allowlists", d)
        self.assertIn("default_action_type", d)
        # allowlists values should be sorted lists
        for tools in d["allowlists"].values():
            self.assertIsInstance(tools, list)
            self.assertEqual(tools, sorted(tools))

    def test_immutable(self):
        policy = self._make_policy()
        with self.assertRaises((AttributeError, TypeError)):
            policy.default_action_type = "read_only"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# load_scope_policy
# ---------------------------------------------------------------------------

class TestLoadScopePolicy(unittest.TestCase):

    def test_loads_defaults_when_settings_missing(self):
        policy = load_scope_policy(settings_path="/nonexistent/settings.json")
        self.assertIn("read_only", policy.known_action_types())
        self.assertEqual(policy.default_action_type, "full_execution")

    def test_override_from_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"SCOPE_READ_ONLY": "Read,Grep"}), encoding="utf-8")
            policy = load_scope_policy(settings_path=p)
        self.assertEqual(policy.allowed_tools("read_only"), frozenset({"Read", "Grep"}))

    def test_custom_action_type_from_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"SCOPE_CUSTOM_TASK": "Read,Bash"}), encoding="utf-8")
            policy = load_scope_policy(settings_path=p)
        self.assertIn("custom_task", policy.known_action_types())
        self.assertEqual(policy.allowed_tools("custom_task"), frozenset({"Read", "Bash"}))

    def test_default_action_type_from_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"SCOPE_DEFAULT_ACTION_TYPE": "read_only"}), encoding="utf-8")
            policy = load_scope_policy(settings_path=p)
        self.assertEqual(policy.default_action_type, "read_only")

    def test_invalid_json_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text("not json", encoding="utf-8")
            policy = load_scope_policy(settings_path=p)
        self.assertIn("full_execution", policy.known_action_types())

    def test_non_scope_keys_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"STALL_THRESHOLD": "5", "DEBUG": "true"}), encoding="utf-8")
            policy = load_scope_policy(settings_path=p)
        # built-in defaults still present
        self.assertIn("read_only", policy.known_action_types())


# ---------------------------------------------------------------------------
# evaluate_scope
# ---------------------------------------------------------------------------

class TestEvaluateScope(unittest.TestCase):

    def _policy(self):
        return load_scope_policy(settings_path="/nonexistent/settings.json")

    def test_all_allowed_returns_true(self):
        policy = self._policy()
        result = evaluate_scope(policy, "read_only", ["Read", "Grep"])
        self.assertTrue(result.allowed)
        self.assertEqual(result.denied, [])

    def test_denied_tool_returns_false(self):
        policy = self._policy()
        result = evaluate_scope(policy, "read_only", ["Read", "Write"])
        self.assertFalse(result.allowed)
        self.assertIn("Write", result.denied)

    def test_multiple_denied_tools(self):
        policy = self._policy()
        result = evaluate_scope(policy, "read_only", ["Write", "Edit", "Bash"])
        # Bash is actually allowed in read_only; Write and Edit are not
        self.assertFalse(result.allowed)
        self.assertIn("Write", result.denied)
        self.assertIn("Edit", result.denied)
        self.assertNotIn("Bash", result.denied)

    def test_empty_requested_always_allowed(self):
        policy = self._policy()
        result = evaluate_scope(policy, "read_only", [])
        self.assertTrue(result.allowed)
        self.assertEqual(result.denied, [])

    def test_full_execution_permits_all_standard_tools(self):
        policy = self._policy()
        tools = ["Read", "Grep", "Glob", "Bash", "Write", "Edit", "WebFetch", "WebSearch"]
        result = evaluate_scope(policy, "full_execution", tools)
        self.assertTrue(result.allowed)

    def test_result_action_type_preserved(self):
        policy = self._policy()
        result = evaluate_scope(policy, "analysis", ["Read"])
        self.assertEqual(result.action_type, "analysis")

    def test_result_requested_preserved(self):
        policy = self._policy()
        tools = ["Read", "Grep"]
        result = evaluate_scope(policy, "read_only", tools)
        self.assertEqual(result.requested, tools)

    def test_to_dict_structure(self):
        policy = self._policy()
        result = evaluate_scope(policy, "read_only", ["Read", "Write"])
        d = result.to_dict()
        self.assertIn("allowed", d)
        self.assertIn("denied", d)
        self.assertIn("action_type", d)
        self.assertIn("requested", d)

    def test_unknown_action_type_falls_back_to_default(self):
        policy = self._policy()
        result = evaluate_scope(policy, "unknown_type", ["Read"])
        # Default is full_execution — Read is permitted there
        self.assertTrue(result.allowed)

    def test_planning_scope_denies_bash(self):
        policy = self._policy()
        result = evaluate_scope(policy, "planning", ["Read", "Bash"])
        self.assertFalse(result.allowed)
        self.assertIn("Bash", result.denied)


if __name__ == "__main__":
    unittest.main()
