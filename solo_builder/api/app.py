"""
Solo Builder REST API
Loads state from state/solo_builder_state.json on every request.

Install:  pip install flask
Run:      python api/app.py
          flask --app api/app.py run
"""

import csv
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, abort, send_from_directory, request, Response

from .constants import (
    STATE_PATH, TRIGGER_PATH, VERIFY_TRIGGER, DESCRIBE_TRIGGER,
    TOOLS_TRIGGER, SET_TRIGGER, SETTINGS_PATH, RENAME_TRIGGER,
    STOP_TRIGGER, HEAL_TRIGGER, ADD_TASK_TRIGGER, ADD_BRANCH_TRIGGER,
    PRIORITY_BRANCH_TRIGGER, UNDO_TRIGGER, DEPENDS_TRIGGER,
    UNDEPENDS_TRIGGER, RESET_TRIGGER, SNAPSHOT_TRIGGER, PAUSE_TRIGGER,
    HEARTBEAT_PATH, JOURNAL_PATH, OUTPUTS_PATH, CACHE_DIR,
    DAG_EXPORT_PATH, DAG_IMPORT_TRIGGER,
    _CONFIG_DEFAULTS, _SHORTCUTS,
    _AVG_TOKENS_PER_ENTRY, _STATS_FILE,
)
from .helpers import (
    _load_state, _load_dag, _write_trigger, _task_summary,
    _load_cumulative_stats,
)

app = Flask(__name__)
_APP_START_TIME = time.time()

from .blueprints.cache import cache_bp
from .blueprints.metrics import metrics_bp
app.register_blueprint(cache_bp)
app.register_blueprint(metrics_bp)


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def dashboard():
    return send_from_directory(Path(__file__).parent, "dashboard.html")


@app.get("/status")
def status():
    state    = _load_state()
    dag      = state.get("dag", {})
    step     = state.get("step", 0)
    threshold = 5
    try:
        cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
    except Exception:
        pass
    total = verified = running = stalled = 0
    for t in dag.values():
        for b in t["branches"].values():
            for s in b["subtasks"].values():
                total += 1
                st = s.get("status", "Pending")
                if st == "Verified":
                    verified += 1
                elif st == "Running":
                    running += 1
                    age = step - s.get("last_update", 0)
                    if age >= threshold:
                        stalled += 1
    return jsonify({
        "step":      step,
        "total":     total,
        "verified":  verified,
        "running":   running,
        "stalled":   stalled,
        "pending":   total - verified - running,
        "pct":       round(verified / total * 100, 1) if total else 0,
        "complete":  verified == total,
    })


@app.get("/tasks")
def list_tasks():
    dag = _load_dag()
    return jsonify({"tasks": [_task_summary(tid, t) for tid, t in dag.items()]})


@app.get("/tasks/<path:task_id>")
def get_task(task_id: str):
    dag  = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    return jsonify({"id": task_id, **task})


@app.post("/tasks/<path:task_id>/trigger")
def trigger_task(task_id: str):
    dag  = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    pending = [
        f"{branch}/{sid}"
        for branch, b in task.get("branches", {}).items()
        for sid, s in b.get("subtasks", {}).items()
        if s.get("status") not in ("Verified", "Running")
    ]
    return jsonify({
        "id": task_id, "accepted": True,
        "status": task.get("status"),
        "pending_subtasks": pending, "pending_count": len(pending),
    }), 202


@app.post("/run")
def run_step():
    """Signal the CLI to execute one step (writes a trigger file the auto loop polls)."""
    state = _load_state()
    if state.get("dag") and not any(
        s.get("status") in ("Pending", "Running")
        for t in state["dag"].values()
        for b in t["branches"].values()
        for s in b["subtasks"].values()
    ):
        return jsonify({"ok": False, "reason": "pipeline already complete",
                        "step": state.get("step", 0)}), 200
    TRIGGER_PATH.parent.mkdir(exist_ok=True)
    TRIGGER_PATH.write_text("1")
    return jsonify({"ok": True, "step": state.get("step", 0)}), 202


@app.post("/stop")
def stop_run():
    """Signal the CLI to stop the auto-run (writes stop_trigger)."""
    STOP_TRIGGER.parent.mkdir(exist_ok=True)
    STOP_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@app.post("/verify")
def verify_subtask():
    """Queue a subtask verify via trigger file."""
    return _write_trigger(VERIFY_TRIGGER, {"subtask": True, "note": False},
                          defaults={"note": "Dashboard verify"})


@app.post("/describe")
def describe_subtask():
    """Queue a subtask describe via trigger file."""
    return _write_trigger(DESCRIBE_TRIGGER, {"subtask": True, "desc": False})


@app.post("/tools")
def tools_subtask():
    """Queue a subtask tools change via trigger file."""
    return _write_trigger(TOOLS_TRIGGER, {"subtask": True, "tools": False})


