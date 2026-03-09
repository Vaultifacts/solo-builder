"""
Solo Builder — Discord Bot Formatters

Pure formatting/helper functions extracted from bot.py.
These functions take state dicts as parameters and have no dependency on
patched module-level constants from bot.py, making them safe to move.
"""

import csv
import io
import json
import os
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent   # solo_builder/


def _has_work(dag: dict) -> bool:
    return any(
        s.get("status") in ("Pending", "Running")
        for t in dag.values()
        for b in t["branches"].values()
        for s in b["subtasks"].values()
    )


def _find_subtask_output(state: dict, st_target: str) -> "tuple[str, str] | None":
    """Return (task_name, output) for a subtask by name, or None if not found."""
    for task_name, task in state.get("dag", {}).items():
        for branch in task.get("branches", {}).values():
            for st_name, st_data in branch.get("subtasks", {}).items():
                if st_name.upper() == st_target.upper():
                    return task_name, st_data.get("output", "")
    return None


def _format_search(state: dict, query: str) -> str:
    """Search subtasks by keyword in name, description, or output."""
    query = query.strip().lower()
    if not query:
        return "Usage: `search <keyword>`"
    dag = state.get("dag", {})
    matches = []
    for task_name, task_data in dag.items():
        for b in task_data.get("branches", {}).values():
            for st_name, st_data in b.get("subtasks", {}).items():
                desc = (st_data.get("description") or "").lower()
                out = (st_data.get("output") or "").lower()
                if query in desc or query in out or query in st_name.lower():
                    icon = {"Verified": "✅", "Running": "▶", "Review": "⏸"}.get(st_data.get("status", "Pending"), "⏳")
                    preview = (st_data.get("description") or "")[:50]
                    matches.append(f"{icon} `{st_name}` ({task_name}) — {preview}")
    n = len(matches)
    header = f"**Search: '{query}'** — {n} match{'es' if n != 1 else ''}"
    if not matches:
        return header + "\n_No matches found._"
    return header + "\n" + "\n".join(matches[:20])


def _format_branches(state: dict, task_filter: str = "") -> str:
    """Return formatted branch listing, optionally filtered to one task."""
    dag = state.get("dag", {})
    task_filter = task_filter.strip()
    if task_filter:
        # Normalise "0" → "Task 0"
        if task_filter.isdigit():
            task_filter = f"Task {task_filter}"
        task_data = dag.get(task_filter)
        if not task_data:
            return f"⚠️ Task `{task_filter}` not found."
        branches = task_data.get("branches", {})
        lines = [f"**{task_filter}** — {len(branches)} branch{'es' if len(branches) != 1 else ''}", "```"]
        for br_name, br_data in branches.items():
            subs = br_data.get("subtasks", {})
            v = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r = sum(1 for s in subs.values() if s.get("status") == "Running")
            p = len(subs) - v - r
            lines.append(f"  {br_name:<14} {len(subs)} STs  {v}✓ {r}▶ {p}●")
            for st_name, st_data in subs.items():
                icon = {"Verified": "✅", "Running": "▶", "Review": "⏸"}.get(st_data.get("status", "Pending"), "⏳")
                lines.append(f"    {icon} {st_name:<5} {st_data.get('status', 'Pending')}")
        lines.append("```")
        return "\n".join(lines)
    # All tasks overview
    lines = ["**Branches Overview**", "```"]
    for task_name, task_data in dag.items():
        branches = task_data.get("branches", {})
        lines.append(f"{task_name}  ({len(branches)} branches)")
        for br_name, br_data in branches.items():
            subs = br_data.get("subtasks", {})
            v = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r = sum(1 for s in subs.values() if s.get("status") == "Running")
            p = len(subs) - v - r
            lines.append(f"  {br_name:<14} {len(subs)} STs  {v}✓ {r}▶ {p}●")
    lines.append("```")
    return "\n".join(lines)


