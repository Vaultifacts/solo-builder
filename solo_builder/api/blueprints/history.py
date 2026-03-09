"""History blueprint — GET /history, /history/count, /history/export, /diff, /dag/diff, /run/history."""
import csv
import io
import json
from pathlib import Path

from flask import Blueprint, jsonify, request, Response

from ..helpers import _load_state, _load_dag

history_bp = Blueprint("history", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@history_bp.get("/history")
def history():
    """Aggregated step-by-step activity log across all subtasks.

    Query params: since, limit, page, task, branch, subtask, status
    page  P — 1-based page number; used with limit as page size (default page=1)
    """
    dag = _load_dag()
    since = request.args.get("since", type=int)
    limit = request.args.get("limit", 30, type=int)
    page  = max(1, request.args.get("page", 1, type=int))
    task_q    = (request.args.get("task")    or "").strip().lower()
    branch_q  = (request.args.get("branch")  or "").strip().lower()
    subtask_q = (request.args.get("subtask") or "").strip().lower()
    status_q  = (request.args.get("status")  or "").strip().lower()
    events = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                st_output = st_data.get("output", "")
                for h in st_data.get("history", []):
                    events.append({
                        "step": h.get("step", 0),
                        "subtask": st_name,
                        "task": task_id,
                        "branch": branch_name,
                        "status": h.get("status", "?"),
                        "output": st_output,
                    })
    if since is not None:
        events = [e for e in events if e["step"] > since]
    if task_q:
        events = [e for e in events if task_q in e["task"].lower()]
    if branch_q:
        events = [e for e in events if branch_q in e["branch"].lower()]
    if subtask_q:
        events = [e for e in events if subtask_q in e["subtask"].lower()]
    if status_q:
        events = [e for e in events if status_q in e["status"].lower()]
    events.sort(key=lambda e: e["step"], reverse=True)
    total = len(events)
    if limit:
        pages = max(1, -(-total // limit))  # ceiling division
        start = (page - 1) * limit
        events = events[start: start + limit]
    else:
        pages = 1
    return jsonify({"events": events, "total": total, "page": page, "pages": pages})


@history_bp.get("/history/count")
def history_count():
    """Return total event count and filtered count.

    Query params: subtask, status, task, branch, since — same as GET /history
    """
    dag = _load_dag()
    since     = request.args.get("since", type=int)
    task_q    = (request.args.get("task")    or "").strip().lower()
    branch_q  = (request.args.get("branch")  or "").strip().lower()
    subtask_q = (request.args.get("subtask") or "").strip().lower()
    status_q  = (request.args.get("status")  or "").strip().lower()
    total = 0
    filtered = 0
    by_status: dict = {}
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                for h in st_data.get("history", []):
                    total += 1
                    s = h.get("status", "")
                    by_status[s] = by_status.get(s, 0) + 1
                    step = h.get("step", 0)
                    if since is not None and step <= since:
                        continue
                    if task_q    and task_q    not in task_id.lower():      continue
                    if branch_q  and branch_q  not in branch_name.lower():  continue
                    if subtask_q and subtask_q not in st_name.lower():      continue
                    if status_q  and status_q  not in s.lower():            continue
                    filtered += 1
    return jsonify({"total": total, "filtered": filtered, "by_status": by_status})


@history_bp.get("/history/export")
def history_export():
    """Return full activity-log events as CSV (default) or JSON (?format=json).

    Query params
    ------------
    format   csv (default) | json
    since    S — return only events with step > S
    limit    N — return the most recent N events (all if omitted or <= 0)
    subtask  substring filter applied to subtask name (case-insensitive)
    status   substring filter applied to status field (case-insensitive)
    task     substring filter applied to task name (case-insensitive)
    """
    dag = _load_dag()
    events = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                for h in st_data.get("history", []):
                    events.append({
                        "step":    h.get("step", 0),
                        "subtask": st_name,
                        "task":    task_id,
                        "branch":  branch_name,
                        "status":  h.get("status", "?"),
                    })

    since = request.args.get("since", type=int)
    if since is not None:
        events = [e for e in events if e["step"] > since]

    subtask_q = (request.args.get("subtask") or "").strip().lower()
    status_q  = (request.args.get("status")  or "").strip().lower()
    task_q    = (request.args.get("task")    or "").strip().lower()
    if subtask_q:
        events = [e for e in events if subtask_q in e["subtask"].lower()]
    if status_q:
        events = [e for e in events if status_q in e["status"].lower()]
    if task_q:
        events = [e for e in events if task_q in e["task"].lower()]

    events.sort(key=lambda e: e["step"])

    limit = request.args.get("limit", type=int)
    if limit is not None and limit > 0:
        events = events[-limit:]

    fmt = request.args.get("format", "csv").strip().lower()
    if fmt == "json":
        return jsonify(events)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["step", "subtask", "task", "branch", "status"])
    for e in events:
        writer.writerow([e["step"], e["subtask"], e["task"], e["branch"], e["status"]])
    return Response(
        buf.getvalue().encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=history.csv"},
    )


@history_bp.get("/diff")
def diff():
    """Compare current state to .1 backup and return JSON diff."""
    _app = _get_app()
    backup_path = Path(str(_app.STATE_PATH) + ".1")
    if not backup_path.exists():
        return jsonify({"changes": [], "old_step": 0, "new_step": 0,
                        "message": "No backup to diff against."})
    try:
        old = json.loads(backup_path.read_text(encoding="utf-8"))
    except Exception:
        return jsonify({"error": "Could not read backup file."}), 500
    current = _load_state()
    old_dag = old.get("dag", {})
    new_dag = current.get("dag", {})
    changes = []
    for task_name, task_data in new_dag.items():
        old_task = old_dag.get(task_name, {})
        for branch_name, branch_data in task_data.get("branches", {}).items():
            old_branch = old_task.get("branches", {}).get(branch_name, {})
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                old_st = old_branch.get("subtasks", {}).get(st_name, {})
                old_status = old_st.get("status", "Pending")
                new_status = st_data.get("status", "Pending")
                if old_status != new_status:
                    changes.append({
                        "subtask": st_name, "task": task_name,
                        "branch": branch_name,
                        "old_status": old_status, "new_status": new_status,
                        "output": (st_data.get("output") or "")[:200],
                    })
    return jsonify({
        "changes": changes,
        "old_step": old.get("step", 0),
        "new_step": current.get("step", 0),
    })


@history_bp.get("/dag/diff")
def dag_diff():
    """Compare DAG status between two step indices using subtask history arrays.

    Query params:
        from  F — starting step index (inclusive)
        to    T — ending step index (inclusive); defaults to current step

    For each subtask, reconstructs its status at step F and step T using its
    history list, then reports any transitions.

    Returns {from, to, changes:[{subtask, task, branch, from_status, to_status}]}
    """
    state = _load_state()
    dag = state.get("dag", {})
    current_step = state.get("step", 0)

    step_from = request.args.get("from", type=int)
    step_to   = request.args.get("to", current_step, type=int)

    if step_from is None:
        return jsonify({"ok": False, "reason": "Missing required 'from' query param."}), 400

    def _status_at(history: list, target: int) -> str:
        """Return the subtask's status as of target step (last entry with step <= target)."""
        status = "Pending"
        for h in history:
            if h.get("step", 0) <= target:
                status = h.get("status", status)
        return status

    changes = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                hist = st_data.get("history", [])
                s_from = _status_at(hist, step_from)
                s_to   = _status_at(hist, step_to)
                if s_from != s_to:
                    changes.append({
                        "subtask":     st_name,
                        "task":        task_id,
                        "branch":      branch_name,
                        "from_status": s_from,
                        "to_status":   s_to,
                    })

    return jsonify({"from": step_from, "to": step_to,
                    "count": len(changes), "changes": changes})


@history_bp.get("/run/history")
def run_history():
    """Step execution log from meta_history as a JSON API.

    Query params:
        since  S — return only records with step_index > S
        limit  N — return the most recent N records (all if omitted or <= 0)
    """
    state = _load_state()
    meta_history = state.get("meta_history", [])
    cumulative = 0
    records = []
    for i, entry in enumerate(meta_history):
        v = entry.get("verified", 0)
        h = entry.get("healed", 0)
        cumulative += v
        records.append({"step_index": i + 1, "verified": v, "healed": h, "cumulative": cumulative})

    since = request.args.get("since", type=int)
    if since is not None and since >= 0:
        records = [r for r in records if r["step_index"] > since]

    limit = request.args.get("limit", type=int)
    if limit is not None and limit > 0:
        records = records[-limit:]

    return jsonify({"records": records, "count": len(records),
                    "total_steps": len(meta_history)})
