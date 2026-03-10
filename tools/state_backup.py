"""State backup and restore tool — TASK-347 (ME-010 to ME-015).

Creates point-in-time backups of critical workflow state files and
restores them on demand.

Files backed up:
  - state/solo_builder_state.json  (primary DAG state)
  - state/step.txt                 (step counter / heartbeat)
  - state/metrics.jsonl            (executor step metrics) — if present
  - config/settings.json           (runtime configuration)

Backups are stored as ZIP archives in a configurable directory
(default: backups/).

Usage:
  python tools/state_backup.py backup [--label LABEL] [--backup-dir DIR]
  python tools/state_backup.py restore <archive> [--backup-dir DIR] [--dry-run]
  python tools/state_backup.py list [--backup-dir DIR]
  python tools/state_backup.py prune [--keep N] [--backup-dir DIR]

Exit codes:
  0 — success
  1 — error
  2 — usage error
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT   = Path(__file__).resolve().parent.parent
DEFAULT_BACKUP_DIR = REPO_ROOT / "backups"

# Files to include in every backup (relative to REPO_ROOT)
_BACKUP_FILES: list[str] = [
    "solo_builder/state/solo_builder_state.json",
    "solo_builder/state/step.txt",
    "solo_builder/metrics.jsonl",
    "solo_builder/config/settings.json",
]


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def _archive_name(label: str | None = None) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_label = f"_{label}" if label else ""
    return f"sb_backup_{ts}{safe_label}.zip"


def backup(
    backup_dir: Path,
    label: str | None = None,
    quiet: bool = False,
) -> Path:
    """Create a backup archive; return the archive path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    archive_path = backup_dir / _archive_name(label)

    included = []
    skipped  = []
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path in _BACKUP_FILES:
            src = REPO_ROOT / rel_path
            if src.exists():
                zf.write(src, arcname=rel_path)
                included.append(rel_path)
            else:
                skipped.append(rel_path)
        # Write manifest
        manifest = {
            "created":  datetime.datetime.now().isoformat(),
            "label":    label or "",
            "included": included,
            "skipped":  skipped,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    if not quiet:
        print(f"Backup created: {archive_path.name}")
        print(f"  Included: {len(included)} files  |  Skipped: {len(skipped)} files")
    return archive_path


def restore(
    archive_path: Path,
    dry_run: bool = False,
    quiet: bool = False,
) -> list[str]:
    """Restore files from archive; return list of restored paths."""
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    restored = []
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = [n for n in zf.namelist() if n != "manifest.json"]
        for name in names:
            dest = REPO_ROOT / name
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(name))
            restored.append(name)

    if not quiet:
        mode = "[DRY-RUN] " if dry_run else ""
        print(f"{mode}Restored {len(restored)} files from {archive_path.name}")
        for r in restored:
            print(f"  {r}")
    return restored


def list_backups(backup_dir: Path, quiet: bool = False) -> list[Path]:
    """List all backup archives in *backup_dir*."""
    if not backup_dir.exists():
        return []
    archives = sorted(backup_dir.glob("sb_backup_*.zip"))
    if not quiet:
        if not archives:
            print("No backups found.")
        else:
            print(f"{'Archive':<45}  {'Size':>8}")
            for a in archives:
                size_kb = round(a.stat().st_size / 1024, 1)
                print(f"  {a.name:<43}  {size_kb:>7.1f} KB")
    return archives


def prune(backup_dir: Path, keep: int = 10, quiet: bool = False) -> list[Path]:
    """Delete oldest archives keeping at most *keep* most recent."""
    archives = list_backups(backup_dir, quiet=True)
    to_delete = archives[:-keep] if len(archives) > keep else []
    for a in to_delete:
        a.unlink()
        if not quiet:
            print(f"Deleted: {a.name}")
    if not quiet and not to_delete:
        print(f"Nothing to prune ({len(archives)} backups, keep={keep}).")
    return to_delete


def read_manifest(archive_path: Path) -> dict:
    """Return the manifest dict from an archive."""
    with zipfile.ZipFile(archive_path, "r") as zf:
        if "manifest.json" in zf.namelist():
            return json.loads(zf.read("manifest.json").decode("utf-8"))
    return {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup and restore Solo Builder state.")
    sub = parser.add_subparsers(dest="cmd")

    p_backup = sub.add_parser("backup",  help="Create a backup archive")
    p_backup.add_argument("--label",      default="", help="Optional label for the archive name")
    p_backup.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    p_backup.add_argument("--quiet",      action="store_true")

    p_restore = sub.add_parser("restore", help="Restore from an archive")
    p_restore.add_argument("archive",     help="Archive filename or full path")
    p_restore.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    p_restore.add_argument("--dry-run",   action="store_true")
    p_restore.add_argument("--quiet",     action="store_true")

    p_list = sub.add_parser("list",    help="List available backups")
    p_list.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    p_list.add_argument("--quiet",     action="store_true")

    p_prune = sub.add_parser("prune",  help="Delete old backups")
    p_prune.add_argument("--keep",     type=int, default=10, help="Number of recent backups to keep")
    p_prune.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    p_prune.add_argument("--quiet",    action="store_true")

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 2

    backup_dir = Path(args.backup_dir)

    try:
        if args.cmd == "backup":
            backup(backup_dir, label=args.label or None, quiet=args.quiet)
        elif args.cmd == "restore":
            archive = Path(args.archive)
            if not archive.is_absolute():
                archive = backup_dir / archive
            restore(archive, dry_run=args.dry_run, quiet=args.quiet)
        elif args.cmd == "list":
            list_backups(backup_dir, quiet=args.quiet)
        elif args.cmd == "prune":
            prune(backup_dir, keep=args.keep, quiet=args.quiet)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
