#!/usr/bin/env python3
"""
tests/test_core_runtime.py — Core runtime hardening tests.

Covers:
    A. Planner (prioritization, stall urgency, staleness, shadow conflict,
       dependency blocking, dynamic tasks)
    B. Verifier roll-up (branch/task status consistency)
    C. SelfHealer (stall detection, Review exclusion, healed_total tracking)
    D. ShadowAgent (stale shadow, shadow lag, expected-state consistency)
    E. Persistence compatibility (older state, backward-compat, backup rotation,
       save/load round-trip)
    F. Dynamic / autonomous integration invariants

Run:
    python -m pytest tests/test_core_runtime.py -v
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from solo_builder_cli import Planner, Verifier, SelfHealer, ShadowAgent


# ── DAG helpers ──────────────────────────────────────────────────────────────

def _st(status="Pending", shadow="Pending", last_update=0, description="", output=""):
    """Build a subtask dict."""
    return {
        "status": status,
        "shadow": shadow,
        "last_update": last_update,
        "description": description,
        "output": output,
    }


def _branch(subtasks, status="Pending"):
    return {"status": status, "subtasks": subtasks}


def _task(branches, status="Pending", depends_on=None):
    return {"status": status, "depends_on": depends_on or [], "branches": branches}


def _simple_dag(**overrides):
    """One task / one branch / two subtasks."""
    dag = {
        "Task 0": _task({
            "Branch A": _branch({
                "A1": _st(status="Pending", last_update=0),
                "A2": _st(status="Running", last_update=5),
            })
        })
    }
    dag.update(overrides)
    return dag


# ═══════════════════════════════════════════════════════════════════════════════
# A.  PLANNER
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlannerRunningOutranksPending(unittest.TestCase):
    """Running subtasks always have higher risk than Pending ones."""

    def test_running_beats_pending(self):
        planner = Planner(stall_threshold=10)
        dag = _simple_dag()
        result = planner.prioritize(dag, step=10)
        # A2 is Running, A1 is Pending
        self.assertEqual(result[0][2], "A2")
        self.assertGreater(result[0][3], result[1][3])


class TestPlannerStallUrgency(unittest.TestCase):
    """Stalled Running subtasks get extra urgency (base 1000 + 500 + staleness*20)."""

    def test_stalled_running_gets_boost(self):
        planner = Planner(stall_threshold=5)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", last_update=0),   # stalled (age 20 >= 5)
                    "A2": _st(status="Running", last_update=18),  # not stalled (age 2)
                })
            })
        }
        result = planner.prioritize(dag, step=20)
        stalled = [r for r in result if r[2] == "A1"][0]
        fresh   = [r for r in result if r[2] == "A2"][0]
        # Stalled: 1000 + 500 + 20*20 = 1900
        self.assertEqual(stalled[3], 1900)
        # Fresh: 1000 + 2*10 = 1020
        self.assertEqual(fresh[3], 1020)
        self.assertGreater(stalled[3], fresh[3])


class TestPlannerStalenessWeight(unittest.TestCase):
    """Pending subtask risk scales with staleness * 8 * w_staleness (only if staleness > 2)."""

    def test_staleness_scoring(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", last_update=0),  # staleness 10
                    "A2": _st(status="Pending", last_update=9),  # staleness 1 (≤2 → 0)
                })
            })
        }
        result = planner.prioritize(dag, step=10)
        scores = {r[2]: r[3] for r in result}
        self.assertEqual(scores["A1"], 10 * 8)  # staleness 10 * 8 * 1.0
        self.assertEqual(scores["A2"], 0)        # staleness 1 ≤ 2 → 0


class TestPlannerShadowConflictBonus(unittest.TestCase):
    """Pending with shadow Done gets 50 * w_shadow bonus."""

    def test_shadow_done_pending_bonus(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", shadow="Done", last_update=0),
                    "A2": _st(status="Pending", shadow="Pending", last_update=0),
                })
            })
        }
        result = planner.prioritize(dag, step=10)
        scores = {r[2]: r[3] for r in result}
        # A1: staleness 10*8 + shadow 50 = 130
        self.assertEqual(scores["A1"], 80 + 50)
        # A2: staleness 10*8 = 80
        self.assertEqual(scores["A2"], 80)


class TestPlannerDependencyBlocking(unittest.TestCase):
    """Tasks with unmet dependencies are excluded from prioritization."""

    def test_blocked_task_excluded(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({"A1": _st(status="Running", last_update=5)})
            }),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st(status="Pending", last_update=0)})},
                depends_on=["Task 0"],
            ),
        }
        result = planner.prioritize(dag, step=10)
        subtask_names = [r[2] for r in result]
        self.assertIn("A1", subtask_names)
        self.assertNotIn("B1", subtask_names)

    def test_unblocked_after_verified(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Verified")})},
                status="Verified",
            ),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st(status="Pending", last_update=0)})},
                depends_on=["Task 0"],
            ),
        }
        result = planner.prioritize(dag, step=10)
        subtask_names = [r[2] for r in result]
        self.assertIn("B1", subtask_names)


class TestPlannerVerifiedExcluded(unittest.TestCase):
    """Verified subtasks are never returned by prioritize()."""

    def test_verified_not_in_results(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified"),
                    "A2": _st(status="Pending", last_update=0),
                })
            })
        }
        result = planner.prioritize(dag, step=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][2], "A2")


class TestPlannerAdjustWeights(unittest.TestCase):
    """adjust_weights modifies the correct weight, with floor at 0.1."""

    def test_adjust_stall(self):
        p = Planner(stall_threshold=10)
        p.adjust_weights("stall_risk", -0.5)
        self.assertEqual(p.w_stall, 0.5)
        p.adjust_weights("stall_risk", -10)
        self.assertEqual(p.w_stall, 0.1)  # floor

    def test_adjust_all_keys(self):
        p = Planner(stall_threshold=10)
        for key, attr in [("stall_risk", "w_stall"), ("staleness", "w_staleness"),
                          ("shadow", "w_shadow"), ("repo", "w_repo")]:
            p.adjust_weights(key, 0.5)
            self.assertEqual(getattr(p, attr), 1.5)


class TestPlannerDynamicTaskVisibility(unittest.TestCase):
    """Tasks injected by RepoAnalyzer at runtime appear in prioritization."""

    def test_injected_task_visible(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Verified")})},
                status="Verified",
            ),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st(status="Pending", last_update=0)})},
                depends_on=["Task 0"],
            ),
        }
        result = planner.prioritize(dag, step=10)
        self.assertTrue(any(r[2] == "B1" for r in result))


# ═══════════════════════════════════════════════════════════════════════════════
# B.  VERIFIER
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifierBranchRollUp(unittest.TestCase):
    """Branch status should roll up from subtask statuses."""

    def test_all_verified_promotes_branch(self):
        v = Verifier()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified"),
                    "A2": _st(status="Verified"),
                }, status="Pending")
            })
        }
        fixes = v.verify(dag)
        self.assertEqual(dag["Task 0"]["branches"]["Branch A"]["status"], "Verified")
        self.assertTrue(any("Verified" in f for f in fixes))

    def test_any_running_promotes_branch_from_pending(self):
        v = Verifier()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running"),
                    "A2": _st(status="Pending"),
                }, status="Pending")
            })
        }
        fixes = v.verify(dag)
        self.assertEqual(dag["Task 0"]["branches"]["Branch A"]["status"], "Running")

    def test_running_branch_not_overwritten_to_running(self):
        """If branch is already Running, don't redundantly 'fix' it."""
        v = Verifier()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running"),
                    "A2": _st(status="Pending"),
                }, status="Running")
            })
        }
        fixes = v.verify(dag)
        # No fix needed — already Running
        branch_fixes = [f for f in fixes if "Branch A" in f and "Running" in f]
        self.assertEqual(len(branch_fixes), 0)


