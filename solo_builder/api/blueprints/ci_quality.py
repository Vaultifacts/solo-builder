"""CI quality gate endpoint — TASK-378.

GET /health/ci-quality — return the configured CI quality tool inventory.

Calls tools/ci_quality_gate.py::_tool_definitions() via _load_tool.

Response shape:
  {
    "ok":    bool,   // true — gate is configured and ready
    "count": int,    // number of configured tools
    "tools": [
      {"name": str},
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

ci_quality_bp = Blueprint("ci_quality", __name__)

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


@ci_quality_bp.get("/health/ci-quality")
def health_ci_quality():
    try:
        cq = _load_tool("ci_quality_gate")
        tools = cq._tool_definitions()
        return jsonify({
            "ok":    True,
            "count": len(tools),
            "tools": [{"name": t["name"]} for t in tools],
        })
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc), "count": 0, "tools": []}), 200
