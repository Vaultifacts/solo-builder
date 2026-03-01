"""
Solo Builder REST API
Loads state from state/solo_builder_state.json on every request.

Install:  pip install flask
Run:      flask --app api/app.py run
          python api/app.py
"""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, abort

app = Flask(__name__)

# Resolve state file relative to project root (one level up from api/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = _PROJECT_ROOT / "state" / "solo_builder_state.json"


def _load_dag() -> dict:
    """Load and return the dag dict from the state file."""
    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)
    return state.get("dag", {})


def _task_summary(task_id: str, task: dict) -> dict:
    """Lightweight summary for the list endpoint — no subtask outputs."""
    branches = task.get("branches", {})
    subtask_count = sum(len(b.get("subtasks", {})) for b in branches.values())
    verified = sum(
        1
        for b in branches.values()
        for s in b.get("subtasks", {}).values()
        if s.get("status") == "Verified"
    )
    return {
        "id": task_id,
        "status": task.get("status"),
        "depends_on": task.get("depends_on", []),
        "branch_count": len(branches),
        "subtask_count": subtask_count,
        "verified_subtasks": verified,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/tasks")
def list_tasks():
    """Return a summary list of all tasks in the DAG."""
    dag = _load_dag()
    tasks = [_task_summary(tid, t) for tid, t in dag.items()]
    return jsonify({"tasks": tasks, "total": len(tasks)})


@app.get("/tasks/<path:task_id>")
def get_task(task_id: str):
    """Return full detail for one task, including all branches and subtasks."""
    dag = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    return jsonify({"id": task_id, **task})


@app.post("/tasks/<path:task_id>/trigger")
def trigger_task(task_id: str):
    """
    Trigger execution of a task.
    Reads live state to determine pending subtasks, returns 202 Accepted.
    Does not mutate the state file — the CLI process owns state writes.
    """
    dag = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")

    pending = [
        f"{branch}/{sid}"
        for branch, b in task.get("branches", {}).items()
        for sid, s in b.get("subtasks", {}).items()
        if s.get("status") not in ("Verified", "Running")
    ]

    return jsonify({
        "id": task_id,
        "accepted": True,
        "status": task.get("status"),
        "pending_subtasks": pending,
        "pending_count": len(pending),
    }), 202


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e)}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed."}), 405


if __name__ == "__main__":
    app.run(debug=True)
