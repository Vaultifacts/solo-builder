"""
utils/state_integrity.py
State integrity checking and repair functions for Solo Builder.

Validates and repairs:
  - Invalid subtask statuses (resets to Pending)
  - Missing required subtask keys (adds defaults)
  - Broken depends_on references (removes non-existent deps)
  - Overall state structure integrity

Usage:
    from utils.state_integrity import check_resume_integrity
    payload = load_state()
    repairs = check_resume_integrity(payload)
    for msg in repairs:
        logger.info(f"State repair: {msg}")
"""

from typing import Dict, List, Any, Optional


# Valid subtask statuses per the project's state machine
VALID_SUBTASK_STATUSES = {"Pending", "Running", "Review", "Verified"}
VALID_SHADOW_STATUSES = {"Pending", "Done"}

# Default values for required subtask fields
DEFAULT_SUBTASK_FIELDS = {
    "status": "Pending",
    "shadow": "Pending",
    "last_update": 0,
    "description": "",
    "output": "",
    "history": [],
}


def check_resume_integrity(payload: Optional[Dict[str, Any]]) -> List[str]:
    """
    Validate and repair a loaded state payload.

    Takes a state dict and repairs common issues:
      - Invalid subtask statuses → reset to Pending
      - Missing subtask keys → add defaults
      - Broken depends_on refs → remove non-existent deps
      - Empty/None payloads → handled gracefully

    Returns a list of repair messages describing what was fixed.
    Repairs are applied in-place to the payload dict.

    Args:
        payload: State dictionary loaded from disk, or None/empty dict

    Returns:
        List of repair messages (empty if no repairs needed)
    """
    repairs: List[str] = []

    # Handle None or empty payload
    if not payload or not isinstance(payload, dict):
        repairs.append("Empty or invalid payload: skipped integrity check")
        return repairs

    # Handle missing top-level keys
    if "dag" not in payload:
        repairs.append("Missing 'dag' key in state: initialized to empty dict")
        payload["dag"] = {}
        return repairs

    dag = payload.get("dag", {})
    if not isinstance(dag, dict):
        repairs.append("dag is not a dict: cannot repair")
        return repairs

    # Collect all valid task IDs for dependency validation
    valid_task_ids = set(dag.keys())

    # Iterate through tasks, branches, and subtasks
    for task_name, task_data in list(dag.items()):
        if not isinstance(task_data, dict):
            repairs.append(f"Task '{task_name}' is not a dict: skipped")
            continue

        # Repair broken depends_on references
        depends_on = task_data.get("depends_on", [])
        if isinstance(depends_on, list):
            broken_deps = [dep for dep in depends_on if dep not in valid_task_ids]
            if broken_deps:
                task_data["depends_on"] = [d for d in depends_on if d in valid_task_ids]
                repairs.append(
                    f"Task '{task_name}': removed broken depends_on refs: {broken_deps}"
                )
        else:
            task_data["depends_on"] = []
            repairs.append(f"Task '{task_name}': depends_on was not a list, reset to []")

        # Process branches
        branches = task_data.get("branches", {})
        if not isinstance(branches, dict):
            repairs.append(f"Task '{task_name}': branches is not a dict, reset to {{}}")
            task_data["branches"] = {}
            continue

        for branch_name, branch_data in list(branches.items()):
            if not isinstance(branch_data, dict):
                repairs.append(
                    f"Task '{task_name}'/Branch '{branch_name}': not a dict, skipped"
                )
                continue

            # Process subtasks
            subtasks = branch_data.get("subtasks", {})
            if not isinstance(subtasks, dict):
                repairs.append(
                    f"Task '{task_name}'/Branch '{branch_name}': "
                    f"subtasks is not a dict, reset to {{}}"
                )
                branch_data["subtasks"] = {}
                continue

            for subtask_name, subtask_data in list(subtasks.items()):
                if not isinstance(subtask_data, dict):
                    repairs.append(
                        f"Task '{task_name}'/Branch '{branch_name}'/Subtask '{subtask_name}': "
                        f"not a dict, skipped"
                    )
                    continue

                path = f"{task_name}/{branch_name}/{subtask_name}"

                # Check and repair status
                status = subtask_data.get("status")
                if status not in VALID_SUBTASK_STATUSES:
                    old_status = status
                    subtask_data["status"] = "Pending"
                    repairs.append(f"{path}: invalid status '{old_status}' → Pending")

                # Check and repair shadow
                shadow = subtask_data.get("shadow")
                if shadow not in VALID_SHADOW_STATUSES:
                    old_shadow = shadow
                    subtask_data["shadow"] = "Pending"
                    repairs.append(
                        f"{path}: invalid shadow '{old_shadow}' → Pending"
                    )

                # Ensure required keys exist with defaults
                for key, default in DEFAULT_SUBTASK_FIELDS.items():
                    if key not in subtask_data:
                        subtask_data[key] = default
                        repairs.append(f"{path}: added missing key '{key}'")

    return repairs
