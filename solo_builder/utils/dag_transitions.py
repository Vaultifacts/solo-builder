"""
utils/dag_transitions.py
DAG status transition and roll-up helpers.

Pure functions operating on DAG dicts — no side effects beyond mutation
of the DAG structure passed in.

Used by: Executor, Verifier, SelfHealer, CLI commands.

Status state machine:
  Pending → Running
  Running → Verified, Running → Review, Running → Pending (heal)
  Review → Verified, Review → Pending (reject)
  Verified is terminal (no transitions out)
  Failed (legacy, not currently used in transitions)

Critical fix for Review status:
  - A branch with ANY subtask in Review should stay Running (not get stuck)
  - verify_rollup() branch logic: Verified ONLY when ALL subtasks Verified
  - Review blocks branch promotion like Running does
"""

from typing import Dict, List, Tuple, Optional


# ── Status constants ─────────────────────────────────────────────────────────
VALID_STATUSES = {"Pending", "Running", "Review", "Verified", "Failed"}
VALID_SHADOWS = {"Pending", "Done"}

# State machine: valid transitions
ALLOWED_TRANSITIONS = {
    "Pending": {"Running"},
    "Running": {"Verified", "Review", "Pending"},  # Pending for healing
    "Review": {"Verified", "Pending"},
    "Verified": set(),  # Terminal
    "Failed": {"Pending"},
}


# ── Transition validation ────────────────────────────────────────────────────

def is_valid_transition(current: str, target: str) -> bool:
    """
    Check if a status transition is allowed.

    Args:
        current: Current status (e.g. "Running")
        target: Target status (e.g. "Verified")

    Returns:
        True if transition is allowed, False otherwise
    """
    if current not in VALID_STATUSES or target not in VALID_STATUSES:
        return False
    return target in ALLOWED_TRANSITIONS.get(current, set())


# ── History recording ────────────────────────────────────────────────────────

def record_history(st_data: Dict, new_status: str, step: int) -> None:
    """
    Append a status transition to the subtask's history timeline.

    Args:
        st_data: Subtask dict to update
        new_status: New status value
        step: Current step number
    """
    st_data.setdefault("history", []).append({"status": new_status, "step": step})


def update_subtask_status(
    subtask_data: Dict, new_status: str, step: int
) -> Optional[str]:
    """
    Validate and update a subtask status, recording history.

    Args:
        subtask_data: Subtask dict to update
        new_status: Target status
        step: Current step number

    Returns:
        None if transition invalid, otherwise returns the new status
    """
    current = subtask_data.get("status", "Pending")
    if not is_valid_transition(current, new_status):
        return None
    subtask_data["status"] = new_status
    record_history(subtask_data, new_status, step)
    return new_status


# ── Roll-up helpers ──────────────────────────────────────────────────────────

def update_branch_status(dag: Dict, task_name: str, branch_name: str) -> None:
    """
    Set branch status to Verified if all subtasks are Verified.

    This is the Executor's incremental roll-up: it only promotes to Verified
    when ALL subtasks are Verified, never demotes.

    The Verifier class handles the full consistency sweep with Review logic.

    Args:
        dag: Full DAG dict
        task_name: Task ID
        branch_name: Branch ID
    """
    sts = dag[task_name]["branches"][branch_name]["subtasks"]
    if all(s.get("status") == "Verified" for s in sts.values()):
        dag[task_name]["branches"][branch_name]["status"] = "Verified"


def update_task_status(dag: Dict, task_name: str) -> None:
    """
    Set task status based on branch statuses:
      - All branches Verified → task Verified
      - Any branch Running/Review → task Running
      - Otherwise → task stays Pending or current status

    Args:
        dag: Full DAG dict
        task_name: Task ID
    """
    branches = dag[task_name]["branches"]
    if all(b.get("status") == "Verified" for b in branches.values()):
        dag[task_name]["status"] = "Verified"
    elif any(b.get("status") in ("Running", "Review") for b in branches.values()):
        dag[task_name]["status"] = "Running"


