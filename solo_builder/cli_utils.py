"""CLI utility functions for Solo Builder — extracted from solo_builder_cli.py."""
import json
import os
import sys
import time
import logging
import logging.handlers

from utils.helper_functions import BOLD, CYAN, GREEN, RESET, YELLOW, dag_stats  # noqa: dag_stats used by _handle_watch/_status


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
