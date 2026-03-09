"""Subtasks blueprint — /subtasks, /subtasks/export, /subtasks/bulk-reset, /subtask/<id>, /subtask/<id>/output, /subtask/<id>/reset, /timeline/<subtask>, /stalled."""
import csv
import io
import json

from flask import Blueprint, jsonify, abort, request, Response

from ..helpers import _load_state, _load_dag

subtasks_bp = Blueprint("subtasks", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@subtasks_bp.get("/subtasks")
def subtasks_all():
    """Flat list of all subtasks across all tasks.

    Query params: task, branch, status, name (case-insensitive substring); output=1 includes full output.
    Pagination: page=<n> (1-based) and limit=<n> (default 0 = all).
    Response includes total (pre-pagination count), page, limit, pages.
    """
    dag = _load_dag()
    task_q   = (request.args.get("task")   or "").strip().lower()
    branch_q = (request.args.get("branch") or "").strip().lower()
    status_q = (request.args.get("status") or "").strip().lower()
    name_q   = (request.args.get("name")   or "").strip().lower()
    include_output = request.args.get("output", "0") == "1"
    try:
        limit = max(0, int(request.args.get("limit", 0)))
    except (ValueError, TypeError):
        limit = 0
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    result = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            if branch_q and branch_q not in br_name.lower():
                continue
            for st_name, st_data in br_data.get("subtasks", {}).items():
                st_status = st_data.get("status", "Pending")
                if status_q and status_q not in st_status.lower():
                    continue
                if name_q and name_q not in st_name.lower():
                    continue
                entry = {
                    "subtask": st_name,
                    "task": task_id,
                    "branch": br_name,
                    "status": st_status,
                    "output_length": len(st_data.get("output", "")),
                }
                if include_output:
                    entry["output"] = st_data.get("output", "")
                result.append(entry)
    total = len(result)
    if limit > 0:
        pages = max(1, -(-total // limit))  # ceiling division
        start = (page - 1) * limit
        result = result[start:start + limit]
    else:
        pages = 1
    return jsonify({
        "subtasks": result,
        "count": len(result),
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    })


@subtasks_bp.get("/subtasks/export")
def subtasks_export():
    """Export all subtasks as CSV (default) or JSON (?format=json).

    Supports same ?task=, ?branch=, ?status=, ?name= filters as GET /subtasks.
    Pagination: ?page=<n>&limit=<n> (limit=0 exports all).
    CSV columns: subtask,task,branch,status,output_length
    JSON wraps rows in {total, page, limit, pages, subtasks: [...]} when paginated.
    """
    dag = _load_dag()
    task_q   = (request.args.get("task")   or "").strip().lower()
    branch_q = (request.args.get("branch") or "").strip().lower()
    status_q = (request.args.get("status") or "").strip().lower()
    name_q   = (request.args.get("name")   or "").strip().lower()
    fmt = (request.args.get("format") or "csv").strip().lower()
    try:
        limit = max(0, int(request.args.get("limit", 0)))
    except (ValueError, TypeError):
        limit = 0
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    rows = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            if branch_q and branch_q not in br_name.lower():
                continue
            for st_name, st_data in br_data.get("subtasks", {}).items():
                st_status = st_data.get("status", "Pending")
                if status_q and status_q not in st_status.lower():
                    continue
                if name_q and name_q not in st_name.lower():
                    continue
                rows.append({
                    "subtask": st_name,
                    "task": task_id,
                    "branch": br_name,
                    "status": st_status,
                    "output_length": len(st_data.get("output", "")),
                })
    total = len(rows)
    if limit > 0:
        pages = max(1, -(-total // limit))
        start = (page - 1) * limit
        rows = rows[start:start + limit]
    else:
        pages = 1
    if fmt == "json":
        payload = {"total": total, "page": page, "limit": limit, "pages": pages, "subtasks": rows}
        data = json.dumps(payload, indent=2).encode("utf-8")
        return Response(
            data, mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=subtasks.json"},
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["subtask", "task", "branch", "status", "output_length"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=subtasks.csv"},
    )


@subtasks_bp.post("/subtasks/bulk-reset")
def subtasks_bulk_reset():
    """Reset multiple subtasks to Pending in a single request.

    Body: {"subtasks": ["A1", "B2", ...], "skip_verified": true}
    - subtasks: list of subtask names to reset (case-sensitive)
    - skip_verified: if true (default), Verified subtasks are preserved
    Returns {ok, reset_count, skipped_count, not_found: [names], reset: [names]}
    """
    from .. import app as _app_mod
    body = request.get_json(silent=True) or {}
    names = body.get("subtasks")
    if not isinstance(names, list) or not names:
        return jsonify({"ok": False, "reason": "Field 'subtasks' must be a non-empty list."}), 400
    skip_verified = body.get("skip_verified", True)
    state = _load_state()
    dag = state.get("dag", {})
    remaining = set(names)
    reset_names: list = []
    skipped_count = 0
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_name not in remaining:
                    continue
                if skip_verified and st_data.get("status") == "Verified":
                    skipped_count += 1
                    remaining.discard(st_name)
                    continue
                st_data["status"] = "Pending"
                st_data["output"] = ""
                st_data.pop("shadow", None)
                reset_names.append(st_name)
                remaining.discard(st_name)
    try:
        _app_mod.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 500
    return jsonify({
        "ok": True,
        "reset_count": len(reset_names),
        "skipped_count": skipped_count,
        "not_found": sorted(remaining),
        "reset": reset_names,
    })


@subtasks_bp.post("/subtasks/bulk-verify")
def subtasks_bulk_verify():
    """Advance multiple subtasks to Verified in a single request.

    Body: {"subtasks": ["A1", "B2", ...], "skip_non_running": false}
    - subtasks: list of subtask names to verify (case-sensitive)
    - skip_non_running: if true, only Running/Review subtasks are advanced (default false)
    Returns {ok, verified_count, skipped_count, not_found: [names], verified: [names]}
    """
    from .. import app as _app_mod
    body = request.get_json(silent=True) or {}
    names = body.get("subtasks")
    if not isinstance(names, list) or not names:
        return jsonify({"ok": False, "reason": "Field 'subtasks' must be a non-empty list."}), 400
    skip_non_running = body.get("skip_non_running", False)
    state = _load_state()
    dag = state.get("dag", {})
    remaining = set(names)
    verified_names: list = []
    skipped_count = 0
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_name not in remaining:
                    continue
                current = st_data.get("status", "Pending")
                if skip_non_running and current not in ("Running", "Review"):
                    skipped_count += 1
                    remaining.discard(st_name)
                    continue
                if current == "Verified":
                    skipped_count += 1
                    remaining.discard(st_name)
                    continue
                st_data["status"] = "Verified"
                verified_names.append(st_name)
                remaining.discard(st_name)
    try:
        _app_mod.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 500
    return jsonify({
        "ok": True,
        "verified_count": len(verified_names),
        "skipped_count": skipped_count,
        "not_found": sorted(remaining),
        "verified": verified_names,
    })


@subtasks_bp.get("/subtask/<subtask_id>")
def get_subtask(subtask_id: str):
    """Return current state of a named subtask (e.g. 'A1') across the DAG."""
    dag = _load_dag()
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            subtasks = branch_data.get("subtasks", {})
            if subtask_id in subtasks:
                st = subtasks[subtask_id]
                return jsonify({
                    "subtask": subtask_id,
                    "task": task_id,
                    "branch": branch_name,
                    "status": st.get("status", "Pending"),
                    "output": st.get("output", ""),
                    "history": st.get("history", []),
                })
    abort(404, description=f"Subtask '{subtask_id}' not found.")


@subtasks_bp.get("/subtask/<subtask_id>/output")
def get_subtask_output(subtask_id: str):
    """Return the raw output text of a named subtask as plain text."""
    dag = _load_dag()
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            subtasks = branch_data.get("subtasks", {})
            if subtask_id in subtasks:
                output = subtasks[subtask_id].get("output", "")
                return Response(output, mimetype="text/plain")
    abort(404, description=f"Subtask '{subtask_id}' not found.")


@subtasks_bp.post("/subtask/<subtask_id>/reset")
def reset_subtask(subtask_id: str):
    """Reset a subtask to Pending via heal_trigger.json.

    Composes on existing heal infrastructure; CLI SelfHealer consumes the trigger.
    Returns {ok, subtask, previous_status} or 404 if not found.
    """
    _app = _get_app()
    dag = _load_dag()
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            subtasks = branch_data.get("subtasks", {})
            if subtask_id in subtasks:
                prev = subtasks[subtask_id].get("status", "Pending")
                _app.HEAL_TRIGGER.parent.mkdir(exist_ok=True)
                _app.HEAL_TRIGGER.write_text(
                    json.dumps({"subtask": subtask_id}), encoding="utf-8"
                )
                return jsonify({
                    "ok": True,
                    "subtask": subtask_id,
                    "task": task_id,
                    "branch": branch_name,
                    "previous_status": prev,
                })
    abort(404, description=f"Subtask '{subtask_id}' not found.")


@subtasks_bp.get("/timeline/<subtask>")
def timeline(subtask: str):
    """Individual subtask timeline: current status, history, description, output."""
    st_upper = subtask.strip().upper()
    dag = _load_dag()
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_name.upper() == st_upper:
                    return jsonify({
                        "subtask": st_name,
                        "task": task_id,
                        "branch": branch_name,
                        "status": st_data.get("status", "Pending"),
                        "description": st_data.get("description", ""),
                        "output": st_data.get("output", ""),
                        "history": st_data.get("history", []),
                        "tools": st_data.get("tools", ""),
                        "last_update": st_data.get("last_update"),
                    })
    abort(404, description=f"Subtask '{subtask}' not found.")


@subtasks_bp.get("/stalled")
def stalled():
    """Return subtasks stuck in Running longer than STALL_THRESHOLD."""
    _app = _get_app()
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    threshold = 5
    try:
        cfg = json.loads(_app.SETTINGS_PATH.read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
    except Exception:
        pass
    stuck = []
    for task_name, task in dag.items():
        for branch_name, branch in task.get("branches", {}).items():
            for st_name, st_data in branch.get("subtasks", {}).items():
                if st_data.get("status") == "Running":
                    age = step - st_data.get("last_update", 0)
                    if age >= threshold:
                        stuck.append({
                            "subtask": st_name, "task": task_name,
                            "branch": branch_name, "age": age,
                        })
    stuck.sort(key=lambda x: x["age"], reverse=True)
    return jsonify({"step": step, "threshold": threshold,
                    "count": len(stuck), "stalled": stuck})
