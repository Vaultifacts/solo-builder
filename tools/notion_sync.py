"""
notion_sync.py — sync repo metrics to existing Notion pages.

Updates in place (surgical block-level PATCHes). Never recreates pages.

Usage:
    python tools/notion_sync.py [--dry-run]   # show intended changes
    python tools/notion_sync.py               # live write
    python tools/notion_sync.py --audit       # inspect block tree only

Block-matching strategy (Task 6 — stable anchors):
    Tables   — scoped to the section that follows a heading whose text
               contains a known anchor ("Summary Metrics").  Falls back
               to all-table scan only if no heading anchor is found.
    Rows     — matched by first-cell label text (never by position).
    Callouts / paragraphs — matched by marker substring in rich_text.

This means the sync survives manual Notion edits as long as:
    • The heading "Summary Metrics" is not renamed.
    • Row labels ("Current Release", "Tasks Merged", …) are not renamed.
    • The quote block still contains "Last reconciliation".
    • The paragraph still contains "Last reconciled".
"""
import re
import sys
import json
import argparse
from datetime import date

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from notion_config import (
    CHECKLIST_PAGE_ID, HEALTH_DASH_ID, CHANGELOG, STATE_JSON, METRIC_LABELS,
)
from notion_client import NotionClient


# ---------------------------------------------------------------------------
# Metric extraction from repo files
# ---------------------------------------------------------------------------

def extract_metrics() -> dict:
    """Parse CHANGELOG.md and STATE.json for current project metrics."""
    metrics = {
        "release": "unknown",
        "tasks_merged": "unknown",
        "api_tests": "unknown",
        "discord_tests": "unknown",
        "phase": "unknown",
        "task_id": "unknown",
        "today": date.today().isoformat(),
    }

    if CHANGELOG.exists():
        text = CHANGELOG.read_text(encoding="utf-8")
        # First version heading e.g. "## v5.8.0 — 2026-03-09"
        m = re.search(r"^## (v\d+\.\d+\.\d+)", text, re.MULTILINE)
        if m:
            metrics["release"] = m.group(1)
        # "**310 tasks** merged"
        m = re.search(r"\*\*(\d+) tasks\*\* merged", text)
        if m:
            metrics["tasks_merged"] = m.group(1)
        # "**600 API tests**"
        m = re.search(r"\*\*(\d+) API tests\*\*", text)
        if m:
            metrics["api_tests"] = f"{m.group(1)} passing"
        # "**305 Discord tests**"
        m = re.search(r"\*\*(\d+) Discord tests\*\*", text)
        if m:
            metrics["discord_tests"] = f"{m.group(1)} passing"

    if STATE_JSON.exists():
        state = json.loads(STATE_JSON.read_text(encoding="utf-8"))
        metrics["task_id"] = state.get("task_id", "unknown")
        metrics["phase"] = state.get("phase", "unknown")

    return metrics


# ---------------------------------------------------------------------------
# Block-tree helpers
# ---------------------------------------------------------------------------

def _collect_table_rows(client: NotionClient, page_id: str, section_anchor: str = "") -> list:
    """
    Return table_row blocks from a specific section of a page.

    If *section_anchor* is given, only the first table that appears after
    a heading containing that text (case-insensitive) is used.  This prevents
    rows from unrelated tables on the same page from causing false label
    matches.

    Falls back to collecting from ALL tables if the anchor heading is not found
    (preserves original behaviour for pages without section headings).
    """
    blocks = client.get_block_children(page_id)

    if section_anchor:
        anchor_lower = section_anchor.lower()
        in_section = False
        for block in blocks:
            btype = block["type"]
            # Detect heading that matches the anchor
            for ht in ("heading_1", "heading_2", "heading_3"):
                if btype == ht:
                    text = client.plain_text(block[ht].get("rich_text", []))
                    if anchor_lower in text.lower():
                        in_section = True
                    elif in_section:
                        # Next heading ends the section — stop searching
                        in_section = False
            # First table encountered after the anchor heading
            if in_section and btype == "table":
                return client.get_block_children(block["id"])

    # Fallback: collect from all tables (original behaviour)
    rows = []
    for block in blocks:
        if block["type"] == "table":
            rows.extend(client.get_block_children(block["id"]))
    return rows


def audit_page_blocks(client: NotionClient, page_id: str, page_name: str):
    """Print a structured view of block types and text content for inspection."""
    print(f"\n── {page_name} block tree ──")
    blocks = client.get_block_children(page_id)
    for block in blocks:
        btype = block["type"]
        if btype in ("heading_1", "heading_2", "heading_3"):
            text = client.plain_text(block[btype].get("rich_text", []))
            print(f'  {btype}: "{text}"')
        elif btype == "quote":
            text = client.plain_text(block["quote"].get("rich_text", []))
            print(f'  quote: "{text[:80]}"')
        elif btype == "paragraph":
            text = client.plain_text(block["paragraph"].get("rich_text", []))
            if text.strip():
                print(f'  paragraph: "{text[:80]}"')
        elif btype == "table":
            rows = client.get_block_children(block["id"])
            print(f"  table ({len(rows)} rows):")
            for row in rows[:10]:  # show up to 10 rows
                if row["type"] == "table_row":
                    cells = row["table_row"]["cells"]
                    c0 = client.plain_text(cells[0]).strip() if cells else ""
                    c1 = client.plain_text(cells[1]).strip() if len(cells) > 1 else ""
                    print(f"    [{c0}] → [{c1[:60]}]")
        elif btype == "to_do":
            text = client.plain_text(block["to_do"].get("rich_text", []))
            checked = "✓" if block["to_do"].get("checked") else "○"
            print(f'  to_do {checked}: "{text[:80]}"')
        else:
            print(f"  {btype}")


