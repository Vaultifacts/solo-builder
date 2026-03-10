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
    {"path": "/status",         "method": "GET",    "tag": "Core",       "summary": "Task/branch status summary"},
    {"path": "/heartbeat",      "method": "GET",    "tag": "Core",       "summary": "Lightweight step counter"},
    {"path": "/health",         "method": "GET",    "tag": "Core",       "summary": "Extended health probe (version, uptime, subtask count)"},
    # Metrics
    {"path": "/metrics",        "method": "GET",    "tag": "Metrics",    "summary": "Run health + analytics history"},
    {"path": "/metrics/summary","method": "GET",    "tag": "Metrics",    "summary": "Executor step metrics (p50/p95/p99/latency buckets)"},
    {"path": "/metrics/export", "method": "GET",    "tag": "Metrics",    "summary": "Export step history as CSV or JSON"},
    {"path": "/agents",         "method": "GET",    "tag": "Metrics",    "summary": "Agent statistics and ETA forecast"},
    {"path": "/forecast",       "method": "GET",    "tag": "Metrics",    "summary": "Detailed completion forecast"},
    # History
    {"path": "/history",        "method": "GET",    "tag": "History",    "summary": "Paged activity log"},
    {"path": "/history/count",  "method": "GET",    "tag": "History",    "summary": "Activity log counts by status"},
    # Tasks
    {"path": "/tasks",          "method": "GET",    "tag": "Tasks",      "summary": "List all tasks"},
    {"path": "/tasks/{task_id}","method": "GET",    "tag": "Tasks",      "summary": "Get task detail"},
    {"path": "/tasks/{task_id}/progress", "method": "GET", "tag": "Tasks", "summary": "Branch progress for a task"},
    {"path": "/tasks/{task_id}/reset",    "method": "POST","tag": "Tasks", "summary": "Reset non-Verified subtasks"},
    # Branches
    {"path": "/branches",       "method": "GET",    "tag": "Branches",   "summary": "List all branches"},
    {"path": "/branches/{branch_id}", "method": "GET", "tag": "Branches","summary": "Get branch detail"},
    # Subtasks
    {"path": "/subtasks",       "method": "GET",    "tag": "Subtasks",   "summary": "List all subtasks"},
    {"path": "/subtasks/bulk-reset", "method": "POST","tag": "Subtasks", "summary": "Bulk-reset selected subtasks"},
    {"path": "/stalled",        "method": "GET",    "tag": "Subtasks",   "summary": "List stalled subtasks (Running >= threshold)"},
    # Triggers
    {"path": "/trigger",        "method": "POST",   "tag": "Triggers",   "summary": "Fire a named trigger"},
    {"path": "/verify",         "method": "POST",   "tag": "Triggers",   "summary": "Trigger subtask verification"},
    {"path": "/describe",       "method": "POST",   "tag": "Triggers",   "summary": "Trigger subtask description update"},
    {"path": "/set",            "method": "POST",   "tag": "Triggers",   "summary": "Set a config value at runtime"},
    # Control
    {"path": "/pause",          "method": "POST",   "tag": "Control",    "summary": "Pause orchestration"},
    {"path": "/resume",         "method": "POST",   "tag": "Control",    "summary": "Resume orchestration"},
    {"path": "/stop",           "method": "POST",   "tag": "Control",    "summary": "Stop orchestration"},
    {"path": "/heal",           "method": "POST",   "tag": "Control",    "summary": "Trigger self-healer"},
    {"path": "/undo",           "method": "POST",   "tag": "Control",    "summary": "Undo last operation"},
    {"path": "/reset",          "method": "POST",   "tag": "Control",    "summary": "Reset workflow state"},
    {"path": "/snapshot",       "method": "POST",   "tag": "Control",    "summary": "Create state snapshot"},
    # Config
    {"path": "/config",         "method": "GET",    "tag": "Config",     "summary": "Get current configuration"},
    {"path": "/config",         "method": "POST",   "tag": "Config",     "summary": "Update configuration"},
    # DAG
    {"path": "/dag/summary",    "method": "GET",    "tag": "DAG",        "summary": "DAG pipeline summary with per-task breakdown"},
    {"path": "/dag/import",     "method": "POST",   "tag": "DAG",        "summary": "Import DAG from JSON"},
    {"path": "/dag/export",     "method": "GET",    "tag": "DAG",        "summary": "Export DAG as JSON"},
    # Cache
    {"path": "/cache/stats",    "method": "GET",    "tag": "Cache",      "summary": "Priority cache statistics"},
    {"path": "/cache/clear",    "method": "POST",   "tag": "Cache",      "summary": "Clear the priority cache"},
    # Webhook
    {"path": "/webhook/test",   "method": "POST",   "tag": "Webhook",    "summary": "Test Discord webhook"},
    # Health (detailed checks)
    {"path": "/health/detailed",         "method": "GET", "tag": "Health", "summary": "Aggregate health: state validator + config drift + metrics alerts"},
    {"path": "/health/gates",            "method": "GET", "tag": "Health", "summary": "Executor gate inventory (schema + policies)"},
    {"path": "/health/context-window",   "method": "GET", "tag": "Health", "summary": "Context window line-count check (CLAUDE.md / MEMORY.md / JOURNAL.md)"},
    {"path": "/health/threat-model",     "method": "GET", "tag": "Health", "summary": "Threat model freshness check (SE-001 to SE-006)"},
    {"path": "/health/slo",              "method": "GET", "tag": "Health", "summary": "SLO status: SLO-003 success rate + SLO-005 latency median"},
    {"path": "/health/prompt-regression","method": "GET", "tag": "Health", "summary": "Prompt template regression check (AI-002, AI-003)"},
    {"path": "/health/debt-scan",        "method": "GET", "tag": "Health", "summary": "Code debt scan: TODO/FIXME/HACK/XXX markers (capped at 20)"},
    {"path": "/health/ci-quality",       "method": "GET", "tag": "Health", "summary": "CI quality gate tool inventory (6 configured tools)"},
    {"path": "/health/pre-release",      "method": "GET", "tag": "Health", "summary": "Pre-release gate inventory (builtin + VERIFY.json gates)"},
    {"path": "/health/live-summary",     "method": "GET", "tag": "Health", "summary": "Live in-process health summary (threat-model + context-window + slo)"},
    # Policy
    {"path": "/policy/hitl",             "method": "GET", "tag": "Policy", "summary": "HITL policy rules from settings.json"},
    {"path": "/policy/scope",            "method": "GET", "tag": "Policy", "summary": "Tool scope policy rules from settings.json"},
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
        paths[path][method] = {
            "tags":    [route["tag"]],
            "summary": route["summary"],
            "operationId": _operation_id(method, path),
            "responses": {
                "200": {"description": "Success"},
                "429": {"description": "Rate limit exceeded"},
            },
        }

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
