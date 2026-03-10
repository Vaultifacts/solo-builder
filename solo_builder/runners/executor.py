"""Executor — advances subtasks through Pending → Running → Verified."""
import asyncio
import json as _json
import logging
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple

from utils.helper_functions import add_memory_snapshot

from .cache import make_cache
from .claude_runner import ClaudeRunner
from .anthropic_runner import AnthropicRunner
from .sdk_tool_runner import SdkToolRunner, validate_tools as _validate_tools
from .hitl_gate import evaluate as _hitl_evaluate, level_name as _hitl_level_name

# ── Read config from settings.json (same defaults as solo_builder_cli.py) ─────
_SOLO     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG_PATH = os.path.join(_SOLO, "config", "settings.json")
try:
    with open(_CFG_PATH, encoding="utf-8") as _f:
        _CFG: dict = _json.load(_f)
except Exception:
    _CFG = {}

CLAUDE_TIMEOUT       : int  = _CFG.get("CLAUDE_TIMEOUT", 60)
CLAUDE_ALLOWED_TOOLS : str  = _CFG.get("CLAUDE_ALLOWED_TOOLS", "")
ANTHROPIC_MODEL      : str  = _CFG.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS : int  = _CFG.get("ANTHROPIC_MAX_TOKENS", 4096)
REVIEW_MODE          : bool = bool(_CFG.get("REVIEW_MODE", False))

logger = logging.getLogger("solo_builder")

_METRICS_PATH = os.path.join(_SOLO, "metrics.jsonl")


def _write_step_metrics(step: int, t0: float, sdk_dispatched: int,
                        sdk_succeeded: int, actions: dict) -> None:
    """Append one JSONL metrics record for this execute_step call (TD-OPS-001)."""
    elapsed = round(time.monotonic() - t0, 3)
    record = {
        "ts":            int(time.time()),
        "step":          step,
        "elapsed_s":     elapsed,
        "sdk_dispatched": sdk_dispatched,
        "sdk_succeeded":  sdk_succeeded,
        "sdk_success_rate": round(sdk_succeeded / sdk_dispatched, 3) if sdk_dispatched else None,
        "started":       sum(1 for v in actions.values() if v == "started"),
        "verified":      sum(1 for v in actions.values() if v in ("verified", "review")),
    }
    try:
        with open(_METRICS_PATH, "a", encoding="utf-8") as _mf:
            _mf.write(_json.dumps(record) + "\n")
    except OSError:
        pass  # never block execution on metrics write failure