def _update_table_row(client: NotionClient, rows: list, label: str, new_value: str, dry_run: bool):
    """Find the row whose first cell matches *label* and update the second cell."""
    for row in rows:
        if row["type"] != "table_row":
            continue
        cells = row["table_row"]["cells"]
        if not cells:
            continue
        cell0_text = client.plain_text(cells[0]).strip()
        if cell0_text == label:
            new_cells = [cells[0], client.rich_text(new_value)]
            for i in range(2, len(cells)):
                new_cells.append(cells[i])
            if dry_run:
                print(f"  [DRY] would patch row '{label}' → '{new_value}'")
            else:
                client.patch_block(row["id"], {"table_row": {"cells": new_cells}})
                print(f"  ✓ updated '{label}' → '{new_value}'")
            return True
    print(f"  ! row not found for label '{label}'", file=sys.stderr)
    return False


def _update_block_containing(
    client: NotionClient,
    page_id: str,
    marker: str,
    new_rich_text: list,
    block_type: str,
    dry_run: bool,
) -> bool:
    """Find the first block of *block_type* whose plain text contains *marker* and PATCH it."""
    for block in client.get_block_children(page_id):
        bt = block["type"]
        if bt != block_type:
            continue
        rt = block[bt].get("rich_text", [])
        if marker in client.plain_text(rt):
            if dry_run:
                print(f"  [DRY] would patch {block_type} containing '{marker}'")
            else:
                client.patch_block(block["id"], {block_type: {"rich_text": new_rich_text}})
                print(f"  ✓ updated {block_type} containing '{marker}'")
            return True
    print(f"  ! block not found: {block_type} containing '{marker}'", file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# Page update functions
# ---------------------------------------------------------------------------

def sync_health_dashboard(client: NotionClient, metrics: dict, dry_run: bool):
    print("Health Dashboard:")
    # Scope table scan to "Summary Metrics" section to avoid matching
    # rows from any future tables added to the page.
    rows = _collect_table_rows(client, HEALTH_DASH_ID, section_anchor="Summary Metrics")

    _update_table_row(client, rows, METRIC_LABELS["release"],       metrics["release"],       dry_run)
    _update_table_row(client, rows, METRIC_LABELS["tasks_merged"],  metrics["tasks_merged"],  dry_run)
    _update_table_row(client, rows, METRIC_LABELS["api_tests"],     metrics["api_tests"],     dry_run)
    _update_table_row(client, rows, METRIC_LABELS["discord_tests"], metrics["discord_tests"], dry_run)

    # Update "Last reconciliation: **YYYY-MM-DD**" quote block
    # The bold date is a separate rich_text segment; rebuild as two segments.
    new_rt = client.rich_text("Last reconciliation: ") + client.rich_text(metrics["today"], bold=True)
    _update_block_containing(
        client, HEALTH_DASH_ID, "Last reconciliation", new_rt, "quote", dry_run
    )


def sync_checklist(client: NotionClient, metrics: dict, dry_run: bool):
    print("Checklist:")
    footer = (
        f"Last reconciled: {metrics['today']} "
        f"| {metrics['release']} "
        f"| {metrics['tasks_merged']} tasks merged"
    )
    new_rt = client.rich_text(footer, italic=True)
    _update_block_containing(
        client, CHECKLIST_PAGE_ID, "Last reconciled", new_rt, "paragraph", dry_run
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sync repo metrics to Notion")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print intended changes without writing to Notion")
    parser.add_argument("--audit", action="store_true",
                        help="Inspect block tree of both pages (read-only, no writes)")
    args = parser.parse_args()

    metrics = extract_metrics()
    print("Extracted metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print()

    try:
        client = NotionClient()

        if args.audit:
            from notion_config import CHECKLIST_PAGE_ID as _CL_ID
            audit_page_blocks(client, HEALTH_DASH_ID, "Health Dashboard")
            audit_page_blocks(client, _CL_ID, "Checklist")
            print("\nAudit complete — no changes made.")
            return

        sync_health_dashboard(client, metrics, dry_run=args.dry_run)
        print()
        sync_checklist(client, metrics, dry_run=args.dry_run)
        mode = "DRY RUN — no changes written." if args.dry_run else "Sync complete."
        print(f"\n{mode}")

    except RuntimeError as exc:
        # Notion API is unavailable or returned a permanent error.
        # Print the reason but exit 0 so the post-commit hook never blocks a commit.
        print(f"\nNotion sync skipped — API error:\n  {exc}", file=sys.stderr)
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
