"""
notion_feedback.py — read the Notion workspace and generate
generated/notion_feedback.json for consumption by task_orchestrator.py.

Reads:
    Checklist (CHECKLIST_PAGE_ID)
        - Layer 1 deliverable table  → completion count
        - Layer 3 to_do blocks       → active priorities with checked state
        - Blockers / Risks table     → risk items
    Gap Audit Findings Database (GAP_AUDIT_DB_ID)
        - All 17 domain rows         → gap domain summary

Usage:
    python tools/notion_feedback.py [--verbose]
"""
import sys
import json
import argparse
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from notion_config import (
    CHECKLIST_PAGE_ID, GAP_AUDIT_DB_ID, GENERATED_DIR,
    FEEDBACK_JSON, LAYER3_HEADING, BLOCKERS_HEADING,
)
from notion_client import NotionClient


# ---------------------------------------------------------------------------
# Checklist block parsing helpers
# ---------------------------------------------------------------------------

def _heading_level(block: dict) -> str | None:
    """Return the heading text if the block is any heading type, else None."""
    for ht in ("heading_1", "heading_2", "heading_3"):
        if block["type"] == ht:
            return NotionClient.plain_text(block[ht].get("rich_text", []))
    return None


def _parse_checklist_page(client: NotionClient) -> dict:
    """
    Traverse Checklist block tree and extract:
        layer1 — {complete, total}
        layer3 — list of {title, checked, raw_text}
        risks   — list of {risk, audit_ref, severity}

    Strategy: scan heading sequence to know which section we're in,
    then collect the appropriate block types within each section.
    """
    blocks = client.get_block_children(CHECKLIST_PAGE_ID)

    layer1_complete = 0
    layer1_total = 0
    layer3_items = []
    risk_items = []

    section = None  # "layer1" | "layer3" | "risks" | None

    # We'll collect table_row blocks per section; tables are encountered
    # as top-level blocks whose children are table_row blocks.
    pending_table_section = None

    for block in blocks:
        btype = block["type"]
        heading_text = _heading_level(block)

        # --- Update section tracker ---
        if heading_text:
            text_lower = heading_text.lower()
            if "layer 1" in text_lower or "project completion" in text_lower:
                section = "layer1"
            elif LAYER3_HEADING.lower() in text_lower or "active priorities" in text_lower:
                section = "layer3"
            elif BLOCKERS_HEADING.lower() in text_lower or "risks" in text_lower:
                section = "risks"
            else:
                section = None
            continue

        # --- Layer 1: count table rows with ✅ in second cell ---
        if section == "layer1" and btype == "table":
            rows = client.get_block_children(block["id"])
            for row in rows:
                if row["type"] != "table_row":
                    continue
                cells = row["table_row"]["cells"]
                if len(cells) < 2:
                    continue
                cell0 = NotionClient.plain_text(cells[0]).strip()
                cell1 = NotionClient.plain_text(cells[1]).strip()
                if not cell0 or cell0.lower() in ("deliverable", "metric"):
                    continue  # header row
                layer1_total += 1
                if "✅" in cell1 or "complete" in cell1.lower():
                    layer1_complete += 1

        # --- Layer 3: collect to_do blocks ---
        if section == "layer3" and btype == "to_do":
            rt = block["to_do"].get("rich_text", [])
            text = NotionClient.plain_text(rt).strip()
            checked = block["to_do"].get("checked", False)
            if text:
                # Extract audit refs from parenthetical e.g. "(AI-002, AI-003)"
                import re
                refs_match = re.search(r"\(([^)]+)\)\s*$", text)
                audit_refs = refs_match.group(1) if refs_match else ""
                title = re.sub(r"\s*\([^)]+\)\s*$", "", text).strip()
                layer3_items.append({
                    "title": title,
                    "checked": checked,
                    "audit_refs": audit_refs,
                    "raw_text": text,
                })

        # --- Risks: collect table rows ---
        if section == "risks" and btype == "table":
            rows = client.get_block_children(block["id"])
            for row in rows:
                if row["type"] != "table_row":
                    continue
                cells = row["table_row"]["cells"]
                if len(cells) < 2:
                    continue
                risk_text = NotionClient.plain_text(cells[0]).strip()
                audit_ref = NotionClient.plain_text(cells[1]).strip() if len(cells) > 1 else ""
                severity  = NotionClient.plain_text(cells[2]).strip() if len(cells) > 2 else ""
                if not risk_text or risk_text.lower() in ("risk", "deliverable"):
                    continue  # header
                risk_items.append({
                    "risk": risk_text,
                    "audit_ref": audit_ref,
                    "severity": severity,
                })

    return {
        "layer1": {"complete": layer1_complete, "total": layer1_total},
        "layer3": layer3_items,
        "risks": risk_items,
    }


