"""Detailed health endpoint — TASK-357 (OM-001 to OM-005).

GET /health/detailed  — aggregate gate-check payload:
  • state_valid      — state schema + dependency validity
  • config_drift     — settings.json drift from defaults
  • metrics_alerts   — metric threshold violations

Response shape:
  {
    "ok": bool,
    "checks": {
      "state_valid":    {"ok": bool, "errors": [...], "warnings": [...]},
      "config_drift":   {"ok": bool, "has_drift": bool,
                         "missing_keys": [...], "overridden_count": int,
                         "unknown_keys": [...]},
      "metrics_alerts": {"ok": bool, "has_alerts": bool,
                         "alert_count": int, "alerts": [...]}
    }
  }

HTTP status: always 200; use the "ok" field for health-gate decisions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Blueprint, jsonify

health_detailed_bp = Blueprint("health_detailed", __name__)

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
    from .. import app as _app_module
    return _app_module


@health_detailed_bp.get("/health/detailed")
def health_detailed():
    _app = _get_app()

    # --- state_valid ---
    try:
        sv = _load_tool("state_validator")
        sv_report = sv.validate(state_path=_app.STATE_PATH)
        state_check = {
            "ok":       sv_report.is_valid,
            "errors":   sv_report.errors,
            "warnings": sv_report.warnings,
        }
    except Exception as exc:
        state_check = {"ok": False, "errors": [str(exc)], "warnings": []}

    # --- config_drift ---
    try:
        cd = _load_tool("config_drift")
        cd_report = cd.detect_drift(settings_path=_app.SETTINGS_PATH)
        drift_check = {
            "ok":               not cd_report.has_drift,
            "has_drift":        cd_report.has_drift,
            "missing_keys":     cd_report.missing_keys,
            "overridden_count": len(cd_report.overridden_keys),
            "unknown_keys":     cd_report.unknown_keys,
        }
    except Exception as exc:
        drift_check = {
            "ok":               False,
            "has_drift":        True,
            "missing_keys":     [],
            "overridden_count": 0,
            "unknown_keys":     [],
            "error":            str(exc),
        }

    # --- metrics_alerts ---
    try:
        mac = _load_tool("metrics_alert_check")
        mac_report = mac.check_alerts()
        alert_check = {
            "ok":          not mac_report.has_alerts,
            "has_alerts":  mac_report.has_alerts,
            "alert_count": len(mac_report.alerts),
            "alerts":      mac_report.alerts,
        }
    except Exception as exc:
        alert_check = {
            "ok":          False,
            "has_alerts":  True,
            "alert_count": 0,
            "alerts":      [],
            "error":       str(exc),
        }

    overall_ok = state_check["ok"] and drift_check["ok"] and alert_check["ok"]

    return jsonify({
        "ok": overall_ok,
        "checks": {
            "state_valid":    state_check,
            "config_drift":   drift_check,
            "metrics_alerts": alert_check,
        },
    })
