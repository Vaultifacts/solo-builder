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
PAUSE_TRIGGER           = _ROOT / "state" / "pause_trigger"
SNAPSHOTS_DIR           = _ROOT / "snapshots"
SETTINGS_PATH  = _ROOT / "config" / "settings.json"
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
    "`graph`                            — visual ASCII DAG dependency graph\n"
    "`heartbeat`                        — live counters from step.txt\n"
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
        await _send(message, "⏸ Pause signal sent — auto-run will pause after the current step. Use `resume` to continue.")

    elif low == "resume":
        if PAUSE_TRIGGER.exists():
            try:
                PAUSE_TRIGGER.unlink()
            except OSError:
                pass
            await _send(message, "▶ Resumed — auto-run will continue.")
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
        "`/graph`                            — visual ASCII DAG dependency graph\n"
        "`/heartbeat`                       — live counters from step.txt\n"
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


@bot.tree.command(name="undo", description="Undo last step (restore from backup)")
async def undo_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    UNDO_TRIGGER.parent.mkdir(exist_ok=True)
    UNDO_TRIGGER.write_text("1")
    await interaction.response.send_message("↩️ Undo queued — CLI will restore from last backup at next step boundary.")


@bot.tree.command(name="pause", description="Pause auto-run (resume continues from same position)")
async def pause_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    if not _auto_running():
        await interaction.response.send_message("⚠️ No auto-run in progress to pause.", ephemeral=True)
        return
    PAUSE_TRIGGER.parent.mkdir(exist_ok=True)
    PAUSE_TRIGGER.write_text("1")
    await interaction.response.send_message("⏸ Pause signal sent — auto-run will pause after the current step. Use `/resume` to continue.")


@bot.tree.command(name="resume", description="Resume a paused auto-run")
async def resume_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    if PAUSE_TRIGGER.exists():
        try:
            PAUSE_TRIGGER.unlink()
        except OSError:
            pass
        await interaction.response.send_message("▶ Resumed — auto-run will continue.")
    else:
        await interaction.response.send_message("⚠️ Not paused.", ephemeral=True)


@bot.tree.command(name="config", description="Show all current runtime settings")
async def config_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    try:
        cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        lines = ["**Current Settings** (`config/settings.json`)", "```"]
        for k, v in cfg.items():
            lines.append(f"  {k:<30} = {v}")
        lines.append("```")
        await interaction.response.send_message("\n".join(lines))
    except Exception:
        await interaction.response.send_message("❌ Could not read `config/settings.json`.")


@bot.tree.command(name="graph", description="Visual ASCII DAG dependency graph")
async def graph_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    await interaction.response.send_message(_format_graph(_load_state()))


@bot.tree.command(name="heartbeat", description="Show live heartbeat counters from step.txt")
async def heartbeat_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
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
        await interaction.response.send_message("\n".join(lines))
    else:
        await interaction.response.send_message("⚠️ No heartbeat — is the CLI running?")


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


@bot.tree.command(name="tools", description="Set allowed tools for a subtask")
@app_commands.describe(subtask="Subtask name (e.g. H1)", tools="Comma-separated tools (e.g. Read,Glob,Grep) or 'none'")
async def tools_cmd(interaction: discord.Interaction, subtask: str, tools: str) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    st_target = subtask.strip().upper()
    tool_val  = tools.strip()
    if not st_target or not tool_val:
        await interaction.response.send_message("Usage: `/tools <subtask> <tool,list>`", ephemeral=True)
        return
    TOOLS_TRIGGER.parent.mkdir(exist_ok=True)
    TOOLS_TRIGGER.write_text(
        json.dumps({"subtask": st_target, "tools": tool_val}), encoding="utf-8"
    )
    label = tool_val if tool_val.lower() != "none" else "(none — headless)"
    await interaction.response.send_message(
        f"✅ Tools queued: `{st_target}` → {label}\nCLI will apply at the next step boundary."
    )


@bot.tree.command(name="reset", description="Reset DAG to initial state (destructive!)")
@app_commands.describe(confirm="Type 'yes' to confirm the reset")
async def reset_cmd(interaction: discord.Interaction, confirm: str = "") -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    if confirm.strip().lower() not in ("yes", "confirm"):
        await interaction.response.send_message(
            "⚠️ This will **destroy all progress**. Use `/reset confirm:yes` to proceed.",
            ephemeral=True,
        )
        return
    RESET_TRIGGER.parent.mkdir(exist_ok=True)
    RESET_TRIGGER.write_text("1")
    await interaction.response.send_message(
        "⚠️ Reset queued — CLI will clear DAG and state at the next step boundary."
    )


@bot.tree.command(name="snapshot", description="Trigger a PDF timeline snapshot")
async def snapshot_cmd(interaction: discord.Interaction) -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    SNAPSHOT_TRIGGER.parent.mkdir(exist_ok=True)
    SNAPSHOT_TRIGGER.write_text("1")
    latest = None
    if SNAPSHOTS_DIR.is_dir():
        pdfs = sorted(SNAPSHOTS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
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


@bot.tree.command(name="set", description="Change or query a runtime setting")
@app_commands.describe(
    key="Setting name (e.g. REVIEW_MODE, ANTHROPIC_MAX_TOKENS)",
    value="New value (omit to show current value)",
)
async def set_cmd(interaction: discord.Interaction, key: str, value: str = "") -> None:
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    key = key.strip().upper()
    if value:
        SET_TRIGGER.parent.mkdir(exist_ok=True)
        SET_TRIGGER.write_text(json.dumps({"key": key, "value": value.strip()}), encoding="utf-8")
        await interaction.response.send_message(
            f"⚙️ `{key}={value.strip()}` queued — CLI will apply at the next step boundary."
        )
    else:
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
        cfg_key = _KEY_MAP.get(key)
        if not cfg_key:
            await interaction.response.send_message(
                f"❌ Unknown setting `{key}`. Known: {', '.join(sorted(_KEY_MAP))}",
                ephemeral=True,
            )
            return
        try:
            cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
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
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    target, dep = target.strip(), dep.strip()
    if not target or not dep:
        state = _load_state()
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
    DEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
    DEPENDS_TRIGGER.write_text(
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
    if not _allowed(interaction):
        await interaction.response.send_message("❌ Wrong channel.", ephemeral=True)
        return
    target, dep = target.strip(), dep.strip()
    if not target or not dep:
        await interaction.response.send_message(
            "Usage: `/undepends <task> <dep>`", ephemeral=True
        )
        return
    UNDEPENDS_TRIGGER.parent.mkdir(exist_ok=True)
    UNDEPENDS_TRIGGER.write_text(
        json.dumps({"target": target, "dep": dep}), encoding="utf-8"
    )
    await interaction.response.send_message(
        f"✅ Undepends queued: Task {target} no longer depends on Task {dep}\n"
        f"CLI will apply at the next step boundary."
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
