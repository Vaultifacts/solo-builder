"""Read-only configuration constants for Solo Builder.

These constants are loaded once from settings.json at import time and are
never mutated at runtime (not targeted by do_set, not patched by tests).

They are re-imported into solo_builder_cli.py so that the canonical names
solo_builder_cli.DAG_UPDATE_INTERVAL etc. remain accessible for any code
that reads them from the module namespace.
"""
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load() -> dict:
    from utils.helper_functions import load_settings
    return load_settings(os.path.join(_HERE, "config", "settings.json"))


_C = _load()

DAG_UPDATE_INTERVAL    : int  = _C["DAG_UPDATE_INTERVAL"]
BAR_WIDTH              : int  = _C["BAR_WIDTH"]
MAX_ALERTS             : int  = _C["MAX_ALERTS"]
EXEC_MAX_PER_STEP      : int  = _C["EXECUTOR_MAX_PER_STEP"]
MAX_SUBTASKS_PER_BRANCH: int  = _C.get("MAX_SUBTASKS_PER_BRANCH", 20)
MAX_BRANCHES_PER_TASK  : int  = _C.get("MAX_BRANCHES_PER_TASK",   10)
CLAUDE_TIMEOUT         : int  = _C.get("CLAUDE_TIMEOUT",           60)
ANTHROPIC_MODEL        : str  = _C.get("ANTHROPIC_MODEL",      "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS   : int  = _C.get("ANTHROPIC_MAX_TOKENS",  4096)
REVIEW_MODE            : bool = bool(_C.get("REVIEW_MODE",        False))

_PDF_OUTPUT_PATH_RAW: str = _C["PDF_OUTPUT_PATH"]
PDF_OUTPUT_PATH: str = (
    _PDF_OUTPUT_PATH_RAW if os.path.isabs(_PDF_OUTPUT_PATH_RAW)
    else os.path.join(_HERE, _PDF_OUTPUT_PATH_RAW)
)

_PROJECT_CONTEXT: str = (
    "Context: Solo Builder is a Python terminal CLI that uses six AI agents "
    "(Planner, ShadowAgent, SelfHealer, Executor, Verifier, MetaOptimizer) "
    "and the Anthropic SDK to manage DAG-based software project tasks. "
)
