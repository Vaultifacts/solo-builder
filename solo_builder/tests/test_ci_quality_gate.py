"""Tests for tools/ci_quality_gate.py (TASK-343)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Cross-platform commands that work without shell=True
_PY = sys.executable
_PASS_CMD = f'"{_PY}" -c pass'
_FAIL_CMD = f'"{_PY}" -c "import sys; sys.exit(1)"'

# ---------------------------------------------------------------------------
# Load module from tools/
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "ci_quality_gate", _TOOLS_DIR / "ci_quality_gate.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_gate         = _mod.run_gate
_tool_definitions = _mod._tool_definitions
ToolResult        = _mod.ToolResult


# ---------------------------------------------------------------------------
# _tool_definitions
# ---------------------------------------------------------------------------

class TestToolDefinitions(unittest.TestCase):

    def test_returns_six_tools(self):
        self.assertEqual(len(_tool_definitions()), 6)

    def test_all_have_name_and_command(self):
        for td in _tool_definitions():
            self.assertIn("name", td)
            self.assertIn("command", td)
            self.assertTrue(td["name"])
            self.assertTrue(td["command"])

    def test_expected_tool_names(self):
        names = {td["name"] for td in _tool_definitions()}
        for expected in ("threat-model", "context-window", "slo-check",
                         "dep-audit", "debt-scan", "pre-release"):
            self.assertIn(expected, names)

    def test_pre_release_has_longest_timeout(self):
        timeouts = {td["name"]: td.get("timeout", 60) for td in _tool_definitions()}
        self.assertGreater(timeouts["pre-release"], timeouts["threat-model"])

    def test_all_use_python_executable(self):
        for td in _tool_definitions():
            self.assertIn("python", td["command"].lower())


# ---------------------------------------------------------------------------
# run_gate — pass/fail logic
# ---------------------------------------------------------------------------

class TestRunGate(unittest.TestCase):

    def _all_passing(self):
        """Patch _tool_definitions to return two fast-passing tools."""
        def fake_defs():
            return [
                {"name": "t1", "command": _PASS_CMD, "timeout": 5},
                {"name": "t2", "command": _PASS_CMD, "timeout": 5},
            ]
        return patch.object(_mod, "_tool_definitions", fake_defs)

    def _one_failing(self):
        def fake_defs():
            return [
                {"name": "t1", "command": _PASS_CMD, "timeout": 5},
                {"name": "t2", "command": _FAIL_CMD, "timeout": 5},
            ]
        return patch.object(_mod, "_tool_definitions", fake_defs)

    def test_returns_0_when_all_pass(self):
        with self._all_passing():
            code = run_gate(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_1_when_any_fail(self):
        with self._one_failing():
            code = run_gate(quiet=True)
        self.assertEqual(code, 1)

    def test_skip_removes_tool(self):
        """If a tool is skipped it should not appear in results."""
        def fake_defs():
            return [
                {"name": "t1", "command": _PASS_CMD, "timeout": 5},
                {"name": "t2", "command": _FAIL_CMD, "timeout": 5},  # would fail
            ]
        with patch.object(_mod, "_tool_definitions", fake_defs):
            code = run_gate(quiet=True, skip={"t2"})
        self.assertEqual(code, 0)

    def test_skip_empty_set_runs_all(self):
        with self._all_passing():
            code = run_gate(quiet=True, skip=set())
        self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

class TestJsonOutput(unittest.TestCase):

    def _passing_patch(self):
        def fake_defs():
            return [{"name": "g1", "command": _PASS_CMD, "timeout": 5}]
        return patch.object(_mod, "_tool_definitions", fake_defs)

    def test_json_structure(self):
        with self._passing_patch(), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=False, as_json=True)
            data = json.loads(mock_out.getvalue())
        self.assertIn("gate_passed", data)
        self.assertIn("results", data)
        self.assertIn("timestamp", data)
        self.assertIn("tools_run", data)
        self.assertIn("tools_passed", data)
        self.assertIn("tools_failed", data)

    def test_gate_passed_true_on_all_pass(self):
        with self._passing_patch(), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=False, as_json=True)
            data = json.loads(mock_out.getvalue())
        self.assertTrue(data["gate_passed"])

    def test_gate_passed_false_on_fail(self):
        def fake_defs():
            return [{"name": "g1", "command": _FAIL_CMD, "timeout": 5}]
        with patch.object(_mod, "_tool_definitions", fake_defs), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=False, as_json=True)
            data = json.loads(mock_out.getvalue())
        self.assertFalse(data["gate_passed"])

    def test_tools_run_count(self):
        def fake_defs():
            return [
                {"name": "g1", "command": _PASS_CMD, "timeout": 5},
                {"name": "g2", "command": _PASS_CMD, "timeout": 5},
            ]
        with patch.object(_mod, "_tool_definitions", fake_defs), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=False, as_json=True)
            data = json.loads(mock_out.getvalue())
        self.assertEqual(data["tools_run"], 2)
        self.assertEqual(data["tools_passed"], 2)
        self.assertEqual(data["tools_failed"], 0)

    def test_tools_failed_count(self):
        def fake_defs():
            return [
                {"name": "g1", "command": _PASS_CMD, "timeout": 5},
                {"name": "g2", "command": _FAIL_CMD, "timeout": 5},
            ]
        with patch.object(_mod, "_tool_definitions", fake_defs), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=False, as_json=True)
            data = json.loads(mock_out.getvalue())
        self.assertEqual(data["tools_failed"], 1)


# ---------------------------------------------------------------------------
# Text output
# ---------------------------------------------------------------------------

class TestTextOutput(unittest.TestCase):

    def test_pass_message_on_success(self):
        def fake_defs():
            return [{"name": "my-tool", "command": _PASS_CMD, "timeout": 5}]
        with patch.object(_mod, "_tool_definitions", fake_defs), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=False, as_json=False)
            output = mock_out.getvalue()
        self.assertIn("PASS", output)
        self.assertIn("my-tool", output)
        self.assertIn("GATE PASSED", output)

    def test_fail_message_on_failure(self):
        def fake_defs():
            return [{"name": "bad-tool", "command": _FAIL_CMD, "timeout": 5}]
        with patch.object(_mod, "_tool_definitions", fake_defs), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=False, as_json=False)
            output = mock_out.getvalue()
        self.assertIn("FAIL", output)
        self.assertIn("GATE FAILED", output)

    def test_quiet_suppresses_output(self):
        def fake_defs():
            return [{"name": "g1", "command": _PASS_CMD, "timeout": 5}]
        with patch.object(_mod, "_tool_definitions", fake_defs), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_gate(quiet=True)
            output = mock_out.getvalue()
        self.assertEqual(output, "")


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------

class TestTimeout(unittest.TestCase):

    def test_timeout_marked_as_failed(self):
        # Use a long sleep that will timeout with timeout=1
        def fake_defs():
            return [{"name": "slow", "command": "ping -n 5 127.0.0.1 > NUL", "timeout": 1}]
        with patch.object(_mod, "_tool_definitions", fake_defs):
            code = run_gate(quiet=True)
        self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_int(self):
        def fake_defs():
            return [{"name": "g", "command": _PASS_CMD, "timeout": 5}]
        with patch.object(_mod, "_tool_definitions", fake_defs):
            rc = _mod.main(["--quiet"])
        self.assertIsInstance(rc, int)

    def test_main_skip_flag(self):
        """--skip removes a tool that would fail."""
        def fake_defs():
            return [
                {"name": "ok",   "command": _PASS_CMD, "timeout": 5},
                {"name": "fail", "command": _FAIL_CMD, "timeout": 5},
            ]
        with patch.object(_mod, "_tool_definitions", fake_defs):
            rc = _mod.main(["--quiet", "--skip", "fail"])
        self.assertEqual(rc, 0)

    def test_main_json_flag(self):
        def fake_defs():
            return [{"name": "g", "command": _PASS_CMD, "timeout": 5}]
        with patch.object(_mod, "_tool_definitions", fake_defs), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            _mod.main(["--json"])
            data = json.loads(mock_out.getvalue())
        self.assertIn("gate_passed", data)


if __name__ == "__main__":
    unittest.main()
