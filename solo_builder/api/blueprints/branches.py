"""Branches blueprint — GET /branches, /branches/<task_id>."""
from flask import Blueprint, jsonify, abort, request

from ..helpers import _load_dag

branches_bp = Blueprint("branches", __name__)


@branches_bp.get("/branches")
def branches_all():
    """Flat list of all branches across all tasks.

    Query params: task — filter by task name (case-insensitive substring)
    """
    dag = _load_dag()
    task_q = (request.args.get("task") or "").strip().lower()
    result = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            subs = br_data.get("subtasks", {})
            total = len(subs)
            v = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r = sum(1 for s in subs.values() if s.get("status") == "Running")
            p = total - v - r
            result.append({
                "task": task_id,
                "branch": br_name,
                "total": total,
                "verified": v,
                "running": r,
                "pending": p,
                "pct": round(v / total * 100, 1) if total else 0.0,
            })
    return jsonify({"branches": result, "count": len(result)})


@branches_bp.get("/branches/<path:task_id>")
def branches(task_id: str):
    """Per-task branch listing with subtask counts and status breakdown."""
    dag = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    result = []
    for br_name, br_data in task.get("branches", {}).items():
        subs = br_data.get("subtasks", {})
        v = sum(1 for s in subs.values() if s.get("status") == "Verified")
        r = sum(1 for s in subs.values() if s.get("status") == "Running")
        rv = sum(1 for s in subs.values() if s.get("status") == "Review")
        p = len(subs) - v - r - rv
        result.append({
            "branch": br_name,
            "subtask_count": len(subs),
            "verified": v, "running": r, "review": rv, "pending": p,
            "subtasks": [
                {"name": sn, "status": sd.get("status", "Pending")}
                for sn, sd in subs.items()
            ],
        })
    return jsonify({"task": task_id, "branch_count": len(result), "branches": result})