@app.post("/set")
def set_setting():
    """Queue a settings change via trigger file."""
    return _write_trigger(SET_TRIGGER, {"key": True, "value": False})


@app.post("/rename")
def rename_subtask():
    """Queue a subtask rename via trigger file."""
    return _write_trigger(RENAME_TRIGGER, {"subtask": True, "desc": False})


@app.get("/heartbeat")
def heartbeat():
    """Lightweight step counter from state/step.txt (no JSON parse)."""
    if not HEARTBEAT_PATH.exists():
        return jsonify({"step": 0, "verified": 0, "total": 0,
                        "pending": 0, "running": 0, "review": 0})
    try:
        parts = HEARTBEAT_PATH.read_text().strip().split(",")
        return jsonify({
            "step":     int(parts[0]),
            "verified": int(parts[1]),
            "total":    int(parts[2]),
            "pending":  int(parts[3]),
            "running":  int(parts[4]),
            "review":   int(parts[5]) if len(parts) > 5 else 0,
        })
    except (ValueError, IndexError):
        return jsonify({"step": 0, "verified": 0, "total": 0,
                        "pending": 0, "running": 0, "review": 0})


@app.get("/health")
def health():
    """Liveness probe: returns server uptime, current step, and state file presence."""
    state = _load_state()
    return jsonify({
        "ok": True,
        "uptime_s": round(time.time() - _APP_START_TIME, 1),
        "step": state.get("step", 0),
        "state_file_exists": STATE_PATH.exists(),
    })


@app.get("/export")
def export_outputs():
    """Download all subtask outputs as a Markdown file."""
    if not OUTPUTS_PATH.exists():
        return jsonify({"error": "No export file found. Run 'export' in the CLI first."}), 404
    return send_from_directory(
        OUTPUTS_PATH.parent,
        OUTPUTS_PATH.name,
        as_attachment=True,
        download_name="solo_builder_outputs.md",
        mimetype="text/markdown",
    )


@app.post("/export")
def generate_export():
    """Regenerate solo_builder_outputs.md from current state, then serve it."""
    state = _load_state()
    dag   = state.get("dag", {})
    step  = state.get("step", 0)
    total = sum(len(b["subtasks"]) for t in dag.values() for b in t["branches"].values())
    verified = sum(
        1 for t in dag.values() for b in t["branches"].values()
        for s in b["subtasks"].values() if s.get("status") == "Verified"
    )
    lines = [
        "# Solo Builder — Claude Outputs\n",
        f"Step: {step}  |  Verified: {verified}/{total}\n",
        "---\n",
    ]
    count = 0
    for task_name, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                out = st_data.get("output", "").strip()
                if not out:
                    continue
                desc = st_data.get("description", "").strip()
                lines.append(f"## {st_name} — {task_name} / {branch_name}\n")
                if desc:
                    lines.append(f"**Prompt:** {desc}\n\n")
                lines.append(f"{out}\n\n")
                count += 1
    if count == 0:
        return jsonify({"ok": False, "reason": "No Claude outputs in state yet."}), 404
    OUTPUTS_PATH.parent.mkdir(exist_ok=True)
    OUTPUTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    return send_from_directory(
        OUTPUTS_PATH.parent,
        OUTPUTS_PATH.name,
        as_attachment=True,
        download_name="solo_builder_outputs.md",
        mimetype="text/markdown",
    )


@app.get("/stats")
def stats():
    """Per-task breakdown: verified, total, pct, avg steps to complete."""
    dag = _load_dag()
    tasks = []
    grand_v = grand_t = 0
    all_dur: list = []
    for task_id, task_data in dag.items():
        tv = tt = 0
        durs: list = []
        for b in task_data.get("branches", {}).values():
            for st in b.get("subtasks", {}).values():
                tt += 1
                if st.get("status") == "Verified":
                    tv += 1
                    h = st.get("history", [])
                    if len(h) >= 2:
                        durs.append(h[-1].get("step", 0) - h[0].get("step", 0))
        pct = round(tv / tt * 100, 1) if tt else 0
        avg = round(sum(durs) / len(durs), 1) if durs else None
        tasks.append({
            "id": task_id, "verified": tv, "total": tt,
            "pct": pct, "avg_steps": avg,
            "status": task_data.get("status"),
        })
        grand_v += tv
        grand_t += tt
        all_dur.extend(durs)
    return jsonify({
        "tasks": tasks,
        "grand_verified": grand_v, "grand_total": grand_t,
        "grand_pct": round(grand_v / grand_t * 100, 1) if grand_t else 0,
        "grand_avg_steps": round(sum(all_dur) / len(all_dur), 1) if all_dur else None,
    })


