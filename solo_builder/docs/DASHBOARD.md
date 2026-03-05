# Solo Builder Dashboard — User Guide

The dashboard is a dark-theme single-page app served by the Flask API at `http://127.0.0.1:5000`.
It polls the CLI's state file every 2 seconds and provides full control over the pipeline without
touching the terminal.

## Starting the Dashboard

```bash
# Terminal 1 — CLI (optional, dashboard works read-only without it)
cd "C:\Users\Matt1\OneDrive\Desktop\Solo Builder\solo_builder"
python solo_builder_cli.py

# Terminal 2 — API server
python api/app.py
```

Open `http://127.0.0.1:5000` in a browser.

---

## Layout Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Header bar: step counter · progress bar · verified/running/    │
│              pending counts · Run/Auto/Stop buttons · theme      │
├──────────────────────────────────────────┬──────────────────────┤
│  Main area (task grid or graph view)     │  Sidebar (10 tabs)   │
│                                          │                       │
│  [Task 0] [Task 1] [Task 2] ...          │  Journal / Diff /    │
│                                          │  Stats / History /   │
│                                          │  Branches / Settings │
│                                          │  Priority / Stalled  │
│                                          │  Agents / Forecast   │
└──────────────────────────────────────────┴──────────────────────┘
```

---

## Header Controls

| Control | Description |
|---------|-------------|
| **Run Step** | Execute one pipeline step immediately |
| **Auto** + step input | Run N steps automatically (0 = run until complete) |
| **Stop** | Halt an in-progress auto-run |
| **Export** | Download all Claude outputs as `solo_builder_outputs.md` |
| **Theme toggle** | Switch between dark and light themes (persists via localStorage) |
| Search box | Filter the task grid by keyword (searches task names and subtask descriptions) |
| Graph toggle | Switch between task grid view and SVG dependency graph view |

---

## Task Grid

Each card shows:
- Task name and overall status badge (Pending / Running / Verified)
- Mini progress bar (green = verified fraction)
- Verified / total subtask count

**Click a task card** to open the subtask detail modal.

---

## Subtask Modal

Shows all subtasks across all branches for a task. Each subtask row has:

- Status badge (color-coded)
- Description text
- Claude output (if any)
- Action buttons:
  - **Verify** — manually mark as Verified (bypasses Claude)
  - **Describe** — set a new Claude prompt for this subtask
  - **Tools** — assign allowed tools (e.g. `Read,Glob,Grep`)
  - **Set** — update a runtime setting inline

---

## Graph View (`g` key or Graph button)

SVG dependency graph showing all 7 tasks as nodes with:
- Progress bars inside each node (green fill = verified %)
- Directed edges showing `depends_on` relationships
- Color-coded border by status

---

## Sidebar Tabs

### Journal
Chronological log of all Claude outputs written to `journal.md`. Each entry shows the subtask
name, task, branch, step number, and Claude's response.

### Diff
Changes to the DAG since the last manual save. Shows which subtasks changed status and any
new outputs added.

### Stats
Per-task breakdown table: task name, branch count, subtask counts by status
(Verified / Running / Review / Pending), and completion percentage.

### History
Last N status transitions across all subtasks — useful for seeing what the pipeline did
in recent steps.

### Branches
All branches across all tasks with subtask count, verified count, and status symbol
(✓ done / ▶ running / ⏸ review / · pending).

### Settings
Live view of `config/settings.json`. Every field is editable inline — click a value,
change it, and press **Save** to apply immediately via `POST /config`.

Key settings:
| Key | Default | Description |
|-----|---------|-------------|
| `EXECUTOR_MAX_PER_STEP` | 6 | Max subtasks advanced per step |
| `STALL_THRESHOLD` | 5 | Steps before SelfHealer resets a stalled subtask |
| `REVIEW_MODE` | false | Require manual verify before marking Verified |
| `VERIFY_PROB` | 0.6 | Dice-roll probability when no API/CLI available |
| `AUTO_STEP_DELAY` | 0.4 | Seconds between steps in auto-run |
| `WEBHOOK_URL` | "" | POST completion JSON to this URL on pipeline finish |

### Priority
Current Planner priority queue — subtasks ranked by risk score. Higher score = executed first.
Includes a visual risk bar per subtask. Running subtasks always outrank Pending ones.

### Stalled
Subtasks that have been in Running state for longer than `STALL_THRESHOLD` steps without
advancing. Each row shows the subtask name, age (steps stalled), and a **Heal** button that
resets it to Pending so the executor retries it.

### Agents
Live statistics for all 6 agents:
- **Planner** — priority cache hits, last refresh step
- **Executor** — subtasks started, verified, by tier (SDK tool / subprocess / SDK direct / dice)
- **ShadowAgent** — conflicts detected and resolved
- **SelfHealer** — total heals performed
- **Verifier** — branch/task roll-ups triggered
- **MetaOptimizer** — verify rate, heal rate, weight adjustments

Includes a forecast gauge SVG showing estimated completion percentage.

### Forecast
Dedicated completion forecast panel showing:
| Field | Description |
|-------|-------------|
| Completion | Current verified % |
| Rate | Verified subtasks per step (rolling average) |
| ETA | Estimated steps remaining to 100% |
| Verified | Absolute count (e.g. 42 / 70) |
| Stalled | Number of currently stalled subtasks |

### Metrics
Historical analytics panel for the full run. Shows:
- **SVG sparkline** — verified-per-step over time (x = step index, y = verifies that step)
- Summary table:

| Field | Description |
|-------|-------------|
| Total steps | Number of steps recorded in history |
| Total verifies | Cumulative verified subtasks |
| Avg rate | Average verified subtasks per step |
| Peak rate | Highest single-step verified count |
| Steps w/ heals | How many steps had SelfHealer resets |
| Total healed | Lifetime heal count by SelfHealer |

Populated from `GET /metrics`. The sparkline will show "Not enough data yet" until at least 2 steps have been recorded.

---

## Subtask Output Viewer

Each subtask row in the detail panel shows a `▶` button when Claude output is available.
Clicking it:
- Expands an inline scrollable panel (max 200px) showing the full output
- Changes the button to `▼`
- Clicking again collapses it

This avoids opening the modal when you just want to quickly read an output. The toggle button
uses `event.stopPropagation()` so clicking it does **not** open the modal.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `r` | Run one step |
| `g` | Toggle graph / grid view |
| `j` | Select next task card |
| `k` | Select previous task card |
| `v` | Verify first non-verified subtask of selected task |
| `Enter` | Open subtask modal for selected task |
| `Esc` | Close modal |

Shortcuts are disabled when focus is inside an input, textarea, or select element.

---

## Completion Sound

When the pipeline reaches 100% verified (status badge transitions to "Complete"), the dashboard
plays three ascending tones (C5 → E5 → G5) via the Web Audio API. The sound fires once per
page load when the completion threshold is first crossed.

---

## Responsive Layout

On screens narrower than 768px the layout switches to single-column: the sidebar moves below
the task grid, and the header wraps to multiple lines. All functionality remains accessible.

---

## REST API (used by the dashboard)

The dashboard communicates exclusively via the Flask REST API at `http://127.0.0.1:5000`.
See [`docs/API.md`](API.md) for the full endpoint reference.

Quick reference of endpoints polled by the dashboard:

| Poller | Endpoint | Interval |
|--------|----------|----------|
| Status bar | `GET /status` | 2s |
| Task grid | `GET /tasks` | 2s |
| Heartbeat counters | `GET /heartbeat` | 2s (during auto-run) |
| Journal tab | `GET /journal` | 2s |
| Diff tab | `GET /diff` | 2s |
| Stats tab | `GET /stats` | 2s |
| History tab | `GET /history` | 2s |
| Branches tab | `GET /branches/<id>` | 2s |
| Settings tab | `GET /config` | 2s |
| Priority tab | `GET /priority` | 2s |
| Stalled tab | `GET /stalled` | 2s |
| Agents tab | `GET /agents` | 2s |
| Forecast tab | `GET /forecast` | 2s |
| Metrics tab | `GET /metrics` | 2s |
