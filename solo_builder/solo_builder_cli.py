"""
solo_builder_cli.py
Solo Builder AI Agent CLI — main entry point.

Agents:
  Planner        → prioritizes subtasks by risk
  Executor       → advances subtask lifecycle (Pending → Running → Verified)
  ShadowAgent    → tracks expected states, detects & resolves conflicts
  Verifier       → enforces DAG consistency (branch/task status roll-up)
  SelfHealer     → detects stalled subtasks and resets them
  MetaOptimizer  → adapts heuristics, generates forecasts

CLI commands: run | snapshot | status | add_task | set KEY=VALUE | help | exit
"""

import asyncio
import logging
import logging.handlers
import os
import sys
import copy
import json
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple

# ── Path setup (allow running from project root or solo_builder/) ─────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from utils.helper_functions import (
    load_settings,
    make_bar,
    dag_stats,
    branch_stats,
    shadow_stats,
    memory_depth,
    add_memory_snapshot,
    format_status,
    format_shadow,
    validate_dag,
    # ANSI
    RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA,
    WHITE, BOLD, DIM, BLINK, RESET,
    STATUS_COLORS,
    # Alerts
    ALERT_STALLED, ALERT_PREDICTIVE, ALERT_CONFLICT, ALERT_HEALED,
)

try:
    from solo_builder_live_multi_snapshot import generate_live_multi_pdf
    _PDF_OK = True
except ImportError:
    _PDF_OK = False


# ── Load config ───────────────────────────────────────────────────────────────
_CFG_PATH = os.path.join(_HERE, "config", "settings.json")
_CFG = load_settings(_CFG_PATH)

STALL_THRESHOLD    : int   = _CFG["STALL_THRESHOLD"]
SNAPSHOT_INTERVAL  : int   = _CFG["SNAPSHOT_INTERVAL"]
STATE_PATH         : str   = _CFG.get("STATE_PATH", "./state/solo_builder_state.json")
AUTO_SAVE_INTERVAL : int   = _CFG.get("AUTO_SAVE_INTERVAL", 5)
AUTO_STEP_DELAY    : float = _CFG.get("AUTO_STEP_DELAY", 0.4)
VERBOSITY          : str   = _CFG["VERBOSITY"]
EXEC_VERIFY_PROB   : float = _CFG["EXECUTOR_VERIFY_PROBABILITY"]
CLAUDE_ALLOWED_TOOLS  : str = _CFG.get("CLAUDE_ALLOWED_TOOLS", "")
WEBHOOK_URL           : str  = _CFG.get("WEBHOOK_URL",            "")

# Read-only constants — loaded from config/loader.py; re-imported here so that
# solo_builder_cli.DAG_UPDATE_INTERVAL etc. remain accessible to injected mixins.
from config.loader import (
    DAG_UPDATE_INTERVAL, PDF_OUTPUT_PATH, BAR_WIDTH, MAX_ALERTS,
    EXEC_MAX_PER_STEP, MAX_SUBTASKS_PER_BRANCH, MAX_BRANCHES_PER_TASK,
    CLAUDE_TIMEOUT, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS, REVIEW_MODE,
    _PROJECT_CONTEXT,
)
if not os.path.isabs(STATE_PATH):
    STATE_PATH = os.path.join(_HERE, STATE_PATH)
_JOURNAL_RAW = _CFG.get("JOURNAL_PATH", "journal.md")
JOURNAL_PATH = _JOURNAL_RAW if os.path.isabs(_JOURNAL_RAW) else os.path.join(_HERE, _JOURNAL_RAW)

_LOG_PATH = os.path.join(_HERE, "state", "solo_builder.log")

# Module-level logger — handlers configured in _setup_logging() called from main()
logger = logging.getLogger("solo_builder")


# ── Journal helpers ──────────────────────────────────────────────────────────
# Kept in cli.py: tests patch solo_builder_cli.JOURNAL_PATH; extraction breaks them.
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
            return  # cache unused this session -- nothing worth logging
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
        pass  # journal write failure is non-fatal


# AGENTS (extracted to solo_builder/agents/)

