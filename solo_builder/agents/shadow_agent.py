"""ShadowAgent — tracks expected states and detects/resolves conflicts."""
from typing import Dict, List, Tuple

from utils.helper_functions import add_memory_snapshot


class ShadowAgent:
    """
    Maintains an expected-state map and detects shadow/status conflicts.
    Conflict: shadow == "Done" but status != "Verified"  (or vice versa).
    """

    def __init__(self) -> None:
        self.expected: Dict[str, str] = {}   # st_name → expected status

    def update_expected(self, dag: Dict) -> None:
        """Rebuild expected state from current DAG."""
        for task_data in dag.values():
            for branch_data in task_data.get("branches", {}).values():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    self.expected[st_name] = st_data.get("status", "Pending")

    def detect_conflicts(self, dag: Dict) -> List[Tuple[str, str, str]]:
        """
        Return list of (task, branch, subtask) where shadow/status are inconsistent.
        """
        conflicts: List[Tuple[str, str, str]] = []
        for task_name, task_data in dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    shadow = st_data.get("shadow", "Pending")
                    status = st_data.get("status", "Pending")
                    # shadow Done but not Verified → stale shadow
                    if shadow == "Done" and status != "Verified":
                        conflicts.append((task_name, branch_name, st_name))
                    # Verified but shadow still Pending → shadow lag (non-critical but fixable)
                    elif status == "Verified" and shadow == "Pending":
                        conflicts.append((task_name, branch_name, st_name))
        return conflicts

    def resolve_conflict(
        self,
        dag: Dict,
        task_name: str,
        branch_name: str,
        st_name: str,
        step: int,
        memory_store: Dict,
    ) -> None:
        """Auto-resolve by aligning shadow with actual status."""
        st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
        status  = st_data.get("status", "Pending")
        if status == "Verified":
            st_data["shadow"] = "Done"
        else:
            st_data["shadow"] = "Pending"
        add_memory_snapshot(memory_store, branch_name, f"{st_name}_conflict_resolved", step)
