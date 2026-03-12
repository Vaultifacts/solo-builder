"""Bot text-command handler — extracted from bot.py (TASK-414).

Provides _handle_text_command() and the helper formatters it depends on.
Uses lazy import of bot module to avoid circular imports.
"""
import asyncio
import json
from typing import Optional

import discord

from .bot_formatters import (
    _has_work, _find_subtask_output,
    _format_log, _format_search, _format_branches, _format_subtasks,
    _format_history, _format_stats, _format_cache, _format_tasks,
    _format_task_progress, _format_priority, _format_stalled, _format_agents,
    _format_forecast, _format_filter, _format_timeline, _format_diff,
    _format_status, _format_graph,
)


def _bot():
    """Lazy import to avoid circular dependency."""
    import solo_builder.discord_bot.bot as _b
    return _b


# Settings key map
_KEY_MAP = {
    "STALL_THRESHOLD": "STALL_THRESHOLD",
    "SNAPSHOT_INTERVAL": "SNAPSHOT_INTERVAL",
    "VERBOSITY": "VERBOSITY",
    "VERIFY_PROB": "EXECUTOR_VERIFY_PROBABILITY",
    "AUTO_STEP_DELAY": "AUTO_STEP_DELAY",
    "AUTO_SAVE_INTERVAL": "AUTO_SAVE_INTERVAL",
    "CLAUDE_ALLOWED_TOOLS": "CLAUDE_ALLOWED_TOOLS",
    "ANTHROPIC_MAX_TOKENS": "ANTHROPIC_MAX_TOKENS",
    "ANTHROPIC_MODEL": "ANTHROPIC_MODEL",
    "REVIEW_MODE": "REVIEW_MODE",
    "WEBHOOK_URL": "WEBHOOK_URL",
    "EXECUTOR_MAX_PER_STEP": "EXECUTOR_MAX_PER_STEP",
    "DAG_UPDATE_INTERVAL": "DAG_UPDATE_INTERVAL",
}


def _format_heal(state: dict, subtask: str) -> str:
    b = _bot()
    st = subtask.strip().upper()
    if not st:
        return "Usage: `heal <subtask>`"
    dag = state.get("dag", {})
    found = False
    for task in dag.values():
        for branch in task.get("branches", {}).values():
            for st_name, st_data in branch.get("subtasks", {}).items():
                if st_name == st:
                    found = True
                    if st_data.get("status") != "Running":
                        return f"\u26a0\ufe0f **{st}** is {st_data.get('status', 'Pending')}, not Running \u2014 nothing to heal."
    if not found:
        return f"\u26a0\ufe0f Subtask **{st}** not found."
    b.HEAL_TRIGGER.parent.mkdir(exist_ok=True)
    b.HEAL_TRIGGER.write_text(json.dumps({"subtask": st}), encoding="utf-8")
    return f"\u21bb **{st}** heal trigger written \u2014 CLI will reset to Pending next loop."


def _format_reset_task(state: dict, task_arg: str) -> str:
    b = _bot()
    task_id = task_arg.strip()
    if not task_id:
        return "Usage: `reset_task <task_id>`"
    dag = state.get("dag", {})
    if task_id not in dag:
        return f"\u26a0\ufe0f Task **{task_id}** not found."
    task = dag[task_id]
    reset_count = 0
    skipped_count = 0
    for branch_data in task.get("branches", {}).values():
        for st_data in branch_data.get("subtasks", {}).values():
            if st_data.get("status") == "Verified":
                skipped_count += 1
            else:
                st_data["status"] = "Pending"
                st_data["output"] = ""
                st_data.pop("shadow", None)
                reset_count += 1
    task["status"] = "Pending"
    try:
        b.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"\u274c Failed to write state: {exc}"
    return (
        f"\u21ba **{task_id}** reset \u2014 {reset_count} subtask(s) \u2192 Pending"
        + (f", {skipped_count} Verified preserved." if skipped_count else ".")
    )


