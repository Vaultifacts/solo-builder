#!/usr/bin/env python
"""Journal archival script for Solo Builder (AI-009).

Archives JOURNAL.md entries older than N days to
claude/journal_archive/YYYY-MM.md (one file per calendar month).

What it does
------------
1. Reads claude/JOURNAL.md line by line.
2. Parses the ISO 8601 timestamp in each entry header:
       - [2026-03-05T23:42:24Z] ...
3. Entries older than --older-than days are grouped by YYYY-MM.
4. Each group is appended to claude/journal_archive/YYYY-MM.md.
5. The original JOURNAL.md is rewritten with only the kept lines.
6. Exits 0 on success; 1 on error.

Usage
-----
    python tools/archive_journal.py                  # default: archive entries > 30 days
    python tools/archive_journal.py --older-than 60  # archive entries > 60 days
    python tools/archive_journal.py --dry-run        # preview without modifying files

Notes
-----
- Only lines matching the journal entry pattern are considered.
  Non-matching lines (headers, blanks) are always kept.
- The archive directory is created if it does not exist.
- Each archive file begins with a summary line on first creation.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parents[1]
JOURNAL_PATH = REPO_ROOT / "claude" / "JOURNAL.md"
ARCHIVE_DIR  = REPO_ROOT / "claude" / "journal_archive"

# Matches: - [2026-03-05T23:42:24.8337338Z] ...
_ENTRY_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2}T[^\]]+Z)\] (.+)$")


def _parse_ts(raw: str) -> datetime | None:
    """Parse an ISO 8601 timestamp; return UTC-aware datetime or None."""
    # Strip sub-second precision so fromisoformat works on 3.10 and earlier.
    trimmed = re.sub(r"\.\d+Z$", "Z", raw).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(trimmed)
    except ValueError:
        return None


def _load_journal(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def _archive_path(month_key: str) -> Path:
    """Return the archive file path for a given 'YYYY-MM' key."""
    return ARCHIVE_DIR / f"{month_key}.md"


def run(older_than: int = 30, dry_run: bool = False, quiet: bool = False) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than)

    if not JOURNAL_PATH.exists():
        if not quiet:
            print(f"JOURNAL.md not found: {JOURNAL_PATH}")
        return 0

    lines = _load_journal(JOURNAL_PATH)
    kept: list[str] = []
    archived: dict[str, list[str]] = defaultdict(list)

    for line in lines:
        m = _ENTRY_RE.match(line.rstrip("\n\r"))
        if not m:
            kept.append(line)
            continue
        ts = _parse_ts(m.group(1))
        if ts is None or ts >= cutoff:
            kept.append(line)
            continue
        month_key = ts.strftime("%Y-%m")
        archived[month_key].append(line)

    total_archived = sum(len(v) for v in archived.values())

    if not quiet:
        print(f"Journal archival  (cutoff: >{older_than} days old)")
        print(f"  Total lines   : {len(lines)}")
        print(f"  To archive    : {total_archived}")
        print(f"  To keep       : {len(kept)}")
        for month, entries in sorted(archived.items()):
            print(f"  {month}: {len(entries)} entries → {_archive_path(month)}")
        if dry_run:
            print("  [dry-run] No files written.")
        print()

    if dry_run or total_archived == 0:
        if not quiet and total_archived == 0:
            print("Nothing to archive.")
        return 0

    # Write archive files
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for month_key, entries in sorted(archived.items()):
        apath = _archive_path(month_key)
        if not apath.exists():
            header = f"# Journal Archive — {month_key}\n\n"
            apath.write_text(header, encoding="utf-8")
        with apath.open("a", encoding="utf-8") as af:
            af.writelines(entries)
        if not quiet:
            print(f"  Wrote {len(entries)} entries → {apath.name}")

    # Rewrite JOURNAL.md with kept lines only
    JOURNAL_PATH.write_text("".join(kept), encoding="utf-8")
    if not quiet:
        print(f"  JOURNAL.md rewritten: {len(kept)} lines remain.")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive old Solo Builder journal entries.")
    parser.add_argument(
        "--older-than", type=int, default=30, metavar="DAYS",
        help="Archive entries older than N days (default: 30)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be archived without writing files",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress output",
    )
    args = parser.parse_args(argv)
    return run(older_than=args.older_than, dry_run=args.dry_run, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
