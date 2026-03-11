# HANDOFF: RESEARCH -> ARCHITECT
Task: TASK-384
Goal: OpenAPIExportRoutes — add 5 missing export routes to generate_openapi.py spec

---

## File Analysis

`tools/generate_openapi.py` — _ROUTES list (lines 30-96):
- Currently 51 routes across 14 tags
- Missing 5 routes from `solo_builder/api/blueprints/export_routes.py`

`solo_builder/api/blueprints/export_routes.py` — routes NOT in spec:
- `GET /export` — Download subtask outputs as Markdown (line 16)
- `POST /export` — Regenerate solo_builder_outputs.md then serve (line 31)
- `GET /stats` — Per-task breakdown: verified, total, pct, avg steps (line 74)
- `GET /search` — Search subtasks by keyword in name/description/output (line 110)
- `GET /journal` — Last 30 journal entries parsed from journal.md (line 134)

## Scope Boundary

- In scope: `tools/generate_openapi.py`, `solo_builder/tests/test_generate_openapi.py`
- Out of scope: all blueprints, dashboard, all other files
- New tag: "Export" for all 5 routes

## Implementation Plan

In `_ROUTES`, append after the Webhook section (line 81-82):
```python
# Export
{"path": "/export",  "method": "GET",  "tag": "Export", "summary": "Download subtask outputs as Markdown"},
{"path": "/export",  "method": "POST", "tag": "Export", "summary": "Regenerate outputs file then download"},
{"path": "/stats",   "method": "GET",  "tag": "Export", "summary": "Per-task verified/total/pct/avg-steps breakdown"},
{"path": "/search",  "method": "GET",  "tag": "Export", "summary": "Search subtasks by keyword in name, description, or output"},
{"path": "/journal", "method": "GET",  "tag": "Export", "summary": "Last 30 journal entries"},
```

In `test_generate_openapi.py`, add 5 new route presence assertions.
