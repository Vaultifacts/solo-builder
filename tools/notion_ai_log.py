"""
notion_ai_log.py — log Claude execution runs into a Notion database.

The "AI Execution Log" database is created automatically under MAIN_PAGE_ID
on the first call to log_run() and its ID is persisted to
generated/.ai_log_db_id so subsequent calls reuse it.

Usage (CLI — log a manual run):
    python tools/notion_ai_log.py \\
        --task "TASK-311" \\
        --status Success \\
        --model "claude-sonnet-4-6" \\
        --duration 42 \\
        --notes "Implemented ThreatModelDocument"

Usage (from Python):
    from notion_ai_log import log_run
    log_run("TASK-311", "Success", "claude-sonnet-4-6", duration_s=42,
            notes="Implemented ThreatModelDocument")
"""
import sys
import argparse
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from notion_config import MAIN_PAGE_ID, GENERATED_DIR, AI_LOG_DB_ID_FILE
from notion_client import NotionClient

# ---------------------------------------------------------------------------
# Database schema (Notion REST API property format)
# ---------------------------------------------------------------------------
_DB_SCHEMA = {
    "Run": {"title": {}},
    "Task": {"rich_text": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "Success",  "color": "green"},
                {"name": "Failed",   "color": "red"},
                {"name": "Partial",  "color": "yellow"},
                {"name": "Skipped",  "color": "gray"},
            ]
        }
    },
    "Model":       {"rich_text": {}},
    "Duration (s)": {"number": {"format": "number"}},
    "Notes":       {"rich_text": {}},
    "Timestamp":   {"rich_text": {}},
}

_VALID_STATUSES = {"Success", "Failed", "Partial", "Skipped"}


# ---------------------------------------------------------------------------
# DB ID persistence
# ---------------------------------------------------------------------------

def _db_id_path():
    import pathlib
    return pathlib.Path(AI_LOG_DB_ID_FILE)


def _load_db_id() -> str | None:
    p = _db_id_path()
    if p.exists():
        val = p.read_text(encoding="utf-8").strip()
        return val if val else None
    return None


def _save_db_id(db_id: str):
    p = _db_id_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(db_id, encoding="utf-8")


# ---------------------------------------------------------------------------
# Ensure database exists  (search → cache → create, in that order)
# ---------------------------------------------------------------------------

def _search_for_existing_db(client: NotionClient) -> str | None:
    """
    Search the workspace for a database titled exactly 'AI Execution Log'
    whose parent is MAIN_PAGE_ID.  Returns the DB ID or None.
    """
    results = client.search("AI Execution Log", filter_type="database")
    for item in results:
        # Match title exactly
        title_parts = item.get("title", [])
        title_text = "".join(t.get("plain_text", "") for t in title_parts).strip()
        if title_text != "AI Execution Log":
            continue
        # Match parent page
        parent = item.get("parent", {})
        parent_id = parent.get("page_id", "").replace("-", "")
        if parent_id == MAIN_PAGE_ID.replace("-", ""):
            return item["id"].replace("-", "")
    return None


def ensure_database(client: NotionClient) -> str:
    """
    Return the AI Execution Log DB ID.

    Resolution order:
        1. Local cache file (fast path — no API call)
        2. Notion search (handles lost/deleted cache file)
        3. Create new database (first-ever run)

    This prevents duplicate databases even if the cache file is deleted.
    """
    # 1. Fast path: trust the local cache
    db_id = _load_db_id()
    if db_id:
        return db_id

    # 2. Search Notion — cache may have been lost
    print("Cache miss — searching Notion for existing AI Execution Log database...")
    db_id = _search_for_existing_db(client)
    if db_id:
        _save_db_id(db_id)
        print(f"Found existing AI Execution Log DB: {db_id}")
        return db_id

    # 3. Create for the first time
    print("Creating AI Execution Log database under Solo Builder root...")
    db = client.create_database(
        parent={"type": "page_id", "page_id": MAIN_PAGE_ID},
        title="AI Execution Log",
        properties=_DB_SCHEMA,
    )
    db_id = db["id"].replace("-", "")
    _save_db_id(db_id)
    print(f"Created AI Execution Log DB: {db_id}")
    return db_id


# ---------------------------------------------------------------------------
# log_run
# ---------------------------------------------------------------------------

def log_run(
    task: str,
    status: str,
    model: str,
    duration_s: float = 0.0,
    notes: str = "",
    client: NotionClient = None,
) -> dict:
    """
    Append one row to the AI Execution Log database.

    Parameters
    ----------
    task       : task ID or short description, e.g. "TASK-311"
    status     : one of Success | Failed | Partial | Skipped
    model      : model ID string, e.g. "claude-sonnet-4-6"
    duration_s : wall-clock seconds (float)
    notes      : free-form notes
    client     : reuse an existing NotionClient (creates one if None)
    """
    if status not in _VALID_STATUSES:
        raise ValueError(f"status must be one of {_VALID_STATUSES}, got {status!r}")

    if client is None:
        client = NotionClient()

    db_id = ensure_database(client)

    ts = datetime.now(timezone.utc).isoformat()
    run_name = f"{task} · {ts[:10]}"

    page = client.create_page(
        parent={"type": "database_id", "database_id": db_id},
        properties={
            "Run":          {"title":     [{"text": {"content": run_name}}]},
            "Task":         {"rich_text": [{"text": {"content": task}}]},
            "Status":       {"select":    {"name": status}},
            "Model":        {"rich_text": [{"text": {"content": model}}]},
            "Duration (s)": {"number":    round(duration_s, 2)},
            "Notes":        {"rich_text": [{"text": {"content": notes}}]},
            "Timestamp":    {"rich_text": [{"text": {"content": ts}}]},
        },
    )
    print(f"Logged: {run_name} [{status}] in {duration_s:.1f}s")
    return page


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Log a Claude run to the Notion AI Execution Log")
    parser.add_argument("--task",     required=True, help="Task ID or description")
    parser.add_argument("--status",   required=True, choices=sorted(_VALID_STATUSES))
    parser.add_argument("--model",    default="claude-sonnet-4-6")
    parser.add_argument("--duration", type=float, default=0.0, metavar="SECONDS")
    parser.add_argument("--notes",    default="")
    args = parser.parse_args()

    log_run(
        task=args.task,
        status=args.status,
        model=args.model,
        duration_s=args.duration,
        notes=args.notes,
    )


if __name__ == "__main__":
    main()
