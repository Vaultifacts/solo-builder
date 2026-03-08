"""Cache blueprint — GET/DELETE /cache, GET /cache/history, GET /cache/export."""
import csv
import io
import json

from flask import Blueprint, jsonify, request, Response

from ..helpers import _load_cumulative_stats

cache_bp = Blueprint("cache", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@cache_bp.get("/cache")
def cache_stats():
    """Return response cache disk stats including cumulative hit/miss totals."""
    _app = _get_app()
    try:
        all_files = list(_app.CACHE_DIR.glob("*.json")) if _app.CACHE_DIR.exists() else []
        entries = [f for f in all_files if f.name != _app._STATS_FILE]
        size = len(entries)
    except Exception as exc:
        return jsonify({"error": f"Could not read cache directory: {exc}"}), 500
    cum = _load_cumulative_stats()
    cum_hits   = cum.get("cumulative_hits", 0)
    cum_misses = cum.get("cumulative_misses", 0)
    return jsonify({
        "entries":               size,
        "estimated_tokens_held": size * _app._AVG_TOKENS_PER_ENTRY,
        "cache_dir":             str(_app.CACHE_DIR),
        "cumulative_hits":       cum_hits,
        "cumulative_misses":     cum_misses,
        "cumulative_total":      cum_hits + cum_misses,
        "cumulative_hit_rate":   round(cum_hits / (cum_hits + cum_misses) * 100, 1)
                                 if (cum_hits + cum_misses) > 0 else None,
    })


@cache_bp.delete("/cache")
def cache_clear():
    """Delete all cached response entries (preserves session_stats.json). Returns count deleted."""
    _app = _get_app()
    if not _app.CACHE_DIR.exists():
        return jsonify({"ok": True, "deleted": 0})
    deleted = 0
    errors = 0
    try:
        for f in _app.CACHE_DIR.glob("*.json"):
            if f.name == _app._STATS_FILE:
                continue  # preserve cumulative stats across manual clears
            try:
                f.unlink()
                deleted += 1
            except OSError:
                errors += 1
    except Exception as exc:
        return jsonify({"error": f"Could not clear cache: {exc}"}), 500
    return jsonify({"ok": True, "deleted": deleted, "errors": errors})


@cache_bp.get("/cache/history")
def cache_history():
    """Return per-session cache hit/miss history from session_stats.json.

    Query params: since
    """
    _app = _get_app()
    try:
        path = _app.CACHE_DIR / _app._STATS_FILE
        if not path.exists():
            return jsonify({"sessions": [], "cumulative_hits": 0, "cumulative_misses": 0})
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return jsonify({"error": f"Could not read cache history: {exc}"}), 500
    since = request.args.get("since", type=int)
    raw_sessions = data.get("sessions", [])
    sessions = []
    for i, s in enumerate(raw_sessions):
        h = s.get("hits", 0)
        m = s.get("misses", 0)
        total = h + m
        sessions.append({
            "session":           i + 1,
            "hits":              h,
            "misses":            m,
            "hit_rate":          round(h / total * 100, 1) if total else None,
            "cumulative_hits":   s.get("cumulative_hits", 0),
            "cumulative_misses": s.get("cumulative_misses", 0),
            "ended_at":          s.get("ended_at", ""),
        })
    if since is not None:
        sessions = [s for s in sessions if s["session"] > since]
    return jsonify({
        "sessions":          sessions,
        "cumulative_hits":   data.get("cumulative_hits", 0),
        "cumulative_misses": data.get("cumulative_misses", 0),
    })


@cache_bp.get("/cache/export")
def cache_export():
    """Return cache session history as CSV (default) or JSON (?format=json).

    Query params
    ------------
    format  csv (default) | json
    since   S — return only sessions with session_index > S
    limit   N — return the most recent N sessions (all if omitted or <= 0)
    """
    _app = _get_app()
    try:
        path = _app.CACHE_DIR / _app._STATS_FILE
        if not path.exists():
            data = {}
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return jsonify({"error": f"Could not read cache history: {exc}"}), 500

    raw_sessions = data.get("sessions", [])
    rows = []
    for i, s in enumerate(raw_sessions):
        h = s.get("hits", 0)
        m = s.get("misses", 0)
        total = h + m
        rows.append({
            "session":           i + 1,
            "hits":              h,
            "misses":            m,
            "hit_rate":          round(h / total * 100, 1) if total else None,
            "cumulative_hits":   s.get("cumulative_hits", 0),
            "cumulative_misses": s.get("cumulative_misses", 0),
            "ended_at":          s.get("ended_at", ""),
        })

    since = request.args.get("since", type=int)
    if since is not None:
        rows = [r for r in rows if r["session"] > since]

    limit = request.args.get("limit", type=int)
    if limit is not None and limit > 0:
        rows = rows[-limit:]

    fmt = request.args.get("format", "csv").strip().lower()
    if fmt == "json":
        return jsonify(rows)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["session", "hits", "misses", "hit_rate", "cumulative_hits", "cumulative_misses", "ended_at"])
    for r in rows:
        writer.writerow([r["session"], r["hits"], r["misses"], r["hit_rate"],
                         r["cumulative_hits"], r["cumulative_misses"], r["ended_at"]])
    return Response(
        buf.getvalue().encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cache.csv"},
    )
