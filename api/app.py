"""
Solo Builder REST API
Loads state from state/solo_builder_state.json on every request.

Install:  pip install flask
Run:      python api/app.py
          flask --app api/app.py run
"""

import json
import re
from pathlib import Path

from flask import Flask, jsonify, abort, send_from_directory, request

app = Flask(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH    = _PROJECT_ROOT / "state" / "solo_builder_state.json"
TRIGGER_PATH  = _PROJECT_ROOT / "state" / "run_trigger"
VERIFY_TRIGGER  = _PROJECT_ROOT / "state" / "verify_trigger.json"
DESCRIBE_TRIGGER = _PROJECT_ROOT / "state" / "describe_trigger.json"
TOOLS_TRIGGER   = _PROJECT_ROOT / "state" / "tools_trigger.json"
SET_TRIGGER     = _PROJECT_ROOT / "state" / "set_trigger.json"
HEARTBEAT_PATH = _PROJECT_ROOT / "state" / "step.txt"
JOURNAL_PATH  = _PROJECT_ROOT / "journal.md"
OUTPUTS_PATH  = _PROJECT_ROOT / "solo_builder_outputs.md"


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
