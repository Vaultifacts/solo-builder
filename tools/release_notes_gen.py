"""Release notes generator — TASK-352 (RD-010 to RD-015).

Extracts structured release notes from CHANGELOG.md for a given version tag
or the most recent version entry.

Features:
  - Parses CHANGELOG.md section headers (## vX.Y.Z — date  Title)
  - Extracts bullet points grouped under the version
  - Outputs Markdown (default) or JSON
  - Optionally writes to a file

Exit codes:
  0 — success
  1 — version not found or parse error
  2 — usage / file error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT      = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

# Matches: ## vX.Y.Z — YYYY-MM-DD  optional title (TASK-NNN)
_HEADER_RE = re.compile(
    r"^##\s+(v[\d.]+)\s+[—-]\s+(\d{4}-\d{2}-\d{2})\s*(.*)?$"
)

# Matches a bullet: - or * followed by text
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReleaseEntry:
    version:  str
    date:     str
    title:    str
    bullets:  list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "date":    self.date,
            "title":   self.title,
            "bullets": self.bullets,
        }

    def to_markdown(self) -> str:
        lines = [f"## {self.version} — {self.date}  {self.title}".rstrip(), ""]
        for b in self.bullets:
            lines.append(f"- {b}")
        if self.bullets:
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_changelog(changelog_path: Path | str | None = None) -> list[ReleaseEntry]:
    """Parse CHANGELOG.md and return a list of ReleaseEntry objects (newest first)."""
    if changelog_path is None:
        changelog_path = CHANGELOG_PATH
    changelog_path = Path(changelog_path)

    try:
        text = changelog_path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError) as exc:
        raise FileNotFoundError(f"CHANGELOG not found: {changelog_path}") from exc

    entries: list[ReleaseEntry] = []
    current: ReleaseEntry | None = None

    for line in text.splitlines():
        m = _HEADER_RE.match(line)
        if m:
            if current is not None:
                entries.append(current)
            current = ReleaseEntry(
                version=m.group(1),
                date=m.group(2),
                title=(m.group(3) or "").strip(),
            )
            continue

        if current is not None:
            bm = _BULLET_RE.match(line)
            if bm:
                current.bullets.append(bm.group(1).strip())

    if current is not None:
        entries.append(current)

    return entries


def get_entry(
    version: str | None = None,
    changelog_path: Path | str | None = None,
) -> ReleaseEntry | None:
    """Return the entry for *version* (e.g. 'v5.40.0') or the latest if None."""
    entries = parse_changelog(changelog_path=changelog_path)
    if not entries:
        return None
    if version is None:
        return entries[0]
    for e in entries:
        if e.version == version:
            return e
    return None


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    version: str | None = None,
    as_json: bool = False,
    output_path: Path | str | None = None,
    quiet: bool = False,
    changelog_path: Path | str | None = None,
) -> int:
    try:
        entry = get_entry(version=version, changelog_path=changelog_path)
    except FileNotFoundError as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if entry is None:
        if not quiet:
            ver_desc = version or "latest"
            print(f"ERROR: Version '{ver_desc}' not found in CHANGELOG.", file=sys.stderr)
        return 1

    if as_json:
        content = json.dumps(entry.to_dict(), indent=2, ensure_ascii=False)
    else:
        content = entry.to_markdown()

    if output_path:
        Path(output_path).write_text(content + "\n", encoding="utf-8")
        if not quiet:
            print(f"Release notes written to: {output_path}")
    else:
        if not quiet:
            print(content)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate release notes from CHANGELOG.md."
    )
    parser.add_argument(
        "version", nargs="?", default=None,
        help="Version tag (e.g. v5.40.0). Defaults to latest."
    )
    parser.add_argument("--json",       action="store_true", dest="as_json")
    parser.add_argument("--quiet",      action="store_true")
    parser.add_argument("--output",     default="", help="Write output to file")
    parser.add_argument("--changelog",  default="", help="Override CHANGELOG.md path")
    args = parser.parse_args(argv)
    return run(
        version=args.version,
        as_json=args.as_json,
        output_path=args.output or None,
        quiet=args.quiet,
        changelog_path=args.changelog or None,
    )


if __name__ == "__main__":
    sys.exit(main())
