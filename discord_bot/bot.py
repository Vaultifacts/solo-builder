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
OUTPUTS_PATH   = _ROOT / "solo_builder_outputs.md"

TOKEN      = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0") or "0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dag": {}, "step": 0}


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


def _format_status(state: dict) -> str:
    dag   = state.get("dag", {})
    step  = state.get("step", 0)
    total = verified = running = review = 0
    rows: list[str] = []

    for task_name, task in dag.items():
        tv = tr = trv = tt = 0
        branch_rows: list[str] = []
        for b_name, b in task.get("branches", {}).items():
            bv = br = brv = bt = 0
            for s in b.get("subtasks", {}).values():
                st = s.get("status", "")
                bt += 1
                if st == "Verified": bv += 1
                elif st == "Running": br += 1
                elif st == "Review":  brv += 1
            tv += bv; tr += br; trv += brv; tt += bt
            b_done = int((bv / bt) * 6) if bt else 0
            b_bar  = "█" * b_done + "░" * (6 - b_done)
            if bv == bt:      b_sym = "✓"
            elif brv:         b_sym = "⏸"
            elif br:          b_sym = "▶"
            else:             b_sym = "·"
            branch_rows.append(f"  {b_name:<14}{b_bar} {bv}/{bt} {b_sym}")

        total += tt; verified += tv; running += tr; review += trv
        done = int((tv / tt) * 10) if tt else 0
        bar  = "█" * done + "░" * (10 - done)
        rows.append(f"{task_name:<8} {bar} {tv}/{tt}")
        rows.extend(branch_rows)

    pct = round(verified / total * 100, 1) if total else 0
    header = (
        f"**Solo Builder** · Step {step}\n"
        f"✅ {verified}  ▶ {running}  ⏸ {review}  "
        f"⏳ {total - verified - running - review} / {total}  ({pct}%)\n"
    )
    return header + "```\n" + "\n".join(rows) + "\n```"


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


bot = SoloBuilderBot()

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
    "`add_task <spec>`                  — queue a new task (added at next step)\n"
    "`add_branch <task> <spec>`         — queue a new branch on an existing task\n"
    "`prioritize_branch <task> <branch>` — boost a branch to front of queue\n"
    "`export`                           — download all Claude outputs\n"
    "`help`                             — this message\n\n"
    "*Slash commands (`/status`, `/run`, `/stop`, …) work too.*"
)


async def _send(message: discord.Message, text: str, **kwargs) -> None:
    """Send a reply and log it to chat.log."""
    await message.channel.send(text, **kwargs)
    _log(str(message.channel), "BOT", text[:200])


async def _handle_text_command(message: discord.Message) -> None:
    text = message.content.strip()
    low  = text.lower()

    if low == "status":
        reply = _format_status(_load_state())
        if _auto_running():
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

    elif low in ("help", "?"):
        await _send(message, _HELP_TEXT)


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

@bot.tree.command(name="help", description="Show available commands")
async def help_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
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
        "`/describe subtask prompt`          — set a custom Claude prompt for a subtask\n"
        "`/add_task spec`                    — queue a new task\n"
        "`/add_branch task spec`             — queue a new branch on a task\n"
        "`/prioritize_branch task branch`    — boost a branch to front of queue\n"
        "`/export`                           — download all Claude outputs\n"
        "`/help`                             — this message"
    )


@bot.tree.command(name="status", description="DAG progress summary")
async def status_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    msg = _format_status(_load_state())
    if _auto_running():
        msg += "\n▶ Auto-run in progress — use `/stop` to cancel."
    await interaction.response.send_message(msg)


@bot.tree.command(name="run", description="Trigger one CLI step")
async def run_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    state = _load_state()
    if not _has_work(state.get("dag", {})):
        await interaction.response.send_message("✅ Pipeline already complete.")
        return
    TRIGGER_PATH.parent.mkdir(exist_ok=True)
    TRIGGER_PATH.write_text("1")
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
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    VERIFY_TRIGGER.parent.mkdir(exist_ok=True)
    VERIFY_TRIGGER.write_text(
        json.dumps({"subtask": subtask.upper(), "note": note}), encoding="utf-8"
    )
    await interaction.response.send_message(
        f"⏳ Verify queued: `{subtask.upper()}` — *{note}*\n"
        f"CLI will process it at the next step boundary."
    )


