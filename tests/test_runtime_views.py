#!/usr/bin/env python3
"""
tests/test_runtime_views.py — Consistency tests for canonical runtime views.

Verifies that the shared runtime_views module produces outputs consistent
with the CLI's live agents (Planner, SelfHealer, MetaOptimizer) for the
same DAG state.

Run:
    python -m pytest tests/test_runtime_views.py -v
    python -m unittest tests.test_runtime_views -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.runtime_views import (
    deps_met,
    compute_risk,
    priority_queue,
    stalled_subtasks,
    dag_summary,
    compute_rates,
    forecast_summary,
    agent_stats,
    per_task_stats,
)
from solo_builder_cli import Planner, SelfHealer, Verifier


# ── DAG helpers ──────────────────────────────────────────────────────────────

def _st(status="Pending", shadow="Pending", last_update=0, description="", output=""):
    return {
        "status": status, "shadow": shadow, "last_update": last_update,
        "description": description, "output": output,
    }


def _branch(subtasks, status="Pending"):
    return {"status": status, "subtasks": subtasks}


def _task(branches, status="Pending", depends_on=None):
    return {"status": status, "depends_on": depends_on or [], "branches": branches}


# ═══════════════════════════════════════════════════════════════════════════════
# PRIORITY CONSISTENCY  (shared helper vs live Planner)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPriorityConsistencyWithPlanner(unittest.TestCase):
    """Priority queue from runtime_views must match Planner.prioritize()."""

    def _compare(self, dag, step, stall_threshold=10):
        """Compare shared helper output against live Planner for same DAG."""
        planner = Planner(stall_threshold=stall_threshold)
        planner_result = planner.prioritize(dag, step)
        shared_result = priority_queue(dag, step, stall_threshold=stall_threshold)

        # Same number of candidates
        self.assertEqual(len(planner_result), len(shared_result),
                         f"Count mismatch: planner={len(planner_result)}, "
                         f"shared={len(shared_result)}")

        # Same ordering and risk scores
        for i, (pr, sr) in enumerate(zip(planner_result, shared_result)):
            p_task, p_branch, p_st, p_risk = pr
            self.assertEqual(sr["subtask"], p_st,
                             f"Row {i}: subtask mismatch {sr['subtask']} != {p_st}")
            self.assertEqual(sr["task"], p_task,
                             f"Row {i}: task mismatch {sr['task']} != {p_task}")
            self.assertEqual(sr["risk"], p_risk,
                             f"Row {i}: risk mismatch {sr['risk']} != {p_risk} "
                             f"for {p_st}")

    def test_simple_pending_running(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", last_update=0),
                    "A2": _st(status="Running", last_update=5),
                })
            })
        }
        self._compare(dag, step=20, stall_threshold=10)

    def test_stalled_running_bonus(self):
        """Stalled Running subtask gets 500*w_stall + staleness*20 bonus."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", last_update=0),   # stalled
                    "A2": _st(status="Running", last_update=18),  # not stalled
                })
            })
        }
        self._compare(dag, step=20, stall_threshold=5)

    def test_shadow_done_bonus(self):
        """Pending + shadow Done gets 50*w_shadow bonus."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", shadow="Done", last_update=0),
                    "A2": _st(status="Pending", shadow="Pending", last_update=0),
                })
            })
        }
        self._compare(dag, step=10, stall_threshold=10)

    def test_staleness_gate(self):
        """Pending with staleness <= 2 gets risk 0."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Pending", last_update=8),  # staleness 2
                    "A2": _st(status="Pending", last_update=0),  # staleness 10
                })
            })
        }
        self._compare(dag, step=10, stall_threshold=10)

    def test_dependency_blocking(self):
        """Blocked tasks excluded from both."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({"A1": _st(status="Running", last_update=5)})
            }),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st(status="Pending")})},
                depends_on=["Task 0"],
            ),
        }
        self._compare(dag, step=20, stall_threshold=10)

    def test_verified_excluded(self):
        """Verified subtasks not in results."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified"),
                    "A2": _st(status="Pending", last_update=0),
                })
            })
        }
        self._compare(dag, step=15, stall_threshold=10)

    def test_dynamic_injected_task(self):
        """Dynamically injected tasks visible when deps met."""
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
        self._compare(dag, step=20, stall_threshold=10)

    def test_empty_dag(self):
        self._compare({}, step=10, stall_threshold=10)

    def test_multi_task_mixed(self):
        """Complex multi-task DAG with mixed statuses."""
        dag = {
            "Task 0": _task(
                {"Branch A": _branch({
                    "A1": _st(status="Verified", shadow="Done"),
                    "A2": _st(status="Running", last_update=3),
                })},
                status="Running",
            ),
            "Task 1": _task(
                {"Branch B": _branch({
                    "B1": _st(status="Pending", last_update=0),
                    "B2": _st(status="Running", last_update=0),  # stalled
                })},
                depends_on=["Task 0"],
            ),
            "Task 2": _task(
                {"Branch C": _branch({
                    "C1": _st(status="Pending", shadow="Done", last_update=1),
                })},
            ),
        }
        self._compare(dag, step=20, stall_threshold=5)