@app.get("/search")
def search():
    """Search subtasks by keyword in name, description, or output."""
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"error": "Missing 'q' query parameter."}), 400
    dag = _load_dag()
    matches = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                desc = (st_data.get("description") or "").lower()
                out = (st_data.get("output") or "").lower()
                if q in desc or q in out or q in st_name.lower():
                    matches.append({
                        "subtask": st_name, "task": task_id,
                        "branch": branch_name,
                        "status": st_data.get("status", "Pending"),
                        "description": (st_data.get("description") or "")[:200],
                        "output": (st_data.get("output") or "")[:200],
                    })
    return jsonify({"query": q, "count": len(matches), "results": matches})


@app.get("/history")
def history():
    """Aggregated step-by-step activity log across all subtasks.

    Query params: since, limit, page, task, branch, subtask, status
    page  P — 1-based page number; used with limit as page size (default page=1)
    """
    dag = _load_dag()
    since = request.args.get("since", type=int)
    limit = request.args.get("limit", 30, type=int)
    page  = max(1, request.args.get("page", 1, type=int))
    task_q    = (request.args.get("task")    or "").strip().lower()
    branch_q  = (request.args.get("branch")  or "").strip().lower()
    subtask_q = (request.args.get("subtask") or "").strip().lower()
    status_q  = (request.args.get("status")  or "").strip().lower()
    events = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                st_output = st_data.get("output", "")
                for h in st_data.get("history", []):
                    events.append({
                        "step": h.get("step", 0),
                        "subtask": st_name,
                        "task": task_id,
                        "branch": branch_name,
                        "status": h.get("status", "?"),
                        "output": st_output,
                    })
    if since is not None:
        events = [e for e in events if e["step"] > since]
    if task_q:
        events = [e for e in events if task_q in e["task"].lower()]
    if branch_q:
        events = [e for e in events if branch_q in e["branch"].lower()]
    if subtask_q:
        events = [e for e in events if subtask_q in e["subtask"].lower()]
    if status_q:
        events = [e for e in events if status_q in e["status"].lower()]
    events.sort(key=lambda e: e["step"], reverse=True)
    total = len(events)
    if limit:
        pages = max(1, -(-total // limit))  # ceiling division
        start = (page - 1) * limit
        events = events[start: start + limit]
    else:
        pages = 1
    return jsonify({"events": events, "total": total, "page": page, "pages": pages})


@app.get("/history/count")
def history_count():
    """Return total event count and filtered count.

    Query params: subtask, status, task, branch, since — same as GET /history
    """
    dag = _load_dag()
    since     = request.args.get("since", type=int)
    task_q    = (request.args.get("task")    or "").strip().lower()
    branch_q  = (request.args.get("branch")  or "").strip().lower()
    subtask_q = (request.args.get("subtask") or "").strip().lower()
    status_q  = (request.args.get("status")  or "").strip().lower()
    total = 0
    filtered = 0
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                for h in st_data.get("history", []):
                    total += 1
                    step = h.get("step", 0)
                    if since is not None and step <= since:
                        continue
                    if task_q    and task_q    not in task_id.lower():      continue
                    if branch_q  and branch_q  not in branch_name.lower():  continue
                    if subtask_q and subtask_q not in st_name.lower():      continue
                    if status_q  and status_q  not in h.get("status", "").lower(): continue
                    filtered += 1
    return jsonify({"total": total, "filtered": filtered})


@app.get("/history/export")
def history_export():
    """Return full activity-log events as CSV (default) or JSON (?format=json).

    Query params
    ------------
    format   csv (default) | json
    since    S — return only events with step > S
    limit    N — return the most recent N events (all if omitted or <= 0)
    subtask  substring filter applied to subtask name (case-insensitive)
    status   substring filter applied to status field (case-insensitive)
    task     substring filter applied to task name (case-insensitive)
    """
    dag = _load_dag()
    events = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                for h in st_data.get("history", []):
                    events.append({
                        "step":    h.get("step", 0),
                        "subtask": st_name,
                        "task":    task_id,
                        "branch":  branch_name,
                        "status":  h.get("status", "?"),
                    })

    since = request.args.get("since", type=int)
    if since is not None:
        events = [e for e in events if e["step"] > since]

    subtask_q = (request.args.get("subtask") or "").strip().lower()
    status_q  = (request.args.get("status")  or "").strip().lower()
    task_q    = (request.args.get("task")    or "").strip().lower()
    if subtask_q:
        events = [e for e in events if subtask_q in e["subtask"].lower()]
    if status_q:
        events = [e for e in events if status_q in e["status"].lower()]
    if task_q:
        events = [e for e in events if task_q in e["task"].lower()]

    events.sort(key=lambda e: e["step"])

    limit = request.args.get("limit", type=int)
    if limit is not None and limit > 0:
        events = events[-limit:]

    fmt = request.args.get("format", "csv").strip().lower()
    if fmt == "json":
        return jsonify(events)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["step", "subtask", "task", "branch", "status"])
    for e in events:
        writer.writerow([e["step"], e["subtask"], e["task"], e["branch"], e["status"]])
    return Response(
        buf.getvalue().encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=history.csv"},
    )


@app.get("/diff")
def diff():
    """Compare current state to .1 backup and return JSON diff."""
    backup_path = Path(str(STATE_PATH) + ".1")
    if not backup_path.exists():
        return jsonify({"changes": [], "old_step": 0, "new_step": 0,
                        "message": "No backup to diff against."})
    try:
        old = json.loads(backup_path.read_text(encoding="utf-8"))
    except Exception:
        return jsonify({"error": "Could not read backup file."}), 500
    current = _load_state()
    old_dag = old.get("dag", {})
    new_dag = current.get("dag", {})
    changes = []
    for task_name, task_data in new_dag.items():
        old_task = old_dag.get(task_name, {})
        for branch_name, branch_data in task_data.get("branches", {}).items():
            old_branch = old_task.get("branches", {}).get(branch_name, {})
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                old_st = old_branch.get("subtasks", {}).get(st_name, {})
                old_status = old_st.get("status", "Pending")
                new_status = st_data.get("status", "Pending")
                if old_status != new_status:
                    changes.append({
                        "subtask": st_name, "task": task_name,
                        "branch": branch_name,
                        "old_status": old_status, "new_status": new_status,
                        "output": (st_data.get("output") or "")[:200],
                    })
    return jsonify({
        "changes": changes,
        "old_step": old.get("step", 0),
        "new_step": current.get("step", 0),
    })


@app.get("/dag/diff")
def dag_diff():
    """Compare DAG status between two step indices using subtask history arrays.

    Query params:
        from  F — starting step index (inclusive)
        to    T — ending step index (inclusive); defaults to current step

    For each subtask, reconstructs its status at step F and step T using its
    history list, then reports any transitions.

    Returns {from, to, changes:[{subtask, task, branch, from_status, to_status}]}
    """
    state = _load_state()
    dag = state.get("dag", {})
    current_step = state.get("step", 0)

    step_from = request.args.get("from", type=int)
    step_to   = request.args.get("to", current_step, type=int)

    if step_from is None:
        return jsonify({"ok": False, "reason": "Missing required 'from' query param."}), 400

    def _status_at(history: list, target: int) -> str:
        """Return the subtask's status as of target step (last entry with step <= target)."""
        status = "Pending"
        for h in history:
            if h.get("step", 0) <= target:
                status = h.get("status", status)
        return status

    changes = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                hist = st_data.get("history", [])
                s_from = _status_at(hist, step_from)
                s_to   = _status_at(hist, step_to)
                if s_from != s_to:
                    changes.append({
                        "subtask":     st_name,
                        "task":        task_id,
                        "branch":      branch_name,
                        "from_status": s_from,
                        "to_status":   s_to,
                    })

    return jsonify({"from": step_from, "to": step_to,
                    "count": len(changes), "changes": changes})


@app.get("/branches")
def branches_all():
    """Flat list of all branches across all tasks.

    Query params: task — filter by task name (case-insensitive substring)
    """
    dag = _load_dag()
    task_q = (request.args.get("task") or "").strip().lower()
    result = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            subs = br_data.get("subtasks", {})
            total = len(subs)
            v = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r = sum(1 for s in subs.values() if s.get("status") == "Running")
            p = total - v - r
            result.append({
                "task": task_id,
                "branch": br_name,
                "total": total,
                "verified": v,
                "running": r,
                "pending": p,
                "pct": round(v / total * 100, 1) if total else 0.0,
            })
    return jsonify({"branches": result, "count": len(result)})


@app.get("/subtasks")
def subtasks_all():
    """Flat list of all subtasks across all tasks.

    Query params: task, branch, status (case-insensitive substring); output=1 includes full output.
    """
    dag = _load_dag()
    task_q   = (request.args.get("task")   or "").strip().lower()
    branch_q = (request.args.get("branch") or "").strip().lower()
    status_q = (request.args.get("status") or "").strip().lower()
    include_output = request.args.get("output", "0") == "1"
    result = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            if branch_q and branch_q not in br_name.lower():
                continue
            for st_name, st_data in br_data.get("subtasks", {}).items():
                st_status = st_data.get("status", "Pending")
                if status_q and status_q not in st_status.lower():
                    continue
                entry = {
                    "subtask": st_name,
                    "task": task_id,
                    "branch": br_name,
                    "status": st_status,
                    "output_length": len(st_data.get("output", "")),
                }
                if include_output:
                    entry["output"] = st_data.get("output", "")
                result.append(entry)
    return jsonify({"subtasks": result, "count": len(result)})


@app.get("/subtasks/export")
def subtasks_export():
    """Export all subtasks as CSV (default) or JSON (?format=json).

    Supports same ?task=, ?branch=, ?status= filters as GET /subtasks.
    CSV columns: subtask,task,branch,status,output_length
    """
    dag = _load_dag()
    task_q   = (request.args.get("task")   or "").strip().lower()
    branch_q = (request.args.get("branch") or "").strip().lower()
    status_q = (request.args.get("status") or "").strip().lower()
    fmt = (request.args.get("format") or "csv").strip().lower()
    rows = []
    for task_id, task_data in dag.items():
        if task_q and task_q not in task_id.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            if branch_q and branch_q not in br_name.lower():
                continue
            for st_name, st_data in br_data.get("subtasks", {}).items():
                st_status = st_data.get("status", "Pending")
                if status_q and status_q not in st_status.lower():
                    continue
                rows.append({
                    "subtask": st_name,
                    "task": task_id,
                    "branch": br_name,
                    "status": st_status,
                    "output_length": len(st_data.get("output", "")),
                })
    if fmt == "json":
        data = json.dumps(rows, indent=2).encode("utf-8")
        return Response(
            data, mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=subtasks.json"},
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["subtask", "task", "branch", "status", "output_length"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=subtasks.csv"},
    )


@app.get("/branches/<path:task_id>")
def branches(task_id: str):
    """Per-task branch listing with subtask counts and status breakdown."""
    dag = _load_dag()
    task = dag.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found.")
    result = []
    for br_name, br_data in task.get("branches", {}).items():
        subs = br_data.get("subtasks", {})
        v = sum(1 for s in subs.values() if s.get("status") == "Verified")
        r = sum(1 for s in subs.values() if s.get("status") == "Running")
        rv = sum(1 for s in subs.values() if s.get("status") == "Review")
        p = len(subs) - v - r - rv
        result.append({
            "branch": br_name,
            "subtask_count": len(subs),
            "verified": v, "running": r, "review": rv, "pending": p,
            "subtasks": [
                {"name": sn, "status": sd.get("status", "Pending")}
                for sn, sd in subs.items()
            ],
        })
    return jsonify({"task": task_id, "branch_count": len(result), "branches": result})


@app.get("/timeline/<subtask>")
def timeline(subtask: str):
    """Individual subtask timeline: current status, history, description, output."""
    st_upper = subtask.strip().upper()
    dag = _load_dag()
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_name.upper() == st_upper:
                    return jsonify({
                        "subtask": st_name,
                        "task": task_id,
                        "branch": branch_name,
                        "status": st_data.get("status", "Pending"),
                        "description": st_data.get("description", ""),
                        "output": st_data.get("output", ""),
                        "history": st_data.get("history", []),
                        "tools": st_data.get("tools", ""),
                        "last_update": st_data.get("last_update"),
                    })
    abort(404, description=f"Subtask '{subtask}' not found.")


@app.get("/journal")
def journal():
    if not JOURNAL_PATH.exists():
        return jsonify({"entries": []})
    content = JOURNAL_PATH.read_text(encoding="utf-8")
    entries = []
    for block in re.split(r"(?=^## )", content, flags=re.MULTILINE):
        if not block.strip().startswith("## "):
            continue
        m = re.match(r"^## (\w+) · (Task \d+) / (Branch \w+) · Step (\d+)", block)
        if not m:
            continue
        body = block[m.end():].strip()
        body = re.sub(r"^\*\*Prompt:\*\*.*\n\n?", "", body).strip()
        body = body.rstrip("-").strip()
        entries.append({
            "subtask": m.group(1), "task": m.group(2),
            "branch":  m.group(3), "step": int(m.group(4)),
            "output":  body[:600],
        })
    return jsonify({"entries": entries[-30:]})


@app.get("/config")
def config():
    """Expose runtime settings as JSON."""
    if not SETTINGS_PATH.exists():
        return jsonify({"error": "Settings file not found."}), 404
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return jsonify(data)
    except Exception:
        return jsonify({"error": "Could not read settings."}), 500


@app.post("/config")
def update_config():
    """Merge posted keys into settings.json and return updated config."""
    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"ok": False, "reason": "No JSON body."}), 400
    if not SETTINGS_PATH.exists():
        return jsonify({"error": "Settings file not found."}), 404
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        for key, val in body.items():
            if key not in data:
                return jsonify({"ok": False, "reason": f"Unknown key '{key}'."}), 400
            data[key] = val
        SETTINGS_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return jsonify({"ok": True, **data})
    except Exception:
        return jsonify({"error": "Could not update settings."}), 500



