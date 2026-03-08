#!/usr/bin/env python3
"""
auto_batch.py — Continuous self-looping batch executor for Solo Builder.

Reads TASK_QUEUE.md, executes every unstarted task through the full
deterministic workflow, and (with --auto-generate) calls Claude to draft
the next batch of tasks when the queue empties, then loops.

Per-batch workflow:
  claude_orchestrate.ps1 (reconcile)
  → start_task.ps1 (branch + triage)
  → advance_state build/DEV
  → claude -p (implement + test + commit)
  → safety-net test run
  → advance_state verify/AUDITOR → audit_check.ps1
  → advance_state done/AUDITOR → claude_orchestrate.ps1
  → commit audit artifacts
  → git merge master --no-ff + tag vX.Y.Z

Usage:
    python tools/auto_batch.py [options]

Options:
    --dry-run           Print what would happen without executing.
    --start-from NNN    Skip tasks before TASK-NNN.
    --limit N           Stop after N batches from the current queue (0 = unlimited).
    --auto-generate     When queue empties, call Claude to draft the next batch
                        and continue looping automatically.
    --max-total N       Hard ceiling on total batches executed this session
                        (guards against runaway loops; default 10 when
                        --auto-generate is set, 0 = unlimited otherwise).
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASK_QUEUE_PATH = REPO_ROOT / "claude" / "TASK_QUEUE.md"
STATE_PATH = REPO_ROOT / "claude" / "STATE.json"
TOOLS_DIR = REPO_ROOT / "tools"
SOLO_DIR = REPO_ROOT / "solo_builder"


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------

def _run(args, *, check=True, capture_output=False, cwd=None, env=None, quiet=False):
    """Run a subprocess; print the command (unless quiet); return CompletedProcess."""
    if not quiet:
        label = " ".join(str(a) for a in args)
        print(f"  $ {label}", flush=True)
    return subprocess.run(
        args,
        check=check,
        capture_output=capture_output,
        text=True,
        cwd=str(cwd or REPO_ROOT),
        env=env,
    )


def _pwsh(script_name, *args, check=True):
    """Run a PowerShell script from tools/."""
    return _run(
        ["powershell.exe", "-File", str(TOOLS_DIR / script_name)] + list(args),
        check=check,
    )


def _git(*args, capture=False, check=True, quiet=False):
    """Run a git command from REPO_ROOT."""
    return _run(["git"] + list(args), check=check, capture_output=capture, quiet=quiet)


# ---------------------------------------------------------------------------
# Working-tree helpers
# ---------------------------------------------------------------------------

def get_dirty_paths() -> list:
    result = _git("status", "--porcelain", capture=True, check=False, quiet=True)
    if result.returncode != 0:
        return []
    paths = []
    for line in result.stdout.splitlines():
        if not line.strip() or len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[1].strip()
        if path:
            paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# TASK_QUEUE.md helpers
# ---------------------------------------------------------------------------

def parse_task_queue() -> list:
    """
    Parse TASK_QUEUE.md and return a list of task dicts:
        {task_id, goal, criteria, body}
    Skips placeholder Goal lines (those that start and end with <>).
    """
    text = TASK_QUEUE_PATH.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^##\s+(TASK-\d{3})\s*$", text)
    tasks = []
    i = 1
    while i < len(blocks) - 1:
        task_id = blocks[i].strip()
        body = blocks[i + 1]
        i += 2

        goal_m = re.search(r"(?m)^Goal:\s*(.+)$", body)
        if not goal_m:
            continue
        goal = goal_m.group(1).strip()
        if goal.startswith("<") and goal.endswith(">"):
            continue

        criteria = ""
        ac_m = re.search(
            r"(?m)^Acceptance [Cc]riteria:\s*\n(.*?)(?=\n##|\Z)",
            body,
            re.DOTALL,
        )
        if ac_m:
            criteria = ac_m.group(1).strip()

        tasks.append(
            {"task_id": task_id, "goal": goal, "criteria": criteria, "body": body.strip()}
        )
    return tasks


def next_task_id() -> str:
    """Return next available TASK-NNN ID.

    Scans ALL TASK-NNN references in the file (headings AND goal text), takes
    the maximum, and returns max+1.  This handles multi-task batch entries where
    TASK-101/102 are mentioned in TASK-100's goal but have no own ## heading.
    """
    text = TASK_QUEUE_PATH.read_text(encoding="utf-8")
    nums = [int(m) for m in re.findall(r"TASK-(\d{3})", text)]
    return f"TASK-{(max(nums) + 1) if nums else 103:03d}"


def parse_task_blocks(raw: str) -> list:
    """
    Extract and return a list of (task_id, block_text) tuples from raw text.
    Only includes blocks that have a non-placeholder Goal line.
    """
    # Split on ## TASK-NNN headings, tolerating leading whitespace or numbering drift
    parts = re.split(r"(?m)^##\s+(TASK-\d{3})\s*$", raw)
    results = []
    i = 1
    while i < len(parts) - 1:
        task_id = parts[i].strip()
        body = parts[i + 1]
        i += 2
        goal_m = re.search(r"(?m)^Goal:\s*(.+)$", body)
        if not goal_m:
            continue
        goal = goal_m.group(1).strip()
        if not goal or (goal.startswith("<") and goal.endswith(">")):
            continue
        block = f"## {task_id}\n{body.rstrip()}"
        results.append((task_id, block))
    return results


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def is_task_merged(task_id: str) -> bool:
    """
    Return True if task/TASK-NNN has been merged into master.
    Primary: branch check.  Fallback: git log search (pre-branch-convention tasks).
    """
    branch = f"task/{task_id}"
    merged = _git("branch", "--merged", "master", capture=True, check=False, quiet=True)
    if merged.returncode == 0:
        if any(b.strip() == branch for b in merged.stdout.splitlines()):
            return True
    log = _git("log", "master", "--oneline", "--grep", task_id,
               capture=True, check=False, quiet=True)
    if log.returncode == 0 and log.stdout.strip():
        return True
    return False


def get_latest_tag() -> str:
    result = _git("describe", "--tags", "--abbrev=0", capture=True, check=False, quiet=True)
    if result.returncode == 0:
        tag = result.stdout.strip()
        if re.match(r"v\d+\.\d+\.\d+", tag):
            return tag
    return "v3.31.0"


def next_minor_tag(current: str) -> str:
    m = re.match(r"v(\d+)\.(\d+)\.(\d+)", current)
    if not m:
        return "v3.32.0"
    return f"v{m.group(1)}.{int(m.group(2)) + 1}.0"


# ---------------------------------------------------------------------------
# Implementation prompt
# ---------------------------------------------------------------------------

_IMPL_PROMPT = """\
You are a senior Python/JavaScript developer on the Solo Builder project.

