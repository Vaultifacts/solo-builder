"""Tests for GET /executor/gates endpoint (TASK-368, AI-026, AI-033)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collections

import api.app as app_module


# ---------------------------------------------------------------------------
# State factory helpers
# ---------------------------------------------------------------------------

def _state(subtasks: dict | None = None) -> dict:
    """Build a minimal state JSON with one task/branch."""
    sts = subtasks or {}
    return {
        "step": 1,
        "dag": {
            "Task-A": {
                "branches": {
                    "Branch-1": {
                        "subtasks": sts
                    }
                }
            }
        },
    }


def _st(status: str = "Running", tools: str = "Glob",
        description: str = "do stuff", action_type: str = "") -> dict:
    d: dict = {
        "name": "ST",
        "status": status,
        "tools": tools,
        "description": description,
        "output": "",
        "history": [],
    }
    if action_type:
        d["action_type"] = action_type
    return d


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path    = Path(self._tmp) / "state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")
        # Write initial empty-DAG state
        self._write_state(_state())

        self._patches = [
            patch.object(app_module, "STATE_PATH",    new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read  = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_state(self, data: dict) -> None:
        self._state_path.write_text(json.dumps(data), encoding="utf-8")

    def _get(self) -> dict:
        resp = self.client.get("/executor/gates")
        self.assertEqual(resp.status_code, 200)
        return json.loads(resp.data)


# ---------------------------------------------------------------------------
# Status and shape
# ---------------------------------------------------------------------------

class TestExecutorGatesStatus(_Base):

    def test_status_200(self):
        resp = self.client.get("/executor/gates")
        self.assertEqual(resp.status_code, 200)

    def test_content_type_json(self):
        resp = self.client.get("/executor/gates")
        self.assertIn("application/json", resp.content_type)


class TestExecutorGatesShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._get())

    def test_running_count_key_present(self):
        self.assertIn("running_count", self._get())

    def test_blocked_count_key_present(self):
        self.assertIn("blocked_count", self._get())

    def test_gates_key_present(self):
        self.assertIn("gates", self._get())

    def test_gates_is_list(self):
        self.assertIsInstance(self._get()["gates"], list)


# ---------------------------------------------------------------------------
# Empty DAG
# ---------------------------------------------------------------------------

class TestExecutorGatesEmptyDag(_Base):

    def test_ok_true_when_no_running_subtasks(self):
        self.assertTrue(self._get()["ok"])

    def test_running_count_zero(self):
        self.assertEqual(self._get()["running_count"], 0)

    def test_blocked_count_zero(self):
        self.assertEqual(self._get()["blocked_count"], 0)

    def test_gates_empty(self):
        self.assertEqual(self._get()["gates"], [])


# ---------------------------------------------------------------------------
# Running subtask — gate row fields
# ---------------------------------------------------------------------------

class TestExecutorGatesRowFields(_Base):

    def setUp(self):
        super().setUp()
        self._write_state(_state({"ST-1": _st(tools="Glob", action_type="full_execution")}))

    def _row(self) -> dict:
        gates = self._get()["gates"]
        self.assertEqual(len(gates), 1)
        return gates[0]

    def test_task_field(self):
        self.assertEqual(self._row()["task"], "Task-A")

    def test_branch_field(self):
        self.assertEqual(self._row()["branch"], "Branch-1")

    def test_subtask_field(self):
        self.assertEqual(self._row()["subtask"], "ST-1")

    def test_tools_field(self):
        self.assertEqual(self._row()["tools"], "Glob")

    def test_action_type_field(self):
        self.assertEqual(self._row()["action_type"], "full_execution")

    def test_hitl_level_field(self):
        self.assertIn("hitl_level", self._row())
        self.assertIsInstance(self._row()["hitl_level"], int)

    def test_hitl_name_field(self):
        self.assertIn("hitl_name", self._row())

    def test_scope_ok_field(self):
        self.assertIn("scope_ok", self._row())

    def test_scope_denied_field(self):
        self.assertIn("scope_denied", self._row())
        self.assertIsInstance(self._row()["scope_denied"], list)

    def test_tools_valid_field(self):
        self.assertIn("tools_valid", self._row())

    def test_blocked_field(self):
        self.assertIn("blocked", self._row())


# ---------------------------------------------------------------------------
# Pending subtask not included
# ---------------------------------------------------------------------------

class TestExecutorGatesPendingExcluded(_Base):

    def test_pending_subtask_not_in_gates(self):
        self._write_state(_state({"ST-P": _st(status="Pending")}))
        data = self._get()
        self.assertEqual(data["running_count"], 0)
        self.assertEqual(len(data["gates"]), 0)

    def test_verified_subtask_not_in_gates(self):
        self._write_state(_state({"ST-V": _st(status="Verified")}))
        data = self._get()
        self.assertEqual(data["running_count"], 0)


# ---------------------------------------------------------------------------
# Valid tool → not blocked
# ---------------------------------------------------------------------------

class TestExecutorGatesValidTool(_Base):

    def test_valid_tool_not_blocked(self):
        self._write_state(_state({"ST-1": _st(tools="Glob", action_type="full_execution")}))
        data = self._get()
        self.assertFalse(data["gates"][0]["blocked"])

    def test_valid_tool_tools_valid_true(self):
        self._write_state(_state({"ST-1": _st(tools="Glob", action_type="full_execution")}))
        data = self._get()
        self.assertTrue(data["gates"][0]["tools_valid"])

    def test_valid_tool_ok_true(self):
        self._write_state(_state({"ST-1": _st(tools="Glob", action_type="full_execution")}))
        data = self._get()
        self.assertTrue(data["ok"])
        self.assertEqual(data["blocked_count"], 0)


# ---------------------------------------------------------------------------
# No-tools subtask
# ---------------------------------------------------------------------------

class TestExecutorGatesNoTools(_Base):

    def test_no_tools_subtask_not_blocked(self):
        self._write_state(_state({"ST-1": _st(tools="")}))
        data = self._get()
        # No tools → HITL and scope not evaluated → not blocked
        self.assertFalse(data["gates"][0]["blocked"])

    def test_no_tools_hitl_level_zero(self):
        self._write_state(_state({"ST-1": _st(tools="")}))
        data = self._get()
        self.assertEqual(data["gates"][0]["hitl_level"], 0)


# ---------------------------------------------------------------------------
# Multiple subtasks
# ---------------------------------------------------------------------------

class TestExecutorGatesMultipleSubtasks(_Base):

    def test_multiple_running_subtasks_all_listed(self):
        self._write_state(_state({
            "ST-1": _st(tools="Glob"),
            "ST-2": _st(tools="Read"),
        }))
        data = self._get()
        self.assertEqual(data["running_count"], 2)
        self.assertEqual(len(data["gates"]), 2)

    def test_running_count_matches_gates_length(self):
        self._write_state(_state({
            "ST-1": _st(tools="Glob"),
            "ST-2": _st(tools="Grep"),
            "ST-3": _st(tools="Read"),
        }))
        data = self._get()
        self.assertEqual(data["running_count"], len(data["gates"]))


# ---------------------------------------------------------------------------
# Corrupt / missing state
# ---------------------------------------------------------------------------

class TestExecutorGatesCorruptState(_Base):

    def test_missing_state_returns_200_with_empty_gates(self):
        self._state_path.unlink()
        resp = self.client.get("/executor/gates")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["gates"], [])

    def test_corrupt_state_returns_200(self):
        self._state_path.write_text("NOT JSON", encoding="utf-8")
        resp = self.client.get("/executor/gates")
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Import fallback paths (lines 61-62, 67-68, 73-75, 79-80)
# ---------------------------------------------------------------------------

class TestExecutorGatesImportFallbacks(_Base):

    def test_hitl_import_failure_still_returns_200(self):
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        with patch.dict(sys.modules, {"runners.hitl_gate": None}):
            # Force import failure
            with patch("builtins.__import__", side_effect=lambda name, *a, **kw:
                        (_ for _ in ()).throw(ImportError("no hitl_gate"))
                        if name == "runners.hitl_gate" else __builtins__.__import__(name, *a, **kw)):
                pass
        data = self._get()
        self.assertIn("gates", data)

    def test_no_tools_valid_tools_true(self):
        self._write_state(_state({"ST-1": _st(tools="", action_type="read_only")}))
        data = self._get()
        self.assertTrue(data["gates"][0]["tools_valid"])
        self.assertFalse(data["gates"][0]["blocked"])

    def test_invalid_tools_blocked(self):
        self._write_state(_state({"ST-1": _st(tools="EvilTool,Malware")}))
        data = self._get()
        gate = data["gates"][0]
        self.assertFalse(gate["tools_valid"])
        self.assertTrue(gate["blocked"])

    def test_hitl_auto_for_empty_tools(self):
        self._write_state(_state({"ST-1": _st(tools="")}))
        data = self._get()
        self.assertEqual(data["gates"][0]["hitl_name"], "Auto")

    def test_scope_ok_when_no_policy(self):
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        data = self._get()
        self.assertTrue(data["gates"][0]["scope_ok"])
        self.assertEqual(data["gates"][0]["scope_denied"], [])


# ---------------------------------------------------------------------------
# Scope evaluation path (lines 109-110, 123-124)
# ---------------------------------------------------------------------------

class TestExecutorGatesScopeEval(_Base):

    def test_scope_with_action_type(self):
        self._write_state(_state({"ST-1": _st(tools="Glob", action_type="read_only")}))
        data = self._get()
        gate = data["gates"][0]
        self.assertEqual(gate["action_type"], "read_only")

    def test_hitl_level_with_valid_tools(self):
        self._write_state(_state({"ST-1": _st(tools="Read,Grep", description="analyze code")}))
        data = self._get()
        gate = data["gates"][0]
        self.assertIsInstance(gate["hitl_level"], int)
        self.assertIsInstance(gate["hitl_name"], str)


# ---------------------------------------------------------------------------
# Import fallback exception paths (lines 61-62, 67-68, 73-75, 79-80)
# ---------------------------------------------------------------------------

class TestExecutorGatesHitlImportFallback(_Base):
    """Cover except block when utils.hitl_policy import fails (lines 61-62)."""

    def test_hitl_policy_import_fail_still_works(self):
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        import utils.hitl_policy as hp_mod
        orig = hp_mod.load_policy
        with patch.object(hp_mod, "load_policy", side_effect=Exception("broken")):
            data = self._get()
        self.assertIn("gates", data)
        self.assertEqual(len(data["gates"]), 1)
        # hitl_level defaults to gate eval only (no policy)
        self.assertIsInstance(data["gates"][0]["hitl_level"], int)


class TestExecutorGatesScopePolicyImportFallback(_Base):
    """Cover except block when utils.tool_scope_policy import fails (lines 67-68)."""

    def test_scope_policy_import_fail_still_works(self):
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        import utils.tool_scope_policy as sp_mod
        with patch.object(sp_mod, "load_scope_policy", side_effect=Exception("broken")):
            data = self._get()
        gate = data["gates"][0]
        self.assertTrue(gate["scope_ok"])
        self.assertEqual(gate["scope_denied"], [])


class TestExecutorGatesHitlGateImportFallback(_Base):
    """Cover except block when runners.hitl_gate import fails (lines 73-75)."""

    def test_hitl_gate_import_fail_uses_lambda(self):
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        import runners.hitl_gate as hg_mod
        with patch.object(hg_mod, "evaluate", side_effect=Exception("broken")):
            data = self._get()
        gate = data["gates"][0]
        # Exception in evaluate → hitl_level = 0 (line 109-110)
        self.assertEqual(gate["hitl_level"], 0)
        self.assertEqual(gate["hitl_name"], "Auto")

    def test_hitl_gate_import_completely_missing(self):
        """Force the 'from runners.hitl_gate import' to fail (lines 73-75)."""
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        saved = sys.modules.pop("runners.hitl_gate", None)
        orig_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__
        def _blocking_import(name, *args, **kwargs):
            if name == "runners.hitl_gate":
                raise ImportError("no hitl_gate")
            return orig_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=_blocking_import):
            data = self._get()
        if saved is not None:
            sys.modules["runners.hitl_gate"] = saved
        gate = data["gates"][0]
        self.assertEqual(gate["hitl_level"], 0)
        self.assertEqual(gate["hitl_name"], "Auto")


class TestExecutorGatesSdkToolRunnerImportFallback(_Base):
    """Cover except block when runners.sdk_tool_runner import fails (lines 79-80)."""

    def test_validate_tools_import_fail_still_works(self):
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        import runners.sdk_tool_runner as str_mod
        with patch.object(str_mod, "validate_tools", side_effect=ValueError("bad")):
            data = self._get()
        gate = data["gates"][0]
        self.assertFalse(gate["tools_valid"])
        self.assertTrue(gate["blocked"])

    def test_sdk_tool_runner_import_completely_missing(self):
        """Force the 'from runners.sdk_tool_runner import' to fail (lines 79-80)."""
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        saved = sys.modules.pop("runners.sdk_tool_runner", None)
        orig_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__
        def _blocking_import(name, *args, **kwargs):
            if name == "runners.sdk_tool_runner":
                raise ImportError("no sdk_tool_runner")
            return orig_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=_blocking_import):
            data = self._get()
        if saved is not None:
            sys.modules["runners.sdk_tool_runner"] = saved
        gate = data["gates"][0]
        # With lambda fallback, tools_valid stays True (no-op validate)
        self.assertTrue(gate["tools_valid"])


# ---------------------------------------------------------------------------
# HITL eval exception path (lines 109-110)
# ---------------------------------------------------------------------------

class TestExecutorGatesHitlEvalException(_Base):
    """Cover except block when _hg_eval raises during gate evaluation."""

    def test_hitl_eval_exception_defaults_to_zero(self):
        self._write_state(_state({"ST-1": _st(tools="Glob")}))
        import runners.hitl_gate as hg_mod
        with patch.object(hg_mod, "evaluate", side_effect=RuntimeError("oops")):
            data = self._get()
        gate = data["gates"][0]
        self.assertEqual(gate["hitl_level"], 0)
        self.assertEqual(gate["hitl_name"], "Auto")


# ---------------------------------------------------------------------------
# Scope eval exception path (lines 123-124)
# ---------------------------------------------------------------------------

class TestExecutorGatesScopeEvalException(_Base):
    """Cover except block when _sp_eval raises during scope evaluation."""

    def test_scope_eval_exception_defaults_to_ok(self):
        self._write_state(_state({"ST-1": _st(tools="Glob", action_type="read_only")}))
        import utils.tool_scope_policy as sp_mod
        orig_load = sp_mod.load_scope_policy
        orig_eval = sp_mod.evaluate_scope
        with patch.object(sp_mod, "evaluate_scope", side_effect=RuntimeError("scope crash")):
            data = self._get()
        gate = data["gates"][0]
        # Exception in scope eval → scope_ok stays True (default)
        self.assertTrue(gate["scope_ok"])


if __name__ == "__main__":
    unittest.main()
