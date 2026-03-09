"""CLI utility functions for Solo Builder — extracted from solo_builder_cli.py."""
import json
import os
import sys
import time
import logging
import logging.handlers

from utils.helper_functions import BOLD, CYAN, GREEN, RESET, YELLOW, dag_stats


def _setup_logging(log_path: str) -> None:
    """Configure a rotating file handler for structured log output."""
    _logger = logging.getLogger("solo_builder")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    _logger.propagate = False


def _splash(pdf_ok: bool) -> None:
    lines = [
        "╔══════════════════════════════════════════════════════╗",
        "║      SOLO BUILDER — AI AGENT CLI  v2.1               ║",
        "║                                                       ║",
        "║  DAG · Shadow · Self-Heal · Auto-Run · Persistence   ║",
        "╚══════════════════════════════════════════════════════╝",
    ]
    print(f"\n{BOLD}{CYAN}")
    for line in lines:
        print(f"  {line}")
    print(RESET)

    if not pdf_ok:
        print(f"  {YELLOW}[!] matplotlib not found — PDF snapshots disabled.")
        print(f"      Install with: pip install matplotlib{RESET}\n")
    time.sleep(0.6)


def _acquire_lock(lock_path: str) -> None:
    """Write a PID lockfile; exit if another instance is already running."""
    if os.path.exists(lock_path):
        try:
            pid = int(open(lock_path).read().strip())
            os.kill(pid, 0)          # Raises if process doesn't exist
            print(f"\n  Solo Builder is already running (PID {pid}).")
            print(f"  If that process is stale, delete {lock_path} and retry.\n")
            sys.exit(1)
        except (ProcessLookupError, PermissionError):
            os.remove(lock_path)     # Stale lock — clean up
    with open(lock_path, "w") as f:
        f.write(str(os.getpid()))


def _release_lock(lock_path: str) -> None:
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass


def _append_journal(
    st_name: str, task_name: str, branch_name: str,
    description: str, output: str, step: int,
) -> None:
    """Append one verified Claude result to the journal file."""
    parent = os.path.dirname(JOURNAL_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    exists = os.path.exists(JOURNAL_PATH)
    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        if not exists:
            f.write("# Solo Builder -- Live Journal\n\n")
        f.write(f"## {st_name} · {task_name} / {branch_name} · Step {step}\n\n")
        if description:
            f.write(f"**Prompt:** {description}\n\n")
        f.write(f"{output}\n\n---\n\n")


def _append_cache_session_stats(cache, steps: int) -> None:
    """Append per-session ResponseCache hit/miss summary to the journal.

    Only writes if the cache was consulted at least once this session.
    Silently skips if cache is None or the journal cannot be written.
    """
    if cache is None:
        return
    try:
        cache.persist_stats()
        s = cache.stats()
        total = s["hits"] + s["misses"]
        if total == 0:
            return
        hit_rate = s["hits"] / total * 100
        cum_total = s["cumulative_hits"] + s["cumulative_misses"]
        cum_rate = s["cumulative_hits"] / cum_total * 100 if cum_total else 0.0
        parent = os.path.dirname(JOURNAL_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        exists = os.path.exists(JOURNAL_PATH)
        with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
            if not exists:
                f.write("# Solo Builder -- Live Journal\n\n")
            f.write(
                f"## Cache session summary · Step {steps}\n\n"
                f"| Metric | Value |\n"
                f"|--------|-------|\n"
                f"| Hits (session) | {s['hits']} |\n"
                f"| Misses (session) | {s['misses']} |\n"
                f"| Hit rate (session) | {hit_rate:.1f}% |\n"
                f"| Hits (all-time) | {s['cumulative_hits']:,} |\n"
                f"| Misses (all-time) | {s['cumulative_misses']:,} |\n"
                f"| Hit rate (all-time) | {cum_rate:.1f}% |\n"
                f"| Entries on disk | {s['size']} |\n"
                f"| Est. tokens saved | {s['estimated_tokens_saved']:,} |\n"
                f"\n---\n\n"
            )
    except Exception:
        pass


def _handle_status_subcommand(state_path: str) -> None:
    """Fast-path 'status' subcommand: print JSON summary from state file and exit."""
    if not os.path.exists(state_path):
        print(json.dumps({"error": "no state file"}))
        return
    with open(state_path) as f:
        state = json.load(f)
    s    = dag_stats(state.get("dag", {}))
    step = state.get("step", 0)
    pct  = round(s["verified"] / s["total"] * 100, 1) if s["total"] else 0.0
    print(json.dumps({
        "step":     step,
        "verified": s["verified"],
        "running":  s["running"],
        "pending":  s["pending"],
        "total":    s["total"],
        "pct":      pct,
        "complete": s["verified"] == s["total"],
    }))


def _handle_watch_subcommand(state_path: str, interval: float = 2.0) -> None:
    """Live 'watch' subcommand: print progress bar on a loop until complete or Ctrl+C."""
    print(f"  Watching pipeline every {interval}s  (Ctrl+C to stop)", flush=True)
    try:
        while True:
            if not os.path.exists(state_path):
                print("\r  No state file — start the CLI first.                    ",
                      end="", flush=True)
            else:
                try:
                    with open(state_path) as f:
                        wstate = json.load(f)
                except (json.JSONDecodeError, OSError):
                    time.sleep(interval)
                    continue
                s    = dag_stats(wstate.get("dag", {}))
                step = wstate.get("step", 0)
                pct  = round(s["verified"] / s["total"] * 100, 1) if s["total"] else 0.0
                bar  = ("=" * int(pct / 5)).ljust(20, "-")
                if s["verified"] == s["total"]:
                    print(f"\r  {GREEN}Complete!{RESET} "
                          f"{s['verified']}/{s['total']} verified in {step} steps.            ")
                    break
                print(
                    f"\r  Step {step:3d}  [{bar}]  "
                    f"{GREEN}{s['verified']:3d}✓{RESET}  "
                    f"{CYAN}{s['running']:2d}▶{RESET}  "
                    f"{YELLOW}{s['pending']:3d}●{RESET}  "
                    f"{pct:5.1f}%",
                    end="", flush=True,
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        print()
