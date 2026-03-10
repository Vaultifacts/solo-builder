"""
notion_config.py — stable Notion workspace IDs and repo paths.
Do not hardcode secrets here; token is read from the environment.
"""
import os
import pathlib

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
NOTION_TOKEN = os.environ.get("NOTION_INTEGRATION_TOKEN", "")
NOTION_VERSION = "2022-06-28"

# ---------------------------------------------------------------------------
# Page / database IDs  (stable — do not change)
# ---------------------------------------------------------------------------
MAIN_PAGE_ID      = "31d3f0ecf3828080ac93f23817b7965a"   # "Solo Builder" root
CHECKLIST_PAGE_ID = "31f3f0ecf3828045bb7ddb88ed89e708"   # Layer 1 + Layer 3
HEALTH_DASH_ID    = "31f3f0ecf38281779922ffabbe539d3f"   # Project Health Dashboard
GAP_AUDIT_DB_ID   = "47f14dd11fda4847bdd6be91cf67a756"   # Gap Audit Findings Database page
GAP_AUDIT_DS_ID   = "43efefab-beb1-4c9b-9a00-e716759b0299"  # data source (collection)

# ---------------------------------------------------------------------------
# AI Execution Log DB — created lazily on first notion_ai_log run
# ---------------------------------------------------------------------------
AI_LOG_DB_ID_FILE = "generated/.ai_log_db_id"

# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------
REPO_ROOT      = pathlib.Path(__file__).parent.parent
CHANGELOG      = REPO_ROOT / "CHANGELOG.md"
STATE_JSON     = REPO_ROOT / "claude" / "STATE.json"
GENERATED_DIR  = REPO_ROOT / "generated"
FEEDBACK_JSON  = GENERATED_DIR / "notion_feedback.json"
NEXT_TASK_JSON = GENERATED_DIR / "next_task.json"

# ---------------------------------------------------------------------------
# Metrics extracted from CHANGELOG — these are the labels that appear
# verbatim in the Health Dashboard Summary Metrics table (cell[0] text).
# ---------------------------------------------------------------------------
METRIC_LABELS = {
    "release":      "Current Release",
    "tasks_merged": "Tasks Merged",
    "api_tests":    "API Tests",
    "discord_tests": "Discord Tests",
}

# Layer 3 section marker used to scope to_do block parsing
LAYER3_HEADING = "Layer 3"
BLOCKERS_HEADING = "Blockers"
