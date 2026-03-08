# HANDOFF TO DEV (from ARCHITECT)

## Task
TASK-104

## Goal
Refactor `solo_builder/api/app.py` (1729 lines) into Flask Blueprints.
Each step must leave all 305 API tests green.

---

## Critical Constraint

`test_app.py` imports `from solo_builder.api.app import app` -- the `app` object MUST remain importable from `solo_builder/api/app.py` at all times.

---

## Implementation Plan

Execute steps in order. Commit after each step. Run `python -m pytest solo_builder/api/test_app.py -q` after each commit.

### Step 1 -- Extract constants and helpers

**Create `solo_builder/api/constants.py`:**
- Move all 21 path/trigger constants (lines 25-48): `STATE_PATH`, `TRIGGER_PATH`, `VERIFY_TRIGGER`, etc.
- Move `_CONFIG_DEFAULTS` dict (lines 847-869)
- Move `_SHORTCUTS` list (lines 888-899)
- Move `_AVG_TOKENS_PER_ENTRY`, `_STATS_FILE` (lines 1210-1213)
- Move `DAG_EXPORT_PATH`, `DAG_IMPORT_TRIGGER` (lines 1552-1553)
- Keep `_APP_START_TIME = time.time()` in `app.py` (must be set at startup, not import time of constants)

**Create `solo_builder/api/helpers.py`:**
- Move `_load_state()` (lines 55-60)
- Move `_load_dag()` (lines 63-64)
- Move `_write_trigger()` (lines 67-83)
- Move `_task_summary()` (lines 86-107)
- Move `_load_cumulative_stats()` (lines 1216-1222)
- Import constants from `constants.py`

**In `app.py`:** replace moved blocks with imports from `constants` and `helpers`.

### Step 2 -- Extract cache blueprint

**Create `solo_builder/api/blueprints/__init__.py`** (empty)

**Create `solo_builder/api/blueprints/cache.py`:**
- Blueprint: `cache_bp = Blueprint('cache', __name__)`
- Move routes: `GET /cache`, `DELETE /cache`, `GET /cache/history`, `GET /cache/export`
- Move helper: `_load_cumulative_stats()` (or import from helpers)
- Move constants: `_AVG_TOKENS_PER_ENTRY`, `_STATS_FILE` (or import from constants)

**In `app.py`:** `from .blueprints.cache import cache_bp; app.register_blueprint(cache_bp)`

### Step 3 -- Extract metrics blueprint

**Create `solo_builder/api/blueprints/metrics.py`:**
- Blueprint: `metrics_bp = Blueprint('metrics', __name__)`
- Move routes: `GET /metrics`, `GET /metrics/export`, `GET /agents`, `GET /forecast`
- Hoist inline `import time as _time` inside `metrics()` to module top

### Step 4 -- Extract history blueprint

**Create `solo_builder/api/blueprints/history.py`:**
- Blueprint: `history_bp = Blueprint('history', __name__)`
- Move routes: `GET /history`, `GET /history/count`, `GET /history/export`, `GET /diff`, `GET /dag/diff`, `GET /run/history`
- Inner function `_status_at` inside `dag_diff()` stays with it

### Step 5 -- Extract triggers blueprint

**Create `solo_builder/api/blueprints/triggers.py`:**
- Blueprint: `triggers_bp = Blueprint('triggers', __name__)`
- Move routes: `POST /verify`, `/describe`, `/tools`, `/rename`, `/heal`, `/add_task`, `/add_branch`, `/prioritize_branch`, `/depends`, `/undepends`
- All use `_write_trigger()` from helpers

### Step 6 -- Extract remaining blueprints (one commit each)

**`blueprints/subtasks.py`** (`subtasks_bp`):
- `GET /subtasks`, `GET /subtasks/export`, `GET /subtask/<id>`, `GET /subtask/<id>/output`, `POST /subtask/<id>/reset`, `GET /timeline/<subtask>`, `GET /stalled`

**`blueprints/control.py`** (`control_bp`):
- `POST /run`, `/stop`, `/pause`, `/resume`, `/undo`, `/snapshot`, `/reset`

**`blueprints/config.py`** (`config_bp`):
- `GET/POST /config`, `POST /config/reset`, `GET /shortcuts`, `POST /set`

**`blueprints/tasks.py`** (`tasks_bp`):
- `GET /tasks`, `GET /tasks/<id>`, `POST /tasks/<id>/trigger`, `GET /graph`, `GET /priority`

**`blueprints/branches.py`** (`branches_bp`):
- `GET /branches`, `GET /branches/<task_id>`

**`blueprints/export_routes.py`** (`export_bp`):
- `GET/POST /export`, `GET /stats`, `GET /search`, `GET /journal`

**`blueprints/dag.py`** (`dag_bp`):
- `GET /tasks/export`, `GET /dag/export`, `POST /dag/import`
- Hoist inline `import io` and `from flask import Response` to module top

**`blueprints/webhook.py`** (`webhook_bp`):
- `POST /webhook`
- Hoist `import urllib.request` to module top

**`blueprints/core.py`** (`core_bp`):
- `GET /`, `GET /status`, `GET /heartbeat`, `GET /health`

### Step 7 -- Update allowed_files.txt

Add all new files.

---

## Allowed Changes

```
solo_builder/api/app.py
solo_builder/api/constants.py          (NEW)
solo_builder/api/helpers.py            (NEW)
solo_builder/api/blueprints/__init__.py (NEW)
solo_builder/api/blueprints/cache.py   (NEW)
solo_builder/api/blueprints/metrics.py (NEW)
solo_builder/api/blueprints/history.py (NEW)
solo_builder/api/blueprints/triggers.py (NEW)
solo_builder/api/blueprints/subtasks.py (NEW)
solo_builder/api/blueprints/control.py  (NEW)
solo_builder/api/blueprints/config.py   (NEW)
solo_builder/api/blueprints/tasks.py    (NEW)
solo_builder/api/blueprints/branches.py (NEW)
solo_builder/api/blueprints/export_routes.py (NEW)
solo_builder/api/blueprints/dag.py      (NEW)
solo_builder/api/blueprints/webhook.py  (NEW)
solo_builder/api/blueprints/core.py     (NEW)
claude/allowed_files.txt
```

---

## Acceptance Criteria

1. `python -m pytest solo_builder/api/test_app.py -q` -- all 305 tests pass
2. `python -m pytest solo_builder/discord_bot/test_bot.py solo_builder/tests/test_cache.py -q` -- all pass
3. `wc -l solo_builder/api/app.py` -- reduced by at least 1500 lines from 1729
4. `from solo_builder.api.app import app` works (critical for test_app.py)
5. All new files in `claude/allowed_files.txt`
6. No logic changes -- move code only

---

## Constraints

- Do NOT change any route URLs, request/response shapes, or status codes
- Do NOT touch `test_app.py` or `test_bot.py`
- Use relative imports within the `api` package (e.g. `from ..helpers import _load_state`)
- Commit after each step so failures are bisectable
- Hoist inline imports to module top when extracting (not a logic change)
