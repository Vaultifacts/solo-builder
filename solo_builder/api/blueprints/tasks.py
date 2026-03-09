"""Tasks blueprint — GET /tasks, /tasks/<id>, /tasks/<id>/export, POST /tasks/<id>/trigger, POST /tasks/<id>/reset, GET /graph, /priority."""
import csv
import io
import json

from flask import Blueprint, jsonify, abort, request, Response

from ..helpers import _load_state, _load_dag, _task_summary

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.get("/tasks")
def list_tasks():
    dag = _load_dag()
    return jsonify({"tasks": [_task_summary(tid, t) for tid, t in dag.items()]})


@tasks_bp.get("/tasks/<path:task_id>")
def get_task(task_id: str):
    dag  = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    return jsonify({"id": task_id, **task})


@tasks_bp.get("/tasks/export")
def export_all_tasks():
    """Download a summary of all tasks as CSV (default) or JSON (?format=json).

    CSV columns: task, status, verified, total, pct
    JSON: {tasks: [...], count}
    """
    dag  = _load_dag()
    rows = []
    for task_id, task_data in dag.items():
        total = 0
        verified = 0
        for br in task_data.get("branches", {}).values():
            for st in br.get("subtasks", {}).values():
                total += 1
                if st.get("status") == "Verified":
                    verified += 1
        pct = round(verified / total * 100, 1) if total else 0
        rows.append({
            "task": task_id,
            "status": task_data.get("status", "Pending"),
            "verified": verified,
            "total": total,
            "pct": pct,
        })
    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt == "json":
        body = json.dumps({"tasks": rows, "count": len(rows)}, indent=2)
        return Response(
            body, mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=tasks.json"},
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["task", "status", "verified", "total", "pct"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=tasks.csv"},
    )


@tasks_bp.get("/tasks/<path:task_id>/export")
def export_task(task_id: str):
    """Download a single task's subtasks as CSV (default) or JSON (?format=json).

    CSV columns: subtask, branch, status, output_length, description
    JSON: {task, subtasks: [...]}
    """
    dag  = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    fmt = (request.args.get("format") or "csv").strip().lower()
    rows = []
    for br_name, br_data in task.get("branches", {}).items():
        for st_name, st_data in br_data.get("subtasks", {}).items():
            rows.append({
                "subtask": st_name,
                "branch": br_name,
                "status": st_data.get("status", "Pending"),
                "output_length": len(st_data.get("output", "")),
                "description": st_data.get("description", ""),
            })
    safe_id = task_id.replace("/", "_").replace(" ", "_")
    if fmt == "json":
        body = json.dumps({"task": task_id, "subtasks": rows}, indent=2)
        return Response(
            body,
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="task_{safe_id}.json"'},
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["subtask", "branch", "status", "output_length", "description"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="task_{safe_id}.csv"'},
    )


@tasks_bp.post("/tasks/<path:task_id>/trigger")
def trigger_task(task_id: str):
    dag  = _load_dag()
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
        "id": task_id, "accepted": True,
        "status": task.get("status"),
        "pending_subtasks": pending, "pending_count": len(pending),
    }), 202


@tasks_bp.post("/tasks/<path:task_id>/reset")
def reset_task(task_id: str):
    """Bulk-reset all subtasks in a task to Pending.

    Directly updates STATE.json; equivalent to running subtask reset for every
    subtask in the task.  Returns {ok, task, reset_count, skipped_count}.
    404 if task not found.
    """
    from .. import app as _app_mod
    state = _load_state()
    dag = state.get("dag", {})
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    reset_count = 0
    skipped_count = 0
    for branch_data in task.get("branches", {}).values():
        for st_data in branch_data.get("subtasks", {}).values():
            if st_data.get("status") == "Verified":
                skipped_count += 1
            else:
                st_data["status"] = "Pending"
                st_data["output"] = ""
                st_data.pop("shadow", None)
                reset_count += 1
    task["status"] = "Pending"
    try:
        _app_mod.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 500
    return jsonify({
        "ok": True,
        "task": task_id,
        "reset_count": reset_count,
        "skipped_count": skipped_count,
    })


