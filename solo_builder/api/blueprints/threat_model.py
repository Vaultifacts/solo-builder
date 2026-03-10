"""Threat model check endpoint — TASK-374 (SE-001 to SE-006).

GET /health/threat-model — run threat model checks and return results as JSON.

Calls tools/threat_model_check.py internal functions directly for a structured
response without subprocess overhead.

Response shape:
  {
    "ok":      bool,    // true when all required checks pass
    "checks": [
      {
        "name":     str,
        "required": bool,
        "passed":   bool,
        "detail":   str   // empty string when passed
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

threat_model_bp = Blueprint("threat_model", __name__)

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


@threat_model_bp.get("/health/threat-model")
def health_threat_model():
    try:
        tm = _load_tool("threat_model_check")
        threat_path = tm.THREAT_MODEL_PATH
        results = []

        file_check = tm._check_file_exists(threat_path)
        results.append(file_check)

        if file_check.passed:
            text = threat_path.read_text(encoding="utf-8")
            results.append(tm._check_gap_ids(text))
            results.append(tm._check_date(text))
            results.extend(tm._check_controls(text))
            results.append(tm._check_threat_sections(text))

        checks = [
            {"name": r.name, "required": r.required, "passed": r.passed, "detail": r.detail}
            for r in results
        ]
        ok = all(r["passed"] for r in checks if r["required"])
        return jsonify({"ok": ok, "checks": checks})
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": str(exc), "checks": []}), 200
