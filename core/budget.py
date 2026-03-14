"""
core/budget.py
Cumulative AI usage tracker for cross-step accounting.

Tracks total AI calls, tokens, estimated cost, and deferred work
across the lifetime of a run, with per-agent breakdowns.

State is persisted via the existing save/load mechanism in
solo_builder_cli.py and is backward-compatible with older state
files (defaults to zeros when absent).
"""

from typing import Any, Dict


class UsageTracker:
    """
    Accumulates AI usage metrics across pipeline steps.

    Usage:
        tracker = UsageTracker()
        tracker.record("PatchReviewer", calls=1, tokens=350, cost_usd=0.002)
        tracker.record("Executor", calls=3, tokens=1200, cost_usd=0.008)
        tracker.add_deferred(2)
        state = tracker.to_dict()  # persist
        tracker2 = UsageTracker.from_dict(state)  # restore
    """

    def __init__(self) -> None:
        self.total_calls: int = 0
        self.total_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.total_deferred: int = 0
        self.by_agent: Dict[str, Dict[str, Any]] = {}

    def record(
        self,
        agent: str,
        calls: int = 0,
        tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record usage from a single agent invocation."""
        self.total_calls += calls
        self.total_tokens += tokens
        self.total_cost_usd += cost_usd

        if agent not in self.by_agent:
            self.by_agent[agent] = {
                "calls": 0,
                "tokens": 0,
                "cost_usd": 0.0,
            }
        entry = self.by_agent[agent]
        entry["calls"] += calls
        entry["tokens"] += tokens
        entry["cost_usd"] += cost_usd

    def add_deferred(self, count: int) -> None:
        """Record deferred work items from a step."""
        self.total_deferred += count

    def record_step(self, budget) -> None:
        """
        Roll up a completed StepBudget into cumulative totals.

        Call this at the end of each step after all phases have run.
        The per-agent detail should be recorded via record() during
        the step; this captures step-level deferred counts.
        """
        self.total_deferred += budget.deferred

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for state persistence."""
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_deferred": self.total_deferred,
            "by_agent": {
                agent: {
                    "calls": v["calls"],
                    "tokens": v["tokens"],
                    "cost_usd": round(v["cost_usd"], 6),
                }
                for agent, v in self.by_agent.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageTracker":
        """Restore from persisted state dict."""
        tracker = cls()
        tracker.total_calls = data.get("total_calls", 0)
        tracker.total_tokens = data.get("total_tokens", 0)
        tracker.total_cost_usd = data.get("total_cost_usd", 0.0)
        tracker.total_deferred = data.get("total_deferred", 0)
        tracker.by_agent = {
            agent: {
                "calls": v.get("calls", 0),
                "tokens": v.get("tokens", 0),
                "cost_usd": v.get("cost_usd", 0.0),
            }
            for agent, v in data.get("by_agent", {}).items()
        }
        return tracker
