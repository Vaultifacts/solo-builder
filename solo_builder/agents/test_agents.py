"""Unit tests for solo_builder/agents/ package."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure solo_builder/ is on sys.path so agents/* can import utils.helper_functions
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.planner import Planner
from agents.shadow_agent import ShadowAgent
from agents.verifier import Verifier
from agents.self_healer import SelfHealer
from agents.meta_optimizer import MetaOptimizer


# ── Helpers ───────────────────────────────────────────────────────────────────

def _st(status="Pending", last_update=0, shadow="Pending", tools=""):
    return {"status": status, "last_update": last_update, "shadow": shadow, "tools": tools}


def _branch(subtasks, status="Pending"):
    return {"status": status, "subtasks": subtasks}


def _task(branches, status="Pending", depends_on=None):
    d = {"status": status, "branches": branches}
    if depends_on:
        d["depends_on"] = depends_on
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# Planner
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlannerRisk(unittest.TestCase):

    def setUp(self):
        self.p = Planner(stall_threshold=5)

    def test_running_base_risk_at_least_1000(self):
        st = _st("Running", last_update=0)
        self.assertGreaterEqual(self.p._risk(st, step=1), 1000)

    def test_running_stalled_higher_than_fresh(self):
        fresh   = self.p._risk(_st("Running", last_update=4), step=5)   # age=1
        stalled = self.p._risk(_st("Running", last_update=0), step=5)   # age=5 = threshold
        self.assertGreater(stalled, fresh)

    def test_pending_low_staleness_zero_risk(self):
        st = _st("Pending", last_update=4)
        self.assertEqual(self.p._risk(st, step=5), 0)   # age=1 ≤ 2

    def test_pending_shadow_done_adds_urgency(self):
        plain  = self.p._risk(_st("Pending", last_update=0, shadow="Pending"), step=10)
        shadow = self.p._risk(_st("Pending", last_update=0, shadow="Done"),    step=10)
        self.assertGreater(shadow, plain)

    def test_verified_zero_risk(self):
        st = _st("Verified", last_update=0)
        self.assertEqual(self.p._risk(st, step=100), 0)

    def test_adjust_weights_clamps_at_minimum(self):
        for _ in range(100):
            self.p.adjust_weights("stall_risk", -1.0)
        self.assertGreaterEqual(self.p.w_stall, 0.1)


class TestPlannerPrioritize(unittest.TestCase):

    def setUp(self):
        self.p = Planner(stall_threshold=5)

    def test_prioritize_returns_candidates(self):
        dag = {
            "Task 0": _task({"A": _branch({"A1": _st("Pending", last_update=0)})})
        }
        result = self.p.prioritize(dag, step=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][2], "A1")

    def test_prioritize_skips_verified(self):
        dag = {
            "Task 0": _task({"A": _branch({"A1": _st("Verified")})})
        }
        self.assertEqual(self.p.prioritize(dag, step=10), [])

    def test_prioritize_sorts_highest_risk_first(self):
        dag = {
            "Task 0": _task({
                "A": _branch({
                    "A1": _st("Running", last_update=0),   # risk ≥ 1000
                    "A2": _st("Pending", last_update=0),   # lower risk
                })
            })
        }
        result = self.p.prioritize(dag, step=10)
        self.assertEqual(result[0][2], "A1")

    def test_prioritize_skips_task_with_unmet_dep(self):
        dag = {
            "Task 0": _task({"A": _branch({"A1": _st("Verified")})}, status="Verified"),
            "Task 1": _task(
                {"B": _branch({"B1": _st("Pending")})},
                depends_on=["Task 0"],
            ),
            "Task 2": _task(
                {"C": _branch({"C1": _st("Pending")})},
                depends_on=["Task 99"],   # unmet
            ),
        }
        result = self.p.prioritize(dag, step=5)
        subtasks = [r[2] for r in result]
        self.assertIn("B1", subtasks)
        self.assertNotIn("C1", subtasks)


# ═══════════════════════════════════════════════════════════════════════════════
# ShadowAgent
# ═══════════════════════════════════════════════════════════════════════════════

class TestShadowAgent(unittest.TestCase):

    def setUp(self):
        self.sa = ShadowAgent()

    def _dag(self, status, shadow):
        return {"T0": _task({"A": _branch({"A1": _st(status, shadow=shadow)})})}

    def test_update_expected_builds_map(self):
        dag = self._dag("Pending", "Pending")
        self.sa.update_expected(dag)
        self.assertEqual(self.sa.expected["A1"], "Pending")

    def test_detect_conflict_shadow_done_not_verified(self):
        dag = self._dag("Pending", "Done")
        conflicts = self.sa.detect_conflicts(dag)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0][2], "A1")

    def test_detect_conflict_verified_shadow_pending(self):
        dag = self._dag("Verified", "Pending")
        conflicts = self.sa.detect_conflicts(dag)
        self.assertEqual(len(conflicts), 1)

    def test_detect_no_conflicts_when_consistent(self):
        dag = self._dag("Verified", "Done")
        self.assertEqual(self.sa.detect_conflicts(dag), [])

    def test_resolve_conflict_verified_sets_shadow_done(self):
        dag = self._dag("Verified", "Pending")
        with patch("agents.shadow_agent.add_memory_snapshot"):
            self.sa.resolve_conflict(dag, "T0", "A", "A1", step=1, memory_store={})
        self.assertEqual(dag["T0"]["branches"]["A"]["subtasks"]["A1"]["shadow"], "Done")

    def test_resolve_conflict_pending_sets_shadow_pending(self):
        dag = self._dag("Pending", "Done")
        with patch("agents.shadow_agent.add_memory_snapshot"):
            self.sa.resolve_conflict(dag, "T0", "A", "A1", step=1, memory_store={})
        self.assertEqual(dag["T0"]["branches"]["A"]["subtasks"]["A1"]["shadow"], "Pending")


# ═══════════════════════════════════════════════════════════════════════════════
# Verifier
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifier(unittest.TestCase):

    def setUp(self):
        self.v = Verifier()

    def test_all_subtasks_verified_promotes_branch(self):
        dag = {"T0": _task({"A": _branch({"A1": _st("Verified"), "A2": _st("Verified")})})}
        fixes = self.v.verify(dag)
        self.assertEqual(dag["T0"]["branches"]["A"]["status"], "Verified")
        self.assertTrue(any("Branch A" in f for f in fixes))

    def test_running_subtask_marks_branch_running(self):
        dag = {"T0": _task({"A": _branch({"A1": _st("Running"), "A2": _st("Pending")})})}
        self.v.verify(dag)
        self.assertEqual(dag["T0"]["branches"]["A"]["status"], "Running")

    def test_all_branches_verified_promotes_task(self):
        dag = {
            "T0": _task({
                "A": _branch({"A1": _st("Verified")}, status="Verified"),
                "B": _branch({"B1": _st("Verified")}, status="Verified"),
            })
        }
        fixes = self.v.verify(dag)
        self.assertEqual(dag["T0"]["status"], "Verified")
        self.assertTrue(any("Task T0" in f for f in fixes))

    def test_consistent_dag_no_fixes(self):
        dag = {
            "T0": _task({"A": _branch({"A1": _st("Verified")}, status="Verified")}, status="Verified")
        }
        fixes = self.v.verify(dag)
        self.assertEqual(fixes, [])


# ═══════════════════════════════════════════════════════════════════════════════
# SelfHealer
# ═══════════════════════════════════════════════════════════════════════════════

class TestSelfHealer(unittest.TestCase):

    def setUp(self):
        self.sh = SelfHealer(stall_threshold=5)

    def _dag_with(self, status, last_update=0):
        return {"T0": _task({"A": _branch({"A1": _st(status, last_update=last_update)})})}

    def test_find_stalled_detects_running_past_threshold(self):
        dag = self._dag_with("Running", last_update=0)
        stalled = self.sh.find_stalled(dag, step=5)
        self.assertEqual(len(stalled), 1)
        self.assertEqual(stalled[0][2], "A1")

    def test_find_stalled_ignores_fresh_running(self):
        dag = self._dag_with("Running", last_update=4)
        stalled = self.sh.find_stalled(dag, step=5)  # age=1 < threshold=5
        self.assertEqual(stalled, [])

    def test_find_stalled_ignores_review(self):
        dag = self._dag_with("Review", last_update=0)
        self.assertEqual(self.sh.find_stalled(dag, step=100), [])

    def test_find_stalled_ignores_pending(self):
        dag = self._dag_with("Pending", last_update=0)
        self.assertEqual(self.sh.find_stalled(dag, step=100), [])

    def test_heal_resets_to_pending(self):
        dag = self._dag_with("Running", last_update=0)
        stalled = self.sh.find_stalled(dag, step=5)
        with patch("agents.self_healer.add_memory_snapshot"):
            count = self.sh.heal(dag, stalled, step=5, memory_store={}, alerts=[])
        st = dag["T0"]["branches"]["A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Pending")
        self.assertEqual(st["shadow"], "Pending")
        self.assertEqual(count, 1)
        self.assertEqual(self.sh.healed_total, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# MetaOptimizer
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetaOptimizer(unittest.TestCase):

    def setUp(self):
        self.mo = MetaOptimizer()
        self.planner = Planner(stall_threshold=5)

    def test_record_computes_rates(self):
        for _ in range(3):
            self.mo.record(healed=1, verified=0)
        self.assertAlmostEqual(self.mo.heal_rate, 1.0)
        self.assertAlmostEqual(self.mo.verify_rate, 0.0)

    def test_optimize_returns_none_before_5_records(self):
        for _ in range(4):
            self.mo.record(0, 0)
        self.assertIsNone(self.mo.optimize(self.planner))

    def test_optimize_high_heal_rate_adjusts_stall_weight(self):
        for _ in range(5):
            self.mo.record(healed=1, verified=0)   # heal_rate=1.0 > 0.5
        old_w = self.planner.w_stall
        self.mo.optimize(self.planner)
        self.assertGreater(self.planner.w_stall, old_w)

    def test_optimize_low_verify_rate_adjusts_staleness_weight(self):
        for _ in range(5):
            self.mo.record(healed=0, verified=0)   # verify_rate=0.0 < 0.2
        old_w = self.planner.w_staleness
        self.mo.optimize(self.planner)
        self.assertGreater(self.planner.w_staleness, old_w)

    def test_forecast_complete(self):
        dag = {"T0": _task({"A": _branch({"A1": _st("Verified")}, status="Verified")}, status="Verified")}
        result = self.mo.forecast(dag)
        self.assertIn("COMPLETE", result)

    def test_forecast_empty_dag(self):
        self.assertEqual(self.mo.forecast({}), "N/A")

    def test_forecast_partial_no_rate(self):
        dag = {"T0": _task({"A": _branch({"A1": _st("Pending"), "A2": _st("Verified")})})}
        result = self.mo.forecast(dag)
        self.assertIn("50", result)   # 1/2 = 50%

    def test_forecast_with_verify_rate_returns_eta(self):
        for _ in range(5):
            self.mo.record(healed=0, verified=1)   # verify_rate=1.0 > 0
        dag = {"T0": _task({"A": _branch({
            "A1": _st("Verified"), "A2": _st("Pending")
        })})}
        result = self.mo.forecast(dag)
        self.assertIn("steps", result)   # ETA branch

    def test_optimize_returns_none_when_rates_moderate(self):
        # heal_rate ≤ 0.5, verify_rate ≥ 0.2 → neither condition fires
        for _ in range(5):
            self.mo.record(healed=0, verified=1)   # heal_rate=0, verify_rate=1.0
        result = self.mo.optimize(self.planner)
        self.assertIsNone(result)


class TestPlannerAdjustWeightsShadow(unittest.TestCase):

    def setUp(self):
        self.p = Planner(stall_threshold=5)

    def test_adjust_weights_shadow_key_increases(self):
        old = self.p.w_shadow
        self.p.adjust_weights("shadow", 0.1)
        self.assertGreater(self.p.w_shadow, old)

    def test_adjust_weights_shadow_clamps_at_minimum(self):
        for _ in range(100):
            self.p.adjust_weights("shadow", -1.0)
        self.assertGreaterEqual(self.p.w_shadow, 0.1)


if __name__ == "__main__":
    unittest.main()
