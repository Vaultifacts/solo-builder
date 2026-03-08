"""Export routes blueprint — GET/POST /export, GET /stats, /search, /journal."""
import re

from flask import Blueprint, jsonify, request, send_from_directory

from ..helpers import _load_state, _load_dag

export_bp = Blueprint("export", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@export_bp.get("/export")
def export_outputs():
    """Download all subtask outputs as a Markdown file."""
    _app = _get_app()
    if not _app.OUTPUTS_PATH.exists():
        return jsonify({"error": "No export file found. Run 'export' in the CLI first."}), 404
    return send_from_directory(
        _app.OUTPUTS_PATH.parent,
        _app.OUTPUTS_PATH.name,
        as_attachment=True,
        download_name="solo_builder_outputs.md",
        mimetype="text/markdown",
    )


@export_bp.post("/export")
def generate_export():
    """Regenerate solo_builder_outputs.md from current state, then serve it."""
    _app = _get_app()
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
    _app.OUTPUTS_PATH.parent.mkdir(exist_ok=True)
    _app.OUTPUTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    return send_from_directory(
        _app.OUTPUTS_PATH.parent,
        _app.OUTPUTS_PATH.name,
        as_attachment=True,
        download_name="solo_builder_outputs.md",
        mimetype="text/markdown",
    )


@export_bp.get("/stats")
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


@export_bp.get("/search")
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


@export_bp.get("/journal")
def journal():
    _app = _get_app()
    if not _app.JOURNAL_PATH.exists():
        return jsonify({"entries": []})
    content = _app.JOURNAL_PATH.read_text(encoding="utf-8")
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