# Agents and runners
from agents import Planner, ShadowAgent, Verifier, SelfHealer, MetaOptimizer
from runners import ClaudeRunner, AnthropicRunner, SdkToolRunner, Executor
from runners.cache import ResponseCache

# Extracted modules -- support both package and direct-module import modes
try:
    from .dag_definition import INITIAL_DAG
    from .display import TerminalDisplay
    from .commands.query_cmds import QueryCommandsMixin
    from .commands.subtask_cmds import SubtaskCommandsMixin
    from .commands.dag_cmds import DagCommandsMixin
    from .commands.settings_cmds import SettingsCommandsMixin
    from .commands.dispatcher import DispatcherMixin
    from .commands.auto_cmds import AutoCommandsMixin
    from .commands.step_runner import StepRunnerMixin
    from .cli_utils import (
        _setup_logging, _splash, _acquire_lock, _release_lock,
        _handle_status_subcommand, _handle_watch_subcommand,
    )
except ImportError:
    from dag_definition import INITIAL_DAG
    from display import TerminalDisplay
    from commands.query_cmds import QueryCommandsMixin
    from commands.subtask_cmds import SubtaskCommandsMixin
    from commands.dag_cmds import DagCommandsMixin
    from commands.settings_cmds import SettingsCommandsMixin
    from commands.dispatcher import DispatcherMixin
    from commands.auto_cmds import AutoCommandsMixin
    from commands.step_runner import StepRunnerMixin
    from cli_utils import (
        _setup_logging, _splash, _acquire_lock, _release_lock,
        _handle_status_subcommand, _handle_watch_subcommand,
        _load_dotenv, _build_arg_parser, _clear_stale_triggers, _emit_json_result,
    )


