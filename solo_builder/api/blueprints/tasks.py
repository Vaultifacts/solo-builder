"""Tasks blueprint — GET /tasks, /tasks/<id>, POST /tasks/<id>/trigger, GET /graph, /priority."""
from flask import Blueprint, jsonify, abort

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
