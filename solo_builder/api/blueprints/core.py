"""Core blueprint — GET /, /status, /heartbeat, /health."""
import json
import time
from pathlib import Path

from flask import Blueprint, jsonify, send_from_directory

from ..helpers import _load_state

core_bp = Blueprint("core", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@core_bp.get("/")
def dashboard():
    return send_from_directory(Path(__file__).resolve().parent.parent, "dashboard.html")


@core_bp.get("/status")
def status():
    _app = _get_app()
    state    = _load_state()
    dag      = state.get("dag", {})
    step     = state.get("step", 0)
    threshold = 5
    try:
        cfg = json.loads(_app.SETTINGS_PATH.read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
    except Exception:
        pass
    total = verified = running = stalled = 0
    for t in dag.values():
        for b in t["branches"].values():
            for s in b["subtasks"].values():
                total += 1
                st = s.get("status", "Pending")
                if st == "Verified":
                    verified += 1
                elif st == "Running":
                    running += 1
                    age = step - s.get("last_update", 0)
                    if age >= threshold:
                        stalled += 1
    return jsonify({
        "step":      step,
        "total":     total,
        "verified":  verified,
        "running":   running,
        "stalled":   stalled,
        "pending":   total - verified - running,
        "pct":       round(verified / total * 100, 1) if total else 0,
        "complete":  verified == total,
    })


@core_bp.get("/heartbeat")
def heartbeat():
    """Lightweight step counter from state/step.txt (no JSON parse)."""
    _app = _get_app()
    if not _app.HEARTBEAT_PATH.exists():
        return jsonify({"step": 0, "verified": 0, "total": 0,
                        "pending": 0, "running": 0, "review": 0})
    try:
        parts = _app.HEARTBEAT_PATH.read_text().strip().split(",")
        return jsonify({
            "step":     int(parts[0]),
            "verified": int(parts[1]),
            "total":    int(parts[2]),
            "pending":  int(parts[3]),
            "running":  int(parts[4]),
            "review":   int(parts[5]) if len(parts) > 5 else 0,
        })
    except (ValueError, IndexError):
        return jsonify({"step": 0, "verified": 0, "total": 0,
                        "pending": 0, "running": 0, "review": 0})


@core_bp.get("/health")
def health():
    """Liveness probe: returns server uptime, current step, and state file presence."""
    _app = _get_app()
    state = _load_state()
    return jsonify({
        "ok": True,
        "uptime_s": round(time.time() - _app._APP_START_TIME, 1),
        "step": state.get("step", 0),
        "state_file_exists": _app.STATE_PATH.exists(),
    })