class SoloBuilderCLI(DispatcherMixin, AutoCommandsMixin, StepRunnerMixin,
                     QueryCommandsMixin, SubtaskCommandsMixin, DagCommandsMixin,
                     SettingsCommandsMixin):
    """
    Orchestrates all agents and handles the interactive CLI loop.

    Step lifecycle:
        Planner → ShadowAgent (conflicts) → SelfHealer → Executor
        → Verifier → ShadowAgent (update expected) → MetaOptimizer → display
    """

    def __init__(self) -> None:
        self.dag          = copy.deepcopy(INITIAL_DAG)
        self.memory_store = {
            branch: []
            for task_data in self.dag.values()
            for branch in task_data.get("branches", {})
        }
        self.step             = 0
        self.snapshot_counter = 0
        self.alerts: List[str] = []
        self._priority_cache: List = []
        self._last_priority_step: int = -(DAG_UPDATE_INTERVAL + 1)  # force first run
        self._last_verified_tasks: int = 0   # triggers cache refresh when a task unblocks

        # Agents
        self.planner  = Planner(stall_threshold=STALL_THRESHOLD)
        self.executor = Executor(max_per_step=EXEC_MAX_PER_STEP,
                                 verify_prob=EXEC_VERIFY_PROB,
                                 project_context=_PROJECT_CONTEXT,
                                 append_journal=_append_journal)
        self.shadow   = ShadowAgent()
        self.verifier = Verifier()
        self.healer   = SelfHealer(stall_threshold=STALL_THRESHOLD)
        self.meta     = MetaOptimizer()
        self.display  = TerminalDisplay(bar_width=BAR_WIDTH,
                                        stall_threshold=STALL_THRESHOLD)
        self.running  = True

        # Mutable runtime config — mirrors the 8 module globals that _cmd_set
        # may change at runtime.  Written alongside the module globals so that
        # code inspecting self._runtime_cfg always sees the current values.
        # This is step 1 of TD-ARCH-001 Phase 2b: the dict is the prerequisite
        # for moving _cmd_set to commands/dispatcher.py without circular imports.
        self._runtime_cfg: dict = {
            "STALL_THRESHOLD":     STALL_THRESHOLD,
            "SNAPSHOT_INTERVAL":   SNAPSHOT_INTERVAL,
            "VERBOSITY":           VERBOSITY,
            "EXEC_VERIFY_PROB":    EXEC_VERIFY_PROB,
            "AUTO_STEP_DELAY":     AUTO_STEP_DELAY,
            "AUTO_SAVE_INTERVAL":  AUTO_SAVE_INTERVAL,
            "CLAUDE_ALLOWED_TOOLS": CLAUDE_ALLOWED_TOOLS,
            "WEBHOOK_URL":         WEBHOOK_URL,
        }

        os.makedirs(PDF_OUTPUT_PATH, exist_ok=True)

        # Validate initial DAG
        warnings = validate_dag(self.dag)
        for w in warnings:
            print(f"{YELLOW}[DAG Warning] {w}{RESET}")

    # ── Snapshot ──────────────────────────────────────────────────────────────
    # Kept in cli.py so that test patches on _PDF_OK resolve correctly.
    def _take_snapshot(self, auto: bool = False) -> None:
        if not _PDF_OK:
            print(f"{YELLOW}PDF unavailable — install matplotlib.{RESET}")
            return
        self.snapshot_counter += 1
        fname = os.path.join(
            PDF_OUTPUT_PATH,
            f"Solo_Builder_Timeline_{self.snapshot_counter:04d}.pdf",
        )
        try:
            generate_live_multi_pdf(self.dag, self.memory_store, fname)
            tag = "AUTO" if auto else "MANUAL"
            print(f"  {GREEN}[{tag}] Snapshot → {fname}{RESET}")
        except Exception as exc:
            print(f"  {RED}Snapshot failed: {exc}{RESET}")

    # ── Settings mutator ─────────────────────────────────────────────────────
    # Kept in cli.py so that `global X; X = val` writes to this module's globals,
    # and _persist_setting reads _CFG_PATH from this module (where tests patch it).
    def _persist_setting(self, cfg_key: str, value) -> None:
        """Silently write one key back to config/settings.json."""
        import json as _json
        try:
            with open(_CFG_PATH, encoding="utf-8") as f:
                cfg = _json.load(f)
            cfg[cfg_key] = value
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                _json.dump(cfg, f, indent=4)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
# ── Global injection ─────────────────────────────────────────────────────────
# Mixin methods look up names in their defining module's globals. Inject all
# uppercase names from this module into each mixin module so that references
# to STATE_PATH, MAX_BRANCHES_PER_TASK, etc. resolve correctly — including
# after runtime mutations from _cmd_set (both point to the same dict object).
#
# ⚠ TEST-PATCH CONSTRAINT — see docs/dev_notes.md for the full explanation:
#   setdefault() copies values ONCE at load time. Test patches on
#   `solo_builder_cli.FOO` do NOT propagate into mixin modules.
#   Functions reading any of these 5 globals MUST stay in this file:
#     _PDF_OK       → _take_snapshot
#     _CFG_PATH     → _persist_setting
#     STATE_PATH    → load_state / save_state  (in step_runner but re-injected)
#     JOURNAL_PATH  → _append_journal / _append_cache_session_stats
#     WEBHOOK_URL   → _fire_completion / main()
#
# NOTE — direct-import constants (setdefault is a no-op for these):
#   DAG_UPDATE_INTERVAL, MAX_ALERTS  → step_runner.py imports from config.loader
#   BAR_WIDTH, DAG_UPDATE_INTERVAL   → auto_cmds.py imports from config.loader
#   These names are already bound before injection runs; setdefault skips them.
def _inject_host_globals_into_mixins():
    """Inject host module globals into mixin modules so their methods resolve names correctly."""
    import sys as _s
    _host_globals = vars(_s.modules[__name__])
    _skip = frozenset({'__builtins__', '__spec__', '__loader__', '__package__'})
    for _mod_name in list(_s.modules):
        if _mod_name.endswith(('query_cmds', 'subtask_cmds', 'dag_cmds', 'settings_cmds',
                               'dispatcher', 'auto_cmds', 'step_runner', 'cli_utils')):
            _target = vars(_s.modules[_mod_name])
            for _k, _v in list(_host_globals.items()):
                if _k not in _skip and not _k.startswith('__'):
                    _target.setdefault(_k, _v)

_inject_host_globals_into_mixins()


