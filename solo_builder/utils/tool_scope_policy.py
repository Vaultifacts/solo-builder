"""Tool-scope enforcement policy (AI-033).

Defines which tools are allowed for each action type when Claude executes
autonomous steps. Constrains the permission surface per task category.

Usage:
    from solo_builder.utils.tool_scope_policy import ToolScopePolicy, load_scope_policy, evaluate_scope

    policy = load_scope_policy()
    result = evaluate_scope(policy, action_type="read_only", requested_tools=["Read", "Grep"])
    # ScopeResult(allowed=True, denied=[], action_type="read_only")
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Built-in default allowlists per action type
# ---------------------------------------------------------------------------
# Keys are action_type strings written into HITL / executor configs.
# Values are frozensets of tool names that are permitted for that action type.

_DEFAULT_ALLOWLISTS: dict[str, frozenset[str]] = {
    # Pure read — no writes permitted
    "read_only": frozenset({
        "Read", "Grep", "Glob", "Bash",
    }),
    # Analysis / search — read + web fetch, no writes
    "analysis": frozenset({
        "Read", "Grep", "Glob", "Bash",
        "WebFetch", "WebSearch",
    }),
    # File edits — may write/edit files but no bash execution
    "file_edit": frozenset({
        "Read", "Grep", "Glob",
        "Write", "Edit",
    }),
    # Full execution — all standard tools
    "full_execution": frozenset({
        "Read", "Grep", "Glob", "Bash",
        "Write", "Edit",
        "WebFetch", "WebSearch",
    }),
    # Verification — read + bash (run tests) only
    "verification": frozenset({
        "Read", "Grep", "Glob", "Bash",
    }),
    # Planning — read + web only (no writes, no exec)
    "planning": frozenset({
        "Read", "Grep", "Glob",
        "WebFetch", "WebSearch",
    }),
}

# Ordered priority: tools in a higher tier are implicitly included in lower tiers
# This is used for validation warnings only — not for enforcement.
_ACTION_TYPE_TIER: dict[str, int] = {
    "read_only":     0,
    "planning":      1,
    "analysis":      2,
    "verification":  3,
    "file_edit":     3,
    "full_execution": 4,
}


@dataclass(frozen=True)
class ScopeResult:
    """Outcome of a scope evaluation."""
    allowed:     bool
    denied:      list[str]
    action_type: str
    requested:   list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed":     self.allowed,
            "denied":      self.denied,
            "action_type": self.action_type,
            "requested":   self.requested,
        }


@dataclass(frozen=True)
class ToolScopePolicy:
    """Immutable tool-scope policy loaded from settings.json (or defaults)."""
    allowlists: dict[str, frozenset[str]]   # action_type → allowed tool set
    default_action_type: str                # fallback when no type specified

    def allowed_tools(self, action_type: str) -> frozenset[str]:
        """Return the set of allowed tools for *action_type*."""
        return self.allowlists.get(action_type, self.allowlists.get(self.default_action_type, frozenset()))

    def known_action_types(self) -> list[str]:
        return sorted(self.allowlists.keys())

    def validate(self) -> list[str]:
        """Return a list of warning strings; empty list = no warnings."""
        warnings: list[str] = []
        if self.default_action_type not in self.allowlists:
            warnings.append(
                f"default_action_type '{self.default_action_type}' not present in allowlists"
            )
        for action_type, tools in self.allowlists.items():
            if not tools:
                warnings.append(f"action_type '{action_type}' has empty allowlist")
        return warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowlists": {k: sorted(v) for k, v in self.allowlists.items()},
            "default_action_type": self.default_action_type,
        }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _parse_csv_set(value: str) -> frozenset[str]:
    """Parse 'A,B,C' → frozenset({'A','B','C'})."""
    return frozenset(t.strip() for t in value.split(",") if t.strip())


def load_scope_policy(settings_path: str | Path | None = None) -> ToolScopePolicy:
    """Load ToolScopePolicy from settings.json, merging over built-in defaults.

    Config keys read from settings.json:
    - SCOPE_<ACTION_TYPE>: comma-separated tool names, e.g.
        "SCOPE_READ_ONLY": "Read,Grep,Glob"
    - SCOPE_DEFAULT_ACTION_TYPE: default action type string
    """
    if settings_path is None:
        settings_path = Path(__file__).resolve().parents[1] / "config" / "settings.json"
    settings_path = Path(settings_path)

    cfg: dict[str, Any] = {}
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    # Start from built-in defaults
    allowlists: dict[str, frozenset[str]] = dict(_DEFAULT_ALLOWLISTS)

    # Override / add from settings.json "SCOPE_<ACTION_TYPE>" keys
    for key, value in cfg.items():
        if key.startswith("SCOPE_") and key != "SCOPE_DEFAULT_ACTION_TYPE":
            action_type = key[len("SCOPE_"):].lower()
            allowlists[action_type] = _parse_csv_set(str(value))

    default_action_type = str(cfg.get("SCOPE_DEFAULT_ACTION_TYPE", "full_execution"))

    return ToolScopePolicy(
        allowlists=allowlists,
        default_action_type=default_action_type,
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_scope(
    policy: ToolScopePolicy,
    action_type: str,
    requested_tools: list[str],
) -> ScopeResult:
    """Check whether *requested_tools* are all permitted for *action_type*.

    Returns a ScopeResult. result.allowed is False if any tool is denied.
    """
    permitted = policy.allowed_tools(action_type)
    denied = [t for t in requested_tools if t not in permitted]
    return ScopeResult(
        allowed=len(denied) == 0,
        denied=denied,
        action_type=action_type,
        requested=list(requested_tools),
    )
