"""PatchReviewer stats endpoints.

GET  /health/patch-review         — current stats snapshot
GET  /health/patch-review/history — paginated recent_reviews list
POST /health/patch-review/reset   — delete stats file (fresh counters)
"""
from __future__ import annotations

import json

import json as _json

from flask import Blueprint, jsonify, request

from ..constants import PATCH_REVIEW_STATS_PATH, _PROJECT_ROOT

patch_review_bp = Blueprint("patch_review", __name__)

# Expose for test patching
_STATS_PATH   = PATCH_REVIEW_STATS_PATH
_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.json"


def _alert_threshold() -> int:
    try:
        cfg = _json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return int(cfg.get("PATCH_REVIEW_ALERT_THRESHOLD", 0))
    except Exception:
        return 0


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
        "ok":                  True,
        "enabled":             s.get("enabled", True),
        "available":           s.get("available", False),
        "use_sdk":             s.get("use_sdk", True),
        "threshold_hits":      s.get("threshold_hits", 0),
        "total_rejections":    s.get("total_rejections", 0),
        "max_rejections":      s.get("max_rejections", 3),
        "max_reviews_per_step": s.get("max_reviews_per_step", 0),
        "alert_threshold":     _alert_threshold(),
        "rejected_subtasks":   s.get("rejected_subtasks", []),
        "recent_reviews":      s.get("recent_reviews", []),
    })


@patch_review_bp.get("/health/patch-review/history")
def history_patch_review():
    """Paginated recent_reviews list.

    Query params:
      limit  int  max entries to return (default 10, max 100)
      page   int  1-based page number (default 1)
    """
    s = _load_stats()
    all_reviews = s.get("recent_reviews", [])

    try:
        limit = min(int(request.args.get("limit", 10)), 100)
    except (ValueError, TypeError):
        limit = 10
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (ValueError, TypeError):
        page = 1

    total = len(all_reviews)
    start = (page - 1) * limit
    items = all_reviews[start: start + limit]
    pages = max((total + limit - 1) // limit, 1) if total else 1

    return jsonify({
        "ok":     True,
        "total":  total,
        "page":   page,
        "pages":  pages,
        "limit":  limit,
        "items":  items,
    })


@patch_review_bp.post("/health/patch-review/reset")
def reset_patch_review():
    """Delete the stats file so PatchReviewer counters start fresh next session."""
    try:
        _STATS_PATH.unlink(missing_ok=True)
        reset = True
    except Exception:
        reset = False
    return jsonify({"ok": True, "reset": reset})