@app.post("/config/reset")
def reset_config():
    """Restore config/settings.json to compiled-in defaults.

    Returns {ok, restored, config} where config is the resulting settings.
    409 if settings file does not exist.
    """
    if not SETTINGS_PATH.exists():
        return jsonify({"ok": False, "reason": "Settings file not found."}), 409
    try:
        SETTINGS_PATH.write_text(json.dumps(_CONFIG_DEFAULTS, indent=4), encoding="utf-8")
        return jsonify({"ok": True, "restored": True, "config": _CONFIG_DEFAULTS})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 500



@app.get("/shortcuts")
def shortcuts():
    """Return all active keyboard shortcuts as a JSON array of {key, description}."""
    return jsonify({"shortcuts": _SHORTCUTS, "count": len(_SHORTCUTS)})


@app.get("/graph")
def graph():
    """Return ASCII dependency graph as JSON."""
    dag = _load_dag()
    if not dag:
        return jsonify({"nodes": [], "text": "No tasks in DAG."})
    sym = {"Verified": "V", "Running": "R", "Review": "W", "Pending": "P", "Blocked": "B"}
    nodes = []
    lines = []
    task_names = list(dag.keys())
    for t_name in task_names:
        t = dag[t_name]
        st = t.get("status", "Pending")
        deps = t.get("depends_on", [])
        branches = t.get("branches", {})
        n_st = sum(len(b.get("subtasks", {})) for b in branches.values())
        n_v = sum(1 for b in branches.values()
                  for s in b.get("subtasks", {}).values()
                  if s.get("status") == "Verified")
        nodes.append({"task": t_name, "status": st, "verified": n_v,
                       "total": n_st, "depends_on": deps})
        tag = sym.get(st, "?")
        line = f"[{tag}] {t_name} [{n_v}/{n_st}]"
        if deps:
            line += f"  <- {', '.join(deps)}"
        lines.append(line)
        dependents = [tn for tn in task_names
                      if t_name in dag[tn].get("depends_on", [])]
        for d in dependents:
            lines.append(f"     +-> {d}")
    return jsonify({"nodes": nodes, "text": "\n".join(lines)})