def _format_reset_branch(state: dict, task_arg: str, branch_arg: str) -> str:
    b = _bot()
    task_id = task_arg.strip()
    branch_id = branch_arg.strip()
    if not task_id or not branch_id:
        return "Usage: `reset_branch <task_id> <branch>`"
    dag = state.get("dag", {})
    if task_id not in dag:
        return f"\u26a0\ufe0f Task **{task_id}** not found."
    branches = dag[task_id].get("branches", {})
    if branch_id not in branches:
        return f"\u26a0\ufe0f Branch **{branch_id}** not found in task **{task_id}**."
    reset_count = 0
    skipped_count = 0
    for st_data in branches[branch_id].get("subtasks", {}).values():
        if st_data.get("status") == "Verified":
            skipped_count += 1
        else:
            st_data["status"] = "Pending"
            st_data["output"] = ""
            st_data.pop("shadow", None)
            reset_count += 1
    try:
        b.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"\u274c Failed to write state: {exc}"
    return (
        f"\u21ba **{task_id}/{branch_id}** reset \u2014 {reset_count} subtask(s) \u2192 Pending"
        + (f", {skipped_count} Verified preserved." if skipped_count else ".")
    )


def _format_bulk_reset(state: dict, names: list[str], skip_verified: bool = True) -> str:
    b = _bot()
    if not names:
        return "Usage: `bulk_reset <A1> [A2 ...]`"
    dag = state.get("dag", {})
    remaining = set(names)
    reset_names: list[str] = []
    skipped_count = 0
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_name not in remaining:
                    continue
                if skip_verified and st_data.get("status") == "Verified":
                    skipped_count += 1
                    remaining.discard(st_name)
                    continue
                st_data["status"] = "Pending"
                st_data["output"] = ""
                st_data.pop("shadow", None)
                reset_names.append(st_name)
                remaining.discard(st_name)
    try:
        b.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"\u274c Failed to write state: {exc}"
    parts = [f"\u21ba bulk-reset: **{len(reset_names)}** \u2192 Pending"]
    if skipped_count:
        parts.append(f"{skipped_count} Verified preserved")
    if remaining:
        parts.append(f"not found: {', '.join(sorted(remaining))}")
    return "  ".join(parts) + "."


def _format_bulk_verify(state: dict, names: list[str], skip_non_running: bool = False) -> str:
    b = _bot()
    if not names:
        return "Usage: `bulk_verify <A1> [A2 ...]`"
    dag = state.get("dag", {})
    remaining = set(names)
    verified_names: list[str] = []
    skipped_count = 0
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_name not in remaining:
                    continue
                current = st_data.get("status", "Pending")
                if current == "Verified":
                    skipped_count += 1
                    remaining.discard(st_name)
                    continue
                if skip_non_running and current not in ("Running", "Review"):
                    skipped_count += 1
                    remaining.discard(st_name)
                    continue
                st_data["status"] = "Verified"
                verified_names.append(st_name)
                remaining.discard(st_name)
    try:
        b.STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"\u274c Failed to write state: {exc}"
    parts = [f"\u2714 bulk-verify: **{len(verified_names)}** \u2192 Verified"]
    if skipped_count:
        parts.append(f"{skipped_count} skipped")
    if remaining:
        parts.append(f"not found: {', '.join(sorted(remaining))}")
    return "  ".join(parts) + "."


