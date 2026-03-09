"""CLI utility functions for Solo Builder — extracted from solo_builder_cli.py."""
import os
import sys
import time
import logging
import logging.handlers

from utils.helper_functions import BOLD, CYAN, RESET, YELLOW


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
