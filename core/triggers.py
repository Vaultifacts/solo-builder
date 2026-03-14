"""
core/triggers.py
Trigger-file IPC helpers extracted from solo_builder_cli.py.

The Solo Builder uses filesystem trigger files for inter-process
communication between the CLI, API, and Discord bot. This module
centralizes trigger path definitions and consumption helpers.

Trigger types:
    - JSON triggers (.json): contain structured payloads, consumed atomically
    - Flag triggers (no extension): presence = signal, content ignored
"""

import json
import os
from typing import Any, Dict, List, Optional, Union


# ── Canonical trigger path registry ──────────────────────────────────────────

# All trigger filenames, keyed by logical name.
# Paths are relative to the state/ directory.
TRIGGER_FILES: Dict[str, str] = {
    "run":              "run_trigger",
    "stop":             "stop_trigger",
    "add_task":         "add_task_trigger.json",
    "add_branch":       "add_branch_trigger.json",
    "prioritize_branch": "prioritize_branch_trigger.json",
    "describe":         "describe_trigger.json",
    "rename":           "rename_trigger.json",
    "tools":            "tools_trigger.json",
    "reset":            "reset_trigger",
    "snapshot":         "snapshot_trigger",
    "set":              "set_trigger.json",
    "depends":          "depends_trigger.json",
    "undepends":        "undepends_trigger.json",
    "undo":             "undo_trigger",
    "pause":            "pause_trigger",
    "heal":             "heal_trigger.json",
    "verify":           "verify_trigger.json",
}


def trigger_path(state_dir: str, name: str) -> str:
    """
    Return the absolute path for a named trigger.

    >>> trigger_path("/app/state", "run")
    '/app/state/run_trigger'
    """
    return os.path.join(state_dir, TRIGGER_FILES[name])


def all_trigger_paths(state_dir: str) -> Dict[str, str]:
    """Return all trigger paths keyed by logical name."""
    return {k: os.path.join(state_dir, v) for k, v in TRIGGER_FILES.items()}


# ── Consumption helpers ──────────────────────────────────────────────────────

def consume_json_trigger(path: str) -> Optional[Union[Dict, List]]:
    """
    Read, parse, and atomically delete a JSON trigger file.

    Returns the parsed dict/list on success, or None if the file
    doesn't exist or can't be read/parsed.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        os.remove(path)
        return data
    except Exception:
        return None


def consume_flag_trigger(path: str) -> bool:
    """
    Check for and consume a flag-type trigger (presence-only, no payload).

    Returns True if the trigger existed and was consumed, False otherwise.
    """
    if not os.path.exists(path):
        return False
    try:
        os.remove(path)
    except OSError:
        pass
    return True


def write_flag_trigger(path: str) -> None:
    """Write a flag trigger file (content is irrelevant)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("1")


def trigger_exists(path: str) -> bool:
    """Check if a trigger file exists without consuming it."""
    return os.path.exists(path)


# ── Startup cleanup ─────────────────────────────────────────────────────────

def cleanup_stale_triggers(state_dir: str,
                           exclude: Optional[List[str]] = None) -> int:
    """
    Remove stale trigger files from a previous run.

    Args:
        state_dir: Path to the state/ directory.
        exclude: Logical trigger names to skip (e.g., ["verify"]).

    Returns the number of files removed.
    """
    os.makedirs(state_dir, exist_ok=True)
    skip = set(exclude or [])
    removed = 0
    for name, filename in TRIGGER_FILES.items():
        if name in skip:
            continue
        path = os.path.join(state_dir, filename)
        try:
            os.remove(path)
            removed += 1
        except FileNotFoundError:
            pass
    return removed
