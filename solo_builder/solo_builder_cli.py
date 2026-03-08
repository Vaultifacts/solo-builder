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

import argparse
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
DAG_UPDATE_INTERVAL: int   = _CFG["DAG_UPDATE_INTERVAL"]
PDF_OUTPUT_PATH    : str   = _CFG["PDF_OUTPUT_PATH"]
STATE_PATH         : str   = _CFG.get("STATE_PATH", "./state/solo_builder_state.json")
AUTO_SAVE_INTERVAL : int   = _CFG.get("AUTO_SAVE_INTERVAL", 5)
AUTO_STEP_DELAY    : float = _CFG.get("AUTO_STEP_DELAY", 0.4)
VERBOSITY          : str   = _CFG["VERBOSITY"]
BAR_WIDTH          : int   = _CFG["BAR_WIDTH"]
MAX_ALERTS         : int   = _CFG["MAX_ALERTS"]
EXEC_MAX_PER_STEP  : int   = _CFG["EXECUTOR_MAX_PER_STEP"]
EXEC_VERIFY_PROB   : float = _CFG["EXECUTOR_VERIFY_PROBABILITY"]
MAX_SUBTASKS_PER_BRANCH: int = _CFG.get("MAX_SUBTASKS_PER_BRANCH", 20)
MAX_BRANCHES_PER_TASK  : int = _CFG.get("MAX_BRANCHES_PER_TASK",   10)
CLAUDE_TIMEOUT        : int = _CFG.get("CLAUDE_TIMEOUT", 60)
CLAUDE_ALLOWED_TOOLS  : str = _CFG.get("CLAUDE_ALLOWED_TOOLS", "")
ANTHROPIC_MODEL       : str  = _CFG.get("ANTHROPIC_MODEL",      "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS  : int  = _CFG.get("ANTHROPIC_MAX_TOKENS", 300)
REVIEW_MODE           : bool = bool(_CFG.get("REVIEW_MODE",       False))
WEBHOOK_URL           : str  = _CFG.get("WEBHOOK_URL",            "")

# One-liner context injected at the front of every Claude prompt so the model
# knows what project it is working within, avoiding "I don't know what X is"
_PROJECT_CONTEXT = (
    "Context: Solo Builder is a Python terminal CLI that uses six AI agents "
    "(Planner, ShadowAgent, SelfHealer, Executor, Verifier, MetaOptimizer) "
    "and the Anthropic SDK to manage DAG-based software project tasks. "
)

# Resolve relative paths to script location
if not os.path.isabs(PDF_OUTPUT_PATH):
    PDF_OUTPUT_PATH = os.path.join(_HERE, PDF_OUTPUT_PATH)
if not os.path.isabs(STATE_PATH):
    STATE_PATH = os.path.join(_HERE, STATE_PATH)
_JOURNAL_RAW = _CFG.get("JOURNAL_PATH", "journal.md")
JOURNAL_PATH = _JOURNAL_RAW if os.path.isabs(_JOURNAL_RAW) else os.path.join(_HERE, _JOURNAL_RAW)

_LOG_PATH = os.path.join(_HERE, "state", "solo_builder.log")

# Module-level logger — handlers configured in _setup_logging() called from main()
logger = logging.getLogger("solo_builder")


def _setup_logging() -> None:
    """Configure a rotating file handler for structured log output."""
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False



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
except ImportError:
    from dag_definition import INITIAL_DAG
    from display import TerminalDisplay
    from commands.query_cmds import QueryCommandsMixin
    from commands.subtask_cmds import SubtaskCommandsMixin
    from commands.dag_cmds import DagCommandsMixin
    from commands.settings_cmds import SettingsCommandsMixin


class SoloBuilderCLI(QueryCommandsMixin, SubtaskCommandsMixin, DagCommandsMixin, SettingsCommandsMixin):
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

        os.makedirs(PDF_OUTPUT_PATH, exist_ok=True)

        # Validate initial DAG
        warnings = validate_dag(self.dag)
        for w in warnings:
            print(f"{YELLOW}[DAG Warning] {w}{RESET}")

    # ── Step ────────────────────────────────────────────────────────────────
    def run_step(self) -> None:
        """Execute one full agent pipeline step."""
        self.step += 1
        step_alerts: List[str] = []

        # 1. Planner: prioritize (re-runs every DAG_UPDATE_INTERVAL steps,
        #    or immediately when a task flips to Verified — which unblocks dependents)
        verified_tasks = sum(
            1 for t in self.dag.values() if t.get("status") == "Verified"
        )
        if (self.step - self._last_priority_step) >= DAG_UPDATE_INTERVAL \
                or verified_tasks > self._last_verified_tasks:
            self._priority_cache     = self.planner.prioritize(self.dag, self.step)
            self._last_priority_step = self.step
            self._last_verified_tasks = verified_tasks
        priority = self._priority_cache

        # 2. ShadowAgent: detect and resolve conflicts
        conflicts = self.shadow.detect_conflicts(self.dag)
        for task_name, branch_name, st_name in conflicts:
            step_alerts.append(
                f"  {ALERT_CONFLICT} {CYAN}{st_name}{RESET}: "
                f"shadow/status mismatch → resolving"
            )
            self.shadow.resolve_conflict(
                self.dag, task_name, branch_name, st_name,
                self.step, self.memory_store,
            )

        # 3. SelfHealer: detect stalls (alert before healing)
        stalled = self.healer.find_stalled(self.dag, self.step)
        for _, _, st_name, age in stalled:
            step_alerts.append(
                f"  {ALERT_STALLED} {CYAN}{st_name}{RESET} stalled {age} steps"
            )
        healed = self.healer.heal(
            self.dag, stalled, self.step, self.memory_store, step_alerts
        )

        # 4. Executor: advance subtasks
        actions = self.executor.execute_step(
            self.dag, priority, self.step, self.memory_store
        )

        # 5. Verifier: fix any status inconsistencies
        fixes = self.verifier.verify(self.dag)
        if VERBOSITY == "DEBUG":
            for fix in fixes:
                step_alerts.append(f"  {DIM}Verifier: {fix}{RESET}")

        # 6. ShadowAgent: update expected state map
        self.shadow.update_expected(self.dag)

        # 7. MetaOptimizer: record + maybe adjust weights
        verified_count = sum(1 for a in actions.values() if a == "verified")
        self.meta.record(healed, verified_count)
        opt_note = self.meta.optimize(self.planner)
        if opt_note and VERBOSITY == "DEBUG":
            step_alerts.append(f"  {DIM}{opt_note}{RESET}")

        # 8. Auto-snapshot
        if self.step % SNAPSHOT_INTERVAL == 0:
            self._take_snapshot(auto=True)

        # 9. Auto-save state
        if self.step % AUTO_SAVE_INTERVAL == 0:
            self.save_state(silent=True)

        # Heartbeat: write live counters every step for Discord bot real-time tracking
        _hb = os.path.join(_HERE, "state", "step.txt")
        try:
            _hb_v = _hb_t = _hb_p = _hb_r = _hb_rv = 0
            for _ht in self.dag.values():
                for _hb2 in _ht["branches"].values():
                    for _hs in _hb2["subtasks"].values():
                        _hb_t += 1
                        _st = _hs.get("status", "")
                        if _st == "Verified":  _hb_v  += 1
                        elif _st == "Pending": _hb_p  += 1
                        elif _st == "Running": _hb_r  += 1
                        elif _st == "Review":  _hb_rv += 1
            with open(_hb, "w") as _f:
                _f.write(f"{self.step},{_hb_v},{_hb_t},{_hb_p},{_hb_r},{_hb_rv}")
        except OSError:
            pass

        # Accumulate alerts
        self.alerts = (self.alerts + step_alerts)[-MAX_ALERTS:]

        # Render
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    # ── Snapshot ────────────────────────────────────────────────────────────
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

    # ── Persistence ──────────────────────────────────────────────────────────
    def save_state(self, silent: bool = False) -> None:
        """Serialize full runtime state to JSON on disk."""
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        # Rotate backups: .3 → delete, .2 → .3, .1 → .2, current → .1
        if os.path.exists(STATE_PATH):
            for i in range(3, 1, -1):
                src = f"{STATE_PATH}.{i - 1}"
                dst = f"{STATE_PATH}.{i}"
                if os.path.exists(src):
                    try:
                        os.replace(src, dst)
                    except OSError:
                        pass
            try:
                import shutil
                shutil.copy2(STATE_PATH, f"{STATE_PATH}.1")
            except OSError:
                pass
        payload = {
            "step":             self.step,
            "snapshot_counter": self.snapshot_counter,
            "healed_total":     self.healer.healed_total,
            "dag":              self.dag,
            "memory_store":     self.memory_store,
            "alerts":           self.alerts,
            "meta_history":     self.meta._history,
        }
        try:
            # Atomic write: serialize to temp file then replace — prevents corruption
            # if the process is killed mid-write (multiple surfaces read STATE_PATH)
            tmp_path = STATE_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, STATE_PATH)
            logger.info("state_saved step=%d path=%s", self.step, STATE_PATH)
            if not silent:
                print(f"  {GREEN}State saved → {STATE_PATH}{RESET}")
        except Exception as exc:
            logger.error("state_save_failed step=%d error=%s", self.step, exc)
            print(f"  {RED}Save failed: {exc}{RESET}")

    def load_state(self) -> bool:
        """
        Load state from disk into this instance.
        Returns True if loaded successfully, False otherwise.
        """
        if not os.path.exists(STATE_PATH):
            return False
        # Try primary state file; on JSON corruption fall back to most recent backup
        paths_to_try = [STATE_PATH] + [f"{STATE_PATH}.{n}" for n in (1, 2, 3)]
        for attempt_path in paths_to_try:
            if not os.path.exists(attempt_path):
                continue
            try:
                with open(attempt_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if attempt_path != STATE_PATH:
                    logger.warning("state_recovered from=%s", attempt_path)
                    print(f"  {YELLOW}Primary state corrupt — recovered from {attempt_path}{RESET}")
                self.step             = payload["step"]
                self.snapshot_counter = payload["snapshot_counter"]
                self.healer.healed_total = payload["healed_total"]
                self.dag              = payload["dag"]
                self.memory_store     = payload["memory_store"]
                self.alerts           = payload["alerts"]
                self.meta._history    = payload.get("meta_history", [])
                # Rebuild MetaOptimizer rolling rates
                if self.meta._history:
                    window = min(10, len(self.meta._history))
                    recent = self.meta._history[-window:]
                    self.meta.heal_rate   = sum(r["healed"]   for r in recent) / window
                    self.meta.verify_rate = sum(r["verified"] for r in recent) / window
                # Rebuild ShadowAgent expected state map
                self.shadow.update_expected(self.dag)
                logger.info("state_loaded step=%d path=%s", self.step, attempt_path)
                return True
            except (json.JSONDecodeError, KeyError):
                if attempt_path == STATE_PATH:
                    logger.warning("state_corrupt path=%s trying_backups=True", attempt_path)
                    print(f"  {YELLOW}State file corrupt — trying backups…{RESET}")
                continue
            except Exception as exc:
                logger.error("state_load_failed path=%s error=%s", attempt_path, exc)
                print(f"  {RED}Load failed: {exc}{RESET}")
                return False
        print(f"  {RED}All state files corrupt or missing — starting fresh.{RESET}")
        return False

    def _consume_json_trigger(path: str):
        """Read, parse, and atomically delete a JSON trigger file.

        Returns the parsed dict/list on success, or *None* if the file
        doesn't exist or can't be read.
        """
        if not os.path.exists(path):
            return None
        try:
            data = json.loads(open(path, encoding="utf-8").read())
            os.remove(path)
            return data
        except Exception:
            return None

    # ── Auto-run ─────────────────────────────────────────────────────────────
    def _cmd_auto(self, args: str) -> None:
        """
        auto [N] — run N steps automatically (default: until COMPLETE).
        Speed controlled by AUTO_STEP_DELAY seconds between steps.
        Press Ctrl+C to pause.
        """
        global AUTO_STEP_DELAY
        try:
            limit = int(args.strip()) if args.strip() else None
        except ValueError:
            print(f"  {YELLOW}Usage: auto [N]  (N = number of steps){RESET}")
            return

        stats = dag_stats(self.dag)
        if stats["verified"] == stats["total"]:
            print(f"  {GREEN}DAG already complete. Reset with 'reset' or add tasks.{RESET}")
            time.sleep(1)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )
            return

        ran    = 0
        label  = f"{limit} steps" if limit else "until complete"
        print(f"  {CYAN}Auto-run: {label}  │  delay={AUTO_STEP_DELAY}s  │  Ctrl+C to pause{RESET}")
        time.sleep(0.6)

        _trigger     = os.path.join(_HERE, "state", "run_trigger")
        _stoptrig    = os.path.join(_HERE, "state", "stop_trigger")
        _attrigger   = os.path.join(_HERE, "state", "add_task_trigger.json")
        _abtrigger   = os.path.join(_HERE, "state", "add_branch_trigger.json")
        _pbtrigger   = os.path.join(_HERE, "state", "prioritize_branch_trigger.json")
        _dtrigger    = os.path.join(_HERE, "state", "describe_trigger.json")
        _rntrigger   = os.path.join(_HERE, "state", "rename_trigger.json")
        _ttrigger    = os.path.join(_HERE, "state", "tools_trigger.json")
        _rtrigger    = os.path.join(_HERE, "state", "reset_trigger")
        _snaptrigger = os.path.join(_HERE, "state", "snapshot_trigger")
        _settrigger  = os.path.join(_HERE, "state", "set_trigger.json")
        _deptrigger  = os.path.join(_HERE, "state", "depends_trigger.json")
        _undeptrigger = os.path.join(_HERE, "state", "undepends_trigger.json")
        _undotrigger  = os.path.join(_HERE, "state", "undo_trigger")
        _pausetrigger = os.path.join(_HERE, "state", "pause_trigger")
        _healtrigger  = os.path.join(_HERE, "state", "heal_trigger.json")
        _dagimptrigger = os.path.join(_HERE, "state", "dag_import_trigger.json")
        try:
            while True:
                self.run_step()
                ran += 1

                stats = dag_stats(self.dag)
                if stats["verified"] == stats["total"]:
                    self.save_state(silent=True)   # flush JSON before bot reads it
                    _fire_completion(self.step, stats["verified"], stats["total"])
                    time.sleep(1.2)
                    break

                if limit is not None and ran >= limit:
                    break

                # Honour external triggers (dashboard Run Step, Discord/Telegram verify)
                # NOTE: check verify_trigger BEFORE breaking on run_trigger so that
                # external verify requests aren't skipped when auto-mode is running.
                _waited  = 0.0
                _stopped = False
                _vtrigger = os.path.join(_HERE, "state", "verify_trigger.json")
                while _waited < AUTO_STEP_DELAY:
                    if os.path.exists(_stoptrig):
                        try:
                            os.remove(_stoptrig)
                        except OSError:
                            pass
                        _stopped = True
                        break
                    # Pause gate: spin while pause_trigger exists (don't advance _waited)
                    while os.path.exists(_pausetrigger):
                        if _waited < 0.05:  # first detection — print once
                            print(f"  {YELLOW}Auto-run paused remotely. Waiting for resume…{RESET}", flush=True)
                            _waited = 0.05
                        time.sleep(0.2)
                        # Still honour stop during pause
                        if os.path.exists(_stoptrig):
                            break
                    vdata = self._consume_json_trigger(_vtrigger)
                    if vdata:
                        for e in (vdata if isinstance(vdata, list) else [vdata]):
                            self._cmd_verify(
                                f"{e.get('subtask', '')} {e.get('note', 'Discord verify')}"
                            )
                    adata = self._consume_json_trigger(_attrigger)
                    if adata:
                        spec = adata.get("spec", "").strip()
                        if spec:
                            self._cmd_add_task(spec)
                    abdata = self._consume_json_trigger(_abtrigger)
                    if abdata:
                        task_arg = abdata.get("task", "").strip()
                        spec     = abdata.get("spec", "").strip()
                        if task_arg and spec:
                            self._cmd_add_branch(task_arg, spec_override=spec)
                    pbdata = self._consume_json_trigger(_pbtrigger)
                    if pbdata:
                        pb_task   = pbdata.get("task", "").strip()
                        pb_branch = pbdata.get("branch", "").strip()
                        if pb_task and pb_branch:
                            self._cmd_prioritize_branch(pb_task, pb_branch)
                    ddata = self._consume_json_trigger(_dtrigger)
                    if ddata:
                        d_st   = ddata.get("subtask", "").strip().upper()
                        d_desc = ddata.get("desc", "").strip()
                        if d_st and d_desc:
                            self._cmd_describe(f"{d_st} {d_desc}")
                    rndata = self._consume_json_trigger(_rntrigger)
                    if rndata:
                        rn_st   = rndata.get("subtask", "").strip().upper()
                        rn_desc = rndata.get("desc", "").strip()
                        if rn_st and rn_desc:
                            self._cmd_rename(f"{rn_st} {rn_desc}")
                    tdata = self._consume_json_trigger(_ttrigger)
                    if tdata:
                        t_st    = tdata.get("subtask", "").strip().upper()
                        t_tools = tdata.get("tools", "").strip()
                        if t_st and t_tools:
                            self._cmd_tools(f"{t_st} {t_tools}")
                    sdata = self._consume_json_trigger(_settrigger)
                    if sdata:
                        s_key = sdata.get("key", "").strip()
                        s_val = sdata.get("value", "").strip()
                        if s_key and s_val:
                            self._cmd_set(f"{s_key}={s_val}")
                    healdata = self._consume_json_trigger(_healtrigger)
                    if healdata:
                        h_st = healdata.get("subtask", "").strip().upper()
                        if h_st:
                            self._cmd_heal(h_st)
                    depdata = self._consume_json_trigger(_deptrigger)
                    if depdata:
                        dep_target = depdata.get("target", "").strip()
                        dep_dep    = depdata.get("dep", "").strip()
                        if dep_target and dep_dep:
                            self._cmd_depends(f"{dep_target} {dep_dep}")
                    if os.path.exists(_undeptrigger):
                        try:
                            uddata = json.loads(
                                open(_undeptrigger, encoding="utf-8").read()
                            )
                            os.remove(_undeptrigger)
                            ud_target = uddata.get("target", "").strip()
                            ud_dep    = uddata.get("dep", "").strip()
                            if ud_target and ud_dep:
                                self._cmd_undepends(f"{ud_target} {ud_dep}")
                        except Exception:
                            pass
                    if os.path.exists(_rtrigger):
                        try:
                            os.remove(_rtrigger)
                        except OSError:
                            pass
                        self._cmd_reset()
                    if os.path.exists(_snaptrigger):
                        try:
                            os.remove(_snaptrigger)
                        except OSError:
                            pass
                        self._take_snapshot(auto=False)
                    if os.path.exists(_undotrigger):
                        try:
                            os.remove(_undotrigger)
                        except OSError:
                            pass
                        self._cmd_undo()
                    dagimpdata = self._consume_json_trigger(_dagimptrigger)
                    if dagimpdata and isinstance(dagimpdata.get("dag"), dict):
                        errors = validate_dag(dagimpdata["dag"])
                        if not errors:
                            self.save_state(silent=True)
                            self.dag = dagimpdata["dag"]
                            self.shadow.update_expected(self.dag)
                            self._last_priority_step = -(DAG_UPDATE_INTERVAL + 1)
                            src = dagimpdata.get("exported_step", "?")
                            print(f"  {GREEN}DAG imported via trigger (exported at step {src}){RESET}")
                            logger.info("dag_imported_via_trigger src_step=%s", src)
                    if os.path.exists(_trigger):
                        try:
                            os.remove(_trigger)
                        except OSError:
                            pass
                        break
                    time.sleep(0.05)
                    _waited += 0.05

                if _stopped:
                    print(f"\n  {YELLOW}Auto-run stopped remotely at step {self.step}.{RESET}")
                    time.sleep(0.5)
                    self.display.render(
                        self.dag, self.memory_store, self.step,
                        self.alerts, self.meta.forecast(self.dag),
                    )
                    break

        except KeyboardInterrupt:
            print(f"\n  {YELLOW}Auto-run paused at step {self.step}.{RESET}")
            time.sleep(0.5)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

    # ── Command dispatcher ───────────────────────────────────────────────────
    def handle_command(self, raw: str) -> None:
        raw = raw.strip()
        cmd = raw.lower()

        if cmd == "run":
            self.run_step()

        elif cmd.startswith("auto"):
            self._cmd_auto(cmd[4:])

        elif cmd == "snapshot":
            self._take_snapshot(auto=False)
            input(f"  {DIM}Press Enter to continue…{RESET}")
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

        elif cmd == "save":
            self.save_state()
            time.sleep(0.6)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

        elif cmd == "load":
            ok = self.load_state()
            if ok:
                print(f"  {GREEN}State loaded — step {self.step}, "
                      f"{dag_stats(self.dag)['verified']} verified.{RESET}")
                time.sleep(0.8)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

        elif cmd.startswith("load_backup"):
            self._cmd_load_backup(raw[12:].strip())

        elif cmd == "undo":
            self._cmd_undo()

        elif cmd == "diff":
            self._cmd_diff()

        elif cmd.startswith("timeline "):
            self._cmd_timeline(raw[9:])

        elif cmd == "reset":
            self._cmd_reset()

        elif cmd == "status":
            self._cmd_status()

        elif cmd == "stats":
            self._cmd_stats()

        elif cmd == "cache":
            self._cmd_cache()

        elif cmd == "cache clear":
            self._cmd_cache(clear=True)

        elif cmd == "history":
            self._cmd_history("")

        elif cmd.startswith("history "):
            self._cmd_history(raw[8:])

        elif cmd == "add_task":
            self._cmd_add_task()

        elif cmd.startswith("add_task "):
            self._cmd_add_task(raw[9:])

        elif cmd.startswith("add_branch"):
            _ab_parts = raw[10:].strip().split(None, 1)
            if len(_ab_parts) >= 2:
                self._cmd_add_branch(_ab_parts[0], spec_override=_ab_parts[1])
            else:
                self._cmd_add_branch(raw[10:])

        elif cmd.startswith("prioritize_branch"):
            _pb_parts = raw[17:].strip().split(None, 1)
            self._cmd_prioritize_branch(*_pb_parts)

        elif cmd == "export":
            self._cmd_export()

        elif cmd == "export_dag" or cmd.startswith("export_dag "):
            self._cmd_export_dag(raw[10:].strip() if cmd.startswith("export_dag ") else "")

        elif cmd.startswith("import_dag "):
            self._cmd_import_dag(raw[11:])

        elif cmd == "depends":
            self._cmd_depends("")

        elif cmd.startswith("depends "):
            self._cmd_depends(raw[8:])

        elif cmd.startswith("undepends "):
            self._cmd_undepends(raw[10:])

        elif cmd.startswith("describe "):
            self._cmd_describe(raw[9:])

        elif cmd.startswith("verify "):
            self._cmd_verify(raw[7:])

        elif cmd.startswith("tools "):
            self._cmd_tools(raw[6:])

        elif cmd.startswith("output "):
            self._cmd_output(raw[7:])

        elif cmd == "branches":
            self._cmd_branches("")

        elif cmd.startswith("branches "):
            self._cmd_branches(raw[9:])

        elif cmd.startswith("rename "):
            self._cmd_rename(raw[7:])

        elif cmd.startswith("search "):
            self._cmd_search(raw[7:])

        elif cmd.startswith("filter "):
            self._cmd_filter(raw[7:])

        elif cmd == "graph":
            self._cmd_graph()

        elif cmd == "log":
            self._cmd_log("")

        elif cmd.startswith("log "):
            self._cmd_log(raw[4:])

        elif cmd == "pause":
            self._cmd_pause()

        elif cmd == "resume":
            self._cmd_resume()

        elif cmd.startswith("set "):
            self._cmd_set(raw[4:])

        elif cmd == "config":
            self._cmd_config()

        elif cmd == "priority":
            self._cmd_priority()

        elif cmd == "stalled":
            self._cmd_stalled()

        elif cmd.startswith("heal "):
            self._cmd_heal(raw[5:])

        elif cmd == "agents":
            self._cmd_agents()

        elif cmd == "forecast":
            self._cmd_forecast()

        elif cmd == "tasks":
            self._cmd_tasks()

        elif cmd == "help":
            self._cmd_help()

        elif cmd == "exit":
            self.save_state(silent=True)
            print(f"\n{CYAN}Solo Builder shutting down. "
                  f"Steps: {self.step}  │  Healed: {self.healer.healed_total}  "
                  f"│  State saved.{RESET}\n")
            self.running = False

        elif cmd == "":
            pass   # empty enter → redraw

        else:
            print(f"  {YELLOW}Unknown command '{cmd}'. "
                  f"Type 'help' for options.{RESET}")
            time.sleep(0.8)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

    # ── Sub-commands ─────────────────────────────────────────────────────────
    def _persist_setting(self, cfg_key: str, value) -> None:
        """Silently write one key back to config/settings.json."""
        try:
            with open(_CFG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            cfg[cfg_key] = value
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass

    def _cmd_set(self, args: str) -> None:
        """set KEY=VALUE — update runtime config."""
        global STALL_THRESHOLD, SNAPSHOT_INTERVAL, VERBOSITY
        global AUTO_STEP_DELAY, AUTO_SAVE_INTERVAL, CLAUDE_ALLOWED_TOOLS, WEBHOOK_URL

        parts = args.split("=", 1)
        if len(parts) != 2:
            bare = args.strip().upper()
            _current: dict = {
                "STALL_THRESHOLD":    str(STALL_THRESHOLD),
                "SNAPSHOT_INTERVAL":  str(SNAPSHOT_INTERVAL),
                "VERBOSITY":          VERBOSITY,
                "VERIFY_PROB":        str(self.executor.verify_prob),
                "AUTO_STEP_DELAY":    str(AUTO_STEP_DELAY),
                "AUTO_SAVE_INTERVAL": str(AUTO_SAVE_INTERVAL),
                "CLAUDE_ALLOWED_TOOLS": CLAUDE_ALLOWED_TOOLS or "(none)",
                "ANTHROPIC_MAX_TOKENS": str(self.executor.anthropic.max_tokens),
                "ANTHROPIC_MODEL":    self.executor.anthropic.model,
                "CLAUDE_SUBPROCESS":  "on" if self.executor.claude.available else "off",
                "REVIEW_MODE":        "on" if self.executor.review_mode else "off",
                "WEBHOOK_URL":        WEBHOOK_URL or "(not set)",
            }
            if bare in _current:
                print(f"  {CYAN}{bare} = {_current[bare]}{RESET}")
            else:
                print(f"  {YELLOW}Usage: set KEY=VALUE{RESET}")
            return

        key, val = parts[0].strip().upper(), parts[1].strip()
        try:
            if key == "STALL_THRESHOLD":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                STALL_THRESHOLD = v
                self.healer.stall_threshold  = STALL_THRESHOLD
                self.planner.stall_threshold = STALL_THRESHOLD
                self.display.stall_threshold = STALL_THRESHOLD
                print(f"  {GREEN}STALL_THRESHOLD = {STALL_THRESHOLD}{RESET}")
                self._persist_setting("STALL_THRESHOLD", STALL_THRESHOLD)

            elif key == "SNAPSHOT_INTERVAL":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                SNAPSHOT_INTERVAL = v
                print(f"  {GREEN}SNAPSHOT_INTERVAL = {SNAPSHOT_INTERVAL}{RESET}")
                self._persist_setting("SNAPSHOT_INTERVAL", SNAPSHOT_INTERVAL)

            elif key == "VERBOSITY":
                v = val.upper()
                if v not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                    raise ValueError("must be one of DEBUG, INFO, WARNING, ERROR")
                VERBOSITY = v
                print(f"  {GREEN}VERBOSITY = {VERBOSITY}{RESET}")
                self._persist_setting("VERBOSITY", VERBOSITY)

            elif key == "VERIFY_PROB":
                v = float(val)
                if not 0.0 <= v <= 1.0:
                    raise ValueError("must be between 0.0 and 1.0")
                self.executor.verify_prob = v
                print(f"  {GREEN}VERIFY_PROB = {val}{RESET}")
                self._persist_setting("EXECUTOR_VERIFY_PROBABILITY", self.executor.verify_prob)

            elif key == "AUTO_STEP_DELAY":
                v = float(val)
                if v < 0:
                    raise ValueError("must be >= 0")
                AUTO_STEP_DELAY = v
                print(f"  {GREEN}AUTO_STEP_DELAY = {AUTO_STEP_DELAY}s{RESET}")
                self._persist_setting("AUTO_STEP_DELAY", AUTO_STEP_DELAY)

            elif key == "AUTO_SAVE_INTERVAL":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                AUTO_SAVE_INTERVAL = v
                print(f"  {GREEN}AUTO_SAVE_INTERVAL = {AUTO_SAVE_INTERVAL}{RESET}")
                self._persist_setting("AUTO_SAVE_INTERVAL", AUTO_SAVE_INTERVAL)

            elif key == "CLAUDE_ALLOWED_TOOLS":
                CLAUDE_ALLOWED_TOOLS = val
                self.executor.claude.allowed_tools = val
                label = val if val else "(none — headless)"
                print(f"  {GREEN}CLAUDE_ALLOWED_TOOLS = {label}{RESET}")
                self._persist_setting("CLAUDE_ALLOWED_TOOLS", val)

            elif key == "ANTHROPIC_MAX_TOKENS":
                v = int(val)
                if v < 1 or v > 8192:
                    raise ValueError("must be between 1 and 8192")
                self.executor.anthropic.max_tokens = v
                print(f"  {GREEN}ANTHROPIC_MAX_TOKENS = {v}{RESET}")
                self._persist_setting("ANTHROPIC_MAX_TOKENS", v)

            elif key == "ANTHROPIC_MODEL":
                self.executor.anthropic.model = val
                print(f"  {GREEN}ANTHROPIC_MODEL = {val}{RESET}")
                self._persist_setting("ANTHROPIC_MODEL", val)

            elif key == "CLAUDE_SUBPROCESS":
                enabled = val.lower() not in ("0", "off", "false", "no")
                self.executor.claude.available = enabled
                label = "on (subprocess)" if enabled else "off (SDK/dice-roll fallback)"
                print(f"  {GREEN}CLAUDE_SUBPROCESS = {label}{RESET}")
                # CLAUDE_SUBPROCESS is not a config.json key — derived at runtime

            elif key == "REVIEW_MODE":
                enabled = val.lower() not in ("0", "off", "false", "no")
                self.executor.review_mode = enabled
                label = "on (subtasks pause at Review for verify)" if enabled else "off (auto-Verified)"
                print(f"  {GREEN}REVIEW_MODE = {label}{RESET}")
                self._persist_setting("REVIEW_MODE", enabled)

            elif key == "WEBHOOK_URL":
                if val and not val.startswith("http"):
                    print(f"  {YELLOW}Warning: WEBHOOK_URL should start with http/https "
                          f"(got {val!r}). Setting anyway.{RESET}")
                WEBHOOK_URL = val
                print(f"  {GREEN}WEBHOOK_URL = {val or '(cleared)'}{RESET}")
                self._persist_setting("WEBHOOK_URL", val)

            else:
                print(f"  {YELLOW}Unknown key '{key}'. "
                      f"Valid: STALL_THRESHOLD, SNAPSHOT_INTERVAL, "
                      f"VERBOSITY, VERIFY_PROB, AUTO_STEP_DELAY, AUTO_SAVE_INTERVAL, "
                      f"CLAUDE_ALLOWED_TOOLS, ANTHROPIC_MAX_TOKENS, ANTHROPIC_MODEL, "
                      f"CLAUDE_SUBPROCESS, REVIEW_MODE, WEBHOOK_URL{RESET}")
        except ValueError:
            print(f"  {RED}Invalid value '{val}' for {key}{RESET}")

        time.sleep(0.5)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def start(self, headless: bool = False, auto_steps: Optional[int] = None,
              no_resume: bool = False, output_format: str = "text") -> None:
        """Run the CLI loop.  In headless mode: skip prompts, auto-run, then exit."""
        if not no_resume and os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                saved_step = saved.get("step", 0)
                saved_v    = dag_stats(saved.get("dag", {})).get("verified", 0)
                saved_t    = dag_stats(saved.get("dag", {})).get("total", 0)
                print(f"  {CYAN}Saved state found: step {saved_step}, "
                      f"{saved_v}/{saved_t} verified.{RESET}")
                if headless:
                    ok = self.load_state()
                    if ok:
                        print(f"  {GREEN}Resumed from step {self.step}.{RESET}")
                else:
                    ans = input(f"  {BOLD}Resume? [Y/n]:{RESET} ").strip().lower()
                    if ans in ("", "y", "yes"):
                        ok = self.load_state()
                        if ok:
                            print(f"  {GREEN}Resumed from step {self.step}.{RESET}")
                            time.sleep(0.5)
            except Exception:
                pass  # corrupt save → start fresh

        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag) if self.step else "N/A",
        )

        if headless:
            self._cmd_auto(str(auto_steps) if auto_steps is not None else "")
            self.save_state()
            return

        while self.running:
            try:
                raw = input(f"\n  {BOLD}{CYAN}solo-builder >{RESET} ")
                self.handle_command(raw)
            except (KeyboardInterrupt, EOFError):
                print(f"\n  {YELLOW}Interrupted — type 'exit' to quit.{RESET}")
                self.display.render(
                    self.dag, self.memory_store, self.step,
                    self.alerts, self.meta.forecast(self.dag),
                )


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
# ── Inject host module globals into mixin modules ────────────────────────────
# Mixin methods look up names in their defining module's globals. Inject all
# uppercase names from this module into each mixin module so that references
# to STATE_PATH, MAX_BRANCHES_PER_TASK, etc. resolve correctly -- including
# after runtime mutations from _cmd_set (both point to the same dict object).
def _inject_host_globals_into_mixins():
    """Inject host module globals into mixin modules so their methods resolve names correctly."""
    import sys as _s
    _host_globals = vars(_s.modules[__name__])
    _skip = frozenset({'__builtins__', '__spec__', '__loader__', '__package__'})
    for _mod_name in list(_s.modules):
        if _mod_name.endswith(('query_cmds', 'subtask_cmds', 'dag_cmds', 'settings_cmds')):
            _target = vars(_s.modules[_mod_name])
            for _k, _v in list(_host_globals.items()):
                if _k not in _skip and not _k.startswith('__'):
                    _target.setdefault(_k, _v)

