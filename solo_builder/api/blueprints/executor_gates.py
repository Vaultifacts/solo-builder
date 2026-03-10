"""Executor gate summary endpoint — TASK-368 (AI-026, AI-033).

GET /executor/gates — evaluate HITL, scope, and tool-validation gates for
every Running subtask in the current DAG, returning a per-subtask summary.

Useful for ops visibility: shows which subtasks are blocked and why.

Response shape:
  {
    "ok":              bool,   // true when no subtask is blocked
    "running_count":   int,
    "blocked_count":   int,
    "gates": [
      {
        "task":         str,
        "branch":       str,
        "subtask":      str,
        "tools":        str,
        "action_type":  str,
        "hitl_level":   int,   // 0=Auto, 1=Notify, 2=Pause, 3=Block
        "hitl_name":    str,
        "scope_ok":     bool,
        "scope_denied": [str],
        "tools_valid":  bool,
        "blocked":      bool
      },
      ...
    ]
  }

HTTP status always 200.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

executor_gates_bp = Blueprint("executor_gates", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@executor_gates_bp.get("/executor/gates")
def executor_gates():
    _app = _get_app()

    # Load state
    try:
        import json as _json
        state = _json.loads(_app.STATE_PATH.read_text(encoding="utf-8"))
        dag = state.get("dag", {})
    except Exception:
        dag = {}

    # Load policies
    try:
        from utils.hitl_policy import load_policy as _load_hp, evaluate_with_policy as _hp_eval
        hitl_policy = _load_hp(settings_path=_app.SETTINGS_PATH)
    except Exception:
        hitl_policy = None

    try:
        from utils.tool_scope_policy import load_scope_policy as _load_sp, evaluate_scope as _sp_eval
        scope_policy = _load_sp(settings_path=_app.SETTINGS_PATH)
    except Exception:
        scope_policy = None

    # Evaluate gates for each Running subtask
    try:
        from runners.hitl_gate import evaluate as _hg_eval, level_name as _hg_name
    except Exception:
        _hg_eval  = lambda tools, desc: 0
        _hg_name  = lambda lvl: "Auto"

    try:
        from runners.sdk_tool_runner import validate_tools as _vtools
    except Exception:
        _vtools = lambda s: None  # no-op

    gate_rows: list[dict] = []
    for task_name, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_data.get("status") != "Running":
                    continue

                tools       = st_data.get("tools", "").strip()
                description = st_data.get("description", "").strip()
                action_type = st_data.get("action_type", "").strip()

                # Tool validation
                tools_valid = True
                if tools:
                    try:
                        _vtools(tools)
                    except ValueError:
                        tools_valid = False

                # HITL gate
                hitl_level = 0
                if tools and tools_valid:
                    try:
                        gate_lvl   = _hg_eval(tools, description)
                        policy_lvl = (_hp_eval(hitl_policy, tools, description)
                                      if hitl_policy is not None else 0)
                        hitl_level = max(gate_lvl, policy_lvl)
                    except Exception:
                        hitl_level = 0
                hitl_name = _hg_name(hitl_level) if hitl_level > 0 else "Auto"

                # Scope gate
                scope_ok     = True
                scope_denied : list[str] = []
                if tools and tools_valid and scope_policy is not None:
                    try:
                        _at = action_type or scope_policy.default_action_type
                        tool_list = [t.strip() for t in tools.split(",") if t.strip()]
                        sr = _sp_eval(scope_policy, _at, tool_list)
                        scope_ok     = sr.allowed
                        scope_denied = sr.denied
                    except Exception:
                        pass

                blocked = (not tools_valid
                           or hitl_level == 3
                           or not scope_ok)

                gate_rows.append({
                    "task":         task_name,
                    "branch":       branch_name,
                    "subtask":      st_name,
                    "tools":        tools,
                    "action_type":  action_type,
                    "hitl_level":   hitl_level,
                    "hitl_name":    hitl_name,
                    "scope_ok":     scope_ok,
                    "scope_denied": scope_denied,
                    "tools_valid":  tools_valid,
                    "blocked":      blocked,
                })

    blocked_count = sum(1 for r in gate_rows if r["blocked"])
    return jsonify({
        "ok":            blocked_count == 0,
        "running_count": len(gate_rows),
        "blocked_count": blocked_count,
        "gates":         gate_rows,
    })
