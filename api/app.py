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
