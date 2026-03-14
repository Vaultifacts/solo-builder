"""
tests/test_dag_transitions.py
Unit tests for core/dag_transitions.py — roll-up, deps_met, verify_rollup,
find_stalled, record_history.
"""

import pytest

from core.dag_transitions import (
    deps_met,
    find_stalled,
    record_history,
    roll_up,
    update_branch_status,
    update_task_status,
    verify_rollup,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dag(task_status="Pending", branch_status="Pending", subtask_statuses=None):
    """Build a minimal single-task, single-branch DAG."""
    if subtask_statuses is None:
        subtask_statuses = {"ST1": "Pending"}
    sts = {name: {"status": s, "last_update": 0} for name, s in subtask_statuses.items()}
    return {
        "T1": {
            "status": task_status,
            "depends_on": [],
            "branches": {
                "B1": {
                    "status": branch_status,
                    "subtasks": sts,
                },
            },
        },
    }


# ── record_history ────────────────────────────────────────────────────────────

class TestRecordHistory:
    def test_appends_entry(self):
        st = {}
        record_history(st, "Running", 5)
        assert st["history"] == [{"status": "Running", "step": 5}]

    def test_appends_multiple(self):
        st = {"history": [{"status": "Pending", "step": 0}]}
        record_history(st, "Running", 3)
        record_history(st, "Verified", 7)
        assert len(st["history"]) == 3
        assert st["history"][-1] == {"status": "Verified", "step": 7}


# ── update_branch_status ─────────────────────────────────────────────────────

class TestUpdateBranchStatus:
    def test_promotes_when_all_verified(self):
        dag = _dag(subtask_statuses={"ST1": "Verified", "ST2": "Verified"})
        update_branch_status(dag, "T1", "B1")
        assert dag["T1"]["branches"]["B1"]["status"] == "Verified"

    def test_no_promote_when_mixed(self):
        dag = _dag(subtask_statuses={"ST1": "Verified", "ST2": "Running"})
        update_branch_status(dag, "T1", "B1")
        assert dag["T1"]["branches"]["B1"]["status"] == "Pending"


# ── update_task_status ────────────────────────────────────────────────────────

class TestUpdateTaskStatus:
    def test_promotes_task_when_all_branches_verified(self):
        dag = _dag(branch_status="Verified")
        update_task_status(dag, "T1")
        assert dag["T1"]["status"] == "Verified"

    def test_promotes_to_running_when_any_branch_running(self):
        dag = _dag(branch_status="Running")
        update_task_status(dag, "T1")
        assert dag["T1"]["status"] == "Running"

    def test_no_change_when_pending(self):
        dag = _dag(branch_status="Pending")
        update_task_status(dag, "T1")
        assert dag["T1"]["status"] == "Pending"


# ── roll_up ───────────────────────────────────────────────────────────────────

class TestRollUp:
    def test_full_rollup(self):
        dag = _dag(subtask_statuses={"ST1": "Verified", "ST2": "Verified"})
        roll_up(dag, "T1", "B1")
        assert dag["T1"]["branches"]["B1"]["status"] == "Verified"
        assert dag["T1"]["status"] == "Verified"


# ── deps_met ──────────────────────────────────────────────────────────────────

class TestDepsMet:
    def test_no_deps(self):
        dag = _dag()
        assert deps_met(dag, "T1") is True

    def test_met_when_dep_verified(self):
        dag = _dag()
        dag["T2"] = {"status": "Pending", "depends_on": ["T1"], "branches": {}}
        dag["T1"]["status"] = "Verified"
        assert deps_met(dag, "T2") is True

    def test_not_met_when_dep_pending(self):
        dag = _dag()
        dag["T2"] = {"status": "Pending", "depends_on": ["T1"], "branches": {}}
        assert deps_met(dag, "T2") is False

    def test_missing_dep_task(self):
        dag = {"T1": {"status": "Pending", "depends_on": ["MISSING"], "branches": {}}}
        assert deps_met(dag, "T1") is False


# ── verify_rollup ─────────────────────────────────────────────────────────────

class TestVerifyRollup:
    def test_promotes_branch_to_verified(self):
        dag = _dag(subtask_statuses={"ST1": "Verified"})
        fixes = verify_rollup(dag)
        assert dag["T1"]["branches"]["B1"]["status"] == "Verified"
        assert any("Verified" in f for f in fixes)

    def test_promotes_branch_to_running(self):
        dag = _dag(subtask_statuses={"ST1": "Running", "ST2": "Pending"})
        fixes = verify_rollup(dag)
        assert dag["T1"]["branches"]["B1"]["status"] == "Running"
        assert any("Running" in f for f in fixes)

    def test_promotes_task_to_verified(self):
        dag = _dag(subtask_statuses={"ST1": "Verified"})
        verify_rollup(dag)
        assert dag["T1"]["status"] == "Verified"

    def test_no_fixes_when_consistent(self):
        dag = _dag(
            task_status="Verified",
            branch_status="Verified",
            subtask_statuses={"ST1": "Verified"},
        )
        fixes = verify_rollup(dag)
        assert fixes == []

    def test_does_not_demote(self):
        """verify_rollup should not demote a branch that's already Verified."""
        dag = _dag(branch_status="Verified", subtask_statuses={"ST1": "Running"})
        fixes = verify_rollup(dag)
        # Branch stays Verified (no demotion logic in verify_rollup)
        assert dag["T1"]["branches"]["B1"]["status"] == "Verified"


# ── find_stalled ──────────────────────────────────────────────────────────────

class TestFindStalled:
    def test_detects_stalled(self):
        dag = _dag(subtask_statuses={"ST1": "Running"})
        dag["T1"]["branches"]["B1"]["subtasks"]["ST1"]["last_update"] = 0
        result = find_stalled(dag, step=10, stall_threshold=5)
        assert len(result) == 1
        assert result[0] == ("T1", "B1", "ST1", 10)

    def test_not_stalled_within_threshold(self):
        dag = _dag(subtask_statuses={"ST1": "Running"})
        dag["T1"]["branches"]["B1"]["subtasks"]["ST1"]["last_update"] = 8
        result = find_stalled(dag, step=10, stall_threshold=5)
        assert result == []

    def test_ignores_review_status(self):
        dag = _dag(subtask_statuses={"ST1": "Review"})
        dag["T1"]["branches"]["B1"]["subtasks"]["ST1"]["last_update"] = 0
        result = find_stalled(dag, step=100, stall_threshold=5)
        assert result == []

    def test_ignores_verified(self):
        dag = _dag(subtask_statuses={"ST1": "Verified"})
        result = find_stalled(dag, step=100, stall_threshold=1)
        assert result == []