def roll_up(dag: Dict, task_name: str, branch_name: str) -> None:
    """
    Convenience: update branch then task status after a subtask change.

    Args:
        dag: Full DAG dict
        task_name: Task ID
        branch_name: Branch ID
    """
    update_branch_status(dag, task_name, branch_name)
    update_task_status(dag, task_name)


# ── Dependency eligibility ───────────────────────────────────────────────────

def deps_met(dag: Dict, task_name: str) -> bool:
    """
    Return True if every task this task depends on is Verified.

    Args:
        dag: Full DAG dict
        task_name: Task ID

    Returns:
        True if all dependencies are Verified, False otherwise
    """
    for dep in dag.get(task_name, {}).get("depends_on", []):
        if dag.get(dep, {}).get("status") != "Verified":
            return False
    return True


# ── Verifier roll-up (full consistency sweep) ────────────────────────────────

def verify_rollup(dag: Dict) -> List[str]:
    """
    Scan all branch and task statuses; correct any inconsistencies.

    This is the Verifier's logic: it handles both promotion (Pending → Running,
    Pending/Running → Verified) and is run as a full sweep after each step.

    CRITICAL FIX for Review status:
      - A branch with ANY subtask in Review should stay Running (not stuck)
      - Branch is Verified ONLY when ALL subtasks are Verified
      - Review blocks branch promotion like Running does

    Returns:
        List of correction messages describing what was fixed
    """
    fixes: List[str] = []

    for task_name, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            sts = branch_data.get("subtasks", {})

            # Compute branch readiness
            all_v = all(s.get("status") == "Verified" for s in sts.values())
            any_r = any(s.get("status") == "Running" for s in sts.values())
            any_review = any(s.get("status") == "Review" for s in sts.values())

            cur_branch_status = branch_data.get("status", "Pending")

            # Apply fixes:
            # 1. All Verified → branch Verified
            if all_v and cur_branch_status != "Verified":
                branch_data["status"] = "Verified"
                fixes.append(f"Branch {branch_name}: → Verified")

            # 2. Any Running or Review → branch Running (fixes stuck Review)
            elif (any_r or any_review) and cur_branch_status == "Pending":
                branch_data["status"] = "Running"
                fixes.append(f"Branch {branch_name}: Pending → Running")

            # 3. If some are Verified but any are Running/Review, stay Running
            elif (any_r or any_review) and cur_branch_status == "Verified":
                branch_data["status"] = "Running"
                fixes.append(
                    f"Branch {branch_name}: demoted (Review/Running present) → Running"
                )

        # Task roll-up: same logic
        branches = task_data.get("branches", {})
        all_bv = all(b.get("status") == "Verified" for b in branches.values())
        any_br = any(b.get("status") in ("Running", "Review") for b in branches.values())
        cur_t = task_data.get("status", "Pending")

        if all_bv and cur_t != "Verified":
            task_data["status"] = "Verified"
            fixes.append(f"Task {task_name}: → Verified")
        elif any_br and cur_t == "Pending":
            task_data["status"] = "Running"
            fixes.append(f"Task {task_name}: → Running")
        elif any_br and cur_t == "Verified":
            task_data["status"] = "Running"
            fixes.append(f"Task {task_name}: demoted → Running")

    return fixes


# ── Stall detection ──────────────────────────────────────────────────────────

def find_stalled(
    dag: Dict, step: int, stall_threshold: int
) -> List[Tuple[str, str, str, int]]:
    """
    Return list of (task, branch, subtask, staleness) for stalled subtasks.

    Only checks status == "Running" (NOT Review, which is human-controlled).

    Args:
        dag: Full DAG dict
        step: Current step number
        stall_threshold: Steps without update to trigger stall

    Returns:
        List of (task_name, branch_name, subtask_name, age_in_steps) tuples
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
