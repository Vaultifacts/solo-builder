"""Version bump tool — TASK-353 (RD-020 to RD-025).

Computes the next semantic version (major/minor/patch) and optionally
updates VERSION.txt and prepends a new section header to CHANGELOG.md.

Usage:
  python tools/version_bump.py [major|minor|patch]
  python tools/version_bump.py --dry-run minor
  python tools/version_bump.py --write minor
  python tools/version_bump.py --current   # print current version only

Semver rules:
  - major: X+1.0.0
  - minor: X.Y+1.0
  - patch: X.Y.Z+1

VERSION.txt stores the current version string (e.g. "v5.42.0").
If VERSION.txt does not exist the tool falls back to parsing the most recent
## vX.Y.Z header from CHANGELOG.md.

Exit codes:
  0 — success
  1 — parse / bump error
  2 — usage error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT      = Path(__file__).resolve().parent.parent
VERSION_PATH   = REPO_ROOT / "VERSION.txt"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_CHANGELOG_HEADER_RE = re.compile(r"^##\s+(v[\d.]+)\s+[—-]")

BUMP_TYPES = ("major", "minor", "patch")


# ---------------------------------------------------------------------------
# SemVer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version_str: str) -> "SemVer":
        m = _SEMVER_RE.match(version_str.strip())
        if not m:
            raise ValueError(f"Invalid semver: {version_str!r}")
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def bump(self, bump_type: str) -> "SemVer":
        if bump_type == "major":
            return SemVer(self.major + 1, 0, 0)
        if bump_type == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if bump_type == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        raise ValueError(f"Unknown bump type: {bump_type!r}")

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_current_version(
    version_path: Path | None = None,
    changelog_path: Path | None = None,
) -> SemVer:
    """Return current version from VERSION.txt or CHANGELOG.md."""
    if version_path is None:
        version_path = VERSION_PATH
    if changelog_path is None:
        changelog_path = CHANGELOG_PATH

    # Try VERSION.txt first
    try:
        text = version_path.read_text(encoding="utf-8").strip()
        return SemVer.parse(text)
    except (OSError, ValueError):
        pass

    # Fall back to CHANGELOG.md
    try:
        for line in changelog_path.read_text(encoding="utf-8").splitlines():
            m = _CHANGELOG_HEADER_RE.match(line)
            if m:
                return SemVer.parse(m.group(1))
    except (OSError, ValueError):
        pass

    raise RuntimeError(
        "Could not determine current version from VERSION.txt or CHANGELOG.md."
    )


def _compute_next(
    bump_type: str,
    version_path: Path | None = None,
    changelog_path: Path | None = None,
) -> tuple[SemVer, SemVer]:
    """Return (current, next) SemVer pair."""
    current = _read_current_version(version_path=version_path, changelog_path=changelog_path)
    return current, current.bump(bump_type)


def _write_version_file(new_version: SemVer, version_path: Path) -> None:
    version_path.write_text(str(new_version) + "\n", encoding="utf-8")


def _prepend_changelog_header(
    new_version: SemVer,
    title: str,
    changelog_path: Path,
) -> None:
    """Insert a new blank section for *new_version* at the top of CHANGELOG.md."""
    try:
        existing = changelog_path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        existing = "# Changelog\n"

    import datetime
    today = datetime.date.today().isoformat()
    header = f"\n## {new_version} — {today}  {title}\n\n- (placeholder)\n\n---\n"

    if existing.startswith("# Changelog"):
        new_content = "# Changelog\n" + header + existing[len("# Changelog"):].lstrip("\n")
    else:
        new_content = "# Changelog\n" + header + existing

    changelog_path.write_text(new_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    bump_type: str | None = None,
    dry_run: bool = True,
    write: bool = False,
    show_current: bool = False,
    as_json: bool = False,
    quiet: bool = False,
    version_path: Path | str | None = None,
    changelog_path: Path | str | None = None,
    new_title: str = "New Release",
) -> int:
    if version_path is not None:
        version_path = Path(version_path)
    if changelog_path is not None:
        changelog_path = Path(changelog_path)

    try:
        if show_current:
            current = _read_current_version(
                version_path=version_path,
                changelog_path=changelog_path,
            )
            if as_json:
                if not quiet:
                    print(json.dumps({"current": str(current)}, indent=2))
            else:
                if not quiet:
                    print(str(current))
            return 0

        if not bump_type:
            if not quiet:
                print("ERROR: bump type required (major|minor|patch)", file=sys.stderr)
            return 2

        if bump_type not in BUMP_TYPES:
            if not quiet:
                print(f"ERROR: invalid bump type {bump_type!r}", file=sys.stderr)
            return 2

        current, next_ver = _compute_next(
            bump_type,
            version_path=version_path,
            changelog_path=changelog_path,
        )

        if as_json:
            data = {
                "bump_type":   bump_type,
                "current":     str(current),
                "next":        str(next_ver),
                "dry_run":     dry_run and not write,
                "wrote_files": False,
            }

        if write and not dry_run:
            _write_version_file(
                next_ver,
                version_path if version_path else VERSION_PATH,
            )
            _prepend_changelog_header(
                next_ver,
                title=new_title,
                changelog_path=changelog_path if changelog_path else CHANGELOG_PATH,
            )
            if as_json:
                data["wrote_files"] = True  # type: ignore[index]

        if not quiet:
            if as_json:
                print(json.dumps(data, indent=2))
            else:
                mode = "DRY-RUN" if not write else "WRITE"
                print(f"[{mode}] {current}  →  {next_ver}  ({bump_type})")
                if write and not dry_run:
                    print(f"  VERSION.txt updated to {next_ver}")
                    print(f"  CHANGELOG.md header prepended for {next_ver}")

    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bump semantic version in VERSION.txt and CHANGELOG.md."
    )
    parser.add_argument(
        "bump_type", nargs="?", default=None,
        choices=[*BUMP_TYPES, None],
        help="Bump type: major, minor, or patch"
    )
    parser.add_argument("--current",    action="store_true", help="Print current version and exit")
    parser.add_argument("--write",      action="store_true",
                        help="Write changes (default is dry-run)")
    parser.add_argument("--json",       action="store_true", dest="as_json")
    parser.add_argument("--quiet",      action="store_true")
    parser.add_argument("--title",      default="New Release",
                        help="Title for new CHANGELOG section")
    parser.add_argument("--version-file", default="", help="Override VERSION.txt path")
    parser.add_argument("--changelog",    default="", help="Override CHANGELOG.md path")
    args = parser.parse_args(argv)

    if not args.current and not args.bump_type:
        parser.print_help()
        return 2

    return run(
        bump_type=args.bump_type,
        dry_run=not args.write,
        write=args.write,
        show_current=args.current,
        as_json=args.as_json,
        quiet=args.quiet,
        version_path=args.version_file or None,
        changelog_path=args.changelog or None,
        new_title=args.title,
    )


if __name__ == "__main__":
    sys.exit(main())
