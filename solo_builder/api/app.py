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
import os
import re
from pathlib import Path

from flask import Flask, jsonify, abort, send_from_directory, request, Response

app = Flask(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH    = _PROJECT_ROOT / "state" / "solo_builder_state.json"
TRIGGER_PATH  = _PROJECT_ROOT / "state" / "run_trigger"
VERIFY_TRIGGER  = _PROJECT_ROOT / "state" / "verify_trigger.json"
DESCRIBE_TRIGGER = _PROJECT_ROOT / "state" / "describe_trigger.json"
TOOLS_TRIGGER   = _PROJECT_ROOT / "state" / "tools_trigger.json"
SET_TRIGGER     = _PROJECT_ROOT / "state" / "set_trigger.json"
SETTINGS_PATH   = _PROJECT_ROOT / "config" / "settings.json"
RENAME_TRIGGER  = _PROJECT_ROOT / "state" / "rename_trigger.json"
STOP_TRIGGER    = _PROJECT_ROOT / "state" / "stop_trigger"
HEAL_TRIGGER    = _PROJECT_ROOT / "state" / "heal_trigger.json"
ADD_TASK_TRIGGER        = _PROJECT_ROOT / "state" / "add_task_trigger.json"
ADD_BRANCH_TRIGGER      = _PROJECT_ROOT / "state" / "add_branch_trigger.json"
PRIORITY_BRANCH_TRIGGER = _PROJECT_ROOT / "state" / "prioritize_branch_trigger.json"
UNDO_TRIGGER            = _PROJECT_ROOT / "state" / "undo_trigger"
DEPENDS_TRIGGER         = _PROJECT_ROOT / "state" / "depends_trigger.json"
UNDEPENDS_TRIGGER       = _PROJECT_ROOT / "state" / "undepends_trigger.json"
RESET_TRIGGER           = _PROJECT_ROOT / "state" / "reset_trigger"
SNAPSHOT_TRIGGER        = _PROJECT_ROOT / "state" / "snapshot_trigger"
PAUSE_TRIGGER           = _PROJECT_ROOT / "state" / "pause_trigger"
HEARTBEAT_PATH = _PROJECT_ROOT / "state" / "step.txt"
JOURNAL_PATH  = _PROJECT_ROOT / "journal.md"
OUTPUTS_PATH  = _PROJECT_ROOT / "solo_builder_outputs.md"
CACHE_DIR     = Path(os.environ.get("CACHE_DIR",
                     str(_PROJECT_ROOT.parent / "claude" / "cache")))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dag": {}, "step": 0}


def _load_dag() -> dict:
    return _load_state().get("dag", {})


def _write_trigger(path: Path, fields: dict[str, bool],
                   defaults: dict | None = None) -> tuple:
    """Parse body, validate, write trigger JSON.  fields maps name→uppercase."""
    body = request.get_json(silent=True) or {}
    defs = defaults or {}
    payload = {}
    for key, upper in fields.items():
        val = (body.get(key) or defs.get(key, "")).strip()
        if upper:
            val = val.upper()
        if not val:
            return jsonify({"ok": False,
                            "reason": f"Missing '{key}' field."}), 400
        payload[key] = val
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return jsonify({"ok": True, **payload}), 202


def _task_summary(task_id: str, task: dict) -> dict:
    branches      = task.get("branches", {})
    subtask_count = sum(len(b.get("subtasks", {})) for b in branches.values())
    verified      = sum(
        1 for b in branches.values()
        for s in b.get("subtasks", {}).values()
        if s.get("status") == "Verified"
    )
    running = sum(
        1 for b in branches.values()
        for s in b.get("subtasks", {}).values()
        if s.get("status") == "Running"
    )
    return {
        "id":               task_id,
        "status":           task.get("status"),
        "depends_on":       task.get("depends_on", []),
        "branch_count":     len(branches),
        "subtask_count":    subtask_count,
        "verified_subtasks": verified,
        "running_subtasks": running,
    }


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
    total    = sum(len(b["subtasks"]) for t in dag.values() for b in t["branches"].values())
    verified = sum(
        1 for t in dag.values() for b in t["branches"].values()
        for s in b["subtasks"].values() if s.get("status") == "Verified"
    )
    running = sum(
        1 for t in dag.values() for b in t["branches"].values()
        for s in b["subtasks"].values() if s.get("status") == "Running"
    )
    return jsonify({
        "step":      state.get("step", 0),
        "total":     total,
        "verified":  verified,
        "running":   running,
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
    """Aggregated step-by-step activity log across all subtasks."""
    dag = _load_dag()
    limit = request.args.get("limit", 30, type=int)
    events = []
    for task_id, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                for h in st_data.get("history", []):
                    events.append({
                        "step": h.get("step", 0),
                        "subtask": st_name,
                        "task": task_id,
                        "branch": branch_name,
                        "status": h.get("status", "?"),
                    })
    events.sort(key=lambda e: e["step"], reverse=True)
    return jsonify({"events": events[:limit]})


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


@app.get("/agents")
def agents():
    """Return agent statistics as JSON."""
    state = _load_state()
    dag = state.get("dag", {})
    step = state.get("step", 0)
    healed = state.get("healed_total", 0)
    meta_history = state.get("meta_history", [])
    threshold = 5
    max_per_step = 6
    try:
        cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
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


@app.get("/forecast")
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


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_AVG_TOKENS_PER_ENTRY = 550  # matches ResponseCache._AVG_TOKENS_PER_ENTRY


_STATS_FILE = "session_stats.json"


def _load_cumulative_stats() -> dict:
    """Read cumulative hit/miss totals from session_stats.json; returns zeros on error."""
    try:
        path = CACHE_DIR / _STATS_FILE
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@app.get("/cache")
def cache_stats():
    """Return response cache disk stats including cumulative hit/miss totals."""
    try:
        all_files = list(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []
        entries = [f for f in all_files if f.name != _STATS_FILE]
        size = len(entries)
    except Exception as exc:
        return jsonify({"error": f"Could not read cache directory: {exc}"}), 500
    cum = _load_cumulative_stats()
    cum_hits   = cum.get("cumulative_hits", 0)
    cum_misses = cum.get("cumulative_misses", 0)
    return jsonify({
        "entries":               size,
        "estimated_tokens_held": size * _AVG_TOKENS_PER_ENTRY,
        "cache_dir":             str(CACHE_DIR),
        "cumulative_hits":       cum_hits,
        "cumulative_misses":     cum_misses,
        "cumulative_total":      cum_hits + cum_misses,
        "cumulative_hit_rate":   round(cum_hits / (cum_hits + cum_misses) * 100, 1)
                                 if (cum_hits + cum_misses) > 0 else None,
    })


@app.delete("/cache")
def cache_clear():
    """Delete all cached response entries (preserves session_stats.json). Returns count deleted."""
    if not CACHE_DIR.exists():
        return jsonify({"ok": True, "deleted": 0})
    deleted = 0
    errors = 0
    try:
        for f in CACHE_DIR.glob("*.json"):
            if f.name == _STATS_FILE:
                continue  # preserve cumulative stats across manual clears
            try:
                f.unlink()
                deleted += 1
            except OSError:
                errors += 1
    except Exception as exc:
        return jsonify({"error": f"Could not clear cache: {exc}"}), 500
    return jsonify({"ok": True, "deleted": deleted, "errors": errors})


@app.get("/cache/history")
def cache_history():
    """Return per-session cache hit/miss history from session_stats.json."""
    try:
        path = CACHE_DIR / _STATS_FILE
        if not path.exists():
            return jsonify({"sessions": [], "cumulative_hits": 0, "cumulative_misses": 0})
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return jsonify({"error": f"Could not read cache history: {exc}"}), 500
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
    return jsonify({
        "sessions":          sessions,
        "cumulative_hits":   data.get("cumulative_hits", 0),
        "cumulative_misses": data.get("cumulative_misses", 0),
    })


# ---------------------------------------------------------------------------
# Metrics / analytics
# ---------------------------------------------------------------------------

@app.get("/metrics")
def metrics():
    """
    Return historical per-step metrics for analytics and charting.

    Response:
      step            — current step count
      total_healed    — lifetime heals by SelfHealer
      summary         — aggregate stats (avg rate, peak, etc.)
      history         — list of per-step records with cumulative counts
    """
    state = _load_state()
    meta_history = state.get("meta_history", [])
    step = state.get("step", 0)
    healed_total = state.get("healed_total", 0)

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
        "step":         step,
        "total_healed": healed_total,
        "summary": {
            "total_steps":            n,
            "total_verifies":         total_verifies,
            "avg_verified_per_step":  avg_rate,
            "peak_verified_per_step": peak_verified,
            "steps_with_heals":       steps_with_heals,
        },
        "history": history,
    })


@app.get("/metrics/export")
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


# ---------------------------------------------------------------------------
# DAG import / export
# ---------------------------------------------------------------------------

DAG_EXPORT_PATH      = _PROJECT_ROOT / "dag_export.json"
DAG_IMPORT_TRIGGER   = _PROJECT_ROOT / "state" / "dag_import_trigger.json"


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
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e)}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed."}), 405


if __name__ == "__main__":
    app.run(debug=True)
