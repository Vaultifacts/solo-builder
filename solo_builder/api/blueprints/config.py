"""Config blueprint — GET/POST /config, POST /config/reset, GET /config/export, GET /shortcuts, POST /set."""
import json

from flask import Blueprint, jsonify, request, Response

from ..helpers import _write_trigger

config_bp = Blueprint("config", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@config_bp.get("/config")
def config():
    """Expose runtime settings as JSON."""
    _app = _get_app()
    if not _app.SETTINGS_PATH.exists():
        return jsonify({"error": "Settings file not found."}), 404
    try:
        data = json.loads(_app.SETTINGS_PATH.read_text(encoding="utf-8"))
        return jsonify(data)
    except Exception:
        return jsonify({"error": "Could not read settings."}), 500


@config_bp.post("/config")
def update_config():
    """Merge posted keys into settings.json and return updated config."""
    _app = _get_app()
    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"ok": False, "reason": "No JSON body."}), 400
    if not _app.SETTINGS_PATH.exists():
        return jsonify({"error": "Settings file not found."}), 404
    try:
        data = json.loads(_app.SETTINGS_PATH.read_text(encoding="utf-8"))
        for key, val in body.items():
            if key not in data:
                return jsonify({"ok": False, "reason": f"Unknown key '{key}'."}), 400
            data[key] = val
        _app.SETTINGS_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return jsonify({"ok": True, **data})
    except Exception:
        return jsonify({"error": "Could not update settings."}), 500


@config_bp.get("/config/export")
def export_config():
    """Return settings.json as a downloadable JSON attachment."""
    _app = _get_app()
    if not _app.SETTINGS_PATH.exists():
        return jsonify({"error": "Settings file not found."}), 404
    try:
        data = _app.SETTINGS_PATH.read_bytes()
        return Response(
            data,
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=settings.json"},
        )
    except Exception:
        return jsonify({"error": "Could not read settings."}), 500


@config_bp.post("/config/reset")
def reset_config():
    """Restore config/settings.json to compiled-in defaults.

    Returns {ok, restored, config} where config is the resulting settings.
    409 if settings file does not exist.
    """
    _app = _get_app()
    if not _app.SETTINGS_PATH.exists():
        return jsonify({"ok": False, "reason": "Settings file not found."}), 409
    try:
        _app.SETTINGS_PATH.write_text(json.dumps(_app._CONFIG_DEFAULTS, indent=4), encoding="utf-8")
        return jsonify({"ok": True, "restored": True, "config": _app._CONFIG_DEFAULTS})
    except Exception as exc:
        return jsonify({"ok": False, "reason": str(exc)}), 500


@config_bp.get("/shortcuts")
def shortcuts():
    """Return all active keyboard shortcuts as a JSON array of {key, description}."""
    _app = _get_app()
    return jsonify({"shortcuts": _app._SHORTCUTS, "count": len(_app._SHORTCUTS)})


@config_bp.post("/set")
def set_setting():
    """Queue a settings change via trigger file."""
    _app = _get_app()
    return _write_trigger(_app.SET_TRIGGER, {"key": True, "value": False})
