#!/usr/bin/env python3
"""
tests/test_dag_invariants.py — DAG invariant validation helpers and tests.

Provides check_dag_invariants() which runs structural + semantic checks on the
DAG that can be called both in tests and as a post-phase runtime guard.

Run:
    python -m pytest tests/test_dag_invariants.py -v
"""

import sys
import unittest
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.helper_functions import validate_dag


# ── Invariant Validation Helpers ─────────────────────────────────────────────

def check_dag_invariants(dag: Dict) -> List[str]:
    """
    Run all DAG invariant checks. Returns a list of violation messages.
    Empty list = all invariants hold.

    Checks:
        1. Structural: validate_dag() — branches/subtasks keys, valid statuses
        2. Shadow consistency: shadow must be in {"Pending","Done"}
        3. Branch roll-up: if all subtasks Verified → branch must be Verified
        4. Task roll-up: if all branches Verified → task must be Verified
        5. Dependency ordering: depends_on references must exist in the DAG
        6. No orphan subtask: every subtask must have required keys
        7. Shadow/status alignment: shadow Done implies status should be Verified
    """
    violations: List[str] = []

    # 1. Structural validation
    violations.extend(validate_dag(dag))

    for task_name, task_data in dag.items():
        # 5. Dependency references exist
        for dep in task_data.get("depends_on", []):
            if dep not in dag:
                violations.append(
                    f"{task_name}: depends_on '{dep}' not found in DAG"
                )

        branches = task_data.get("branches", {})
        all_branches_verified = True

        for branch_name, branch_data in branches.items():
            subtasks = branch_data.get("subtasks", {})
            if not subtasks:
                continue

            all_st_verified = True
            for st_name, st_data in subtasks.items():
                status = st_data.get("status", "Pending")
                shadow = st_data.get("shadow", "Pending")

                # 6. Required keys check
                for key in ("status", "shadow", "last_update"):
                    if key not in st_data:
                        violations.append(
                            f"{task_name}/{branch_name}/{st_name}: missing '{key}'"
                        )

                if status != "Verified":
                    all_st_verified = False

                # 7. Shadow/status alignment warning (soft invariant)
                if shadow == "Done" and status not in ("Verified", "Review"):
                    violations.append(
                        f"{task_name}/{branch_name}/{st_name}: "
                        f"shadow=Done but status={status} (expected Verified or Review)"
                    )

            # 3. Branch roll-up check
            if all_st_verified and branch_data.get("status") != "Verified":
                violations.append(
                    f"{task_name}/{branch_name}: all subtasks Verified "
                    f"but branch status={branch_data.get('status')}"
                )

            if branch_data.get("status") != "Verified":
                all_branches_verified = False

        # 4. Task roll-up check
        if branches and all_branches_verified and task_data.get("status") != "Verified":
            violations.append(
                f"{task_name}: all branches Verified "
                f"but task status={task_data.get('status')}"
            )

    return violations


def check_post_phase_invariants(dag: Dict, phase: str) -> List[str]:
    """
    Lightweight post-phase check suitable for runtime injection.
    Returns violations; empty = OK. Phase name is for context in messages.
    """
    violations = []
    structural = validate_dag(dag)
    if structural:
        violations.extend(f"[{phase}] {w}" for w in structural)

    # Quick dependency existence check
    for task_name, task_data in dag.items():
        for dep in task_data.get("depends_on", []):
            if dep not in dag:
                violations.append(
                    f"[{phase}] {task_name}: depends_on '{dep}' missing from DAG"
                )
    return violations


# ── Helpers for tests ────────────────────────────────────────────────────────

def _st(status="Pending", shadow="Pending", last_update=0, **kw):
    d = {"status": status, "shadow": shadow, "last_update": last_update,
         "description": "", "output": ""}
    d.update(kw)
    return d


def _branch(subtasks, status="Pending"):
    return {"status": status, "subtasks": subtasks}


