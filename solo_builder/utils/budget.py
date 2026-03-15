"""Budget tracking for autonomous execution — tracks cost, tokens, and throughput.

Monitors cumulative API usage across steps, enforces budget limits, and provides
per-step and per-agent breakdowns. State persists via to_dict/from_dict for
cross-session accounting.

Usage:
    tracker = UsageTracker()
    tracker.record_usage(step=1, tokens_in=100, tokens_out=50, model="claude-sonnet-4-6")
    ok, reason = tracker.check_budget()
    if not ok:
        log.warning(f"Budget exhausted: {reason}")
    summary = tracker.total_summary()
    tracker.reset()
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
import os
import json as _json


# ── Default pricing per token (USD) ──────────────────────────────────────────
_DEFAULT_PRICING = {
    "claude-opus-4-1": {"input": 0.015 / 1000, "output": 0.075 / 1000},
    "claude-sonnet-4-6": {"input": 0.003 / 1000, "output": 0.015 / 1000},
    "claude-haiku-4-5-20251001": {"input": 0.00080 / 1000, "output": 0.004 / 1000},
}

_SOLO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG_PATH = os.path.join(_SOLO, "config", "settings.json")
try:
    with open(_CFG_PATH, encoding="utf-8") as _f:
        _CFG: dict = _json.load(_f)
except Exception:
    _CFG = {}


@dataclass
class StepBudget:
    """Per-step budget snapshot: tokens used, API calls, and cost."""

    step: int
    tokens_in: int = 0
    tokens_out: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    api_calls: int = 0
    deferred: int = 0  # Deferred subtasks from this step

    def add_call(
        self,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> None:
        """Record a single API call within this step."""
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.total_tokens += tokens_in + tokens_out
        self.cost_usd += cost_usd
        self.api_calls += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepBudget":
        """Restore from serialized state."""
        # Get all field names from the dataclass
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in field_names})


@dataclass
class UsageTracker:
    """
    Accumulates AI usage metrics across pipeline steps.

    Tracks total tokens, cost, API calls, and per-agent breakdown.
    Enforces budget limits and provides step/total summaries.

    Usage:
        tracker = UsageTracker()
        tracker.record_usage(step=1, tokens_in=100, tokens_out=50, model="claude-sonnet-4-6")
        ok, reason = tracker.check_budget()
        if not ok:
            log.warning(reason)
        summary = tracker.total_summary()
    """

    # Budget limits (0 = unlimited)
    max_cost_usd: float = field(
        default_factory=lambda: float(_CFG.get("BUDGET_MAX_COST", 0))
    )
    max_total_tokens: int = field(
        default_factory=lambda: int(_CFG.get("BUDGET_MAX_TOKENS", 0))
    )
    max_api_calls_per_step: int = field(
        default_factory=lambda: int(_CFG.get("BUDGET_MAX_API_CALLS_PER_STEP", 0))
    )

    # Accumulation
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_api_calls: int = 0
    total_deferred: int = 0
    by_step: Dict[int, StepBudget] = field(default_factory=dict)
    by_agent: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def record_usage(
        self,
        step: int,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: str = "claude-sonnet-4-6",
        agent: str = "",
    ) -> None:
        """
        Record a single API call.

        Args:
            step: Step number this call occurred in.
            tokens_in: Input tokens consumed.
            tokens_out: Output tokens generated.
            model: Model identifier for pricing lookup.
            agent: Optional agent/phase name for breakdown.
        """
        # Estimate cost from model pricing
        pricing = _DEFAULT_PRICING.get(model, _DEFAULT_PRICING["claude-sonnet-4-6"])
        cost_in = tokens_in * pricing["input"]
        cost_out = tokens_out * pricing["output"]
        cost_usd = cost_in + cost_out

        # Update totals
        self.total_tokens += tokens_in + tokens_out
        self.total_cost_usd += cost_usd
        self.total_api_calls += 1

        # Record per-step
        if step not in self.by_step:
            self.by_step[step] = StepBudget(step=step)
        self.by_step[step].add_call(tokens_in, tokens_out, cost_usd)

        # Record per-agent if provided
        if agent:
            if agent not in self.by_agent:
                self.by_agent[agent] = {
                    "calls": 0,
                    "tokens": 0,
                    "cost_usd": 0.0,
                }
            self.by_agent[agent]["calls"] += 1
            self.by_agent[agent]["tokens"] += tokens_in + tokens_out
            self.by_agent[agent]["cost_usd"] += cost_usd

    def check_budget(self) -> tuple[bool, str]:
        """
        Check if any budget limit is exceeded.

        Returns:
            (ok, reason) where ok=False if a limit is exceeded, reason explains why.
        """
        if self.max_cost_usd > 0 and self.total_cost_usd > self.max_cost_usd:
            return (
                False,
                f"Cost budget exceeded: ${self.total_cost_usd:.4f} > "
                f"${self.max_cost_usd:.4f}",
            )

        if self.max_total_tokens > 0 and self.total_tokens > self.max_total_tokens:
            return (
                False,
                f"Token budget exceeded: {self.total_tokens} > {self.max_total_tokens}",
            )

        if self.max_api_calls_per_step > 0:
            for step, budget in self.by_step.items():
                if budget.api_calls > self.max_api_calls_per_step:
                    return (
                        False,
                        f"API calls budget exceeded in step {step}: "
                        f"{budget.api_calls} > {self.max_api_calls_per_step}",
                    )

        return (True, "")

    def step_summary(self, step: int) -> Dict[str, Any]:
        """
        Get per-step aggregated usage.

        Args:
            step: Step number to summarize.

        Returns:
            Dict with step, tokens_in, tokens_out, total_tokens, cost_usd, api_calls.
        """
        if step not in self.by_step:
            return {
                "step": step,
                "tokens_in": 0,
                "tokens_out": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "api_calls": 0,
            }
        return self.by_step[step].to_dict()

    def total_summary(self) -> Dict[str, Any]:
        """
        Get overall accumulated usage.

        Returns:
            Dict with totals, limits, and per-agent breakdown.
        """
        return {
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "total_api_calls": self.total_api_calls,
            "total_deferred": self.total_deferred,
            "max_cost_usd": self.max_cost_usd,
            "max_total_tokens": self.max_total_tokens,
            "max_api_calls_per_step": self.max_api_calls_per_step,
            "budget_ok": self.check_budget()[0],
            "by_agent": {
                agent: {
                    "calls": v["calls"],
                    "tokens": v["tokens"],
                    "cost_usd": round(v["cost_usd"], 6),
                }
                for agent, v in self.by_agent.items()
            },
        }

    def reset(self) -> None:
        """Clear all accumulated usage."""
        self.total_cost_usd = 0.0
        self.total_tokens = 0
        self.total_api_calls = 0
        self.total_deferred = 0
        self.by_step.clear()
        self.by_agent.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "max_cost_usd": self.max_cost_usd,
            "max_total_tokens": self.max_total_tokens,
            "max_api_calls_per_step": self.max_api_calls_per_step,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "total_api_calls": self.total_api_calls,
            "total_deferred": self.total_deferred,
            "by_step": {
                str(step): budget.to_dict() for step, budget in self.by_step.items()
            },
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
        tracker = cls(
            max_cost_usd=data.get("max_cost_usd", 0.0),
            max_total_tokens=data.get("max_total_tokens", 0),
            max_api_calls_per_step=data.get("max_api_calls_per_step", 0),
        )
        tracker.total_cost_usd = data.get("total_cost_usd", 0.0)
        tracker.total_tokens = data.get("total_tokens", 0)
        tracker.total_api_calls = data.get("total_api_calls", 0)
        tracker.total_deferred = data.get("total_deferred", 0)

        # Restore per-step budgets
        for step_str, step_data in data.get("by_step", {}).items():
            step = int(step_str)
            tracker.by_step[step] = StepBudget.from_dict(step_data)

        # Restore per-agent breakdown
        for agent, agent_data in data.get("by_agent", {}).items():
            tracker.by_agent[agent] = {
                "calls": agent_data.get("calls", 0),
                "tokens": agent_data.get("tokens", 0),
                "cost_usd": agent_data.get("cost_usd", 0.0),
            }

        return tracker