# ═══════════════════════════════════════════════════════════════════════════════
# STALLED CONSISTENCY  (shared helper vs live SelfHealer)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStalledConsistencyWithSelfHealer(unittest.TestCase):
    """Stalled list from runtime_views must match SelfHealer.find_stalled()."""

    def _compare(self, dag, step, threshold=10):
        healer = SelfHealer(stall_threshold=threshold)
        healer_result = healer.find_stalled(dag, step)
        shared_result = stalled_subtasks(dag, step, stall_threshold=threshold)

        # Same count
        self.assertEqual(len(healer_result), len(shared_result))

        # Same subtask names (order: both sorted by age desc)
        healer_names = [s[2] for s in healer_result]
        shared_names = [s["subtask"] for s in shared_result]
        self.assertEqual(healer_names, shared_names)

        # Same ages
        healer_ages = [s[3] for s in healer_result]
        shared_ages = [s["age"] for s in shared_result]
        self.assertEqual(healer_ages, shared_ages)

    def test_basic_stalled(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Running", last_update=0),  # stalled
                    "A2": _st(status="Running", last_update=8),  # not stalled
                })
            })
        }
        self._compare(dag, step=10, threshold=5)

    def test_review_excluded(self):
        """Review subtasks must NOT appear in stalled list."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "R1": _st(status="Review", last_update=0),
                })
            })
        }
        self._compare(dag, step=100, threshold=5)

    def test_pending_excluded(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "P1": _st(status="Pending", last_update=0),
                })
            })
        }
        self._compare(dag, step=100, threshold=5)

    def test_empty_dag(self):
        self._compare({}, step=10, threshold=5)


# ═══════════════════════════════════════════════════════════════════════════════
# FORECAST / RATES CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeRates(unittest.TestCase):
    """Rate computation must match MetaOptimizer.record() logic."""

    def test_empty_history(self):
        rates = compute_rates([])
        self.assertEqual(rates["verify_rate"], 0.0)
        self.assertEqual(rates["heal_rate"], 0.0)

    def test_rolling_window(self):
        history = [{"healed": 1, "verified": 2}] * 20
        rates = compute_rates(history)
        self.assertAlmostEqual(rates["verify_rate"], 2.0)
        self.assertAlmostEqual(rates["heal_rate"], 1.0)

    def test_short_history(self):
        history = [{"healed": 0, "verified": 3}]
        rates = compute_rates(history)
        self.assertAlmostEqual(rates["verify_rate"], 3.0)
        self.assertAlmostEqual(rates["heal_rate"], 0.0)

    def test_window_caps_at_10(self):
        """Only last 10 entries should matter."""
        old = [{"healed": 100, "verified": 100}] * 5
        new = [{"healed": 0, "verified": 1}] * 10
        rates = compute_rates(old + new)
        self.assertAlmostEqual(rates["verify_rate"], 1.0)
        self.assertAlmostEqual(rates["heal_rate"], 0.0)


class TestForecastSummary(unittest.TestCase):
    """Forecast summary must produce correct stats and ETA."""

    def test_basic_forecast(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified"),
                    "A2": _st(status="Running"),
                    "A3": _st(status="Pending"),
                })
            })
        }
        history = [{"healed": 0, "verified": 1}] * 10
        fc = forecast_summary(dag, history, step=20)
        self.assertEqual(fc["total"], 3)
        self.assertEqual(fc["verified"], 1)
        self.assertEqual(fc["running"], 1)
        self.assertEqual(fc["pending"], 1)
        self.assertEqual(fc["remaining"], 2)
        self.assertAlmostEqual(fc["verify_rate"], 1.0)
        self.assertEqual(fc["eta_steps"], 2)  # remaining 2 / rate 1.0

    def test_no_history_eta_none(self):
        dag = {"Task 0": _task({"Branch A": _branch({"A1": _st()})})}
        fc = forecast_summary(dag, [], step=5)
        self.assertIsNone(fc["eta_steps"])

    def test_empty_dag(self):
        fc = forecast_summary({}, [], step=0)
        self.assertEqual(fc["total"], 0)
        self.assertIsNone(fc["eta_steps"])


# ═══════════════════════════════════════════════════════════════════════════════
# DAG SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestDagSummary(unittest.TestCase):
    def test_counts(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified"),
                    "A2": _st(status="Running"),
                    "A3": _st(status="Pending"),
                    "A4": _st(status="Review"),
                    "A5": _st(status="Failed"),
                })
            })
        }
        s = dag_summary(dag)
        self.assertEqual(s["total"], 5)
        self.assertEqual(s["verified"], 1)
        self.assertEqual(s["running"], 1)
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["review"], 1)
        self.assertEqual(s["failed"], 1)

    def test_empty_dag(self):
        s = dag_summary({})
        self.assertEqual(s["total"], 0)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentStats(unittest.TestCase):
    def test_basic_agent_stats(self):
        state = {
            "step": 50,
            "healed_total": 3,
            "dag": {
                "Task 0": _task({
                    "Branch A": _branch({
                        "A1": _st(status="Verified"),
                        "A2": _st(status="Running", last_update=30),
                    })
                })
            },
            "meta_history": [{"healed": 1, "verified": 2}] * 5,
            "safety_state": {
                "dynamic_tasks_created": 4,
                "patch_rejections": {"X1": {"count": 2}},
                "patch_threshold_hits": 1,
            },
        }
        a = agent_stats(state, stall_threshold=10, executor_max_per_step=6)
        self.assertEqual(a["step"], 50)
        self.assertEqual(a["healer"]["healed_total"], 3)
        self.assertEqual(a["healer"]["threshold"], 10)
        self.assertEqual(a["healer"]["currently_stalled"], 1)  # A2 age=20 >= 10
        self.assertAlmostEqual(a["meta"]["verify_rate"], 2.0)
        self.assertAlmostEqual(a["meta"]["heal_rate"], 1.0)
        self.assertEqual(a["forecast"]["total"], 2)
        self.assertEqual(a["forecast"]["verified"], 1)
        self.assertEqual(a["safety_guard"]["dynamic_tasks_created"], 4)
        self.assertEqual(a["safety_guard"]["patch_rejections_total"], 2)
        self.assertEqual(a["safety_guard"]["patch_threshold_hits"], 1)

    def test_backward_compat_no_safety_state(self):
        """Older state without safety_state should still work."""
        state = {
            "step": 10,
            "healed_total": 0,
            "dag": {"Task 0": _task({"Branch A": _branch({"A1": _st()})})},
            "meta_history": [],
        }
        a = agent_stats(state, stall_threshold=10)
        self.assertEqual(a["safety_guard"]["dynamic_tasks_created"], 0)
        self.assertEqual(a["safety_guard"]["patch_rejections_total"], 0)
        self.assertEqual(a["safety_guard"]["patch_threshold_hits"], 0)


# ═══════════════════════════════════════════════════════════════════════════════
# PER-TASK STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerTaskStats(unittest.TestCase):
    def test_basic_stats(self):
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": _st(status="Verified"),
                    "A2": _st(status="Pending"),
                })
            }),
            "Task 1": _task({
                "Branch B": _branch({
                    "B1": _st(status="Running"),
                })
            }),
        }
        result = per_task_stats(dag)
        self.assertEqual(result["grand_verified"], 1)
        self.assertEqual(result["grand_total"], 3)
        self.assertEqual(len(result["tasks"]), 2)
        t0 = [t for t in result["tasks"] if t["id"] == "Task 0"][0]
        self.assertEqual(t0["verified"], 1)
        self.assertEqual(t0["total"], 2)
        self.assertEqual(t0["pct"], 50.0)

    def test_empty_dag(self):
        result = per_task_stats({})
        self.assertEqual(result["grand_total"], 0)
        self.assertEqual(len(result["tasks"]), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPS_MET
# ═══════════════════════════════════════════════════════════════════════════════

class TestDepsMet(unittest.TestCase):
    def test_no_deps(self):
        dag = {"Task 0": _task({"Branch A": _branch({"A1": _st()})})}
        self.assertTrue(deps_met(dag, "Task 0"))

    def test_dep_verified(self):
        dag = {
            "Task 0": _task({"Branch A": _branch({"A1": _st()})}, status="Verified"),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st()})},
                depends_on=["Task 0"],
            ),
        }
        self.assertTrue(deps_met(dag, "Task 1"))

    def test_dep_not_verified(self):
        dag = {
            "Task 0": _task({"Branch A": _branch({"A1": _st()})}, status="Running"),
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st()})},
                depends_on=["Task 0"],
            ),
        }
        self.assertFalse(deps_met(dag, "Task 1"))

    def test_missing_dep(self):
        dag = {
            "Task 1": _task(
                {"Branch B": _branch({"B1": _st()})},
                depends_on=["Task 0"],
            ),
        }
        self.assertFalse(deps_met(dag, "Task 1"))


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE_RISK MATCHES PLANNER._RISK
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeRiskMatchesPlanner(unittest.TestCase):
    """compute_risk() must return identical values to Planner._risk()."""

    def _compare(self, st_data, step, threshold=10):
        planner = Planner(stall_threshold=threshold)
        expected = planner._risk(st_data, step)
        actual = compute_risk(st_data, step, stall_threshold=threshold)
        self.assertEqual(actual, expected,
                         f"Risk mismatch for {st_data}: expected {expected}, got {actual}")

    def test_pending_fresh(self):
        self._compare(_st(status="Pending", last_update=9), step=10)

    def test_pending_stale(self):
        self._compare(_st(status="Pending", last_update=0), step=10)

    def test_pending_shadow_done(self):
        self._compare(_st(status="Pending", shadow="Done", last_update=0), step=10)

    def test_running_fresh(self):
        self._compare(_st(status="Running", last_update=8), step=10, threshold=5)

    def test_running_stalled(self):
        self._compare(_st(status="Running", last_update=0), step=20, threshold=5)

    def test_verified(self):
        self._compare(_st(status="Verified"), step=10)

    def test_review(self):
        self._compare(_st(status="Review"), step=10)


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-SURFACE CONSISTENCY (simulated)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossSurfaceConsistency(unittest.TestCase):
    """
    Simulate what API and bot would compute for the same state,
    verify they produce identical results via shared helpers.
    """

    def _make_state(self):
        return {
            "step": 30,
            "healed_total": 2,
            "dag": {
                "Task 0": _task(
                    {"Branch A": _branch({
                        "A1": _st(status="Verified", shadow="Done"),
                        "A2": _st(status="Running", last_update=10),
                        "A3": _st(status="Pending", last_update=5),
                    })},
                    status="Running",
                ),
                "Task 1": _task(
                    {"Branch B": _branch({
                        "B1": _st(status="Pending", shadow="Done", last_update=0),
                    })},
                    depends_on=["Task 0"],
                ),
            },
            "meta_history": [
                {"healed": 0, "verified": 1},
                {"healed": 1, "verified": 0},
                {"healed": 0, "verified": 2},
            ],
            "safety_state": {
                "dynamic_tasks_created": 3,
                "ra_last_run_step": 25,
                "patch_rejections": {},
                "patch_threshold_hits": 0,
            },
        }

    def test_priority_api_vs_bot(self):
        """Both surfaces use same shared helper → identical results."""
        state = self._make_state()
        dag = state["dag"]
        step = state["step"]
        threshold = 10

        # Both API and bot now call _priority_queue
        api_result = priority_queue(dag, step, stall_threshold=threshold, limit=30)
        bot_result = priority_queue(dag, step, stall_threshold=threshold)

        # API limits to 30, but with <30 candidates they should be identical
        self.assertEqual(api_result, bot_result[:30])

    def test_stalled_api_vs_bot(self):
        state = self._make_state()
        dag = state["dag"]
        step = state["step"]
        threshold = 10

        api_result = stalled_subtasks(dag, step, stall_threshold=threshold)
        bot_result = stalled_subtasks(dag, step, stall_threshold=threshold)
        self.assertEqual(api_result, bot_result)

    def test_forecast_api_vs_bot(self):
        state = self._make_state()
        dag = state["dag"]
        step = state["step"]
        meta_history = state["meta_history"]

        api_result = forecast_summary(dag, meta_history, step)
        bot_result = forecast_summary(dag, meta_history, step)
        self.assertEqual(api_result, bot_result)

    def test_agents_api_vs_bot(self):
        state = self._make_state()
        api_result = agent_stats(state, stall_threshold=10, executor_max_per_step=6)
        bot_result = agent_stats(state, stall_threshold=10, executor_max_per_step=6)
        self.assertEqual(api_result, bot_result)

    def test_priority_matches_cli_planner(self):
        """Shared helper must match the live Planner for same state."""
        state = self._make_state()
        dag = state["dag"]
        step = state["step"]
        threshold = 10

        planner = Planner(stall_threshold=threshold)
        planner_result = planner.prioritize(dag, step)
        shared_result = priority_queue(dag, step, stall_threshold=threshold)

        self.assertEqual(len(planner_result), len(shared_result))
        for pr, sr in zip(planner_result, shared_result):
            self.assertEqual(pr[2], sr["subtask"])
            self.assertEqual(pr[3], sr["risk"])

    def test_stalled_matches_cli_healer(self):
        """Shared helper must match the live SelfHealer for same state."""
        state = self._make_state()
        dag = state["dag"]
        step = state["step"]
        threshold = 10

        healer = SelfHealer(stall_threshold=threshold)
        healer_result = healer.find_stalled(dag, step)
        shared_result = stalled_subtasks(dag, step, stall_threshold=threshold)

        self.assertEqual(len(healer_result), len(shared_result))
        for hr, sr in zip(healer_result, shared_result):
            self.assertEqual(hr[2], sr["subtask"])
            self.assertEqual(hr[3], sr["age"])


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility(unittest.TestCase):
    """Shared helpers work with older state files missing newer keys."""

    def test_state_without_meta_history(self):
        state = {
            "step": 10,
            "healed_total": 0,
            "dag": {"Task 0": _task({"Branch A": _branch({"A1": _st()})})},
        }
        a = agent_stats(state, stall_threshold=10)
        self.assertEqual(a["meta"]["verify_rate"], 0.0)
        self.assertIsNone(a["forecast"]["eta_steps"])

    def test_state_without_safety_state(self):
        state = {
            "step": 5,
            "healed_total": 0,
            "dag": {"Task 0": _task({"Branch A": _branch({"A1": _st()})})},
            "meta_history": [],
        }
        a = agent_stats(state, stall_threshold=10)
        self.assertEqual(a["safety_guard"]["dynamic_tasks_created"], 0)

    def test_subtask_without_last_update(self):
        """Subtask missing last_update defaults to 0."""
        dag = {
            "Task 0": _task({
                "Branch A": _branch({
                    "A1": {"status": "Running", "shadow": "Pending"},
                })
            })
        }
        stuck = stalled_subtasks(dag, step=100, stall_threshold=5)
        self.assertEqual(len(stuck), 1)
        self.assertEqual(stuck[0]["age"], 100)


if __name__ == "__main__":
    unittest.main()
