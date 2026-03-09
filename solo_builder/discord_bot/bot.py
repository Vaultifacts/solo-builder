#!/usr/bin/env python3
"""
Solo Builder — Discord Bot

Slash commands:
  /status            — DAG progress summary
  /run               — trigger one step
  /auto [n]          — run N steps automatically (default: until complete)
  /verify subtask [note] — approve a Review-gated subtask (REVIEW_MODE)
  /export            — download all Claude outputs as a file
  /help              — command list

Also sends a completion notification to DISCORD_CHANNEL_ID when all
subtasks reach Verified.

Setup:
  pip install "discord.py>=2.0"

  1. Go to https://discord.com/developers/applications
  2. New Application → Bot → Reset Token → copy token
  3. Bot settings: disable "Public Bot", enable no privileged intents needed
  4. OAuth2 → URL Generator → scopes: bot + applications.commands
     permissions: Send Messages, Attach Files → copy URL → invite to server
  5. Add to .env:
       DISCORD_BOT_TOKEN=<token>
       DISCORD_CHANNEL_ID=<channel ID>   # optional: restrict to one channel

Run (Terminal 3):
  cd solo_builder
  python discord_bot/bot.py
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import discord
from discord import app_commands

_ROOT          = Path(__file__).resolve().parent.parent   # solo_builder/
STATE_PATH     = _ROOT / "state" / "solo_builder_state.json"
STEP_PATH      = _ROOT / "state" / "step.txt"
TRIGGER_PATH   = _ROOT / "state" / "run_trigger"
VERIFY_TRIGGER   = _ROOT / "state" / "verify_trigger.json"
STOP_TRIGGER     = _ROOT / "state" / "stop_trigger"
ADD_TASK_TRIGGER        = _ROOT / "state" / "add_task_trigger.json"
ADD_BRANCH_TRIGGER      = _ROOT / "state" / "add_branch_trigger.json"
PRIORITY_BRANCH_TRIGGER = _ROOT / "state" / "prioritize_branch_trigger.json"
DESCRIBE_TRIGGER        = _ROOT / "state" / "describe_trigger.json"
TOOLS_TRIGGER           = _ROOT / "state" / "tools_trigger.json"
RESET_TRIGGER           = _ROOT / "state" / "reset_trigger"
SNAPSHOT_TRIGGER        = _ROOT / "state" / "snapshot_trigger"
SET_TRIGGER             = _ROOT / "state" / "set_trigger.json"
DEPENDS_TRIGGER         = _ROOT / "state" / "depends_trigger.json"
UNDEPENDS_TRIGGER       = _ROOT / "state" / "undepends_trigger.json"
UNDO_TRIGGER            = _ROOT / "state" / "undo_trigger"
RENAME_TRIGGER          = _ROOT / "state" / "rename_trigger.json"
PAUSE_TRIGGER           = _ROOT / "state" / "pause_trigger"
HEAL_TRIGGER            = _ROOT / "state" / "heal_trigger.json"
SNAPSHOTS_DIR           = _ROOT / "snapshots"
SETTINGS_PATH  = _ROOT / "config" / "settings.json"
JOURNAL_PATH   = _ROOT / "journal.md"
OUTPUTS_PATH   = _ROOT / "solo_builder_outputs.md"

TOKEN      = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0") or "0")

# ---------------------------------------------------------------------------
# Formatters (extracted to bot_formatters.py; re-exported for test patching)
# ---------------------------------------------------------------------------

from .bot_formatters import (
    _has_work, _find_subtask_output,
    _format_log, _format_search, _format_branches, _format_history,
    _format_stats, _format_cache, _format_tasks, _format_task_progress,
    _format_priority, _format_stalled, _format_agents, _format_forecast,
    _format_filter, _format_timeline, _format_diff, _format_status, _format_graph,
)

# Settings key map (hoisted from _handle_text_command to avoid duplication)
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dag": {}, "step": 0}


def _format_heal(state: dict, subtask: str) -> str:
    """Validate and write heal_trigger.json to reset a Running subtask."""
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
                        return f"⚠️ **{st}** is {st_data.get('status', 'Pending')}, not Running — nothing to heal."
    if not found:
        return f"⚠️ Subtask **{st}** not found."
    HEAL_TRIGGER.parent.mkdir(exist_ok=True)
    HEAL_TRIGGER.write_text(json.dumps({"subtask": st}), encoding="utf-8")
    return f"↻ **{st}** heal trigger written — CLI will reset to Pending next loop."


def _format_reset_task(state: dict, task_arg: str) -> str:
    """Bulk-reset all non-Verified subtasks in a task to Pending (writes STATE.json directly)."""
    task_id = task_arg.strip()
    if not task_id:
        return "Usage: `reset_task <task_id>`"
    dag = state.get("dag", {})
    if task_id not in dag:
        return f"⚠️ Task **{task_id}** not found."
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
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"❌ Failed to write state: {exc}"
    return (
        f"↺ **{task_id}** reset — {reset_count} subtask(s) → Pending"
        + (f", {skipped_count} Verified preserved." if skipped_count else ".")
    )


def _format_reset_branch(state: dict, task_arg: str, branch_arg: str) -> str:
    """Bulk-reset all non-Verified subtasks in a branch to Pending (writes STATE.json directly)."""
    task_id = task_arg.strip()
    branch_id = branch_arg.strip()
    if not task_id or not branch_id:
        return "Usage: `reset_branch <task_id> <branch>`"
    dag = state.get("dag", {})
    if task_id not in dag:
        return f"⚠️ Task **{task_id}** not found."
    branches = dag[task_id].get("branches", {})
    if branch_id not in branches:
        return f"⚠️ Branch **{branch_id}** not found in task **{task_id}**."
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
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"❌ Failed to write state: {exc}"
    return (
        f"↺ **{task_id}/{branch_id}** reset — {reset_count} subtask(s) → Pending"
        + (f", {skipped_count} Verified preserved." if skipped_count else ".")
    )


def _format_bulk_reset(state: dict, names: list[str], skip_verified: bool = True) -> str:
    """Bulk-reset named subtasks to Pending (writes STATE.json directly)."""
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
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"❌ Failed to write state: {exc}"
    parts = [f"↺ bulk-reset: **{len(reset_names)}** → Pending"]
    if skipped_count:
        parts.append(f"{skipped_count} Verified preserved")
    if remaining:
        parts.append(f"not found: {', '.join(sorted(remaining))}")
    return "  ".join(parts) + "."


def _format_bulk_verify(state: dict, names: list[str], skip_non_running: bool = False) -> str:
    """Bulk-advance named subtasks to Verified (writes STATE.json directly)."""
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
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        return f"❌ Failed to write state: {exc}"
    parts = [f"✔ bulk-verify: **{len(verified_names)}** → Verified"]
    if skipped_count:
        parts.append(f"{skipped_count} skipped")
    if remaining:
        parts.append(f"not found: {', '.join(sorted(remaining))}")
    return "  ".join(parts) + "."


def _allowed(interaction: discord.Interaction) -> bool:
    return not CHANNEL_ID or interaction.channel_id == CHANNEL_ID


async def _get_channel(channel_id: int) -> discord.abc.Messageable | None:
    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except Exception:
            ch = None
    return ch


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

LOG_PATH = _ROOT / "discord_bot" / "chat.log"


def _log(channel: str, author: str, text: str) -> None:
    from datetime import datetime, timezone
    line = (
        f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] "
        f"#{channel} {author}: {text}\n"
    )
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)


class SoloBuilderBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        self.loop.create_task(_poll_completion(self))

    async def on_ready(self) -> None:
        print(f"Solo Builder Bot ready · logged in as {self.user}", flush=True)
        print(f"Slash commands synced. Invite URL scope: bot+applications.commands", flush=True)

    async def on_message(self, message: discord.Message) -> None:
        if CHANNEL_ID and message.channel.id != CHANNEL_ID:
            return
        if message.author == self.user:
            return

        _log(str(message.channel), str(message.author), message.content)

        # Natural language command parsing (no slash needed)
        await _handle_text_command(message)

    async def on_error(self, event: str, *args, **kwargs) -> None:
        import traceback
        _log("BOT", "ERROR", f"Event {event}: {traceback.format_exc()[:300]}")


bot = SoloBuilderBot()


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    """Global slash command error handler — catches rate limits and unknown errors."""
    import traceback
    if isinstance(error, app_commands.CommandInvokeError):
        cause = error.original
        if isinstance(cause, discord.errors.HTTPException) and cause.status == 429:
            retry = getattr(cause, "retry_after", 5)
            msg = f"⏱ Rate limited by Discord — retry in {retry:.1f}s."
        else:
            msg = f"⚠ Command error: {str(cause)[:200]}"
        _log("BOT", "ERROR", msg)
    else:
        msg = f"⚠ {str(error)[:200]}"
        _log("BOT", "ERROR", msg)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

# Running auto-task reference — prevents duplicate concurrent runs
_auto_task: Optional[asyncio.Task] = None


def _auto_running() -> bool:
    return _auto_task is not None and not _auto_task.done()


# ---------------------------------------------------------------------------
# Natural language command handler
# ---------------------------------------------------------------------------

_HELP_TEXT = (
    "**Solo Builder — plain-text commands**\n"
    "`status`                           — DAG progress summary\n"
    "`run`                              — trigger one step\n"
    "`auto [n]`                         — run N steps (default: until complete)\n"
    "`stop`                             — cancel an in-progress auto run\n"
    "`verify <subtask> [note]`          — approve a Review-gated subtask\n"
    "`output <subtask>`                 — show Claude output for a subtask\n"
    "`describe <subtask> <prompt>`      — set a custom Claude prompt for a subtask\n"
    "`tools <subtask> <tool,list>`      — set allowed tools for a subtask\n"
    "`add_task <spec>`                  — queue a new task (added at next step)\n"
    "`add_branch <task> <spec>`         — queue a new branch on an existing task\n"
    "`prioritize_branch <task> <branch>` — boost a branch to front of queue\n"
    "`reset confirm`                    — reset DAG to initial state (destructive!)\n"
    "`depends [<task> <dep>]`            — add a dependency or show dep graph\n"
    "`undepends <task> <dep>`           — remove a dependency\n"
    "`set KEY=VALUE`                    — change a runtime setting\n"
    "`set KEY`                          — show current value of a setting\n"
    "`snapshot`                         — trigger a PDF snapshot\n"
    "`export`                           — download all Claude outputs\n"
    "`undo`                             — undo last step (restore from backup)\n"
    "`pause`                            — pause auto-run (resume continues)\n"
    "`resume`                           — resume a paused auto-run\n"
    "`config`                           — show all current runtime settings\n"
    "`diff`                             — show what changed since last save\n"
    "`timeline <subtask>`               — show status history timeline\n"
    "`stats`                            — per-task breakdown (verified, avg steps)\n"
    "`cache`                            — show response cache disk stats\n"
    "`cache clear`                      — show cache stats and wipe all entries\n"
    "`history [N]`                      — last N status transitions (default 20)\n"
    "`search <keyword>`                 — find subtasks by keyword\n"
    "`filter <status>`                  — show subtasks matching a status\n"
    "`priority`                         — show what executes next (ranked by risk)\n"
    "`stalled`                          — show subtasks stuck longer than threshold\n"
    "`heal <subtask>`                   — reset a Running subtask to Pending\n"
    "`agents`                           — show all agent statistics\n"
    "`forecast`                         — detailed completion forecast with ETA\n"
    "`tasks`                            — per-task summary table (verified/total/status)\n"
    "`task_progress <task_id>`          — per-branch progress for a single task\n"
    "`log [subtask]`                    — show journal entries\n"
    "`graph`                            — visual ASCII DAG dependency graph\n"
    "`heartbeat`                        — live counters from step.txt\n"
    "`help`                             — this message\n\n"
    "*Slash commands (`/status`, `/run`, `/stop`, …) work too.*"
)


async def _send(message: discord.Message, text: str, **kwargs) -> None:
    """Send a reply, chunking at 1950 chars if needed to avoid Discord 2000-char limit.
    Retries once on rate limit (HTTP 429)."""
    _log(str(message.channel), "BOT", text[:200])
    chunks = []
    if len(text) <= 1950:
        chunks = [text]
    else:
        # Split on newlines to preserve code block integrity
        current: list = []
        for line in text.splitlines(keepends=True):
            if sum(len(l) for l in current) + len(line) > 1950:
                if current:
                    chunks.append("".join(current))
                    current = []
            current.append(line)
        if current:
            chunks.append("".join(current))
    for i, chunk in enumerate(chunks):
        kw = kwargs if i == len(chunks) - 1 else {}
        for attempt in range(2):
            try:
                await message.channel.send(chunk, **kw)
                break
            except discord.errors.HTTPException as e:
                if e.status == 429 and attempt == 0:
                    await asyncio.sleep(getattr(e, "retry_after", 5))
                else:
                    raise


async def _handle_text_command(message: discord.Message) -> None:
    text = message.content.strip()
    low  = text.lower()

    if low == "status":
        reply = _format_status(_load_state())
        if _auto_running():
            if PAUSE_TRIGGER.exists():
                reply += "\n⏸ Auto-run **paused** — use `resume` to continue."
            else:
                reply += "\n▶ Auto-run in progress — use `stop` to cancel."
        await _send(message, reply)

    elif low == "run":
        state = _load_state()
        if not _has_work(state.get("dag", {})):
            await _send(message, "✅ Pipeline already complete.")
        else:
            TRIGGER_PATH.parent.mkdir(exist_ok=True)
            TRIGGER_PATH.write_text("1")
            await _send(message, f"▶ Step triggered (step {state.get('step', 0)} → next)")

    elif low.startswith("auto"):
        if _auto_running():
            await _send(message, "⚠️ Auto already running. Use `stop` to cancel or `status` to check progress.")
            return
        rest = text[4:].strip()
        n: Optional[int] = None
        if rest.isdigit():
            n = int(rest)
        label = f"{n} steps" if n is not None else "until complete"
        global _auto_task
        _auto_task = asyncio.create_task(_run_auto(message.channel.id, n))
        await _send(message, f"▶ Auto-run started: {label}")

    elif low == "stop":
        if _auto_running():
            _auto_task.cancel()
        STOP_TRIGGER.parent.mkdir(exist_ok=True)
        STOP_TRIGGER.write_text("1")
        await _send(message, "⏹ Stop signal sent — CLI will halt after the current step.")

    elif low.startswith("verify"):
        rest = text[6:].strip()
        if not rest:
            await _send(message, "Usage: `verify <subtask> [note]`")
            return
        parts   = rest.split(" ", 1)
        subtask = parts[0].upper()
        note    = parts[1].strip() if len(parts) > 1 else "Discord verify"
        VERIFY_TRIGGER.parent.mkdir(exist_ok=True)
        VERIFY_TRIGGER.write_text(
            json.dumps({"subtask": subtask, "note": note}), encoding="utf-8"
        )
        await _send(
            message,
            f"⏳ Verify queued: `{subtask}` — *{note}*\n"
            f"CLI will process it at the next step boundary."
        )

    elif low == "export":
        if not OUTPUTS_PATH.exists():
            await _send(message, "No export file yet. Run `export` in the CLI first.")
        else:
            size_kb = OUTPUTS_PATH.stat().st_size // 1024
            await _send(
                message,
                f"Solo Builder outputs · {size_kb} KB",
                file=discord.File(str(OUTPUTS_PATH), filename="solo_builder_outputs.md"),
            )

    elif low.startswith("add_task"):
        spec = text[8:].strip()
        if not spec:
            await _send(message, "Usage: `add_task <spec>` — e.g. `add_task Build the OAuth2 flow`")
            return
        ADD_TASK_TRIGGER.parent.mkdir(exist_ok=True)
        ADD_TASK_TRIGGER.write_text(json.dumps({"spec": spec}), encoding="utf-8")
        await _send(
            message,
            f"✅ Task queued: *{spec[:80]}*\nCLI will add it at the next step boundary."
        )

    elif low.startswith("add_branch"):
        rest = text[10:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await _send(message, "Usage: `add_branch <task> <spec>` — e.g. `add_branch 0 Add error handling`")
            return
        task_arg, spec = parts[0], parts[1].strip()
        if not spec:
            await _send(message, "Usage: `add_branch <task> <spec>` — e.g. `add_branch 0 Add error handling`")
            return
        ADD_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
        ADD_BRANCH_TRIGGER.write_text(json.dumps({"task": task_arg, "spec": spec}), encoding="utf-8")
        await _send(
            message,
            f"✅ Branch queued on Task {task_arg}: *{spec[:80]}*\nCLI will add it at the next step boundary."
        )

    elif low.startswith("output"):
        st_target = text[6:].strip().upper()
        if not st_target:
            await _send(message, "Usage: `output <subtask>` — e.g. `output A3`")
            return
        state = _load_state()
        result = _find_subtask_output(state, st_target)
        if result is None:
            await _send(message, f"❌ Subtask `{st_target}` not found.")
        else:
            task_name, out = result
            if out:
                await _send(message, f"**{st_target}** ({task_name}):\n```\n{out[:1800]}\n```")
            else:
                await _send(message, f"**{st_target}** ({task_name}): no output recorded yet.")

    elif low.startswith("describe"):
        rest = text[8:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await _send(message, "Usage: `describe <subtask> <prompt>` — e.g. `describe A3 Implement retry logic`")
            return
        st_target, desc = parts[0].upper(), parts[1].strip()
        DESCRIBE_TRIGGER.parent.mkdir(exist_ok=True)
        DESCRIBE_TRIGGER.write_text(
            json.dumps({"subtask": st_target, "desc": desc}), encoding="utf-8"
        )
        await _send(
            message,
            f"✅ Describe queued: `{st_target}` — *{desc[:80]}*\nCLI will apply it at the next step boundary."
        )

    elif low.startswith("tools"):
        rest = text[5:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await _send(message, "Usage: `tools <subtask> <tool,list | none>` — e.g. `tools H1 Read,Glob,Grep`")
            return
        st_target, tool_val = parts[0].upper(), parts[1].strip()
        TOOLS_TRIGGER.parent.mkdir(exist_ok=True)
        TOOLS_TRIGGER.write_text(
            json.dumps({"subtask": st_target, "tools": tool_val}), encoding="utf-8"
        )
        label = tool_val if tool_val.lower() != "none" else "(none — headless)"
        await _send(
            message,
            f"✅ Tools queued: `{st_target}` → {label}\nCLI will apply at the next step boundary."
        )

    elif low == "reset confirm":
        RESET_TRIGGER.parent.mkdir(exist_ok=True)
        RESET_TRIGGER.write_text("1")
        await _send(message, "⚠️ Reset queued — CLI will clear DAG and state at the next step boundary.")

    elif low == "reset":
        await _send(message, "⚠️ This will **destroy all progress**. Type `reset confirm` to proceed.")

    elif low == "snapshot":
        SNAPSHOT_TRIGGER.parent.mkdir(exist_ok=True)
        SNAPSHOT_TRIGGER.write_text("1")
        # Also send the latest existing PDF if available
        latest = None
        if SNAPSHOTS_DIR.is_dir():
            pdfs = sorted(SNAPSHOTS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                latest = pdfs[0]
        if latest:
            await _send(
                message,
                f"📸 Snapshot triggered. Latest existing PDF attached:",
                file=discord.File(str(latest), filename=latest.name),
            )
        else:
            await _send(message, "📸 Snapshot triggered — CLI will generate a PDF at the next step boundary.")

    elif low.startswith("prioritize_branch"):
        rest = text[17:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await _send(message, "Usage: `prioritize_branch <task> <branch>` — e.g. `prioritize_branch 0 A`")
            return
        pb_task, pb_branch = parts[0], parts[1].strip()
        PRIORITY_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
        PRIORITY_BRANCH_TRIGGER.write_text(
            json.dumps({"task": pb_task, "branch": pb_branch}), encoding="utf-8"
        )
        await _send(
            message,
            f"✅ Priority boost queued: Task {pb_task} / {pb_branch}\nCLI will boost it at the next step boundary."
        )

    elif low.startswith("undepends"):
        rest = text[9:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await _send(message, "Usage: `undepends <task> <dep>` — e.g. `undepends 1 0`")
            return
        UNDEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
        UNDEPENDS_TRIGGER.write_text(
            json.dumps({"target": parts[0], "dep": parts[1].strip()}), encoding="utf-8"
        )
        await _send(
            message,
            f"✅ Undepends queued: Task {parts[0]} no longer depends on Task {parts[1].strip()}\n"
            f"CLI will apply at the next step boundary."
        )

    elif low.startswith("depends"):
        rest = text[7:].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            # Show dependency graph from state
            state = _load_state()
            dag = state.get("dag", {})
            if not dag:
                await _send(message, "No DAG loaded.")
                return
            lines = ["**Dependency Graph**"]
            for t_name, t_data in dag.items():
                deps = t_data.get("depends_on", [])
                st = t_data.get("status", "?")
                sym = {"Verified": "✅", "Running": "▶"}.get(st, "⏳")
                dep_str = f" ← {', '.join(deps)}" if deps else " (root)"
                lines.append(f"{sym} {t_name}{dep_str}")
            await _send(message, "\n".join(lines))
            return
        DEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
        DEPENDS_TRIGGER.write_text(
            json.dumps({"target": parts[0], "dep": parts[1].strip()}), encoding="utf-8"
        )
        await _send(
            message,
            f"✅ Depends queued: Task {parts[0]} → Task {parts[1].strip()}\n"
            f"CLI will apply at the next step boundary."
        )

    elif low.startswith("set "):
        rest = text[4:].strip()
        if "=" in rest:
            # Setter: set KEY=VALUE → write trigger for CLI
            k, v = rest.split("=", 1)
            k, v = k.strip(), v.strip()
            if not k:
                await _send(message, "Usage: `set KEY=VALUE` or `set KEY`")
                return
            SET_TRIGGER.parent.mkdir(exist_ok=True)
            SET_TRIGGER.write_text(json.dumps({"key": k, "value": v}), encoding="utf-8")
            await _send(message, f"⚙️ `{k.upper()}={v}` queued — CLI will apply at the next step boundary.")
        else:
            # Getter: set KEY → read config/settings.json
            bare = rest.upper()
            cfg_key = _KEY_MAP.get(bare)
            if not cfg_key:
                await _send(message, f"❌ Unknown setting `{bare}`. Known: {', '.join(sorted(_KEY_MAP))}")
                return
            try:
                cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                val = cfg.get(cfg_key, "(not set)")
                await _send(message, f"⚙️ `{bare}` = `{val}`")
            except Exception:
                await _send(message, "❌ Could not read `config/settings.json`.")

    elif low == "undo":
        UNDO_TRIGGER.parent.mkdir(exist_ok=True)
        UNDO_TRIGGER.write_text("1")
        await _send(message, "↩️ Undo queued — CLI will restore from last backup at next step boundary.")

    elif low == "pause":
        if not _auto_running():
            await _send(message, "⚠️ No auto-run in progress to pause.")
            return
        PAUSE_TRIGGER.parent.mkdir(exist_ok=True)
        PAUSE_TRIGGER.write_text("1")
        hb = _read_heartbeat()
        extra = ""
        if hb:
            step, v, t, p, r, w = hb
            pct = round(v / t * 100, 1) if t else 0
            extra = f"\nStep {step} — {v}✅ {r}▶ {w}⏸ {p}⏳ / {t} ({pct}%)"
        await _send(message, f"⏸ Pause signal sent — auto-run will pause after the current step. Use `resume` to continue.{extra}")

    elif low == "resume":
        if PAUSE_TRIGGER.exists():
            try:
                PAUSE_TRIGGER.unlink()
            except OSError:
                pass
            hb = _read_heartbeat()
            extra = ""
            if hb:
                step, v, t, p, r, w = hb
                pct = round(v / t * 100, 1) if t else 0
                extra = f"\nStep {step} — {v}✅ {r}▶ {w}⏸ {p}⏳ / {t} ({pct}%)"
            await _send(message, f"▶ Resumed — auto-run will continue.{extra}")
        else:
            await _send(message, "⚠️ Not paused.")

    elif low == "config":
        try:
            cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            lines = ["**Current Settings** (`config/settings.json`)", "```"]
            for k, v in cfg.items():
                lines.append(f"  {k:<30} = {v}")
            lines.append("```")
            await _send(message, "\n".join(lines))
        except Exception:
            await _send(message, "❌ Could not read `config/settings.json`.")

    elif low == "graph":
        state = _load_state()
        await _send(message, _format_graph(state))

    elif low == "priority":
        state = _load_state()
        await _send(message, _format_priority(state))

    elif low == "stalled":
        state = _load_state()
        await _send(message, _format_stalled(state))

    elif low == "heal" or low.startswith("heal "):
        st_arg = text[5:].strip() if " " in text else ""
        state = _load_state()
        await _send(message, _format_heal(state, st_arg))

    elif low.startswith("reset_task ") or low == "reset_task":
        task_arg = text[11:].strip() if low.startswith("reset_task ") else ""
        state = _load_state()
        await _send(message, _format_reset_task(state, task_arg))

    elif low.startswith("reset_branch ") or low == "reset_branch":
        parts = text[13:].strip().split(None, 1) if low.startswith("reset_branch ") else []
        task_arg   = parts[0] if len(parts) > 0 else ""
        branch_arg = parts[1] if len(parts) > 1 else ""
        state = _load_state()
        await _send(message, _format_reset_branch(state, task_arg, branch_arg))

    elif low.startswith("bulk_reset ") or low == "bulk_reset":
        names = text[11:].strip().split() if low.startswith("bulk_reset ") else []
        state = _load_state()
        await _send(message, _format_bulk_reset(state, names))

    elif low.startswith("bulk_verify ") or low == "bulk_verify":
        names = text[12:].strip().split() if low.startswith("bulk_verify ") else []
        state = _load_state()
        await _send(message, _format_bulk_verify(state, names))

    elif low.startswith("task_progress ") or low == "task_progress":
        task_arg = text[14:].strip() if low.startswith("task_progress ") else ""
        state = _load_state()
        await _send(message, _format_task_progress(state, task_arg))

    elif low == "agents":
        state = _load_state()
        await _send(message, _format_agents(state))

    elif low == "forecast":
        state = _load_state()
        await _send(message, _format_forecast(state))

    elif low == "tasks":
        state = _load_state()
        await _send(message, _format_tasks(state))

    elif low == "diff":
        await _send(message, _format_diff())

    elif low == "filter" or low.startswith("filter "):
        status_arg = text[7:].strip() if " " in text else ""
        state = _load_state()
        await _send(message, _format_filter(state, status_arg))

    elif low.startswith("timeline "):
        st = text[9:].strip()
        state = _load_state()
        await _send(message, _format_timeline(state, st))

    elif low == "stats":
        state = _load_state()
        await _send(message, _format_stats(state))

    elif low == "cache":
        await _send(message, _format_cache(clear=False))

    elif low == "cache clear":
        await _send(message, _format_cache(clear=True))

    elif low == "history" or low.startswith("history "):
        n = 20
        rest = text[7:].strip() if low.startswith("history ") else ""
        if rest.isdigit():
            n = int(rest)
        state = _load_state()
        await _send(message, _format_history(state, n))

    elif low.startswith("search "):
        q = text[7:].strip()
        state = _load_state()
        await _send(message, _format_search(state, q))

    elif low == "log" or low.startswith("log "):
        st = text[3:].strip() if low.startswith("log ") else ""
        await _send(message, _format_log(st))

    elif low == "branches" or low.startswith("branches "):
        task_arg = text[9:].strip() if low.startswith("branches ") else ""
        state = _load_state()
        await _send(message, _format_branches(state, task_arg))

    elif low.startswith("rename "):
        parts = text[7:].strip().split(None, 1)
        if len(parts) < 2:
            await _send(message, "Usage: `rename <subtask> <new description>`")
        else:
            st, desc = parts[0].strip().upper(), parts[1].strip()
            RENAME_TRIGGER.parent.mkdir(exist_ok=True)
            RENAME_TRIGGER.write_text(json.dumps({"subtask": st, "desc": desc}))
            await _send(message, f"✎ Rename queued: `{st}` → {desc[:80]}")

    elif low == "heartbeat":
        hb = _read_heartbeat()
        if hb:
            step, v, tot, p, r, rv = hb
            pct = round(v / tot * 100, 1) if tot else 0
            lines = [
                f"**Heartbeat** · Step {step}",
                f"✅ {v}  ▶ {r}  ⏸ {rv}  ⏳ {p} / {tot}  ({pct}%)",
            ]
            if _auto_running():
                lines.append("▶ Auto-run in progress")
            await _send(message, "\n".join(lines))
        else:
            await _send(message, "⚠️ No heartbeat — is the CLI running?")

    elif low in ("help", "?"):
        await _send(message, _HELP_TEXT)


# ---------------------------------------------------------------------------
# Slash commands (extracted to bot_slash.py)
# ---------------------------------------------------------------------------

from .bot_slash import register_slash_commands
register_slash_commands(bot)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

def _read_heartbeat() -> tuple[int, int, int, int, int, int] | None:
    """Returns (step, verified, total, pending, running, review) from step.txt, or None."""
    try:
        parts = STEP_PATH.read_text().strip().split(",")
        if len(parts) == 6:
            return tuple(int(x) for x in parts)  # type: ignore[return-value]
        return int(parts[0]), 0, 0, 0, 0, 0
    except Exception:
        return None


def _format_step_line(state: dict) -> str:
    """One-line step ticker: Step 12 — 8✅ 3▶ 1⏸ 58⏳ / 70 (14.3%)"""
    hb = _read_heartbeat()
    if hb:
        step, verified, total, pending, running, review = hb
    else:
        dag = state.get("dag", {})
        step = state.get("step", 0)
        total = verified = running = review = 0
        for t in dag.values():
            for b in t["branches"].values():
                for s in b["subtasks"].values():
                    st = s.get("status", "")
                    total += 1
                    if st == "Verified": verified += 1
                    elif st == "Running": running += 1
                    elif st == "Review":  review += 1
        pending = total - verified - running - review
    pct = round(verified / total * 100, 1) if total else 0
    return (
        f"Step {step} — "
        f"{verified}✅ {running}▶ {review}⏸ {pending}⏳ / {total} ({pct}%)"
    )


async def _run_auto(channel_id: int, n: Optional[int]) -> None:
    """Drive the CLI through n steps (or until complete) via trigger file."""
    limit     = n if n is not None else 200   # safety cap
    completed = 0
    ch        = await _get_channel(channel_id)

    def _hb_step() -> int:
        hb = _read_heartbeat()
        return hb[0] if hb else _load_state().get("step", 0)

    def _hb_has_work() -> bool:
        hb = _read_heartbeat()
        if hb:
            _, _, _, pending, running, _ = hb
            return (pending + running) > 0
        return _has_work(_load_state().get("dag", {}))

    for _ in range(limit):
        # Pause gate: wait while pause trigger exists
        while PAUSE_TRIGGER.exists():
            await asyncio.sleep(0.5)
        if not _hb_has_work():
            # Wait up to 30 s for the auto-save JSON to reflect all-Verified.
            # The JSON saves every 5 steps so can lag well behind the heartbeat.
            state = _load_state()
            for _ in range(300):
                await asyncio.sleep(0.1)
                state = _load_state()
                stats = state.get("dag", {})
                if stats and all(
                    s.get("status") == "Verified"
                    for t in stats.values()
                    for b in t["branches"].values()
                    for s in b["subtasks"].values()
                ):
                    break
            if ch:
                # Use heartbeat for accurate counts if JSON is still stale
                hb = _read_heartbeat()
                if hb and hb[1] == hb[2] and hb[2] > 0:
                    _, v, tot, _, _, _ = hb
                    status_line = _format_status(state)
                    # Patch header counts if JSON still shows wrong numbers
                    dag_v = sum(
                        1 for t in state.get("dag", {}).values()
                        for b in t["branches"].values()
                        for s in b["subtasks"].values()
                        if s.get("status") == "Verified"
                    )
                    if dag_v < tot:
                        status_line = (
                            f"**Solo Builder** · Step {hb[0]}\n"
                            f"✅ {v}  ▶ 0  ⏸ 0  ⏳ 0 / {tot}  (100.0%)\n"
                            f"*(JSON still flushing — counts from heartbeat)*"
                        )
                    msg = f"✅ Pipeline complete after {completed} steps.\n{status_line}"
                else:
                    msg = f"✅ Pipeline complete after {completed} steps.\n{_format_status(state)}"
                await ch.send(msg)
                _log(str(ch), "BOT", msg[:200])
            return

        current_step = _hb_step()
        TRIGGER_PATH.parent.mkdir(exist_ok=True)
        TRIGGER_PATH.write_text("1")

        # Wait up to 60 s for the CLI heartbeat (step.txt) to advance
        for _ in range(600):
            await asyncio.sleep(0.1)
            if _hb_step() > current_step:
                completed += 1
                break
        else:
            if ch:
                msg = f"⚠️ Step timeout after {completed} steps. Is the CLI running?"
                await ch.send(msg)
                _log(str(ch), "BOT", msg)
            return

        # Per-step ticker
        if ch:
            ticker = _format_step_line(_load_state())
            await ch.send(ticker)
            _log(str(ch), "BOT", ticker)

    # n-step run finished
    final = _load_state()
    if ch:
        msg = f"✅ {completed}/{limit} steps done.\n{_format_status(final)}"
        await ch.send(msg)
        _log(str(ch), "BOT", msg[:200])


async def _poll_completion(client: discord.Client) -> None:
    """Notify DISCORD_CHANNEL_ID once when all subtasks reach Verified."""
    if not CHANNEL_ID:
        return
    notified = False
    while True:
        await asyncio.sleep(10)
        state    = _load_state()
        dag      = state.get("dag", {})
        if not dag:
            notified = False
            continue
        total    = sum(
            1 for t in dag.values()
            for b in t["branches"].values()
            for s in b["subtasks"].values()
        )
        verified = sum(
            1 for t in dag.values()
            for b in t["branches"].values()
            for s in b["subtasks"].values()
            if s.get("status") == "Verified"
        )
        if total and verified == total:
            if not notified:
                notified = True
                ch = await _get_channel(CHANNEL_ID)
                if ch:
                    await ch.send(
                        f"🎉 **Solo Builder complete!**\n"
                        f"{verified}/{total} subtasks verified · "
                        f"{state.get('step', 0)} steps"
                    )
        else:
            notified = False   # reset so we re-notify after a dag reset


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not TOKEN:
        raise SystemExit(
            "DISCORD_BOT_TOKEN not set.\n"
            "1. Go to https://discord.com/developers/applications\n"
            "2. New Application → Bot → Reset Token → copy it\n"
            "3. Add DISCORD_BOT_TOKEN=<token> to your .env\n"
            "4. Optionally add DISCORD_CHANNEL_ID=<channel ID> to restrict access"
        )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
