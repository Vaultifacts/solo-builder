"""Context window budget endpoint — TASK-370 (AI-008 to AI-013).

GET /health/context-window — expose per-file context window budget utilization.

Calls tools/context_window_budget.py::check_budget() and returns the report
as JSON, giving the dashboard real-time visibility into context file pressure.

Response shape:
  {
    "ok":        bool,          // true when no file is warn/critical/over_budget
    "has_issues": bool,
    "results": [
      {
        "label":       str,     // "CLAUDE.md" | "MEMORY.md" | "JOURNAL.md"
        "path":        str,
        "lines":       int | null,
        "budget":      int,
        "utilization": float,   // 0–100+ %
        "status":      str      // ok | warn | critical | over_budget | missing
      },
      ...
    ]
  }

HTTP status: always 200; use the "ok" field for gate decisions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Blueprint, jsonify

context_window_bp = Blueprint("context_window", __name__)

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


def _get_app():
    from api.app import app, SETTINGS_PATH  # noqa: PLC0415
    return app, SETTINGS_PATH


@context_window_bp.get("/health/context-window")
def context_window():
    try:
        _, settings_path = _get_app()
        cwb = _load_tool("context_window_budget")
        report = cwb.check_budget(settings_path=settings_path)
        return jsonify({
            "ok":        not report.has_issues,
            "has_issues": report.has_issues,
            "results":   [r.to_dict() for r in report.results],
        })
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc), "has_issues": True, "results": []}), 200
