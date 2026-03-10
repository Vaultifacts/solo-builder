"""Debt scan endpoint — TASK-377 (ME-003).

GET /health/debt-scan — scan source files for TODO/FIXME/HACK/XXX markers and
return a structured summary.

Calls tools/debt_scan.py::scan() via _load_tool.

Response shape:
  {
    "ok":     bool,   // true when count == 0
    "count":  int,    // total debt items found
    "results": [
      {
        "path":   str,
        "line":   int,
        "marker": str,  // TODO | FIXME | HACK | XXX | NOQA
        "text":   str
      },
      ...               // capped at 20 items
    ]
  }

HTTP status: always 200; use "ok" / "count" for gate decisions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Blueprint, jsonify

debt_scan_bp = Blueprint("debt_scan", __name__)

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


@debt_scan_bp.get("/health/debt-scan")
def health_debt_scan():
    try:
        ds = _load_tool("debt_scan")
        items = ds.scan()
        count = len(items)
        results = [
            {"path": str(i.path), "line": i.line, "marker": i.marker, "text": i.text}
            for i in items[:20]
        ]
        return jsonify({"ok": count == 0, "count": count, "results": results})
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc), "count": 0, "results": []}), 200
