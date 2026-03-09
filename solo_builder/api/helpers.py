"""
Shared helper functions for the Solo Builder API.

Helpers use lazy imports from the `app` module so that test patches on
`app_module.STATE_PATH`, `app_module.CACHE_DIR`, etc. are respected.
"""
import json
from pathlib import Path

from flask import jsonify, request


def _load_state() -> dict:
    from . import app as _app
    try:
        with open(_app.STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dag": {}, "step": 0}


def _load_dag() -> dict:
    return _load_state().get("dag", {})


def _write_trigger(path: Path, fields: dict,
                   defaults: dict | None = None) -> tuple:
    """Parse body, validate, write trigger JSON.  fields maps name→uppercase."""
    body = request.get_json(silent=True) or {}
    defs = defaults or {}
    payload = {}
    for key, upper in fields.items():
        val = (body.get(key) or defs.get(key, "")).strip()
        if upper:
            val = val.upper()
        if not val:
            return jsonify({"ok": False,
                            "reason": f"Missing '{key}' field."}), 400
        payload[key] = val
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return jsonify({"ok": True, **payload}), 202


def _task_summary(task_id: str, task: dict) -> dict:
    """Lightweight per-task summary for GET /tasks grid rendering.

    Intentionally excludes the branches dict to keep GET /tasks O(tasks)
    rather than O(tasks × branches × subtasks).  The dashboard detail panel
    uses the separate GET /tasks/<id> endpoint which returns full branch data.
    """
    branches      = task.get("branches", {})
    subtask_count = sum(len(b.get("subtasks", {})) for b in branches.values())
    verified      = sum(
        1 for b in branches.values()
        for s in b.get("subtasks", {}).values()
        if s.get("status") == "Verified"
    )
    running = sum(
        1 for b in branches.values()
        for s in b.get("subtasks", {}).values()
        if s.get("status") == "Running"
    )
    return {
        "id":               task_id,
        "status":           task.get("status"),
        "depends_on":       task.get("depends_on", []),
        "branch_count":     len(branches),
        "subtask_count":    subtask_count,
        "verified_subtasks": verified,
        "running_subtasks": running,
    }


def _load_cumulative_stats() -> dict:
    """Read cumulative hit/miss totals from session_stats.json; returns zeros on error."""
    from . import app as _app
    try:
        path = _app.CACHE_DIR / _app._STATS_FILE
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
