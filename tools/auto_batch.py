#!/usr/bin/env python3
"""
auto_batch.py — Continuous batch executor for Solo Builder dashboard/API features.

Reads TASK_QUEUE.md, finds unstarted task batches, and drives each through
the full deterministic workflow:

  claude_orchestrate.ps1 (reconcile)
  → start_task.ps1 (branch + triage)
  → advance_state build/DEV
  → claude -p (implement + commit)
  → advance_state verify/AUDITOR
  → audit_check.ps1
  → advance_state done/AUDITOR
  → claude_orchestrate.ps1 (reconcile for next task)
  → commit audit artifacts
  → git merge master --no-ff + tag

Usage:
    python tools/auto_batch.py [--dry-run] [--start-from TASK-NNN] [--limit N]

Options:
    --dry-run        Print what would happen without executing anything.
    --start-from     Skip all tasks before this task ID (e.g. TASK-103).
    --limit N        Process at most N batches then stop (0 = unlimited).
"""

import argparse
import json
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
    script_path = TOOLS_DIR / script_name
    return _run(
        ["powershell.exe", "-File", str(script_path)] + list(args),
        check=check,
    )


def _git(*args, capture=False, check=True, quiet=False):
    """Run a git command from REPO_ROOT."""
    return _run(["git"] + list(args), check=check, capture_output=capture, quiet=quiet)


# ---------------------------------------------------------------------------
# Working-tree helpers
# ---------------------------------------------------------------------------

def get_dirty_paths() -> list:
    """Return list of dirty paths in working tree."""
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
# TASK_QUEUE.md parser
# ---------------------------------------------------------------------------

def parse_task_queue() -> list:
    """
    Parse TASK_QUEUE.md and return a list of task dicts:
        {task_id, goal, criteria, body}
    Only includes tasks that have a non-placeholder Goal line.
    """
    text = TASK_QUEUE_PATH.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^##\s+(TASK-\d{3})\s*$", text)
    # blocks: ['preamble', 'TASK-001', 'body1', 'TASK-002', 'body2', ...]
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
            continue  # placeholder

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


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def is_task_merged(task_id: str) -> bool:
    """Return True if task/TASK-NNN has been merged into master.

    Primary check: task/TASK-NNN branch exists and is merged.
    Fallback: task ID appears in master's git log (pre-branch-convention tasks).
    """
    branch = f"task/{task_id}"
    merged = _git("branch", "--merged", "master", capture=True, check=False, quiet=True)
    if merged.returncode == 0:
        if any(b.strip() == branch for b in merged.stdout.splitlines()):
            return True

    # Fallback: look for TASK-NNN reference in master commit history.
    log = _git("log", "master", "--oneline", "--grep", task_id,
               capture=True, check=False, quiet=True)
    if log.returncode == 0 and log.stdout.strip():
        return True

    return False


def get_latest_tag() -> str:
    """Return latest vX.Y.Z tag, or v3.31.0 as fallback."""
    result = _git("describe", "--tags", "--abbrev=0", capture=True, check=False, quiet=True)
    if result.returncode == 0:
        tag = result.stdout.strip()
        if re.match(r"v\d+\.\d+\.\d+", tag):
            return tag
    return "v3.31.0"


def next_minor_tag(current: str) -> str:
    """Bump the minor version: v3.31.0 → v3.32.0."""
    m = re.match(r"v(\d+)\.(\d+)\.(\d+)", current)
    if not m:
        return "v3.32.0"
    major, minor = int(m.group(1)), int(m.group(2))
    return f"v{major}.{minor + 1}.0"


# ---------------------------------------------------------------------------
# Claude implementation prompt
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
    goal_brief = task["goal"][:70].rstrip()
    return _IMPL_PROMPT.format(
        task_id=task["task_id"],
        goal=task["goal"],
        criteria=task["criteria"] or "(see goal above)",
        task_id_lower=task["task_id"].lower(),
        goal_brief=goal_brief,
    )


# ---------------------------------------------------------------------------
# Single-batch executor
# ---------------------------------------------------------------------------

