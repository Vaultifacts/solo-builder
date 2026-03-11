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
# get_active_agents — file-read path
# ---------------------------------------------------------------------------

class TestGetActiveAgents(unittest.TestCase):

    def setUp(self):
        import tempfile, shutil
        self._tmp = tempfile.mkdtemp()
        self._runtime_dir = Path(self._tmp) / "runtime"
        self._runtime_dir.mkdir()
        self._main_py = self._runtime_dir / "main.py"
        self._main_py.touch()
        self._storage_dir = self._runtime_dir / "storage" / "state"
        self._storage_dir.mkdir(parents=True)
        self._agents_file = self._storage_dir / "active-agents.json"
        self._shutil = shutil

    def tearDown(self):
        self._shutil.rmtree(self._tmp, ignore_errors=True)

    def test_returns_list_when_file_present(self):
        self._agents_file.write_text(
            json.dumps({"active_agent_ids": ["testing_agent", "security_agent"]}),
            encoding="utf-8",
        )
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_active_agents()
        self.assertEqual(result, ["testing_agent", "security_agent"])

    def test_returns_none_when_aawo_not_configured(self):
        with patch.object(bridge, "_aawo_path", return_value=None):
            result = bridge.get_active_agents()
        self.assertIsNone(result)

    def test_returns_none_when_file_missing(self):
        # agents file never created
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_active_agents()
        self.assertIsNone(result)

    def test_returns_none_when_json_invalid(self):
        self._agents_file.write_text("not valid json", encoding="utf-8")
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_active_agents()
        self.assertIsNone(result)

    def test_returns_empty_list_when_key_missing_from_json(self):
        self._agents_file.write_text(json.dumps({}), encoding="utf-8")
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_active_agents()
        self.assertEqual(result, [])


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


# ---------------------------------------------------------------------------
# get_outcome_stats — file-read path
# ---------------------------------------------------------------------------

class TestGetOutcomeStats(unittest.TestCase):

    def setUp(self):
        import tempfile, shutil
        self._tmp = tempfile.mkdtemp()
        self._runtime_dir = Path(self._tmp) / "runtime"
        self._runtime_dir.mkdir()
        self._main_py = self._runtime_dir / "main.py"
        self._main_py.touch()
        self._logs_dir = self._runtime_dir / "storage" / "logs"
        self._logs_dir.mkdir(parents=True)
        self._outcomes_file = self._logs_dir / "outcomes.jsonl"
        self._shutil = shutil

    def tearDown(self):
        self._shutil.rmtree(self._tmp, ignore_errors=True)

    def _write(self, records):
        with open(self._outcomes_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def test_returns_none_when_not_configured(self):
        with patch.object(bridge, "_aawo_path", return_value=None):
            self.assertIsNone(bridge.get_outcome_stats())

    def test_returns_none_when_file_missing(self):
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            self.assertIsNone(bridge.get_outcome_stats())

    def test_returns_dict_with_counts(self):
        self._write([
            {"agent_id": "testing_agent", "outcome": "success"},
            {"agent_id": "testing_agent", "outcome": "success"},
            {"agent_id": "testing_agent", "outcome": "fail"},
        ])
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_outcome_stats()
        self.assertEqual(result["testing_agent"]["success"], 2)
        self.assertEqual(result["testing_agent"]["fail"], 1)
        self.assertEqual(result["testing_agent"]["total"], 3)

    def test_success_rate_computed(self):
        self._write([
            {"agent_id": "testing_agent", "outcome": "success"},
            {"agent_id": "testing_agent", "outcome": "fail"},
        ])
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_outcome_stats()
        self.assertAlmostEqual(result["testing_agent"]["success_rate"], 0.5, places=3)

    def test_multiple_agents(self):
        self._write([
            {"agent_id": "testing_agent", "outcome": "success"},
            {"agent_id": "security_agent", "outcome": "fail"},
        ])
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_outcome_stats()
        self.assertIn("testing_agent", result)
        self.assertIn("security_agent", result)

    def test_ignores_bad_json_lines(self):
        with open(self._outcomes_file, "w", encoding="utf-8") as f:
            f.write("not-json\n")
            f.write(json.dumps({"agent_id": "testing_agent", "outcome": "success"}) + "\n")
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_outcome_stats()
        self.assertEqual(result["testing_agent"]["total"], 1)

    def test_returns_none_when_no_valid_records(self):
        self._write([{"outcome": "success"}])  # no agent_id
        with patch.object(bridge, "_aawo_path", return_value=self._main_py):
            result = bridge.get_outcome_stats()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