TASK: {task_id}
GOAL: {goal}

ACCEPTANCE CRITERIA:
{criteria}

FILES TO EDIT (and ONLY these, unless you have a clear reason):
  solo_builder/api/app.py          — Flask REST API
  solo_builder/api/dashboard.html  — dashboard SPA (only if criteria require it)
  solo_builder/api/test_app.py     — unittest suite

WORKFLOW:
1. Read the current content of all three files first.
2. Implement the features following EXISTING PATTERNS exactly.
3. Add tests in test_app.py (follow _Base class, _make_state(), _write_state() helpers).
   Write at least 5 tests per new endpoint/feature.
4. Run tests:
     cd solo_builder && PYTHONIOENCODING=utf-8 python -m unittest api.test_app -v 2>&1 | tail -10
5. Fix any failures and rerun until all tests pass.
6. Commit ONLY the changed files:
     git add solo_builder/api/app.py solo_builder/api/dashboard.html solo_builder/api/test_app.py
     git commit -m "feat(api): {task_id_lower} — {goal_brief}"

RULES:
  - Follow existing code patterns exactly — no new abstractions.
  - Never add docstrings, comments, or type annotations to code you did not change.
  - Keep changes minimal and focused on the acceptance criteria only.
  - Do not refactor surrounding code.
  - PYTHONIOENCODING=utf-8 is required before running Python on Windows.