_HELP_TEXT = (
    "**Solo Builder \u2014 plain-text commands**\n"
    "`status`                           \u2014 DAG progress summary\n"
    "`run`                              \u2014 trigger one step\n"
    "`auto [n]`                         \u2014 run N steps (default: until complete)\n"
    "`stop`                             \u2014 cancel an in-progress auto run\n"
    "`verify <subtask> [note]`          \u2014 approve a Review-gated subtask\n"
    "`output <subtask>`                 \u2014 show Claude output for a subtask\n"
    "`describe <subtask> <prompt>`      \u2014 set a custom Claude prompt for a subtask\n"
    "`tools <subtask> <tool,list>`      \u2014 set allowed tools for a subtask\n"
    "`add_task <spec>`                  \u2014 queue a new task (added at next step)\n"
    "`add_branch <task> <spec>`         \u2014 queue a new branch on an existing task\n"
    "`prioritize_branch <task> <branch>` \u2014 boost a branch to front of queue\n"
    "`reset confirm`                    \u2014 reset DAG to initial state (destructive!)\n"
    "`depends [<task> <dep>]`            \u2014 add a dependency or show dep graph\n"
    "`undepends <task> <dep>`           \u2014 remove a dependency\n"
    "`set KEY=VALUE`                    \u2014 change a runtime setting\n"
    "`set KEY`                          \u2014 show current value of a setting\n"
    "`snapshot`                         \u2014 trigger a PDF snapshot\n"
    "`export`                           \u2014 download all Claude outputs\n"
    "`undo`                             \u2014 undo last step (restore from backup)\n"
    "`pause`                            \u2014 pause auto-run (resume continues)\n"
    "`resume`                           \u2014 resume a paused auto-run\n"
    "`config`                           \u2014 show all current runtime settings\n"
    "`diff`                             \u2014 show what changed since last save\n"
    "`timeline <subtask>`               \u2014 show status history timeline\n"
    "`stats`                            \u2014 per-task breakdown (verified, avg steps)\n"
    "`cache`                            \u2014 show response cache disk stats\n"
    "`cache clear`                      \u2014 show cache stats and wipe all entries\n"
    "`history [N]`                      \u2014 last N status transitions (default 20)\n"
    "`search <keyword>`                 \u2014 find subtasks by keyword\n"
    "`filter <status>`                  \u2014 show subtasks matching a status\n"
    "`subtasks [task=X] [status=Y]`     \u2014 list subtasks with optional filters\n"
    "`priority`                         \u2014 show what executes next (ranked by risk)\n"
    "`stalled`                          \u2014 show subtasks stuck longer than threshold\n"
    "`heal <subtask>`                   \u2014 reset a Running subtask to Pending\n"
    "`agents`                           \u2014 show all agent statistics\n"
    "`forecast`                         \u2014 detailed completion forecast with ETA\n"
    "`tasks`                            \u2014 per-task summary table (verified/total/status)\n"
    "`task_progress <task_id>`          \u2014 per-branch progress for a single task\n"
    "`log [subtask]`                    \u2014 show journal entries\n"
    "`graph`                            \u2014 visual ASCII DAG dependency graph\n"
    "`heartbeat`                        \u2014 live counters from step.txt\n"
    "`help`                             \u2014 this message\n\n"
    "*Slash commands (`/status`, `/run`, `/stop`, \u2026) work too.*"
)


