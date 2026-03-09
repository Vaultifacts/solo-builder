"""DAG blueprint — GET /dag/summary, /tasks/export, /dag/export, POST /dag/import."""
import io
import json

from flask import Blueprint, jsonify, request, Response

from ..helpers import _load_state

dag_bp = Blueprint("dag", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@dag_bp.get("/dag/summary")
def dag_summary():
    """Return a JSON pipeline summary with per-task breakdowns and a markdown text field."""
    state = _load_state()
    dag   = state.get("dag", {})
    step  = state.get("step", 0)

    total = verified = running = pending = 0
    task_rows = []
    for task_id, task_data in dag.items():
        t_total = t_verified = t_running = 0
        branches = task_data.get("branches", {})
        for br in branches.values():
            for st in br.get("subtasks", {}).values():
                t_total += 1
                s = st.get("status", "Pending")
                if s == "Verified":
                    t_verified += 1
                elif s == "Running":
                    t_running += 1
        t_pct = round(t_verified / t_total * 100, 1) if t_total else 0.0
        t_status = task_data.get("status", "Pending")
        task_rows.append({
            "id":       task_id,
            "status":   t_status,
            "branches": len(branches),
            "subtasks": t_total,
            "verified": t_verified,
            "running":  t_running,
            "pct":      t_pct,
        })
        total    += t_total
        verified += t_verified
        running  += t_running
        pending  += t_total - t_verified - t_running

    pct = round(verified / total * 100, 1) if total else 0.0

    lines = [
        "## Pipeline Summary",
        f"- Step {step}",
        f"- {verified}/{total} subtasks verified ({pct}%)",
        f"- {running} running, {pending} pending",
        "",
        "### Tasks",
    ]
    for row in task_rows:
        bar = ("=" * int(row["pct"] / 10)).ljust(10, "-")
        lines.append(
            f"- **{row['id']}** [{bar}] {row['verified']}/{row['subtasks']} "
            f"({row['pct']}%)  {row['status']}"
        )

    return jsonify({
        "step":     step,
        "total":    total,
        "verified": verified,
        "running":  running,
        "pending":  pending,
        "pct":      pct,
        "complete": verified == total and total > 0,
        "tasks":    task_rows,
        "summary":  "\n".join(lines),
    })


@dag_bp.get("/tasks/export")
@dag_bp.get("/dag/export")
def dag_export():
    """Return the current DAG structure as a downloadable JSON file."""
    state = _load_state()
    payload = {
        "exported_step": state.get("step", 0),
        "dag": state.get("dag", {}),
    }
    data = json.dumps(payload, indent=2).encode("utf-8")
    return Response(
        data,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=dag_export.json"},
    )


@dag_bp.post("/dag/import")
def dag_import():
    """
    Replace the persisted DAG with one uploaded as JSON.
    Accepts either:
      - JSON body: {"dag": {...}}  (with optional "exported_step")
      - JSON body: the raw DAG object itself (top-level task keys)
    Writes dag_import_trigger.json so the CLI auto-loop picks it up.
    """
    _app = _get_app()
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    dag = body.get("dag") if "dag" in body else body
    if not isinstance(dag, dict):
        return jsonify({"error": "Invalid DAG structure"}), 400
    # Basic validation: each value must have a "branches" key
    for task_name, task_data in dag.items():
        if not isinstance(task_data, dict) or "branches" not in task_data:
            return jsonify({"error": f"Task '{task_name}' missing 'branches' key"}), 400
    trigger_path = _app.DAG_IMPORT_TRIGGER
    trigger_path.parent.mkdir(exist_ok=True)
    trigger_path.write_text(json.dumps({
        "dag": dag,
        "exported_step": body.get("exported_step"),
    }), encoding="utf-8")
    return jsonify({"ok": True, "tasks": len(dag)}), 202
