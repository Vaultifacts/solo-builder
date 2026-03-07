"""MetaOptimizer agent — records metrics, adapts Planner weights, forecasts."""
from typing import Dict, List, Optional

from utils.helper_functions import GREEN, RESET
from .planner import Planner


class MetaOptimizer:
    """
    Records per-step metrics and adapts Planner weights.
    Also generates completion forecasts.
    """

    def __init__(self) -> None:
        self._history: List[Dict[str, int]] = []
        self.heal_rate   = 0.0
        self.verify_rate = 0.0

    def record(self, healed: int, verified: int) -> None:
        self._history.append({"healed": healed, "verified": verified})
        window = min(10, len(self._history))
        recent = self._history[-window:]
        self.heal_rate   = sum(r["healed"]   for r in recent) / window
        self.verify_rate = sum(r["verified"] for r in recent) / window

    def optimize(self, planner: Planner) -> Optional[str]:
        """Return an optimisation note if any weight was adjusted."""
        if len(self._history) < 5:
            return None
        if self.heal_rate > 0.5:
            planner.adjust_weights("stall_risk", 0.1)
            return (f"Meta-Opt: ↑ stall_risk weight "
                    f"(heal_rate={self.heal_rate:.2f})")
        if self.verify_rate < 0.2:
            planner.adjust_weights("staleness", 0.1)
            return (f"Meta-Opt: ↑ staleness weight "
                    f"(verify_rate={self.verify_rate:.2f})")
        return None

    def forecast(self, dag: Dict) -> str:
        """Simple linear-extrapolation forecast for completion."""
        total = verified = 0
        for task_data in dag.values():
            for branch_data in task_data.get("branches", {}).values():
                for st_data in branch_data.get("subtasks", {}).values():
                    total    += 1
                    if st_data.get("status") == "Verified":
                        verified += 1
        if total == 0:
            return "N/A"
        if verified == total:
            return f"{GREEN}COMPLETE{RESET}"
        pct = verified / total * 100
        if self.verify_rate > 0:
            remaining     = total - verified
            eta           = remaining / (self.verify_rate + 1e-6)
            return f"~{eta:.0f} steps  ({pct:.0f}% done)"
        return f"{pct:.0f}% done  (ETA unavailable)"