async def _handle_text_command(message: discord.Message) -> None:
    b = _bot()
    text = message.content.strip()
    low  = text.lower()

    if low == "status":
        reply = _format_status(b._load_state())
        if b._auto_running():
            if b.PAUSE_TRIGGER.exists():
                reply += "\n\u23f8 Auto-run **paused** \u2014 use `resume` to continue."
            else:
                reply += "\n\u25b6 Auto-run in progress \u2014 use `stop` to cancel."
        await b._send(message, reply)

    elif low == "run":
        state = b._load_state()
        if not _has_work(state.get("dag", {})):
            await b._send(message, "\u2705 Pipeline already complete.")
        else:
            b.TRIGGER_PATH.parent.mkdir(exist_ok=True)
            b.TRIGGER_PATH.write_text("1")
            await b._send(message, f"\u25b6 Step triggered (step {state.get('step', 0)} \u2192 next)")

    elif low.startswith("auto"):
        if b._auto_running():
            await b._send(message, "\u26a0\ufe0f Auto already running. Use `stop` to cancel or `status` to check progress.")
            return
        rest = text[4:].strip()
        n: Optional[int] = None
        if rest.isdigit():
            n = int(rest)
        label = f"{n} steps" if n is not None else "until complete"
        b._auto_task = asyncio.create_task(b._run_auto(message.channel.id, n))
        await b._send(message, f"\u25b6 Auto-run started: {label}")

    elif low == "stop":
        if b._auto_running():
            b._auto_task.cancel()
        b.STOP_TRIGGER.parent.mkdir(exist_ok=True)
        b.STOP_TRIGGER.write_text("1")
        await b._send(message, "\u23f9 Stop signal sent \u2014 CLI will halt after the current step.")

    elif low.startswith("verify"):
        rest = text[6:].strip()
        if not rest:
            await b._send(message, "Usage: `verify <subtask> [note]`")
            return
        parts   = rest.split(" ", 1)
        subtask = parts[0].upper()
        note    = parts[1].strip() if len(parts) > 1 else "Discord verify"
        b.VERIFY_TRIGGER.parent.mkdir(exist_ok=True)
        b.VERIFY_TRIGGER.write_text(
            json.dumps({"subtask": subtask, "note": note}), encoding="utf-8"
        )
        await b._send(
            message,
            f"\u23f3 Verify queued: `{subtask}` \u2014 *{note}*\n"
            f"CLI will process it at the next step boundary."
        )

    elif low == "export":
        if not b.OUTPUTS_PATH.exists():
            await b._send(message, "No export file yet. Run `export` in the CLI first.")
        else:
            size_kb = b.OUTPUTS_PATH.stat().st_size // 1024
            await b._send(
                message,
                f"Solo Builder outputs \u00b7 {size_kb} KB",
                file=discord.File(str(b.OUTPUTS_PATH), filename="solo_builder_outputs.md"),
            )

    elif low.startswith("add_task"):
        spec = text[8:].strip()
        if not spec:
            await b._send(message, "Usage: `add_task <spec>` \u2014 e.g. `add_task Build the OAuth2 flow`")
            return
        b.ADD_TASK_TRIGGER.parent.mkdir(exist_ok=True)
        b.ADD_TASK_TRIGGER.write_text(json.dumps({"spec": spec}), encoding="utf-8")
        await b._send(
            message,
            f"\u2705 Task queued: *{spec[:80]}*\nCLI will add it at the next step boundary."
        )

    elif low.startswith("add_branch"):
        rest = text[10:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await b._send(message, "Usage: `add_branch <task> <spec>` \u2014 e.g. `add_branch 0 Add error handling`")
            return
        task_arg, spec = parts[0], parts[1].strip()
        if not spec:
            await b._send(message, "Usage: `add_branch <task> <spec>` \u2014 e.g. `add_branch 0 Add error handling`")
            return
        b.ADD_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
        b.ADD_BRANCH_TRIGGER.write_text(json.dumps({"task": task_arg, "spec": spec}), encoding="utf-8")
        await b._send(
            message,
            f"\u2705 Branch queued on Task {task_arg}: *{spec[:80]}*\nCLI will add it at the next step boundary."
        )

    elif low.startswith("output"):
        st_target = text[6:].strip().upper()
        if not st_target:
            await b._send(message, "Usage: `output <subtask>` \u2014 e.g. `output A3`")
            return
        state = b._load_state()
        result = _find_subtask_output(state, st_target)
        if result is None:
            await b._send(message, f"\u274c Subtask `{st_target}` not found.")
        else:
            task_name, out = result
            if out:
                await b._send(message, f"**{st_target}** ({task_name}):\n```\n{out[:1800]}\n```")
            else:
                await b._send(message, f"**{st_target}** ({task_name}): no output recorded yet.")

    elif low.startswith("describe"):
        rest = text[8:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await b._send(message, "Usage: `describe <subtask> <prompt>` \u2014 e.g. `describe A3 Implement retry logic`")
            return
        st_target, desc = parts[0].upper(), parts[1].strip()
        b.DESCRIBE_TRIGGER.parent.mkdir(exist_ok=True)
        b.DESCRIBE_TRIGGER.write_text(
            json.dumps({"subtask": st_target, "desc": desc}), encoding="utf-8"
        )
        await b._send(
            message,
            f"\u2705 Describe queued: `{st_target}` \u2014 *{desc[:80]}*\nCLI will apply it at the next step boundary."
        )

    elif low.startswith("tools"):
        rest = text[5:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await b._send(message, "Usage: `tools <subtask> <tool,list | none>` \u2014 e.g. `tools H1 Read,Glob,Grep`")
            return
        st_target, tool_val = parts[0].upper(), parts[1].strip()
        b.TOOLS_TRIGGER.parent.mkdir(exist_ok=True)
        b.TOOLS_TRIGGER.write_text(
            json.dumps({"subtask": st_target, "tools": tool_val}), encoding="utf-8"
        )
        label = tool_val if tool_val.lower() != "none" else "(none \u2014 headless)"
        await b._send(
            message,
            f"\u2705 Tools queued: `{st_target}` \u2192 {label}\nCLI will apply at the next step boundary."
        )

    elif low == "reset confirm":
        b.RESET_TRIGGER.parent.mkdir(exist_ok=True)
        b.RESET_TRIGGER.write_text("1")
        await b._send(message, "\u26a0\ufe0f Reset queued \u2014 CLI will clear DAG and state at the next step boundary.")

    elif low == "reset":
        await b._send(message, "\u26a0\ufe0f This will **destroy all progress**. Type `reset confirm` to proceed.")

    elif low == "snapshot":
        b.SNAPSHOT_TRIGGER.parent.mkdir(exist_ok=True)
        b.SNAPSHOT_TRIGGER.write_text("1")
        latest = None
        if b.SNAPSHOTS_DIR.is_dir():
            pdfs = sorted(b.SNAPSHOTS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                latest = pdfs[0]
        if latest:
            await b._send(
                message,
                "\ud83d\udcf8 Snapshot triggered. Latest existing PDF attached:",
                file=discord.File(str(latest), filename=latest.name),
            )
        else:
            await b._send(message, "\ud83d\udcf8 Snapshot triggered \u2014 CLI will generate a PDF at the next step boundary.")

    elif low.startswith("prioritize_branch"):
        rest = text[17:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await b._send(message, "Usage: `prioritize_branch <task> <branch>` \u2014 e.g. `prioritize_branch 0 A`")
            return
        pb_task, pb_branch = parts[0], parts[1].strip()
        b.PRIORITY_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
        b.PRIORITY_BRANCH_TRIGGER.write_text(
            json.dumps({"task": pb_task, "branch": pb_branch}), encoding="utf-8"
        )
        await b._send(
            message,
            f"\u2705 Priority boost queued: Task {pb_task} / {pb_branch}\nCLI will boost it at the next step boundary."
        )

    elif low.startswith("undepends"):
        rest = text[9:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await b._send(message, "Usage: `undepends <task> <dep>` \u2014 e.g. `undepends 1 0`")
            return
        b.UNDEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
        b.UNDEPENDS_TRIGGER.write_text(
            json.dumps({"target": parts[0], "dep": parts[1].strip()}), encoding="utf-8"
        )
        await b._send(
            message,
            f"\u2705 Undepends queued: Task {parts[0]} no longer depends on Task {parts[1].strip()}\n"
            f"CLI will apply at the next step boundary."
        )

    elif low.startswith("depends"):
        rest = text[7:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            state = b._load_state()
            dag = state.get("dag", {})
            if not dag:
                await b._send(message, "No DAG loaded.")
                return
            lines = ["**Dependency Graph**"]
            for t_name, t_data in dag.items():
                deps = t_data.get("depends_on", [])
                st = t_data.get("status", "?")
                sym = {"Verified": "\u2705", "Running": "\u25b6"}.get(st, "\u23f3")
                dep_str = f" \u2190 {', '.join(deps)}" if deps else " (root)"
                lines.append(f"{sym} {t_name}{dep_str}")
            await b._send(message, "\n".join(lines))
            return
        b.DEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
        b.DEPENDS_TRIGGER.write_text(
            json.dumps({"target": parts[0], "dep": parts[1].strip()}), encoding="utf-8"
        )
        await b._send(
            message,
            f"\u2705 Depends queued: Task {parts[0]} \u2192 Task {parts[1].strip()}\n"
            f"CLI will apply at the next step boundary."
        )

    elif low.startswith("set "):
        rest = text[4:].strip()
        if "=" in rest:
            k, v = rest.split("=", 1)
            k, v = k.strip(), v.strip()
            if not k:
                await b._send(message, "Usage: `set KEY=VALUE` or `set KEY`")
                return
            b.SET_TRIGGER.parent.mkdir(exist_ok=True)
            b.SET_TRIGGER.write_text(json.dumps({"key": k, "value": v}), encoding="utf-8")
            await b._send(message, f"\u2699\ufe0f `{k.upper()}={v}` queued \u2014 CLI will apply at the next step boundary.")
        else:
            bare = rest.upper()
            cfg_key = _KEY_MAP.get(bare)
            if not cfg_key:
                await b._send(message, f"\u274c Unknown setting `{bare}`. Known: {', '.join(sorted(_KEY_MAP))}")
                return
            try:
                cfg = json.loads(b.SETTINGS_PATH.read_text(encoding="utf-8"))
                val = cfg.get(cfg_key, "(not set)")
                await b._send(message, f"\u2699\ufe0f `{bare}` = `{val}`")
            except Exception:
                await b._send(message, "\u274c Could not read `config/settings.json`.")

    elif low == "undo":
        b.UNDO_TRIGGER.parent.mkdir(exist_ok=True)
        b.UNDO_TRIGGER.write_text("1")
        await b._send(message, "\u21a9\ufe0f Undo queued \u2014 CLI will restore from last backup at next step boundary.")

    elif low == "pause":
        if not b._auto_running():
            await b._send(message, "\u26a0\ufe0f No auto-run in progress to pause.")
            return
        b.PAUSE_TRIGGER.parent.mkdir(exist_ok=True)
        b.PAUSE_TRIGGER.write_text("1")
        hb = b._read_heartbeat()
        extra = ""
        if hb:
            step, v, t, p, r, w = hb
            pct = round(v / t * 100, 1) if t else 0
            extra = f"\nStep {step} \u2014 {v}\u2705 {r}\u25b6 {w}\u23f8 {p}\u23f3 / {t} ({pct}%)"
        await b._send(message, f"\u23f8 Pause signal sent \u2014 auto-run will pause after the current step. Use `resume` to continue.{extra}")

    elif low == "resume":
        if b.PAUSE_TRIGGER.exists():
            try:
                b.PAUSE_TRIGGER.unlink()
            except OSError:
                pass
            hb = b._read_heartbeat()
            extra = ""
            if hb:
                step, v, t, p, r, w = hb
                pct = round(v / t * 100, 1) if t else 0
                extra = f"\nStep {step} \u2014 {v}\u2705 {r}\u25b6 {w}\u23f8 {p}\u23f3 / {t} ({pct}%)"
            await b._send(message, f"\u25b6 Resumed \u2014 auto-run will continue.{extra}")
        else:
            await b._send(message, "\u26a0\ufe0f Not paused.")

    elif low == "config":
        try:
            cfg = json.loads(b.SETTINGS_PATH.read_text(encoding="utf-8"))
            lines = ["**Current Settings** (`config/settings.json`)", "```"]
            for k, v in cfg.items():
                lines.append(f"  {k:<30} = {v}")
            lines.append("```")
            await b._send(message, "\n".join(lines))
        except Exception:
            await b._send(message, "\u274c Could not read `config/settings.json`.")

    elif low == "graph":
        state = b._load_state()
        await b._send(message, _format_graph(state))

    elif low == "priority":
        state = b._load_state()
        await b._send(message, _format_priority(state))

    elif low == "stalled":
        state = b._load_state()
        await b._send(message, _format_stalled(state))

    elif low == "heal" or low.startswith("heal "):
        st_arg = text[5:].strip() if " " in text else ""
        state = b._load_state()
        await b._send(message, _format_heal(state, st_arg))

    elif low.startswith("reset_task ") or low == "reset_task":
        task_arg = text[11:].strip() if low.startswith("reset_task ") else ""
        state = b._load_state()
        await b._send(message, _format_reset_task(state, task_arg))

    elif low.startswith("reset_branch ") or low == "reset_branch":
        parts = text[13:].strip().split(None, 1) if low.startswith("reset_branch ") else []
        task_arg   = parts[0] if len(parts) > 0 else ""
        branch_arg = parts[1] if len(parts) > 1 else ""
        state = b._load_state()
        await b._send(message, _format_reset_branch(state, task_arg, branch_arg))

    elif low.startswith("bulk_reset ") or low == "bulk_reset":
        names = text[11:].strip().split() if low.startswith("bulk_reset ") else []
        state = b._load_state()
        await b._send(message, _format_bulk_reset(state, names))

    elif low.startswith("bulk_verify ") or low == "bulk_verify":
        names = text[12:].strip().split() if low.startswith("bulk_verify ") else []
        state = b._load_state()
        await b._send(message, _format_bulk_verify(state, names))

    elif low.startswith("task_progress ") or low == "task_progress":
        task_arg = text[14:].strip() if low.startswith("task_progress ") else ""
        state = b._load_state()
        await b._send(message, _format_task_progress(state, task_arg))

    elif low == "agents":
        state = b._load_state()
        await b._send(message, _format_agents(state))

    elif low == "forecast":
        state = b._load_state()
        await b._send(message, _format_forecast(state))

    elif low == "tasks":
        state = b._load_state()
        await b._send(message, _format_tasks(state))

    elif low == "diff":
        await b._send(message, _format_diff())

    elif low == "filter" or low.startswith("filter "):
        status_arg = text[7:].strip() if " " in text else ""
        state = b._load_state()
        await b._send(message, _format_filter(state, status_arg))

    elif low.startswith("timeline "):
        st = text[9:].strip()
        state = b._load_state()
        await b._send(message, _format_timeline(state, st))

    elif low == "stats":
        state = b._load_state()
        await b._send(message, _format_stats(state))

    elif low == "cache":
        await b._send(message, _format_cache(clear=False))

    elif low == "cache clear":
        await b._send(message, _format_cache(clear=True))

    elif low == "history" or low.startswith("history "):
        n = 20
        rest = text[7:].strip() if low.startswith("history ") else ""
        if rest.isdigit():
            n = int(rest)
        state = b._load_state()
        await b._send(message, _format_history(state, n))

    elif low.startswith("search "):
        q = text[7:].strip()
        state = b._load_state()
        await b._send(message, _format_search(state, q))

    elif low == "log" or low.startswith("log "):
        st = text[3:].strip() if low.startswith("log ") else ""
        await b._send(message, _format_log(st))

    elif low == "branches" or low.startswith("branches "):
        task_arg = text[9:].strip() if low.startswith("branches ") else ""
        state = b._load_state()
        await b._send(message, _format_branches(state, task_arg))

    elif low == "subtasks" or low.startswith("subtasks "):
        rest = text[8:].strip() if low.startswith("subtasks ") else ""
        task_filter = ""
        status_filter = ""
        for part in rest.split():
            if part.startswith("status="):
                status_filter = part[7:]
        if "task=" in rest:
            after = rest[rest.index("task=") + 5:]
            task_filter = after.split(" status=")[0].split(" task=")[0].strip()
        state = b._load_state()
        await b._send(message, _format_subtasks(state, task_filter, status_filter))

    elif low.startswith("rename "):
        parts = text[7:].strip().split(None, 1)
        if len(parts) < 2:
            await b._send(message, "Usage: `rename <subtask> <new description>`")
        else:
            st, desc = parts[0].strip().upper(), parts[1].strip()
            b.RENAME_TRIGGER.parent.mkdir(exist_ok=True)
            b.RENAME_TRIGGER.write_text(json.dumps({"subtask": st, "desc": desc}))
            await b._send(message, f"\u270e Rename queued: `{st}` \u2192 {desc[:80]}")

    elif low == "heartbeat":
        hb = b._read_heartbeat()
        if hb:
            step, v, tot, p, r, rv = hb
            pct = round(v / tot * 100, 1) if tot else 0
            lines = [
                f"**Heartbeat** \u00b7 Step {step}",
                f"\u2705 {v}  \u25b6 {r}  \u23f8 {rv}  \u23f3 {p} / {tot}  ({pct}%)",
            ]
            if b._auto_running():
                lines.append("\u25b6 Auto-run in progress")
            await b._send(message, "\n".join(lines))
        else:
            await b._send(message, "\u26a0\ufe0f No heartbeat \u2014 is the CLI running?")

    elif low in ("help", "?"):
        await b._send(message, _HELP_TEXT)
