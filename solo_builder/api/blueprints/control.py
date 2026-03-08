"""Control blueprint — POST /run, /stop, /undo, /reset, /snapshot, /pause, /resume."""
from flask import Blueprint, jsonify, request

from ..helpers import _load_state

control_bp = Blueprint("control", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@control_bp.post("/run")
def run_step():
    """Signal the CLI to execute one step (writes a trigger file the auto loop polls)."""
    _app = _get_app()
    state = _load_state()
    if state.get("dag") and not any(
        s.get("status") in ("Pending", "Running")
        for t in state["dag"].values()
        for b in t["branches"].values()
        for s in b["subtasks"].values()
    ):
        return jsonify({"ok": False, "reason": "pipeline already complete",
                        "step": state.get("step", 0)}), 200
    _app.TRIGGER_PATH.parent.mkdir(exist_ok=True)
    _app.TRIGGER_PATH.write_text("1")
    return jsonify({"ok": True, "step": state.get("step", 0)}), 202


@control_bp.post("/stop")
def stop_run():
    """Signal the CLI to stop the auto-run (writes stop_trigger)."""
    _app = _get_app()
    _app.STOP_TRIGGER.parent.mkdir(exist_ok=True)
    _app.STOP_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@control_bp.post("/undo")
def undo():
    """Restore the pre-step backup (writes undo_trigger)."""
    _app = _get_app()
    _app.UNDO_TRIGGER.parent.mkdir(exist_ok=True)
    _app.UNDO_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@control_bp.post("/reset")
def reset_dag():
    """Reset the DAG to initial state (requires confirm=yes in body)."""
    _app = _get_app()
    data = request.get_json(force=True, silent=True) or {}
    if data.get("confirm", "").lower() != "yes":
        return jsonify({"ok": False, "reason": "Send {\"confirm\": \"yes\"} to confirm reset."}), 400
    _app.RESET_TRIGGER.parent.mkdir(exist_ok=True)
    _app.RESET_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@control_bp.post("/snapshot")
def snapshot():
    """Trigger a PDF timeline snapshot (writes snapshot_trigger)."""
    _app = _get_app()
    _app.SNAPSHOT_TRIGGER.parent.mkdir(exist_ok=True)
    _app.SNAPSHOT_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@control_bp.post("/pause")
def pause_auto():
    """Pause the auto-run (writes pause_trigger)."""
    _app = _get_app()
    _app.PAUSE_TRIGGER.parent.mkdir(exist_ok=True)
    _app.PAUSE_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@control_bp.post("/resume")
def resume_auto():
    """Resume a paused auto-run (removes pause_trigger)."""
    _app = _get_app()
    try:
        if _app.PAUSE_TRIGGER.exists():
            _app.PAUSE_TRIGGER.unlink()
    except OSError:
        pass
    return jsonify({"ok": True}), 202
