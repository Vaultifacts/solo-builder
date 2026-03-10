"""Policy inspection endpoints — TASK-366/TASK-367 (AI-026, AI-033).

GET /policy/hitl   — loaded HitlPolicy as JSON + validation warnings
GET /policy/scope  — loaded ToolScopePolicy as JSON + validation warnings

HTTP status always 200; use the "ok" field for gate decisions.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

policy_bp = Blueprint("policy", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


# ---------------------------------------------------------------------------
# /policy/hitl
# ---------------------------------------------------------------------------

@policy_bp.get("/policy/hitl")
def policy_hitl():
    """Return the currently-loaded HitlPolicy as JSON.

    Response shape:
      {
        "ok":           bool,
        "policy":       {pause_tools, notify_tools, block_keywords, pause_keywords},
        "warnings":     [...],
        "settings_path": str
      }
    """
    try:
        from utils.hitl_policy import load_policy as _load_policy
        _app = _get_app()
        settings_path = str(getattr(_app, "SETTINGS_PATH", ""))
        from pathlib import Path
        policy = _load_policy(settings_path=Path(settings_path) if settings_path else None)
        warnings = policy.validate()
        return jsonify({
            "ok":           len(warnings) == 0,
            "policy":       policy.to_dict(),
            "warnings":     warnings,
            "settings_path": settings_path,
        })
    except Exception as exc:
        return jsonify({
            "ok":       False,
            "error":    str(exc),
            "policy":   {},
            "warnings": [],
        })


# ---------------------------------------------------------------------------
# /policy/scope
# ---------------------------------------------------------------------------

@policy_bp.get("/policy/scope")
def policy_scope():
    """Return the currently-loaded ToolScopePolicy as JSON.

    Response shape:
      {
        "ok":                bool,
        "policy":            {allowlists, default_action_type},
        "warnings":          [...],
        "settings_path":     str
      }
    """
    try:
        from utils.tool_scope_policy import load_scope_policy as _load_scope_policy
        _app = _get_app()
        settings_path = str(getattr(_app, "SETTINGS_PATH", ""))
        from pathlib import Path
        policy = _load_scope_policy(settings_path=Path(settings_path) if settings_path else None)
        warnings = policy.validate()
        return jsonify({
            "ok":               len(warnings) == 0,
            "policy":           policy.to_dict(),
            "warnings":         warnings,
            "settings_path":    settings_path,
        })
    except Exception as exc:
        return jsonify({
            "ok":       False,
            "error":    str(exc),
            "policy":   {},
            "warnings": [],
        })