"""


def build_impl_prompt(task: dict) -> str:
    return _IMPL_PROMPT.format(
        task_id=task["task_id"],
        goal=task["goal"],
        criteria=task["criteria"] or "(see goal above)",
        task_id_lower=task["task_id"].lower(),
        goal_brief=task["goal"][:70].rstrip(),
    )


# ---------------------------------------------------------------------------
# Draft prompt (for --auto-generate)
# ---------------------------------------------------------------------------

_DRAFT_PROMPT = """\
You are continuing work on the Solo Builder project — a Python CLI agent loop
with a Flask REST API (solo_builder/api/app.py) and a dark-theme dashboard SPA
(solo_builder/api/dashboard.html).  All features are tested in test_app.py.

RECENT GIT LOG (last 20 commits on master):
{recent_log}

LAST 3 TASKS IN QUEUE (for format reference):
{last_tasks}

YOUR JOB:
Draft the next 3 dashboard/API features starting from task ID {next_id}.
Each task must:
  1. Be a single, self-contained REST endpoint OR dashboard UI feature.
  2. Be a logical follow-on to the recent work shown above.
  3. Be testable with at least 5 unittest cases using the _Base pattern.

Preferred feature areas (pick the most logical 3):
  - New REST endpoints that expose data not yet available via the API
  - Dashboard filter, sort, or export enhancements
  - Observability endpoints (diff, replay, audit, search)
  - UX polish: badges, counters, confirmation dialogs, tooltips

OUTPUT RULES — CRITICAL:
  - Output ONLY the 3 ## TASK-NNN blocks below.
  - No preamble, no explanation, no text outside the blocks.
  - Use exactly this format:

## {next_id}
Goal: [single-line goal]

Acceptance criteria:
- {next_id}: [specific, testable criterion]
- {next_id}: [specific, testable criterion]

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

