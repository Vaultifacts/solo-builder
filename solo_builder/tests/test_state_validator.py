"""Tests for tools/state_validator.py (TASK-349, PW-020 to PW-025)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "state_validator", _TOOLS_DIR / "state_validator.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["state_validator"] = _mod
_spec.loader.exec_module(_mod)

validate         = _mod.validate
ValidationReport = _mod.ValidationReport
_detect_cycle    = _mod._detect_cycle
run              = _mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(dag=None, step=1):
    return {"dag": dag if dag is not None else {}, "step": step}


def _make_task(branches=None, depends_on=None):
    return {
        "status":     "Running",
        "depends_on": depends_on if depends_on is not None else [],
        "branches":   branches if branches is not None else {},
    }


def _make_branch(subtasks=None):
    return {"status": "Running", "subtasks": subtasks if subtasks is not None else {}}


def _make_subtask(status="Pending"):
    return {"status": status, "shadow": "Pending", "last_update": 0, "output": "", "description": ""}


# ---------------------------------------------------------------------------
# _detect_cycle
# ---------------------------------------------------------------------------

class TestDetectCycle(unittest.TestCase):

    def test_empty_graph_no_cycle(self):
        self.assertEqual(_detect_cycle({}), [])

    def test_linear_no_cycle(self):
        g = {"A": ["B"], "B": ["C"], "C": []}
        self.assertEqual(_detect_cycle(g), [])

    def test_self_loop_detected(self):
        g = {"A": ["A"]}
        result = _detect_cycle(g)
        self.assertIn("A", result)

    def test_two_node_cycle(self):
        g = {"A": ["B"], "B": ["A"]}
        result = _detect_cycle(g)
        self.assertTrue(len(result) > 0)

    def test_three_node_cycle(self):
        g = {"A": ["B"], "B": ["C"], "C": ["A"]}
        result = _detect_cycle(g)
        self.assertTrue(len(result) > 0)

    def test_disconnected_cycle_only_cycle_nodes_returned(self):
        g = {"X": [], "Y": [], "A": ["B"], "B": ["A"]}
        result = _detect_cycle(g)
        self.assertIn("A", result)
        self.assertIn("B", result)
        self.assertNotIn("X", result)
        self.assertNotIn("Y", result)


# ---------------------------------------------------------------------------
# ValidationReport
# ---------------------------------------------------------------------------

class TestValidationReport(unittest.TestCase):

    def test_empty_is_valid(self):
        r = ValidationReport()
        self.assertTrue(r.is_valid)

    def test_error_makes_invalid(self):
        r = ValidationReport(errors=["something wrong"])
        self.assertFalse(r.is_valid)

    def test_warnings_alone_stay_valid(self):
        r = ValidationReport(warnings=["heads up"])
        self.assertTrue(r.is_valid)

    def test_to_dict_keys(self):
        r = ValidationReport(errors=["e"], warnings=["w"])
        d = r.to_dict()
        for k in ("is_valid", "errors", "warnings"):
            self.assertIn(k, d)
        self.assertFalse(d["is_valid"])


# ---------------------------------------------------------------------------
# validate() — schema
# ---------------------------------------------------------------------------

class TestValidateSchema(unittest.TestCase):

    def test_valid_minimal_state(self):
        state = _make_state()
        report = validate(state=state)
        self.assertTrue(report.is_valid)

    def test_missing_dag_key(self):
        report = validate(state={"step": 1})
        self.assertFalse(report.is_valid)
        self.assertTrue(any("dag" in e for e in report.errors))

    def test_missing_step_key(self):
        report = validate(state={"dag": {}})
        self.assertFalse(report.is_valid)
        self.assertTrue(any("step" in e for e in report.errors))

    def test_step_wrong_type(self):
        report = validate(state={"dag": {}, "step": "not_int"})
        self.assertFalse(report.is_valid)
        self.assertTrue(any("step" in e for e in report.errors))

    def test_step_bool_rejected(self):
        report = validate(state={"dag": {}, "step": True})
        self.assertFalse(report.is_valid)

    def test_negative_step_rejected(self):
        report = validate(state={"dag": {}, "step": -1})
        self.assertFalse(report.is_valid)

    def test_dag_not_dict(self):
        report = validate(state={"dag": [1, 2], "step": 0})
        self.assertFalse(report.is_valid)

    def test_root_not_dict(self):
        report = validate(state=[1, 2])
        self.assertFalse(report.is_valid)

    def test_task_missing_branches(self):
        state = _make_state(dag={"T1": {"status": "Running", "depends_on": []}})
        report = validate(state=state)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("branches" in e for e in report.errors))

    def test_branches_not_dict(self):
        state = _make_state(dag={"T1": {"status": "Running", "depends_on": [], "branches": "bad"}})
        report = validate(state=state)
        self.assertFalse(report.is_valid)

    def test_branch_missing_subtasks(self):
        state = _make_state(dag={"T1": _make_task(branches={"Br1": {"status": "Running"}})})
        report = validate(state=state)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("subtasks" in e for e in report.errors))

    def test_subtasks_not_dict(self):
        state = _make_state(dag={"T1": _make_task(branches={"Br1": _make_branch(subtasks="bad")})})
        report = validate(state=state)
        self.assertFalse(report.is_valid)


# ---------------------------------------------------------------------------
# validate() — depends_on
# ---------------------------------------------------------------------------

class TestValidateDependencies(unittest.TestCase):

    def test_valid_depends_on(self):
        state = _make_state(dag={
            "T1": _make_task(depends_on=[]),
            "T2": _make_task(depends_on=["T1"]),
        })
        report = validate(state=state)
        self.assertTrue(report.is_valid)

    def test_unknown_dependency(self):
        state = _make_state(dag={"T1": _make_task(depends_on=["T_UNKNOWN"])})
        report = validate(state=state)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("T_UNKNOWN" in e for e in report.errors))

    def test_depends_on_not_list(self):
        state = _make_state(dag={"T1": _make_task(depends_on="T2")})
        report = validate(state=state)
        self.assertFalse(report.is_valid)

    def test_cycle_two_tasks(self):
        state = _make_state(dag={
            "T1": _make_task(depends_on=["T2"]),
            "T2": _make_task(depends_on=["T1"]),
        })
        report = validate(state=state)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("cycle" in e.lower() for e in report.errors))

    def test_no_cycle_chain(self):
        state = _make_state(dag={
            "T1": _make_task(depends_on=[]),
            "T2": _make_task(depends_on=["T1"]),
            "T3": _make_task(depends_on=["T2"]),
        })
        self.assertTrue(validate(state=state).is_valid)

    def test_self_loop_cycle(self):
        state = _make_state(dag={"T1": _make_task(depends_on=["T1"])})
        # T1 depends on itself — unknown dep (T1 is in task_ids but creates a self-loop)
        report = validate(state=state)
        self.assertFalse(report.is_valid)


# ---------------------------------------------------------------------------
# validate() — subtask statuses
# ---------------------------------------------------------------------------

class TestValidateSubtaskStatuses(unittest.TestCase):

    def test_valid_statuses_produce_no_warnings(self):
        subtasks = {
            "S1": _make_subtask("Pending"),
            "S2": _make_subtask("Running"),
            "S3": _make_subtask("Verified"),
        }
        state = _make_state(dag={"T1": _make_task(branches={"Br1": _make_branch(subtasks)})})
        report = validate(state=state)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.warnings, [])

    def test_unknown_status_produces_warning(self):
        subtasks = {"S1": _make_subtask("Bogus")}
        state = _make_state(dag={"T1": _make_task(branches={"Br1": _make_branch(subtasks)})})
        report = validate(state=state)
        self.assertTrue(report.is_valid)  # warning, not error
        self.assertTrue(any("Bogus" in w for w in report.warnings))

    def test_missing_status_produces_warning(self):
        subtasks = {"S1": {"shadow": "Pending", "last_update": 0, "output": ""}}
        state = _make_state(dag={"T1": _make_task(branches={"Br1": _make_branch(subtasks)})})
        report = validate(state=state)
        self.assertTrue(report.is_valid)
        self.assertTrue(len(report.warnings) > 0)


# ---------------------------------------------------------------------------
# validate() — file-based loading
# ---------------------------------------------------------------------------

class TestValidateFromFile(unittest.TestCase):

    def test_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps(_make_state()), encoding="utf-8")
            report = validate(state_path=p)
        self.assertTrue(report.is_valid)

    def test_missing_file(self):
        report = validate(state_path="/nonexistent/state.json")
        self.assertFalse(report.is_valid)
        self.assertTrue(any("not found" in e.lower() for e in report.errors))

    def test_invalid_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text("not json", encoding="utf-8")
            report = validate(state_path=p)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("json" in e.lower() for e in report.errors))


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_on_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps(_make_state()), encoding="utf-8")
            code = run(quiet=True, state_path=p)
        self.assertEqual(code, 0)

    def test_returns_1_on_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps({"step": 1}), encoding="utf-8")  # missing dag
            code = run(quiet=True, state_path=p)
        self.assertEqual(code, 1)

    def test_json_output_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps(_make_state()), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=True, state_path=p)
                data = json.loads(mock_out.getvalue())
        for k in ("is_valid", "errors", "warnings"):
            self.assertIn(k, data)

    def test_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps(_make_state()), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True, state_path=p)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_text_output_mentions_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps(_make_state()), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=False, state_path=p)
                output = mock_out.getvalue()
        self.assertIn("valid", output.lower())

    def test_text_output_shows_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps({"step": 1}), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=False, state_path=p)
                output = mock_out.getvalue()
        self.assertIn("ERR", output)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_valid_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps(_make_state()), encoding="utf-8")
            rc = _mod.main(["--quiet", "--state", str(p)])
        self.assertEqual(rc, 0)

    def test_main_invalid_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps({"step": 0}), encoding="utf-8")
            rc = _mod.main(["--quiet", "--state", str(p)])
        self.assertEqual(rc, 1)

    def test_main_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps(_make_state()), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--json", "--state", str(p)])
                data = json.loads(mock_out.getvalue())
        self.assertIn("is_valid", data)


if __name__ == "__main__":
    unittest.main()