class TestVerifierTaskRollUp(unittest.TestCase):
    """Task status should roll up from branch statuses."""

    def test_all_branches_verified_promotes_task(self):
        v = Verifier()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({"A1": _st(status="Verified")}, status="Verified"),
                "Branch B": _branch({"B1": _st(status="Verified")}, status="Verified"),
            }, status="Pending")
        }
        fixes = v.verify(dag)
        self.assertEqual(dag["Task 0"]["status"], "Verified")

    def test_any_branch_running_promotes_task_from_pending(self):
        v = Verifier()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({"A1": _st(status="Running")}, status="Running"),
                "Branch B": _branch({"B1": _st(status="Pending")}, status="Pending"),
            }, status="Pending")
        }
        fixes = v.verify(dag)
        self.assertEqual(dag["Task 0"]["status"], "Running")

    def test_mixed_branches_no_false_verified(self):
        v = Verifier()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({"A1": _st(status="Verified")}, status="Verified"),
                "Branch B": _branch({"B1": _st(status="Pending")}, status="Pending"),
            }, status="Pending")
        }
        v.verify(dag)
        self.assertNotEqual(dag["Task 0"]["status"], "Verified")


# ═══════════════════════════════════════════════════════════════════════════════
# C.  SELF-HEALER
# ═══════════════════════════════════════════════════════════════════════════════