# ---------------------------------------------------------------------------
# Gap Audit DB reading
# ---------------------------------------------------------------------------

def _parse_gap_audit_db(client: NotionClient) -> list:
    """Return sorted list of gap domain dicts from the Gap Audit Findings Database."""
    SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, "": 3}
    pages = client.query_database(GAP_AUDIT_DB_ID)
    domains = []
    for page in pages:
        props = page.get("properties", {})

        def _title(p):
            return "".join(rt.get("plain_text", "") for rt in p.get("title", []))

        def _text(p):
            return "".join(rt.get("plain_text", "") for rt in p.get("rich_text", []))

        def _select(p):
            sel = p.get("select")
            return sel["name"] if sel else ""

        def _number(p):
            return p.get("number") or 0

        domain_name = _title(props.get("Domain", {}))
        domains.append({
            "domain": domain_name,
            "gap_count": int(_number(props.get("Gap Count", {}))),
            "gap_ids": _text(props.get("Gap IDs", {})),
            "severity": _select(props.get("Severity", {})),
            "status": _select(props.get("Status", {})),
            "notes": _text(props.get("Notes", {})),
        })

    domains.sort(key=lambda d: (SEVERITY_ORDER.get(d["severity"], 3), -d["gap_count"]))
    return domains


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_feedback(verbose: bool = False) -> dict:
    client = NotionClient()

    if verbose:
        print("Reading Checklist page...")
    checklist = _parse_checklist_page(client)

    if verbose:
        print("Reading Gap Audit Findings Database...")
    gap_domains = _parse_gap_audit_db(client)

    layer1 = checklist["layer1"]
    pct = round(100 * layer1["complete"] / layer1["total"]) if layer1["total"] else 0

    feedback = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer1_completion": {
            "complete": layer1["complete"],
            "total": layer1["total"],
            "pct": pct,
        },
        "layer3_priorities": checklist["layer3"],
        "risks": checklist["risks"],
        "gap_domains": gap_domains,
        "summary": {
            "total_gaps": sum(d["gap_count"] for d in gap_domains),
            "high_severity_domains": [d["domain"] for d in gap_domains if d["severity"] == "High"],
            "open_priorities": sum(1 for p in checklist["layer3"] if not p["checked"]),
        },
    }

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_JSON.write_text(json.dumps(feedback, indent=2), encoding="utf-8")

    if verbose:
        print(f"\nLayer 1: {layer1['complete']}/{layer1['total']} ({pct}%)")
        print(f"Layer 3: {len(checklist['layer3'])} priorities, "
              f"{feedback['summary']['open_priorities']} open")
        print(f"Gap domains: {len(gap_domains)}, total gaps: {feedback['summary']['total_gaps']}")
        print(f"High-severity: {', '.join(feedback['summary']['high_severity_domains'])}")

    print(f"\nWrote {FEEDBACK_JSON}")
    return feedback


def main():
    parser = argparse.ArgumentParser(description="Read Notion workspace → notion_feedback.json")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    generate_feedback(verbose=args.verbose)


if __name__ == "__main__":
    main()
