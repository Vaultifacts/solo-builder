"""
Solo Builder REST API
Loads state from state/solo_builder_state.json on every request.

Install:  pip install flask
Run:      python api/app.py
          flask --app api/app.py run
"""

import time

from flask import Flask, jsonify, request

from .middleware import SecurityHeadersMiddleware, ApiRateLimiter
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

_security = SecurityHeadersMiddleware()
_rate_limiter = ApiRateLimiter()

from .blueprints.cache import cache_bp
from .blueprints.metrics import metrics_bp
from .blueprints.history import history_bp
from .blueprints.triggers import triggers_bp
from .blueprints.subtasks import subtasks_bp
from .blueprints.control import control_bp
from .blueprints.config import config_bp
from .blueprints.tasks import tasks_bp
from .blueprints.branches import branches_bp
from .blueprints.export_routes import export_bp
from .blueprints.dag import dag_bp
from .blueprints.webhook import webhook_bp
from .blueprints.core import core_bp
from .blueprints.health_detailed import health_detailed_bp

app.register_blueprint(cache_bp)
app.register_blueprint(metrics_bp)
app.register_blueprint(history_bp)
app.register_blueprint(triggers_bp)
app.register_blueprint(subtasks_bp)
app.register_blueprint(control_bp)
app.register_blueprint(config_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(branches_bp)
app.register_blueprint(export_bp)
app.register_blueprint(dag_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(core_bp)
app.register_blueprint(health_detailed_bp)


@app.before_request
def _record_request_start():
    request._start_time = time.time()  # type: ignore[attr-defined]


@app.before_request
def rate_limit():
    ip    = request.remote_addr or "unknown"
    write = request.method in ("POST", "DELETE", "PUT", "PATCH")
    if not _rate_limiter.check(ip=ip, is_write=write):
        return jsonify({"error": "Rate limit exceeded. Try again shortly."}), 429


@app.after_request
def security_headers(resp):
    resp = _security.apply(resp)
    # X-Response-Time: elapsed milliseconds (OM-003)
    try:
        elapsed_ms = round((time.time() - request._start_time) * 1000)  # type: ignore[attr-defined]
        resp.headers["X-Response-Time"] = f"{elapsed_ms}ms"
    except AttributeError:
        pass
    return resp


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