def _branches_to_csv(state: dict) -> bytes:
    """Return CSV bytes of all branches (task,branch,total,verified,running,review,pending,pct)."""
    dag = state.get("dag", {})
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["task", "branch", "total", "verified", "running", "review", "pending", "pct"])
    for task_name, task_data in dag.items():
        for br_name, br_data in task_data.get("branches", {}).items():
            subs = br_data.get("subtasks", {})
            total = len(subs)
            v  = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r  = sum(1 for s in subs.values() if s.get("status") == "Running")
            rv = sum(1 for s in subs.values() if s.get("status") == "Review")
            p  = total - v - r - rv
            pct = round(v / total * 100, 1) if total else 0.0
            writer.writerow([task_name, br_name, total, v, r, rv, p, pct])
    return buf.getvalue().encode("utf-8")


def _format_subtasks(state: dict, task_filter: str = "", status_filter: str = "") -> str:
    """Return formatted subtask listing with optional ?task= and ?status= filters."""
    dag = state.get("dag", {})
    task_q   = task_filter.strip().lower()
    status_q = status_filter.strip().lower()
    rows: list = []
    for task_name, task_data in dag.items():
        if task_q and task_q not in task_name.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            for st_name, st_data in br_data.get("subtasks", {}).items():
                st_status = st_data.get("status", "Pending")
                if status_q and status_q not in st_status.lower():
                    continue
                rows.append((task_name, br_name, st_name, st_status))
    if not rows:
        return "⚠️ No subtasks match the given filters."
    icon_map = {"Verified": "✅", "Running": "▶", "Review": "⏸", "Pending": "⏳"}
    lines = [f"**Subtasks** ({len(rows)})", "```"]
    for task_name, br_name, st_name, st_status in rows:
        icon = icon_map.get(st_status, "⏳")
        lines.append(f"{icon} {st_name:<5} {st_status:<10}  {task_name} / {br_name}")
    lines.append("```")
    msg = "\n".join(lines)
    if len(msg) > 1900:
        msg = msg[:1900] + "\n…(truncated)"
    return msg


def _subtasks_to_csv(state: dict, task_filter: str = "", status_filter: str = "") -> bytes:
    """Return CSV bytes of all subtasks with optional task/status filters."""
    dag = state.get("dag", {})
    task_q   = task_filter.strip().lower()
    status_q = status_filter.strip().lower()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["subtask", "task", "branch", "status", "output_length"])
    for task_name, task_data in dag.items():
        if task_q and task_q not in task_name.lower():
            continue
        for br_name, br_data in task_data.get("branches", {}).items():
            for st_name, st_data in br_data.get("subtasks", {}).items():
                st_status = st_data.get("status", "Pending")
                if status_q and status_q not in st_status.lower():
                    continue
                writer.writerow([st_name, task_name, br_name, st_status,
                                  len(st_data.get("output", ""))])
    return buf.getvalue().encode("utf-8")


def _format_history(state: dict, limit: int = 20, task_filter: str = "",
                    branch_filter: str = "", status_filter: str = "") -> str:
    """Return a formatted recent activity log across all subtasks.

    Optional task_filter, branch_filter, status_filter apply case-insensitive substring matching.
    """
    dag = state.get("dag", {})
    task_q   = task_filter.strip().lower()
    branch_q = branch_filter.strip().lower()
    status_q = status_filter.strip().lower()
    events: list = []
    for task_name, task_data in dag.items():
        if task_q and task_q not in task_name.lower():
            continue
        for br_name, b in task_data.get("branches", {}).items():
            if branch_q and branch_q not in br_name.lower():
                continue
            for st_name, st_data in b.get("subtasks", {}).items():
                for h in st_data.get("history", []):
                    st = h.get("status", "?")
                    if status_q and status_q not in st.lower():
                        continue
                    icon = {"Running": "▶", "Verified": "✅", "Review": "⏸"}.get(st, "❓")
                    events.append((h.get("step", 0), st_name, task_name, st, icon))
    events.sort(key=lambda x: x[0], reverse=True)
    events = events[:limit]
    if not events:
        return "**Recent Activity**\n_No history recorded yet._"
    lines = [f"**Recent Activity** (last {limit})", "```"]
    for step, st_name, task_name, status, icon in events:
        lines.append(f"  Step {step:<4} {st_name:<5} {status:<10} ({task_name})")
    lines.append("```")
    return "\n".join(lines)


