"""DAG blueprint — GET /tasks/export, /dag/export, POST /dag/import."""
import io
import json

from flask import Blueprint, jsonify, request, Response

from ..helpers import _load_state

dag_bp = Blueprint("dag", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


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
