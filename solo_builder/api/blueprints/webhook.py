"""Webhook blueprint — POST /webhook."""
import json
import urllib.request
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from ..helpers import _load_state

webhook_bp = Blueprint("webhook", __name__)


def _get_app():
    from .. import app as _app_module
    return _app_module


@webhook_bp.post("/webhook")
def fire_webhook():
    """POST completion payload to WEBHOOK_URL if configured and pipeline is complete."""
    _app = _get_app()
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
        cfg = json.loads(_app.SETTINGS_PATH.read_text(encoding="utf-8"))
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
