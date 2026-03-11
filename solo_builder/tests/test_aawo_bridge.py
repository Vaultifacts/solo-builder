"""Tests for utils/aawo_bridge.py"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import utils.aawo_bridge as bridge


def _mock_run(stdout: str, returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout     = stdout
    m.stderr     = ""
    return m


_ROUTE_JSON = json.dumps({
    "task":               "run tests",
    "selected_agent_id":  "testing_agent",
    "score":              1.0,
    "reasoning":          ["keyword match: 'test'"],
    "fallback":           False,
    "policy_blocked":     False,
})

_SNAP_JSON = json.dumps({
    "signals":      {"has_tests": True, "has_ci": False},
    "complexity":   {"value": "medium", "file_count": 50},
    "risk_factors": ["no_ci"],
    "captured_at":  "2026-03-10T00:00:00Z",
})


# ---------------------------------------------------------------------------
# _run / route_task / get_snapshot — subprocess layer
# ---------------------------------------------------------------------------

class TestRunLayer(unittest.TestCase):

    def _patch_path(self, exists=True):
        fake = MagicMock(spec=Path)
        fake.exists.return_value = exists
        return patch.object(bridge, "_aawo_path", return_value=fake if exists else None)

    def test_route_task_returns_dict_on_success(self):
        with self._patch_path(), \
             patch("subprocess.run", return_value=_mock_run(_ROUTE_JSON)):
            result = bridge.route_task("run tests")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["selected_agent_id"], "testing_agent")

    def test_route_task_returns_none_on_timeout(self):
        with self._patch_path(), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = bridge.route_task("run tests")
        self.assertIsNone(result)

    def test_route_task_returns_none_on_nonzero_exit(self):
        with self._patch_path(), \
             patch("subprocess.run", return_value=_mock_run("", returncode=1)):
            result = bridge.route_task("run tests")
        self.assertIsNone(result)

    def test_route_task_returns_none_when_aawo_not_found(self):
        with patch.object(bridge, "_aawo_path", return_value=None):
            result = bridge.route_task("run tests")
        self.assertIsNone(result)

    def test_route_task_returns_none_on_json_error(self):
        with self._patch_path(), \
             patch("subprocess.run", return_value=_mock_run("not json")):
            result = bridge.route_task("run tests")
        self.assertIsNone(result)

    def test_get_snapshot_returns_dict_on_success(self):
        with self._patch_path(), \
             patch("subprocess.run", return_value=_mock_run(_SNAP_JSON)):
            result = bridge.get_snapshot()
        self.assertIsInstance(result, dict)
        self.assertIn("signals", result)

    def test_get_snapshot_returns_none_on_timeout(self):
        with self._patch_path(), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = bridge.get_snapshot()
        self.assertIsNone(result)

    def test_run_cycle_returns_true_on_success(self):
        with self._patch_path(), \
             patch("subprocess.run", return_value=_mock_run("", returncode=0)):
            result = bridge.run_cycle()
        self.assertTrue(result)

    def test_run_cycle_returns_false_on_timeout(self):
        with self._patch_path(), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = bridge.run_cycle()
        self.assertFalse(result)

    def test_run_cycle_returns_false_on_nonzero_exit(self):
        with self._patch_path(), \
             patch("subprocess.run", return_value=_mock_run("", returncode=1)):
            result = bridge.run_cycle()
        self.assertFalse(result)

    def test_run_cycle_returns_false_when_aawo_not_found(self):
        with patch.object(bridge, "_aawo_path", return_value=None):
            result = bridge.run_cycle()
        self.assertFalse(result)

    def test_run_cycle_uses_incremental_flag(self):
        """Cycle always passes --incremental so it reuses prior snapshot."""
        calls = []
        def _fake_run(args, **kwargs):
            calls.append(args)
            return _mock_run("", returncode=0)
        fake = MagicMock(spec=Path)
        fake.exists.return_value = True
        with patch.object(bridge, "_aawo_path", return_value=fake), \
             patch("subprocess.run", side_effect=_fake_run):
            bridge.run_cycle(repo_path=".")
        self.assertIn("--incremental", calls[0])


# ---------------------------------------------------------------------------
# Security invariants
# ---------------------------------------------------------------------------

class TestSubprocessSecurity(unittest.TestCase):

    def _capture_call(self):
        calls = []
        def _fake_run(args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return _mock_run(_ROUTE_JSON)
        return calls, _fake_run

    def test_subprocess_uses_shell_false(self):
        fake = MagicMock(spec=Path)
        fake.exists.return_value = True
        calls, fake_run = self._capture_call()
        with patch.object(bridge, "_aawo_path", return_value=fake), \
             patch("subprocess.run", side_effect=fake_run):
            bridge.route_task("run tests")
        self.assertFalse(calls[0]["kwargs"].get("shell", True))

    def test_subprocess_args_is_list(self):
        fake = MagicMock(spec=Path)
        fake.exists.return_value = True
        calls, fake_run = self._capture_call()
        with patch.object(bridge, "_aawo_path", return_value=fake), \
             patch("subprocess.run", side_effect=fake_run):
            bridge.route_task("run tests")
        self.assertIsInstance(calls[0]["args"], list)


# ---------------------------------------------------------------------------
# enrich_subtask
# ---------------------------------------------------------------------------

class TestEnrichSubtask(unittest.TestCase):

    def _route_testing_agent(self, *_a, **_kw):
        return {
            "task": "run tests", "selected_agent_id": "testing_agent",
            "score": 1.0, "reasoning": [], "fallback": False, "policy_blocked": False,
        }

    def test_enrich_subtask_sets_action_type_and_tools(self):
        st = {"description": "run tests"}
        with patch.object(bridge, "route_task", side_effect=self._route_testing_agent):
            bridge.enrich_subtask(st, "run tests")
        self.assertEqual(st["action_type"], "read_only")
        self.assertEqual(st["tools"], "Read,Grep,Glob")

    def test_enrich_subtask_skips_if_tools_already_set(self):
        st = {"description": "run tests", "tools": "Glob"}
        with patch.object(bridge, "route_task") as mock_route:
            bridge.enrich_subtask(st, "run tests")
        mock_route.assert_not_called()
        self.assertEqual(st["tools"], "Glob")  # unchanged

    def test_enrich_subtask_skips_on_policy_blocked(self):
        st = {"description": "run tests"}
        with patch.object(bridge, "route_task", return_value={
            "selected_agent_id": "testing_agent", "policy_blocked": True,
        }):
            bridge.enrich_subtask(st, "run tests")
        self.assertNotIn("action_type", st)

    def test_enrich_subtask_skips_on_none(self):
        st = {"description": "run tests"}
        with patch.object(bridge, "route_task", return_value=None):
            bridge.enrich_subtask(st, "run tests")
        self.assertNotIn("action_type", st)

    def test_enrich_subtask_injects_aawo_routing_metadata(self):
        st = {"description": "run tests"}
        with patch.object(bridge, "route_task", side_effect=self._route_testing_agent):
            bridge.enrich_subtask(st, "run tests")
        self.assertIn("_aawo_routing", st)
        self.assertEqual(st["_aawo_routing"]["agent_id"], "testing_agent")

    def test_enrich_subtask_skips_unknown_agent(self):
        st = {"description": "run tests"}
        with patch.object(bridge, "route_task", return_value={
            "selected_agent_id": "unknown_agent_xyz", "policy_blocked": False,
        }):
            bridge.enrich_subtask(st, "run tests")
        self.assertNotIn("action_type", st)


# ---------------------------------------------------------------------------
# resolve_executor_config / _load_mapping
# ---------------------------------------------------------------------------

class TestResolveExecutorConfig(unittest.TestCase):

    def test_known_agent_testing(self):
        cfg = bridge.resolve_executor_config("testing_agent")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["action_type"], "read_only")
        self.assertIn("Read", cfg["tools"])

    def test_known_agent_security(self):
        cfg = bridge.resolve_executor_config("security_agent")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["action_type"], "analysis")

    def test_unknown_agent_returns_none(self):
        result = bridge.resolve_executor_config("nonexistent_agent")
        self.assertIsNone(result)

    def test_load_mapping_merges_settings_override(self):
        override_cfg = json.dumps({"AAWO_AGENT_MAPPING": {
            "testing_agent": {"action_type": "full_execution", "tools": "Read"}
        }})
        with patch.object(bridge, "_load_settings", return_value=json.loads(override_cfg)):
            mapping = bridge._load_mapping()
        self.assertEqual(mapping["testing_agent"]["action_type"], "full_execution")
        # other agents still present from builtin
        self.assertIn("security_agent", mapping)

    def test_load_mapping_non_dict_override_ignored(self):
        with patch.object(bridge, "_load_settings", return_value={"AAWO_AGENT_MAPPING": "bad"}):
            mapping = bridge._load_mapping()
        self.assertEqual(mapping, bridge._BUILTIN_MAPPING)


if __name__ == "__main__":
    unittest.main()
