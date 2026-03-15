"""Tests for utils/budget.py — UsageTracker and StepBudget classes."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.budget import StepBudget, UsageTracker


class TestStepBudgetInit(unittest.TestCase):
    """Test StepBudget initialization and basic properties."""

    def test_init_defaults(self):
        budget = StepBudget(step=1)
        self.assertEqual(budget.step, 1)
        self.assertEqual(budget.tokens_in, 0)
        self.assertEqual(budget.tokens_out, 0)
        self.assertEqual(budget.total_tokens, 0)
        self.assertEqual(budget.cost_usd, 0.0)
        self.assertEqual(budget.api_calls, 0)
        self.assertEqual(budget.deferred, 0)

    def test_init_with_values(self):
        budget = StepBudget(
            step=2,
            tokens_in=100,
            tokens_out=50,
            total_tokens=150,
            cost_usd=0.003,
            api_calls=1,
            deferred=2,
        )
        self.assertEqual(budget.step, 2)
        self.assertEqual(budget.tokens_in, 100)
        self.assertEqual(budget.tokens_out, 50)
        self.assertEqual(budget.total_tokens, 150)
        self.assertEqual(budget.cost_usd, 0.003)
        self.assertEqual(budget.api_calls, 1)
        self.assertEqual(budget.deferred, 2)


class TestStepBudgetAddCall(unittest.TestCase):
    """Test StepBudget.add_call() method."""

    def test_add_call_single(self):
        budget = StepBudget(step=1)
        budget.add_call(tokens_in=100, tokens_out=50, cost_usd=0.003)
        self.assertEqual(budget.tokens_in, 100)
        self.assertEqual(budget.tokens_out, 50)
        self.assertEqual(budget.total_tokens, 150)
        self.assertEqual(budget.cost_usd, 0.003)
        self.assertEqual(budget.api_calls, 1)

    def test_add_call_multiple(self):
        budget = StepBudget(step=1)
        budget.add_call(tokens_in=100, tokens_out=50, cost_usd=0.003)
        budget.add_call(tokens_in=200, tokens_out=100, cost_usd=0.006)
        self.assertEqual(budget.tokens_in, 300)
        self.assertEqual(budget.tokens_out, 150)
        self.assertEqual(budget.total_tokens, 450)
        self.assertAlmostEqual(budget.cost_usd, 0.009, places=6)
        self.assertEqual(budget.api_calls, 2)

    def test_add_call_zero_tokens(self):
        budget = StepBudget(step=1)
        budget.add_call(tokens_in=0, tokens_out=0, cost_usd=0.0)
        self.assertEqual(budget.total_tokens, 0)
        self.assertEqual(budget.cost_usd, 0.0)
        self.assertEqual(budget.api_calls, 1)


class TestStepBudgetSerialization(unittest.TestCase):
    """Test StepBudget to_dict/from_dict."""

    def test_to_dict_roundtrip(self):
        original = StepBudget(
            step=5,
            tokens_in=150,
            tokens_out=75,
            total_tokens=225,
            cost_usd=0.005,
            api_calls=2,
            deferred=1,
        )
        data = original.to_dict()
        restored = StepBudget.from_dict(data)
        self.assertEqual(restored.step, 5)
        self.assertEqual(restored.tokens_in, 150)
        self.assertEqual(restored.tokens_out, 75)
        self.assertEqual(restored.total_tokens, 225)
        self.assertAlmostEqual(restored.cost_usd, 0.005, places=6)
        self.assertEqual(restored.api_calls, 2)
        self.assertEqual(restored.deferred, 1)

    def test_from_dict_partial_data(self):
        data = {"step": 3, "tokens_in": 50}
        restored = StepBudget.from_dict(data)
        self.assertEqual(restored.step, 3)
        self.assertEqual(restored.tokens_in, 50)
        self.assertEqual(restored.tokens_out, 0)


class TestUsageTrackerInit(unittest.TestCase):
    """Test UsageTracker initialization."""

    def test_init_defaults(self):
        tracker = UsageTracker()
        self.assertEqual(tracker.total_cost_usd, 0.0)
        self.assertEqual(tracker.total_tokens, 0)
        self.assertEqual(tracker.total_api_calls, 0)
        self.assertEqual(tracker.total_deferred, 0)
        self.assertEqual(len(tracker.by_step), 0)
        self.assertEqual(len(tracker.by_agent), 0)

    def test_init_with_budget_limits(self):
        tracker = UsageTracker(
            max_cost_usd=10.0,
            max_total_tokens=50000,
            max_api_calls_per_step=5,
        )
        self.assertEqual(tracker.max_cost_usd, 10.0)
        self.assertEqual(tracker.max_total_tokens, 50000)
        self.assertEqual(tracker.max_api_calls_per_step, 5)


class TestUsageTrackerRecordUsage(unittest.TestCase):
    """Test UsageTracker.record_usage() method."""

    def test_record_single_usage(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50)
        self.assertEqual(tracker.total_tokens, 150)
        self.assertGreater(tracker.total_cost_usd, 0.0)
        self.assertEqual(tracker.total_api_calls, 1)
        self.assertIn(1, tracker.by_step)

    def test_record_multiple_steps(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50)
        tracker.record_usage(step=2, tokens_in=200, tokens_out=100)
        self.assertEqual(tracker.total_tokens, 450)
        self.assertEqual(tracker.total_api_calls, 2)
        self.assertEqual(len(tracker.by_step), 2)

    def test_record_with_agent_breakdown(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50, agent="executor")
        tracker.record_usage(step=1, tokens_in=50, tokens_out=25, agent="reviewer")
        self.assertEqual(tracker.total_api_calls, 2)
        self.assertIn("executor", tracker.by_agent)
        self.assertIn("reviewer", tracker.by_agent)
        self.assertEqual(tracker.by_agent["executor"]["calls"], 1)
        self.assertEqual(tracker.by_agent["reviewer"]["calls"], 1)

    def test_record_with_custom_model_pricing(self):
        tracker = UsageTracker()
        # Haiku is cheaper
        tracker.record_usage(
            step=1,
            tokens_in=1000,
            tokens_out=500,
            model="claude-haiku-4-5-20251001",
        )
        haiku_cost = tracker.total_cost_usd

        tracker2 = UsageTracker()
        # Sonnet is more expensive
        tracker2.record_usage(
            step=1,
            tokens_in=1000,
            tokens_out=500,
            model="claude-sonnet-4-6",
        )
        sonnet_cost = tracker2.total_cost_usd

        self.assertLess(haiku_cost, sonnet_cost)

    def test_record_zero_tokens(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=0, tokens_out=0)
        self.assertEqual(tracker.total_tokens, 0)
        self.assertEqual(tracker.total_cost_usd, 0.0)
        self.assertEqual(tracker.total_api_calls, 1)


class TestUsageTrackerCheckBudget(unittest.TestCase):
    """Test UsageTracker.check_budget() validation."""

    def test_check_budget_ok_no_limits(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=1000, tokens_out=500)
        ok, reason = tracker.check_budget()
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_check_budget_ok_under_cost_limit(self):
        tracker = UsageTracker(max_cost_usd=100.0)
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50)
        ok, reason = tracker.check_budget()
        self.assertTrue(ok)

    def test_check_budget_exceeded_cost(self):
        tracker = UsageTracker(max_cost_usd=0.001)
        tracker.record_usage(step=1, tokens_in=10000, tokens_out=10000)
        ok, reason = tracker.check_budget()
        self.assertFalse(ok)
        self.assertIn("Cost budget exceeded", reason)

    def test_check_budget_exceeded_tokens(self):
        tracker = UsageTracker(max_total_tokens=100)
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50)
        ok, reason = tracker.check_budget()
        self.assertFalse(ok)
        self.assertIn("Token budget exceeded", reason)

    def test_check_budget_exceeded_api_calls_per_step(self):
        tracker = UsageTracker(max_api_calls_per_step=2)
        tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        ok, reason = tracker.check_budget()
        self.assertFalse(ok)
        self.assertIn("API calls budget exceeded", reason)

    def test_check_budget_under_limit_single_step(self):
        tracker = UsageTracker(max_api_calls_per_step=5)
        tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        ok, reason = tracker.check_budget()
        self.assertTrue(ok)

    def test_check_budget_multiple_steps_limits_per_step(self):
        tracker = UsageTracker(max_api_calls_per_step=2)
        # Step 1: 2 calls (OK)
        tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        # Step 2: 3 calls (FAIL)
        tracker.record_usage(step=2, tokens_in=10, tokens_out=10)
        tracker.record_usage(step=2, tokens_in=10, tokens_out=10)
        tracker.record_usage(step=2, tokens_in=10, tokens_out=10)
        ok, reason = tracker.check_budget()
        self.assertFalse(ok)
        self.assertIn("step 2", reason)


class TestUsageTrackerSummaries(unittest.TestCase):
    """Test UsageTracker summary methods."""

    def test_step_summary_empty(self):
        tracker = UsageTracker()
        summary = tracker.step_summary(1)
        self.assertEqual(summary["step"], 1)
        self.assertEqual(summary["tokens_in"], 0)
        self.assertEqual(summary["tokens_out"], 0)
        self.assertEqual(summary["total_tokens"], 0)
        self.assertEqual(summary["cost_usd"], 0.0)
        self.assertEqual(summary["api_calls"], 0)

    def test_step_summary_recorded(self):
        tracker = UsageTracker()
        tracker.record_usage(step=2, tokens_in=150, tokens_out=75)
        summary = tracker.step_summary(2)
        self.assertEqual(summary["step"], 2)
        self.assertEqual(summary["tokens_in"], 150)
        self.assertEqual(summary["tokens_out"], 75)
        self.assertEqual(summary["total_tokens"], 225)
        self.assertGreater(summary["cost_usd"], 0.0)
        self.assertEqual(summary["api_calls"], 1)

    def test_total_summary_empty(self):
        tracker = UsageTracker(max_cost_usd=10.0, max_total_tokens=1000)
        summary = tracker.total_summary()
        self.assertEqual(summary["total_cost_usd"], 0.0)
        self.assertEqual(summary["total_tokens"], 0)
        self.assertEqual(summary["total_api_calls"], 0)
        self.assertEqual(summary["max_cost_usd"], 10.0)
        self.assertEqual(summary["max_total_tokens"], 1000)
        self.assertTrue(summary["budget_ok"])

    def test_total_summary_with_usage(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50, agent="phase1")
        tracker.record_usage(step=2, tokens_in=200, tokens_out=100, agent="phase2")
        summary = tracker.total_summary()
        self.assertEqual(summary["total_tokens"], 450)
        self.assertEqual(summary["total_api_calls"], 2)
        self.assertIn("phase1", summary["by_agent"])
        self.assertIn("phase2", summary["by_agent"])
        self.assertEqual(summary["by_agent"]["phase1"]["calls"], 1)
        self.assertEqual(summary["by_agent"]["phase2"]["calls"], 1)

    def test_total_summary_includes_deferred(self):
        tracker = UsageTracker()
        tracker.total_deferred = 5
        summary = tracker.total_summary()
        self.assertEqual(summary["total_deferred"], 5)


class TestUsageTrackerReset(unittest.TestCase):
    """Test UsageTracker.reset() method."""

    def test_reset_clears_all(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50, agent="test")
        tracker.total_deferred = 2
        # Verify data is present
        self.assertGreater(tracker.total_tokens, 0)
        self.assertGreater(len(tracker.by_step), 0)
        self.assertGreater(len(tracker.by_agent), 0)
        # Reset
        tracker.reset()
        # Verify all cleared
        self.assertEqual(tracker.total_cost_usd, 0.0)
        self.assertEqual(tracker.total_tokens, 0)
        self.assertEqual(tracker.total_api_calls, 0)
        self.assertEqual(tracker.total_deferred, 0)
        self.assertEqual(len(tracker.by_step), 0)
        self.assertEqual(len(tracker.by_agent), 0)

    def test_reset_preserves_limits(self):
        tracker = UsageTracker(
            max_cost_usd=5.0,
            max_total_tokens=10000,
            max_api_calls_per_step=10,
        )
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50)
        tracker.reset()
        self.assertEqual(tracker.max_cost_usd, 5.0)
        self.assertEqual(tracker.max_total_tokens, 10000)
        self.assertEqual(tracker.max_api_calls_per_step, 10)


class TestUsageTrackerSerialization(unittest.TestCase):
    """Test UsageTracker to_dict/from_dict persistence."""

    def test_to_dict_basic(self):
        tracker = UsageTracker(max_cost_usd=5.0)
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50, agent="test")
        data = tracker.to_dict()
        self.assertEqual(data["max_cost_usd"], 5.0)
        self.assertEqual(data["total_tokens"], 150)
        self.assertEqual(data["total_api_calls"], 1)
        self.assertIn("1", data["by_step"])
        self.assertIn("test", data["by_agent"])

    def test_from_dict_basic(self):
        data = {
            "max_cost_usd": 10.0,
            "max_total_tokens": 50000,
            "max_api_calls_per_step": 5,
            "total_cost_usd": 0.003,
            "total_tokens": 150,
            "total_api_calls": 1,
            "total_deferred": 0,
            "by_step": {
                "1": {
                    "step": 1,
                    "tokens_in": 100,
                    "tokens_out": 50,
                    "total_tokens": 150,
                    "cost_usd": 0.003,
                    "api_calls": 1,
                    "deferred": 0,
                }
            },
            "by_agent": {
                "executor": {
                    "calls": 1,
                    "tokens": 150,
                    "cost_usd": 0.003,
                }
            },
        }
        tracker = UsageTracker.from_dict(data)
        self.assertEqual(tracker.max_cost_usd, 10.0)
        self.assertEqual(tracker.total_tokens, 150)
        self.assertEqual(tracker.total_api_calls, 1)
        self.assertIn(1, tracker.by_step)
        self.assertIn("executor", tracker.by_agent)

    def test_roundtrip_full_session(self):
        original = UsageTracker(max_cost_usd=50.0)
        original.record_usage(step=1, tokens_in=100, tokens_out=50, agent="p1")
        original.record_usage(step=1, tokens_in=100, tokens_out=50, agent="p2")
        original.record_usage(step=2, tokens_in=200, tokens_out=100, agent="p1")
        original.total_deferred = 3

        data = original.to_dict()
        restored = UsageTracker.from_dict(data)

        self.assertEqual(restored.max_cost_usd, original.max_cost_usd)
        self.assertEqual(restored.total_tokens, original.total_tokens)
        self.assertEqual(restored.total_api_calls, original.total_api_calls)
        self.assertEqual(restored.total_deferred, 3)
        self.assertEqual(len(restored.by_step), 2)
        self.assertEqual(len(restored.by_agent), 2)
        self.assertAlmostEqual(
            restored.total_cost_usd, original.total_cost_usd, places=6
        )

    def test_from_dict_missing_fields_defaults(self):
        data = {}
        tracker = UsageTracker.from_dict(data)
        self.assertEqual(tracker.total_tokens, 0)
        self.assertEqual(tracker.total_cost_usd, 0.0)
        self.assertEqual(tracker.total_api_calls, 0)

    def test_from_dict_partial_by_agent(self):
        data = {
            "by_agent": {
                "agent1": {
                    "calls": 2,
                    "cost_usd": 0.005,
                    # missing "tokens"
                }
            }
        }
        tracker = UsageTracker.from_dict(data)
        self.assertEqual(tracker.by_agent["agent1"]["calls"], 2)
        self.assertEqual(tracker.by_agent["agent1"]["cost_usd"], 0.005)
        self.assertEqual(tracker.by_agent["agent1"]["tokens"], 0)


class TestUsageTrackerZeroLimitsMeansUnlimited(unittest.TestCase):
    """Test that 0 limits mean unlimited."""

    def test_zero_cost_limit_is_unlimited(self):
        tracker = UsageTracker(max_cost_usd=0)
        tracker.record_usage(step=1, tokens_in=100000, tokens_out=100000)
        ok, reason = tracker.check_budget()
        self.assertTrue(ok)

    def test_zero_token_limit_is_unlimited(self):
        tracker = UsageTracker(max_total_tokens=0)
        tracker.record_usage(step=1, tokens_in=100000, tokens_out=100000)
        ok, reason = tracker.check_budget()
        self.assertTrue(ok)

    def test_zero_api_calls_limit_is_unlimited(self):
        tracker = UsageTracker(max_api_calls_per_step=0)
        for _ in range(100):
            tracker.record_usage(step=1, tokens_in=10, tokens_out=10)
        ok, reason = tracker.check_budget()
        self.assertTrue(ok)


class TestUsageTrackerAgentAggregation(unittest.TestCase):
    """Test per-agent aggregation and reporting."""

    def test_same_agent_multiple_calls(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=50, tokens_out=25, agent="executor")
        tracker.record_usage(step=1, tokens_in=50, tokens_out=25, agent="executor")
        tracker.record_usage(step=2, tokens_in=100, tokens_out=50, agent="executor")
        self.assertEqual(tracker.by_agent["executor"]["calls"], 3)
        self.assertEqual(tracker.by_agent["executor"]["tokens"], 300)

    def test_multiple_agents_isolated(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50, agent="a")
        tracker.record_usage(step=1, tokens_in=200, tokens_out=100, agent="b")
        self.assertEqual(tracker.by_agent["a"]["calls"], 1)
        self.assertEqual(tracker.by_agent["a"]["tokens"], 150)
        self.assertEqual(tracker.by_agent["b"]["calls"], 1)
        self.assertEqual(tracker.by_agent["b"]["tokens"], 300)

    def test_no_agent_not_recorded_in_by_agent(self):
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50)
        self.assertEqual(len(tracker.by_agent), 0)
        # but still counted in totals
        self.assertEqual(tracker.total_api_calls, 1)


if __name__ == "__main__":
    unittest.main()
