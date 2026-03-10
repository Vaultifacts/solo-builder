"""SLO check endpoint — TASK-375 (OM-035 to OM-040).

GET /health/slo — evaluate SLO-003 (SDK success rate) and SLO-005 (latency)
against the live metrics.jsonl and return structured results.

Response shape:
  {
    "ok":      bool,   // true when all SLOs pass (or insufficient data)
    "records": int,    // number of metrics records found
    "results": [
      {
        "slo":    str,   // "SLO-003" | "SLO-005"
        "target": str,   // human-readable requirement
        "value":  float | null,
        "status": str,   // ok | breach | no_data | skip
        "detail": str
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

slo_bp = Blueprint("slo", __name__)

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


@slo_bp.get("/health/slo")
def health_slo():
    try:
        sc = _load_tool("slo_check")
        records = sc._load_records(sc.METRICS_PATH)
        if len(records) >= sc.DEFAULT_MIN_RECORDS:
            results = [sc._check_slo003(records), sc._check_slo005(records)]
            ok = all(r["status"] == "ok" for r in results)
        else:
            results = []
            ok = True  # insufficient data — not a failure
        return jsonify({"ok": ok, "records": len(records), "results": results})
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc), "records": 0, "results": []}), 200
