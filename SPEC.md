# Solo Builder v2.1.49 — Full Specification & Capability Overview

> Exhaustive technical reference for every system, agent, interface, data structure, and operational mode in Solo Builder.

---

## Table of Contents

1. [Project Identity](#1-project-identity)
2. [Architecture Overview](#2-architecture-overview)
3. [DAG Data Model](#3-dag-data-model)
4. [Agent System (6 Agents)](#4-agent-system-6-agents)
5. [Execution Engine (4 Tiers)](#5-execution-engine-4-tiers)
6. [CLI Interface](#6-cli-interface)
7. [REST API (Flask)](#7-rest-api-flask)
8. [Web Dashboard](#8-web-dashboard)
9. [Discord Bot](#9-discord-bot)
10. [Inter-Process Communication (IPC)](#10-inter-process-communication-ipc)
11. [Persistence & State Management](#11-persistence--state-management)
12. [Configuration System](#12-configuration-system)
13. [PDF Snapshot System](#13-pdf-snapshot-system)
14. [Profiler Harness](#14-profiler-harness)
15. [Testing Infrastructure](#15-testing-infrastructure)
16. [CI/CD Pipeline](#16-cicd-pipeline)
17. [Terminal Display System](#17-terminal-display-system)
18. [Utilities & Shared Library](#18-utilities--shared-library)
19. [File Inventory](#19-file-inventory)
20. [Dependency Map](#20-dependency-map)
21. [Version History Summary](#21-version-history-summary)

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Name** | Solo Builder |
| **Version** | 2.1.49 |
| **Release Date** | 2026-03-05 |
| **Language** | Python 3.11+ (targets 3.13) |
| **License** | MIT |
| **Repository** | `github.com/Vaultifacts/solo-builder` |
| **Package** | `solo-builder` (PyPI-ready via `pyproject.toml`) |
| **Entry Point** | `solo_builder_cli:main` |
| **Total Source Lines** | ~30,000+ (CLI: 3,533 / API: 724 / Bot: 1,944 / Tests: 3,199 / Utils: 185 / Profiler: 333 / PDF: 389 / Demo: 21,222) |
| **Total Tests** | 265 (194 bot + 71 API) |
| **Total CLI Commands** | 34 |
| **Total API Endpoints** | 30+ (GET + POST) |
| **Total Discord Commands** | 45+ (slash + plain-text) |

**One-liner:** A Python terminal CLI that uses six AI agents and the Anthropic SDK to manage DAG-based project tasks — with a live web dashboard and Discord bot.

---

## 2. Architecture Overview

### 2.1 High-Level System Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                          │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │ Terminal  │    │ Web Dashboard│    │    Discord Bot        │   │
│  │   CLI     │    │ (SPA @ :5000)│    │  (slash + plain-text)│   │
│  └────┬─────┘    └──────┬───────┘    └──────────┬───────────┘   │
│       │                 │                       │               │
│       │          ┌──────┴───────┐        ┌──────┴──────┐        │
│       │          │  Flask API   │        │  discord.py │        │
│       │          │  (30+ routes)│        │  (45+ cmds) │        │
│       │          └──────┬───────┘        └──────┬──────┘        │
│       │                 │                       │               │
│       │      ┌──────────┴───────────────────────┘               │
│       │      │  IPC: trigger files (state/*.json)               │
│       │      │                                                  │
│  ┌────┴──────┴──────────────────────────────────────────────┐   │
│  │              SOLO BUILDER CLI ORCHESTRATOR                │   │
│  │                                                           │   │
│  │  Step Pipeline (per step):                                │   │
│  │  ┌─────────┐  ┌───────────┐  ┌───────────┐  ┌─────────┐ │   │
│  │  │ Planner │→│ShadowAgent│→│SelfHealer │→│Executor │ │   │
│  │  └─────────┘  └───────────┘  └───────────┘  └────┬────┘ │   │
│  │                                                    │      │   │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────────┐   │      │   │
│  │  │MetaOptim.│←│ShadowAgent│←│   Verifier    │←──┘      │   │
│  │  └──────────┘  └───────────┘  └───────────────┘          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────┴──────────────────────────────┐   │
│  │                    DATA LAYER                             │   │
│  │  state/solo_builder_state.json  │  journal.md            │   │
│  │  config/settings.json           │  state/step.txt        │   │
│  │  snapshots/*.pdf                │  solo_builder_outputs.md│   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Per-Step Pipeline

Every step executes this 7-phase agent pipeline in sequence:

```
1. Planner.prioritize()        → sorted priority queue by risk score
2. ShadowAgent.detect_conflicts() → find shadow/status mismatches → resolve
3. SelfHealer.find_stalled()   → detect + heal stalled subtasks
4. Executor.execute_step()     → advance up to 6 subtasks (4-tier routing)
5. Verifier.verify()           → enforce branch/task roll-up consistency
6. ShadowAgent.update_expected() → sync expected state map
7. MetaOptimizer.record() + optimize() → adapt planner weights
```

Plus: auto-snapshot (every N steps), auto-save (every 5 steps), heartbeat write.

---

## 3. DAG Data Model

### 3.1 Hierarchy

```
DAG
 └── Task (N tasks, keyed "Task 0" .. "Task N")
      ├── status: Pending | Running | Verified
      ├── depends_on: [list of task names]
      └── branches
           └── Branch (keyed "Branch A" .. "Branch Z")
                ├── status: Pending | Running | Verified
                └── subtasks
                     └── Subtask (keyed "A1", "A2", "B1", etc.)
                          ├── status: Pending | Running | Review | Verified
                          ├── shadow: Pending | Done
                          ├── last_update: int (step number)
                          ├── description: str (Claude prompt)
                          ├── output: str (Claude response)
                          ├── tools: str (comma-separated, e.g. "Read,Glob,Grep")
                          └── history: [{status, step}, ...]
```

### 3.2 Default DAG (INITIAL_DAG)

The built-in DAG is a diamond fan-out/fan-in graph with **7 tasks**, **16 branches**, and **70 subtasks**:

| Task | Depends On | Branches | Subtasks | Description |
|------|-----------|----------|----------|-------------|
| Task 0 | (none — seed) | A (5), B (3) | 8 | Feature brainstorming, elevator pitch, risks |
| Task 1 | Task 0 | C (4), D (2) | 6 | DAG concepts, scheduling, shadow state |
| Task 2 | Task 0 | E (5), F (4) | 9 | Self-healing, MetaOptimizer, agent metrics |
| Task 3 | Task 0 | G (6), H (4), I (3) | 13 | CI, technical debt, agile, project mgmt |
| Task 4 | Task 0 | J (8), K (5) | 13 | Clean code, SOLID, TDD, linting, versioning |
| Task 5 | Task 0 | L (6), M (4), N (5) | 15 | Metrics, roadmaps, DX, open source, release |
| Task 6 | Tasks 1-5 | O (3), P (3) | 6 | Synthesis — reads state file, writes summary |

**Topology:** Task 0 is the root. Tasks 1–5 fan out from Task 0 (all depend on Task 0 only). Task 6 fans in from Tasks 1–5 (depends on all five). This creates a diamond pattern.

### 3.3 Subtask Status Lifecycle

```
Pending → Running → Verified              (normal flow)
Pending → Running → Review → Verified     (REVIEW_MODE enabled)
Running → Pending                          (SelfHealer reset — stalled)
Running → Pending                          (manual heal command)
```

### 3.4 Roll-Up Rules

- **Branch → Verified** when ALL subtasks are Verified
- **Branch → Running** when ANY subtask is Running
- **Task → Verified** when ALL branches are Verified
- **Task → Running** when ANY branch is Running
- **Task blocked** when ANY dependency task is not Verified

### 3.5 Dependency Resolution

Tasks are only eligible for execution when all tasks in their `depends_on` list have `status == "Verified"`. The Planner skips blocked tasks entirely during prioritization.

---

## 4. Agent System (6 Agents)

### 4.1 Planner

**File:** `solo_builder_cli.py:320-389`
**Class:** `Planner`

**Purpose:** Prioritizes subtasks by computed risk score — higher score = more urgent.

**Risk Score Calculation:**
```python
# Running subtasks (base priority 1000):
risk = 1000 * w_stall
if age >= stall_threshold:
    risk += 500 * w_stall + age * 20     # stalled — extra urgency
else:
    risk += age * 10 * w_staleness       # normal running

# Pending subtasks:
risk = age * 8 * w_staleness if age > 2 else 0
if shadow == "Done":
    risk += 50 * w_shadow                # shadow conflict bonus
```

**Weights** (adjustable by MetaOptimizer):
- `w_stall` (default 1.0) — stall urgency multiplier
- `w_staleness` (default 1.0) — age-based urgency multiplier
- `w_shadow` (default 1.0) — shadow-conflict urgency multiplier

**Caching:** Priority list is cached for `DAG_UPDATE_INTERVAL` steps (default 5). Cache refreshes immediately when the count of Verified tasks increases (unblocking dependents).

**Key Method:**
```python
def prioritize(dag, step) → List[(task, branch, subtask, risk_score)]
```

### 4.2 Executor

**File:** `solo_builder_cli.py:705-940`
**Class:** `Executor`

**Purpose:** Advances subtasks through `Pending → Running → Verified` using 4-tier execution routing.

**Per-step behavior:**
1. Scans priority list up to `max_per_step` (default 6)
2. Pending subtasks → set to Running
3. Running subtasks → route to appropriate executor tier
4. On success → set to Verified (or Review in REVIEW_MODE)
5. On failure → stays Running (retry next step or SelfHealer resets)

**Concurrency model:**
- SDK tool-use jobs: `asyncio.gather()` (async coroutines)
- Claude subprocess jobs: `ThreadPoolExecutor` (parallel processes)
- SDK direct jobs: `asyncio.gather()` (async coroutines)
- All three batches run sequentially per step; within each batch, jobs run concurrently

**Roll-up:** After each verification, cascading roll-up checks branch → task status.

### 4.3 ShadowAgent

**File:** `solo_builder_cli.py:945-996`
**Class:** `ShadowAgent`

**Purpose:** Maintains an expected-state map and detects shadow/status inconsistencies.

**Conflict types:**
1. `shadow == "Done"` but `status != "Verified"` → stale shadow
2. `status == "Verified"` but `shadow == "Pending"` → shadow lag

**Resolution:** Aligns shadow with actual status (sets shadow to "Done" if Verified, "Pending" otherwise).

**Invoked twice per step:**
1. Before Executor — detect and resolve conflicts
2. After Verifier — update expected state map

### 4.4 Verifier

**File:** `solo_builder_cli.py:1001-1036`
**Class:** `Verifier`

**Purpose:** Enforces DAG structural invariants by fixing inconsistent branch/task statuses.

**Rules enforced:**
- If all subtasks Verified but branch is not → fix branch to Verified
- If any subtask Running but branch is Pending → fix branch to Running
- If all branches Verified but task is not → fix task to Verified
- If any branch Running but task is Pending → fix task to Running

### 4.5 SelfHealer

**File:** `solo_builder_cli.py:1042-1085`
**Class:** `SelfHealer`

**Purpose:** Detects subtasks stalled in Running state and resets them to Pending.

**Detection:** A subtask is stalled when:
- `status == "Running"` AND
- `(current_step - last_update) >= STALL_THRESHOLD` (default 5)

**Healing action:** Reset status to Pending, shadow to Pending, update last_update.

**Tracking:** `healed_total` counter persists across saves/loads.

**Note:** Review-status subtasks are NOT considered stalled (they're intentionally paused).

### 4.6 MetaOptimizer

**File:** `solo_builder_cli.py:1091-1141`
**Class:** `MetaOptimizer`

**Purpose:** Records per-step metrics and adapts Planner heuristic weights over time.

**Metrics tracked (rolling window of 10 steps):**
- `heal_rate` — average heals per step
- `verify_rate` — average verifications per step

**Optimization rules:**
- If `heal_rate > 0.5` → increase `w_stall` by 0.1 (stalls happening too often)
- If `verify_rate < 0.2` → increase `w_staleness` by 0.1 (pipeline moving too slowly)

**Forecasting:**
```python
def forecast(dag) → str
# Linear extrapolation: remaining / verify_rate = ETA in steps
```

---

## 5. Execution Engine (4 Tiers)

The Executor routes each Running subtask through a waterfall of 4 execution tiers:

### 5.1 Tier 1: SdkToolRunner (Preferred)

**File:** `solo_builder_cli.py:512-699`
**Class:** `SdkToolRunner`
**Condition:** Subtask has `tools` AND `ANTHROPIC_API_KEY` is set
**Method:** Async Anthropic SDK with tool-use protocol
**Concurrency:** `asyncio.gather()` — all tool jobs run concurrently

**Supported tools:**
| Tool | Schema | Implementation |
|------|--------|----------------|
| `Read` | `{file_path: str}` | Opens file, returns first 12,000 chars |
| `Glob` | `{pattern: str, path?: str}` | Python `glob.glob()`, returns up to 100 matches |
| `Grep` | `{pattern: str, path?: str, glob?: str}` | Regex search across up to 20 files, 200 lines |

**Tool-use loop:** Up to 8 rounds of tool calls per subtask. Rate-limit retry with exponential backoff (5s → 60s max, up to 3 retries).

**Performance:** ~5s per subtask (vs ~30s for subprocess).

### 5.2 Tier 2: ClaudeRunner (Subprocess Fallback)

**File:** `solo_builder_cli.py:395-450`
**Class:** `ClaudeRunner`
**Condition:** Subtask has `tools` AND `claude` CLI is installed AND SDK unavailable
**Method:** `subprocess.run(["claude", "-p", ..., "--allowedTools", ...])`
**Concurrency:** `ThreadPoolExecutor` — parallel subprocesses

**Behavior:** Invokes `claude -p` with `--output-format json` and parses the result. Timeout configurable (default 60s).

### 5.3 Tier 3: AnthropicRunner (SDK Direct)

**File:** `solo_builder_cli.py:453-506`
**Class:** `AnthropicRunner`
**Condition:** Subtask has NO tools AND `ANTHROPIC_API_KEY` is set
**Method:** Direct `anthropic.messages.create()` — no subprocess, no tools
**Concurrency:** `asyncio.gather()` — all SDK jobs run concurrently

**Context injection:** Every prompt is prefixed with `_PROJECT_CONTEXT` (a one-liner describing Solo Builder so the model has project awareness).

### 5.4 Tier 4: Dice Roll (Offline Fallback)

**Condition:** No API key, no Claude CLI
**Method:** `random.random() < EXECUTOR_VERIFY_PROBABILITY` (default 0.6)
**Output:** No Claude output — just probabilistic status advancement

This ensures the pipeline can always make progress even without external services, which is essential for CI testing and offline demos.

### 5.5 Fallback Chain

```
SdkToolRunner fails? → falls back to ClaudeRunner
ClaudeRunner fails?  → stays Running (retry next step)
AnthropicRunner fails? → dice roll
All fail?            → stays Running → SelfHealer resets after threshold
```

---

## 6. CLI Interface

### 6.1 Entry Point

```bash
python solo_builder_cli.py [options]
```

### 6.2 CLI Arguments

| Flag | Description |
|------|-------------|
| `--headless` | Run without interactive prompt (for scripting/CI) |
| `--auto N` | Auto-run N steps at startup |
| `--no-resume` | Start fresh — ignore saved state |
| `--export` | Write `solo_builder_outputs.md` after auto-run completes |
| `--quiet` | Suppress terminal display output |
| `--output-format json` | Print final status as JSON to stdout |
| `--webhook URL` | POST completion event to URL when all subtasks Verified |

### 6.3 All 34 CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Execute one step of the 7-phase agent pipeline |
| `auto [N]` | Run N steps automatically (omit N for full run); Ctrl+C to pause |
| `status` | Show DAG statistics summary (counts, rates, forecast) |
| `verify <ST> [note]` | Manually set subtask to Verified (human gate) |
| `describe <ST> <prompt>` | Assign custom Claude prompt to subtask; resets to Pending |
| `tools <ST> <tool,list>` | Set allowed tools for subtask (e.g., `Read,Glob,Grep` or `none`) |
| `output <ST>` | Display Claude output for a specific subtask |
| `add_task [spec \| depends: N]` | Append new task; inline spec skips prompt; `\| depends: N` for explicit deps |
| `add_branch <Task N> [spec]` | Add branch to existing task; inline spec skips prompt |
| `prioritize_branch <task> <branch>` | Boost branch's Pending subtasks to front of queue |
| `set KEY=VALUE` | Change runtime setting (persists to settings.json) |
| `set KEY` | Show current value of a setting |
| `depends [<task> <dep>]` | Add dependency or show dependency graph |
| `undepends <task> <dep>` | Remove a dependency |
| `rename <ST> <text>` | Update subtask description without resetting status |
| `filter <status>` | Show only subtasks matching a status |
| `search <query>` | Search subtasks by keyword in name, description, or output |
| `branches [Task N]` | List all branches (or per-task detail with subtask breakdown) |
| `timeline <ST>` | Show status history for a subtask |
| `log [ST]` | Show journal entries, optionally filtered by subtask |
| `history [N]` | Show recent step-by-step activity log |
| `diff` | Compare current state to last backup |
| `stats` | Per-task breakdown with verified counts and avg steps |
| `graph` | ASCII dependency graph with status icons and progress counters |
| `config` | Formatted table of all runtime settings |
| `priority` | Show planner's cached priority queue with risk scores |
| `stalled` | Show subtasks stuck longer than STALL_THRESHOLD |
| `heal <ST>` | Manually reset a Running subtask to Pending |
| `agents` | Show all agent stats (planner weights, executor config, healer totals, meta rates) |
| `forecast` | Detailed completion forecast with verify/heal rates and ETA |
| `tasks` | Per-task summary table with status, branch count, verified/total |
| `export` | Dump all subtask outputs to `solo_builder_outputs.md` |
| `snapshot` | Save a 4-page PDF report |
| `save` / `load` | Manual state persistence |
| `load_backup [1\|2\|3]` | Restore from numbered backup file |
| `undo` | Restore from most recent backup (.1) |
| `pause` / `resume` | Write/remove pause trigger (also usable from Discord/dashboard) |
| `reset` | Clear state and restart with the default diamond DAG |
| `help` | Show command reference |
| `exit` | Save state and quit |

### 6.4 Lockfile Protection

A process lockfile at `state/solo_builder.lock` prevents two CLI instances from corrupting the shared state file. Created on startup, removed on clean exit.

---

## 7. REST API (Flask)

**File:** `api/app.py` (724 lines)
**Server:** `python api/app.py` → `http://127.0.0.1:5000`
**CORS:** Enabled (`Access-Control-Allow-Origin: *`)

### 7.1 All Endpoints

#### GET Endpoints (Read-only)

| Route | Returns |
|-------|---------|
| `GET /` | Serves `dashboard.html` (SPA) |
| `GET /status` | `{step, total, verified, running, pending, pct, complete}` |
| `GET /tasks` | List of task summaries with branch/subtask counts |
| `GET /tasks/<id>` | Full task data including all branches and subtasks |
| `GET /heartbeat` | Lightweight counters from `step.txt` (no JSON parse) |
| `GET /journal` | Parsed journal entries (last 30) |
| `GET /export` | Download `solo_builder_outputs.md` |
| `GET /config` | Runtime settings from `settings.json` |
| `GET /graph` | ASCII dependency graph as JSON `{nodes, text}` |
| `GET /stats` | Per-task breakdown: verified, total, pct, avg_steps |
| `GET /search?q=<query>` | Search subtasks by keyword |
| `GET /history?limit=N` | Aggregated activity log across all subtasks |
| `GET /diff` | Compare current state to `.1` backup |
| `GET /branches/<task>` | Per-task branch listing with subtask detail |
| `GET /timeline/<subtask>` | Individual subtask timeline, description, output, history, tools |
| `GET /priority` | Priority queue with risk scores (top 30) |
| `GET /stalled` | Subtasks stuck longer than STALL_THRESHOLD |
| `GET /agents` | Agent statistics (planner, executor, healer, meta, forecast) |
| `GET /forecast` | Detailed completion forecast with rates and ETA |

#### POST Endpoints (Actions via trigger files)

| Route | Action | Trigger File |
|-------|--------|-------------|
| `POST /run` | Execute one CLI step | `state/run_trigger` |
| `POST /stop` | Stop auto-run | `state/stop_trigger` |
| `POST /verify` | Verify a subtask | `state/verify_trigger.json` |
| `POST /describe` | Set subtask prompt | `state/describe_trigger.json` |
| `POST /tools` | Set subtask tools | `state/tools_trigger.json` |
| `POST /set` | Change a setting | `state/set_trigger.json` |
| `POST /config` | Merge settings into settings.json | (direct write) |
| `POST /rename` | Rename subtask description | `state/rename_trigger.json` |
| `POST /heal` | Reset stalled subtask | `state/heal_trigger.json` |
| `POST /export` | Regenerate and download outputs.md | (direct write) |
| `POST /tasks/<id>/trigger` | Trigger a specific task | (returns pending info) |

---

## 8. Web Dashboard

**File:** `api/dashboard.html`
**Type:** Single-page application (SPA), dark theme
**Polling:** Every 2 seconds via `GET /status` and other endpoints

### 8.1 Dashboard Features

| Panel / Tab | Description |
|-------------|-------------|
| **Header bar** | Step counter, progress percentage, Run Step / Auto / Stop / Export buttons |
| **Task progress** | Per-task cards with branch bars, subtask counts |
| **Subtask modal** | Click subtask → description, output, history, tools, Verify / Rename buttons |
| **Journal tab** | Live journal entries |
| **Diff tab** | State changes since last backup |
| **Stats tab** | Per-task statistics |
| **History tab** | Color-coded status transitions |
| **Branches tab** | Per-task branch tree with subtask detail |
| **Settings tab** | Editable inputs for all config keys (POSTs to `/config`) |
| **Priority tab** | Priority queue with risk bars and candidate counts |
| **Stalled tab** | Stuck subtasks with age bars, threshold display, heal buttons |
| **Agents tab** | Forecast gauge SVG, agent stat cards |

---

## 9. Discord Bot

**File:** `discord_bot/bot.py` (1,944 lines)
**Framework:** `discord.py >= 2.0`
**Auth:** `DISCORD_BOT_TOKEN` in `.env`
**Channel restriction:** Optional `DISCORD_CHANNEL_ID`

### 9.1 All Discord Commands

All commands work as both `/slash` commands and plain-text (no `/` prefix needed):

| Command | Description |
|---------|-------------|
| `status` | DAG progress summary with per-task bar charts |
| `run` | Trigger one step |
| `auto [n]` | Run N steps with per-step ticker feedback |
| `stop` | Cancel bot auto-run + write stop_trigger for CLI |
| `verify <ST> [note]` | Approve a Review-gated subtask |
| `output <ST>` | Show Claude output for subtask |
| `describe <ST> <prompt>` | Assign custom prompt |
| `tools <ST> <tools>` | Set allowed tools |
| `set KEY=VALUE` | Change runtime setting |
| `add_task <spec>` | Queue new task |
| `add_branch <task> <spec>` | Queue new branch |
| `prioritize_branch <task> <branch>` | Boost branch priority |
| `depends [<task> <dep>]` | Add dependency or show graph |
| `undepends <task> <dep>` | Remove dependency |
| `rename <ST> <desc>` | Rename subtask description |
| `filter <status>` | Show subtasks by status |
| `branches [task]` | Branch overview or per-task detail |
| `timeline <ST>` | Subtask status history |
| `log [ST]` | Journal entries |
| `search <query>` | Search subtasks |
| `history` | Recent activity log |
| `diff` | State diff |
| `stats` | Per-task statistics |
| `graph` | Dependency graph |
| `config` | Runtime settings table |
| `priority` | Priority queue with risk scores |
| `stalled` | Stuck subtasks |
| `heal <ST>` | Reset stalled subtask |
| `agents` | Agent statistics |
| `forecast` | Completion forecast with ETA |
| `pause` / `resume` | Pause/resume auto-run with heartbeat feedback |
| `reset confirm` | Reset DAG (requires confirmation) |
| `snapshot` | Trigger PDF; attaches latest PDF |
| `export` | Download outputs.md as file attachment |
| `help` | Command list |

### 9.2 Bot Features

- **Per-step ticker:** During `auto` runs, posts `Step N — X✓ Y▶ Z⏸ W⏳ / 70` after each step
- **Completion notification:** Sends celebration message when all subtasks reach Verified
- **Chat log:** All messages logged to `discord_bot/chat.log`
- **Stop guard:** Prevents concurrent auto runs
- **Heartbeat:** Reads `state/step.txt` for real-time counter display

---

## 10. Inter-Process Communication (IPC)

The CLI, API, and Discord bot communicate via **trigger files** in the `state/` directory. This is a lightweight, file-based IPC mechanism.

### 10.1 Trigger File Registry

| Trigger File | Writer(s) | Consumer | Format |
|-------------|-----------|----------|--------|
| `run_trigger` | API, Bot | CLI auto-loop | Plain text ("1") |
| `stop_trigger` | API, Bot | CLI auto-loop | Plain text ("1") |
| `pause_trigger` | Bot, CLI | CLI auto-loop | Presence-based (exists = paused) |
| `verify_trigger.json` | API, Bot | CLI auto-loop | `{subtask, note}` |
| `describe_trigger.json` | API, Bot | CLI auto-loop | `{subtask, desc}` |
| `tools_trigger.json` | API, Bot | CLI auto-loop | `{subtask, tools}` |
| `set_trigger.json` | API, Bot | CLI auto-loop | `{key, value}` |
| `rename_trigger.json` | API, Bot | CLI auto-loop | `{subtask, desc}` |
| `heal_trigger.json` | API, Bot | CLI auto-loop | `{subtask}` |
| `add_task_trigger.json` | Bot | CLI auto-loop | `{spec}` |
| `add_branch_trigger.json` | Bot | CLI auto-loop | `{task, spec}` |
| `prioritize_branch_trigger.json` | Bot | CLI auto-loop | `{task, branch}` |
| `depends_trigger.json` | Bot | CLI auto-loop | `{target, dep}` |
| `undepends_trigger.json` | Bot | CLI auto-loop | `{target, dep}` |
| `reset_trigger` | Bot | CLI auto-loop | Presence-based |
| `snapshot_trigger` | Bot | CLI auto-loop | Presence-based |
| `undo_trigger` | Bot | CLI auto-loop | Presence-based |

### 10.2 Consumption Pattern

The CLI auto-loop polls all trigger files every 50ms during the `AUTO_STEP_DELAY` pause between steps. When found:
1. Read and parse the file
2. Delete the file atomically
3. Execute the corresponding command
4. Continue the auto-loop

---

## 11. Persistence & State Management

### 11.1 State File

**Path:** `state/solo_builder_state.json`

**Schema:**
```json
{
  "step": 25,
  "snapshot_counter": 1,
  "healed_total": 3,
  "dag": { ... },
  "memory_store": {
    "Branch A": [{"snapshot": "A1_started", "timestamp": 1}, ...],
    ...
  },
  "alerts": ["..."],
  "meta_history": [{"healed": 0, "verified": 2}, ...]
}
```

### 11.2 Auto-Save

State saves automatically every `AUTO_SAVE_INTERVAL` steps (default 5).

### 11.3 Backup Rotation

On every save, the previous state files are rotated:
```
current → .1 → .2 → .3 (deleted)
```

This gives 3 levels of undo via `load_backup [1|2|3]` or `undo`.

### 11.4 Heartbeat File

**Path:** `state/step.txt`
**Format:** `step,verified,total,pending,running,review`
**Updated:** Every step
**Purpose:** Lightweight status for bot/dashboard without parsing full JSON

### 11.5 Journal

**Path:** `journal.md`
**Format:** Markdown with entries per verified subtask
**Structure:**
```markdown
## A1 · Task 0 / Branch A · Step 3
**Prompt:** List 5 key features...
<Claude output here>
---
```

---

## 12. Configuration System

### 12.1 Config File

**Path:** `config/settings.json`

### 12.2 All Configuration Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `STALL_THRESHOLD` | int | 5 | Steps before SelfHealer resets a Running subtask |
| `SNAPSHOT_INTERVAL` | int | 20 | Steps between automatic PDF snapshots |
| `DAG_UPDATE_INTERVAL` | int | 5 | Steps between Planner re-prioritization |
| `PDF_OUTPUT_PATH` | str | `./snapshots/` | Directory for PDF reports |
| `STATE_PATH` | str | `./state/solo_builder_state.json` | State file location |
| `JOURNAL_PATH` | str | `journal.md` | Journal file location |
| `AUTO_SAVE_INTERVAL` | int | 5 | Steps between auto-saves |
| `AUTO_STEP_DELAY` | float | 0.4 | Seconds between auto steps |
| `MAX_SUBTASKS_PER_BRANCH` | int | 20 | Hard cap on subtasks per branch |
| `MAX_BRANCHES_PER_TASK` | int | 10 | Hard cap on branches per task |
| `VERBOSITY` | str | `INFO` | Log level: `INFO` or `DEBUG` |
| `BAR_WIDTH` | int | 20 | Progress bar character width |
| `MAX_ALERTS` | int | 10 | Maximum retained alert messages |
| `EXECUTOR_MAX_PER_STEP` | int | 6 | Max subtasks advanced per step |
| `EXECUTOR_VERIFY_PROBABILITY` | float | 0.6 | Dice-roll verification probability |
| `CLAUDE_TIMEOUT` | int | 60 | Subprocess timeout in seconds |
| `CLAUDE_ALLOWED_TOOLS` | str | `""` | Default tools for ClaudeRunner |
| `ANTHROPIC_MODEL` | str | `claude-sonnet-4-6` | Model for SDK calls |
| `ANTHROPIC_MAX_TOKENS` | int | 512 | Max tokens per SDK call |
| `REVIEW_MODE` | bool | false | Enable human-in-the-loop gating |
| `WEBHOOK_URL` | str | `""` | POST completion events to this URL |

### 12.3 Runtime Modification

Settings can be changed at runtime via:
- CLI: `set KEY=VALUE`
- API: `POST /config` or `POST /set`
- Discord: `set KEY=VALUE` or `/set key value`
- Dashboard: Settings panel with editable inputs

Changes persist to `config/settings.json` immediately.

---

## 13. PDF Snapshot System

**File:** `solo_builder_live_multi_snapshot.py` (389 lines)
**Dependencies:** `matplotlib >= 3.10`, `numpy >= 2.2` (optional)

### 13.1 PDF Contents (4 Pages)

1. **Page 1: Timeline** — Step-by-step progression visualization
2. **Page 2: Task/Branch Progress** — Bar charts per task and branch
3. **Page 3: Subtask Detail** — Individual subtask status grid
4. **Page 4: Agent Stats** — Planner weights, executor config, healer totals, meta rates

### 13.2 Trigger Methods

- CLI: `snapshot` command
- Auto: Every `SNAPSHOT_INTERVAL` steps
- Discord: `snapshot` command (attaches PDF)
- API/Dashboard: via trigger file

---

## 14. Profiler Harness

**File:** `profiler_harness.py` (333 lines)

**Purpose:** Performance benchmarking that patches all SDK/subprocess paths at module level — no production code changes required.

**Outputs:**
- Per-agent timing breakdown
- Concurrency statistics
- Planner cache hit rate

**Optimal configuration found:** `EXECUTOR_MAX_PER_STEP=6` → 157s wall time / 70 subtasks with live API; 29s in dice-roll mode.

**Modes:**
- Full run: `python profiler_harness.py`
- Dry run (CI): `python profiler_harness.py --dry-run` (3 steps)

---

## 15. Testing Infrastructure

### 15.1 Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `discord_bot/test_bot.py` | 194 | All bot commands, helpers, state management |
| `api/test_app.py` | 71 | All API endpoints, error handling |
| **Total** | **265** | |

### 15.2 Bot Test Coverage (194 tests)

| Test Group | Count | Covers |
|------------|-------|--------|
| `_has_work` | 8 | Work detection logic |
| `_format_status` | 15 | Status formatting |
| `_auto_running` | 4 | Auto-run state tracking |
| `_read_heartbeat` | 3 | step.txt parsing |
| `_format_step_line` | 6 | Step line formatting |
| `_load_state` | 8 | State file loading |
| `_handle_text_command` | 12 | Plain-text command parsing |
| `_run_auto` | 6 | Auto-run lifecycle |
| `_fire_completion` | 3 | Completion notification |
| `_cmd_add_task` | 18 | Task addition (inline spec, deps, normalization) |
| `_cmd_add_branch` | 12 | Branch addition |
| `_cmd_verify` | 10 | Subtask verification |
| `_cmd_describe` | 6 | Prompt assignment |
| `_cmd_tools` | 6 | Tool assignment |
| `_cmd_set` | 6 | Setting changes |
| `_cmd_reset` | 4 | DAG reset |
| `_cmd_export` | 3 | Export generation |
| `_cmd_status` | 8 | Status display |
| `_cmd_depends` | 6 | Dependency management |
| `_cmd_undepends` | 4 | Dependency removal |
| `_cmd_output` | 4 | Output display |
| `save_state` / `load_state` | 4 | Persistence |
| `_take_snapshot` | 2 | PDF snapshots |
| `_cmd_prioritize_branch` | 4 | Branch prioritization |
| `_cmd_filter` | 3 | Status filtering |
| `_cmd_timeline` | 2 | Timeline display |
| `_cmd_branches` | 3 | Branch listing |
| `_cmd_log` | 2 | Journal display |
| `_cmd_rename` | 2 | Subtask renaming |
| `_cmd_stalled` | 2 | Stalled detection |
| `_cmd_priority` | 2 | Priority queue display |
| `_cmd_heal` | 3 | Manual healing |
| `_cmd_agents` | 2 | Agent stats display |
| `_cmd_forecast` | 2 | Forecast display |
| Misc | ~5 | Edge cases, inline spec, find_subtask_output |

### 15.3 API Test Coverage (71 tests)

Covers all GET and POST endpoints including error cases, empty states, and edge conditions.

### 15.4 Test Execution

```bash
# Bot tests (~0.03s, no Discord connection needed)
python discord_bot/test_bot.py
python -m pytest discord_bot/test_bot.py -v

# API tests
python api/test_app.py
python -m pytest api/test_app.py -v
```

---

## 16. CI/CD Pipeline

**File:** `.github/workflows/smoke-test.yml` (10,324 bytes)
**Trigger:** Push or PR to `master`
**Runner:** `ubuntu-latest`, Python 3.13

### 16.1 CI Test Matrix

| Step | What It Tests | Pass Criteria |
|------|--------------|---------------|
| 15-step headless run | `--auto 15 --no-resume` | >= 18 subtasks Verified |
| Export command | `--headless --export --no-resume --auto 2` | `solo_builder_outputs.md` exists, > 30 bytes |
| stop_trigger cleanup | Plants stale trigger before startup | Pipeline advances, trigger consumed |
| Bot unit tests | 194 tests | All pass |
| API unit tests | 71 tests | All pass |
| Profiler dry-run | `--dry-run` (3 steps) | No errors |
| REVIEW_MODE gate | `REVIEW_MODE=True`, 2 steps | >= 1 subtask in Review state |
| Webhook POST | Local http.server, `_fire_completion()` | Correct JSON payload received |
| add_task inline spec | Inline spec | Skips `input()` call |
| add_task dep wiring | Explicit dependencies | Digit normalization works |
| add_branch inline spec | Inline spec for branch | Skips `input()` call |

---

## 17. Terminal Display System

**File:** `solo_builder_cli.py:1147-1288`
**Class:** `TerminalDisplay`

### 17.1 Display Layout

```
═══════════════════════════════════════════════════════════════════
  SOLO BUILDER — AI AGENT CLI  │  Step: 25  │  ETA: ~18 steps  (50% done)
═══════════════════════════════════════════════════════════════════

  ▶ Task 0  [Verified]
    ├─ Branch A [Verified]
    │  Progress [====================] 5/5
    │  Shadow   [!!!!!!!!!!!!!!!!!!!!] 5/5
    │  Memory   [####################] 15 snapshots
    │    ◦ A1   Verified       shadow=Done       age=3
    │      ↳ Solo Builder is an AI-powered CLI that manages DAG-based t…
    │    ◦ A2   Verified       shadow=Done       age=4
    │      ↳ ...
    │
    └─ Branch B [Verified]
    ...

  ────────── ALERTS ──────────
  ⚠ STALLED ⚠ C3 stalled 5 steps
  ⚠ PREDICTIVE FIX ⚠ C3 reset after 5 steps stalled

  ──────────────────────────────────────────────────────────────────
  Overall [================================--------] 35✓ 2⏸ 4▶ 29● / 70  (50.0%)

  Commands: run │ auto [N] │ ... │ exit
═══════════════════════════════════════════════════════════════════
```

### 17.2 ANSI Color Coding

| Element | Color |
|---------|-------|
| Pending | Yellow |
| Running | Cyan |
| Review | Magenta |
| Verified | Green |
| Failed | Red |
| Shadow Pending | Magenta |
| Shadow Done | Green |
| Progress bars | Green |
| Memory bars | Blue |
| Alerts | Red/Yellow (blinking) |

---

## 18. Utilities & Shared Library

**File:** `utils/helper_functions.py` (185 lines)

### 18.1 Exports

| Export | Type | Description |
|--------|------|-------------|
| `RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA, WHITE, BOLD, DIM, BLINK, RESET` | str constants | ANSI escape codes |
| `STATUS_COLORS` | dict | Status → ANSI color map |
| `SHADOW_COLORS` | dict | Shadow → ANSI color map |
| `ALERT_STALLED, ALERT_PREDICTIVE, ALERT_CONFLICT, ALERT_HEALED` | str constants | Alert icons with ANSI |
| `load_settings(path)` | function | Load JSON config with defaults fallback |
| `make_bar(filled, total, char, empty, width)` | function | Fixed-width progress bar string |
| `dag_stats(dag)` | function | `{total, pending, running, review, verified}` |
| `branch_stats(branch)` | function | `(verified, running, total)` |
| `shadow_stats(branch)` | function | `(shadow_done, total)` |
| `memory_depth(store, branch)` | function | Count of memory snapshots |
| `add_memory_snapshot(store, branch, label, step)` | function | Append memory entry |
| `format_status(status)` | function | Color-formatted status string |
| `format_shadow(shadow)` | function | Color-formatted shadow string |
| `validate_dag(dag)` | function | Structural validation, returns warnings list |
| `clamp(value, lo, hi)` | function | Integer clamping |

---

## 19. File Inventory

```
solo-builder/
├── solo_builder_cli.py              3,533 lines  Main CLI (6 agents, 4 runners, 34 commands)
├── api/
│   ├── app.py                         724 lines  Flask REST API (30+ endpoints)
│   ├── dashboard.html                           SPA (dark theme, 9 sidebar tabs)
│   └── test_app.py                    817 lines  71 API tests
├── discord_bot/
│   ├── bot.py                       1,944 lines  Discord bot (45+ commands)
│   ├── test_bot.py                  2,382 lines  194 bot tests
│   └── __init__.py
├── utils/
│   ├── helper_functions.py            185 lines  Shared utilities
│   └── __init__.py
├── config/
│   └── settings.json                             Runtime configuration (21 keys)
├── profiler_harness.py                333 lines  Performance benchmarking
├── solo_builder_live_multi_snapshot.py 389 lines  4-page PDF report generator
├── make_demo_cast.py               16,146 lines  Demo animation generator
├── gen_demo_cast.py                 5,076 lines  Demo utilities
├── pyproject.toml                                Package metadata
├── requirements.txt                              Dependencies
├── README.md                        19,774 bytes Full documentation
├── CHANGELOG.md                     44,256 bytes 49 versions documented
├── CONTRIBUTING.md                   4,112 bytes Developer guidelines
├── __init__.py                                   Package init (version 2.0.0)
├── .env.example                                  Environment template
├── .gitignore                                    Git exclusions
├── .github/workflows/smoke-test.yml 10,324 bytes CI pipeline (11 test steps)
├── demo.cast                                     Asciinema recording
├── demo.gif                                      Demo animation
└── review_mode_demo.gif                          REVIEW_MODE demo
```

---

## 20. Dependency Map

### 20.1 Core Dependencies

| Package | Version | Required By |
|---------|---------|-------------|
| `anthropic` | >= 0.40 | SdkToolRunner, AnthropicRunner |
| `flask` | >= 3.1 | REST API |
| `python-dotenv` | >= 1.0 | Environment loading |

### 20.2 Optional Dependencies

| Package | Version | Required By |
|---------|---------|-------------|
| `matplotlib` | >= 3.10 | PDF snapshots |
| `numpy` | >= 2.2 | PDF snapshots |
| `discord.py` | >= 2.0 | Discord bot |

### 20.3 Standard Library Usage

The core CLI uses only stdlib modules: `argparse`, `asyncio`, `os`, `sys`, `copy`, `json`, `random`, `subprocess`, `time`, `concurrent.futures`, `typing`, `shutil`, `glob`, `re`.

---

## 21. Version History Summary

Solo Builder has shipped **49 versions** from v2.0.0 to v2.1.49, with the following trajectory:

| Version Range | Key Milestones |
|--------------|----------------|
| v2.0.0 | Initial release: 6 agents, diamond DAG, CLI, dice-roll executor |
| v2.0.1–v2.0.5 | ClaudeRunner subprocess, AnthropicRunner SDK, REVIEW_MODE |
| v2.0.6–v2.0.10 | SdkToolRunner with tool-use protocol, async execution |
| v2.1.0–v2.1.10 | Discord bot, Flask API, web dashboard |
| v2.1.11–v2.1.20 | Persistence, auto-save, lockfile, heartbeat, webhook |
| v2.1.21–v2.1.30 | PDF snapshots, profiler, export, journal, diff, stats |
| v2.1.31–v2.1.40 | History, search, timeline, branches, rename, filter, graph |
| v2.1.41–v2.1.49 | Settings editor, priority queue, stalled panel, heal, agents, forecast |

**Test growth:** 0 → 265 tests across 49 releases (avg ~5.4 new tests per version).

---

*Generated from source analysis of Solo Builder v2.1.49 (2026-03-05). All line counts, class names, method signatures, and configuration values verified against the codebase.*
