"""
Shared constants for the Solo Builder API.
"""
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

STATE_PATH    = _PROJECT_ROOT / "state" / "solo_builder_state.json"
TRIGGER_PATH  = _PROJECT_ROOT / "state" / "run_trigger"
VERIFY_TRIGGER  = _PROJECT_ROOT / "state" / "verify_trigger.json"
DESCRIBE_TRIGGER = _PROJECT_ROOT / "state" / "describe_trigger.json"
TOOLS_TRIGGER   = _PROJECT_ROOT / "state" / "tools_trigger.json"
SET_TRIGGER     = _PROJECT_ROOT / "state" / "set_trigger.json"
SETTINGS_PATH   = _PROJECT_ROOT / "config" / "settings.json"
RENAME_TRIGGER  = _PROJECT_ROOT / "state" / "rename_trigger.json"
STOP_TRIGGER    = _PROJECT_ROOT / "state" / "stop_trigger"
HEAL_TRIGGER    = _PROJECT_ROOT / "state" / "heal_trigger.json"
ADD_TASK_TRIGGER        = _PROJECT_ROOT / "state" / "add_task_trigger.json"
ADD_BRANCH_TRIGGER      = _PROJECT_ROOT / "state" / "add_branch_trigger.json"
PRIORITY_BRANCH_TRIGGER = _PROJECT_ROOT / "state" / "prioritize_branch_trigger.json"
UNDO_TRIGGER            = _PROJECT_ROOT / "state" / "undo_trigger"
DEPENDS_TRIGGER         = _PROJECT_ROOT / "state" / "depends_trigger.json"
UNDEPENDS_TRIGGER       = _PROJECT_ROOT / "state" / "undepends_trigger.json"
RESET_TRIGGER           = _PROJECT_ROOT / "state" / "reset_trigger"
SNAPSHOT_TRIGGER        = _PROJECT_ROOT / "state" / "snapshot_trigger"
PAUSE_TRIGGER           = _PROJECT_ROOT / "state" / "pause_trigger"
HEARTBEAT_PATH = _PROJECT_ROOT / "state" / "step.txt"
JOURNAL_PATH  = _PROJECT_ROOT / "journal.md"
OUTPUTS_PATH  = _PROJECT_ROOT / "solo_builder_outputs.md"
CACHE_DIR     = Path(os.environ.get("CACHE_DIR",
                     str(_PROJECT_ROOT.parent / "claude" / "cache")))

DAG_EXPORT_PATH    = _PROJECT_ROOT / "dag_export.json"
DAG_IMPORT_TRIGGER = _PROJECT_ROOT / "state" / "dag_import_trigger.json"

_CONFIG_DEFAULTS = {
    "STALL_THRESHOLD": 5,
    "SNAPSHOT_INTERVAL": 20,
    "DAG_UPDATE_INTERVAL": 5,
    "PDF_OUTPUT_PATH": "./snapshots/",
    "STATE_PATH": "./state/solo_builder_state.json",
    "JOURNAL_PATH": "journal.md",
    "AUTO_SAVE_INTERVAL": 10,
    "AUTO_STEP_DELAY": 1.5,
    "MAX_SUBTASKS_PER_BRANCH": 20,
    "MAX_BRANCHES_PER_TASK": 10,
    "VERBOSITY": "INFO",
    "BAR_WIDTH": 20,
    "MAX_ALERTS": 10,
    "EXECUTOR_MAX_PER_STEP": 6,
    "EXECUTOR_VERIFY_PROBABILITY": 0.9,
    "CLAUDE_TIMEOUT": 60,
    "CLAUDE_ALLOWED_TOOLS": "",
    "ANTHROPIC_MODEL": "claude-sonnet-4-6",
    "ANTHROPIC_MAX_TOKENS": 4096,
    "REVIEW_MODE": False,
    "WEBHOOK_URL": "",
}

_SHORTCUTS = [
    {"key": "j",    "description": "Select next task"},
    {"key": "k",    "description": "Select previous task"},
    {"key": "←",    "description": "History: previous page"},
    {"key": "→",    "description": "History: next page"},
    {"key": "r",    "description": "Run one step"},
    {"key": "g",    "description": "Open Graph tab"},
    {"key": "b",    "description": "Switch to Branches tab"},
    {"key": "s",    "description": "Switch to Subtasks tab"},
    {"key": "h",    "description": "Switch to History tab"},
    {"key": "v",    "description": "Focus Verify input"},
    {"key": "p",    "description": "Pause / resume polling"},
    {"key": "?",    "description": "Toggle keyboard shortcut help"},
    {"key": "Esc",  "description": "Close modal / clear search"},
]

_AVG_TOKENS_PER_ENTRY = 550  # matches ResponseCache._AVG_TOKENS_PER_ENTRY
_STATS_FILE = "session_stats.json"

METRICS_JSONL_PATH = _PROJECT_ROOT / "metrics.jsonl"
