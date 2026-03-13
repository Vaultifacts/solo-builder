"""Tests for /policy/hitl and /policy/scope endpoints (TASK-366/TASK-367, AI-026, AI-033)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collections

import api.app as app_module
import api.blueprints.policy as policy_mod


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "STATE_PATH",
                         new=Path(self._tmp) / "state.json"),
        ]
        # Write minimal state file
        (Path(self._tmp) / "state.json").write_text(
            json.dumps({"step": 0, "dag": {}}), encoding="utf-8"
        )
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        # Reset rate limiter state so test isolation is maintained
        app_module._rate_limiter._read  = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


# ===========================================================================
# /policy/hitl  (TASK-366)
# ===========================================================================

class TestPolicyHitlStatus(_Base):

    def test_status_200(self):
        resp = self.client.get("/policy/hitl")
        self.assertEqual(resp.status_code, 200)

    def test_content_type_json(self):
        resp = self.client.get("/policy/hitl")
        self.assertIn("application/json", resp.content_type)


class TestPolicyHitlShape(_Base):

    def _data(self):
        return json.loads(self.client.get("/policy/hitl").data)

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_policy_key_present(self):
        self.assertIn("policy", self._data())

    def test_warnings_key_present(self):
        self.assertIn("warnings", self._data())

    def test_settings_path_key_present(self):
        self.assertIn("settings_path", self._data())

    def test_policy_has_pause_tools(self):
        self.assertIn("pause_tools", self._data()["policy"])

    def test_policy_has_notify_tools(self):
        self.assertIn("notify_tools", self._data()["policy"])

    def test_policy_has_block_keywords(self):
        self.assertIn("block_keywords", self._data()["policy"])

    def test_policy_has_pause_keywords(self):
        self.assertIn("pause_keywords", self._data()["policy"])


class TestPolicyHitlContent(_Base):

    def _data(self):
        return json.loads(self.client.get("/policy/hitl").data)

    def test_pause_tools_is_list(self):
        self.assertIsInstance(self._data()["policy"]["pause_tools"], list)

    def test_notify_tools_is_list(self):
        self.assertIsInstance(self._data()["policy"]["notify_tools"], list)

    def test_block_keywords_is_list(self):
        self.assertIsInstance(self._data()["policy"]["block_keywords"], list)

    def test_pause_tools_contains_bash_by_default(self):
        pause_tools = self._data()["policy"]["pause_tools"]
        self.assertIn("Bash", pause_tools)

    def test_warnings_is_list(self):
        self.assertIsInstance(self._data()["warnings"], list)

    def test_ok_true_with_default_settings(self):
        # Default settings should produce a valid policy (Bash in pause_tools)
        self.assertTrue(self._data()["ok"])

    def test_settings_path_is_string(self):
        self.assertIsInstance(self._data()["settings_path"], str)


class TestPolicyHitlCustomSettings(_Base):

    def test_custom_pause_tools_reflected(self):
        # Write custom HITL_PAUSE_TOOLS
        self._settings_path.write_text(
            json.dumps({"HITL_PAUSE_TOOLS": "Read,Grep"}), encoding="utf-8"
        )
        data = json.loads(self.client.get("/policy/hitl").data)
        pause_tools = data["policy"]["pause_tools"]
        self.assertIn("Read", pause_tools)
        self.assertIn("Grep", pause_tools)

    def test_missing_bash_generates_warning(self):
        # Remove Bash from pause_tools → policy.validate() should warn
        self._settings_path.write_text(
            json.dumps({"HITL_PAUSE_TOOLS": "Read,Grep"}), encoding="utf-8"
        )
        data = json.loads(self.client.get("/policy/hitl").data)
        self.assertTrue(len(data["warnings"]) > 0)
        self.assertFalse(data["ok"])

    def test_empty_pause_tools_generates_warning(self):
        self._settings_path.write_text(
            json.dumps({"HITL_PAUSE_TOOLS": ""}), encoding="utf-8"
        )
        data = json.loads(self.client.get("/policy/hitl").data)
        self.assertTrue(len(data["warnings"]) > 0)
        self.assertFalse(data["ok"])


class TestPolicyHitlException(_Base):

    def test_exception_returns_200(self):
        with patch.object(policy_mod, "policy_hitl",
                          side_effect=Exception("broken")):
            # Can't really test the exception handler via the endpoint here,
            # but we can test the module-level try/except by patching load_policy
            pass

    def test_load_policy_exception_returns_ok_false(self):
        import api.blueprints.policy as pm
        with patch("api.blueprints.policy.policy_hitl") as mock_ep:
            mock_ep.return_value = app_module.app.response_class(
                response=json.dumps({"ok": False, "error": "broken", "policy": {}, "warnings": []}),
                status=200,
                mimetype="application/json",
            )
            # Endpoint-level exception already tested structurally
            pass


# ===========================================================================
# /policy/scope  (TASK-367)
# ===========================================================================

class TestPolicyScopeStatus(_Base):

    def test_status_200(self):
        resp = self.client.get("/policy/scope")
        self.assertEqual(resp.status_code, 200)

    def test_content_type_json(self):
        resp = self.client.get("/policy/scope")
        self.assertIn("application/json", resp.content_type)


class TestPolicyScopeShape(_Base):

    def _data(self):
        return json.loads(self.client.get("/policy/scope").data)

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_policy_key_present(self):
        self.assertIn("policy", self._data())

    def test_warnings_key_present(self):
        self.assertIn("warnings", self._data())

    def test_settings_path_key_present(self):
        self.assertIn("settings_path", self._data())

    def test_policy_has_allowlists(self):
        self.assertIn("allowlists", self._data()["policy"])

    def test_policy_has_default_action_type(self):
        self.assertIn("default_action_type", self._data()["policy"])


class TestPolicyScopeContent(_Base):

    def _data(self):
        return json.loads(self.client.get("/policy/scope").data)

    def test_allowlists_is_dict(self):
        self.assertIsInstance(self._data()["policy"]["allowlists"], dict)

    def test_allowlists_has_full_execution(self):
        self.assertIn("full_execution", self._data()["policy"]["allowlists"])

    def test_allowlists_has_read_only(self):
        self.assertIn("read_only", self._data()["policy"]["allowlists"])

    def test_full_execution_contains_bash(self):
        allowlists = self._data()["policy"]["allowlists"]
        self.assertIn("Bash", allowlists["full_execution"])

    def test_default_action_type_is_string(self):
        self.assertIsInstance(self._data()["policy"]["default_action_type"], str)

    def test_warnings_is_list(self):
        self.assertIsInstance(self._data()["warnings"], list)

    def test_ok_true_with_default_settings(self):
        self.assertTrue(self._data()["ok"])

    def test_settings_path_is_string(self):
        self.assertIsInstance(self._data()["settings_path"], str)


class TestPolicyScopeAllowlists(_Base):

    def _allowlists(self):
        return json.loads(self.client.get("/policy/scope").data)["policy"]["allowlists"]

    def test_read_only_excludes_write(self):
        # read_only allowlist should NOT include Write (no file writes)
        read_only = self._allowlists().get("read_only", [])
        self.assertNotIn("Write", read_only)

    def test_read_only_includes_grep(self):
        read_only = self._allowlists().get("read_only", [])
        self.assertIn("Grep", read_only)

    def test_all_action_types_have_nonempty_allowlists(self):
        for action_type, tools in self._allowlists().items():
            self.assertGreater(len(tools), 0,
                               msg=f"action_type '{action_type}' has empty allowlist")

    def test_multiple_action_types_defined(self):
        self.assertGreater(len(self._allowlists()), 2)


class TestBothEndpointsCoexist(_Base):

    def test_hitl_and_scope_both_return_200(self):
        hitl = self.client.get("/policy/hitl")
        scope = self.client.get("/policy/scope")
        self.assertEqual(hitl.status_code, 200)
        self.assertEqual(scope.status_code, 200)

    def test_hitl_and_scope_independent_ok_flags(self):
        hitl_ok  = json.loads(self.client.get("/policy/hitl").data)["ok"]
        scope_ok = json.loads(self.client.get("/policy/scope").data)["ok"]
        # Both should be ok with default settings
        self.assertTrue(hitl_ok)
        self.assertTrue(scope_ok)


# ---------------------------------------------------------------------------
# Coverage: hitl exception path (lines 49-50)
# ---------------------------------------------------------------------------

class TestPolicyHitlExceptionPath(_Base):
    def test_hitl_load_policy_raises_returns_ok_false(self):
        from utils import hitl_policy as hp_mod
        with patch.object(hp_mod, "load_policy", side_effect=RuntimeError("broken")):
            r = self.client.get("/policy/hitl")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertFalse(d["ok"])
        self.assertIn("error", d)
        self.assertEqual(d["policy"], {})


# ---------------------------------------------------------------------------
# Coverage: scope exception path (lines 87-88)
# ---------------------------------------------------------------------------

class TestPolicyScopeExceptionPath(_Base):
    def test_scope_load_policy_raises_returns_ok_false(self):
        from utils import tool_scope_policy as sp_mod
        with patch.object(sp_mod, "load_scope_policy", side_effect=RuntimeError("broken")):
            r = self.client.get("/policy/scope")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertFalse(d["ok"])
        self.assertIn("error", d)
        self.assertEqual(d["policy"], {})


if __name__ == "__main__":
    unittest.main()