_inject_host_globals_into_mixins()


def _splash() -> None:
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

    if not _PDF_OK:
        print(f"  {YELLOW}[!] matplotlib not found — PDF snapshots disabled.")
        print(f"      Install with: pip install matplotlib{RESET}\n")
    time.sleep(0.6)


def _fire_completion(steps: int, verified: int, total: int) -> None:
    """Non-blocking: POST webhook and/or Windows toast on pipeline completion."""
    import threading

    def _webhook() -> None:
        if not WEBHOOK_URL:
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
            urllib.request.urlopen(req, timeout=10)
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


def main() -> None:
    """Entry point — interactive or headless."""
    # ── status subcommand (fast path, no lock needed) ────────────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        _state_path = os.path.join(_HERE, "state", "solo_builder_state.json")
        if not os.path.exists(_state_path):
            print(json.dumps({"error": "no state file"}))
            return
        with open(_state_path) as _f:
            _state = json.load(_f)
        _s    = dag_stats(_state.get("dag", {}))
        _step = _state.get("step", 0)
        _pct  = round(_s["verified"] / _s["total"] * 100, 1) if _s["total"] else 0.0
        print(json.dumps({
            "step":     _step,
            "verified": _s["verified"],
            "running":  _s["running"],
            "pending":  _s["pending"],
            "total":    _s["total"],
            "pct":      _pct,
            "complete": _s["verified"] == _s["total"],
        }))
        return

    # ── watch subcommand (live progress bar, no lock needed) ─────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        _state_path = os.path.join(_HERE, "state", "solo_builder_state.json")
        _interval   = 2.0
        if len(sys.argv) > 2:
            try:
                _interval = float(sys.argv[2])
            except ValueError:
                pass
        print(f"  Watching pipeline every {_interval}s  (Ctrl+C to stop)", flush=True)
        try:
            while True:
                if not os.path.exists(_state_path):
                    print("\r  No state file — start the CLI first.                    ",
                          end="", flush=True)
                else:
                    try:
                        with open(_state_path) as _f:
                            _wstate = json.load(_f)
                    except (json.JSONDecodeError, OSError):
                        time.sleep(_interval)
                        continue
                    _s    = dag_stats(_wstate.get("dag", {}))
                    _step = _wstate.get("step", 0)
                    _pct  = round(_s["verified"] / _s["total"] * 100, 1) if _s["total"] else 0.0
                    _bar  = ("=" * int(_pct / 5)).ljust(20, "-")
                    if _s["verified"] == _s["total"]:
                        print(f"\r  {GREEN}Complete!{RESET} "
                              f"{_s['verified']}/{_s['total']} verified in {_step} steps.            ")
                        break
                    print(
                        f"\r  Step {_step:3d}  [{_bar}]  "
                        f"{GREEN}{_s['verified']:3d}✓{RESET}  "
                        f"{CYAN}{_s['running']:2d}▶{RESET}  "
                        f"{YELLOW}{_s['pending']:3d}●{RESET}  "
                        f"{_pct:5.1f}%",
                        end="", flush=True,
                    )
                time.sleep(_interval)
        except KeyboardInterrupt:
            print()
        return

    # ── .env loader (no external dependency) ────────────────────────────────
    _env_path = os.path.join(_HERE, ".env")
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

    # ── Argument parsing ─────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(prog="solo-builder", add_help=True)
    parser.add_argument(
        "--headless", action="store_true",
        help="Non-interactive mode: auto-run then exit (no prompts).",
    )
    parser.add_argument(
        "--auto", type=int, metavar="N", default=None,
        help="Steps to run in headless mode (omit for full pipeline).",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Ignore saved state and start a fresh pipeline.",
    )
    parser.add_argument(
        "--output-format", choices=["text", "json"], default="text",
        help="'json' sends final stats as JSON to stdout; all other output goes to stderr.",
    )
    parser.add_argument(
        "--webhook", metavar="URL", default=None,
        help="POST completion JSON to this URL (overrides WEBHOOK_URL in settings).",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress all display output (headless only). Combine with --output-format json "
             "for completely silent runs where only the JSON result reaches stdout.",
    )
    parser.add_argument(
        "--export", action="store_true",
        help="After the run, write all Claude outputs to solo_builder_outputs.md.",
    )
    args = parser.parse_args()

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
    _LOCK_PATH  = os.path.join(_HERE, "state", "solo_builder.lock")
    _STOP_PATH  = os.path.join(_HERE, "state", "stop_trigger")
    _RUN_PATH   = os.path.join(_HERE, "state", "run_trigger")
    _AT_PATH    = os.path.join(_HERE, "state", "add_task_trigger.json")
    _AB_PATH    = os.path.join(_HERE, "state", "add_branch_trigger.json")
    _PB_PATH    = os.path.join(_HERE, "state", "prioritize_branch_trigger.json")
    _D_PATH     = os.path.join(_HERE, "state", "describe_trigger.json")
    _T_PATH     = os.path.join(_HERE, "state", "tools_trigger.json")
    _R_PATH     = os.path.join(_HERE, "state", "reset_trigger")
    _SNAP_PATH  = os.path.join(_HERE, "state", "snapshot_trigger")
    _SET_PATH   = os.path.join(_HERE, "state", "set_trigger.json")
    _DEP_PATH   = os.path.join(_HERE, "state", "depends_trigger.json")
    _UDEP_PATH  = os.path.join(_HERE, "state", "undepends_trigger.json")
    _UNDO_PATH  = os.path.join(_HERE, "state", "undo_trigger")
    _PAUSE_PATH = os.path.join(_HERE, "state", "pause_trigger")
    _HEAL_PATH  = os.path.join(_HERE, "state", "heal_trigger.json")
    os.makedirs(os.path.join(_HERE, "state"), exist_ok=True)
    _setup_logging()
    logger.info("startup version=2.1.50 headless=%s auto=%s", args.headless, args.auto)
    # Clear stale triggers from previous runs
    _DAGIMPORT_PATH = os.path.join(_HERE, "state", "dag_import_trigger.json")
    for _stale in (_STOP_PATH, _RUN_PATH, _AT_PATH, _AB_PATH, _PB_PATH,
                   _D_PATH, _T_PATH, _R_PATH, _SNAP_PATH, _SET_PATH,
                   _DEP_PATH, _UDEP_PATH, _UNDO_PATH, _PAUSE_PATH, _HEAL_PATH,
                   _DAGIMPORT_PATH):
        try:
            os.remove(_stale)
        except FileNotFoundError:
            pass
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
        _splash()
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
                stats = dag_stats(cli.dag)
                out = {
                    "steps":    cli.step,
                    "verified": stats["verified"],
                    "total":    stats["total"],
                    "complete": stats["verified"] == stats["total"],
                }
                if args.export:
                    out["export"] = {"path": _export_path, "count": _export_count}
                print(json.dumps(out))


if __name__ == "__main__":
    main()
