#!/usr/bin/env python3
"""
tests/test_budget_manager.py — Tests for budget management, cost tracking,
and cumulative usage accounting.

Covers:
    - StepBudget token and cost limit deferral
    - StepBudget record_usage tracking
    - UsageTracker cumulative accounting
    - UsageTracker serialization/deserialization
    - UsageTracker backward compatibility
    - Budget-aware observability fields in agent_stats

Run:
    python -m pytest tests/test_budget_manager.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.safety import StepBudget
from core.budget import UsageTracker
from core.persistence import apply_backward_compat_defaults
from utils.runtime_views import agent_stats


class TestStepBudgetTokenLimit(unittest.TestCase):
    """StepBudget exhaustion via token limit."""

    def test_token_limit_exhaustion(self):
        b = StepBudget(max_tokens=500)
        self.assertFalse(b.exhausted)
        b.record_usage(tokens=300)
        self.assertFalse(b.exhausted)
        b.record_usage(tokens=200)
        self.assertTrue(b.exhausted)

    def test_token_limit_defers_consume(self):
        b = StepBudget(max_tokens=100)
        b.record_usage(tokens=100)
        self.assertFalse(b.consume(1))
        self.assertEqual(b.deferred, 1)

    def test_token_limit_zero_means_unlimited(self):
        b = StepBudget(max_tokens=0)
        b.record_usage(tokens=999999)
        self.assertFalse(b.exhausted)
        self.assertTrue(b.consume(1))


class TestStepBudgetCostLimit(unittest.TestCase):
    """StepBudget exhaustion via cost limit."""

    def test_cost_limit_exhaustion(self):
        b = StepBudget(max_cost_usd=0.01)
        self.assertFalse(b.exhausted)
        b.record_usage(cost_usd=0.005)
        self.assertFalse(b.exhausted)
        b.record_usage(cost_usd=0.005)
        self.assertTrue(b.exhausted)

    def test_cost_limit_defers_consume(self):
        b = StepBudget(max_cost_usd=0.01)
        b.record_usage(cost_usd=0.01)
        self.assertFalse(b.consume(1))
        self.assertEqual(b.deferred, 1)

    def test_cost_limit_zero_means_unlimited(self):
        b = StepBudget(max_cost_usd=0.0)
        b.record_usage(cost_usd=999.99)
        self.assertFalse(b.exhausted)


class TestStepBudgetCombinedLimits(unittest.TestCase):
    """StepBudget with multiple limits — first to trigger wins."""

    def test_calls_triggers_first(self):
        b = StepBudget(max_calls=2, max_tokens=10000, max_cost_usd=1.0)
        b.consume(2)
        self.assertTrue(b.exhausted)
        self.assertEqual(b.tokens_used, 0)

    def test_tokens_triggers_first(self):
        b = StepBudget(max_calls=100, max_tokens=50, max_cost_usd=1.0)
        b.record_usage(tokens=50)
        self.assertTrue(b.exhausted)
        self.assertEqual(b.used, 0)

    def test_cost_triggers_first(self):
        b = StepBudget(max_calls=100, max_tokens=10000, max_cost_usd=0.001)
        b.record_usage(cost_usd=0.001)
        self.assertTrue(b.exhausted)
        self.assertEqual(b.used, 0)


class TestStepBudgetRecordUsage(unittest.TestCase):
    """record_usage accumulates correctly."""

    def test_accumulates_tokens_and_cost(self):
        b = StepBudget()
        b.record_usage(tokens=100, cost_usd=0.01)
        b.record_usage(tokens=200, cost_usd=0.02)
        self.assertEqual(b.tokens_used, 300)
        self.assertAlmostEqual(b.cost_usd, 0.03)


class TestUsageTracker(unittest.TestCase):
    """Cumulative AI usage tracker."""

    def test_record_accumulates(self):
        ut = UsageTracker()
        ut.record("Executor", calls=2, tokens=500, cost_usd=0.01)
        ut.record("PatchReviewer", calls=1, tokens=200, cost_usd=0.005)
        self.assertEqual(ut.total_calls, 3)
        self.assertEqual(ut.total_tokens, 700)
        self.assertAlmostEqual(ut.total_cost_usd, 0.015)

    def test_per_agent_breakdown(self):
        ut = UsageTracker()
        ut.record("Executor", calls=2, tokens=500)
        ut.record("PatchReviewer", calls=1, tokens=200)
        ut.record("Executor", calls=1, tokens=100)
        self.assertEqual(ut.by_agent["Executor"]["calls"], 3)
        self.assertEqual(ut.by_agent["Executor"]["tokens"], 600)
        self.assertEqual(ut.by_agent["PatchReviewer"]["calls"], 1)

    def test_add_deferred(self):
        ut = UsageTracker()
        ut.add_deferred(3)
        ut.add_deferred(2)
        self.assertEqual(ut.total_deferred, 5)

    def test_record_step_captures_deferred(self):
        ut = UsageTracker()
        budget = StepBudget(max_calls=2)
        budget.consume(2)
        budget.consume(3)  # deferred
        ut.record_step(budget)
        self.assertEqual(ut.total_deferred, 3)

    def test_serialization_roundtrip(self):
        ut = UsageTracker()
        ut.record("Executor", calls=5, tokens=1000, cost_usd=0.05)
        ut.record("PatchReviewer", calls=2, tokens=400, cost_usd=0.02)
        ut.add_deferred(3)

        data = ut.to_dict()
        ut2 = UsageTracker.from_dict(data)

        self.assertEqual(ut2.total_calls, 7)
        self.assertEqual(ut2.total_tokens, 1400)
        self.assertAlmostEqual(ut2.total_cost_usd, 0.07)
        self.assertEqual(ut2.total_deferred, 3)
        self.assertEqual(ut2.by_agent["Executor"]["calls"], 5)
        self.assertEqual(ut2.by_agent["PatchReviewer"]["tokens"], 400)

    def test_from_dict_empty(self):
        ut = UsageTracker.from_dict({})
        self.assertEqual(ut.total_calls, 0)
        self.assertEqual(ut.total_tokens, 0)
        self.assertAlmostEqual(ut.total_cost_usd, 0.0)
        self.assertEqual(ut.total_deferred, 0)
        self.assertEqual(ut.by_agent, {})

    def test_cost_rounding(self):
        ut = UsageTracker()
        ut.record("X", cost_usd=0.1 + 0.2)
        data = ut.to_dict()
        self.assertEqual(data["total_cost_usd"], round(0.3, 6))


class TestBackwardCompatUsageState(unittest.TestCase):
    """Older state files without usage_state get valid defaults."""

    def test_missing_usage_state_gets_defaults(self):
        payload = {"meta_history": [], "safety_state": {}, "recovery_state": {}}
        apply_backward_compat_defaults(payload)
        us = payload["usage_state"]
        self.assertEqual(us["total_calls"], 0)
        self.assertEqual(us["total_tokens"], 0)
        self.assertAlmostEqual(us["total_cost_usd"], 0.0)
        self.assertEqual(us["total_deferred"], 0)
        self.assertEqual(us["by_agent"], {})

    def test_existing_usage_state_preserved(self):
        payload = {
            "meta_history": [], "safety_state": {}, "recovery_state": {},
            "usage_state": {
                "total_calls": 42, "total_tokens": 9000,
                "total_cost_usd": 1.23, "total_deferred": 5,
                "by_agent": {"Executor": {"calls": 42, "tokens": 9000, "cost_usd": 1.23}},
            },
        }
        apply_backward_compat_defaults(payload)
        self.assertEqual(payload["usage_state"]["total_calls"], 42)


class TestAgentStatsUsageSection(unittest.TestCase):
    """agent_stats() includes usage section."""

    def test_usage_section_present(self):
        state = {
            "dag": {},
            "step": 10,
            "healed_total": 0,
            "meta_history": [],
            "safety_state": {},
        }
        stats = agent_stats(state)
        self.assertIn("usage", stats)
        self.assertEqual(stats["usage"]["total_calls"], 0)

    def test_usage_section_with_data(self):
        state = {
            "dag": {},
            "step": 10,
            "healed_total": 0,
            "meta_history": [],
            "safety_state": {},
            "usage_state": {
                "total_calls": 15,
                "total_tokens": 3000,
                "total_cost_usd": 0.1,
                "total_deferred": 2,
                "by_agent": {
                    "Executor": {"calls": 10, "tokens": 2000, "cost_usd": 0.07},
                    "PatchReviewer": {"calls": 5, "tokens": 1000, "cost_usd": 0.03},
                },
            },
        }
        stats = agent_stats(state)
        self.assertEqual(stats["usage"]["total_calls"], 15)
        self.assertEqual(stats["usage"]["total_tokens"], 3000)
        self.assertEqual(len(stats["usage"]["by_agent"]), 2)


if __name__ == "__main__":
    unittest.main()
