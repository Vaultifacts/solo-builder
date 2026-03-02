#!/usr/bin/env python3
"""
Solo Builder — Telegram Bot

Control the CLI from your phone:
  /status  — DAG progress summary
  /run     — trigger one step
  /export  — download all Claude outputs as Markdown
  /help    — command list

Setup:
  pip install "python-telegram-bot>=20.0"
  # Create a bot via @BotFather, then add to your .env:
  TELEGRAM_BOT_TOKEN=<token>
  TELEGRAM_CHAT_ID=<your chat ID>   # optional: restricts bot to one user

Run (Terminal 3):
  cd solo_builder
  python telegram_bot/bot.py
"""

import asyncio
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

_ROOT        = Path(__file__).resolve().parent.parent   # solo_builder/
STATE_PATH   = _ROOT / "state" / "solo_builder_state.json"
TRIGGER_PATH = _ROOT / "state" / "run_trigger"
OUTPUTS_PATH = _ROOT / "solo_builder_outputs.md"

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")   # optional whitelist


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dag": {}, "step": 0}


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
        done = int((tv / tt) * 8) if tt else 0
        bar  = "█" * done + "░" * (8 - done)
        rows.append(f"`{task_name}` {bar} {tv}/{tt}")

    pct = round(verified / total * 100, 1) if total else 0
    header = (
        f"*Solo Builder* · Step {step}\n"
        f"✅ {verified}  ▶ {running}  ⏸ {review}  "
        f"⏳ {total - verified - running - review} / {total} ({pct}%)\n\n"
    )
    return header + "\n".join(rows)


def _allowed(update: Update) -> bool:
    return not CHAT_ID or str(update.effective_chat.id) == CHAT_ID


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text(
        "*Solo Builder Bot*\n\n"
        "/status — DAG progress summary\n"
        "/run    — trigger one step\n"
        "/export — download all Claude outputs\n"
        "/help   — this message",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text(_format_status(_load_state()), parse_mode="Markdown")


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    state = _load_state()
    dag   = state.get("dag", {})
    has_work = any(
        s.get("status") in ("Pending", "Running")
        for t in dag.values()
        for b in t["branches"].values()
        for s in b["subtasks"].values()
    )
    if not has_work:
        await update.message.reply_text("✅ Pipeline already complete.")
        return
    TRIGGER_PATH.parent.mkdir(exist_ok=True)
    TRIGGER_PATH.write_text("1")
    await update.message.reply_text(
        f"▶ Step triggered (step {state.get('step', 0)} → next)"
    )


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    if not OUTPUTS_PATH.exists():
        await update.message.reply_text(
            "No export file yet. Run `export` in the CLI first."
        )
        return
    size_kb = OUTPUTS_PATH.stat().st_size // 1024
    with OUTPUTS_PATH.open("rb") as fh:
        await update.message.reply_document(
            document=fh,
            filename="solo_builder_outputs.md",
            caption=f"Solo Builder outputs · {size_kb} KB",
        )


# ---------------------------------------------------------------------------
# Background completion poller
# ---------------------------------------------------------------------------

async def _poll_completion(app: Application) -> None:
    """Notify CHAT_ID when all subtasks reach Verified. Resets on DAG reset."""
    if not CHAT_ID:
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
                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=(
                        f"🎉 *Solo Builder complete!*\n"
                        f"{verified}/{total} subtasks verified · "
                        f"{state.get('step', 0)} steps"
                    ),
                    parse_mode="Markdown",
                )
        else:
            notified = False   # reset so we re-notify after a dag reset


async def _on_startup(app: Application) -> None:
    asyncio.create_task(_poll_completion(app))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN not set.\n"
            "1. Create a bot via @BotFather in Telegram\n"
            "2. Add TELEGRAM_BOT_TOKEN=<token> to your .env\n"
            "3. Optionally add TELEGRAM_CHAT_ID=<your chat ID> to restrict access"
        )
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(_on_startup)
        .build()
    )
    app.add_handler(CommandHandler("start",  cmd_help))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("run",    cmd_run))
    app.add_handler(CommandHandler("export", cmd_export))

    print("Solo Builder Bot started. Send /help in Telegram.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
