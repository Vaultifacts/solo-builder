"""PatchReviewer stats endpoint — GET /health/patch-review.

Reads the stats snapshot written by executor.py after each review_step()
call.  Returns current threshold_hits, per-subtask rejection counts,
SDK availability, and per-step review history so the dashboard can surface
review quality metrics.

Response shape:
  {
    "ok":               bool,
    "enabled":          bool,
    "available":        bool,   // SDK client initialised successfully
    "use_sdk":          bool,   // configured to use Claude SDK
    "threshold_hits":   int,    // times rejection limit was reached
    "total_rejections": int,    // total rejection events across all subtasks
    "max_rejections":   int,    // configured per-subtask limit
    "rejected_subtasks": [      // subtasks with at least one rejection
      {"name": str, "count": int, "last_reason": str}
    ],
    "recent_reviews":   [       // last 10 step summaries
      {"step": int, "approved": int, "rejected": int,
       "escalated": int, "deferred": int}
    ]
  }
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify

patch_review_bp = Blueprint("patch_review", __name__)

_SOLO       = Path(__file__).resolve().parents[3]
_STATS_PATH = _SOLO / "state" / "patch_review_stats.json"


def _load_stats() -> dict:
    try:
        with open(_STATS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@patch_review_bp.get("/health/patch-review")
def health_patch_review():
    s = _load_stats()
    return jsonify({
        "ok":               True,
        "enabled":          s.get("enabled", True),
        "available":        s.get("available", False),
        "use_sdk":          s.get("use_sdk", True),
        "threshold_hits":   s.get("threshold_hits", 0),
        "total_rejections": s.get("total_rejections", 0),
        "max_rejections":   s.get("max_rejections", 3),
        "rejected_subtasks": s.get("rejected_subtasks", []),
        "recent_reviews":   s.get("recent_reviews", []),
    })
