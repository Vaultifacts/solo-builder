"""
Solo Builder — Slash Commands

All 39 slash commands extracted from bot.py.
Call register_slash_commands(bot) after bot = SoloBuilderBot().
All references to bot.py names go through the lazy `_b` import.
"""

import asyncio
import io
import json
from typing import Optional

import discord
from discord import app_commands


def register_slash_commands(bot: discord.Client) -> None:
    """Register all slash commands on bot.tree. Must be called after bot is created."""
    import discord_bot.bot as _b

    @bot.tree.command(name="help", description="Show available commands")
    async def help_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(
            "**Solo Builder Bot**\n\n"
            "`/status`                           — DAG progress summary\n"
            "`/run`                              — trigger one step\n"
            "`/auto [n]`                         — run N steps (default: until complete)\n"
            "`/stop`                             — cancel an in-progress auto run\n"
            "`/verify subtask [note]`            — approve a subtask (REVIEW_MODE)\n"
            "`/output subtask`                   — show Claude output for a subtask\n"
            "`/rename subtask desc`              — update a subtask's description\n"
            "`/describe subtask prompt`          — set a custom Claude prompt for a subtask\n"
            "`/tools subtask tools`              — set allowed tools for a subtask\n"
            "`/add_task spec`                    — queue a new task\n"
            "`/add_branch task spec`             — queue a new branch on a task\n"
            "`/prioritize_branch task branch`    — boost a branch to front of queue\n"
            "`/set key [value]`                  — change or query a runtime setting\n"
            "`/depends [target dep]`             — add dependency or show dep graph\n"
            "`/undepends target dep`             — remove a dependency\n"
            "`/reset confirm:yes`                — reset DAG (destructive!)\n"
            "`/snapshot`                         — trigger a PDF snapshot\n"
            "`/export`                           — download all Claude outputs\n"
            "`/undo`                             — undo last step (restore from backup)\n"
            "`/config`                           — show all current settings\n"
            "`/branches [task]`                  — list branches for a task (or overview)\n"
            "`/graph`                            — visual ASCII DAG dependency graph\n"
            "`/filter <status>`                  — show subtasks matching a status\n"
            "`/priority`                         — show what executes next (ranked by risk)\n"
            "`/stalled`                          — show subtasks stuck longer than threshold\n"
            "`/heal <subtask>`                   — reset a Running subtask to Pending\n"
            "`/agents`                           — show all agent statistics\n"
            "`/forecast`                         — detailed completion forecast with ETA\n"
            "`/tasks`                            — per-task summary table (verified/total/status)\n"
            "`/task_progress task_id`            — per-branch progress for a single task\n"
            "`/heartbeat`                        — live counters from step.txt\n"
            "`/cache [clear:yes]`                — response cache disk stats (optional wipe)\n"
            "`/help`                             — this message"
        )

    @bot.tree.command(name="status", description="DAG progress summary")
    async def status_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        msg = _b._format_status(_b._load_state())
        if _b._auto_running():
            msg += "\n▶ Auto-run in progress — use `/stop` to cancel."
        await interaction.response.send_message(msg)

    @bot.tree.command(name="undo", description="Undo last step (restore from backup)")
    async def undo_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        _b.UNDO_TRIGGER.parent.mkdir(exist_ok=True)
        _b.UNDO_TRIGGER.write_text("1")
        await interaction.response.send_message("↩️ Undo queued — CLI will restore from last backup at next step boundary.")

    @bot.tree.command(name="pause", description="Pause auto-run (resume continues from same position)")
    async def pause_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        if not _b._auto_running():
            await interaction.response.send_message("⚠️ No auto-run in progress to pause.", ephemeral=True)
            return
        _b.PAUSE_TRIGGER.parent.mkdir(exist_ok=True)
        _b.PAUSE_TRIGGER.write_text("1")
        hb = _b._read_heartbeat()
        extra = ""
        if hb:
            step, v, t, p, r, w = hb
            pct = round(v / t * 100, 1) if t else 0
            extra = f"\nStep {step} — {v}✅ {r}▶ {w}⏸ {p}⏳ / {t} ({pct}%)"
        await interaction.response.send_message(f"⏸ Pause signal sent — auto-run will pause after the current step. Use `/resume` to continue.{extra}")

    @bot.tree.command(name="resume", description="Resume a paused auto-run")
    async def resume_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        if _b.PAUSE_TRIGGER.exists():
            try:
                _b.PAUSE_TRIGGER.unlink()
            except OSError:
                pass
            hb = _b._read_heartbeat()
            extra = ""
            if hb:
                step, v, t, p, r, w = hb
                pct = round(v / t * 100, 1) if t else 0
                extra = f"\nStep {step} — {v}✅ {r}▶ {w}⏸ {p}⏳ / {t} ({pct}%)"
            await interaction.response.send_message(f"▶ Resumed — auto-run will continue.{extra}")
        else:
            await interaction.response.send_message("⚠️ Not paused.", ephemeral=True)

    @bot.tree.command(name="config", description="Show all current runtime settings")
    async def config_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        try:
            cfg = json.loads(_b.SETTINGS_PATH.read_text(encoding="utf-8"))
            lines = ["**Current Settings** (`config/settings.json`)", "```"]
            for k, v in cfg.items():
                lines.append(f"  {k:<30} = {v}")
            lines.append("```")
            await interaction.response.send_message("\n".join(lines))
        except Exception:
            await interaction.response.send_message("❌ Could not read `config/settings.json`.")

    @bot.tree.command(name="stats", description="Per-task breakdown (verified, avg steps)")
    async def stats_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_stats(_b._load_state()))

    @bot.tree.command(name="cache", description="Show response cache disk stats (optional clear)")
    @app_commands.describe(clear="Pass 'yes' to wipe all cached entries after printing stats")
    async def cache_cmd(interaction: discord.Interaction, clear: str = "") -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_cache(clear=clear.strip().lower() == "yes"))

    @bot.tree.command(name="tasks", description="Per-task summary table (verified/total/status)")
    async def tasks_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_tasks(_b._load_state()))

    @bot.tree.command(name="log", description="Show journal entries (optionally for one subtask)")
    @app_commands.describe(subtask="Optional subtask name to filter by (e.g. A1)")
    async def log_cmd(interaction: discord.Interaction, subtask: str = "") -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_log(subtask))

    @bot.tree.command(name="search", description="Find subtasks by keyword in name/description/output")
    @app_commands.describe(query="Keyword to search for")
    async def search_cmd(interaction: discord.Interaction, query: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_search(_b._load_state(), query))

    @bot.tree.command(name="filter", description="Show subtasks matching a status (Verified/Running/Pending/Review)")
    @app_commands.describe(status="Status to filter by (Verified, Running, Pending, or Review)")
    async def filter_cmd(interaction: discord.Interaction, status: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_filter(_b._load_state(), status))

    @bot.tree.command(name="priority", description="Show which subtasks execute next (ranked by risk)")
    async def priority_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_priority(_b._load_state()))

    @bot.tree.command(name="stalled", description="Show subtasks stuck longer than STALL_THRESHOLD")
    async def stalled_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_stalled(_b._load_state()))

    @bot.tree.command(name="heal", description="Reset a Running subtask to Pending")
    @app_commands.describe(subtask="Subtask name (e.g. A1)")
    async def heal_cmd(interaction: discord.Interaction, subtask: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_heal(_b._load_state(), subtask))

    @bot.tree.command(name="reset_task", description="Bulk-reset all non-Verified subtasks in a task to Pending")
    @app_commands.describe(task="Task ID (e.g. Task 0)")
    async def reset_task_cmd(interaction: discord.Interaction, task: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_reset_task(_b._load_state(), task))

    @bot.tree.command(name="reset_branch", description="Bulk-reset all non-Verified subtasks in a branch to Pending")
    @app_commands.describe(task="Task ID (e.g. Task 0)", branch="Branch name (e.g. Branch A)")
    async def reset_branch_cmd(interaction: discord.Interaction, task: str, branch: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_reset_branch(_b._load_state(), task, branch))

    @bot.tree.command(name="bulk_reset", description="Reset multiple named subtasks to Pending in one command")
    @app_commands.describe(subtasks="Space-separated subtask names (e.g. A1 A2 B3)")
    async def bulk_reset_cmd(interaction: discord.Interaction, subtasks: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        names = subtasks.strip().split()
        await interaction.response.send_message(_b._format_bulk_reset(_b._load_state(), names))

    @bot.tree.command(name="bulk_verify", description="Advance multiple named subtasks to Verified in one command")
    @app_commands.describe(subtasks="Space-separated subtask names (e.g. A1 A2 B3)")
    async def bulk_verify_cmd(interaction: discord.Interaction, subtasks: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        names = subtasks.strip().split()
        await interaction.response.send_message(_b._format_bulk_verify(_b._load_state(), names))

    @bot.tree.command(name="task_progress", description="Per-branch progress summary for a task")
    @app_commands.describe(task_id="Task ID to inspect (e.g. TASK-001)")
    async def task_progress_cmd(interaction: discord.Interaction, task_id: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_task_progress(_b._load_state(), task_id))

    @bot.tree.command(name="agents", description="Show all agent statistics")
    async def agents_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_agents(_b._load_state()))

    @bot.tree.command(name="forecast", description="Detailed completion forecast with ETA")
    async def forecast_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_forecast(_b._load_state()))

    @bot.tree.command(name="history", description="Show recent status transitions across all subtasks")
    @app_commands.describe(limit="Number of entries to show (default 20)")
    async def history_cmd(interaction: discord.Interaction, limit: int = 20) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_history(_b._load_state(), limit))

    @bot.tree.command(name="branches", description="List branches for a task with subtask counts")
    @app_commands.describe(
        task="Task name or number (e.g. 0, Task 0). Omit for overview.",
        export="Send as CSV file attachment instead of text",
    )
    async def branches_cmd(
        interaction: discord.Interaction, task: str = "", export: bool = False
    ) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        state = _b._load_state()
        if export:
            csv_bytes = _b._branches_to_csv(state)
            await interaction.response.send_message(
                "📊 Branches export",
                file=discord.File(io.BytesIO(csv_bytes), filename="branches.csv"),
            )
        else:
            await interaction.response.send_message(_b._format_branches(state, task))

    @bot.tree.command(name="subtasks", description="List subtasks with optional task and status filters")
    @app_commands.describe(
        task="Filter by task name substring (case-insensitive). Omit for all tasks.",
        status="Filter by status: Pending, Running, Review, Verified",
        export="Send as CSV file attachment instead of text",
    )
    async def subtasks_cmd(
        interaction: discord.Interaction, task: str = "", status: str = "", export: bool = False
    ) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        state = _b._load_state()
        if export:
            csv_bytes = _b._subtasks_to_csv(state, task, status)
            await interaction.response.send_message(
                "📊 Subtasks export",
                file=discord.File(io.BytesIO(csv_bytes), filename="subtasks.csv"),
            )
        else:
            await interaction.response.send_message(_b._format_subtasks(state, task, status))

    @bot.tree.command(name="rename", description="Update a subtask's description")
    @app_commands.describe(subtask="Subtask name (e.g. A1)", description="New description text")
    async def rename_cmd(interaction: discord.Interaction, subtask: str, description: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        st = subtask.strip().upper()
        _b.RENAME_TRIGGER.parent.mkdir(exist_ok=True)
        _b.RENAME_TRIGGER.write_text(json.dumps({"subtask": st, "desc": description.strip()}))
        await interaction.response.send_message(f"✎ Rename queued: `{st}` → {description.strip()[:80]}")

    @bot.tree.command(name="graph", description="Visual ASCII DAG dependency graph")
    async def graph_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_graph(_b._load_state()))

    @bot.tree.command(name="diff", description="Show what changed since last save")
    async def diff_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_diff())

    @bot.tree.command(name="timeline", description="Show status history timeline for a subtask")
    @app_commands.describe(subtask="Subtask name (e.g. A1)")
    async def timeline_cmd(interaction: discord.Interaction, subtask: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        await interaction.response.send_message(_b._format_timeline(_b._load_state(), subtask))

    @bot.tree.command(name="heartbeat", description="Show live heartbeat counters from step.txt")
    async def heartbeat_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        hb = _b._read_heartbeat()
        if hb:
            step, v, tot, p, r, rv = hb
            pct = round(v / tot * 100, 1) if tot else 0
            lines = [
                f"**Heartbeat** · Step {step}",
                f"✅ {v}  ▶ {r}  ⏸ {rv}  ⏳ {p} / {tot}  ({pct}%)",
            ]
            if _b._auto_running():
                lines.append("▶ Auto-run in progress")
            await interaction.response.send_message("\n".join(lines))
        else:
            await interaction.response.send_message("⚠️ No heartbeat — is the CLI running?")

    @bot.tree.command(name="run", description="Trigger one CLI step")
    async def run_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        state = _b._load_state()
        if not _b._has_work(state.get("dag", {})):
            await interaction.response.send_message("✅ Pipeline already complete.")
            return
        _b.TRIGGER_PATH.parent.mkdir(exist_ok=True)
        _b.TRIGGER_PATH.write_text("1")
        await interaction.response.send_message(
            f"▶ Step triggered (step {state.get('step', 0)} → next)"
        )

    @bot.tree.command(name="verify", description="Approve a Review-gated subtask")
    @app_commands.describe(
        subtask="Subtask name (e.g. A3)",
        note="Optional review note",
    )
    async def verify_cmd(
        interaction: discord.Interaction,
        subtask: str,
        note: str = "Discord verify",
    ) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        _b.VERIFY_TRIGGER.parent.mkdir(exist_ok=True)
        _b.VERIFY_TRIGGER.write_text(
            json.dumps({"subtask": subtask.upper(), "note": note}), encoding="utf-8"
        )
        await interaction.response.send_message(
            f"⏳ Verify queued: `{subtask.upper()}` — *{note}*\n"
            f"CLI will process it at the next step boundary."
        )

    @bot.tree.command(name="auto", description="Run steps automatically")
    @app_commands.describe(n="Number of steps (omit for full run)")
    async def auto_cmd(interaction: discord.Interaction, n: Optional[int] = None) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        if _b._auto_running():
            await interaction.response.send_message(
                "⚠️ Auto already running. Use `/stop` to cancel or `/status` to check progress.",
                ephemeral=True,
            )
            return
        label = f"{n} steps" if n is not None else "until complete"
        _b._auto_task = asyncio.create_task(_b._run_auto(interaction.channel_id, n))
        await interaction.response.send_message(
            f"▶ Auto-run started: {label}\nUse `/status` for progress."
        )

    @bot.tree.command(name="stop", description="Cancel an in-progress auto run")
    async def stop_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        if _b._auto_running():
            _b._auto_task.cancel()
        _b.STOP_TRIGGER.parent.mkdir(exist_ok=True)
        _b.STOP_TRIGGER.write_text("1")
        await interaction.response.send_message(
            "⏹ Stop signal sent — CLI will halt after the current step."
        )

    @bot.tree.command(name="export", description="Download all Claude outputs as Markdown")
    async def export_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        if not _b.OUTPUTS_PATH.exists():
            await interaction.response.send_message(
                "No export file yet. Run `export` in the CLI first."
            )
            return
        size_kb = _b.OUTPUTS_PATH.stat().st_size // 1024
        await interaction.response.send_message(
            f"Solo Builder outputs · {size_kb} KB",
            file=discord.File(str(_b.OUTPUTS_PATH), filename="solo_builder_outputs.md"),
        )

    @bot.tree.command(name="add_task", description="Queue a new task to be added at the next step")
    @app_commands.describe(spec="What the task should accomplish")
    async def add_task_cmd(interaction: discord.Interaction, spec: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        spec = spec.strip()
        if not spec:
            await interaction.response.send_message("Usage: `/add_task <spec>`", ephemeral=True)
            return
        _b.ADD_TASK_TRIGGER.parent.mkdir(exist_ok=True)
        _b.ADD_TASK_TRIGGER.write_text(json.dumps({"spec": spec}), encoding="utf-8")
        await interaction.response.send_message(
            f"✅ Task queued: *{spec[:80]}*\nCLI will add it at the next step boundary."
        )

    @bot.tree.command(name="add_branch", description="Queue a new branch on an existing task")
    @app_commands.describe(task="Task number or name (e.g. 0 or Task 0)", spec="What the branch should cover")
    async def add_branch_cmd(interaction: discord.Interaction, task: str, spec: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        task = task.strip()
        spec = spec.strip()
        if not task or not spec:
            await interaction.response.send_message("Usage: `/add_branch <task> <spec>`", ephemeral=True)
            return
        _b.ADD_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
        _b.ADD_BRANCH_TRIGGER.write_text(json.dumps({"task": task, "spec": spec}), encoding="utf-8")
        await interaction.response.send_message(
            f"✅ Branch queued on Task {task}: *{spec[:80]}*\nCLI will add it at the next step boundary."
        )

    @bot.tree.command(name="output", description="Show Claude output for a specific subtask")
    @app_commands.describe(subtask="Subtask name (e.g. A3)")
    async def output_cmd(interaction: discord.Interaction, subtask: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        st_target = subtask.strip().upper()
        if not st_target:
            await interaction.response.send_message("Usage: `/output <subtask>`", ephemeral=True)
            return
        state = _b._load_state()
        result = _b._find_subtask_output(state, st_target)
        if result is None:
            await interaction.response.send_message(f"❌ Subtask `{st_target}` not found.")
        else:
            task_name, out = result
            if out:
                await interaction.response.send_message(
                    f"**{st_target}** ({task_name}):\n```\n{out[:1800]}\n```"
                )
            else:
                await interaction.response.send_message(
                    f"**{st_target}** ({task_name}): no output recorded yet."
                )

    @bot.tree.command(name="describe", description="Set a custom Claude prompt for a subtask")
    @app_commands.describe(subtask="Subtask name (e.g. A3)", prompt="The custom description/prompt to assign")
    async def describe_cmd(interaction: discord.Interaction, subtask: str, prompt: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        st_target = subtask.strip().upper()
        prompt    = prompt.strip()
        if not st_target or not prompt:
            await interaction.response.send_message("Usage: `/describe <subtask> <prompt>`", ephemeral=True)
            return
        _b.DESCRIBE_TRIGGER.parent.mkdir(exist_ok=True)
        _b.DESCRIBE_TRIGGER.write_text(
            json.dumps({"subtask": st_target, "desc": prompt}), encoding="utf-8"
        )
        await interaction.response.send_message(
            f"✅ Describe queued: `{st_target}` — *{prompt[:80]}*\nCLI will apply it at the next step boundary."
        )

    @bot.tree.command(name="tools", description="Set allowed tools for a subtask")
    @app_commands.describe(subtask="Subtask name (e.g. H1)", tools="Comma-separated tools (e.g. Read,Glob,Grep) or 'none'")
    async def tools_cmd(interaction: discord.Interaction, subtask: str, tools: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        st_target = subtask.strip().upper()
        tool_val  = tools.strip()
        if not st_target or not tool_val:
            await interaction.response.send_message("Usage: `/tools <subtask> <tool,list>`", ephemeral=True)
            return
        _b.TOOLS_TRIGGER.parent.mkdir(exist_ok=True)
        _b.TOOLS_TRIGGER.write_text(
            json.dumps({"subtask": st_target, "tools": tool_val}), encoding="utf-8"
        )
        label = tool_val if tool_val.lower() != "none" else "(none — headless)"
        await interaction.response.send_message(
            f"✅ Tools queued: `{st_target}` → {label}\nCLI will apply at the next step boundary."
        )

    @bot.tree.command(name="reset", description="Reset DAG to initial state (destructive!)")
    @app_commands.describe(confirm="Type 'yes' to confirm the reset")
    async def reset_cmd(interaction: discord.Interaction, confirm: str = "") -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        if confirm.strip().lower() not in ("yes", "confirm"):
            await interaction.response.send_message(
                "⚠️ This will **destroy all progress**. Use `/reset confirm:yes` to proceed.",
                ephemeral=True,
            )
            return
        _b.RESET_TRIGGER.parent.mkdir(exist_ok=True)
        _b.RESET_TRIGGER.write_text("1")
        await interaction.response.send_message(
            "⚠️ Reset queued — CLI will clear DAG and state at the next step boundary."
        )

    @bot.tree.command(name="snapshot", description="Trigger a PDF timeline snapshot")
    async def snapshot_cmd(interaction: discord.Interaction) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        _b.SNAPSHOT_TRIGGER.parent.mkdir(exist_ok=True)
        _b.SNAPSHOT_TRIGGER.write_text("1")
        latest = None
        if _b.SNAPSHOTS_DIR.is_dir():
            pdfs = sorted(_b.SNAPSHOTS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                latest = pdfs[0]
        if latest:
            await interaction.response.send_message(
                "📸 Snapshot triggered. Latest existing PDF attached:",
                file=discord.File(str(latest), filename=latest.name),
            )
        else:
            await interaction.response.send_message(
                "📸 Snapshot triggered — CLI will generate a PDF at the next step boundary."
            )

    @bot.tree.command(name="prioritize_branch", description="Boost a branch to the front of the execution queue")
    @app_commands.describe(task="Task number or name (e.g. 0)", branch="Branch name (e.g. A)")
    async def prioritize_branch_cmd(interaction: discord.Interaction, task: str, branch: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        task   = task.strip()
        branch = branch.strip()
        if not task or not branch:
            await interaction.response.send_message("Usage: `/prioritize_branch <task> <branch>`", ephemeral=True)
            return
        _b.PRIORITY_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
        _b.PRIORITY_BRANCH_TRIGGER.write_text(
            json.dumps({"task": task, "branch": branch}), encoding="utf-8"
        )
        await interaction.response.send_message(
            f"✅ Priority boost queued: Task {task} / {branch}\nCLI will boost it at the next step boundary."
        )

    @bot.tree.command(name="set", description="Change or query a runtime setting")
    @app_commands.describe(
        key="Setting name (e.g. REVIEW_MODE, ANTHROPIC_MAX_TOKENS)",
        value="New value (omit to show current value)",
    )
    async def set_cmd(interaction: discord.Interaction, key: str, value: str = "") -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        key = key.strip().upper()
        if value:
            _b.SET_TRIGGER.parent.mkdir(exist_ok=True)
            _b.SET_TRIGGER.write_text(json.dumps({"key": key, "value": value.strip()}), encoding="utf-8")
            await interaction.response.send_message(
                f"⚙️ `{key}={value.strip()}` queued — CLI will apply at the next step boundary."
            )
        else:
            cfg_key = _b._KEY_MAP.get(key)
            if not cfg_key:
                await interaction.response.send_message(
                    f"❌ Unknown setting `{key}`. Known: {', '.join(sorted(_b._KEY_MAP))}",
                    ephemeral=True,
                )
                return
            try:
                cfg = json.loads(_b.SETTINGS_PATH.read_text(encoding="utf-8"))
                val = cfg.get(cfg_key, "(not set)")
                await interaction.response.send_message(f"⚙️ `{key}` = `{val}`")
            except Exception:
                await interaction.response.send_message("❌ Could not read `config/settings.json`.", ephemeral=True)

    @bot.tree.command(name="depends", description="Add a task dependency or show the dep graph")
    @app_commands.describe(
        target="Task to add dependency to (e.g. 1). Omit both to show the graph.",
        dep="Task it should depend on (e.g. 0). Omit both to show the graph.",
    )
    async def depends_cmd(interaction: discord.Interaction, target: str = "", dep: str = "") -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        target, dep = target.strip(), dep.strip()
        if not target or not dep:
            state = _b._load_state()
            dag = state.get("dag", {})
            if not dag:
                await interaction.response.send_message("No DAG loaded.")
                return
            lines = ["**Dependency Graph**"]
            for t_name, t_data in dag.items():
                deps = t_data.get("depends_on", [])
                st = t_data.get("status", "?")
                sym = {"Verified": "✅", "Running": "▶"}.get(st, "⏳")
                dep_str = f" ← {', '.join(deps)}" if deps else " (root)"
                lines.append(f"{sym} {t_name}{dep_str}")
            await interaction.response.send_message("\n".join(lines))
            return
        _b.DEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
        _b.DEPENDS_TRIGGER.write_text(
            json.dumps({"target": target, "dep": dep}), encoding="utf-8"
        )
        await interaction.response.send_message(
            f"✅ Depends queued: Task {target} → Task {dep}\nCLI will apply at the next step boundary."
        )

    @bot.tree.command(name="undepends", description="Remove a task dependency")
    @app_commands.describe(
        target="Task to remove dependency from (e.g. 1)",
        dep="Dependency to remove (e.g. 0)",
    )
    async def undepends_cmd(interaction: discord.Interaction, target: str, dep: str) -> None:
        if not _b._allowed(interaction):
            await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
            return
        target, dep = target.strip(), dep.strip()
        if not target or not dep:
            await interaction.response.send_message(
                "Usage: `/undepends <task> <dep>`", ephemeral=True
            )
            return
        _b.UNDEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
        _b.UNDEPENDS_TRIGGER.write_text(
            json.dumps({"target": target, "dep": dep}), encoding="utf-8"
        )
        await interaction.response.send_message(
            f"✅ Undepends queued: Task {target} no longer depends on Task {dep}\n"
            f"CLI will apply at the next step boundary."
        )