@app.get("/priority")
def priority():
    """Return planner-style priority queue as JSON."""
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    candidates = []
    for task_name, task in dag.items():
        deps_met = all(dag.get(d, {}).get("status") == "Verified"
                       for d in task.get("depends_on", []))
        if not deps_met:
            continue
        for branch_name, branch in task.get("branches", {}).items():
            for st_name, st_data in branch.get("subtasks", {}).items():
                status = st_data.get("status", "Pending")
                if status not in ("Pending", "Running"):
                    continue
                age = step - st_data.get("last_update", 0)
                risk = 1000 + age * 10 if status == "Running" else age * 8
                candidates.append({
                    "subtask": st_name, "task": task_name,
                    "branch": branch_name, "status": status,
                    "risk": risk, "age": age,
                })
    candidates.sort(key=lambda x: x["risk"], reverse=True)
    return jsonify({"step": step, "count": len(candidates),
                    "queue": candidates[:30]})


@app.get("/stalled")
def stalled():
    """Return subtasks stuck in Running longer than STALL_THRESHOLD."""
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    threshold = 5
    try:
        cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
    except Exception:
        pass
    stuck = []
    for task_name, task in dag.items():
        for branch_name, branch in task.get("branches", {}).items():
            for st_name, st_data in branch.get("subtasks", {}).items():
                if st_data.get("status") == "Running":
                    age = step - st_data.get("last_update", 0)
                    if age >= threshold:
                        stuck.append({
                            "subtask": st_name, "task": task_name,
                            "branch": branch_name, "age": age,
                        })
    stuck.sort(key=lambda x: x["age"], reverse=True)
    return jsonify({"step": step, "threshold": threshold,
                    "count": len(stuck), "stalled": stuck})


