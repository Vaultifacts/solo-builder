# HANDOFF: RESEARCH -> ARCHITECT
Task: TASK-104
Goal: Refactor solo_builder/api/app.py (1729 lines) into focused modules

---

## File Structure Summary

`solo_builder/api/app.py` is 1729 lines containing:
- 60+ route handlers spread across one flat file
- 7 helper/utility functions
- 21 trigger/path constants (lines 25-48)
- `_CONFIG_DEFAULTS` dict (lines 847-869)
- `_SHORTCUTS` list (lines 888-899)
- No blueprints, no factory pattern

---

## Route Groupings (proposed blueprints)

| Blueprint | Routes | Est. Lines |
|-----------|--------|-----------|
| core_bp | GET /, /status, /heartbeat, /health | ~80 |
| tasks_bp | GET /tasks, /tasks/<id>, POST /tasks/<id>/trigger, GET /graph, /priority | ~120 |
| control_bp | POST /run, /stop, /pause, /resume, /undo, /snapshot, /reset | ~90 |
| subtasks_bp | GET/POST /subtask/<id>, /subtask/<id>/output, /subtask/<id>/reset, /subtasks, /subtasks/export, /timeline/<id>, /stalled | ~250 |
| branches_bp | GET /branches, /branches/<task_id> | ~55 |
| history_bp | GET /history, /history/count, /history/export, /diff, /dag/diff, /run/history | ~220 |
| config_bp | GET/POST /config, POST /config/reset, GET /shortcuts, POST /set | ~100 |
| export_bp | GET/POST /export, GET /stats, /search, /journal | ~170 |
| dag_bp | GET /tasks/export, /dag/export, POST /dag/import | ~60 |
| cache_bp | GET/DELETE /cache, GET /cache/history, /cache/export | ~160 |
| metrics_bp | GET /metrics, /metrics/export, /agents, /forecast | ~180 |
| triggers_bp | POST /verify, /describe, /tools, /rename, /heal, /add_task, /add_branch, /prioritize_branch, /depends, /undepends | ~110 |
| webhook_bp | POST /webhook | ~45 |

---

## Top 5 Largest Functions

| Rank | Function | Lines |
|------|----------|-------|
| 1 | `metrics()` | ~100 |
| 2 | `cache_export()` | ~58 |
| 3 | `dag_diff()` | ~49 |
| 4 | `agents()` | ~49 |
| 5 | `history()` | ~48 |

---

## Key Findings

1. **No blueprint structure** -- 60+ routes in one flat file. Comment banners already mark natural split points (`# Cache`, `# Metrics / analytics`, `# DAG import / export`).
2. **`_load_state()` called on every request** with full JSON file read (no caching) -- 13 routes call it.
3. **`_load_dag()` called by 18 routes** -- thin wrapper over `_load_state()["dag"]`.
4. **`_write_trigger()` is the one abstraction** -- used by 5 routes cleanly; 8 more manual trigger-writes follow the same pattern but don't use it.
5. **Inline imports** inside functions (`urllib.request`, redundant `io`, `flask.Response`) at lines 1565-1567, 1383, 1674 -- should be hoisted.
6. **STALL_THRESHOLD read from disk** in 4+ routes independently -- duplicated logic.
7. **File is fully self-contained** -- no imports of other solo_builder modules (reads state from JSON files directly).

---

## Hypotheses

1. Flask Blueprints are the right abstraction -- each blueprint registers its own routes, shares helpers via imports from a `api/helpers.py` module.
2. `_load_state()`, `_load_dag()`, `_write_trigger()`, `_task_summary()` belong in `api/helpers.py` -- all blueprints import from there.
3. Module-level constants (21 path constants, `_CONFIG_DEFAULTS`, `_SHORTCUTS`, `_APP_START_TIME`) belong in `api/constants.py`.
4. All 305 existing API tests (`test_app.py`) must pass after every incremental commit -- the test suite imports `app` from `solo_builder.api.app`, so `app` must remain importable from there.
5. The `app` object must stay in `app.py` (or be re-exported from it) since `test_app.py` does `from solo_builder.api.app import app`.
6. Blueprints can be extracted one at a time -- each is independently testable.

---

## Recommended Incremental Order

1. Extract constants to `api/constants.py` -- zero risk
2. Extract helpers to `api/helpers.py` (`_load_state`, `_load_dag`, `_write_trigger`, `_task_summary`, `_load_cumulative_stats`) -- low risk
3. Extract `cache_bp` to `api/blueprints/cache.py` -- self-contained, good first blueprint
4. Extract `metrics_bp` to `api/blueprints/metrics.py` -- large, independent
5. Extract `history_bp` to `api/blueprints/history.py`
6. Extract `triggers_bp` to `api/blueprints/triggers.py` -- all use `_write_trigger`
7. Extract `subtasks_bp`, `branches_bp`, `tasks_bp`, `control_bp`, `config_bp`, `export_bp`, `dag_bp`, `webhook_bp`, `core_bp` in remaining commits
8. `app.py` becomes thin: imports, app object, blueprint registration, error handlers only
