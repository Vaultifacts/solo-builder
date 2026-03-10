"""Tests for tools/pre_release_check.py (TASK-340)."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Load the module from the tools/ directory (not on sys.path by default)
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "pre_release_check", _TOOLS_DIR / "pre_release_check.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GateResult       = _mod.GateResult
_run_gate        = _mod._run_gate
_builtin_gates   = _mod._builtin_gates
_load_verify_gates = _mod._load_verify_gates
run_checks       = _mod.run_checks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _passing_gate(name="gate-ok"):
    return GateResult(name=name, command="true", required=True,
                      passed=True, output="", duration_s=0.1)


def _failing_gate(name="gate-fail"):
    return GateResult(name=name, command="false", required=True,
                      passed=False, output="error text", duration_s=0.1)


# ---------------------------------------------------------------------------
# _run_gate
# ---------------------------------------------------------------------------

class TestRunGate(unittest.TestCase):

    def test_passing_command(self):
        passed, output, dur = _run_gate("t", "exit 0", timeout=5)
        self.assertTrue(passed)
        self.assertGreaterEqual(dur, 0)

    def test_failing_command(self):
        passed, output, dur = _run_gate("t", "exit 1", timeout=5)
        self.assertFalse(passed)

    def test_output_captured(self):
        passed, output, dur = _run_gate("t", 'echo hello', timeout=5)
        self.assertTrue(passed)
        self.assertIn("hello", output)

    def test_timeout_returns_false(self):
        passed, output, dur = _run_gate("t", "ping -n 5 127.0.0.1 > NUL", timeout=1)
        self.assertFalse(passed)
        self.assertIn("TIMEOUT", output)

    def test_output_truncated_at_500(self):
        long_cmd = f'python -c "print(\'x\' * 2000)"'
        passed, output, dur = _run_gate("t", long_cmd, timeout=10)
        self.assertLessEqual(len(output), 500)


# ---------------------------------------------------------------------------
# _builtin_gates
# ---------------------------------------------------------------------------

class TestBuiltinGates(unittest.TestCase):

    def test_returns_list(self):
        gates = _builtin_gates()
        self.assertIsInstance(gates, list)

    def test_python_tests_present(self):
        names = [g["name"] for g in _builtin_gates()]
        self.assertIn("python-tests", names)

    def test_python_tests_is_required(self):
        gates = {g["name"]: g for g in _builtin_gates()}
        self.assertTrue(gates["python-tests"]["required"])

    def test_git_clean_present(self):
        names = [g["name"] for g in _builtin_gates()]
        self.assertIn("git-clean", names)

    def test_git_clean_not_required(self):
        gates = {g["name"]: g for g in _builtin_gates()}
        self.assertFalse(gates["git-clean"]["required"])

    def test_context_window_present(self):
        names = [g["name"] for g in _builtin_gates()]
        self.assertIn("context-window", names)

    def test_slo_check_present(self):
        names = [g["name"] for g in _builtin_gates()]
        self.assertIn("slo-check", names)

    def test_prompt_regression_present(self):
        names = [g["name"] for g in _builtin_gates()]
        self.assertIn("prompt-regression", names)

    def test_prompt_regression_required(self):
        gates = {g["name"]: g for g in _builtin_gates()}
        self.assertTrue(gates["prompt-regression"]["required"])

    def test_prompt_regression_command_contains_script(self):
        gates = {g["name"]: g for g in _builtin_gates()}
        self.assertIn("prompt_regression_check.py", gates["prompt-regression"]["command"])

    def test_each_gate_has_command(self):
        for g in _builtin_gates():
            self.assertIn("command", g)
            self.assertTrue(g["command"])


# ---------------------------------------------------------------------------
# _load_verify_gates
# ---------------------------------------------------------------------------

class TestLoadVerifyGates(unittest.TestCase):

    def test_returns_list_on_missing_file(self):
        with patch.object(_mod, "VERIFY_JSON", Path("/nonexistent/VERIFY.json")):
            result = _load_verify_gates()
        self.assertIsInstance(result, list)

    def test_returns_commands_from_valid_json(self, tmp_path=None):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "VERIFY.json"
            p.write_text(json.dumps({"commands": [
                {"name": "custom-gate", "command": "echo ok", "required": False}
            ]}), encoding="utf-8")
            with patch.object(_mod, "VERIFY_JSON", p):
                result = _load_verify_gates()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "custom-gate")

    def test_returns_empty_on_invalid_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "VERIFY.json"
            p.write_text("not json", encoding="utf-8")
            with patch.object(_mod, "VERIFY_JSON", p):
                result = _load_verify_gates()
        self.assertEqual(result, [])

    def test_returns_empty_when_no_commands_key(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "VERIFY.json"
            p.write_text(json.dumps({"other": []}), encoding="utf-8")
            with patch.object(_mod, "VERIFY_JSON", p):
                result = _load_verify_gates()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# VERIFY.json prompt-regression entry
# ---------------------------------------------------------------------------

class TestVerifyJsonPromptRegression(unittest.TestCase):
    """VERIFY.json must declare prompt-regression as a required gate."""

    def _verify_gates(self):
        return _load_verify_gates()

    def test_prompt_regression_in_verify_json(self):
        names = [g["name"] for g in self._verify_gates()]
        self.assertIn("prompt-regression", names)

    def test_prompt_regression_required_in_verify_json(self):
        gates = {g["name"]: g for g in self._verify_gates()}
        self.assertTrue(gates["prompt-regression"]["required"])

    def test_prompt_regression_command_in_verify_json(self):
        gates = {g["name"]: g for g in self._verify_gates()}
        self.assertIn("prompt_regression_check.py", gates["prompt-regression"]["command"])


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------

class TestRunChecks(unittest.TestCase):

    def _patch_gates(self, gate_dicts):
        """Patch both builtin + verify gate sources to return given list."""
        def _fake_builtin():
            return gate_dicts

        def _fake_verify():
            return []

        return (
            patch.object(_mod, "_builtin_gates", _fake_builtin),
            patch.object(_mod, "_load_verify_gates", _fake_verify),
        )

    def test_returns_0_when_all_required_pass(self):
        patches = self._patch_gates([
            {"name": "g1", "command": "exit 0", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            code = run_checks(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_1_when_required_fails(self):
        patches = self._patch_gates([
            {"name": "g1", "command": "exit 1", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            code = run_checks(quiet=True)
        self.assertEqual(code, 1)

    def test_optional_failure_does_not_affect_exit_code(self):
        patches = self._patch_gates([
            {"name": "req", "command": "exit 0", "required": True,  "timeout_sec": 5},
            {"name": "opt", "command": "exit 1", "required": False, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            code = run_checks(quiet=True)
        self.assertEqual(code, 0)

    def test_json_output_structure(self):
        import io
        patches = self._patch_gates([
            {"name": "g1", "command": "exit 0", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                code = run_checks(quiet=False, as_json=True)
                output = mock_out.getvalue()
        data = json.loads(output)
        self.assertIn("release_ready", data)
        self.assertIn("gates", data)
        self.assertIn("timestamp", data)

    def test_json_release_ready_true_on_pass(self):
        import io
        patches = self._patch_gates([
            {"name": "g1", "command": "exit 0", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=True)
                data = json.loads(mock_out.getvalue())
        self.assertTrue(data["release_ready"])

    def test_json_release_ready_false_on_fail(self):
        import io
        patches = self._patch_gates([
            {"name": "g1", "command": "exit 1", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=True)
                data = json.loads(mock_out.getvalue())
        self.assertFalse(data["release_ready"])

    def test_text_output_contains_pass(self):
        import io
        patches = self._patch_gates([
            {"name": "my-gate", "command": "exit 0", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=False)
                output = mock_out.getvalue()
        self.assertIn("PASS", output)
        self.assertIn("my-gate", output)

    def test_text_output_contains_fail(self):
        import io
        patches = self._patch_gates([
            {"name": "bad-gate", "command": "exit 1", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=False)
                output = mock_out.getvalue()
        self.assertIn("FAIL", output)

    def test_quiet_suppresses_output(self):
        import io
        patches = self._patch_gates([
            {"name": "g1", "command": "exit 0", "required": True, "timeout_sec": 5},
        ])
        with patches[0], patches[1]:
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=True)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_verify_gates_merged_with_builtins(self):
        """Gates from VERIFY.json are appended to builtin gates."""
        import io

        def _fake_builtin():
            return [{"name": "builtin-g", "command": "exit 0", "required": True, "timeout_sec": 5}]

        def _fake_verify():
            return [{"name": "verify-g", "command": "exit 0", "required": False, "timeout_sec": 5}]

        with patch.object(_mod, "_builtin_gates", _fake_builtin), \
             patch.object(_mod, "_load_verify_gates", _fake_verify), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_checks(quiet=False, as_json=True)
            data = json.loads(mock_out.getvalue())

        gate_names = [g["name"] for g in data["gates"]]
        self.assertIn("builtin-g", gate_names)
        self.assertIn("verify-g", gate_names)

    def test_unittest_discover_excluded_from_verify_gates(self):
        """unittest-discover gate in VERIFY.json should be skipped."""
        import io

        def _fake_builtin():
            return []

        def _fake_verify():
            return [
                {"name": "unittest-discover", "command": "exit 0", "required": True, "timeout_sec": 5},
                {"name": "other-gate",        "command": "exit 0", "required": False, "timeout_sec": 5},
            ]

        with patch.object(_mod, "_builtin_gates", _fake_builtin), \
             patch.object(_mod, "_load_verify_gates", _fake_verify), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            run_checks(quiet=False, as_json=True)
            data = json.loads(mock_out.getvalue())

        gate_names = [g["name"] for g in data["gates"]]
        self.assertNotIn("unittest-discover", gate_names)
        self.assertIn("other-gate", gate_names)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_int(self):
        with patch.object(_mod, "_builtin_gates", lambda: [
            {"name": "g", "command": "exit 0", "required": True, "timeout_sec": 5}
        ]), patch.object(_mod, "_load_verify_gates", lambda: []):
            rc = _mod.main(["--quiet"])
        self.assertIsInstance(rc, int)

    def test_main_json_flag(self):
        import io
        with patch.object(_mod, "_builtin_gates", lambda: [
            {"name": "g", "command": "exit 0", "required": True, "timeout_sec": 5}
        ]), patch.object(_mod, "_load_verify_gates", lambda: []), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            _mod.main(["--json"])
            out = mock_out.getvalue()
        data = json.loads(out)
        self.assertIn("release_ready", data)


if __name__ == "__main__":
    unittest.main()