def _fire_completion(steps: int, verified: int, total: int) -> None:
    """Non-blocking: POST webhook and/or Windows toast on pipeline completion."""
    import threading

    def _webhook() -> None:
        if not WEBHOOK_URL:
            return
        if not WEBHOOK_URL.startswith(("http://", "https://")):
            return
        try:
            import urllib.request, urllib.error
            payload = json.dumps({
                "event": "complete", "steps": steps,
                "verified": verified, "total": total,
            }).encode()
            req = urllib.request.Request(
                WEBHOOK_URL, data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)  # noqa: S310  # nosec B310
        except Exception as exc:
            # Log failures — silent to the user but auditable
            try:
                import datetime
                _log = os.path.join(_HERE, "state", "webhook_errors.log")
                with open(_log, "a", encoding="utf-8") as _wf:
                    _wf.write(
                        f"{datetime.datetime.now(datetime.timezone.utc).isoformat()} "
                        f"POST {WEBHOOK_URL!r} failed: {exc}\n"
                    )
            except Exception:
                pass

    def _notify() -> None:
        try:
            msg = f"Solo Builder: {verified}/{total} verified in {steps} steps"
            subprocess.Popen(
                ["powershell.exe", "-WindowStyle", "Hidden", "-Command",
                 f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null;'
                 f'[System.Windows.Forms.MessageBox]::Show("{msg}", "Solo Builder Complete")'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    threading.Thread(target=_webhook, daemon=True).start()
    threading.Thread(target=_notify,  daemon=True).start()


def main() -> None:
    """Entry point — interactive or headless."""
    # ── status subcommand (fast path, no lock needed) ────────────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        _handle_status_subcommand(os.path.join(_HERE, "state", "solo_builder_state.json"))
        return

    # ── watch subcommand (live progress bar, no lock needed) ─────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        _interval = 2.0
        if len(sys.argv) > 2:
            try:
                _interval = float(sys.argv[2])
            except ValueError:
                pass
        _handle_watch_subcommand(
            os.path.join(_HERE, "state", "solo_builder_state.json"), _interval
        )
        return

    _load_dotenv(_HERE)

    # ── Argument parsing ─────────────────────────────────────────────────────
    args = _build_arg_parser().parse_args()

    # ── Apply flag overrides ─────────────────────────────────────────────────
    if args.webhook:
        global WEBHOOK_URL
        WEBHOOK_URL = args.webhook

    _json_mode  = args.headless and args.output_format == "json"
    _quiet_mode = args.headless and args.quiet
    _null_fh    = None
    if _quiet_mode:
        _null_fh   = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = _null_fh         # silence stderr first
    if _json_mode:
        sys.stdout = sys.stderr       # ANSI display → (possibly devnull) stderr; JSON → real stdout

    # ── Run ──────────────────────────────────────────────────────────────────
    _LOCK_PATH = _clear_stale_triggers(_HERE, _LOG_PATH)
    logger.info("startup version=2.1.50 headless=%s auto=%s", args.headless, args.auto)
    _acquire_lock(_LOCK_PATH)
    cli = None

    # Graceful SIGTERM handler — save state then exit cleanly
    import signal as _signal
    def _sigterm_handler(signum, frame):
        if cli is not None:
            try:
                cli.save_state(silent=True)
            except Exception:
                pass
        _release_lock(_LOCK_PATH)
        sys.exit(0)
    _signal.signal(_signal.SIGTERM, _sigterm_handler)

    try:
        _splash(_PDF_OK)
        cli = SoloBuilderCLI()
        cli.start(
            headless=args.headless,
            auto_steps=args.auto,
            no_resume=args.no_resume,
        )
    except Exception as _exc:
        logger.error("unhandled_exception error=%s", _exc, exc_info=True)
        raise
    finally:
        if cli is not None:
            logger.info("shutdown step=%d", cli.step)
        _export_path, _export_count = (None, 0)
        if args.export and cli is not None:
            _export_path, _export_count = cli._cmd_export()
        _release_lock(_LOCK_PATH)
        if cli is not None:
            _append_cache_session_stats(
                getattr(cli.executor.anthropic, "cache", None),
                cli.step,
            )
        if _quiet_mode:
            sys.stderr = sys.__stderr__
            if _null_fh:
                _null_fh.close()
        if _json_mode:
            sys.stdout = sys.__stdout__
            if cli is not None:
                _emit_json_result(cli, args, _export_path, _export_count)


if __name__ == "__main__":
    main()
