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


@core_bp.get("/health/summary")
def health_summary():
    """Aggregate health summary — runs lightweight checks and returns pass/fail counts."""
    checks = []
    # State file
    _app = _get_app()
    state_ok = _app.STATE_PATH.exists()
    checks.append({"name": "state_file", "ok": state_ok})
    # Settings file
    settings_ok = _app.SETTINGS_PATH.exists()
    checks.append({"name": "settings_file", "ok": settings_ok})
    # Step count
    state = _load_state()
    step = state.get("step", 0)
    checks.append({"name": "step_count", "ok": step >= 0, "value": step})
    # Subtask count
    dag = state.get("dag", {})
    total = sum(len(b.get("subtasks", {})) for t in dag.values() for b in t.get("branches", {}).values())
    checks.append({"name": "subtask_count", "ok": True, "value": total})
    passed = sum(1 for c in checks if c["ok"])
    return jsonify({
        "ok": all(c["ok"] for c in checks),
        "passed": passed,
        "total": len(checks),
        "checks": checks,
    })


@core_bp.get("/api/docs/ui")
def api_docs_ui():
    """Serve a minimal Swagger UI page pointing to /api/docs."""
    from flask import Response
    html = """<!DOCTYPE html>
<html><head><title>Solo Builder API</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url:"/api/docs",dom_id:"#swagger-ui",deepLinking:true})</script>
</body></html>"""
    return Response(html, mimetype="text/html")


@core_bp.get("/api/docs")
def api_docs():
    """Return OpenAPI 3.0 JSON spec for all API routes."""
    try:
        import importlib.util, sys as _sys
        tools_dir = Path(__file__).resolve().parents[3] / "tools"
        spec_path = tools_dir / "generate_openapi.py"
        if "generate_openapi" in _sys.modules:
            mod = _sys.modules["generate_openapi"]
        else:
            _spec = importlib.util.spec_from_file_location("generate_openapi", spec_path)
            mod = importlib.util.module_from_spec(_spec)
            _sys.modules["generate_openapi"] = mod
            _spec.loader.exec_module(mod)
        return jsonify(mod.build_spec())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@core_bp.get("/perf")
def perf():
    """Backend performance metrics — response times and state file size."""
    _app = _get_app()
    state = _load_state()
    dag = state.get("dag", {})
    subtask_count = sum(
        len(b.get("subtasks", {}))
        for t in dag.values()
        for b in t.get("branches", {}).values()
    )
    state_size = 0
    try:
        state_size = _app.STATE_PATH.stat().st_size
    except Exception:
        pass
    return jsonify({
        "state_size_bytes": state_size,
        "state_size_kb": round(state_size / 1024, 1) if state_size else 0,
        "task_count": len(dag),
        "subtask_count": subtask_count,
        "step": state.get("step", 0),
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
