"""Branches blueprint — GET /branches, /branches/export, /branches/<task_id>, POST /branches/<task_id>/reset.

Note on /branches/<task_id> vs /tasks/<task_id>/branches:
- /branches/<task_id>        includes subtasks[] array (name+status) — used by dashboard detail view
- /tasks/<task_id>/branches  paginated, branch-level counts only, no subtask list
"""
import csv
import io
import json

from flask import Blueprint, jsonify, abort, request, Response

from ..helpers import _load_dag, _load_state

branches_bp = Blueprint("branches", __name__)


@branches_bp.get("/branches")
def branches_all():
    """Flat list of all branches across all tasks.

    Query params:
      task   — filter by task name (case-insensitive substring)
      status — filter by branch activity: pending|running|review|verified
               pending  = has pending subtasks  (pending > 0)
               running  = has running subtasks  (running > 0)
               review   = has review subtasks   (review  > 0)
               verified = all subtasks verified (verified == total > 0)
    """
    dag = _load_dag()
    task_q   = (request.args.get("task")   or "").strip().lower()
    status_q = (request.args.get("status") or "").strip().lower()
    result = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            subs = br_data.get("subtasks", {})
            total = len(subs)
            v  = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r  = sum(1 for s in subs.values() if s.get("status") == "Running")
            rv = sum(1 for s in subs.values() if s.get("status") == "Review")
            p  = total - v - r - rv
            result.append({
                "task": task_id,
                "branch": br_name,
                "total": total,
                "verified": v,
                "running": r,
                "review": rv,
                "pending": p,
                "pct": round(v / total * 100, 1) if total else 0.0,
                "review_pct": round(rv / total * 100, 1) if total else 0.0,
            })
    if status_q == "verified":
        result = [b for b in result if b["verified"] == b["total"] and b["total"] > 0]
    elif status_q == "running":
        result = [b for b in result if b["running"] > 0]
    elif status_q == "review":
        result = [b for b in result if b["review"] > 0]
    elif status_q == "pending":
        result = [b for b in result if b["pending"] > 0]
    all_count = len(result)
    limit = max(0, request.args.get("limit", 0, type=int))
    page  = max(1, request.args.get("page",  1, type=int))
    if limit > 0:
        pages = max(1, -(-all_count // limit))
        start = (page - 1) * limit
        result = result[start: start + limit]
    else:
        pages = 1
    return jsonify({"branches": result, "count": len(result), "total": all_count, "page": page, "pages": pages})


@branches_bp.get("/branches/export")
def branches_export():
    """Export flat branch list as CSV (default) or JSON (?format=json).

    Supports same ?task= and ?status= filters as GET /branches (no pagination).
    CSV columns: task,branch,total,verified,running,review,pending,pct
    """
    dag = _load_dag()
    task_q   = (request.args.get("task")   or "").strip().lower()
    status_q = (request.args.get("status") or "").strip().lower()
    rows = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            subs = br_data.get("subtasks", {})
            total = len(subs)
            v  = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r  = sum(1 for s in subs.values() if s.get("status") == "Running")
            rv = sum(1 for s in subs.values() if s.get("status") == "Review")
            p  = total - v - r - rv
            rows.append({"task": task_id, "branch": br_name, "total": total,
                         "verified": v, "running": r, "review": rv, "pending": p,
                         "pct": round(v / total * 100, 1) if total else 0.0})
    if status_q == "verified":
        rows = [b for b in rows if b["verified"] == b["total"] and b["total"] > 0]
    elif status_q == "running":
        rows = [b for b in rows if b["running"] > 0]
    elif status_q == "review":
        rows = [b for b in rows if b["review"] > 0]
    elif status_q == "pending":
        rows = [b for b in rows if b["pending"] > 0]
    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt == "json":
        return Response(
            json.dumps({"branches": rows, "total": len(rows)}, indent=2).encode("utf-8"),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=branches.json"},
        )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["task", "branch", "total", "verified", "running", "review", "pending", "pct"])
    for b in rows:
        writer.writerow([b["task"], b["branch"], b["total"], b["verified"],
                         b["running"], b["review"], b["pending"], b["pct"]])
    return Response(
        buf.getvalue().encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=branches.csv"},
    )


@branches_bp.get("/branches/<path:task_id>")
def branches(task_id: str):
    """Per-task branch listing with full subtask name/status array.

    Note: GET /tasks/<task_id>/branches is the newer paginated endpoint for
    branch-level counts and status filtering.  This endpoint is kept because
    it returns the subtasks[] array (name+status per subtask) which the
    dashboard Branches detail view requires for row rendering.
    """
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


@branches_bp.post("/branches/<path:task_id>/reset")
def reset_branch(task_id: str):
    """Bulk-reset all non-Verified subtasks in a branch to Pending.

    Body: {"branch": "<branch_name>"}
    Returns {ok, task, branch, reset_count, skipped_count}.
    404 if task or branch not found.
    """
    from .. import app as _app_mod
    body = request.get_json(silent=True) or {}
    branch_name = (body.get("branch") or "").strip()
    if not branch_name:
        return jsonify({"ok": False, "reason": "Missing 'branch' field."}), 400
    state = _load_state()
    dag = state.get("dag", {})
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    branch = task.get("branches", {}).get(branch_name)
    if branch is None:
        abort(404, description=f"Branch '{branch_name}' not found in task '{task_id}'.")
    reset_count = 0
    skipped_count = 0
    for st_data in branch.get("subtasks", {}).values():
        if st_data.get("status") == "Verified":
            skipped_count += 1
        else:
            st_data["status"] = "Pending"
            st_data["output"] = ""
            st_data.pop("shadow", None)
            reset_count += 1
    try:
        _app_mod.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 500
    return jsonify({
        "ok": True,
        "task": task_id,
        "branch": branch_name,
        "reset_count": reset_count,
        "skipped_count": skipped_count,
    })
