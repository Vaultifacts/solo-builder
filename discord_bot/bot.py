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
TRIGGER_PATH   = _ROOT / "state" / "run_trigger"
VERIFY_TRIGGER = _ROOT / "state" / "verify_trigger.json"
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


def _format_status(state: dict) -> str:
    dag   = state.get("dag", {})
    step  = state.get("step", 0)
    total = verified = running = review = 0
    rows: list[str] = []

    for task_name, task in dag.items():
        tv = tr = trv = tt = 0
        for b in task["branches"].values():
            for s in b["subtasks"].values():
                st = s.get("status", "")
                tt += 1
                if st == "Verified": tv += 1
                elif st == "Running": tr += 1
                elif st == "Review":  trv += 1
        total += tt; verified += tv; running += tr; review += trv
        done = int((tv / tt) * 10) if tt else 0
        bar  = "█" * done + "░" * (10 - done)
        rows.append(f"{task_name:<8} {bar} {tv}/{tt}")

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

class SoloBuilderBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        self.loop.create_task(_poll_completion(self))

    async def on_ready(self) -> None:
        print(f"Solo Builder Bot ready · logged in as {self.user}")
        print(f"Slash commands synced. Invite URL scope: bot+applications.commands")


bot = SoloBuilderBot()


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
        "`/status`                    — DAG progress summary\n"
        "`/run`                       — trigger one step\n"
        "`/auto [n]`                  — run N steps (default: until complete)\n"
        "`/verify subtask [note]`     — approve a subtask (REVIEW_MODE)\n"
        "`/export`                    — download all Claude outputs\n"
        "`/help`                      — this message"
    )


@bot.tree.command(name="status", description="DAG progress summary")
async def status_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    await interaction.response.send_message(_format_status(_load_state()))


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
    label = f"{n} steps" if n is not None else "until complete"
    asyncio.create_task(_run_auto(interaction.channel_id, n))
    await interaction.response.send_message(
        f"▶ Auto-run started: {label}\nUse `/status` for progress."
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


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def _run_auto(channel_id: int, n: Optional[int]) -> None:
    """Drive the CLI through n steps (or until complete) via trigger file."""
    limit     = n if n is not None else 200   # safety cap
    completed = 0

    for _ in range(limit):
        state = _load_state()
        if not _has_work(state.get("dag", {})):
            ch = await _get_channel(channel_id)
            if ch:
                await ch.send(
                    f"✅ Pipeline complete after {completed} steps.\n"
                    f"{_format_status(state)}"
                )
            return

        current_step = state.get("step", 0)
        TRIGGER_PATH.parent.mkdir(exist_ok=True)
        TRIGGER_PATH.write_text("1")

        # Wait up to 15 s for the CLI to process the step
        for _ in range(150):
            await asyncio.sleep(0.1)
            if _load_state().get("step", 0) > current_step:
                completed += 1
                break
        else:
            ch = await _get_channel(channel_id)
            if ch:
                await ch.send(
                    f"⚠️ Step timeout after {completed} steps. Is the CLI running?"
                )
            return

    # n-step run finished
    final = _load_state()
    ch = await _get_channel(channel_id)
    if ch:
        await ch.send(
            f"✅ {completed}/{limit} steps done.\n{_format_status(final)}"
        )


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
