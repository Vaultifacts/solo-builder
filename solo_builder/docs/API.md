# Solo Builder REST API Reference

Base URL: `http://127.0.0.1:5000`

All responses are JSON. POST endpoints return HTTP 202 on success; errors return 400 or 404.
CORS headers are set on all responses (`Access-Control-Allow-Origin: *`).

---

## GET Endpoints

### `GET /`
Serves the web dashboard HTML (`api/dashboard.html`).

### `GET /status`
DAG progress summary.
```json
{"step": 42, "total": 70, "verified": 35, "running": 4, "pending": 28, "review": 3, "percent": 50.0}
```

### `GET /tasks`
All tasks as a JSON array.
```json
[{"id": "Task 0", "status": "Verified", "branch_count": 2, "subtask_count": 10, "verified_subtasks": 10, ...}]
```

### `GET /tasks/<id>`
Single task detail including all branches and subtasks.

### `GET /tasks/<id>/trigger` → `POST /tasks/<id>/trigger`
Returns pending subtask list for a task (POST returns 202).
```json
{"id": "Task 0", "accepted": true, "status": "Running", "pending_subtasks": ["Branch A/A1"], "pending_count": 1}
```

### `GET /heartbeat`
Lightweight live counters from `state/step.txt` (no JSON parse of state file).
```json
{"step": 42, "verified": 35, "total": 70, "pending": 28, "running": 4, "review": 3}
```

### `GET /export`
Serve existing `solo_builder_outputs.md` (404 if not generated yet).

### `GET /stats`
Per-task breakdown: verified count, total, percent, avg steps.

### `GET /search?q=<keyword>`
Find subtasks by keyword in name/description/output. Returns array of matches.

### `GET /history?n=<int>`
Last N status transitions across all subtasks (default 20).

### `GET /diff`
Changes since last save (new subtasks, status changes).

### `GET /branches/<id>`
Branch detail for a task: subtask counts, statuses.

### `GET /timeline/<subtask>`
Status history timeline for a specific subtask (e.g. `/timeline/A1`).

### `GET /journal`
Journal entries from `journal.md`.

### `GET /config`
Contents of `config/settings.json`.

### `GET /graph`
Dependency graph as JSON: nodes (tasks) and edges (dependencies).

### `GET /priority`
Planner priority queue — subtasks ranked by risk score.

### `GET /stalled`
Subtasks stuck longer than `STALL_THRESHOLD` steps.

### `GET /agents`
Agent statistics: Planner cache, Executor throughput, SelfHealer counts, MetaOptimizer rates, forecast.

### `GET /forecast`
Completion forecast.
```json
{"percent_complete": 50.0, "verified_per_step": 2.1, "eta_steps": 17, "verified": 35, "total": 70, "stalled_count": 0}
```

---

## POST Endpoints

### `POST /run`
Trigger one CLI step. Returns `{"ok": true, "step": N}` or `{"ok": false, "reason": "pipeline already complete"}`.

### `POST /stop`
Write `state/stop_trigger` — CLI halts after the current step.

### `POST /pause`
Write `state/pause_trigger` — CLI pauses the auto-run after the current step.

### `POST /resume`
Remove `state/pause_trigger` — resumes a paused auto-run.

### `POST /verify`
Queue a subtask verify via `state/verify_trigger.json`.
```json
{"subtask": "A1", "note": "Looks good"}
```

### `POST /describe`
Set a custom Claude prompt for a subtask.
```json
{"subtask": "A1", "desc": "Write a detailed design document for the auth module"}
```

### `POST /tools`
Set allowed tools for a subtask.
```json
{"subtask": "O1", "tools": "Read,Glob,Grep"}
```

### `POST /rename`
Update a subtask's description.
```json
{"subtask": "A1", "desc": "New description text"}
```

### `POST /heal`
Reset a Running subtask to Pending.
```json
{"subtask": "A1"}
```

### `POST /add_task`
Queue a new task (added at next CLI step boundary).
```json
{"spec": "Build OAuth2 integration | depends: 5"}
```

### `POST /add_branch`
Queue a new branch on an existing task.
```json
{"task": "0", "spec": "Add error handling"}
```

### `POST /prioritize_branch`
Boost a branch's Pending subtasks to front of the priority queue.
```json
{"task": "0", "branch": "A"}
```

### `POST /depends`
Add a task dependency.
```json
{"target": "1", "dep": "0"}
```

### `POST /undepends`
Remove a task dependency.
```json
{"target": "1", "dep": "0"}
```

### `POST /undo`
Restore from the pre-step backup (writes `state/undo_trigger`).

### `POST /reset`
Reset DAG to initial state. **Destructive — requires confirmation.**
```json
{"confirm": "yes"}
```

### `POST /snapshot`
Trigger a PDF timeline snapshot at the next CLI step boundary.

### `POST /export`
Generate `solo_builder_outputs.md` from all subtask Claude outputs.
Returns the file content as `text/markdown`.

### `POST /set`
Change a runtime setting (queued via trigger file).
```json
{"key": "REVIEW_MODE", "value": "true"}
```

### `POST /config`
Directly update `config/settings.json` (no trigger file — takes effect on next read).
```json
{"ANTHROPIC_MAX_TOKENS": 512}
```

---

## DAG Import / Export

### `GET /dag/export`
Download the current DAG structure as a JSON file attachment.

**Response** (`application/json`, `Content-Disposition: attachment; filename=dag_export.json`):
```json
{
  "exported_step": 42,
  "dag": {
    "Task 0": { "status": "Verified", "depends_on": [], "branches": { ... } },
    ...
  }
}
```

### `POST /dag/import`
Replace the CLI's live DAG with an imported one. Writes `state/dag_import_trigger.json`; the
CLI auto-loop consumes it at the next delay window (saves current state as undo backup first).

**Request body** — either wrapped:
```json
{"dag": { "Task 0": { ... }, ... }, "exported_step": 42}
```
or the raw DAG object (top-level task keys):
```json
{"Task 0": { "status": "Pending", "depends_on": [], "branches": { ... } }}
```

Each task must have a `"branches"` key; missing branches returns `400`.

**Response** `202`:
```json
{"ok": true, "tasks": 1}
```

---

## Metrics / Analytics

### `GET /metrics`
Return historical per-step metrics for analytics and charting.

**Response**:
```json
{
  "step": 42,
  "total_healed": 3,
  "summary": {
    "total_steps": 42,
    "total_verifies": 70,
    "avg_verified_per_step": 1.67,
    "peak_verified_per_step": 6,
    "steps_with_heals": 2
  },
  "history": [
    {"step_index": 1, "verified": 2, "healed": 0, "cumulative": 2},
    {"step_index": 2, "verified": 3, "healed": 1, "cumulative": 5},
    ...
  ]
}
```

Fields:
| Field | Description |
|-------|-------------|
| `step` | Current CLI step counter |
| `total_healed` | Lifetime SelfHealer resets |
| `summary.avg_verified_per_step` | Mean verified count per recorded step |
| `summary.peak_verified_per_step` | Highest single-step verified count |
| `summary.steps_with_heals` | Steps where at least one heal occurred |
| `history[].cumulative` | Running total of verified subtasks up to this step |

---

## Error Responses

All error responses use JSON:
```json
{"error": "description"}       // 404, 405
{"ok": false, "reason": "..."}  // 400 from POST validation
```