def _task(branches, status="Pending", depends_on=None):
    return {"status": status, "depends_on": depends_on or [], "branches": branches}


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckDagInvariantsValid(unittest.TestCase):
    """A well-formed DAG should pass all invariant checks."""

    def test_valid_dag_no_violations(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Done"),
                    "A2": _st(status="Verified", shadow="Done"),
                }, status="Verified"),
            }, status="Verified"),
        }
        violations = check_dag_invariants(dag)
        self.assertEqual(violations, [])

    def test_valid_pending_dag(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", shadow="Pending"),
                    "A2": _st(status="Pending", shadow="Pending"),
                }, status="Pending"),
            }, status="Pending"),
        }
        violations = check_dag_invariants(dag)
        self.assertEqual(violations, [])

    def test_valid_mixed_dag(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Done"),
                    "A2": _st(status="Running", shadow="Pending", last_update=5),
                }, status="Running"),
            }, status="Running"),
        }
        violations = check_dag_invariants(dag)
        self.assertEqual(violations, [])


class TestCheckDagInvariantsViolations(unittest.TestCase):
    """Detect various invariant violations."""

    def test_missing_branches_key(self):
        dag = {"Task 0": {"status": "Pending", "depends_on": []}}
        violations = check_dag_invariants(dag)
        self.assertTrue(any("missing 'branches'" in v for v in violations))

    def test_invalid_status(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="INVALID"),
                })
            })
        }
        violations = check_dag_invariants(dag)
        self.assertTrue(any("invalid status" in v for v in violations))

    def test_invalid_shadow(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", shadow="WRONG"),
                })
            })
        }
        violations = check_dag_invariants(dag)
        self.assertTrue(any("invalid shadow" in v for v in violations))

    def test_broken_dependency_reference(self):
        dag = {
            "Task 1": _task(
                {"Branch A": _branch({"A1": _st()})},
                depends_on=["Task 0"],
            )
        }
        violations = check_dag_invariants(dag)
        self.assertTrue(any("not found in DAG" in v for v in violations))

    def test_branch_rollup_violation(self):
        """All subtasks Verified but branch still Pending."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Done"),
                    "A2": _st(status="Verified", shadow="Done"),
                }, status="Pending")  # Should be Verified!
            })
        }
        violations = check_dag_invariants(dag)
        self.assertTrue(any("all subtasks Verified" in v for v in violations))

    def test_task_rollup_violation(self):
        """All branches Verified but task still Pending."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Done"),
                }, status="Verified")
            }, status="Pending")
        }
        violations = check_dag_invariants(dag)
        self.assertTrue(any("all branches Verified" in v for v in violations))

    def test_shadow_status_misalignment(self):
        """shadow Done but status is Pending (not Verified/Review)."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", shadow="Done"),
                })
            })
        }
        violations = check_dag_invariants(dag)
        self.assertTrue(any("shadow=Done but status=Pending" in v for v in violations))

    def test_missing_required_key(self):
        """Subtask missing 'last_update' key."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": {"status": "Pending", "shadow": "Pending"},
                })
            })
        }
        violations = check_dag_invariants(dag)
        self.assertTrue(any("missing 'last_update'" in v for v in violations))


class TestPostPhaseInvariants(unittest.TestCase):
    """Lightweight post-phase checks for runtime use."""

    def test_valid_dag_passes(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({"A1": _st()})
            })
        }
        violations = check_post_phase_invariants(dag, "RepoAnalyzer")
        self.assertEqual(violations, [])

    def test_broken_dep_caught(self):
        dag = {
            "Task 1": _task(
                {"Branch A": _branch({"A1": _st()})},
                depends_on=["NonExistent"],
            )
        }
        violations = check_post_phase_invariants(dag, "Executor")
        self.assertTrue(any("missing from DAG" in v for v in violations))

    def test_phase_name_in_message(self):
        dag = {"Task 0": {"status": "Pending", "depends_on": []}}
        violations = check_post_phase_invariants(dag, "Verifier")
        self.assertTrue(any("[Verifier]" in v for v in violations))


class TestCheckDagInvariantsMultiTask(unittest.TestCase):
    """Multi-task DAG with dependencies."""

    def test_valid_multi_task(self):
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Verified", shadow="Done")},
                                     status="Verified")},
                status="Verified",
            ),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st(status="Running", last_update=5)},
                                     status="Running")},
                depends_on=["Task 0"],
                status="Running",
            ),
        }
        violations = check_dag_invariants(dag)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
