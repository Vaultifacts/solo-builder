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
    _format_log, _format_search, _format_branches, _branches_to_csv, _format_subtasks, _subtasks_to_csv, _format_history,
    _format_stats, _format_cache, _format_tasks, _format_task_progress,
    _format_priority, _format_stalled, _format_agents, _format_forecast,
    _format_filter, _format_timeline, _format_diff, _format_status, _format_graph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dag": {}, "step": 0}


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
# Text commands (extracted to bot_commands.py)
# ---------------------------------------------------------------------------
from .bot_commands import (
    _handle_text_command,
    _format_heal, _format_reset_task, _format_reset_branch,
    _format_bulk_reset, _format_bulk_verify,
    _HELP_TEXT, _KEY_MAP,
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