def execute_batch(task: dict, dry_run: bool, tag: str) -> str:
    """
    Run the full workflow for one task batch.
    Returns the new tag string on success.  Raises RuntimeError on failure.
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

    # ── 0. Reconcile STATE/NEXT_ACTION before start_task ──────────────────
    print(f"\n[0/8] claude_orchestrate.ps1 (reconcile state)", flush=True)
    _pwsh("claude_orchestrate.ps1")

    # ── 1. Ensure clean tree (auto-commit TASK_QUEUE.md if it's the only dirty file) ──
    dirty = get_dirty_paths()
    if dirty == ["claude/TASK_QUEUE.md"] or dirty == ["claude/JOURNAL.md"] or \
       all(p.startswith("claude/") for p in dirty):
        print(f"  Auto-committing claude/ changes before start_task...", flush=True)
        _git("add", "claude/")
        _git("commit", "-m", f"chore: queue/journal updates before {task_id}")
        dirty = get_dirty_paths()
    if dirty:
        raise RuntimeError(f"Dirty working tree before start_task: {dirty}")

    # ── 2. start_task.ps1 ─────────────────────────────────────────────────
    print(f"\n[1/8] start_task.ps1 — {task_id}", flush=True)
    _pwsh("start_task.ps1", "-TaskId", task_id, "-Goal", task["goal"])

    # ── 3. Advance state: triage/RESEARCH → build/DEV ─────────────────────
    print("\n[2/8] advance_state → build/DEV", flush=True)
    _pwsh("advance_state.ps1", "-ToPhase", "build", "-ToRole", "DEV")

    # ── 4. claude -p: implement + test + commit ────────────────────────────
    print(f"\n[3/8] claude -p — implementing {task_id}", flush=True)
    prompt = build_impl_prompt(task)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    _run(
        [
            "claude", "-p", prompt,
            "--allowedTools", "Read,Edit,Write,Bash,Grep,Glob",
            "--output-format", "text",
        ],
        cwd=REPO_ROOT,
        env=env,
    )

    # ── 5. Safety-net: verify tests still pass ────────────────────────────
    print("\n[4/8] safety-net: run test suite", flush=True)
    _run(
        ["python", "-m", "unittest", "api.test_app", "-v"],
        cwd=str(SOLO_DIR),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    # ── 6. Advance state: build/DEV → verify/AUDITOR ──────────────────────
    print("\n[5/8] advance_state → verify/AUDITOR", flush=True)
    _pwsh("advance_state.ps1", "-ToPhase", "verify", "-ToRole", "AUDITOR")
    _pwsh("claude_orchestrate.ps1")
    _pwsh("audit_check.ps1")

    # ── 7. Advance state: verify/AUDITOR → done/AUDITOR ───────────────────
    print("\n[6/8] advance_state → done/AUDITOR", flush=True)
    _pwsh("advance_state.ps1", "-ToPhase", "done", "-ToRole", "AUDITOR")
    _pwsh("claude_orchestrate.ps1")

    # ── 8. Commit audit artifacts ──────────────────────────────────────────
    print("\n[7/8] commit audit artifacts", flush=True)
    dirty_after = get_dirty_paths()
    if dirty_after:
        _git("add", "claude/")
        _git("commit", "-m", f"chore: audit artifacts {task_id} verify/AUDITOR pass")

    # ── 9. Merge to master + tag ───────────────────────────────────────────
    print(f"\n[8/8] merge task/{task_id} -> master + tag {new_tag}", flush=True)
    branch = f"task/{task_id}"
    _git("checkout", "master")
    _git(
        "merge", "--no-ff", branch,
        "-m",
        f"feat(api): {task_id} — {task['goal'][:60]}\n\n"
        f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>",
    )
    _git("tag", new_tag)

    print(f"\n  OK  {task_id} complete — tagged {new_tag}", flush=True)
    return new_tag


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Continuous batch executor for Solo Builder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print steps without executing")
    parser.add_argument("--start-from", metavar="TASK-NNN",
                        help="Skip tasks before this ID (e.g. TASK-103)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max batches to run (0 = unlimited)")
    args = parser.parse_args()

    # Parse queue
    all_tasks = parse_task_queue()
    print(f"Parsed {len(all_tasks)} tasks with goals from TASK_QUEUE.md", flush=True)

    # Filter: skip already-merged and apply --start-from
    skipping = bool(args.start_from)
    pending = []
    for task in all_tasks:
        if skipping:
            if task["task_id"] == args.start_from:
                skipping = False
            else:
                continue
        if is_task_merged(task["task_id"]):
            print(f"  {task['task_id']} — already merged, skipping", flush=True)
            continue
        pending.append(task)

    if not pending:
        print(
            "\nAll tasks in TASK_QUEUE.md are complete (or none match --start-from).\n"
            "Add new tasks to claude/TASK_QUEUE.md to continue.",
            flush=True,
        )
        return 0

    if args.limit > 0:
        pending = pending[: args.limit]

    print(f"\n{len(pending)} task(s) to process:", flush=True)
    for t in pending:
        print(f"  {t['task_id']} — {t['goal'][:65]}", flush=True)

    tag = get_latest_tag()
    print(f"\nCurrent latest tag: {tag}", flush=True)

    failed = []
    for task in pending:
        try:
            tag = execute_batch(task, dry_run=args.dry_run, tag=tag)
        except subprocess.CalledProcessError as exc:
            msg = f"Subprocess failed (exit {exc.returncode}): {exc.cmd}"
            print(f"\n  FAIL  {task['task_id']}: {msg}", flush=True)
            failed.append((task["task_id"], msg))
            break
        except RuntimeError as exc:
            print(f"\n  FAIL  {task['task_id']}: {exc}", flush=True)
            failed.append((task["task_id"], str(exc)))
            break

    if failed:
        task_id, reason = failed[0]
        print(
            f"\nBatch executor stopped after failure on {task_id}.\n"
            f"Reason: {reason}\n"
            f"Fix the issue then rerun with:  python tools/auto_batch.py --start-from {task_id}",
            flush=True,
        )
        return 1

    print(f"\nAll batches complete.  Latest tag: {tag}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
