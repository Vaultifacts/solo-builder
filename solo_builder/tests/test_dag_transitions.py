"""Unit tests for utils/dag_transitions module."""
import sys
import unittest
from pathlib import Path

# Ensure solo_builder/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.dag_transitions import (
    is_valid_transition,
    record_history,
    update_subtask_status,
    update_branch_status,
    update_task_status,
    roll_up,
    deps_met,
    verify_rollup,
    find_stalled,
)


# ── Test Helpers ─────────────────────────────────────────────────────────────

def _st(status="Pending", last_update=0, shadow="Pending", tools=""):
    """Create a subtask dict."""
    return {"status": status, "last_update": last_update, "shadow": shadow, "tools": tools}


def _branch(subtasks, status="Pending"):
    """Create a branch dict."""
    return {"status": status, "subtasks": subtasks}


def _task(branches, status="Pending", depends_on=None):
    """Create a task dict."""
    d = {"status": status, "branches": branches}
    if depends_on:
        d["depends_on"] = depends_on
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# Status Transition Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsValidTransition(unittest.TestCase):
    """Test is_valid_transition state machine."""

    def test_pending_to_running_valid(self):
        """Pending → Running is allowed."""
        self.assertTrue(is_valid_transition("Pending", "Running"))

    def test_pending_to_verified_invalid(self):
        """Pending → Verified skips Running (invalid)."""
        self.assertFalse(is_valid_transition("Pending", "Verified"))

    def test_pending_to_review_invalid(self):
        """Pending → Review is invalid (must go through Running)."""
        self.assertFalse(is_valid_transition("Pending", "Review"))

    def test_running_to_verified_valid(self):
        """Running → Verified is allowed."""
        self.assertTrue(is_valid_transition("Running", "Verified"))

    def test_running_to_review_valid(self):
        """Running → Review is allowed."""
        self.assertTrue(is_valid_transition("Running", "Review"))

    def test_running_to_pending_valid_heal(self):
        """Running → Pending is allowed (healing mechanism)."""
        self.assertTrue(is_valid_transition("Running", "Pending"))

    def test_review_to_verified_valid(self):
        """Review → Verified is allowed (approval)."""
        self.assertTrue(is_valid_transition("Review", "Verified"))

    def test_review_to_pending_valid_reject(self):
        """Review → Pending is allowed (rejection)."""
        self.assertTrue(is_valid_transition("Review", "Pending"))

    def test_review_to_running_invalid(self):
        """Review → Running is invalid (must go through Pending or Verified)."""
        self.assertFalse(is_valid_transition("Review", "Running"))

    def test_verified_terminal(self):
        """Verified → anything is invalid (terminal)."""
        self.assertFalse(is_valid_transition("Verified", "Pending"))
        self.assertFalse(is_valid_transition("Verified", "Running"))
        self.assertFalse(is_valid_transition("Verified", "Review"))
        self.assertFalse(is_valid_transition("Verified", "Verified"))

    def test_invalid_status(self):
        """Invalid status names return False."""
        self.assertFalse(is_valid_transition("Pending", "Unknown"))
        self.assertFalse(is_valid_transition("Unknown", "Verified"))


# ═══════════════════════════════════════════════════════════════════════════════
# History Recording
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistoryRecording(unittest.TestCase):
    """Test history tracking."""

    def test_record_history_creates_list(self):
        """record_history creates history list if missing."""
        st = {}
        record_history(st, "Running", 1)
        self.assertIn("history", st)
        self.assertEqual(len(st["history"]), 1)

    def test_record_history_appends(self):
        """record_history appends to existing history."""
        st = {"history": [{"status": "Pending", "step": 0}]}
        record_history(st, "Running", 1)
        self.assertEqual(len(st["history"]), 2)
        self.assertEqual(st["history"][1]["status"], "Running")
        self.assertEqual(st["history"][1]["step"], 1)

    def test_update_subtask_status_records_history(self):
        """update_subtask_status records transitions."""
        st = _st("Pending")
        result = update_subtask_status(st, "Running", 1)
        self.assertEqual(result, "Running")
        self.assertEqual(st["status"], "Running")
        self.assertEqual(len(st.get("history", [])), 1)
        self.assertEqual(st["history"][0]["status"], "Running")