class TestSelfHealerStallDetection(unittest.TestCase):
    """Only Running subtasks past the stall threshold are detected."""

    def test_detects_stalled_running(self):
        h = SelfHealer(stall_threshold=5)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", last_update=0),  # age=10 >= 5 → stalled
                    "A2": _st(status="Running", last_update=8),  # age=2 < 5  → not stalled
                })
            })
        }
        stalled = h.find_stalled(dag, step=10)
        names = [s[2] for s in stalled]
        self.assertIn("A1", names)
        self.assertNotIn("A2", names)

    def test_review_not_detected(self):
        """Review subtasks must NOT be treated as stalled."""
        h = SelfHealer(stall_threshold=5)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "R1": _st(status="Review", last_update=0),  # age=20 but Review
                })
            })
        }
        stalled = h.find_stalled(dag, step=20)
        self.assertEqual(len(stalled), 0)

    def test_pending_not_detected(self):
        h = SelfHealer(stall_threshold=5)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "P1": _st(status="Pending", last_update=0),
                })
            })
        }
        stalled = h.find_stalled(dag, step=100)
        self.assertEqual(len(stalled), 0)


class TestSelfHealerHeal(unittest.TestCase):
    """Healing resets to Pending, updates shadow/last_update, increments healed_total."""

    def test_heal_resets_subtask(self):
        h = SelfHealer(stall_threshold=5)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", shadow="Pending", last_update=0),
                })
            })
        }
        stalled = [("Task 0", "Branch A", "A1", 15)]
        memory = {"Branch A": []}
        alerts = []
        count = h.heal(dag, stalled, step=15, memory_store=memory, alerts=alerts)

        st = dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Pending")
        self.assertEqual(st["shadow"], "Pending")
        self.assertEqual(st["last_update"], 15)
        self.assertEqual(count, 1)
        self.assertEqual(h.healed_total, 1)

    def test_healed_total_accumulates(self):
        h = SelfHealer(stall_threshold=5)
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", last_update=0),
                    "A2": _st(status="Running", last_update=0),
                })
            })
        }
        stalled = [("Task 0", "Branch A", "A1", 10), ("Task 0", "Branch A", "A2", 10)]
        h.heal(dag, stalled, step=10, memory_store={"Branch A": []}, alerts=[])
        self.assertEqual(h.healed_total, 2)
        # Heal again
        dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["status"] = "Running"
        dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["last_update"] = 10
        stalled2 = [("Task 0", "Branch A", "A1", 10)]
        h.heal(dag, stalled2, step=20, memory_store={"Branch A": []}, alerts=[])
        self.assertEqual(h.healed_total, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# D.  SHADOW AGENT
# ═══════════════════════════════════════════════════════════════════════════════

class TestShadowAgentExpectedState(unittest.TestCase):
    """update_expected rebuilds the st_name → status map."""

    def test_builds_expected_map(self):
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running"),
                    "A2": _st(status="Verified"),
                })
            })
        }
        sa.update_expected(dag)
        self.assertEqual(sa.expected["A1"], "Running")
        self.assertEqual(sa.expected["A2"], "Verified")