[repeat for next two IDs]
"""


def build_draft_prompt(completed_count: int) -> str:
    log = _git("log", "master", "--oneline", "-20", capture=True, check=False, quiet=True)
    recent_log = log.stdout.strip() if log.returncode == 0 else "(unavailable)"

    all_tasks = parse_task_queue()
    last_tasks = all_tasks[-3:] if len(all_tasks) >= 3 else all_tasks
    last_tasks_text = "\n\n".join(
        f"## {t['task_id']}\nGoal: {t['goal']}\n\nAcceptance criteria:\n{t['criteria']}"
        for t in last_tasks
    )

    nxt = next_task_id()
    return _DRAFT_PROMPT.format(
        recent_log=recent_log,
        last_tasks=last_tasks_text or "(queue empty)",
        next_id=nxt,
        completed_count=completed_count,
    )


# ---------------------------------------------------------------------------
# Batch generator (--auto-generate)
# ---------------------------------------------------------------------------

def generate_next_batch(completed_count: int, dry_run: bool) -> int:
    """
    Call Claude to draft the next batch of tasks, validate, and append to
    TASK_QUEUE.md.  Returns number of new tasks appended (0 on failure).
    """
    print("\n" + "~" * 62, flush=True)
    print("  AUTO-GENERATE: drafting next task batch via claude -p", flush=True)
    print("~" * 62, flush=True)

    if dry_run:
        nxt = next_task_id()
        print(f"[DRY-RUN] Would generate 3 tasks starting from {nxt}")
        return 3  # pretend we generated tasks so the loop can continue in dry-run

    prompt = build_draft_prompt(completed_count)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    result = _run(
        [
            "claude", "-p", prompt,
            "--allowedTools", "Read",          # read-only — just needs context files
            "--output-format", "text",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        print(f"  claude -p failed (exit {result.returncode}):", flush=True)
        print(result.stderr[:500], flush=True)
        return 0

    raw = result.stdout.strip()
    if not raw:
        print("  claude -p returned empty output — stopping auto-generate.", flush=True)
        return 0

    blocks = parse_task_blocks(raw)
    if not blocks:
        print("  No valid ## TASK-NNN blocks found in claude output:", flush=True)
        print(raw[:600], flush=True)
        return 0

    # Deduplicate against what's already in the queue
    existing_ids = {t["task_id"] for t in parse_task_queue()}
    new_blocks = [(tid, blk) for tid, blk in blocks if tid not in existing_ids]
    if not new_blocks:
        print("  All generated task IDs already exist in queue — nothing to append.", flush=True)
        return 0

    # Append to TASK_QUEUE.md
    current = TASK_QUEUE_PATH.read_text(encoding="utf-8")
    separator = "\n\n" if current.endswith("\n") else "\n\n\n"
    addition = separator + "\n\n".join(blk for _, blk in new_blocks) + "\n"
    TASK_QUEUE_PATH.write_text(current + addition, encoding="utf-8")

    print(f"\n  Appended {len(new_blocks)} new task(s) to TASK_QUEUE.md:", flush=True)
    for tid, _ in new_blocks:
        print(f"    + {tid}", flush=True)

    # Commit the queue update
    dirty = get_dirty_paths()
    if "claude/TASK_QUEUE.md" in dirty:
        _git("add", "claude/TASK_QUEUE.md")
        _git("commit", "-m", f"chore: auto-generate tasks {', '.join(t for t, _ in new_blocks)}")

    return len(new_blocks)


# ---------------------------------------------------------------------------
# Single-batch executor
# ---------------------------------------------------------------------------

def execute_batch(task: dict, dry_run: bool, tag: str) -> str:
    """
    Run the full workflow for one task.
    Returns the new tag string on success.  Raises on failure.
    """
    task_id = task["task_id"]
    new_tag = next_minor_tag(tag)

    print(f"\n{'=' * 62}", flush=True)
    print(f"  BATCH  {task_id}  ({tag} -> {new_tag})", flush=True)
    print(f"  GOAL   {task['goal'][:70]}", flush=True)
    print(f"{'=' * 62}", flush=True)

    if dry_run:
        print(f"[DRY-RUN] Would run full workflow for {task_id} -> {new_tag}")
        return new_tag

    # 0. Reconcile STATE/NEXT_ACTION
    print(f"\n[0/8] claude_orchestrate.ps1 (reconcile)", flush=True)
    _pwsh("claude_orchestrate.ps1")

    # 1. Ensure clean tree
    dirty = get_dirty_paths()
    if dirty and all(p.startswith("claude/") for p in dirty):
        print(f"  Auto-committing claude/ changes before start_task...", flush=True)
        _git("add", "claude/")
        _git("commit", "-m", f"chore: queue/journal updates before {task_id}")
        dirty = get_dirty_paths()
    if dirty:
        raise RuntimeError(f"Dirty working tree before start_task: {dirty}")

    # 2. start_task.ps1
    print(f"\n[1/8] start_task.ps1 — {task_id}", flush=True)
    _pwsh("start_task.ps1", "-TaskId", task_id, "-Goal", task["goal"])

    # 3. Advance: triage/RESEARCH → build/DEV
    print("\n[2/8] advance_state → build/DEV", flush=True)
    _pwsh("advance_state.ps1", "-ToPhase", "build", "-ToRole", "DEV")

    # 4. claude -p: implement + test + commit
    print(f"\n[3/8] claude -p — implementing {task_id}", flush=True)
    _run(
        [
            "claude", "-p", build_impl_prompt(task),
            "--allowedTools", "Read,Edit,Write,Bash,Grep,Glob",
            "--output-format", "text",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    # 5. Safety-net: verify tests pass
    print("\n[4/8] safety-net: run test suite", flush=True)
    _run(
        ["python", "-m", "unittest", "api.test_app", "-v"],
        cwd=str(SOLO_DIR),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    # 6. Advance: build/DEV → verify/AUDITOR
    print("\n[5/8] advance_state → verify/AUDITOR", flush=True)
    _pwsh("advance_state.ps1", "-ToPhase", "verify", "-ToRole", "AUDITOR")
    _pwsh("claude_orchestrate.ps1")
    _pwsh("audit_check.ps1")

    # 7. Advance: verify/AUDITOR → done/AUDITOR
    print("\n[6/8] advance_state → done/AUDITOR", flush=True)
    _pwsh("advance_state.ps1", "-ToPhase", "done", "-ToRole", "AUDITOR")
    _pwsh("claude_orchestrate.ps1")

    # 8. Commit audit artifacts
    print("\n[7/8] commit audit artifacts", flush=True)
    dirty_after = get_dirty_paths()
    if dirty_after:
        _git("add", "claude/")
        _git("commit", "-m", f"chore: audit artifacts {task_id} verify/AUDITOR pass")

    # 9. Merge + tag
    print(f"\n[8/8] merge task/{task_id} -> master + tag {new_tag}", flush=True)
    _git("checkout", "master")
    _git(
        "merge", "--no-ff", f"task/{task_id}",
        "-m",
        f"feat(api): {task_id} — {task['goal'][:60]}\n\n"
        f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>",
    )
    _git("tag", new_tag)

    print(f"\n  OK  {task_id} complete — tagged {new_tag}", flush=True)
    return new_tag


# ---------------------------------------------------------------------------
# Queue loader (filters to pending tasks)
# ---------------------------------------------------------------------------

def load_pending(start_from: str | None) -> list:
    all_tasks = parse_task_queue()
    skipping = bool(start_from)
    pending = []
    for task in all_tasks:
        if skipping:
            if task["task_id"] == start_from:
                skipping = False
            else:
                continue
        if is_task_merged(task["task_id"]):
            print(f"  {task['task_id']} — already merged, skipping", flush=True)
            continue
        pending.append(task)
    return pending


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Continuous self-looping batch executor for Solo Builder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print steps without executing")
    parser.add_argument("--start-from", metavar="TASK-NNN",
                        help="Skip tasks before this ID")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after N tasks from the initial queue (0=unlimited)")
    parser.add_argument("--auto-generate", action="store_true",
                        help="When queue empties, call Claude to draft the next batch and loop")
    parser.add_argument("--max-total", type=int, default=0,
                        help="Hard ceiling on total batches this session "
                             "(default 10 when --auto-generate, else 0=unlimited)")
    args = parser.parse_args()

    # Apply sensible default for max-total when auto-generating
    max_total = args.max_total
    if args.auto_generate and max_total == 0:
        max_total = 10
        print(f"  --auto-generate: defaulting --max-total to {max_total} "
              "(pass --max-total 0 to remove limit)", flush=True)

    tag = get_latest_tag()
    print(f"Current latest tag: {tag}", flush=True)

    total_executed = 0
    start_from = args.start_from  # only applied on first pass through the queue

    while True:
        # ── Load pending tasks ─────────────────────────────────────────────
        print(f"\nScanning TASK_QUEUE.md for pending tasks...", flush=True)
        pending = load_pending(start_from)
        start_from = None  # only skip on the first scan

        if args.limit > 0:
            remaining_under_limit = args.limit - total_executed
            if remaining_under_limit <= 0:
                print(f"\n--limit {args.limit} reached. Stopping.", flush=True)
                break
            pending = pending[:remaining_under_limit]

        if not pending:
            if not args.auto_generate:
                print(
                    "\nQueue exhausted. Add tasks to claude/TASK_QUEUE.md to continue.\n"
                    "Or rerun with --auto-generate to have Claude draft the next batch.",
                    flush=True,
                )
                break

            # Auto-generate the next batch
            added = generate_next_batch(total_executed, dry_run=args.dry_run)
            if added == 0:
                print("\nAuto-generate produced no new tasks — stopping.", flush=True)
                break
            # Re-scan on next loop iteration
            continue

        # ── Execute pending tasks ──────────────────────────────────────────
        for task in pending:
            if max_total > 0 and total_executed >= max_total:
                print(f"\n--max-total {max_total} reached. Stopping.", flush=True)
                return 0

            try:
                tag = execute_batch(task, dry_run=args.dry_run, tag=tag)
                total_executed += 1
            except subprocess.CalledProcessError as exc:
                print(
                    f"\n  FAIL  {task['task_id']}: subprocess exit {exc.returncode}\n"
                    f"  Fix the issue then rerun with:  "
                    f"python tools/auto_batch.py --start-from {task['task_id']}",
                    flush=True,
                )
                return 1
            except RuntimeError as exc:
                print(
                    f"\n  FAIL  {task['task_id']}: {exc}\n"
                    f"  Fix the issue then rerun with:  "
                    f"python tools/auto_batch.py --start-from {task['task_id']}",
                    flush=True,
                )
                return 1

        # After exhausting the current pending list, loop back to re-scan.
        # If --auto-generate is off, the next scan will find nothing and we'll break.
        # If --limit is set, we'll break at the top of the loop.

    print(
        f"\nDone. {total_executed} batch(es) executed this session. Latest tag: {tag}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