# ═══════════════════════════════════════════════════════════════════════════════
# Subtask Status Update
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateSubtaskStatus(unittest.TestCase):
    """Test subtask status updates."""

    def test_valid_transition_updates(self):
        """Valid transition updates status and returns new status."""
        st = _st("Pending")
        result = update_subtask_status(st, "Running", 1)
        self.assertEqual(result, "Running")
        self.assertEqual(st["status"], "Running")

    def test_invalid_transition_returns_none(self):
        """Invalid transition returns None and doesn't update."""
        st = _st("Verified")
        result = update_subtask_status(st, "Running", 1)
        self.assertIsNone(result)
        self.assertEqual(st["status"], "Verified")

    def test_running_to_review(self):
        """Running → Review updates correctly."""
        st = _st("Running", last_update=5)
        result = update_subtask_status(st, "Review", 10)
        self.assertEqual(result, "Review")
        self.assertEqual(st["status"], "Review")

    def test_review_to_verified(self):
        """Review → Verified updates correctly."""
        st = _st("Review")
        result = update_subtask_status(st, "Verified", 20)
        self.assertEqual(result, "Verified")
        self.assertEqual(st["status"], "Verified")


# ═══════════════════════════════════════════════════════════════════════════════
# Branch Roll-up
# ═══════════════════════════════════════════════════════════════════════════════

class TestBranchRollup(unittest.TestCase):
    """Test branch status roll-up logic."""

    def test_all_subtasks_verified_promotes_branch(self):
        """All subtasks Verified → branch Verified."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Verified"),
                    "A2": _st("Verified"),
                }, status="Running")
            })
        }
        update_branch_status(dag, "Task 0", "A")
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Verified")

    def test_one_pending_no_promote(self):
        """One Pending subtask → branch stays Running."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Verified"),
                    "A2": _st("Pending"),
                }, status="Running")
            })
        }
        update_branch_status(dag, "Task 0", "A")
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Running")

    def test_one_running_no_promote(self):
        """One Running subtask → branch stays Running."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Verified"),
                    "A2": _st("Running"),
                }, status="Running")
            })
        }
        update_branch_status(dag, "Task 0", "A")
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Running")

    def test_review_subtask_no_promote(self):
        """Review subtask blocks branch promotion (critical fix)."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Verified"),
                    "A2": _st("Review"),
                }, status="Running")
            })
        }
        update_branch_status(dag, "Task 0", "A")
        # update_branch_status only promotes if ALL are Verified
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Running")


# ═══════════════════════════════════════════════════════════════════════════════
# Task Roll-up
# ═══════════════════════────────────────────────────────────────────────────────

class TestTaskRollup(unittest.TestCase):
    """Test task status roll-up logic."""

    def test_all_branches_verified_promotes_task(self):
        """All branches Verified → task Verified."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
                "B": _branch({"B1": _st("Verified")}, status="Verified"),
            }, status="Running")
        }
        update_task_status(dag, "Task 0")
        self.assertEqual(dag["Task 0"]["status"], "Verified")

    def test_one_branch_running_keeps_task_running(self):
        """One branch Running → task Running."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
                "B": _branch({"B1": _st("Running")}, status="Running"),
            }, status="Pending")
        }
        update_task_status(dag, "Task 0")
        self.assertEqual(dag["Task 0"]["status"], "Running")

    def test_one_branch_review_keeps_task_running(self):
        """One branch in Review → task Running (critical fix)."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
                "B": _branch({"B1": _st("Review")}, status="Running"),
            }, status="Pending")
        }
        update_task_status(dag, "Task 0")
        self.assertEqual(dag["Task 0"]["status"], "Running")

    def test_mixed_statuses_running(self):
        """Mixed branch statuses → task stays Running."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
                "B": _branch({"B1": _st("Running")}, status="Running"),
                "C": _branch({"C1": _st("Review")}, status="Running"),
            }, status="Pending")
        }
        update_task_status(dag, "Task 0")
        self.assertEqual(dag["Task 0"]["status"], "Running")


