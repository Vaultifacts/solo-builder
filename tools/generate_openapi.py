"""OpenAPI 3.0 spec generator for Solo Builder REST API (TASK-345, DK-005, DK-006).

Introspects all registered Flask blueprints and generates a machine-readable
OpenAPI 3.0 spec. Outputs JSON (default) or YAML (if pyyaml is installed).

Usage:
    python tools/generate_openapi.py [--output PATH] [--format json|yaml] [--quiet]

Exit codes:
    0 — spec written / printed successfully
    1 — error generating spec
    2 — usage error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Route introspection
# ---------------------------------------------------------------------------

# Hand-curated route catalogue.  Flask's app.url_map is authoritative but
# requires a running app context; to keep this tool dependency-free we
# maintain the catalogue here and validate it with tests.
_ROUTES: list[dict] = [
    # Core
    {"path": "/",               "method": "GET",    "tag": "Core",       "summary": "Dashboard HTML"},
    {"path": "/status",         "method": "GET",    "tag": "Core",       "summary": "Task/branch status summary",
     "response": {"type": "object", "properties": {
         "step":     {"type": "integer"}, "total":    {"type": "integer"},
         "verified": {"type": "integer"}, "running":  {"type": "integer"},
         "review":   {"type": "integer"}, "stalled":  {"type": "integer"},
         "pending":  {"type": "integer"}, "pct":      {"type": "number"},
         "complete": {"type": "boolean"},
     }}},
    {"path": "/heartbeat",      "method": "GET",    "tag": "Core",       "summary": "Lightweight step counter",
     "response": {"type": "object", "properties": {
         "step":     {"type": "integer"}, "verified": {"type": "integer"},
         "total":    {"type": "integer"}, "pending":  {"type": "integer"},
         "running":  {"type": "integer"}, "review":   {"type": "integer"},
     }}},
    {"path": "/health",         "method": "GET",    "tag": "Core",       "summary": "Extended health probe (version, uptime, subtask count)",
     "response": {"type": "object", "properties": {
         "ok":                 {"type": "boolean"}, "version":          {"type": "string"},
         "uptime_s":           {"type": "number"},  "step":             {"type": "integer"},
         "state_file_exists":  {"type": "boolean"}, "total_subtasks":   {"type": "integer"},
     }}},
    # Metrics
    {"path": "/metrics",        "method": "GET",    "tag": "Metrics",    "summary": "Run health + analytics history",
     "response": {"type": "object", "properties": {
         "steps":   {"type": "integer"}, "healed":   {"type": "integer"},
         "verified":{"type": "integer"},
     }}},
    {"path": "/metrics/summary","method": "GET",    "tag": "Metrics",    "summary": "Executor step metrics (p50/p95/p99/latency buckets)",
     "response": {"type": "object", "properties": {
         "count":  {"type": "integer"}, "p50": {"type": "number"},
         "p99":    {"type": "number"},  "min": {"type": "number"},
         "max":    {"type": "number"},
     }}},
    {"path": "/metrics/export", "method": "GET",    "tag": "Metrics",    "summary": "Export step history as CSV or JSON",
     "query": [("format", "string", "Output format: csv or json (default json)")]},
    {"path": "/agents",         "method": "GET",    "tag": "Metrics",    "summary": "Agent statistics and ETA forecast",
     "response": {"type": "object", "properties": {
         "agents":   {"type": "array", "items": {"type": "object"}},
         "forecast": {"type": "string"},
     }}},
    {"path": "/forecast",       "method": "GET",    "tag": "Metrics",    "summary": "Detailed completion forecast",
     "response": {"type": "object", "properties": {
         "forecast": {"type": "string"}, "pct_done": {"type": "number"},
     }}},
    # History
    {"path": "/history",        "method": "GET",    "tag": "History",    "summary": "Paged activity log",
     "query": [("since", "integer", "Return events after this step number"),
               ("limit", "integer", "Max events to return (default 50)"),
               ("page",  "integer", "Page number (1-based)")],
     "response": {"type": "object", "properties": {
         "events": {"type": "array",   "items": {"type": "object"}},
         "total":  {"type": "integer"}, "review": {"type": "integer"},
         "page":   {"type": "integer"}, "pages":  {"type": "integer"},
     }}},
    {"path": "/history/count",  "method": "GET",    "tag": "History",    "summary": "Activity log counts by status",
     "response": {"type": "object", "properties": {
         "total":    {"type": "integer"}, "filtered": {"type": "integer"},
         "by_status": {"type": "object"},
     }}},
    # Tasks
    {"path": "/tasks",          "method": "GET",    "tag": "Tasks",      "summary": "List all tasks",
     "response": {"type": "object", "properties": {
         "tasks": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/tasks/{task_id}","method": "GET",    "tag": "Tasks",      "summary": "Get task detail",
     "response": {"type": "object", "properties": {
         "task_id":  {"type": "string"}, "branches": {"type": "object"},
     }}},
    {"path": "/tasks/{task_id}/progress", "method": "GET", "tag": "Tasks", "summary": "Branch progress for a task"},
    {"path": "/tasks/{task_id}/reset",    "method": "POST","tag": "Tasks", "summary": "Reset non-Verified subtasks"},
    # Branches
    {"path": "/branches",       "method": "GET",    "tag": "Branches",   "summary": "List all branches",
     "response": {"type": "object", "properties": {
         "branches": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/branches/{task_id}", "method": "GET", "tag": "Branches","summary": "Get branches and subtasks for a specific task",
     "response": {"type": "object", "properties": {
         "task_id":  {"type": "string"}, "branches": {"type": "object"},
     }}},
    # Subtasks
    {"path": "/subtasks",       "method": "GET",    "tag": "Subtasks",   "summary": "List all subtasks",
     "response": {"type": "object", "properties": {
         "subtasks": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/subtasks/bulk-reset", "method": "POST","tag": "Subtasks", "summary": "Bulk-reset selected subtasks"},
    {"path": "/stalled",        "method": "GET",    "tag": "Subtasks",   "summary": "List stalled subtasks (Running >= threshold)",
     "response": {"type": "object", "properties": {
         "stalled": {"type": "array", "items": {"type": "object"}},
         "count":   {"type": "integer"},
     }}},
    # Triggers
    {"path": "/verify",         "method": "POST",   "tag": "Triggers",   "summary": "Trigger subtask verification",
     "body": {"subtask": {"type": "string", "description": "Subtask name to verify"}}},
    {"path": "/describe",       "method": "POST",   "tag": "Triggers",   "summary": "Trigger subtask description update",
     "body": {"subtask": {"type": "string"}}},
    {"path": "/set",            "method": "POST",   "tag": "Triggers",   "summary": "Set a config value at runtime",
     "body": {"key": {"type": "string"}, "value": {"type": "string"}}},
    # Control
    {"path": "/pause",          "method": "POST",   "tag": "Control",    "summary": "Pause orchestration"},
    {"path": "/resume",         "method": "POST",   "tag": "Control",    "summary": "Resume orchestration"},
    {"path": "/stop",           "method": "POST",   "tag": "Control",    "summary": "Stop orchestration"},
    {"path": "/heal",           "method": "POST",   "tag": "Control",    "summary": "Trigger self-healer"},
    {"path": "/undo",           "method": "POST",   "tag": "Control",    "summary": "Undo last operation"},
    {"path": "/reset",          "method": "POST",   "tag": "Control",    "summary": "Reset workflow state"},
    {"path": "/snapshot",       "method": "POST",   "tag": "Control",    "summary": "Create state snapshot"},
    # Config
    {"path": "/config",         "method": "GET",    "tag": "Config",     "summary": "Get current configuration",
     "response": {"type": "object", "properties": {
         "settings": {"type": "object"},
     }}},
    {"path": "/config",         "method": "POST",   "tag": "Config",     "summary": "Update configuration",
     "body": {"key": {"type": "string"}, "value": {}}},
    # DAG
    {"path": "/dag/summary",    "method": "GET",    "tag": "DAG",        "summary": "DAG pipeline summary with per-task breakdown",
     "response": {"type": "object", "properties": {
         "total":    {"type": "integer"}, "verified": {"type": "integer"},
         "pending":  {"type": "integer"}, "tasks":    {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/dag/import",     "method": "POST",   "tag": "DAG",        "summary": "Import DAG from JSON",
     "body": {"dag": {"type": "object", "description": "DAG structure to import"}}},
    {"path": "/dag/export",     "method": "GET",    "tag": "DAG",        "summary": "Export DAG as JSON"},
    # Export
    {"path": "/export",  "method": "GET",  "tag": "Export", "summary": "Download subtask outputs as Markdown"},
    {"path": "/export",  "method": "POST", "tag": "Export", "summary": "Regenerate outputs file then download"},
    {"path": "/stats",   "method": "GET",  "tag": "Export", "summary": "Per-task verified/total/pct/avg-steps breakdown"},
    {"path": "/search",  "method": "GET",  "tag": "Export", "summary": "Search subtasks by keyword in name, description, or output",
     "query": [("q", "string", "Keyword to search for")]},
    {"path": "/journal", "method": "GET",  "tag": "Export", "summary": "Last 30 journal entries"},
    # Health (detailed checks)
    {"path": "/health/detailed",         "method": "GET", "tag": "Health", "summary": "Aggregate health: state validator + config drift + metrics alerts",
     "response": {"type": "object", "properties": {
         "overall_ok": {"type": "boolean"}, "checks": {"type": "object"},
     }}},
    {"path": "/health/context-window",   "method": "GET", "tag": "Health", "summary": "Context window line-count check (CLAUDE.md / MEMORY.md / JOURNAL.md)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "files": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/health/threat-model",     "method": "GET", "tag": "Health", "summary": "Threat model freshness check (SE-001 to SE-006)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "gaps": {"type": "array", "items": {"type": "string"}},
     }}},
    {"path": "/health/slo",              "method": "GET", "tag": "Health", "summary": "SLO status: SLO-003 success rate + SLO-005 latency median",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "violations": {"type": "array", "items": {"type": "string"}},
     }}},
    {"path": "/health/prompt-regression","method": "GET", "tag": "Health", "summary": "Prompt template regression check (AI-002, AI-003)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "failures": {"type": "array", "items": {"type": "string"}},
     }}},
    {"path": "/health/debt-scan",        "method": "GET", "tag": "Health", "summary": "Code debt scan: TODO/FIXME/HACK/XXX markers (capped at 20)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "count": {"type": "integer"},
         "items": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/health/ci-quality",       "method": "GET", "tag": "Health", "summary": "CI quality gate tool inventory (6 configured tools)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "tools": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/health/pre-release",      "method": "GET", "tag": "Health", "summary": "Pre-release gate inventory (builtin + VERIFY.json gates)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "gates": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/health/summary",          "method": "GET", "tag": "Health", "summary": "Aggregate health summary — state/settings/step/subtask checks",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "passed": {"type": "integer"}, "total": {"type": "integer"},
     }}},
    {"path": "/api/docs/ui",             "method": "GET", "tag": "Core",   "summary": "Swagger UI page for interactive API documentation"},
    {"path": "/api/docs",               "method": "GET", "tag": "Core",   "summary": "OpenAPI 3.0 JSON spec for all API routes",
     "response": {"type": "object", "properties": {
         "openapi": {"type": "string"}, "paths": {"type": "object"},
     }}},
    {"path": "/perf",                    "method": "GET", "tag": "Core",   "summary": "Backend performance metrics (state size, task/subtask counts)",
     "response": {"type": "object", "properties": {
         "state_size_bytes": {"type": "integer"}, "subtask_count": {"type": "integer"},
     }}},
    {"path": "/changes",                 "method": "GET", "tag": "Core",   "summary": "Lightweight change detection since a given step (TASK-412)",
     "response": {"type": "object", "properties": {
         "step": {"type": "integer"}, "since": {"type": "integer"},
         "changed": {"type": "boolean"}, "count": {"type": "integer"},
         "changes": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/health/aawo",             "method": "GET", "tag": "Health", "summary": "AAWO status: active agents, outcome stats, agent configs",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "available": {"type": "boolean"},
         "active_agents": {"type": "array"}, "outcome_stats": {"type": "object"},
     }}},
    {"path": "/health/live-summary",     "method": "GET", "tag": "Health", "summary": "Live in-process health summary (threat-model + context-window + slo)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "checks": {"type": "object"},
     }}},
    # Policy
    {"path": "/policy/hitl",             "method": "GET", "tag": "Policy", "summary": "HITL policy rules from settings.json",
     "response": {"type": "object", "properties": {
         "rules": {"type": "array", "items": {"type": "object"}},
     }}},
    {"path": "/policy/scope",            "method": "GET", "tag": "Policy", "summary": "Tool scope policy rules from settings.json",
     "response": {"type": "object", "properties": {
         "rules": {"type": "array", "items": {"type": "object"}},
     }}},
    # Cache (extended)
    {"path": "/cache",                   "method": "GET",    "tag": "Cache",    "summary": "Priority cache contents",
     "response": {"type": "object", "properties": {
         "entries":              {"type": "integer"}, "cumulative_hits":    {"type": "integer"},
         "cumulative_misses":    {"type": "integer"}, "cumulative_hit_rate":{"type": "number"},
         "estimated_tokens_held":{"type": "integer"}, "cache_dir":          {"type": "string"},
     }}},
    {"path": "/cache",                   "method": "DELETE", "tag": "Cache",    "summary": "Clear the priority cache (DELETE variant)",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "deleted": {"type": "integer"}, "errors": {"type": "integer"},
     }}},
    {"path": "/cache/export",            "method": "GET",    "tag": "Cache",    "summary": "Export cache as JSON"},
    {"path": "/cache/history",           "method": "GET",    "tag": "Cache",    "summary": "Cache operation history",
     "response": {"type": "object", "properties": {
         "sessions":          {"type": "array", "items": {"type": "object"}},
         "cumulative_hits":   {"type": "integer"},
         "cumulative_misses": {"type": "integer"},
     }}},
    # Tasks (extended)
    {"path": "/tasks/{task_id}/branches",  "method": "GET",  "tag": "Tasks",  "summary": "List branches for a task"},
    {"path": "/tasks/{task_id}/subtasks",  "method": "GET",  "tag": "Tasks",  "summary": "List subtasks for a task"},
    {"path": "/tasks/{task_id}/timeline",  "method": "GET",  "tag": "Tasks",  "summary": "Timeline of subtask events for a task"},
    {"path": "/tasks/{task_id}/export",    "method": "GET",  "tag": "Tasks",  "summary": "Export task data as JSON"},
    {"path": "/tasks/{task_id}/bulk-reset",  "method": "POST", "tag": "Tasks", "summary": "Bulk-reset subtasks in a task"},
    {"path": "/tasks/{task_id}/bulk-verify", "method": "POST", "tag": "Tasks", "summary": "Bulk-verify subtasks in a task"},
    {"path": "/tasks/{task_id}/trigger",     "method": "POST", "tag": "Tasks", "summary": "Fire execution trigger for a task"},
    {"path": "/tasks/export",              "method": "GET",  "tag": "Tasks",  "summary": "Export all tasks as JSON"},
    # Branches (extended)
    {"path": "/branches/{task_id}/reset",  "method": "POST", "tag": "Branches", "summary": "Reset branches for a task"},
    {"path": "/branches/export",           "method": "GET",  "tag": "Branches", "summary": "Export all branches as JSON"},
    # Subtasks (extended)
    {"path": "/subtask/{subtask_id}",        "method": "GET",  "tag": "Subtasks", "summary": "Get a single subtask by ID"},
    {"path": "/subtask/{subtask_id}/output", "method": "GET",  "tag": "Subtasks", "summary": "Get output for a single subtask"},
    {"path": "/subtask/{subtask_id}/reset",  "method": "POST", "tag": "Subtasks", "summary": "Reset a single subtask"},
    {"path": "/subtasks/bulk-verify",        "method": "POST", "tag": "Subtasks", "summary": "Bulk-verify selected subtasks"},
    {"path": "/subtasks/export",             "method": "GET",  "tag": "Subtasks", "summary": "Export all subtasks as JSON"},
    # History (extended)
    {"path": "/history/export",            "method": "GET",  "tag": "History",  "summary": "Export activity history as CSV or JSON"},
    # Control (extended)
    {"path": "/run",                       "method": "POST", "tag": "Control",  "summary": "Trigger one execution cycle",
     "response": {"type": "object", "properties": {
         "ok": {"type": "boolean"}, "reason": {"type": "string"},
     }}},
    {"path": "/run/history",               "method": "GET",  "tag": "Control",  "summary": "History of run cycles",
     "response": {"type": "object", "properties": {
         "records":     {"type": "array", "items": {"type": "object"}},
         "count":       {"type": "integer"},
         "total_steps": {"type": "integer"},
     }}},
    # Triggers (extended)
    {"path": "/add_task",       "method": "POST", "tag": "Triggers", "summary": "Add a new task to the DAG",
     "body": {"spec": {"type": "string", "description": "Task specification / goal"}}},
    {"path": "/add_branch",     "method": "POST", "tag": "Triggers", "summary": "Add a new branch to a task",
     "body": {"task": {"type": "string"}, "spec": {"type": "string"}}},
    {"path": "/rename",         "method": "POST", "tag": "Triggers", "summary": "Rename a task or branch",
     "body": {"task": {"type": "string"}, "name": {"type": "string"}}},
    {"path": "/depends",        "method": "POST", "tag": "Triggers", "summary": "Add a dependency between tasks",
     "body": {"target": {"type": "string"}, "dep": {"type": "string"}}},
    {"path": "/undepends",      "method": "POST", "tag": "Triggers", "summary": "Remove a dependency between tasks",
     "body": {"target": {"type": "string"}, "dep": {"type": "string"}}},
    {"path": "/prioritize_branch", "method": "POST", "tag": "Triggers", "summary": "Set branch priority",
     "body": {"task": {"type": "string"}, "branch": {"type": "string"}}},
    {"path": "/tools",          "method": "POST", "tag": "Triggers", "summary": "Set allowed tools for a subtask",
     "body": {"subtask": {"type": "string"}, "tools": {"type": "string"}}},
    {"path": "/webhook",        "method": "POST", "tag": "Webhook",  "summary": "Receive external webhook events",
     "body": {"event": {"type": "string"}, "payload": {"type": "object"}}},
    # Config (extended)
    {"path": "/config/reset",              "method": "POST", "tag": "Config",   "summary": "Reset configuration to defaults"},
    {"path": "/config/export",             "method": "GET",  "tag": "Config",   "summary": "Export current configuration as JSON"},
    # Misc
    {"path": "/priority",                  "method": "GET",  "tag": "Subtasks", "summary": "List highest-priority subtasks"},
    {"path": "/shortcuts",                 "method": "GET",  "tag": "Core",     "summary": "Available command shortcuts"},
    {"path": "/diff",                      "method": "GET",  "tag": "DAG",      "summary": "DAG diff since last snapshot"},
    {"path": "/dag/diff",                  "method": "GET",  "tag": "DAG",      "summary": "Detailed DAG diff"},
    {"path": "/graph",                     "method": "GET",  "tag": "DAG",      "summary": "DAG dependency graph as DOT or JSON"},
    {"path": "/timeline/{subtask}",        "method": "GET",  "tag": "History",  "summary": "Timeline of events for a specific subtask"},
    {"path": "/executor/gates",            "method": "GET",  "tag": "Health",   "summary": "Executor gate inventory (schema + policies)"},
]


def _read_version() -> str:
    try:
        toml = REPO_ROOT / "pyproject.toml"
        for line in toml.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version"):
                return line.split("=")[1].strip().strip('"\'')
    except Exception:
        pass
    return "0.0.0"


def build_spec() -> dict:
    """Build and return the OpenAPI 3.0 spec as a Python dict."""
    version = _read_version()

    # Group routes by path
    paths: dict[str, dict] = {}
    for route in _ROUTES:
        path  = route["path"]
        method = route["method"].lower()
        if path not in paths:
            paths[path] = {}
        # Auto-extract path parameters from {param} segments
        path_params = re.findall(r"\{([^}]+)\}", path)
        parameters: list[dict] = [
            {
                "name": param,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
            for param in path_params
        ]
        # Add explicit query parameters if declared
        for qname, qtype, qdesc in route.get("query", []):
            parameters.append({
                "name": qname,
                "in": "query",
                "required": False,
                "description": qdesc,
                "schema": {"type": qtype},
            })

        resp_200: dict = {"description": "Success"}
        if "response" in route:
            resp_200["content"] = {
                "application/json": {"schema": route["response"]}
            }
        operation: dict = {
            "tags":    [route["tag"]],
            "summary": route["summary"],
            "operationId": _operation_id(method, path),
            "responses": {
                "200": resp_200,
                "400": {"description": "Bad request"},
                "429": {"description": "Rate limit exceeded"},
            },
        }
        if parameters:
            operation["parameters"] = parameters
        if "body" in route:
            body_schema: dict = {
                "type": "object",
                "properties": route["body"],
            }
            required_fields = list(route["body"].keys())
            if required_fields:
                body_schema["required"] = required_fields
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": body_schema,
                    }
                },
            }
        paths[path][method] = operation

    # Collect tags
    seen_tags: list[str] = []
    for route in _ROUTES:
        if route["tag"] not in seen_tags:
            seen_tags.append(route["tag"])
    tags = [{"name": t} for t in seen_tags]

    return {
        "openapi": "3.0.3",
        "info": {
            "title":       "Solo Builder REST API",
            "version":     version,
            "description": (
                "Local automation API for the Solo Builder + Claude Code integration. "
                "Bound to 127.0.0.1 only — not exposed externally."
            ),
        },
        "servers": [{"url": "http://127.0.0.1:5001", "description": "Local dev"}],
        "tags":    tags,
        "paths":   paths,
    }


def _operation_id(method: str, path: str) -> str:
    """Derive a camelCase operationId from HTTP method + path."""
    def _pascal(segment: str) -> str:
        """Convert a URL segment to PascalCase, handling hyphens and underscores."""
        clean = segment.strip("{}")
        # Split on both hyphens and underscores then capitalize each sub-part
        sub_parts = clean.replace("-", "_").split("_")
        return "".join(s.capitalize() for s in sub_parts if s)

    path_parts = [p for p in path.strip("/").split("/") if p]
    result = method + "".join(_pascal(p) for p in path_parts)
    return result or method


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate OpenAPI spec for Solo Builder API.")
    parser.add_argument("--output", default="", help="Output file path (stdout if omitted)")
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--quiet",  action="store_true")
    args = parser.parse_args(argv)

    try:
        spec = build_spec()
    except Exception as exc:
        if not args.quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "yaml":
        try:
            import yaml
            output_text = yaml.dump(spec, allow_unicode=True, sort_keys=False)
        except ImportError:
            if not args.quiet:
                print("ERROR: pyyaml not installed. Run: pip install pyyaml", file=sys.stderr)
            return 1
    else:
        output_text = json.dumps(spec, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        if not args.quiet:
            print(f"OpenAPI spec written to {args.output}")
    else:
        if not args.quiet:
            print(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
