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
