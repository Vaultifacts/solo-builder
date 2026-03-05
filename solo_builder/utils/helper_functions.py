"""
utils/helper_functions.py
Shared utilities for Solo Builder: ANSI codes, progress bars, DAG stats, memory helpers.
"""

import json
import os
from typing import Dict, Any, Tuple, List


# ── ANSI Color Codes ──────────────────────────────────────────────────────────
RED     = "\033[91m"
YELLOW  = "\033[93m"
GREEN   = "\033[92m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
WHITE   = "\033[97m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
BLINK   = "\033[5m"
RESET   = "\033[0m"

# ── Status / Shadow Color Maps ────────────────────────────────────────────────
STATUS_COLORS: Dict[str, str] = {
    "Pending":  YELLOW,
    "Running":  CYAN,
    "Review":   MAGENTA,
    "Verified": GREEN,
    "Failed":   RED,
}

SHADOW_COLORS: Dict[str, str] = {
    "Pending": MAGENTA,
    "Done":    GREEN,
}

# ── Alert Constants ───────────────────────────────────────────────────────────
ALERT_STALLED    = f"{BLINK}{RED}⚠ STALLED ⚠{RESET}"
ALERT_PREDICTIVE = f"{BLINK}{YELLOW}⚠ PREDICTIVE FIX ⚠{RESET}"
ALERT_CONFLICT   = f"{BLINK}{RED}⚠ CONFLICT ⚠{RESET}"
ALERT_HEALED     = f"{GREEN}✔ SELF-HEALED{RESET}"

# ── Default bar width ─────────────────────────────────────────────────────────
BAR_WIDTH = 20


# ── Config Loader ─────────────────────────────────────────────────────────────
def load_settings(path: str = "./config/settings.json") -> Dict[str, Any]:
    """Load configuration from JSON file; return defaults if not found."""
    defaults: Dict[str, Any] = {
        "STALL_THRESHOLD":          5,
        "SNAPSHOT_INTERVAL":        20,
        "DAG_UPDATE_INTERVAL":      1,
        "PDF_OUTPUT_PATH":          "./snapshots/",
        "MAX_SUBTASKS_PER_BRANCH":  20,
        "MAX_BRANCHES_PER_TASK":    10,
        "VERBOSITY":                "INFO",
        "BAR_WIDTH":                20,
        "MAX_ALERTS":               10,
        "EXECUTOR_MAX_PER_STEP":    2,
        "EXECUTOR_VERIFY_PROBABILITY": 0.6,
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        defaults.update(loaded)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return defaults


# ── Progress Bar ──────────────────────────────────────────────────────────────
def make_bar(
    filled: int,
    total: int,
    char: str = "=",
    empty: str = "-",
    width: int = BAR_WIDTH,
) -> str:
    """Return a fixed-width progress bar string."""
    if total <= 0:
        return empty * width
    ratio = max(0.0, min(1.0, filled / total))
    filled_count = round(ratio * width)
    return char * filled_count + empty * (width - filled_count)


# ── DAG Statistics ────────────────────────────────────────────────────────────
def dag_stats(dag: Dict) -> Dict[str, int]:
    """Compute overall subtask counts across the entire DAG."""
    stats = {"total": 0, "pending": 0, "running": 0, "review": 0, "verified": 0}
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_data in branch_data.get("subtasks", {}).values():
                stats["total"] += 1
                status = st_data.get("status", "Pending")
                if status == "Pending":
                    stats["pending"] += 1
                elif status == "Running":
                    stats["running"] += 1
                elif status == "Review":
                    stats["review"] += 1
                elif status == "Verified":
                    stats["verified"] += 1
    return stats


def branch_stats(branch_data: Dict) -> Tuple[int, int, int]:
    """Return (verified, running, total) subtask counts for a branch."""
    subtasks = branch_data.get("subtasks", {})
    total    = len(subtasks)
    verified = sum(1 for s in subtasks.values() if s.get("status") == "Verified")
    running  = sum(1 for s in subtasks.values() if s.get("status") == "Running")
    return verified, running, total


def shadow_stats(branch_data: Dict) -> Tuple[int, int]:
    """Return (shadow_done, total) for a branch."""
    subtasks    = branch_data.get("subtasks", {})
    total       = len(subtasks)
    shadow_done = sum(1 for s in subtasks.values() if s.get("shadow") == "Done")
    return shadow_done, total


# ── Memory Helpers ────────────────────────────────────────────────────────────
def memory_depth(memory_store: Dict, branch: str) -> int:
    """Return the number of stored memory snapshots for a branch."""
    return len(memory_store.get(branch, []))


def add_memory_snapshot(
    memory_store: Dict, branch: str, label: str, step: int
) -> None:
    """Append a memory snapshot entry to a branch's memory list."""
    if branch not in memory_store:
        memory_store[branch] = []
    memory_store[branch].append({"snapshot": label, "timestamp": step})


# ── Formatting Helpers ────────────────────────────────────────────────────────
def format_status(status: str) -> str:
    color = STATUS_COLORS.get(status, WHITE)
    return f"{color}{status}{RESET}"


def format_shadow(shadow: str) -> str:
    color = SHADOW_COLORS.get(shadow, WHITE)
    return f"{color}{shadow}{RESET}"


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


# ── DAG Validation ────────────────────────────────────────────────────────────
def validate_dag(dag: Dict) -> List[str]:
    """
    Perform structural validation on the DAG.
    Returns a list of warning strings (empty if valid).
    """
    warnings: List[str] = []
    valid_statuses = {"Pending", "Running", "Verified", "Failed"}
    valid_shadows  = {"Pending", "Done"}

    for task_name, task_data in dag.items():
        if "branches" not in task_data:
            warnings.append(f"{task_name}: missing 'branches' key")
            continue
        for branch_name, branch_data in task_data["branches"].items():
            if "subtasks" not in branch_data:
                warnings.append(f"{task_name}/{branch_name}: missing 'subtasks' key")
                continue
            for st_name, st_data in branch_data["subtasks"].items():
                if st_data.get("status") not in valid_statuses:
                    warnings.append(
                        f"{task_name}/{branch_name}/{st_name}: "
                        f"invalid status '{st_data.get('status')}'"
                    )
                if st_data.get("shadow") not in valid_shadows:
                    warnings.append(
                        f"{task_name}/{branch_name}/{st_name}: "
                        f"invalid shadow '{st_data.get('shadow')}'"
                    )
    return warnings