@tasks_bp.get("/tasks/<path:task_id>/progress")
def task_progress(task_id: str):
    """Lightweight progress summary for a single task.

    Returns {task, status, verified, total, pct, running, pending, review}.
    404 if task not found.
    """
    dag = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    counts = {"Verified": 0, "Running": 0, "Pending": 0, "Review": 0}
    for br_data in task.get("branches", {}).values():
        for st_data in br_data.get("subtasks", {}).values():
            s = st_data.get("status", "Pending")
            counts[s] = counts.get(s, 0) + 1
    total = sum(counts.values())
    verified = counts["Verified"]
    pct = round(verified / total * 100, 1) if total else 0.0
    return jsonify({
        "task": task_id,
        "status": task.get("status", "Pending"),
        "verified": verified,
        "total": total,
        "pct": pct,
        "running": counts["Running"],
        "pending": counts["Pending"],
        "review": counts["Review"],
    })


@tasks_bp.post("/tasks/<path:task_id>/bulk-verify")
def bulk_verify_task(task_id: str):
    """Advance subtasks in a task to Verified.

    Body (optional JSON): {"skip_non_running": false}
    - skip_non_running: if true, only Running/Review subtasks are advanced (default false)
    Already-Verified subtasks are always skipped.
    Returns {ok, task, verified_count, skipped_count}.
    404 if task not found.
    """
    from .. import app as _app_mod
    state = _load_state()
    dag = state.get("dag", {})
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    body = request.get_json(silent=True) or {}
    skip_non_running = body.get("skip_non_running", False)
    verified_count = 0
    skipped_count = 0
    for branch_data in task.get("branches", {}).values():
        for st_data in branch_data.get("subtasks", {}).values():
            current = st_data.get("status", "Pending")
            if current == "Verified":
                skipped_count += 1
            elif skip_non_running and current not in ("Running", "Review"):
                skipped_count += 1
            else:
                st_data["status"] = "Verified"
                verified_count += 1
    if verified_count > 0:
        task["status"] = "Verified"
    try:
        _app_mod.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 500
    return jsonify({
        "ok": True,
        "task": task_id,
        "verified_count": verified_count,
        "skipped_count": skipped_count,
    })


