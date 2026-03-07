"""Planner agent — prioritizes subtasks by computed risk score."""
from typing import Dict, List, Tuple


class Planner:
    """Prioritizes subtasks by computed risk score. Higher = more urgent."""

    def __init__(self, stall_threshold: int) -> None:
        self.stall_threshold = stall_threshold
        # Meta-optimizer adjustable weights
        self.w_stall    = 1.0
        self.w_staleness = 1.0
        self.w_shadow   = 1.0

    # ── Public ──────────────────────────────────────────────────────────────
    def prioritize(
        self, dag: Dict, step: int
    ) -> List[Tuple[str, str, str, int]]:
        """
        Return a sorted list of (task, branch, subtask, risk_score) for all
        non-Verified subtasks, highest risk first.
        """
        candidates: List[Tuple[str, str, str, int]] = []
        for task_name, task_data in dag.items():
            if not self._deps_met(dag, task_name):
                continue
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    if st_data.get("status") not in ("Pending", "Running"):
                        continue
                    risk = self._risk(st_data, step)
                    candidates.append((task_name, branch_name, st_name, risk))
        candidates.sort(key=lambda x: x[3], reverse=True)
        return candidates

    def _deps_met(self, dag: Dict, task_name: str) -> bool:
        """Return True if every task this task depends on is Verified."""
        for dep in dag.get(task_name, {}).get("depends_on", []):
            if dag.get(dep, {}).get("status") != "Verified":
                return False
        return True

    def adjust_weights(self, key: str, delta: float) -> None:
        """Hook for MetaOptimizer to tune heuristic weights."""
        if key == "stall_risk":
            self.w_stall    = max(0.1, self.w_stall    + delta)
        elif key == "staleness":
            self.w_staleness = max(0.1, self.w_staleness + delta)
        elif key == "shadow":
            self.w_shadow   = max(0.1, self.w_shadow   + delta)

    # ── Private ─────────────────────────────────────────────────────────────
    def _risk(self, st_data: Dict, step: int) -> int:
        staleness = step - st_data.get("last_update", 0)
        status    = st_data.get("status", "Pending")

        if status == "Running":
            # Base of 1000 guarantees Running always outranks Pending regardless
            # of how long Pending subtasks have been waiting.
            risk = int(1000 * self.w_stall)
            if staleness >= self.stall_threshold:
                # Extra urgency for stalled — bump above normal Running
                risk += int(500 * self.w_stall) + staleness * 20
            else:
                risk += int(staleness * 10 * self.w_staleness)
        elif status == "Pending":
            risk = int(staleness * 8 * self.w_staleness) if staleness > 2 else 0
            if st_data.get("shadow") == "Done":
                # Shadow claims Done but status is Pending → extra urgency
                risk += int(50 * self.w_shadow)
        else:
            risk = 0

        return risk
