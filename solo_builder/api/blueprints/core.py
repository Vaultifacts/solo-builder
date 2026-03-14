"""Core blueprint — GET /, /status, /heartbeat, /health, /changes."""
import json
import time
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

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
    total = verified = running = review = stalled = 0
    stalled_by_branch = []
    for task_name, t in dag.items():
        for branch_name, b in t["branches"].items():
            branch_stalled = 0
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
                        branch_stalled += 1
                elif st == "Review":
                    review += 1
            if branch_stalled:
                stalled_by_branch.append({
                    "task": task_name,
                    "branch": branch_name,
                    "count": branch_stalled,
                })
    return jsonify({
        "step":             step,
        "total":            total,
        "verified":         verified,
        "running":          running,
        "review":           review,
        "stalled":          stalled,
        "pending":          total - verified - running - review,
        "pct":              round(verified / total * 100, 1) if total else 0,
        "complete":         verified == total,
        "stalled_by_branch": sorted(stalled_by_branch, key=lambda x: x["count"], reverse=True),
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


def _read_version() -> str:
    """Read version from pyproject.toml; fall back to importlib.metadata."""
    try:
        toml = Path(__file__).resolve().parents[3] / "pyproject.toml"
        for line in toml.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version"):
                return line.split("=")[1].strip().strip('"\'')
    except Exception:
        pass
    try:
        import importlib.metadata
        return importlib.metadata.version("solo-builder")
    except Exception:
        pass
    return "unknown"


@core_bp.get("/health")
def health():
    """Extended health probe: uptime, version, step, state file, SLO-001 test count."""
    _app = _get_app()
    state = _load_state()
    dag   = state.get("dag", {})
    total_subtasks = sum(
        len(b.get("subtasks", {}))
        for t in dag.values()
        for b in t.get("branches", {}).values()
    )
    return jsonify({
        "ok":               True,
        "version":          _read_version(),
        "uptime_s":         round(time.time() - _app._APP_START_TIME, 1),
        "step":             state.get("step", 0),
        "state_file_exists": _app.STATE_PATH.exists(),
        "total_subtasks":   total_subtasks,
    })


@core_bp.get("/health/aawo")
def health_aawo():
    """Lightweight AAWO status endpoint — active agents + outcome stats."""
    try:
        from utils.aawo_bridge import (get_active_agents, get_outcome_stats,
                                        resolve_executor_config)
        agents = get_active_agents() or []
        outcomes = get_outcome_stats() or {}
        agent_configs = {}
        for agent_id in set(list(outcomes.keys()) + agents):
            cfg = resolve_executor_config(agent_id)
            if cfg:
                agent_configs[agent_id] = cfg
        return jsonify({
            "ok": True,
            "available": True,
            "active_agents": agents,
            "outcome_stats": outcomes,
            "agent_configs": agent_configs,
        })
    except Exception as exc:
        return jsonify({
            "ok": True,
            "available": False,
            "error": str(exc),
            "active_agents": [],
            "outcome_stats": {},
            "agent_configs": {},
        })


@core_bp.get("/changes")
def changes():
    """Lightweight change detection endpoint (TASK-412 hybrid).

    Query params:
      since  — step number; returns changes since that step

    Response:
      {step, changed: bool, changes: [{subtask, task, branch, old_status, new_status, step}]}
    """
    state = _load_state()
    dag   = state.get("dag", {})
    step  = state.get("step", 0)
    since = request.args.get("since", type=int, default=0)

    result = []
    for task_id, task_data in dag.items():
        for br_name, br_data in task_data.get("branches", {}).items():
            for st_name, st_data in br_data.get("subtasks", {}).items():
                history = st_data.get("history", [])
                for entry in history:
                    if entry.get("step", 0) > since:
                        result.append({
                            "subtask": st_name,
                            "task":    task_id,
                            "branch":  br_name,
                            "status":  entry.get("status", ""),
                            "step":    entry.get("step", 0),
                        })
    result.sort(key=lambda e: e["step"])
    return jsonify({
        "step":    step,
        "since":   since,
        "changed": len(result) > 0,
        "count":   len(result),
        "changes": result,
    })
