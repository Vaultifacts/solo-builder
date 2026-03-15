"""Verifier agent — enforces DAG status invariants."""
from typing import Dict, List

from utils.dag_transitions import verify_rollup


class Verifier:
    """Enforces DAG invariants: branch/task statuses must reflect subtask states."""

    def verify(self, dag: Dict) -> List[str]:
        """
        Scan all branch and task statuses; correct any inconsistencies.
        Returns list of correction messages.
        """
        fixes: List[str] = []
        for task_name, task_data in dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                sts              = branch_data.get("subtasks", {})
                all_v            = all(s.get("status") == "Verified" for s in sts.values())
                any_r            = any(s.get("status") == "Running"  for s in sts.values())
                cur_branch_status = branch_data.get("status", "Pending")

                if all_v and cur_branch_status != "Verified":
                    branch_data["status"] = "Verified"
                    fixes.append(f"Branch {branch_name}: Pending/Running → Verified")
                elif any_r and cur_branch_status == "Pending":
                    branch_data["status"] = "Running"
                    fixes.append(f"Branch {branch_name}: Pending → Running")

            branches = task_data.get("branches", {})
            all_bv   = all(b.get("status") == "Verified" for b in branches.values())
            any_br   = any(b.get("status") == "Running"  for b in branches.values())
            cur_t    = task_data.get("status", "Pending")

            if all_bv and cur_t != "Verified":
                task_data["status"] = "Verified"
                fixes.append(f"Task {task_name}: → Verified")
            elif any_br and cur_t == "Pending":
                task_data["status"] = "Running"
                fixes.append(f"Task {task_name}: → Running")

        verify_rollup(dag)
        return fixes
