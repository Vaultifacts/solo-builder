"""Triggers blueprint — POST /verify, /describe, /tools, /rename, /heal, /add_task, /add_branch, /prioritize_branch, /depends, /undepends."""
import json

from flask import Blueprint, jsonify, request

from ..helpers import _write_trigger
from ..validators import require_string_fields

triggers_bp = Blueprint("triggers", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@triggers_bp.post("/verify")
def verify_subtask():
    """Queue a subtask verify via trigger file."""
    _app = _get_app()
    return _write_trigger(_app.VERIFY_TRIGGER, {"subtask": True, "note": False},
                          defaults={"note": "Dashboard verify"})


@triggers_bp.post("/describe")
def describe_subtask():
    """Queue a subtask describe via trigger file."""
    _app = _get_app()
    return _write_trigger(_app.DESCRIBE_TRIGGER, {"subtask": True, "desc": False})


@triggers_bp.post("/tools")
def tools_subtask():
    """Queue a subtask tools change via trigger file."""
    _app = _get_app()
    return _write_trigger(_app.TOOLS_TRIGGER, {"subtask": True, "tools": False})


@triggers_bp.post("/rename")
def rename_subtask():
    """Queue a subtask rename via trigger file."""
    _app = _get_app()
    return _write_trigger(_app.RENAME_TRIGGER, {"subtask": True, "desc": False})


@triggers_bp.post("/heal")
def heal():
    """Write heal_trigger.json so the CLI resets a Running subtask to Pending."""
    _app = _get_app()
    err = require_string_fields(("subtask",))
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    subtask = data["subtask"].strip().upper()
    _app.HEAL_TRIGGER.parent.mkdir(exist_ok=True)
    _app.HEAL_TRIGGER.write_text(json.dumps({"subtask": subtask}), encoding="utf-8")
    return jsonify({"ok": True, "subtask": subtask}), 202


@triggers_bp.post("/add_task")
def add_task():
    """Queue a new task (writes add_task_trigger.json)."""
    _app = _get_app()
    err = require_string_fields(("spec",))
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    spec = data["spec"].strip()
    _app.ADD_TASK_TRIGGER.parent.mkdir(exist_ok=True)
    _app.ADD_TASK_TRIGGER.write_text(json.dumps({"spec": spec}), encoding="utf-8")
    return jsonify({"ok": True, "spec": spec}), 202


@triggers_bp.post("/add_branch")
def add_branch():
    """Queue a new branch on an existing task (writes add_branch_trigger.json)."""
    _app = _get_app()
    err = require_string_fields(("task", "spec"))
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    task = data["task"].strip()
    spec = data["spec"].strip()
    _app.ADD_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
    _app.ADD_BRANCH_TRIGGER.write_text(json.dumps({"task": task, "spec": spec}), encoding="utf-8")
    return jsonify({"ok": True, "task": task, "spec": spec}), 202


@triggers_bp.post("/prioritize_branch")
def prioritize_branch():
    """Boost a branch to the front of the execution queue."""
    _app = _get_app()
    err = require_string_fields(("task", "branch"))
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    task   = data["task"].strip()
    branch = data["branch"].strip()
    _app.PRIORITY_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
    _app.PRIORITY_BRANCH_TRIGGER.write_text(json.dumps({"task": task, "branch": branch}), encoding="utf-8")
    return jsonify({"ok": True, "task": task, "branch": branch}), 202


@triggers_bp.post("/depends")
def add_depends():
    """Add a task dependency (writes depends_trigger.json)."""
    _app = _get_app()
    err = require_string_fields(("target", "dep"))
    if err:
        return err
    data   = request.get_json(force=True, silent=True) or {}
    target = data["target"].strip()
    dep    = data["dep"].strip()
    _app.DEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
    _app.DEPENDS_TRIGGER.write_text(json.dumps({"target": target, "dep": dep}), encoding="utf-8")
    return jsonify({"ok": True, "target": target, "dep": dep}), 202


@triggers_bp.post("/undepends")
def remove_depends():
    """Remove a task dependency (writes undepends_trigger.json)."""
    _app = _get_app()
    err = require_string_fields(("target", "dep"))
    if err:
        return err
    data   = request.get_json(force=True, silent=True) or {}
    target = data["target"].strip()
    dep    = data["dep"].strip()
    _app.UNDEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
    _app.UNDEPENDS_TRIGGER.write_text(json.dumps({"target": target, "dep": dep}), encoding="utf-8")
    return jsonify({"ok": True, "target": target, "dep": dep}), 202
