"""Lock file generator — TASK-361 (SE-015).

Generates/updates tools/requirements-lock.txt by filtering `pip freeze` output
to only the packages declared in tools/requirements.txt.

Usage:
  python tools/lock_file_gen.py              # write/update lock file
  python tools/lock_file_gen.py --check      # exit 1 if lock file is stale/missing
  python tools/lock_file_gen.py --dry-run    # show what would be written
  python tools/lock_file_gen.py --json       # JSON output

Exit codes:
  0 — lock file written (or up to date when --check)
  1 — lock file stale or missing (--check only)
  2 — error (pip unavailable, requirements.txt missing, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO_ROOT / "tools" / "requirements.txt"
LOCK_FILE    = REPO_ROOT / "tools" / "requirements-lock.txt"

_COMMENT_RE = re.compile(r"^\s*#|^\s*$")
_PKG_NAME_RE = re.compile(r"^([A-Za-z0-9_\-\.]+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _parse_requirements(req_path: Path) -> list[str]:
    """Return normalised package names from a requirements.txt."""
    names: list[str] = []
    try:
        for line in req_path.read_text(encoding="utf-8").splitlines():
            if _COMMENT_RE.match(line):
                continue
            m = _PKG_NAME_RE.match(line.strip())
            if m:
                names.append(m.group(1).lower().replace("-", "_"))
    except (OSError, FileNotFoundError):
        pass
    return names


def _pip_freeze() -> list[str] | None:
    """Run `pip freeze` and return lines, or None on error."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout.splitlines()
    except Exception:
        return None


def _filter_freeze(freeze_lines: list[str], pkg_names: list[str]) -> list[str]:
    """Keep only freeze lines for packages in *pkg_names*."""
    kept: list[str] = []
    for line in freeze_lines:
        m = _PKG_NAME_RE.match(line.strip())
        if m and m.group(1).lower().replace("-", "_") in pkg_names:
            kept.append(line.strip())
    return sorted(kept, key=str.lower)


def _build_lock_content(pinned: list[str]) -> str:
    today = date.today().isoformat()
    header = (
        f"# Exact pinned versions for tools/requirements.txt dependencies\n"
        f"# Generated: {today} via pip freeze\n"
        f"# Install with: pip install -r tools/requirements-lock.txt\n\n"
    )
    return header + "\n".join(pinned) + "\n"


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def generate(
    req_path: Path | str | None = None,
    lock_path: Path | str | None = None,
    dry_run: bool = False,
) -> tuple[list[str], str | None]:
    """Generate pinned entries.  Returns (pinned_lines, error_message)."""
    req  = Path(req_path)  if req_path  else REQUIREMENTS
    lock = Path(lock_path) if lock_path else LOCK_FILE

    pkg_names = _parse_requirements(req)
    if not pkg_names:
        return [], f"No packages found in {req}"

    freeze = _pip_freeze()
    if freeze is None:
        return [], "pip freeze failed"

    pinned = _filter_freeze(freeze, pkg_names)
    if not pinned:
        return [], f"No installed packages matched {req}"

    if not dry_run:
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(_build_lock_content(pinned), encoding="utf-8")

    return pinned, None


def is_stale(
    req_path: Path | str | None = None,
    lock_path: Path | str | None = None,
) -> bool:
    """Return True if lock file is missing or out of date vs pip freeze."""
    lock = Path(lock_path) if lock_path else LOCK_FILE
    if not lock.exists():
        return True

    current_lines = {
        line.strip() for line in lock.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    req  = Path(req_path) if req_path else REQUIREMENTS
    pkg_names = _parse_requirements(req)
    freeze = _pip_freeze()
    if freeze is None:
        return True

    fresh_pinned = set(_filter_freeze(freeze, pkg_names))
    return current_lines != fresh_pinned


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    dry_run: bool = False,
    check: bool = False,
    req_path: Path | str | None = None,
    lock_path: Path | str | None = None,
) -> int:
    lock = Path(lock_path) if lock_path else LOCK_FILE

    if check:
        stale = is_stale(req_path=req_path, lock_path=lock_path)
        exit_code = 1 if stale else 0
        if not quiet:
            if as_json:
                print(json.dumps({"stale": stale, "lock_path": str(lock)}))
            else:
                msg = "STALE — run lock_file_gen.py to update" if stale else "UP TO DATE"
                print(f"Lock file: {msg}")
        return exit_code

    pinned, err = generate(req_path=req_path, lock_path=lock_path, dry_run=dry_run)

    if err:
        if not quiet:
            print(f"ERROR: {err}", file=sys.stderr)
        return 2

    if not quiet:
        if as_json:
            print(json.dumps({
                "dry_run":   dry_run,
                "lock_path": str(lock),
                "pinned":    pinned,
                "count":     len(pinned),
            }))
        else:
            prefix = "[DRY-RUN] " if dry_run else ""
            print(f"{prefix}Lock file: {lock}")
            for p in pinned:
                print(f"  {p}")
            if not dry_run:
                print(f"Written {len(pinned)} package(s).")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate/update tools/requirements-lock.txt."
    )
    parser.add_argument("--json",      action="store_true", dest="as_json")
    parser.add_argument("--quiet",     action="store_true")
    parser.add_argument("--dry-run",   action="store_true")
    parser.add_argument("--check",     action="store_true",
                        help="Exit 1 if lock file is stale or missing")
    parser.add_argument("--req",       default="", help="Override requirements.txt path")
    parser.add_argument("--lock",      default="", help="Override lock file path")
    args = parser.parse_args(argv)
    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        dry_run=args.dry_run,
        check=args.check,
        req_path=args.req or None,
        lock_path=args.lock or None,
    )


if __name__ == "__main__":
    sys.exit(main())
