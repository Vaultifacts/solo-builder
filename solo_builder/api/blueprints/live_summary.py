"""Live health summary endpoint — TASK-381.

GET /health/live-summary — run the three fast in-process health checks
(threat-model, context-window, slo) and return a consolidated summary.

All checks are called via Python APIs (no subprocess). Total latency is
typically < 100 ms and safe to poll on every dashboard tick.

Response shape:
  {
    "ok":     bool,   // true when all checks pass
    "passed": int,    // number of checks that passed
    "total":  int,    // total checks run
    "checks": [
      {"name": str, "ok": bool, "detail": str},
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

live_summary_bp = Blueprint("live_summary", __name__)

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


def _run_threat_model() -> dict:
    tm = _load_tool("threat_model_check")
    exit_code = tm.run_checks(quiet=True)
    return {"name": "threat-model", "ok": exit_code == 0, "detail": ""}


def _run_context_window() -> dict:
    cw = _load_tool("context_window_check")
    exit_code = cw.check(quiet=True)
    return {"name": "context-window", "ok": exit_code == 0, "detail": ""}


def _run_slo() -> dict:
    sc = _load_tool("slo_check")
    records = sc._load_records(sc.METRICS_PATH)
    if len(records) >= sc.DEFAULT_MIN_RECORDS:
        results = [sc._check_slo003(records), sc._check_slo005(records)]
        ok = all(r["status"] == "ok" for r in results)
    else:
        ok = True  # insufficient data — not a failure
    return {"name": "slo", "ok": ok, "detail": ""}


_CHECK_RUNNERS = [_run_threat_model, _run_context_window, _run_slo]


@live_summary_bp.get("/health/live-summary")
def health_live_summary():
    checks: list[dict] = []
    for runner in _CHECK_RUNNERS:
        try:
            checks.append(runner())
        except Exception as exc:  # pragma: no cover
            name = runner.__name__.replace("_run_", "").replace("_", "-")
            checks.append({"name": name, "ok": False, "detail": str(exc)[:100]})

    passed = sum(1 for c in checks if c["ok"])
    return jsonify({
        "ok":     all(c["ok"] for c in checks),
        "passed": passed,
        "total":  len(checks),
        "checks": checks,
    })
