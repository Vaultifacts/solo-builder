"""
core/persistence.py
State persistence helpers extracted from solo_builder_cli.py.

Handles:
    - Backup rotation (.1 → .2 → .3)
    - State serialization to disk
    - State deserialization from disk (with backward-compatible defaults)
    - Heartbeat file writes (step.txt for Discord bot tracking)
"""

import json
import os
import shutil
from typing import Any, Dict, Optional


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

    Returns True on success, False on failure.
    The caller is responsible for assembling the payload dict.
    """
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    rotate_backups(state_path)
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception:
        return False


# ── Load state ───────────────────────────────────────────────────────────────

def load_state_from_disk(state_path: str) -> Optional[Dict[str, Any]]:
    """
    Load and return the state dict from disk.

    Returns None if the file doesn't exist or can't be parsed.
    The caller is responsible for applying the payload to runtime objects.
    """
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
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
    return payload


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
