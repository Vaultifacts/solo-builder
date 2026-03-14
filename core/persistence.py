"""
core/persistence.py
State persistence helpers extracted from solo_builder_cli.py.

Handles:
    - Backup rotation (.1 → .2 → .3)
    - Atomic state serialization to disk (temp-file + os.replace)
    - State deserialization with automatic backup fallback
    - Backward-compatible defaults for older state files
    - Recovery metadata tracking
    - Heartbeat file writes (step.txt for Discord bot tracking)
"""

import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional


# ── Backup rotation ──────────────────────────────────────────────────────────

def rotate_backups(state_path: str) -> None:
    """
    Rotate backup files: .3 → delete, .2 → .3, .1 → .2, current → .1.

    Must be called *before* writing a new state file.
    """
    if not os.path.exists(state_path):
        return
    for i in range(3, 1, -1):
        src = f"{state_path}.{i - 1}"
        dst = f"{state_path}.{i}"
        if os.path.exists(src):
            try:
                os.replace(src, dst)
            except OSError:
                pass
    try:
        shutil.copy2(state_path, f"{state_path}.1")
    except OSError:
        pass


# ── Save state ───────────────────────────────────────────────────────────────

def save_state_to_disk(state_path: str, payload: Dict[str, Any],
                       silent: bool = False) -> bool:
    """
    Serialize state payload to JSON on disk, with backup rotation.

    Uses temp-file + atomic os.replace() so a crash mid-write never
    leaves a truncated state file.  The backup rotation happens *after*
    the new file is safely on disk.

    Returns True on success, False on failure.
    The caller is responsible for assembling the payload dict.
    """
    parent = os.path.dirname(state_path) or "."
    os.makedirs(parent, exist_ok=True)
    try:
        # 1. Write to temp file in the same directory (same filesystem for rename)
        fd, tmp_path = tempfile.mkstemp(
            dir=parent, prefix=".state_tmp_", suffix=".json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            os.unlink(tmp_path)
            raise
        # 2. Rotate backups *before* replacing current with new
        rotate_backups(state_path)
        # 3. Atomic replace: old current is now .1; new data becomes current
        os.replace(tmp_path, state_path)
        return True
    except Exception:
        return False


# ── Load state ───────────────────────────────────────────────────────────────

def _try_load_json(path: str) -> Optional[Dict[str, Any]]:
    """Attempt to load a JSON file; returns None on any failure."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_state_from_disk(
    state_path: str,
    fallback_to_backup: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Load and return the state dict from disk.

    If the current state file is missing or corrupt and *fallback_to_backup*
    is True, automatically tries .1, .2, .3 backups in order.

    When a backup is used, the returned dict will contain a
    ``_recovery_source`` key (e.g. ``"backup.1"``) so callers can detect
    and report the fallback.

    Returns None only if no usable state file is found.
    """
    data = _try_load_json(state_path)
    if data is not None:
        return data

    if not fallback_to_backup:
        return None

    # Current state is missing or corrupt — try backups
    for i in range(1, 4):
        backup_path = f"{state_path}.{i}"
        data = _try_load_json(backup_path)
        if data is not None:
            data["_recovery_source"] = f"backup.{i}"
            return data
    return None


def apply_backward_compat_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure backward-compatible defaults for fields that may be absent
    in older state files.

    Mutates and returns the payload dict for convenience.
    """
    payload.setdefault("meta_history", [])
    payload.setdefault("safety_state", {})
    ss = payload["safety_state"]
    ss.setdefault("dynamic_tasks_created", 0)
    ss.setdefault("ra_last_run_step", -1)
    ss.setdefault("patch_rejections", {})
    ss.setdefault("patch_threshold_hits", 0)

    # Recovery metadata (added for runtime reliability hardening)
    payload.setdefault("recovery_state", {})
    rs = payload["recovery_state"]
    rs.setdefault("last_completed_step", 0)
    rs.setdefault("last_started_step", 0)
    rs.setdefault("last_save_step", 0)
    rs.setdefault("last_failed_phase", None)
    rs.setdefault("recovery_count", 0)
    rs.setdefault("last_recovery_source", None)
    rs.setdefault("malformed_trigger_count", 0)
    rs.setdefault("persistence_fallback_count", 0)
    rs.setdefault("partial_work_repair_count", 0)
    rs.setdefault("phase_failures", [])

    return payload


# ── Resume integrity ────────────────────────────────────────────────────────

def check_resume_integrity(
    payload: Dict[str, Any],
    repair: bool = True,
) -> List[str]:
    """
    Validate critical invariants in a loaded state payload.

    Returns a list of issue descriptions.  When *repair* is True, safe
    inconsistencies are fixed in-place (the message will note the fix).
    When an issue is too severe to repair, the message starts with
    ``FATAL:``.

    Checks:
        - Invalid status values on subtasks
        - Broken dependency references
        - Branch/task roll-up inconsistencies
        - Missing required subtask fields
        - Running subtasks with no output (partial-work detection)
    """
    from core.dag_transitions import VALID_STATUSES

    issues: List[str] = []
    dag = payload.get("dag", {})

    for task_name, task_data in dag.items():
        if not isinstance(task_data, dict):
            issues.append(f"FATAL: {task_name} is not a dict")
            continue

        # Dependency references
        for dep in task_data.get("depends_on", []):
            if dep not in dag:
                if repair:
                    task_data["depends_on"].remove(dep)
                    issues.append(
                        f"{task_name}: removed broken dep '{dep}'"
                    )
                else:
                    issues.append(
                        f"{task_name}: depends_on '{dep}' missing from DAG"
                    )

        branches = task_data.get("branches", {})
        if not isinstance(branches, dict):
            issues.append(f"FATAL: {task_name}.branches is not a dict")
            continue

        all_branches_verified = bool(branches)
        for branch_name, branch_data in branches.items():
            if not isinstance(branch_data, dict):
                issues.append(
                    f"FATAL: {task_name}/{branch_name} is not a dict"
                )
                continue

            subtasks = branch_data.get("subtasks", {})
            all_st_verified = bool(subtasks)

            for st_name, st_data in subtasks.items():
                if not isinstance(st_data, dict):
                    issues.append(
                        f"FATAL: {task_name}/{branch_name}/{st_name} "
                        f"is not a dict"
                    )
                    continue

                status = st_data.get("status", "Pending")

                # Invalid status
                if status not in VALID_STATUSES:
                    if repair:
                        st_data["status"] = "Pending"
                        issues.append(
                            f"{task_name}/{branch_name}/{st_name}: "
                            f"invalid status '{status}' → reset to Pending"
                        )
                        status = "Pending"
                    else:
                        issues.append(
                            f"{task_name}/{branch_name}/{st_name}: "
                            f"invalid status '{status}'"
                        )

                # Missing required fields
                for key, default in (
                    ("shadow", "Pending"),
                    ("last_update", 0),
                    ("description", ""),
                ):
                    if key not in st_data:
                        if repair:
                            st_data[key] = default
                            issues.append(
                                f"{task_name}/{branch_name}/{st_name}: "
                                f"missing '{key}' → set to {default!r}"
                            )

                # Partial-work detection: Running with no output
                if status == "Running" and not st_data.get("output"):
                    step = payload.get("step", 0)
                    last = st_data.get("last_update", 0)
                    if step - last > 0:
                        if repair:
                            st_data["status"] = "Pending"
                            st_data["shadow"] = "Pending"
                            issues.append(
                                f"{task_name}/{branch_name}/{st_name}: "
                                f"Running with no output (stale {step - last} "
                                f"steps) → reset to Pending"
                            )
                            status = "Pending"
                        else:
                            issues.append(
                                f"{task_name}/{branch_name}/{st_name}: "
                                f"Running with no output"
                            )

                if status != "Verified":
                    all_st_verified = False

            # Branch roll-up fix
            if all_st_verified and subtasks:
                if branch_data.get("status") != "Verified":
                    if repair:
                        branch_data["status"] = "Verified"
                        issues.append(
                            f"{task_name}/{branch_name}: "
                            f"all subtasks Verified → branch Verified"
                        )
                    else:
                        issues.append(
                            f"{task_name}/{branch_name}: "
                            f"roll-up inconsistency"
                        )
            else:
                all_branches_verified = False

        # Task roll-up fix
        if all_branches_verified and branches:
            if task_data.get("status") != "Verified":
                if repair:
                    task_data["status"] = "Verified"
                    issues.append(
                        f"{task_name}: all branches Verified → task Verified"
                    )
                else:
                    issues.append(f"{task_name}: roll-up inconsistency")

    return issues


# ── Heartbeat ────────────────────────────────────────────────────────────────

def write_heartbeat(heartbeat_path: str, step: int, dag: Dict) -> None:
    """
    Write live counters to a step.txt file for Discord bot real-time tracking.

    Format: step,verified,total,pending,running,review
    """
    v = t = p = r = rv = 0
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_data in branch_data.get("subtasks", {}).values():
                t += 1
                status = st_data.get("status", "")
                if status == "Verified":
                    v += 1
                elif status == "Pending":
                    p += 1
                elif status == "Running":
                    r += 1
                elif status == "Review":
                    rv += 1
    try:
        with open(heartbeat_path, "w") as f:
            f.write(f"{step},{v},{t},{p},{r},{rv}")
    except OSError:
        pass