@tasks_bp.get("/tasks/<path:task_id>/branches")
def task_branches(task_id: str):
    """Paginated branch list for a single task.

    Optional filters: ?status=<substring> (case-insensitive match on dominant branch status).
    Pagination: ?page=<n> (1-based) and ?limit=<n> (default 0 = all).
    Response: {task, branches, count, total, page, limit, pages}
    Each branch entry: {branch, subtask_count, verified, running, pending, review, pct, status}
    404 if task not found.
    """
    dag = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    status_q = (request.args.get("status") or "").strip().lower()
    try:
        limit = max(0, int(request.args.get("limit", 0)))
    except (ValueError, TypeError):
        limit = 0
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    result = []
    for br_name, br_data in task.get("branches", {}).items():
        counts = {"Verified": 0, "Running": 0, "Pending": 0, "Review": 0}
        for st_data in br_data.get("subtasks", {}).values():
            s = st_data.get("status", "Pending")
            counts[s] = counts.get(s, 0) + 1
        total_st = sum(counts.values())
        verified = counts["Verified"]
        pct = round(verified / total_st * 100, 1) if total_st else 0.0
        # Dominant status: Running > Review > Pending > Verified
        if counts["Running"]:
            dom = "Running"
        elif counts["Review"]:
            dom = "Review"
        elif counts["Pending"]:
            dom = "Pending"
        else:
            dom = "Verified"
        if status_q and status_q not in dom.lower():
            continue
        result.append({
            "branch": br_name,
            "subtask_count": total_st,
            "verified": verified,
            "running": counts["Running"],
            "pending": counts["Pending"],
            "review": counts["Review"],
            "pct": pct,
            "status": dom,
        })

    total = len(result)
    if limit > 0:
        pages = max(1, -(-total // limit))
        start = (page - 1) * limit
        result = result[start:start + limit]
    else:
        pages = 1

    return jsonify({
        "task": task_id,
        "branches": result,
        "count": len(result),
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    })


@tasks_bp.get("/tasks/<path:task_id>/subtasks")
def task_subtasks(task_id: str):
    """Flat list of subtasks for a single task.

    Supports same ?branch=, ?status= filters (case-insensitive substring) as GET /subtasks.
    Pagination: ?page=<n> (1-based) and ?limit=<n> (default 0 = all).
    Response: {task, subtasks, count, total, page, limit, pages}
    """
    dag = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    branch_q = (request.args.get("branch") or "").strip().lower()
    status_q = (request.args.get("status") or "").strip().lower()
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
    for br_name, br_data in task.get("branches", {}).items():
        if branch_q and branch_q not in br_name.lower():
            continue
        for st_name, st_data in br_data.get("subtasks", {}).items():
            st_status = st_data.get("status", "Pending")
            if status_q and status_q not in st_status.lower():
                continue
            entry = {
                "subtask": st_name,
                "branch": br_name,
                "status": st_status,
                "output_length": len(st_data.get("output", "")),
            }
            if include_output:
                entry["output"] = st_data.get("output", "")
            result.append(entry)
    total = len(result)
    if limit > 0:
        pages = max(1, -(-total // limit))
        start = (page - 1) * limit
        result = result[start:start + limit]
    else:
        pages = 1
    return jsonify({
        "task": task_id,
        "subtasks": result,
        "count": len(result),
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    })


@tasks_bp.get("/tasks/<path:task_id>/timeline")
def task_timeline(task_id: str):
    """Aggregate timeline for all subtasks in a task.

    Returns {task, step, subtasks: [{subtask, branch, status, history, last_update}]}
    sorted by last_update ascending (chronological order of last activity).
    history entries: [{step, status}] from subtask history array.
    """
    state = _load_state()
    dag = state.get("dag", {})
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    entries = []
    for br_name, br_data in task.get("branches", {}).items():
        for st_name, st_data in br_data.get("subtasks", {}).items():
            entries.append({
                "subtask": st_name,
                "branch": br_name,
                "status": st_data.get("status", "Pending"),
                "history": st_data.get("history", []),
                "last_update": st_data.get("last_update", 0),
            })
    entries.sort(key=lambda x: x["last_update"])
    return jsonify({
        "task": task_id,
        "step": state.get("step", 0),
        "count": len(entries),
        "subtasks": entries,
    })


@tasks_bp.get("/graph")
def graph():
    """Return ASCII dependency graph as JSON."""
    dag = _load_dag()
    if not dag:
        return jsonify({"nodes": [], "text": "No tasks in DAG."})
    sym = {"Verified": "V", "Running": "R", "Review": "W", "Pending": "P", "Blocked": "B"}
    nodes = []
    lines = []
    task_names = list(dag.keys())
    for t_name in task_names:
        t = dag[t_name]
        st = t.get("status", "Pending")
        deps = t.get("depends_on", [])
        branches = t.get("branches", {})
        n_st = sum(len(b.get("subtasks", {})) for b in branches.values())
        n_v = sum(1 for b in branches.values()
                  for s in b.get("subtasks", {}).values()
                  if s.get("status") == "Verified")
        nodes.append({"task": t_name, "status": st, "verified": n_v,
                       "total": n_st, "depends_on": deps})
        tag = sym.get(st, "?")
        line = f"[{tag}] {t_name} [{n_v}/{n_st}]"
        if deps:
            line += f"  <- {', '.join(deps)}"
        lines.append(line)
        dependents = [tn for tn in task_names
                      if t_name in dag[tn].get("depends_on", [])]
        for d in dependents:
            lines.append(f"     +-> {d}")
    return jsonify({"nodes": nodes, "text": "\n".join(lines)})


@tasks_bp.get("/priority")
def priority():
    """Return planner-style priority queue as JSON."""
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    candidates = []
    for task_name, task in dag.items():
        deps_met = all(dag.get(d, {}).get("status") == "Verified"
                       for d in task.get("depends_on", []))
        if not deps_met:
            continue
        for branch_name, branch in task.get("branches", {}).items():
            for st_name, st_data in branch.get("subtasks", {}).items():
                status = st_data.get("status", "Pending")
                if status not in ("Pending", "Running"):
                    continue
                age = step - st_data.get("last_update", 0)
                risk = 1000 + age * 10 if status == "Running" else age * 8
                candidates.append({
                    "subtask": st_name, "task": task_name,
                    "branch": branch_name, "status": status,
                    "risk": risk, "age": age,
                })
    candidates.sort(key=lambda x: x["risk"], reverse=True)
    return jsonify({"step": step, "count": len(candidates),
                    "queue": candidates[:30]})