def _format_stats(state: dict) -> str:
    """Return a formatted per-task stats table."""
    dag = state.get("dag", {})
    lines = ["**Per-Task Statistics**", "```"]
    lines.append(f"{'Task':<12} {'V':>4} {'Tot':>4} {'Pct':>5}  {'Avg':>5}")
    lines.append("─" * 38)
    grand_v = grand_t = 0
    all_dur: list = []
    for task_name, task_data in dag.items():
        tv = tt = 0
        durs: list = []
        for b in task_data.get("branches", {}).values():
            for st in b.get("subtasks", {}).values():
                tt += 1
                if st.get("status") == "Verified":
                    tv += 1
                    h = st.get("history", [])
                    if len(h) >= 2:
                        durs.append(h[-1].get("step", 0) - h[0].get("step", 0))
        pct = round(tv / tt * 100, 1) if tt else 0
        avg = f"{sum(durs)/len(durs):.1f}" if durs else "—"
        mark = "✅" if tv == tt and tt > 0 else "▶" if tv > 0 else "⏳"
        lines.append(f"{mark} {task_name:<10} {tv:>4} {tt:>4} {pct:>4}%  {avg:>5}")
        grand_v += tv
        grand_t += tt
        all_dur.extend(durs)
    lines.append("─" * 38)
    gp = round(grand_v / grand_t * 100, 1) if grand_t else 0
    ga = f"{sum(all_dur)/len(all_dur):.1f}" if all_dur else "—"
    lines.append(f"  {'TOTAL':<10} {grand_v:>4} {grand_t:>4} {gp:>4}%  {ga:>5}")
    lines.append("```")
    return "\n".join(lines)


def _format_cache(clear: bool = False) -> str:
    """Return a cache stats summary by reading the cache directory directly."""
    cache_dir = Path(os.environ.get("CACHE_DIR", str(_ROOT.parent / "claude" / "cache")))
    try:
        entries = list(cache_dir.glob("*.json"))
        size = len(entries)
    except Exception:
        return "❌ Could not read cache directory."
    avg_tokens = 550
    est_tokens = size * avg_tokens
    lines = [
        "**Response Cache (disk)**",
        "```",
        f"{'Entries on disk':<22} {size}",
        f"{'Est. tokens held':<22} {est_tokens:,}",
        f"{'Cache directory':<22} {cache_dir}",
        "```",
    ]
    if clear:
        deleted = 0
        for f in entries:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
        lines.append(f"🗑️ Cleared **{deleted}** cache entries.")
    else:
        lines.append("_Use `cache clear` to wipe all entries._")
    return "\n".join(lines)


def _format_tasks(state: dict) -> str:
    """Return a per-task summary table (verified/total, %, status)."""
    dag = state.get("dag", {})
    if not dag:
        return "No tasks."
    lines = ["**Tasks**", "```"]
    for t_name, t_data in dag.items():
        branches = t_data.get("branches", {})
        total = sum(len(b.get("subtasks", {})) for b in branches.values())
        verified = sum(
            1 for b in branches.values()
            for st in b.get("subtasks", {}).values()
            if st.get("status") == "Verified"
        )
        pct = int(verified / total * 100) if total else 0
        status = t_data.get("status", "Pending")
        mark = "✅" if status == "Verified" else "▶" if verified > 0 else "⏳"
        lines.append(f"{mark} {t_name:<10} {verified:>2}/{total:<2} {pct:>3}%  [{status}]")
    lines.append("```")
    return "\n".join(lines)


