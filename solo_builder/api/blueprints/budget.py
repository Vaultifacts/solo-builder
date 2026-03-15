"""Budget dashboard endpoint — GET /health/budget.

Exposes API usage limits (from settings.json) and cumulative activity
(from metrics.jsonl) so the dashboard can surface budget pressure.

Response shape:
  {
    "ok":                   bool,
    "has_limits":           bool,
    "max_cost_usd":         float,   // 0 = unlimited
    "max_total_tokens":     int,     // 0 = unlimited
    "max_api_calls_per_step": int,   // 0 = unlimited
    "total_api_calls":      int,
    "total_succeeded":      int,
    "total_steps":          int,
    "sdk_success_rate":     float | null,
    "recent_steps":         list    // last 5 steps from metrics.jsonl
  }
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Blueprint, jsonify

budget_bp = Blueprint("budget", __name__)

_SOLO         = Path(__file__).resolve().parents[3]
_CFG_PATH     = _SOLO / "config" / "settings.json"
_METRICS_PATH = _SOLO / "metrics.jsonl"


def _load_cfg() -> dict:
    try:
        with open(_CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_metrics() -> list:
    records = []
    try:
        with open(_METRICS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
    except FileNotFoundError:
        pass
    return records


@budget_bp.get("/health/budget")
def health_budget():
    cfg     = _load_cfg()
    records = _load_metrics()

    max_cost           = float(cfg.get("BUDGET_MAX_COST", 0))
    max_tokens         = int(cfg.get("BUDGET_MAX_TOKENS", 0))
    max_calls_per_step = int(cfg.get("BUDGET_MAX_API_CALLS_PER_STEP", 0))

    total_calls     = sum(r.get("sdk_dispatched", 0) for r in records)
    total_succeeded = sum(r.get("sdk_succeeded",  0) for r in records)
    total_steps     = len(records)

    success_rate = round(total_succeeded / total_calls, 3) if total_calls else None

    recent = [
        {
            "step":       r.get("step"),
            "elapsed_s":  r.get("elapsed_s"),
            "dispatched": r.get("sdk_dispatched", 0),
            "succeeded":  r.get("sdk_succeeded",  0),
        }
        for r in records[-5:]
    ]

    has_limits = max_cost > 0 or max_tokens > 0 or max_calls_per_step > 0

    return jsonify({
        "ok":                     True,
        "has_limits":             has_limits,
        "max_cost_usd":           max_cost,
        "max_total_tokens":       max_tokens,
        "max_api_calls_per_step": max_calls_per_step,
        "total_api_calls":        total_calls,
        "total_succeeded":        total_succeeded,
        "total_steps":            total_steps,
        "sdk_success_rate":       success_rate,
        "recent_steps":           recent,
    })