@app.post("/heal")
def heal():
    """Write heal_trigger.json so the CLI resets a Running subtask to Pending."""
    data = request.get_json(force=True, silent=True) or {}
    subtask = data.get("subtask", "").strip().upper()
    if not subtask:
        return jsonify({"ok": False, "reason": "Missing 'subtask' field."}), 400
    HEAL_TRIGGER.parent.mkdir(exist_ok=True)
    HEAL_TRIGGER.write_text(json.dumps({"subtask": subtask}), encoding="utf-8")
    return jsonify({"ok": True, "subtask": subtask}), 202


@app.post("/add_task")
def add_task():
    """Queue a new task (writes add_task_trigger.json)."""
    data = request.get_json(force=True, silent=True) or {}
    spec = data.get("spec", "").strip()
    if not spec:
        return jsonify({"ok": False, "reason": "Missing 'spec' field."}), 400
    ADD_TASK_TRIGGER.parent.mkdir(exist_ok=True)
    ADD_TASK_TRIGGER.write_text(json.dumps({"spec": spec}), encoding="utf-8")
    return jsonify({"ok": True, "spec": spec}), 202


@app.post("/add_branch")
def add_branch():
    """Queue a new branch on an existing task (writes add_branch_trigger.json)."""
    data = request.get_json(force=True, silent=True) or {}
    task = data.get("task", "").strip()
    spec = data.get("spec", "").strip()
    if not task or not spec:
        return jsonify({"ok": False, "reason": "Missing 'task' or 'spec' field."}), 400
    ADD_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
    ADD_BRANCH_TRIGGER.write_text(json.dumps({"task": task, "spec": spec}), encoding="utf-8")
    return jsonify({"ok": True, "task": task, "spec": spec}), 202


