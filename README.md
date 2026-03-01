# Solo Builder

> **Build faster. Ship smarter. Solo.**

Solo Builder is a Python terminal CLI that orchestrates AI agents — Planner, Executor, Verifier, SelfHealer, ShadowAgent, and MetaOptimizer — to manage a DAG-based project task graph, enabling a solo developer to run multi-branch, dependency-aware workflows from a single interactive shell. The system tracks subtask lifecycle (Pending → Running → Verified), detects stalls and DAG inconsistencies automatically, and snapshots state as versioned PDFs with a persistent `journal.md`, giving developers an auditable record of project progress. Built entirely in Python with no external orchestration framework, Solo Builder is a lightweight, self-contained alternative to heavyweight project management tools — designed for one developer operating with the leverage of a coordinated agent team.

---

## How It Works

Tasks are organized as a **DAG (Directed Acyclic Graph)** of branches and subtasks. Each step runs a six-agent pipeline:

| Agent | Role |
|---|---|
| **Planner** | Priority-ranks subtasks by risk score (staleness, stall age, shadow conflicts) |
| **Executor** | Advances subtasks: Pending → Running → Verified. Calls `claude -p` for subtasks with descriptions. |
| **ShadowAgent** | Tracks expected state, detects and resolves status conflicts |
| **Verifier** | Enforces DAG consistency — rolls up branch and task status when all subtasks verify |
| **SelfHealer** | Detects subtasks stalled in Running for ≥ `STALL_THRESHOLD` steps and resets them |
| **MetaOptimizer** | Adapts Planner weights based on heal rate and verify rate over time |

Subtasks with a `description` field are executed by calling the Claude Code CLI headlessly (`claude -p "<description>" --output-format json`). Subtasks without descriptions use a simulated probability roll as a fallback. Parallel subtasks across multiple tasks run concurrently via `ThreadPoolExecutor`.

### Dependency Model

Tasks declare `depends_on` lists. The Planner skips any task whose dependencies are not yet Verified. This enables:

- **Sequential chains**: `Task 0 → Task 1 → Task 2`
- **Fan-out**: `Task 0 → {Task 1, Task 2, Task 3}` (all run in parallel once Task 0 completes)
- **Fan-in (diamond)**: `{Task 1…5} → Task 6` (Task 6 waits for all five to finish)

---

## Getting Started

### Requirements

- Python 3.10+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated (`claude --version`)
- `matplotlib` for PDF snapshots (optional): `pip install matplotlib`

### Run

```bash
cd solo_builder
python solo_builder_cli.py
```

On first run, the default DAG loads automatically. On subsequent runs, you are prompted to resume saved state.

---

## Commands

| Command | Description |
|---|---|
| `run` | Execute one agent pipeline step |
| `auto [N]` | Run N steps automatically (default: until all tasks Verified) |
| `add_task` | Append a new Task — Claude decomposes your spec into subtasks |
| `add_branch <Task N>` | Add a new branch to an existing task via Claude decomposition |
| `depends` | Print the full dependency graph |
| `depends <T> <dep>` | Add a dependency: Task T depends on dep |
| `undepends <T> <dep>` | Remove a dependency |
| `describe <ST> <text>` | Attach a Claude prompt to any subtask and re-queue it |
| `output <ST>` | Print the full Claude output for a subtask |
| `export` | Write all Claude outputs to `solo_builder_outputs.md` |
| `snapshot` | Generate a PDF timeline snapshot |
| `save` / `load` | Persist and restore DAG state |
| `reset` | Reset to initial DAG, clear saved state |
| `status` | Show detailed DAG statistics |
| `set KEY=VALUE` | Tune runtime config (see below) |
| `help` | Show command reference |
| `exit` | Quit and auto-save |

### Config Keys (`set KEY=VALUE`)

| Key | Default | Description |
|---|---|---|
| `STALL_THRESHOLD` | 5 | Steps before SelfHealer resets a stalled subtask |
| `VERIFY_PROB` | 0.6 | Completion probability for simulated (no-description) subtasks |
| `AUTO_STEP_DELAY` | 0.4 | Seconds between steps in `auto` mode |
| `AUTO_SAVE_INTERVAL` | 5 | Steps between auto-saves |
| `SNAPSHOT_INTERVAL` | 20 | Steps between automatic PDF snapshots |

---

## Persistent Outputs

| File | Contents |
|---|---|
| `state/solo_builder_state.json` | Full DAG state, step counter, memory store |
| `journal.md` | Append-only log of every Claude-verified subtask (prompt + output) |
| `solo_builder_outputs.md` | On-demand export of all Claude outputs (`export` command) |
| `snapshots/` | PDF timeline snapshots (requires matplotlib) |

---

## Project Structure

```
solo_builder/
├── solo_builder_cli.py          # Main entry point — all six agents
├── solo_builder_live_multi_snapshot.py  # PDF generation (matplotlib)
├── utils/
│   └── helper_functions.py     # ANSI codes, bars, DAG stats, validators
├── config/
│   └── settings.json           # Runtime configuration
├── state/                      # Auto-created — persisted DAG state
├── snapshots/                  # Auto-created — PDF snapshots
├── journal.md                  # Auto-created — live Claude output log
└── README.md                   # This file
```