def _format_task_progress(state: dict, task_id: str) -> str:
    """Return a per-branch progress summary for a single task."""
    task_id = task_id.strip()
    if not task_id:
        return "Usage: `task_progress <task_id>`"
    dag = state.get("dag", {})
    if task_id not in dag:
        return f"⚠️ Task **{task_id}** not found."
    task = dag[task_id]
    branches = task.get("branches", {})
    if not branches:
        return f"**{task_id}** — no branches."
    lines = [f"**{task_id}** — {task.get('status', 'Pending')}", "```"]
    t_total = t_verified = t_running = t_review = t_pending = 0
    for br_name, br_data in branches.items():
        subtasks = br_data.get("subtasks", {})
        total    = len(subtasks)
        verified = sum(1 for s in subtasks.values() if s.get("status") == "Verified")
        running  = sum(1 for s in subtasks.values() if s.get("status") == "Running")
        review   = sum(1 for s in subtasks.values() if s.get("status") == "Review")
        pending  = total - verified - running - review
        pct      = int(verified / total * 100) if total else 0
        bar_fill = int(pct * 10 / 100)
        bar      = "█" * bar_fill + "░" * (10 - bar_fill)
        extras = f"{running}▶" if running else ""
        if review:   extras += f" {review}⏸"
        if pending:  extras += f" {pending}●"
        lines.append(f"{br_name:<16} [{bar}] {verified:>2}/{total:<2} {pct:>3}%  {extras.strip()}")
        t_total    += total
        t_verified += verified
        t_running  += running
        t_review   += review
        t_pending  += pending
    t_pct = int(t_verified / t_total * 100) if t_total else 0
    t_extras = (f"{t_running}▶" if t_running else "") + \
               (f" {t_review}⏸" if t_review else "") + \
               (f" {t_pending}●" if t_pending else "")
    lines.append(f"{'TOTAL':<16}   {t_verified:>2}/{t_total:<2} {t_pct:>3}%  {t_extras.strip()}")
    lines.append("```")
    return "\n".join(lines)


def _format_priority(state: dict) -> str:
    """Show which subtasks would execute next, ranked by risk score."""
    dag = state.get("dag", {})
    step = state.get("step", 0)
    if not dag:
        return "No tasks in DAG."
    candidates = []
    for task_name, task in dag.items():
        deps_met = all(dag.get(d, {}).get("status") == "Verified"
                       for d in task.get("depends_on", []))
        if not deps_met:
            continue
        for branch in task.get("branches", {}).values():
            for st_name, st_data in branch.get("subtasks", {}).items():
                status = st_data.get("status", "Pending")
                if status not in ("Pending", "Running"):
                    continue
                age = step - st_data.get("last_update", 0)
                risk = 1000 + age * 10 if status == "Running" else age * 8
                candidates.append((st_name, task_name, status, risk))
    candidates.sort(key=lambda x: x[3], reverse=True)
    if not candidates:
        return "✅ **Priority Queue** — empty (all subtasks Verified or blocked)"
    lines = [f"**Priority Queue** ({len(candidates)} candidates, step {step})", "```"]
    for i, (st_name, task_name, status, risk) in enumerate(candidates[:15]):
        marker = "▶ " if i < 6 else "  "
        icon = "▶" if status == "Running" else "⏳"
        lines.append(f"{marker}{icon} {st_name:<5} {status:<9} risk={risk:<5} {task_name}")
    if len(candidates) > 15:
        lines.append(f"… and {len(candidates) - 15} more")
    lines.append("```")
    lines.append("_Top 6 (▶) execute next step_")
    return "\n".join(lines)


