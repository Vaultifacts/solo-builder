"""
core/dag_transitions.py
DAG status transition and roll-up helpers extracted from solo_builder_cli.py.

Pure functions operating on DAG dicts — no side effects beyond mutation
of the DAG structure passed in.

Used by: Executor, Verifier, SelfHealer, _cmd_verify, _cmd_heal.
"""

from typing import Dict, List, Tuple


# ── Status constants ─────────────────────────────────────────────────────────
VALID_STATUSES = {"Pending", "Running", "Review", "Verified", "Failed"}
VALID_SHADOWS = {"Pending", "Done"}


# ── History recording ────────────────────────────────────────────────────────

def record_history(st_data: Dict, new_status: str, step: int) -> None:
    """Append a status transition to the subtask's history timeline."""
    st_data.setdefault("history", []).append({"status": new_status, "step": step})


# ── Roll-up helpers ──────────────────────────────────────────────────────────

def update_branch_status(dag: Dict, task_name: str, branch_name: str) -> None:
    """
    Set branch status to Verified if all subtasks are Verified.

    This is the Executor's roll-up: it only promotes to Verified, never
    demotes. The Verifier class handles the full consistency sweep.
    """
    sts = dag[task_name]["branches"][branch_name]["subtasks"]
    if all(s.get("status") == "Verified" for s in sts.values()):
        dag[task_name]["branches"][branch_name]["status"] = "Verified"


def update_task_status(dag: Dict, task_name: str) -> None:
    """
    Set task status based on branch statuses:
    - All branches Verified → task Verified
    - Any branch Running → task Running
    """
    branches = dag[task_name]["branches"]
    if all(b.get("status") == "Verified" for b in branches.values()):
        dag[task_name]["status"] = "Verified"
    elif any(b.get("status") == "Running" for b in branches.values()):
        dag[task_name]["status"] = "Running"


def roll_up(dag: Dict, task_name: str, branch_name: str) -> None:
    """Convenience: update branch then task status after a subtask change."""
    update_branch_status(dag, task_name, branch_name)
    update_task_status(dag, task_name)


# ── Dependency eligibility ───────────────────────────────────────────────────

def deps_met(dag: Dict, task_name: str) -> bool:
    """Return True if every task this task depends on is Verified."""
    for dep in dag.get(task_name, {}).get("depends_on", []):
        if dag.get(dep, {}).get("status") != "Verified":
            return False
    return True


# ── Verifier roll-up (full consistency sweep) ────────────────────────────────

def verify_rollup(dag: Dict) -> List[str]:
    """
    Scan all branch and task statuses; correct any inconsistencies.
    Returns list of correction messages.

    This is the Verifier's logic: it handles both promotion (Pending → Running,
    Pending/Running → Verified) and is run as a full sweep after each step.
    """
    fixes: List[str] = []
    for task_name, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            sts = branch_data.get("subtasks", {})
            all_v = all(s.get("status") == "Verified" for s in sts.values())
            any_r = any(s.get("status") == "Running" for s in sts.values())
            cur_branch_status = branch_data.get("status", "Pending")

            if all_v and cur_branch_status != "Verified":
                branch_data["status"] = "Verified"
                fixes.append(f"Branch {branch_name}: Pending/Running → Verified")
            elif any_r and cur_branch_status == "Pending":
                branch_data["status"] = "Running"
                fixes.append(f"Branch {branch_name}: Pending → Running")

        branches = task_data.get("branches", {})
        all_bv = all(b.get("status") == "Verified" for b in branches.values())
        any_br = any(b.get("status") == "Running" for b in branches.values())
        cur_t = task_data.get("status", "Pending")

        if all_bv and cur_t != "Verified":
            task_data["status"] = "Verified"
            fixes.append(f"Task {task_name}: → Verified")
        elif any_br and cur_t == "Pending":
            task_data["status"] = "Running"
            fixes.append(f"Task {task_name}: → Running")

    return fixes


# ── Stall detection ──────────────────────────────────────────────────────────

def find_stalled(dag: Dict, step: int,
                 stall_threshold: int) -> List[Tuple[str, str, str, int]]:
    """
    Return list of (task, branch, subtask, staleness) for stalled subtasks.

    Only checks status == "Running" (NOT Review).
    """
    stalled: List[Tuple[str, str, str, int]] = []
    for task_name, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_data.get("status") == "Running":
                    age = step - st_data.get("last_update", 0)
                    if age >= stall_threshold:
                        stalled.append((task_name, branch_name, st_name, age))
    return stalled