class Executor:
    """Advances subtasks through Pending → Running → Verified."""

    def __init__(
        self,
        max_per_step: int,
        verify_prob: float,
        project_context: str = "",
        append_journal: Optional[Callable] = None,
    ) -> None:
        self.max_per_step     = max_per_step
        self.verify_prob      = verify_prob
        self.review_mode      = REVIEW_MODE
        self._project_context = project_context
        self._append_journal  = append_journal or (lambda *a, **kw: None)
        # Response cache: keyed by SHA-256(prompt); persists across sessions.
        # Disable with NOCACHE=1 env var. Location: claude/cache/ (default).
        _cache = make_cache()
        self.claude    = ClaudeRunner(timeout=CLAUDE_TIMEOUT, allowed_tools=CLAUDE_ALLOWED_TOOLS)
        self.anthropic = AnthropicRunner(model=ANTHROPIC_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS, cache=_cache)
        # SDK tool-use runner — replaces subprocess for tool-bearing subtasks
        self.sdk_tool = SdkToolRunner(
            client=self.anthropic.client,
            async_client=self.anthropic.async_client,
            model=ANTHROPIC_MODEL,
            max_tokens=max(ANTHROPIC_MAX_TOKENS, 512),
        )

    # ── Async gather helpers (class-level to avoid per-step closure allocation) ─
    @staticmethod
    async def _gather_sdktool(runner, jobs):
        return await asyncio.gather(
            *(runner.arun(_ctx + sd.get("description", ""), st)
              for _, _, _, sd, st, _ctx in jobs),
            return_exceptions=True,
        )

    @staticmethod
    async def _gather_sdk(runner, jobs):
        return await asyncio.gather(
            *(runner.arun(p) for _, _, _, _, p in jobs),
            return_exceptions=True,
        )

    def execute_step(
        self,
        dag: Dict,
        priority_list: List[Tuple[str, str, str, int]],
        step: int,
        memory_store: Dict,
    ) -> Dict[str, str]:
        """
        Advance up to max_per_step subtasks.
        Returns {subtask_name: action} where action ∈ {"started", "verified"}.
        """
        actions: Dict[str, str] = {}
        advanced = 0
        sdk_tool_jobs: list = []   # SDK tool-use (preferred for tool-bearing subtasks)
        claude_jobs:   list = []   # subprocess fallback when SDK unavailable
        sdk_jobs:      list = []   # SDK direct (no tools)
        _step_t0         = time.monotonic()
        _sdk_dispatched  = 0
        _sdk_succeeded   = 0

        # CLAUDE_LOCAL=1: route all Running subtasks through the local claude CLI
        # instead of the Anthropic API, reducing cloud token consumption.
        _use_local = os.environ.get("CLAUDE_LOCAL", "0") == "1"

        for task_name, branch_name, st_name, _ in priority_list:
            if advanced >= self.max_per_step:
                break

            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            status  = st_data.get("status", "Pending")

            if status == "Pending":
                st_data["status"]      = "Running"
                st_data["last_update"] = step
                st_data.setdefault("history", []).append({"status": "Running", "step": step})
                dag[task_name]["status"]                              = "Running"
                dag[task_name]["branches"][branch_name]["status"]     = "Running"
                add_memory_snapshot(memory_store, branch_name, f"{st_name}_started", step)
                actions[st_name] = "started"
                advanced += 1
                logger.debug("subtask_started step=%d task=%s branch=%s subtask=%s", step, task_name, branch_name, st_name)

            elif status == "Running":
                st_tools    = st_data.get("tools", "").strip()
                description = st_data.get("description", "").strip()

                # ── Tool validation + HITL gate ────────────────────────────
                if st_tools:
                    try:
                        _validate_tools(st_tools)
                    except ValueError as _vt_err:
                        logger.error("invalid_tools step=%d task=%s subtask=%s error=%s",
                                     step, task_name, st_name, _vt_err)
                        continue  # subtask stays Running; config must be fixed

                    _hl = _hitl_evaluate(st_tools, description)
                    if _hl == 3:
                        logger.warning("hitl_blocked step=%d task=%s subtask=%s tools=%s",
                                       step, task_name, st_name, st_tools)
                        continue  # subtask stays Running; re-evaluated each step
                    elif _hl == 2 and sys.stdin.isatty():
                        _yn = input(
                            f"\n  [HITL] Approve '{st_name}' tools={st_tools!r}? [y/N] "
                        ).strip().lower()
                        if _yn != "y":
                            logger.warning("hitl_denied step=%d task=%s subtask=%s",
                                           step, task_name, st_name)
                            continue
                    elif _hl >= 1:
                        logger.warning("hitl_%s step=%d task=%s subtask=%s tools=%s",
                                       _hitl_level_name(_hl).lower(), step,
                                       task_name, st_name, st_tools)

                if _use_local and self.claude.available:
                    # Local CLI mode: bypass API runners entirely.
                    # tools string is passed through so ClaudeRunner can forward it.
                    claude_jobs.append((task_name, branch_name, st_name, st_data, st_tools))
                    advanced += 1
                elif st_tools:
                    if self.sdk_tool.available:
                        # SDK tool-use (preferred — no subprocess overhead)
                        sdk_tool_jobs.append((task_name, branch_name, st_name, st_data, st_tools, self._project_context))
                        advanced += 1
                        _sdk_dispatched += 1
                    elif self.claude.available:
                        # Subprocess fallback when SDK unavailable (TD-ARCH-003)
                        logger.warning("subprocess_fallback step=%d task=%s subtask=%s "
                                       "(SDK unavailable — ClaudeRunner subprocess used)",
                                       step, task_name, st_name)
                        claude_jobs.append((task_name, branch_name, st_name, st_data, st_tools))
                        advanced += 1
                elif self.anthropic.available:
                    # No tools — use SDK directly (faster, no subprocess)
                    raw_prompt = (
                        description
                        or f"You completed subtask '{st_name}' in task '{task_name}'. "
                           f"Write one concrete sentence describing what was accomplished."
                    )
                    auto_prompt = self._project_context + raw_prompt
                    sdk_jobs.append((task_name, branch_name, st_name, st_data, auto_prompt))
                    advanced += 1
                    _sdk_dispatched += 1
                elif random.random() < self.verify_prob:
                        new_status             = "Review" if self.review_mode else "Verified"
                        st_data["status"]      = new_status
                        st_data["shadow"]      = "Done"
                        st_data["last_update"] = step
                        self._record_history(st_data, new_status, step)
                        add_memory_snapshot(memory_store, branch_name, f"{st_name}_verified", step)
                        actions[st_name] = "review" if self.review_mode else "verified"
                        advanced += 1
                        logger.debug("subtask_%s step=%d task=%s subtask=%s via=dice_roll", new_status.lower(), step, task_name, st_name)
                        if not self.review_mode:
                            self._roll_up(dag, task_name, branch_name)

        # ── SDK tool-use jobs (async, no subprocess) ─────────────────────────
        if sdk_tool_jobs:
            names = ", ".join(j[2] for j in sdk_tool_jobs)
            logger.info("sdk_tool_dispatch step=%d jobs=%s", step, names)
            _sdktool_results = asyncio.run(
                self._gather_sdktool(self.sdk_tool, sdk_tool_jobs)
            )
            for (task_name, branch_name, st_name, st_data, st_tools, _ctx), result \
                    in zip(sdk_tool_jobs, _sdktool_results):
                success, output = (False, str(result)[:200]) \
                    if isinstance(result, Exception) else result
                if success:
                    _sdk_succeeded += 1
                    new_status             = "Review" if self.review_mode else "Verified"
                    st_data["status"]      = new_status
                    st_data["shadow"]      = "Done"
                    st_data["output"]      = output[:400]
                    st_data["last_update"] = step
                    self._record_history(st_data, new_status, step)
                    add_memory_snapshot(memory_store, branch_name,
                                        f"{st_name}_sdktool_verified", step)
                    actions[st_name] = "review" if self.review_mode else "verified"
                    logger.info("subtask_%s step=%d task=%s subtask=%s via=sdk_tool", new_status.lower(), step, task_name, st_name)
                    if not self.review_mode:
                        self._roll_up(dag, task_name, branch_name)
                    self._append_journal(
                        st_name, task_name, branch_name,
                        st_data.get("description", ""), output, step,
                    )
                else:
                    logger.warning("sdk_tool_failed step=%d task=%s subtask=%s error=%.100s", step, task_name, st_name, output)
                    # SDK tool run failed — escalate to subprocess or dice-roll
                    if self.claude.available:
                        claude_jobs.append(
                            (task_name, branch_name, st_name, st_data, st_tools)
                        )
                    elif random.random() < self.verify_prob:
                        # No subprocess available — dice-roll so pipeline isn't blocked
                        new_status             = "Review" if self.review_mode else "Verified"
                        st_data["status"]      = new_status
                        st_data["shadow"]      = "Done"
                        st_data["last_update"] = step
                        self._record_history(st_data, new_status, step)
                        add_memory_snapshot(memory_store, branch_name,
                                            f"{st_name}_verified", step)
                        actions[st_name] = "review" if self.review_mode else "verified"
                        if not self.review_mode:
                            self._roll_up(dag, task_name, branch_name)

        # ── Run Claude jobs in parallel ───────────────────────────────────────
        if claude_jobs:
            names = ", ".join(j[2] for j in claude_jobs)
            logger.info("claude_dispatch step=%d jobs=%s", step, names)
            with ThreadPoolExecutor(max_workers=len(claude_jobs)) as pool:
                futures = {
                    pool.submit(self.claude.run,
                                self._project_context + st_data.get("description", ""),
                                st_name, st_tools): (task_name, branch_name, st_name, st_data)
                    for task_name, branch_name, st_name, st_data, st_tools in claude_jobs
                }
                for future in as_completed(futures):
                    task_name, branch_name, st_name, st_data = futures[future]
                    success, output = future.result()
                    if success:
                        new_status             = "Review" if self.review_mode else "Verified"
                        st_data["status"]      = new_status
                        st_data["shadow"]      = "Done"
                        st_data["output"]      = output
                        st_data["last_update"] = step
                        self._record_history(st_data, new_status, step)
                        add_memory_snapshot(memory_store, branch_name, f"{st_name}_claude_verified", step)
                        actions[st_name] = "review" if self.review_mode else "verified"
                        logger.info("subtask_%s step=%d task=%s subtask=%s via=claude_subprocess", new_status.lower(), step, task_name, st_name)
                        if not self.review_mode:
                            self._roll_up(dag, task_name, branch_name)
                        self._append_journal(
                            st_name, task_name, branch_name,
                            st_data.get("description", ""), output, step,
                        )
                    # On failure: stay Running → will retry next step or self-heal

        # ── SDK jobs (async Anthropic API, no subprocess) ─────────────────────
        if sdk_jobs:
            names = ", ".join(j[2] for j in sdk_jobs)
            logger.info("sdk_dispatch step=%d jobs=%s", step, names)
            _sdk_results = asyncio.run(
                self._gather_sdk(self.anthropic, sdk_jobs)
            )
            for (task_name, branch_name, st_name, st_data, _), result \
                    in zip(sdk_jobs, _sdk_results):
                success, output = (False, str(result)[:200]) \
                    if isinstance(result, Exception) else result
                if success:
                    _sdk_succeeded += 1
                    new_status             = "Review" if self.review_mode else "Verified"
                    st_data["status"]      = new_status
                    st_data["shadow"]      = "Done"
                    st_data["output"]      = output[:400]
                    st_data["last_update"] = step
                    self._record_history(st_data, new_status, step)
                    add_memory_snapshot(memory_store, branch_name,
                                        f"{st_name}_sdk_verified", step)
                    actions[st_name] = "review" if self.review_mode else "verified"
                    logger.info("subtask_%s step=%d task=%s subtask=%s via=sdk_direct", new_status.lower(), step, task_name, st_name)
                    if not self.review_mode:
                        self._roll_up(dag, task_name, branch_name)
                else:
                    logger.warning("sdk_direct_failed step=%d task=%s subtask=%s error=%.100s", step, task_name, st_name, output)
                    # SDK failed — dice-roll so pipeline isn't blocked
                    if random.random() < self.verify_prob:
                        st_data["status"]      = "Verified"
                        st_data["shadow"]      = "Done"
                        st_data["last_update"] = step
                        self._record_history(st_data, "Verified", step)
                        add_memory_snapshot(memory_store, branch_name,
                                            f"{st_name}_verified", step)
                        actions[st_name] = "verified"
                        self._roll_up(dag, task_name, branch_name)

        _write_step_metrics(step, _step_t0, _sdk_dispatched, _sdk_succeeded, actions)
        elapsed_ms = round((time.monotonic() - _step_t0) * 1000)
        logger.info("step_complete step=%d elapsed_ms=%d actions=%d",
                    step, elapsed_ms, len(actions))
        return actions

    @staticmethod
    def _record_history(st_data: Dict, new_status: str, step: int) -> None:
        """Append a status transition to the subtask's history timeline."""
        st_data.setdefault("history", []).append({"status": new_status, "step": step})

    # ── Roll-up helpers ──────────────────────────────────────────────────────
    def _roll_up(self, dag: Dict, task_name: str, branch_name: str) -> None:
        self._update_branch(dag, task_name, branch_name)
        self._update_task(dag, task_name)

    def _update_branch(self, dag: Dict, task_name: str, branch_name: str) -> None:
        sts = dag[task_name]["branches"][branch_name]["subtasks"]
        if all(s.get("status") == "Verified" for s in sts.values()):
            dag[task_name]["branches"][branch_name]["status"] = "Verified"

    def _update_task(self, dag: Dict, task_name: str) -> None:
        branches = dag[task_name]["branches"]
        if all(b.get("status") == "Verified" for b in branches.values()):
            dag[task_name]["status"] = "Verified"
        elif any(b.get("status") == "Running" for b in branches.values()):
            dag[task_name]["status"] = "Running"