def _format_stalled(state: dict, task_filter: str = "", branch_filter: str = "") -> str:
    """Show subtasks stuck in Running longer than STALL_THRESHOLD.

    Optional task_filter and branch_filter apply case-insensitive substring matching.
    """
    dag = state.get("dag", {})
    step = state.get("step", 0)
    task_q   = task_filter.strip().lower()
    branch_q = branch_filter.strip().lower()
    threshold = 5
    try:
        cfg = json.loads((_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
    except Exception:
        pass
    stuck = []
    branch_counts: dict = {}
    for task_name, task in dag.items():
        if task_q and task_q not in task_name.lower():
            continue
        for branch_name, branch in task.get("branches", {}).items():
            if branch_q and branch_q not in branch_name.lower():
                continue
            for st_name, st_data in branch.get("subtasks", {}).items():
                if st_data.get("status") == "Running":
                    age = step - st_data.get("last_update", 0)
                    if age >= threshold:
                        desc = (st_data.get("description") or "")[:40]
                        stuck.append((st_name, task_name, branch_name, age, desc))
                        key = f"{task_name} / {branch_name}"
                        branch_counts[key] = branch_counts.get(key, 0) + 1
    stuck.sort(key=lambda x: x[3], reverse=True)
    if not stuck:
        return f"✅ **Stalled Subtasks** — none (threshold: {threshold} steps)"
    lines = [f"⚠️ **Stalled Subtasks** ({len(stuck)}, threshold: {threshold} steps)"]
    if len(branch_counts) > 1:
        lines.append("```")
        for key, cnt in sorted(branch_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {key:<30} {cnt} stalled")
        lines.append("```")
    lines.append("```")
    for st_name, task_name, branch_name, age, desc in stuck:
        lines.append(f"  {st_name:<5} stalled {age} steps  {task_name} — {desc}")
    lines.append("```")
    lines.append("_SelfHealer auto-resets after threshold_")
    return "\n".join(lines)


def _format_agents(state: dict) -> str:
    """Show agent statistics from state file."""
    step = state.get("step", 0)
    dag = state.get("dag", {})
    healed = state.get("healed_total", 0)
    meta_history = state.get("meta_history", [])
    # Compute live stats
    total = verified = running = pending = stalled_count = 0
    threshold = 5
    cfg = {}
    try:
        cfg = json.loads((_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
        threshold = int(cfg.get("STALL_THRESHOLD", 5))
    except Exception:
        pass
    for task in dag.values():
        for branch in task.get("branches", {}).values():
            for st_data in branch.get("subtasks", {}).values():
                total += 1
                s = st_data.get("status", "Pending")
                if s == "Verified":
                    verified += 1
                elif s == "Running":
                    running += 1
                    age = step - st_data.get("last_update", 0)
                    if age >= threshold:
                        stalled_count += 1
                elif s == "Pending":
                    pending += 1
    heal_rate = verify_rate = 0.0
    if meta_history:
        window = min(10, len(meta_history))
        recent = meta_history[-window:]
        heal_rate = sum(r.get("healed", 0) for r in recent) / window
        verify_rate = sum(r.get("verified", 0) for r in recent) / window
    pct = round(verified / total * 100) if total else 0
    eta = f"~{(total - verified) / (verify_rate + 1e-6):.0f} steps" if verify_rate > 0 else "N/A"
    lines = [
        f"**Agent Statistics** (step {step})",
        "```",
        f"Planner       cache refreshes every 5 steps",
        f"Executor      max_per_step: {cfg.get('EXECUTOR_MAX_PER_STEP', 6)}",
        f"SelfHealer    healed: {healed}  threshold: {threshold}  stalled now: {stalled_count}",
        f"ShadowAgent   tracking subtask states",
        f"MetaOptimizer {len(meta_history)} entries  heal_rate: {heal_rate:.2f}  verify_rate: {verify_rate:.2f}",
        f"Forecast      {pct}% done ({verified}/{total})  ETA: {eta}",
        "```",
    ]
    return "\n".join(lines)


def _format_forecast(state: dict) -> str:
    """Show detailed completion forecast."""
    dag = state.get("dag", {})
    step = state.get("step", 0)
    meta_history = state.get("meta_history", [])
    total = verified = running = pending = review = 0
    for task in dag.values():
        for branch in task.get("branches", {}).values():
            for st_data in branch.get("subtasks", {}).values():
                total += 1
                s = st_data.get("status", "Pending")
                if s == "Verified": verified += 1
                elif s == "Running": running += 1
                elif s == "Pending": pending += 1
                elif s == "Review": review += 1
    remaining = total - verified
    pct = round(verified / total * 100, 1) if total else 0
    verify_rate = heal_rate = 0.0
    if meta_history:
        window = min(10, len(meta_history))
        recent = meta_history[-window:]
        verify_rate = sum(r.get("verified", 0) for r in recent) / window
        heal_rate = sum(r.get("healed", 0) for r in recent) / window
    eta = f"~{remaining / verify_rate:.0f} steps" if verify_rate > 0 else "N/A"
    bar_len = 20
    filled = round(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    lines = [
        f"**Completion Forecast** (step {step})",
        "```",
        f"Progress   {bar} {pct}%",
        f"Breakdown  {verified}✓  {running}▶  {pending}⏳  {review}⏸",
        f"Remaining  {remaining} subtasks",
        f"Verify     {verify_rate:.2f}/step (last 10)",
        f"Heal       {heal_rate:.2f}/step (last 10)",
        f"ETA        {eta}",
        "```",
    ]
    return "\n".join(lines)


def _format_filter(state: dict, status: str) -> str:
    """Return subtasks matching a given status."""
    target = status.strip().capitalize()
    valid = ("Verified", "Running", "Pending", "Review")
    if target not in valid:
        return f"Usage: `filter <{'|'.join(valid)}>`"
    icon = {"Verified": "✅", "Running": "▶", "Pending": "⏳", "Review": "⏸"}.get(target, "❓")
    matches = []
    for task_name, task in state.get("dag", {}).items():
        for branch in task.get("branches", {}).values():
            for st_name, st_data in branch.get("subtasks", {}).items():
                if st_data.get("status", "Pending") == target:
                    desc = (st_data.get("description") or "")[:50]
                    matches.append(f"{st_name} ({task_name}) — {desc}")
    header = f"{icon} **{target} Subtasks** ({len(matches)})"
    if not matches:
        return f"{header}\n_None._"
    body = "\n".join(f"  {m}" for m in matches[:30])
    return f"{header}\n```\n{body}\n```"


def _format_timeline(state: dict, st_target: str) -> str:
    """Return a formatted timeline string for a subtask's history array."""
    st_target = st_target.strip().upper()
    if not st_target:
        return "Usage: `timeline <subtask>` (e.g. `timeline A1`)"
    for task_name, task in state.get("dag", {}).items():
        for branch in task.get("branches", {}).values():
            for st_name, st_data in branch.get("subtasks", {}).items():
                if st_name.upper() == st_target:
                    history = st_data.get("history", [])
                    status = st_data.get("status", "Pending")
                    icon = {"Pending": "⏳", "Running": "▶", "Verified": "✅", "Review": "⏸"}.get(status, "❓")
                    lines = [f"**Timeline: {st_name}** ({task_name})", f"Current: {icon} {status}"]
                    if not history:
                        lines.append("_No transitions recorded yet._")
                    else:
                        parts = ["⏳ Pending"]
                        for h in history:
                            s = h.get("status", "?")
                            step = h.get("step", "?")
                            hi = {"Running": "▶", "Verified": "✅", "Review": "⏸"}.get(s, "❓")
                            parts.append(f"{hi} {s} (step {step})")
                        lines.append(" → ".join(parts))
                    return "\n".join(lines)
    return f"⚠️ Subtask `{st_target}` not found."


def _format_status(state: dict) -> str:
    """Return a markdown summary matching GET /dag/summary's `summary` field format."""
    dag   = state.get("dag", {})
    step  = state.get("step", 0)
    total = verified = running = review = pending = 0
    task_rows: list[str] = []

    for task_id, task_data in dag.items():
        t_total = t_verified = t_running = t_review = 0
        for br in task_data.get("branches", {}).values():
            for st in br.get("subtasks", {}).values():
                t_total += 1
                s = st.get("status", "Pending")
                if s == "Verified":
                    t_verified += 1
                elif s == "Running":
                    t_running += 1
                elif s == "Review":
                    t_review += 1
        t_pct = round(t_verified / t_total * 100, 1) if t_total else 0.0
        t_status = task_data.get("status", "Pending")
        bar = ("=" * int(t_pct / 10)).ljust(10, "-")
        task_rows.append(
            f"- **{task_id}** [{bar}] {t_verified}/{t_total} ({t_pct}%)  {t_status}"
        )
        total    += t_total
        verified += t_verified
        running  += t_running
        review   += t_review
        pending  += t_total - t_verified - t_running - t_review

    pct = round(verified / total * 100, 1) if total else 0.0
    lines = [
        "## Pipeline Summary",
        f"- Step {step}",
        f"- {verified}/{total} subtasks verified ({pct}%)",
        f"- {running} running, {review} review, {pending} pending",
        "",
        "### Tasks",
    ] + task_rows
    return "\n".join(lines)


def _format_log(st_filter: str = "") -> str:
    """Return formatted journal entries, optionally filtered by subtask name."""
    import re as _re
    import discord_bot.bot as _b
    JOURNAL_PATH = _b.JOURNAL_PATH  # respect test patches on bot_module.JOURNAL_PATH
    st_filter = st_filter.strip().upper()
    if not JOURNAL_PATH.exists():
        return "⚠️ No journal file found."
    try:
        content = JOURNAL_PATH.read_text(encoding="utf-8")
    except Exception:
        return "❌ Could not read journal."
    blocks = _re.split(r"(?=^## )", content, flags=_re.MULTILINE)
    entries = []
    for block in blocks:
        if not block.strip().startswith("## "):
            continue
        m = _re.match(r"^## (\w+) · (Task \d+) / (Branch \w+) · Step (\d+)", block)
        if not m:
            continue
        st_name = m.group(1)
        if st_filter and st_name.upper() != st_filter:
            continue
        body = block[m.end():].strip()
        body = _re.sub(r"^\*\*Prompt:\*\*.*\n\n?", "", body).strip().rstrip("-").strip()
        entries.append(f"`{st_name}` · {m.group(2)} / {m.group(3)} · Step {m.group(4)}\n{body[:100]}")
    label = f" for `{st_filter}`" if st_filter else ""
    header = f"**Journal{label}** — {len(entries)} entr{'ies' if len(entries) != 1 else 'y'}"
    if not entries:
        return header + "\n_No entries found._"
    return header + "\n" + "\n".join(entries[-10:])


def _format_diff() -> str:
    """Compare current state to .1 backup and return a formatted diff string."""
    import discord_bot.bot as _b
    STATE_PATH = _b.STATE_PATH  # respect test patches on bot_module.STATE_PATH
    backup_path = Path(str(STATE_PATH) + ".1")
    if not backup_path.exists():
        return "⚠️ No backup to diff against (need at least 2 saves)."
    try:
        old = json.loads(backup_path.read_text(encoding="utf-8"))
    except Exception:
        return "❌ Could not read backup file."
    current = _b._load_state()  # respect test patches on bot_module._load_state
    old_dag = old.get("dag", {})
    new_dag = current.get("dag", {})
    old_step = old.get("step", 0)
    new_step = current.get("step", 0)
    changes = []
    for task_name, task_data in new_dag.items():
        old_task = old_dag.get(task_name, {})
        for branch_name, branch_data in task_data.get("branches", {}).items():
            old_branch = old_task.get("branches", {}).get(branch_name, {})
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                old_st = old_branch.get("subtasks", {}).get(st_name, {})
                old_status = old_st.get("status", "?")
                new_status = st_data.get("status", "?")
                if old_status != new_status:
                    out = st_data.get("output", "")
                    preview = f" — {out[:50]}" if out and new_status in ("Verified", "Review") else ""
                    changes.append(f"`{st_name}` {old_status} → {new_status}{preview}")
    if not changes:
        return f"**Diff** · Step {old_step} → {new_step}\nNo subtask status changes."
    lines = [f"**Diff** · Step {old_step} → {new_step}"]
    for c in changes:
        lines.append(c)
    return "\n".join(lines)


def _format_graph(state: dict) -> str:
    """Build an ASCII dependency graph of the DAG."""
    dag = state.get("dag", {})
    if not dag:
        return "No tasks in DAG."
    sym = {"Verified": "✅", "Running": "▶️", "Review": "⏸", "Pending": "⏳", "Blocked": "🔒"}
    lines = ["**DAG Graph**", "```"]
    task_names = list(dag.keys())
    for i, t_name in enumerate(task_names):
        t = dag[t_name]
        st = t.get("status", "Pending")
        icon = sym.get(st, "⏳")
        deps = t.get("depends_on", [])
        branches = t.get("branches", {})
        n_st = sum(len(b.get("subtasks", {})) for b in branches.values())
        n_v = sum(1 for b in branches.values() for s in b.get("subtasks", {}).values()
                  if s.get("status") == "Verified")
        line = f"{icon} {t_name} [{n_v}/{n_st}]"
        if deps:
            line += f"  ← {', '.join(deps)}"
        lines.append(line)
        # Draw arrows to dependents
        dependents = [tn for tn in task_names if t_name in dag[tn].get("depends_on", [])]
        if dependents:
            for d in dependents:
                lines.append(f"   └──▶ {d}")
    lines.append("```")
    return "\n".join(lines)
