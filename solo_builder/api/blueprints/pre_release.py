"""Pre-release gate inventory endpoint — TASK-379.

GET /health/pre-release — return the configured pre-release gate inventory.

Calls tools/pre_release_check.py::_builtin_gates() and _load_verify_gates()
via _load_tool to enumerate all configured release gates.

Response shape:
  {
    "ok":       bool,  // true — gate list is available
    "total":    int,   // total gates configured
    "required": int,   // number of required gates
    "gates": [
      {"name": str, "required": bool},
      ...
    ]
  }

HTTP status: always 200; ok is always true (inventory endpoint).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Blueprint, jsonify

pre_release_bp = Blueprint("pre_release", __name__)

_TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools"


def _load_tool(name: str):
    """Load a tool module from tools/ by name; cache in sys.modules."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _TOOLS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pre_release_bp.get("/health/pre-release")
def health_pre_release():
    try:
        prc = _load_tool("pre_release_check")
        builtin = prc._builtin_gates()
        verify  = prc._load_verify_gates()
        all_gates = builtin + [g for g in verify if g["name"] not in {"unittest-discover"}]
        required_count = sum(1 for g in all_gates if g.get("required", False))
        return jsonify({
            "ok":       True,
            "total":    len(all_gates),
            "required": required_count,
            "gates":    [
                {"name": g["name"], "required": bool(g.get("required", False))}
                for g in all_gates
            ],
        })
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc), "total": 0, "required": 0, "gates": []}), 200
