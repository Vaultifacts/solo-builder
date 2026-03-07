"""SelfHealer agent — detects stalled subtasks and resets them to Pending."""
import logging
from typing import Dict, List, Tuple

from utils.helper_functions import (
    add_memory_snapshot,
    CYAN, RESET,
    ALERT_PREDICTIVE,
)

logger = logging.getLogger("solo_builder")


class SelfHealer:
    """Detects subtasks stalled in Running state and resets them to Pending."""

    def __init__(self, stall_threshold: int) -> None:
        self.stall_threshold = stall_threshold
        self.healed_total    = 0

    def find_stalled(
        self, dag: Dict, step: int
    ) -> List[Tuple[str, str, str, int]]:
        """Return list of (task, branch, subtask, staleness) for stalled subtasks."""
        stalled: List[Tuple[str, str, str, int]] = []
        for task_name, task_data in dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    if st_data.get("status") == "Running":   # Review subtasks are not stalled
                        age = step - st_data.get("last_update", 0)
                        if age >= self.stall_threshold:
                            stalled.append((task_name, branch_name, st_name, age))
        return stalled

    def heal(
        self,
        dag: Dict,
        stalled: List[Tuple[str, str, str, int]],
        step: int,
        memory_store: Dict,
        alerts: List[str],
    ) -> int:
        """Reset stalled subtasks. Returns count healed."""
        count = 0
        for task_name, branch_name, st_name, age in stalled:
            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            st_data["status"]      = "Pending"
            st_data["shadow"]      = "Pending"
            st_data["last_update"] = step
            add_memory_snapshot(memory_store, branch_name, f"{st_name}_healed", step)
            alerts.append(
                f"  {ALERT_PREDICTIVE} {CYAN}{st_name}{RESET} "
                f"reset after {age} steps stalled"
            )
            count          += 1
            self.healed_total += 1
            logger.warning(
                "subtask_healed step=%d task=%s branch=%s subtask=%s stalled_steps=%d",
                step, task_name, branch_name, st_name, age,
            )
        return count
