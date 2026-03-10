# Notion Automation — Operating Workflow

## Overview

This system keeps the Solo Builder Notion workspace in sync with the repo
and selects the next safe task to work on.

**Three-layer architecture (never mix layers):**

| Layer | What it is | Where |
|---|---|---|
| Layer 1 | Project deliverables (8 items, 100% complete) | Checklist page |
| Layer 2 | 1,052 gap audit findings across 17 domains | Gap Audit Findings Database |
| Layer 3 | Active priorities selected for near-term action | Checklist page |

Completion % = Layer 1 only. Layer 2 never affects completion metrics.

---

## Daily Automated Flow

```
Repo change
    ↓
git commit
    ↓
.git/hooks/post-commit  (runs automatically after every commit)
    ↓
tools/notion_sync.py    (updates Health Dashboard + Checklist metrics in Notion)
    ↓
[manually or on schedule]
    ↓
tools/notion_feedback.py   →   generated/notion_feedback.json
    ↓
tools/task_orchestrator.py →   generated/next_task.json
    ↓
Claude executes next_task.json
    ↓
tools/notion_ai_log.py     (logs execution result to AI Execution Log database)
```

---

## Script Reference

### 0. Prerequisites

```powershell
# Set once per shell session (PowerShell)
$env:NOTION_INTEGRATION_TOKEN = "<your-token>"

# Or for bash
export NOTION_INTEGRATION_TOKEN="<your-token>"
```

Token prefix is not assumed — works with `ntn_...`, `secret_...`, or any prefix.

---

### 1. Verify Permissions (run once after setup)

```bash
python tools/verify_permissions.py
```

Checks that the integration token has read/write access to:
- Solo Builder (root page)
- Project Cumulative Checklist
- Project Health Dashboard
- Gap Audit Findings Database

If a resource shows ❌, open it in Notion → Connections → Add connection → select your integration.

---

### 2. Sync repo metrics to Notion

**Dry-run first (always safe):**
```bash
python tools/notion_sync.py --dry-run
```

**Live write:**
```bash
python tools/notion_sync.py
```

**Inspect block structure without writing:**
```bash
python tools/notion_sync.py --audit
```

What gets updated:
| Target | What changes |
|---|---|
| Health Dashboard — Summary Metrics table | Current Release, Tasks Merged, API Tests, Discord Tests |
| Health Dashboard — quote block | Last reconciliation date |
| Checklist — footer paragraph | Last reconciled date, version, task count |

Matching strategy: rows matched by **label text** (not position).  The sync
is resilient to manual page edits as long as the heading "Summary Metrics"
and the row labels are not renamed.

---

### 3. Generate feedback JSON

```bash
python tools/notion_feedback.py --verbose
```

Reads from Notion:
- Layer 1 deliverable table → completion count
- Layer 3 to_do blocks → active priorities with checked state
- Blockers/Risks table → risk items
- Gap Audit Findings Database → 17 domain summaries

Writes:
```
generated/notion_feedback.json
```

Key fields in the output:
```json
{
  "layer1_completion": { "complete": 8, "total": 8, "pct": 100 },
  "layer3_priorities": [ { "title": "...", "checked": false, "audit_refs": "..." } ],
  "risks": [ { "risk": "...", "audit_ref": "...", "severity": "High" } ],
  "gap_domains": [ { "domain": "...", "gap_count": 78, "severity": "High" } ],
  "summary": {
    "total_gaps": 1052,
    "high_severity_domains": ["AI Assisted Development", ...],
    "open_priorities": 7
  }
}
```

---

### 4. Select next task

```bash
python tools/task_orchestrator.py --verbose
```

Reads `generated/notion_feedback.json`, scores each unchecked Layer 3 item
by safety (doc/design = 90, spec = 75, tests = 65, cross-cutting = 50),
then writes the highest-scoring unchecked item to:

```
generated/next_task.json
```

Safety rules:
- Only unchecked items are eligible
- Among ties, original Notion order is preserved (first = highest user priority)
- Output includes: title, audit_refs, risk_level, rationale, estimated_scope, suggested_task_id

---

### 5. Log an execution run

**From CLI:**
```bash
python tools/notion_ai_log.py \
    --task "TASK-311" \
    --status Success \
    --model "claude-sonnet-4-6" \
    --duration 42 \
    --notes "Implemented ThreatModelDocument"
```

**From Python (import):**
```python
from notion_ai_log import log_run
log_run("TASK-311", "Success", "claude-sonnet-4-6", duration_s=42,
        notes="Implemented ThreatModelDocument")
```

Valid statuses: `Success` | `Failed` | `Partial` | `Skipped`

The AI Execution Log database is created automatically on first use and its ID
is cached in `generated/.ai_log_db_id`.  If the cache file is lost, the script
searches Notion for the existing database before creating a new one (no duplicates).

---

## Post-Commit Hook Installation

The hook file is at `tools/post-commit.hook`.  Install it once:

**Git Bash / bash:**
```bash
cp tools/post-commit.hook .git/hooks/post-commit
chmod +x .git/hooks/post-commit
```

**PowerShell:**
```powershell
Copy-Item tools\post-commit.hook .git\hooks\post-commit
# chmod is handled automatically by Git on Windows
```

The hook runs `notion_sync.py` silently after every commit.
It skips without error if `NOTION_INTEGRATION_TOKEN` is not set in the shell.
It never blocks a commit — all errors are suppressed with `|| true`.

---

## Dependency Installation

```bash
pip install -r tools/requirements.txt
```

Installs:
- `requests>=2.32` — Notion REST API calls
- `charset-normalizer>=3.0` — suppresses the requests dependency warning

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ERROR: NOTION_INTEGRATION_TOKEN is not set` | Set the env var (see Prerequisites above) |
| `404 page not found` in verify_permissions | Share the page with your integration in Notion |
| `RequestsDependencyWarning` on import | `pip install charset-normalizer` |
| `! row not found for label 'Current Release'` | Run `--audit` to inspect the block tree; confirm the heading "Summary Metrics" exists |
| Duplicate AI Execution Log databases | Safe: `ensure_database()` searches before creating; delete the extra one manually |
| Hook doesn't run | Confirm `.git/hooks/post-commit` is executable: `ls -la .git/hooks/post-commit` |