@app.post("/prioritize_branch")
def prioritize_branch():
    """Boost a branch to the front of the execution queue."""
    data = request.get_json(force=True, silent=True) or {}
    task   = data.get("task", "").strip()
    branch = data.get("branch", "").strip()
    if not task or not branch:
        return jsonify({"ok": False, "reason": "Missing 'task' or 'branch' field."}), 400
    PRIORITY_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
    PRIORITY_BRANCH_TRIGGER.write_text(json.dumps({"task": task, "branch": branch}), encoding="utf-8")
    return jsonify({"ok": True, "task": task, "branch": branch}), 202


@app.post("/undo")
def undo():
    """Restore the pre-step backup (writes undo_trigger)."""
    UNDO_TRIGGER.parent.mkdir(exist_ok=True)
    UNDO_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@app.post("/depends")
def add_depends():
    """Add a task dependency (writes depends_trigger.json)."""
    data   = request.get_json(force=True, silent=True) or {}
    target = data.get("target", "").strip()
    dep    = data.get("dep", "").strip()
    if not target or not dep:
        return jsonify({"ok": False, "reason": "Missing 'target' or 'dep' field."}), 400
    DEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
    DEPENDS_TRIGGER.write_text(json.dumps({"target": target, "dep": dep}), encoding="utf-8")
    return jsonify({"ok": True, "target": target, "dep": dep}), 202


@app.post("/undepends")
def remove_depends():
    """Remove a task dependency (writes undepends_trigger.json)."""
    data   = request.get_json(force=True, silent=True) or {}
    target = data.get("target", "").strip()
    dep    = data.get("dep", "").strip()
    if not target or not dep:
        return jsonify({"ok": False, "reason": "Missing 'target' or 'dep' field."}), 400
    UNDEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
    UNDEPENDS_TRIGGER.write_text(json.dumps({"target": target, "dep": dep}), encoding="utf-8")
    return jsonify({"ok": True, "target": target, "dep": dep}), 202


@app.post("/reset")
def reset_dag():
    """Reset the DAG to initial state (requires confirm=yes in body)."""
    data = request.get_json(force=True, silent=True) or {}
    if data.get("confirm", "").lower() != "yes":
        return jsonify({"ok": False, "reason": "Send {\"confirm\": \"yes\"} to confirm reset."}), 400
    RESET_TRIGGER.parent.mkdir(exist_ok=True)
    RESET_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@app.post("/snapshot")
def snapshot():
    """Trigger a PDF timeline snapshot (writes snapshot_trigger)."""
    SNAPSHOT_TRIGGER.parent.mkdir(exist_ok=True)
    SNAPSHOT_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@app.post("/pause")
def pause_auto():
    """Pause the auto-run (writes pause_trigger)."""
    PAUSE_TRIGGER.parent.mkdir(exist_ok=True)
    PAUSE_TRIGGER.write_text("1")
    return jsonify({"ok": True}), 202


@app.post("/resume")
def resume_auto():
    """Resume a paused auto-run (removes pause_trigger)."""
    try:
        if PAUSE_TRIGGER.exists():
            PAUSE_TRIGGER.unlink()
    except OSError:
        pass
    return jsonify({"ok": True}), 202


@app.get("/run/history")
def run_history():
    """Step execution log from meta_history as a JSON API.

    Query params:
        since  S — return only records with step_index > S
        limit  N — return the most recent N records (all if omitted or <= 0)
    """
    state = _load_state()
    meta_history = state.get("meta_history", [])
    cumulative = 0
    records = []
    for i, entry in enumerate(meta_history):
        v = entry.get("verified", 0)
        h = entry.get("healed", 0)
        cumulative += v
        records.append({"step_index": i + 1, "verified": v, "healed": h, "cumulative": cumulative})

    since = request.args.get("since", type=int)
    if since is not None and since >= 0:
        records = [r for r in records if r["step_index"] > since]

    limit = request.args.get("limit", type=int)
    if limit is not None and limit > 0:
        records = records[-limit:]

    return jsonify({"records": records, "count": len(records),
                    "total_steps": len(meta_history)})


# ---------------------------------------------------------------------------
# DAG import / export
# ---------------------------------------------------------------------------