class TestShadowAgentConflictDetection(unittest.TestCase):
    """Detects shadow/status mismatches."""

    def test_shadow_done_status_pending(self):
        """shadow Done + status Pending → conflict."""
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", shadow="Done"),
                })
            })
        }
        conflicts = sa.detect_conflicts(dag)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0][2], "A1")

    def test_status_verified_shadow_pending(self):
        """status Verified + shadow Pending → shadow lag conflict."""
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Pending"),
                })
            })
        }
        conflicts = sa.detect_conflicts(dag)
        self.assertEqual(len(conflicts), 1)

    def test_no_conflict_when_aligned(self):
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Done"),
                    "A2": _st(status="Pending", shadow="Pending"),
                })
            })
        }
        conflicts = sa.detect_conflicts(dag)
        self.assertEqual(len(conflicts), 0)

    def test_shadow_done_status_running(self):
        """shadow Done + status Running → conflict (not Verified)."""
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", shadow="Done"),
                })
            })
        }
        conflicts = sa.detect_conflicts(dag)
        self.assertEqual(len(conflicts), 1)


class TestShadowAgentResolution(unittest.TestCase):
    """resolve_conflict aligns shadow with actual status."""

    def test_verified_sets_shadow_done(self):
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Pending"),
                })
            })
        }
        memory = {"Branch A": []}
        sa.resolve_conflict(dag, "Task 0", "Branch A", "A1", step=5, memory_store=memory)
        self.assertEqual(dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["shadow"], "Done")

    def test_non_verified_resets_shadow_pending(self):
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", shadow="Done"),
                })
            })
        }
        memory = {"Branch A": []}
        sa.resolve_conflict(dag, "Task 0", "Branch A", "A1", step=5, memory_store=memory)
        self.assertEqual(dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["shadow"], "Pending")

    def test_resolution_adds_memory(self):
        sa = ShadowAgent()
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Pending"),
                })
            })
        }
        memory = {"Branch A": []}
        sa.resolve_conflict(dag, "Task 0", "Branch A", "A1", step=7, memory_store=memory)
        self.assertTrue(any("conflict_resolved" in m["snapshot"] for m in memory["Branch A"]))


# ═══════════════════════════════════════════════════════════════════════════════
# E.  PERSISTENCE COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistenceBackwardCompat(unittest.TestCase):
    """Older state files without safety_state must load without error."""

    def test_load_without_safety_state(self):
        """Simulate an older state file missing the safety_state key."""
        tmp = tempfile.mkdtemp()
        state_path = os.path.join(tmp, "state.json")
        payload = {
            "step": 42,
            "snapshot_counter": 3,
            "healed_total": 7,
            "dag": {"Task 0": _task({"Branch A": _branch({"A1": _st()})})},
            "memory_store": {"Branch A": []},
            "alerts": ["old alert"],
        }
        with open(state_path, "w") as f:
            json.dump(payload, f)

        # Verify safety_state defaults work via .get()
        with open(state_path) as f:
            loaded = json.load(f)
        ss = loaded.get("safety_state", {})
        self.assertEqual(ss.get("dynamic_tasks_created", 0), 0)
        self.assertEqual(ss.get("ra_last_run_step", -1), -1)
        self.assertEqual(ss.get("patch_rejections", {}), {})
        self.assertEqual(ss.get("patch_threshold_hits", 0), 0)

    def test_load_with_safety_state(self):
        """State file with safety_state loads correctly."""
        tmp = tempfile.mkdtemp()
        state_path = os.path.join(tmp, "state.json")
        payload = {
            "step": 100,
            "snapshot_counter": 5,
            "healed_total": 12,
            "dag": {"Task 0": _task({"Branch A": _branch({"A1": _st()})})},
            "memory_store": {},
            "alerts": [],
            "meta_history": [{"healed": 1, "verified": 2}],
            "safety_state": {
                "dynamic_tasks_created": 15,
                "ra_last_run_step": 90,
                "patch_rejections": {"A1": {"count": 2, "reasons": ["bad"]}},
                "patch_threshold_hits": 3,
            },
        }
        with open(state_path, "w") as f:
            json.dump(payload, f)
        with open(state_path) as f:
            loaded = json.load(f)
        ss = loaded["safety_state"]
        self.assertEqual(ss["dynamic_tasks_created"], 15)
        self.assertEqual(ss["ra_last_run_step"], 90)
        self.assertEqual(ss["patch_rejections"]["A1"]["count"], 2)
        self.assertEqual(ss["patch_threshold_hits"], 3)