# ═══════════════════════════════════════════════════════════════════════════════
# Full Verify Rollup
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyRollup(unittest.TestCase):
    """Test full DAG consistency sweep."""

    def test_all_verified_stays_verified(self):
        """All-Verified DAG needs no fixes."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
            }, status="Verified")
        }
        fixes = verify_rollup(dag)
        self.assertEqual(fixes, [])
        self.assertEqual(dag["Task 0"]["status"], "Verified")

    def test_pending_branch_with_running_subtask_becomes_running(self):
        """Pending branch with Running subtask → Running."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Running")}, status="Pending"),
            }, status="Pending")
        }
        fixes = verify_rollup(dag)
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Running")
        self.assertGreater(len(fixes), 0)

    def test_review_subtask_fixes_stuck_branch(self):
        """Review subtask promotes Pending branch to Running (critical fix)."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Review")}, status="Pending"),
            }, status="Pending")
        }
        fixes = verify_rollup(dag)
        # Branch should be Running because it has a Review subtask
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Running")
        self.assertTrue(any("RUNNING" in str(f).upper() for f in fixes))

    def test_all_verified_branch_promotes_task(self):
        """All-Verified branch prompts task to Verified."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
            }, status="Running")
        }
        fixes = verify_rollup(dag)
        self.assertEqual(dag["Task 0"]["status"], "Verified")
        self.assertIn("Task 0", str(fixes))

    def test_mixed_branch_statuses_keeps_task_running(self):
        """One Running branch → task stays Running."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
                "B": _branch({"B1": _st("Running")}, status="Running"),
            }, status="Pending")
        }
        fixes = verify_rollup(dag)
        self.assertEqual(dag["Task 0"]["status"], "Running")

    def test_demote_verified_task_if_branch_running(self):
        """Task Verified but branch Running → demote task."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Running")}, status="Running"),
            }, status="Verified")
        }
        fixes = verify_rollup(dag)
        self.assertEqual(dag["Task 0"]["status"], "Running")
        self.assertGreater(len(fixes), 0)

    def test_demote_verified_branch_if_subtask_review(self):
        """Branch Verified but subtask Review → demote branch (critical fix)."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Review")}, status="Verified"),
            }, status="Verified")
        }
        fixes = verify_rollup(dag)
        # Branch should be demoted to Running (Review present)
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Running")
        self.assertGreater(len(fixes), 0)

    def test_multi_branch_multi_subtask_consistency(self):
        """Complex DAG with mixed statuses gets fixed."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Verified"),
                    "A2": _st("Verified"),
                }, status="Pending"),  # Should be Verified
                "B": _branch({
                    "B1": _st("Running"),
                }, status="Verified"),  # Should be Running
            }, status="Pending")  # Should be Running
        }
        fixes = verify_rollup(dag)
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Verified")
        self.assertEqual(dag["Task 0"]["branches"]["B"]["status"], "Running")
        self.assertEqual(dag["Task 0"]["status"], "Running")
        self.assertGreater(len(fixes), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# Dependency Eligibility
# ═══════════════════════════════════════════════════════════════════════════════

class TestDepsMetCheck(unittest.TestCase):
    """Test dependency verification."""

    def test_no_deps_always_met(self):
        """Task with no depends_on → deps_met returns True."""
        dag = {"Task 0": _task({}, depends_on=[])}
        self.assertTrue(deps_met(dag, "Task 0"))

    def test_single_verified_dep_met(self):
        """Single Verified dependency → deps_met returns True."""
        dag = {
            "Task 0": _task({}, status="Verified"),
            "Task 1": _task({}, depends_on=["Task 0"]),
        }
        self.assertTrue(deps_met(dag, "Task 1"))

    def test_single_pending_dep_not_met(self):
        """Single Pending dependency → deps_met returns False."""
        dag = {
            "Task 0": _task({}, status="Pending"),
            "Task 1": _task({}, depends_on=["Task 0"]),
        }
        self.assertFalse(deps_met(dag, "Task 1"))

    def test_single_running_dep_not_met(self):
        """Single Running dependency → deps_met returns False."""
        dag = {
            "Task 0": _task({}, status="Running"),
            "Task 1": _task({}, depends_on=["Task 0"]),
        }
        self.assertFalse(deps_met(dag, "Task 1"))

    def test_multiple_deps_all_verified(self):
        """All dependencies Verified → deps_met returns True."""
        dag = {
            "Task 0": _task({}, status="Verified"),
            "Task 1": _task({}, status="Verified"),
            "Task 2": _task({}, depends_on=["Task 0", "Task 1"]),
        }
        self.assertTrue(deps_met(dag, "Task 2"))

    def test_multiple_deps_one_not_verified(self):
        """One dependency not Verified → deps_met returns False."""
        dag = {
            "Task 0": _task({}, status="Verified"),
            "Task 1": _task({}, status="Running"),
            "Task 2": _task({}, depends_on=["Task 0", "Task 1"]),
        }
        self.assertFalse(deps_met(dag, "Task 2"))


# ═══════════════════════════════════════════════════════════════════════════════
# Stall Detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindStalled(unittest.TestCase):
    """Test stalled subtask detection."""

    def test_no_stalled_when_running_fresh(self):
        """Running subtask with age < threshold → not stalled."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Running", last_update=8)}, status="Running")
            })
        }
        stalled = find_stalled(dag, step=10, stall_threshold=5)
        self.assertEqual(stalled, [])

    def test_stalled_when_old(self):
        """Running subtask with age ≥ threshold → stalled."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Running", last_update=0)}, status="Running")
            })
        }
        stalled = find_stalled(dag, step=10, stall_threshold=5)
        self.assertEqual(len(stalled), 1)
        self.assertEqual(stalled[0], ("Task 0", "A", "A1", 10))

    def test_verified_not_stalled(self):
        """Verified subtask never stalled (even if very old)."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Verified", last_update=0)}, status="Verified")
            })
        }
        stalled = find_stalled(dag, step=100, stall_threshold=5)
        self.assertEqual(stalled, [])

    def test_review_not_stalled(self):
        """Review subtask not flagged as stalled (human-controlled)."""
        dag = {
            "Task 0": _task({
                "A": _branch({"A1": _st("Review", last_update=0)}, status="Running")
            })
        }
        stalled = find_stalled(dag, step=100, stall_threshold=5)
        self.assertEqual(stalled, [])

    def test_multiple_stalled(self):
        """Multiple Running/stalled subtasks all found."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Running", last_update=0),  # stalled
                    "A2": _st("Running", last_update=8),  # fresh
                }, status="Running"),
                "B": _branch({
                    "B1": _st("Running", last_update=2),  # stalled
                }, status="Running"),
            })
        }
        stalled = find_stalled(dag, step=10, stall_threshold=5)
        self.assertEqual(len(stalled), 2)
        # Check we got A1 and B1
        names = {(s[0], s[1], s[2]) for s in stalled}
        self.assertIn(("Task 0", "A", "A1"), names)
        self.assertIn(("Task 0", "B", "B1"), names)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple operations."""

    def test_roll_up_convenience_function(self):
        """roll_up updates both branch and task."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Verified"),
                    "A2": _st("Verified"),
                }, status="Running")
            }, status="Running")
        }
        roll_up(dag, "Task 0", "A")
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Verified")
        self.assertEqual(dag["Task 0"]["status"], "Verified")

    def test_complex_workflow_scenario(self):
        """Realistic scenario: multiple subtasks through full lifecycle."""
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Pending"),
                    "A2": _st("Pending"),
                }, status="Pending")
            }, status="Pending")
        }

        # Step 1: A1 starts
        st_a1 = dag["Task 0"]["branches"]["A"]["subtasks"]["A1"]
        update_subtask_status(st_a1, "Running", 1)
        # Update branch and task status
        dag["Task 0"]["branches"]["A"]["status"] = "Running"
        update_task_status(dag, "Task 0")
        self.assertEqual(dag["Task 0"]["status"], "Running")

        # Step 2: A1 goes to Review
        update_subtask_status(st_a1, "Review", 5)

        # Step 3: A2 starts
        st_a2 = dag["Task 0"]["branches"]["A"]["subtasks"]["A2"]
        update_subtask_status(st_a2, "Running", 5)

        # Verify rollup fixes branch status (Review/Running present)
        fixes = verify_rollup(dag)
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Running")

        # Step 4: A1 approved from Review
        update_subtask_status(st_a1, "Verified", 10)

        # Step 5: A2 completes
        update_subtask_status(st_a2, "Verified", 15)

        # Full rollup: all subtasks Verified → branch and task Verified
        fixes = verify_rollup(dag)
        self.assertEqual(dag["Task 0"]["branches"]["A"]["status"], "Verified")
        self.assertEqual(dag["Task 0"]["status"], "Verified")
        self.assertEqual(len(st_a1["history"]), 3)  # Pending→Running→Review→Verified


if __name__ == "__main__":
    unittest.main()
