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

    # --- slo_status ---
    try:
        sc = _load_tool("slo_check")
        records = sc._load_records(sc.METRICS_PATH)
        if len(records) >= sc.DEFAULT_MIN_RECORDS:
            slo_results = [sc._check_slo003(records), sc._check_slo005(records)]
            slo_ok = all(r["status"] == "ok" for r in slo_results)
        else:
            slo_results = []
            slo_ok = True  # insufficient data — not a failure
        slo_check_result = {
            "ok":      slo_ok,
            "records": len(records),
            "results": slo_results,
        }
    except Exception as exc:
        slo_check_result = {"ok": False, "records": 0, "results": [], "error": str(exc)}

    # --- repo_health (AAWO snapshot signals + active agents — informational only) ---
    try:
        from utils.aawo_bridge import (get_snapshot as _aawo_snapshot,
                                       get_active_agents as _aawo_agents,
                                       get_outcome_stats as _aawo_outcomes)
        _snap    = _aawo_snapshot(repo_path=".")
        _agents  = _aawo_agents()
        _outcomes = _aawo_outcomes()
        if _snap is not None:
            repo_health_check = {
                "ok":            True,
                "available":     True,
                "signals":       _snap.get("signals", {}),
                "complexity":    _snap.get("complexity", {}).get("value", "unknown"),
                "file_count":    _snap.get("complexity", {}).get("file_count", 0),
                "risk_factors":  _snap.get("risk_factors", []),
                "captured_at":   _snap.get("captured_at", ""),
                "active_agents": _agents or [],
                "outcome_stats": _outcomes or {},
            }
        else:
            repo_health_check = {
                "ok": True, "available": False,
                "signals": {}, "risk_factors": [], "active_agents": _agents or [],
                "outcome_stats": _outcomes or {},
            }
    except Exception as exc:
        repo_health_check = {"ok": True, "available": False, "error": str(exc),
                             "active_agents": [], "outcome_stats": {}}

    # --- patch_review (informational — escalations indicate quality issues) ---
    try:
        from .patch_review import _load_stats as _pr_load
        pr = _pr_load()
        patch_review_check = {
            "ok":             True,
            "enabled":        pr.get("enabled", True),
            "available":      pr.get("available", False),
            "threshold_hits": pr.get("threshold_hits", 0),
            "total_rejections": pr.get("total_rejections", 0),
        }
    except Exception as exc:
        patch_review_check = {"ok": True, "enabled": True, "available": False,
                               "threshold_hits": 0, "total_rejections": 0,
                               "error": str(exc)}

    overall_ok = (state_check["ok"] and drift_check["ok"]
                  and alert_check["ok"] and slo_check_result["ok"])
    # repo_health and patch_review are informational — excluded from overall_ok

    return jsonify({
        "ok": overall_ok,
        "checks": {
            "state_valid":    state_check,
            "config_drift":   drift_check,
            "metrics_alerts": alert_check,
            "slo_status":     slo_check_result,
            "repo_health":    repo_health_check,
            "patch_review":   patch_review_check,
        },
    })
