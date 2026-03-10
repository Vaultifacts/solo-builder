"""Test data factories — canonical state builders for Solo Builder tests (TASK-324).

All new tests SHOULD use these factories instead of defining inline _make_state helpers.
Existing tests retain their inline helpers to avoid mass-refactoring risk.

Public API
----------
make_subtask(status, **kwargs)        → subtask dict
make_dag(subtasks, task, branch)      → dag dict
make_state(subtasks, step, task, ...)  → full state dict with dag
make_multi_task_state()               → state dict with two tasks / four branches
"""
from __future__ import annotations

from typing import Dict, Optional


# ── Subtask factory ───────────────────────────────────────────────────────────

def make_subtask(
    status: str = "Pending",
    output: str = "",
    description: str = "",
    shadow: str = "Pending",
    last_update: int = 0,
) -> dict:
    return {
        "status":      status,
        "shadow":      shadow,
        "last_update": last_update,
        "output":      output,
        "description": description,
    }


# ── DAG factory ───────────────────────────────────────────────────────────────

def make_dag(
    subtasks: Optional[Dict[str, str]] = None,
    task: str = "Task 0",
    branch: str = "Branch A",
    task_status: str = "Running",
    branch_status: str = "Running",
) -> dict:
    """Build a minimal DAG dict.

    Parameters
    ----------
    subtasks
        Mapping of subtask name → status string.
        Defaults to {"A1": "Verified", "A2": "Pending"}.
    task / branch
        Names for the single task / branch created.
    task_status / branch_status
        Status strings for the task and branch nodes.
    """
    sts = subtasks if subtasks is not None else {"A1": "Verified", "A2": "Pending"}
    return {
        task: {
            "status":     task_status,
            "depends_on": [],
            "branches": {
                branch: {
                    "status":   branch_status,
                    "subtasks": {
                        name: make_subtask(
                            status=status,
                            output=f"out {name}",
                            description=f"desc {name}",
                        )
                        for name, status in sts.items()
                    },
                }
            },
        }
    }


# ── State factory ─────────────────────────────────────────────────────────────

def make_state(
    subtasks: Optional[Dict[str, str]] = None,
    step: int = 10,
    task: str = "Task 0",
    branch: str = "Branch A",
    **dag_kwargs,
) -> dict:
    """Build a minimal state dict.

    Returns a dict suitable for writing to STATE_PATH in integration tests.
    """
    return {
        "step": step,
        "dag":  make_dag(subtasks=subtasks, task=task, branch=branch, **dag_kwargs),
    }


# ── Multi-task state factory ──────────────────────────────────────────────────

def make_multi_task_state() -> dict:
    """Build a state with two tasks and two branches each (4 branches total)."""
    return {
        "step": 20,
        "dag": {
            "Task 0": {
                "status":     "Verified",
                "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status":   "Verified",
                        "subtasks": {
                            "A1": make_subtask("Verified", output="done", description="d1"),
                            "A2": make_subtask("Verified", output="done", description="d2"),
                        },
                    },
                    "Branch B": {
                        "status":   "Verified",
                        "subtasks": {
                            "B1": make_subtask("Verified", output="done", description="d3"),
                        },
                    },
                },
            },
            "Task 1": {
                "status":     "Running",
                "depends_on": ["Task 0"],
                "branches": {
                    "Branch C": {
                        "status":   "Running",
                        "subtasks": {
                            "C1": make_subtask("Running", description="d4"),
                            "C2": make_subtask("Pending", description="d5"),
                        },
                    },
                    "Branch D": {
                        "status":   "Pending",
                        "subtasks": {
                            "D1": make_subtask("Pending", description="d6"),
                        },
                    },
                },
            },
        },
    }