@app.get("/tasks/export")
@app.get("/dag/export")
def dag_export():
    """Return the current DAG structure as a downloadable JSON file."""
    state = _load_state()
    payload = {
        "exported_step": state.get("step", 0),
        "dag": state.get("dag", {}),
    }
    import io
    data = json.dumps(payload, indent=2).encode("utf-8")
    from flask import Response
    return Response(
        data,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=dag_export.json"},
    )


@app.post("/dag/import")
def dag_import():
    """
    Replace the persisted DAG with one uploaded as JSON.
    Accepts either:
      - JSON body: {"dag": {...}}  (with optional "exported_step")
      - JSON body: the raw DAG object itself (top-level task keys)
    Writes dag_import_trigger.json so the CLI auto-loop picks it up.
    """
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    dag = body.get("dag") if "dag" in body else body
    if not isinstance(dag, dict):
        return jsonify({"error": "Invalid DAG structure"}), 400
    # Basic validation: each value must have a "branches" key
    for task_name, task_data in dag.items():
        if not isinstance(task_data, dict) or "branches" not in task_data:
            return jsonify({"error": f"Task '{task_name}' missing 'branches' key"}), 400
    trigger_path = DAG_IMPORT_TRIGGER
    trigger_path.parent.mkdir(exist_ok=True)
    trigger_path.write_text(json.dumps({
        "dag": dag,
        "exported_step": body.get("exported_step"),
    }), encoding="utf-8")
    return jsonify({"ok": True, "tasks": len(dag)}), 202


# ---------------------------------------------------------------------------
# GET /subtask/<subtask_id>  (TASK-076)
# ---------------------------------------------------------------------------

@app.get("/subtask/<subtask_id>")
def get_subtask(subtask_id: str):
    """Return current state of a named subtask (e.g. 'A1') across the DAG."""
    dag = _load_dag()
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            subtasks = branch_data.get("subtasks", {})
            if subtask_id in subtasks:
                st = subtasks[subtask_id]
                return jsonify({
                    "subtask": subtask_id,
                    "task": task_id,
                    "branch": branch_name,
                    "status": st.get("status", "Pending"),
                    "output": st.get("output", ""),
                    "history": st.get("history", []),
                })
    abort(404, description=f"Subtask '{subtask_id}' not found.")


@app.get("/subtask/<subtask_id>/output")
def get_subtask_output(subtask_id: str):
    """Return the raw output text of a named subtask as plain text."""
    dag = _load_dag()
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            subtasks = branch_data.get("subtasks", {})
            if subtask_id in subtasks:
                output = subtasks[subtask_id].get("output", "")
                return Response(output, mimetype="text/plain")
    abort(404, description=f"Subtask '{subtask_id}' not found.")


@app.post("/subtask/<subtask_id>/reset")
def reset_subtask(subtask_id: str):
    """Reset a subtask to Pending via heal_trigger.json.

    Composes on existing heal infrastructure; CLI SelfHealer consumes the trigger.
    Returns {ok, subtask, previous_status} or 404 if not found.
    """
    dag = _load_dag()
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            subtasks = branch_data.get("subtasks", {})
            if subtask_id in subtasks:
                prev = subtasks[subtask_id].get("status", "Pending")
                HEAL_TRIGGER.parent.mkdir(exist_ok=True)
                HEAL_TRIGGER.write_text(
                    json.dumps({"subtask": subtask_id}), encoding="utf-8"
                )
                return jsonify({
                    "ok": True,
                    "subtask": subtask_id,
                    "task": task_id,
                    "branch": branch_name,
                    "previous_status": prev,
                })
    abort(404, description=f"Subtask '{subtask_id}' not found.")


# ---------------------------------------------------------------------------
# POST /webhook  (TASK-078)
# ---------------------------------------------------------------------------

@app.post("/webhook")
def fire_webhook():
    """POST completion payload to WEBHOOK_URL if configured and pipeline is complete."""
    import urllib.request
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    total = verified = 0
    for t in dag.values():
        for b in t.get("branches", {}).values():
            for s in b.get("subtasks", {}).values():
                total += 1
                if s.get("status") == "Verified":
                    verified += 1
    pct = round(verified / total * 100, 1) if total else 0.0
    webhook_url = ""
    try:
        cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        webhook_url = cfg.get("WEBHOOK_URL", "")
    except Exception:
        pass
    if not webhook_url:
        return jsonify({"ok": False, "reason": "WEBHOOK_URL not configured"}), 200
    payload = json.dumps({
        "event": "complete",
        "step": step,
        "total": total,
        "verified": verified,
        "pct": pct,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            webhook_url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return jsonify({"ok": True, "sent": True, "url": webhook_url}), 200
    except Exception as exc:
        return jsonify({"ok": False, "sent": False, "error": str(exc)}), 200


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e)}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed."}), 405


if __name__ == "__main__":
    app.run(debug=False)
