"""hitl_gate.py — Human-in-the-Loop gate for Solo Builder executor.

Evaluates whether a subtask requires human approval before Claude executes it.
This is Phase 2 of the HITL Trigger Design (TASK-312 / TASK-313).

Usage (future — Phase 3 wires this into executor.py):
    from .hitl_gate import evaluate, HITLBlockError

    level = evaluate(st_tools, description)
    if level == 3:
        raise HITLBlockError(...)
    elif level == 2:
        confirm = input(f"[HITL] Approve? [y/N] ")
        if confirm.strip().lower() != "y":
            raise HITLBlockError(...)
    elif level == 1:
        logger.info("hitl_notify ...")
    # level 0: proceed

HITL levels
-----------
0  Auto    — proceed without human input
1  Notify  — log and proceed; human reviews asynchronously
2  Pause   — halt and request explicit approval before continuing
3  Block   — reject; requires human to re-scope the task
"""

_DESTRUCTIVE_KEYWORDS = frozenset([
    "delete", "drop", "purge", "rm -rf", "rmdir", "truncate",
    "wipe", "overwrite", "format",
])

_PATH_TRAVERSAL_PATTERNS = ("..", "~/", "/etc/", "/usr/", "C:\\Windows")

# Tools that require a Pause gate
_PAUSE_TOOLS = frozenset(["Bash", "Write", "Edit"])

# Tools that require a Notify gate
_NOTIFY_TOOLS = frozenset(["WebFetch", "WebSearch"])

# Tools that are always safe (read-only)
_SAFE_TOOLS = frozenset(["Read", "Glob", "Grep"])


class HITLBlockError(RuntimeError):
    """Raised when evaluate() returns level 3 or the user declines a Pause."""


def evaluate(tools: str, description: str) -> int:
    """Return the minimum HITL level required for this operation.

    Parameters
    ----------
    tools       : comma-separated tool list from the subtask "tools" field
                  (empty string means no tools)
    description : the subtask description string

    Returns
    -------
    int
        0 = Auto, 1 = Notify, 2 = Pause, 3 = Block
    """
    tool_set = {t.strip() for t in tools.split(",") if t.strip()} if tools else set()
    desc_lower = description.lower()

    # Rule 1: Bash always requires Pause
    if "Bash" in tool_set:
        return 2

    # Rule 2: Write or Edit requires Pause
    if tool_set & {"Write", "Edit"}:
        return 2

    # Rule 3: Web tools require Notify
    if tool_set & _NOTIFY_TOOLS:
        return 1

    # Rule 4: Destructive keyword in description requires Pause
    for kw in _DESTRUCTIVE_KEYWORDS:
        if kw in desc_lower:
            return 2

    # Rule 5: Path traversal in description requires Pause
    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern in description:
            return 2

    # Rule 6: No tools, or only safe read-only tools → Auto
    return 0


def level_name(level: int) -> str:
    """Return the human-readable name for a HITL level."""
    return {0: "Auto", 1: "Notify", 2: "Pause", 3: "Block"}.get(level, "Unknown")
