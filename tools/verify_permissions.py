"""
verify_permissions.py — confirm the Notion integration token has access to
all required workspace resources.

Usage:
    python tools/verify_permissions.py

Exit codes:
    0 — all resources accessible
    1 — one or more resources inaccessible (see output for details)

Run this BEFORE running any other notion_*.py script to catch sharing
errors early.  No writes are performed.
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from notion_config import (
    CHECKLIST_PAGE_ID, HEALTH_DASH_ID, GAP_AUDIT_DB_ID, MAIN_PAGE_ID,
)
from notion_client import NotionClient

import requests

RESOURCES = [
    ("Solo Builder (root page)",          "page",     MAIN_PAGE_ID),
    ("Project Cumulative Checklist",      "page",     CHECKLIST_PAGE_ID),
    ("Project Health Dashboard",          "page",     HEALTH_DASH_ID),
    ("Gap Audit Findings Database",       "database", GAP_AUDIT_DB_ID),
]


def _check_page(client: NotionClient, page_id: str) -> tuple[bool, str]:
    try:
        client.get_page(page_id)
        return True, "OK"
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        if code == 404:
            return False, "404 — page not found or not shared with integration"
        if code == 401:
            return False, "401 — token rejected (check NOTION_INTEGRATION_TOKEN)"
        if code == 403:
            return False, "403 — integration lacks read access (share page with integration)"
        return False, f"HTTP {code} — {e}"


def _check_database(client: NotionClient, db_id: str) -> tuple[bool, str]:
    try:
        # Query with limit 1 — just tests access, doesn't fetch all rows
        import requests as _req
        r = _req.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=client._headers,
            json={"page_size": 1},
        )
        r.raise_for_status()
        return True, f"OK ({r.json().get('results', []).__len__()} rows in first page)"
    except _req.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        if code == 404:
            return False, "404 — database not found or not shared with integration"
        if code == 403:
            return False, "403 — integration lacks access (share database with integration)"
        return False, f"HTTP {code} — {e}"


def run_checks() -> bool:
    client = NotionClient()
    all_ok = True

    print("Checking Notion integration permissions...\n")
    for name, kind, resource_id in RESOURCES:
        if kind == "page":
            ok, msg = _check_page(client, resource_id)
        else:
            ok, msg = _check_database(client, resource_id)

        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}")
        print(f"       ID: {resource_id}")
        print(f"       {msg}")
        if not ok:
            all_ok = False
            print(f"       FIX: In Notion, open the page/database → Connections → Add connection")
            print(f"            then select your integration.")
        print()

    if all_ok:
        print("All resources are accessible. Integration is correctly configured.\n")
    else:
        print("One or more resources are not accessible.")
        print("Fix the sharing settings in Notion and re-run this script.\n")

    return all_ok


if __name__ == "__main__":
    ok = run_checks()
    sys.exit(0 if ok else 1)
