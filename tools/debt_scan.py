"""Debt Scanner — TASK-336 (ME-003).

Scans the repository for inline debt markers (TODO, FIXME, HACK, XXX, NOQA)
in Python and JavaScript source files and appends a "Code-Level Debt Scan"
section to docs/TECH_DEBT_REGISTER.md.

Usage:
    python tools/debt_scan.py [--dry-run] [--json] [--quiet]

Options:
    --dry-run   Print findings without writing to TECH_DEBT_REGISTER.md
    --json      Output machine-readable JSON (implies --dry-run, no file write)
    --quiet     Suppress text output (still writes file unless --dry-run)

Exits:
    0 — scan complete (debt items may exist; non-zero count is not an error)
    1 — I/O or unexpected error
    2 — usage error
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT    = Path(__file__).resolve().parent.parent
REGISTER_PATH = REPO_ROOT / "docs" / "TECH_DEBT_REGISTER.md"

SCAN_GLOBS = ["solo_builder/**/*.py", "tools/*.py", "solo_builder/api/static/*.js"]
EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}

MARKER_RE = re.compile(r"#.*?\b(TODO|FIXME|HACK|XXX|NOQA)\b[:\s]*(.*)", re.IGNORECASE)


class DebtItem(NamedTuple):
    path: str
    line: int
    marker: str
    text: str


def _scan_file(path: Path, repo_root: Path) -> list[DebtItem]:
    items: list[DebtItem] = []
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = MARKER_RE.search(line)
            if m:
                items.append(DebtItem(
                    path=str(path.relative_to(repo_root)).replace("\\", "/"),
                    line=i,
                    marker=m.group(1).upper(),
                    text=m.group(2).strip(),
                ))
    except OSError:
        pass
    return items


def _collect_files(root: Path, globs: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for pattern in globs:
        for p in root.glob(pattern):
            if p in seen:
                continue
            if any(ex in p.parts for ex in EXCLUDE_DIRS):
                continue
            if p.is_file():
                seen.add(p)
                files.append(p)
    return sorted(files)


def scan(root: Path = REPO_ROOT) -> list[DebtItem]:
    """Return all debt items found in the repository source tree."""
    items: list[DebtItem] = []
    for f in _collect_files(root, SCAN_GLOBS):
        items.extend(_scan_file(f, root))
    return items


def _format_register_section(items: list[DebtItem]) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    lines = [
        "",
        "---",
        "",
        f"## Code-Level Debt Scan (auto-generated {now})",
        "",
        f"Scanned {len(set(i.path for i in items))} files; "
        f"found {len(items)} inline debt markers.",
        "",
        "| File | Line | Marker | Note |",
        "|---|---|---|---|",
    ]
    for item in items:
        note = item.text[:80] + ("…" if len(item.text) > 80 else "")
        lines.append(f"| `{item.path}` | {item.line} | {item.marker} | {note} |")
    if not items:
        lines.append("| — | — | — | No markers found |")
    lines.append("")
    return "\n".join(lines)


def _update_register(section: str, register: Path) -> None:
    """Replace any existing auto-generated section or append a new one."""
    try:
        content = register.read_text(encoding="utf-8")
    except OSError:
        content = ""

    # Remove existing auto-generated section
    start_marker = "## Code-Level Debt Scan (auto-generated"
    if start_marker in content:
        idx = content.index("\n---\n\n" + start_marker)
        content = content[:idx]

    content = content.rstrip() + "\n" + section
    register.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan codebase for debt markers.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print findings without writing to TECH_DEBT_REGISTER.md")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Output JSON (implies --dry-run)")
    parser.add_argument("--quiet", action="store_true", help="Suppress text output")
    args = parser.parse_args(argv)

    try:
        items = scan()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(
            {"count": len(items),
             "items": [{"path": i.path, "line": i.line, "marker": i.marker, "text": i.text}
                       for i in items]},
            ensure_ascii=False,
        ))
        return 0

    section = _format_register_section(items)

    if not args.dry_run:
        try:
            _update_register(section, REGISTER_PATH)
        except Exception as exc:
            print(f"ERROR writing register: {exc}", file=sys.stderr)
            return 1

    if not args.quiet:
        by_marker: dict[str, int] = {}
        for item in items:
            by_marker[item.marker] = by_marker.get(item.marker, 0) + 1
        print(f"Debt scan complete — {len(items)} markers found")
        for marker, count in sorted(by_marker.items()):
            print(f"  {marker:<8} {count}")
        if not args.dry_run:
            print(f"  => written to {REGISTER_PATH.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
