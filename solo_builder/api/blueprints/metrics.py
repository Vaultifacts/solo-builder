"""Metrics blueprint — GET /metrics, /metrics/export, /agents, /forecast."""
import csv
import io
import json
import time as _time

from flask import Blueprint, jsonify, request, Response

from ..helpers import _load_state
from ..constants import METRICS_JSONL_PATH

metrics_bp = Blueprint("metrics", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@metrics_bp.get("/agents")
def agents():
    """Return agent statistics as JSON."""
    _app = _get_app()
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    healed = state.get("healed_total", 0)
    meta_history = state.get("meta_history", [])
    threshold = 5
    max_per_step = 6
    try:
        cfg = json.loads(_app.SETTINGS_PATH.read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
        max_per_step = int(cfg.get("EXECUTOR_MAX_PER_STEP", 6))
    except Exception:
        pass
    total = verified = running = stalled_count = 0
    for task in dag.values():
        for branch in task.get("branches", {}).values():
            for st_data in branch.get("subtasks", {}).values():
                total += 1
                s = st_data.get("status", "Pending")
                if s == "Verified":
                    verified += 1
                elif s == "Running":
                    running += 1
                    age = step - st_data.get("last_update", 0)
                    if age >= threshold:
                        stalled_count += 1
    heal_rate = verify_rate = 0.0
    if meta_history:
        window = min(10, len(meta_history))
        recent = meta_history[-window:]
        heal_rate = round(sum(r.get("healed", 0) for r in recent) / window, 3)
        verify_rate = round(sum(r.get("verified", 0) for r in recent) / window, 3)
    remaining = total - verified
    eta = round(remaining / (verify_rate + 1e-6)) if verify_rate > 0 else None
    return jsonify({
        "step": step,
        "planner": {"cache_interval": 5},
        "executor": {"max_per_step": max_per_step},
        "healer": {"healed_total": healed, "threshold": threshold,
                   "currently_stalled": stalled_count},
        "meta": {"history_len": len(meta_history),
                 "heal_rate": heal_rate, "verify_rate": verify_rate},
        "forecast": {"total": total, "verified": verified, "remaining": remaining,
                     "pct": round(verified / total * 100) if total else 0,
                     "eta_steps": eta},
    })


@metrics_bp.get("/forecast")
def forecast():
    """Return detailed completion forecast as JSON."""
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    meta_history = state.get("meta_history", [])
    total = verified = running = pending = review = 0
    for task in dag.values():
        for branch in task.get("branches", {}).values():
            for st_data in branch.get("subtasks", {}).values():
                total += 1
                s = st_data.get("status", "Pending")
                if s == "Verified": verified += 1
                elif s == "Running": running += 1
                elif s == "Pending": pending += 1
                elif s == "Review": review += 1
    remaining = total - verified
    pct = round(verified / total * 100, 1) if total else 0
    verify_rate = heal_rate = 0.0
    if meta_history:
        window = min(10, len(meta_history))
        recent = meta_history[-window:]
        verify_rate = round(sum(r.get("verified", 0) for r in recent) / window, 3)
        heal_rate = round(sum(r.get("healed", 0) for r in recent) / window, 3)
    eta = round(remaining / (verify_rate + 1e-6)) if verify_rate > 0 else None
    return jsonify({
        "step": step, "total": total, "verified": verified,
        "running": running, "pending": pending, "review": review,
        "remaining": remaining, "pct": pct,
        "verify_rate": verify_rate, "heal_rate": heal_rate,
        "eta_steps": eta,
    })


@metrics_bp.get("/metrics")
def metrics():
    """
    Return run health summary + historical per-step metrics for analytics and charting.

    Health fields (TASK-091):
      step, total, verified, pending, running, review, stalled, pct, elapsed_s, steps_per_min

    Analytics fields:
      total_healed, summary (avg rate, peak, etc.), history (per-step records)
    """
    _app = _get_app()
    state = _load_state()
    dag = state.get("dag", {})
    meta_history = state.get("meta_history", [])
    step = state.get("step", 0)
    healed_total = state.get("healed_total", 0)

    # Health counts
    threshold = 5
    try:
        cfg = json.loads(_app.SETTINGS_PATH.read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
    except Exception:
        pass
    total = verified = running = pending = review = stalled = 0
    for t in dag.values():
        for b in t.get("branches", {}).values():
            for s in b.get("subtasks", {}).values():
                total += 1
                st = s.get("status", "Pending")
                if st == "Verified":
                    verified += 1
                elif st == "Running":
                    running += 1
                    if step - s.get("last_update", 0) >= threshold:
                        stalled += 1
                elif st == "Review":
                    review += 1
                else:
                    pending += 1
    pct = round(verified / total * 100, 1) if total else 0.0

    # Elapsed time — use state file mtime as "last active" and ctime as "start"
    elapsed_s = None
    steps_per_min = None
    try:
        stat = _app.STATE_PATH.stat()
        born = stat.st_ctime  # creation time on Windows; metadata-change on Linux
        elapsed_s = round(_time.time() - born, 1)
        if elapsed_s > 0 and step > 0:
            steps_per_min = round(step / (elapsed_s / 60), 2)
    except Exception:
        pass

    # Analytics history
    cumulative = 0
    history = []
    total_verifies = 0
    peak_verified = 0
    steps_with_heals = 0
    for i, entry in enumerate(meta_history):
        v = entry.get("verified", 0)
        h = entry.get("healed", 0)
        cumulative += v
        total_verifies += v
        if v > peak_verified:
            peak_verified = v
        if h > 0:
            steps_with_heals += 1
        history.append({
            "step_index": i + 1,
            "verified":   v,
            "healed":     h,
            "cumulative": cumulative,
        })

    n = len(history)
    avg_rate = round(total_verifies / n, 3) if n else 0.0
    return jsonify({
        "step":          step,
        "total":         total,
        "verified":      verified,
        "pending":       pending,
        "running":       running,
        "review":        review,
        "stalled":       stalled,
        "pct":           pct,
        "elapsed_s":     elapsed_s,
        "steps_per_min": steps_per_min,
        "total_healed":  healed_total,
        "summary": {
            "total_steps":            n,
            "total_verifies":         total_verifies,
            "avg_verified_per_step":  avg_rate,
            "peak_verified_per_step": peak_verified,
            "steps_with_heals":       steps_with_heals,
        },
        "history": history,
    })


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the *pct*-th percentile of a pre-sorted list (0 < pct <= 1)."""
    if not sorted_values:
        return 0.0
    idx = max(0, int(len(sorted_values) * pct) - 1)
    return round(sorted_values[idx], 4)


def _latency_buckets(sorted_values: list[float]) -> dict[str, int]:
    """Count values into five latency bands (PE-001 to PE-005)."""
    buckets: dict[str, int] = {
        "lt_1s": 0, "1s_5s": 0, "5s_10s": 0, "10s_30s": 0, "gt_30s": 0,
    }
    for v in sorted_values:
        if v < 1:
            buckets["lt_1s"] += 1
        elif v < 5:
            buckets["1s_5s"] += 1
        elif v < 10:
            buckets["5s_10s"] += 1
        elif v < 30:
            buckets["10s_30s"] += 1
        else:
            buckets["gt_30s"] += 1
    return buckets


@metrics_bp.get("/metrics/summary")
def metrics_summary():
    """Return executor step metrics summary from metrics.jsonl (TASK-323, TASK-344).

    Fields returned:
      record_count     — total JSONL records in the file
      avg_elapsed_s    — mean step elapsed time in seconds
      min_elapsed_s    — minimum step elapsed time
      p50_elapsed_s    — median step elapsed time (PE-001)
      p95_elapsed_s    — 95th-percentile step elapsed time
      p99_elapsed_s    — 99th-percentile step elapsed time (PE-002 to PE-005)
      max_elapsed_s    — maximum step elapsed time
      latency_buckets  — count of steps in each latency band
      sdk_success_rate — overall SDK success rate (0.0–1.0 or null if no dispatches)
      total_started    — total subtasks started across all recorded steps
      total_verified   — total subtasks verified across all recorded steps
    """
    records = []
    try:
        with open(METRICS_JSONL_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        records = []

    if not records:
        return jsonify({
            "record_count":    0,
            "avg_elapsed_s":   None,
            "min_elapsed_s":   None,
            "p50_elapsed_s":   None,
            "p95_elapsed_s":   None,
            "p99_elapsed_s":   None,
            "max_elapsed_s":   None,
            "latency_buckets": None,
            "sdk_success_rate": None,
            "total_started":   0,
            "total_verified":  0,
        })

    elapsed = sorted(r.get("elapsed_s", 0.0) for r in records)
    n = len(elapsed)
    avg_elapsed = round(sum(elapsed) / n, 4)

    total_dispatched = sum(r.get("sdk_dispatched", 0) for r in records)
    total_succeeded  = sum(r.get("sdk_succeeded",  0) for r in records)
    sdk_rate = round(total_succeeded / total_dispatched, 4) if total_dispatched else None

    total_started  = sum(r.get("started",  0) for r in records)
    total_verified = sum(r.get("verified", 0) for r in records)

    return jsonify({
        "record_count":    n,
        "avg_elapsed_s":   avg_elapsed,
        "min_elapsed_s":   round(elapsed[0], 4),
        "p50_elapsed_s":   _percentile(elapsed, 0.50),
        "p95_elapsed_s":   _percentile(elapsed, 0.95),
        "p99_elapsed_s":   _percentile(elapsed, 0.99),
        "max_elapsed_s":   round(elapsed[-1], 4),
        "latency_buckets": _latency_buckets(elapsed),
        "sdk_success_rate": sdk_rate,
        "total_started":   total_started,
        "total_verified":  total_verified,
    })


@metrics_bp.get("/metrics/export")
def metrics_export():
    """Return per-step metrics history as CSV (default) or JSON (?format=json).

    Query params
    ------------
    format  csv (default) | json
    since   S — return only rows with step_index > S (applied before limit)
    limit   N — return the most recent N rows only (all rows if omitted or <= 0)
    """
    state = _load_state()
    meta_history = state.get("meta_history", [])
    cumulative = 0
    rows = []
    for i, entry in enumerate(meta_history):
        v = entry.get("verified", 0)
        h = entry.get("healed", 0)
        cumulative += v
        rows.append({"step_index": i + 1, "verified": v, "healed": h, "cumulative": cumulative})

    since = request.args.get("since", type=int)
    if since is not None and since >= 0:
        rows = [r for r in rows if r["step_index"] > since]

    limit = request.args.get("limit", type=int)
    if limit is not None and limit > 0:
        rows = rows[-limit:]

    fmt = request.args.get("format", "csv").strip().lower()
    if fmt == "json":
        return jsonify(rows)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["step_index", "verified", "healed", "cumulative"])
    for row in rows:
        writer.writerow([row["step_index"], row["verified"], row["healed"], row["cumulative"]])
    return Response(
        buf.getvalue().encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=metrics.csv"},
    )
