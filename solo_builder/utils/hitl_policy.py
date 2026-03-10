"""HITL policy loader — TASK-338 (AI-026, AI-032).

Loads HITL trigger thresholds from settings.json and exposes them as a
validated HitlPolicy object.  This makes HITL criteria inspectable,
testable, and configurable without touching hitl_gate.py.

HITL levels (from docs/HITL_TRIGGER_DESIGN.md):
    0  Auto    — proceed without human input
    1  Notify  — log and proceed; human reviews asynchronously
    2  Pause   — halt and request explicit approval
    3  Block   — reject; requires human to re-scope the task

Usage:
    from utils.hitl_policy import HitlPolicy, load_policy, evaluate_with_policy

    policy = load_policy()
    level  = evaluate_with_policy(policy, tools="Bash,Read", description="rm -rf /")
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_SOLO_ROOT = Path(__file__).resolve().parents[1]
_SETTINGS_PATH = _SOLO_ROOT / "config" / "settings.json"

# Defaults mirror the hardcoded constants in hitl_gate.py
_DEFAULTS = {
    "HITL_PAUSE_TOOLS":    "Bash,Write,Edit",
    "HITL_NOTIFY_TOOLS":   "WebFetch,WebSearch",
    "HITL_BLOCK_KEYWORDS": "force-push,branch -D,reset --hard",
    "HITL_PAUSE_KEYWORDS": "delete,drop,purge,rm -rf,truncate,wipe,overwrite,format",
}

_PATH_TRAVERSAL_PATTERNS = ("..", "~/", "/etc/", "/usr/", "C:\\Windows")


@dataclass(frozen=True)
class HitlPolicy:
    """Immutable snapshot of HITL trigger thresholds loaded from config."""

    pause_tools:    frozenset = field(default_factory=frozenset)
    notify_tools:   frozenset = field(default_factory=frozenset)
    block_keywords: frozenset = field(default_factory=frozenset)
    pause_keywords: frozenset = field(default_factory=frozenset)

    def validate(self) -> list[str]:
        """Return a list of validation warnings (empty = policy is sane)."""
        warnings: list[str] = []
        if not self.pause_tools:
            warnings.append("HITL_PAUSE_TOOLS is empty — no tools require Pause approval")
        if "Bash" not in self.pause_tools:
            warnings.append("HITL_PAUSE_TOOLS does not include 'Bash' — shell execution unguarded")
        return warnings

    def to_dict(self) -> dict:
        return {
            "pause_tools":    sorted(self.pause_tools),
            "notify_tools":   sorted(self.notify_tools),
            "block_keywords": sorted(self.block_keywords),
            "pause_keywords": sorted(self.pause_keywords),
        }


def _parse_csv(value: str) -> frozenset:
    return frozenset(v.strip() for v in value.split(",") if v.strip())


def load_policy(settings_path: Optional[Path] = None) -> HitlPolicy:
    """Load HITL policy from settings.json.

    Falls back to _DEFAULTS for any missing key.  Never raises — returns a
    valid policy even if the settings file is absent or malformed.
    """
    path = settings_path or _SETTINGS_PATH
    cfg: dict = {}
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    def _get(key: str) -> str:
        return cfg.get(key, _DEFAULTS[key])

    return HitlPolicy(
        pause_tools=    _parse_csv(_get("HITL_PAUSE_TOOLS")),
        notify_tools=   _parse_csv(_get("HITL_NOTIFY_TOOLS")),
        block_keywords= _parse_csv(_get("HITL_BLOCK_KEYWORDS")),
        pause_keywords= _parse_csv(_get("HITL_PAUSE_KEYWORDS")),
    )


def evaluate_with_policy(policy: HitlPolicy, tools: str, description: str) -> int:
    """Return the minimum HITL level for this operation, using the given policy.

    Parameters
    ----------
    policy      : HitlPolicy loaded from settings
    tools       : comma-separated tool list (empty string = no tools)
    description : the subtask description

    Returns
    -------
    int — 0 (Auto), 1 (Notify), 2 (Pause), 3 (Block)
    """
    tool_set  = _parse_csv(tools)
    desc_lower = description.lower()

    # Level 3: Block — known destructive git operations
    for kw in policy.block_keywords:
        if kw in description:
            return 3

    # Level 2: Pause — tool-based
    if tool_set & policy.pause_tools:
        return 2

    # Level 2: Pause — keyword in description
    for kw in policy.pause_keywords:
        if kw in desc_lower:
            return 2

    # Level 2: Pause — path traversal
    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern in description:
            return 2

    # Level 1: Notify — web tools
    if tool_set & policy.notify_tools:
        return 1

    return 0