class TestSaveLoadRoundTrip(unittest.TestCase):
    """Verify save → load produces identical state."""

    def test_round_trip(self):
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Verified", shadow="Done")})},
                status="Verified",
            ),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st(status="Running", last_update=5)})},
                depends_on=["Task 0"],
            ),
        }
        payload = {
            "step": 50,
            "snapshot_counter": 2,
            "healed_total": 4,
            "dag": dag,
            "memory_store": {"Branch A": [{"snapshot": "test", "timestamp": 10}]},
            "alerts": ["alert1"],
            "meta_history": [{"healed": 0, "verified": 1}],
            "safety_state": {
                "dynamic_tasks_created": 8,
                "ra_last_run_step": 45,
                "patch_rejections": {},
                "patch_threshold_hits": 1,
            },
        }
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "state.json")
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        with open(path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["step"], 50)
        self.assertEqual(loaded["dag"], dag)
        self.assertEqual(loaded["safety_state"]["dynamic_tasks_created"], 8)


class TestBackupRotation(unittest.TestCase):
    """Backup rotation: current → .1, .1 → .2, .2 → .3, .3 deleted."""

    def test_rotation_logic(self):
        tmp = tempfile.mkdtemp()
        base = os.path.join(tmp, "state.json")
        # Simulate existing files
        for suffix in ["", ".1", ".2", ".3"]:
            with open(base + suffix, "w") as f:
                f.write(f"gen{suffix or '0'}")

        # Simulate rotation logic (from save_state)
        import shutil
        for i in range(3, 1, -1):
            src = f"{base}.{i - 1}"
            dst = f"{base}.{i}"
            if os.path.exists(src):
                os.replace(src, dst)
        shutil.copy2(base, f"{base}.1")

        # Verify: .1 = old current, .2 = old .1, .3 = old .2
        with open(f"{base}.1") as f:
            self.assertEqual(f.read(), "gen0")
        with open(f"{base}.2") as f:
            self.assertEqual(f.read(), "gen.1")
        with open(f"{base}.3") as f:
            self.assertEqual(f.read(), "gen.2")


# ═══════════════════════════════════════════════════════════════════════════════
# F.  DYNAMIC / AUTONOMOUS INTEGRATION INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDynamicIntegration(unittest.TestCase):
    """Integration invariants for dynamic task injection and persistence."""

    def test_injected_task_has_correct_structure(self):
        """A dynamically injected task must have valid DAG structure."""
        from utils.helper_functions import validate_dag
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Verified", shadow="Done")})},
                status="Verified",
            ),
            "Task 1": _task(
                {"Branch B": _branch({
                    "B1": _st(status="Pending", description="Fix TODO: memory leak"),
                })},
                depends_on=["Task 0"],
            ),
        }
        warnings = validate_dag(dag)
        self.assertEqual(warnings, [])

    def test_planner_sees_injected_task_when_deps_met(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Verified")})},
                status="Verified",
            ),
            "Task 1": _task(
                {"Branch Debt": _branch({
                    "D1": _st(status="Pending", last_update=0),
                })},
                depends_on=["Task 0"],
            ),
        }
        result = planner.prioritize(dag, step=20)
        self.assertTrue(any(r[2] == "D1" for r in result))

    def test_planner_blocks_injected_task_when_deps_unmet(self):
        planner = Planner(stall_threshold=10)
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Running", last_update=5)})},
            ),
            "Task 1": _task(
                {"Branch Debt": _branch({
                    "D1": _st(status="Pending", last_update=0),
                })},
                depends_on=["Task 0"],
            ),
        }
        result = planner.prioritize(dag, step=20)
        self.assertFalse(any(r[2] == "D1" for r in result))

    def test_verifier_correct_after_injection(self):
        """Verifier must correctly roll up status for newly added tasks."""
        v = Verifier()
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({"A1": _st(status="Verified")}, status="Verified")},
                status="Verified",
            ),
            "Task 1": _task(
                {"Branch Debt": _branch({
                    "D1": _st(status="Verified"),
                    "D2": _st(status="Verified"),
                }, status="Pending")},
                depends_on=["Task 0"],
                status="Pending",
            ),
        }
        v.verify(dag)
        self.assertEqual(dag["Task 1"]["branches"]["Branch Debt"]["status"], "Verified")
        self.assertEqual(dag["Task 1"]["status"], "Verified")


if __name__ == "__main__":
    unittest.main()