@bot.tree.command(name="auto", description="Run steps automatically")
@app_commands.describe(n="Number of steps (omit for full run)")
async def auto_cmd(interaction: discord.Interaction, n: Optional[int] = None) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    if _auto_running():
        await interaction.response.send_message(
            "⚠️ Auto already running. Use `/stop` to cancel or `/status` to check progress.",
            ephemeral=True,
        )
        return
    global _auto_task
    label = f"{n} steps" if n is not None else "until complete"
    _auto_task = asyncio.create_task(_run_auto(interaction.channel_id, n))
    await interaction.response.send_message(
        f"▶ Auto-run started: {label}\nUse `/status` for progress."
    )


@bot.tree.command(name="stop", description="Cancel an in-progress auto run")
async def stop_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    if _auto_running():
        _auto_task.cancel()
    STOP_TRIGGER.parent.mkdir(exist_ok=True)
    STOP_TRIGGER.write_text("1")
    await interaction.response.send_message(
        "⏹ Stop signal sent — CLI will halt after the current step."
    )


@bot.tree.command(name="export", description="Download all Claude outputs as Markdown")
async def export_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    if not OUTPUTS_PATH.exists():
        await interaction.response.send_message(
            "No export file yet. Run `export` in the CLI first."
        )
        return
    size_kb = OUTPUTS_PATH.stat().st_size // 1024
    await interaction.response.send_message(
        f"Solo Builder outputs · {size_kb} KB",
        file=discord.File(str(OUTPUTS_PATH), filename="solo_builder_outputs.md"),
    )


@bot.tree.command(name="add_task", description="Queue a new task to be added at the next step")
@app_commands.describe(spec="What the task should accomplish")
async def add_task_cmd(interaction: discord.Interaction, spec: str) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    spec = spec.strip()
    if not spec:
        await interaction.response.send_message("Usage: `/add_task <spec>`", ephemeral=True)
        return
    ADD_TASK_TRIGGER.parent.mkdir(exist_ok=True)
    ADD_TASK_TRIGGER.write_text(json.dumps({"spec": spec}), encoding="utf-8")
    await interaction.response.send_message(
        f"✅ Task queued: *{spec[:80]}*\nCLI will add it at the next step boundary."
    )


@bot.tree.command(name="add_branch", description="Queue a new branch on an existing task")
@app_commands.describe(task="Task number or name (e.g. 0 or Task 0)", spec="What the branch should cover")
async def add_branch_cmd(interaction: discord.Interaction, task: str, spec: str) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    task = task.strip()
    spec = spec.strip()
    if not task or not spec:
        await interaction.response.send_message("Usage: `/add_branch <task> <spec>`", ephemeral=True)
        return
    ADD_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
    ADD_BRANCH_TRIGGER.write_text(json.dumps({"task": task, "spec": spec}), encoding="utf-8")
    await interaction.response.send_message(
        f"✅ Branch queued on Task {task}: *{spec[:80]}*\nCLI will add it at the next step boundary."
    )


@bot.tree.command(name="output", description="Show Claude output for a specific subtask")
@app_commands.describe(subtask="Subtask name (e.g. A3)")
async def output_cmd(interaction: discord.Interaction, subtask: str) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    st_target = subtask.strip().upper()
    if not st_target:
        await interaction.response.send_message("Usage: `/output <subtask>`", ephemeral=True)
        return
    state = _load_state()
    result = _find_subtask_output(state, st_target)
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
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    st_target = subtask.strip().upper()
    prompt    = prompt.strip()
    if not st_target or not prompt:
        await interaction.response.send_message("Usage: `/describe <subtask> <prompt>`", ephemeral=True)
        return
    DESCRIBE_TRIGGER.parent.mkdir(exist_ok=True)
    DESCRIBE_TRIGGER.write_text(
        json.dumps({"subtask": st_target, "desc": prompt}), encoding="utf-8"
    )
    await interaction.response.send_message(
        f"✅ Describe queued: `{st_target}` — *{prompt[:80]}*\nCLI will apply it at the next step boundary."
    )


@bot.tree.command(name="prioritize_branch", description="Boost a branch to the front of the execution queue")
@app_commands.describe(task="Task number or name (e.g. 0)", branch="Branch name (e.g. A)")
async def prioritize_branch_cmd(interaction: discord.Interaction, task: str, branch: str) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    task   = task.strip()
    branch = branch.strip()
    if not task or not branch:
        await interaction.response.send_message("Usage: `/prioritize_branch <task> <branch>`", ephemeral=True)
        return
    PRIORITY_BRANCH_TRIGGER.parent.mkdir(exist_ok=True)
    PRIORITY_BRANCH_TRIGGER.write_text(
        json.dumps({"task": task, "branch": branch}), encoding="utf-8"
    )
    await interaction.response.send_message(
        f"✅ Priority boost queued: Task {task} / {branch}\nCLI will boost it at the next step boundary."
    )


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
