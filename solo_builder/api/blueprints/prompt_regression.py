"""Prompt regression check endpoint — TASK-376 (AI-002, AI-003).

GET /health/prompt-regression — validate all registered PromptTemplate entries
and return regression check results as JSON.

Calls tools/prompt_regression_check.py::run_checks() via _load_tool.

Response shape:
  {
    "ok":     bool,    // true when all templates pass
    "passed": bool,
    "total":  int,
    "failed": int,
    "results": [
      {
        "name":   str,
        "passed": bool,
        "errors": [str, ...]
      },
      ...
    ]
  }

HTTP status: always 200; use "ok" for gate decisions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Blueprint, jsonify

prompt_regression_bp = Blueprint("prompt_regression", __name__)

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


@prompt_regression_bp.get("/health/prompt-regression")
def health_prompt_regression():
    try:
        _, settings_path = _get_app()
        prc = _load_tool("prompt_regression_check")
        report = prc.run_checks(settings_path=settings_path)
        d = report.to_dict()
        return jsonify({"ok": d["passed"], **d})
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "passed": False, "total": 0,
                        "failed": 0, "results": [], "error": str(exc)}), 200
