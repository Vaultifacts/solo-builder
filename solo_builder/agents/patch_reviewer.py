"""
agents/patch_reviewer.py
PatchReviewer agent — evaluates Executor output before Verifier.

Sits between Executor and Verifier in the step pipeline:
    … → Executor → **PatchReviewer** → Verifier → …

Responsibilities:
    1. Inspect code patches / output produced by Executor.
    2. Ask Claude (via Anthropic SDK) to critique the patch.
    3. Reject patches that break style, violate task description,
       or remove important code — resetting the subtask to Pending.

Safety features (Dynamic Task Safety Guard):
    - Tracks rejection count per subtask
    - After MAX_PATCH_REJECTIONS, moves to Review instead of Pending
    - Optional AI budget integration
"""

import os
import re
from typing import Any, Dict, List, Tuple

from utils.helper_functions import (
    BLINK, CYAN, GREEN, RED, RESET, YELLOW,
    add_memory_snapshot,
)

# ── Review prompt template ───────────────────────────────────────────────────
_REVIEW_PROMPT = """\
You are a strict code reviewer. Evaluate the following patch/output produced \
by an AI executor for the given task.

## Task description
{description}

## Executor output
{output}

## Review criteria
1. Does the output fulfil the task description?
2. Does it follow good coding style and conventions?
3. Does it avoid removing important code or functionality?
4. Is it free of obvious bugs, security issues, or regressions?

Reply with EXACTLY one line:
APPROVED — if the output passes all criteria.
REJECTED: <reason> — if it fails any criterion.
"""

ALERT_REJECTION_LIMIT = f"{BLINK}{YELLOW}⚠ REJECTION LIMIT ⚠{RESET}"

# ── Dangerous patterns for heuristic checks ──────────────────────────────────
_DANGEROUS_PATTERNS = [
    # File deletion / destruction
    r"rm\s+-rf",
    r"rm\s+-f\s+/",
    r"shutil\.rmtree\(",
    r"os\.remove\(",
    r"\.unlink\(\)",
    # Credential exposure
    r"api[_-]?key\s*=\s*['\"]",
    r"password\s*=\s*['\"]",
    r"secret\s*=\s*['\"]",
    r"token\s*=\s*['\"]",
    r"sk[-_]",  # OpenAI key prefix
    r"github[_-]?token",
    # Large file modifications
    r"DELETE\s+\d{4,}",  # Delete >1000 lines
]

_DANGEROUS_KEYWORDS = [
    "DROP TABLE",
    "TRUNCATE",
    "DELETE FROM",
]


class PatchReviewer:
    """
    Reviews Executor output using heuristics and optional Anthropic SDK.

    After each step, iterates over subtasks that were just advanced by the
    Executor (status == Review or Verified with new output).  For each,
    sends the output + task description to Claude for critique.

    If rejected:
        - Increments rejection counter for the subtask
        - If under MAX_PATCH_REJECTIONS: resets to Pending for retry
        - If at/over threshold: moves to Review with alert (needs human attention)

    Configurable via settings keys:
        PATCH_REVIEWER_ENABLED    (bool, default True)
        PATCH_REVIEWER_USE_SDK    (bool, default True if ANTHROPIC_API_KEY set)
        PATCH_REVIEWER_MODEL      (str,  default from ANTHROPIC_MODEL)
        PATCH_REVIEWER_MAX_TOKENS (int,  default 256)
        MAX_PATCH_REJECTIONS      (int,  default 3)
        MAX_PATCH_REVIEWS_PER_STEP (int, default 0 = unlimited)
    """

    def __init__(self, settings: Dict[str, Any] | None = None) -> None:
        cfg = settings or {}
        self.enabled      = cfg.get("PATCH_REVIEWER_ENABLED", True)
        self._model       = cfg.get("PATCH_REVIEWER_MODEL",
                                    cfg.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
        self._max_tokens  = cfg.get("PATCH_REVIEWER_MAX_TOKENS", 256)
        self.max_rejections = cfg.get("MAX_PATCH_REJECTIONS", 3)
        self.max_reviews_per_step = cfg.get("MAX_PATCH_REVIEWS_PER_STEP", 0)
        self.use_sdk      = cfg.get("PATCH_REVIEWER_USE_SDK", True)
        self._client      = None
        self.available    = self._init_client()
        # Rejection tracking: {subtask_name: {"count": N, "reasons": [...]}}
        self._rejections: Dict[str, Dict[str, Any]] = {}
        # Observability counter
        self.threshold_hits: int = 0

    def _init_client(self) -> bool:
        """Initialise the Anthropic SDK client; return False if unavailable."""
        if not self.enabled or not self.use_sdk:
            return False
        try:
            import anthropic  # noqa: PLC0415
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                return False
            self._client = anthropic.Anthropic(api_key=key)
            return True
        except ImportError:
            return False

    # ── Rejection tracking ───────────────────────────────────────────────
    def rejection_count(self, st_name: str) -> int:
        """Return the number of times a subtask has been rejected."""
        return self._rejections.get(st_name, {}).get("count", 0)

    def rejection_reasons(self, st_name: str) -> List[str]:
        """Return the list of rejection reasons for a subtask."""
        return self._rejections.get(st_name, {}).get("reasons", [])

    # ── Public API ───────────────────────────────────────────────────────
    def review_step(
        self,
        dag: Dict,
        executor_actions: Dict[str, str],
        step: int,
        memory_store: Dict,
        alerts: List[str],
        budget=None,
    ) -> Dict[str, str]:
        """
        Review subtasks that the Executor just advanced.

        Parameters
        ----------
        dag              : The live DAG dict.
        executor_actions : {subtask_name: action} from Executor.execute_step().
        step             : Current pipeline step number.
        memory_store     : Branch → memory snapshots.
        alerts           : Mutable alert list for the current step.
        budget           : Optional StepBudget for AI call tracking.

        Returns
        -------
        Dict mapping subtask_name → "approved" | "rejected" | "escalated" | "deferred".
        """
        if not self.enabled:
            return {}

        results: Dict[str, str] = {}
        reviews_this_step = 0

        for task_name, task_data in dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    # Only review subtasks the Executor just touched
                    if st_name not in executor_actions:
                        continue
                    action = executor_actions[st_name]
                    if action not in ("verified", "review"):
                        continue

                    output      = st_data.get("output", "").strip()
                    description = st_data.get("description", "").strip()

                    # Nothing to review if no output was produced
                    if not output:
                        results[st_name] = "approved"
                        continue

                    # Throughput cap: defer excess reviews
                    if (self.max_reviews_per_step > 0
                            and reviews_this_step >= self.max_reviews_per_step):
                        results[st_name] = "deferred"
                        alerts.append(
                            f"  {YELLOW}[PatchReviewer]{RESET} "
                            f"{CYAN}{st_name}{RESET} deferred (throughput cap)"
                        )
                        continue

                    # Check AI budget before calling Claude
                    if budget is not None and budget.exhausted:
                        results[st_name] = "deferred"
                        alerts.append(
                            f"  {YELLOW}[PatchReviewer]{RESET} "
                            f"{CYAN}{st_name}{RESET} deferred (budget exhausted)"
                        )
                        continue

                    # First, check heuristics (always available)
                    approved, reason, risk_score = self._check_heuristics(
                        description, output
                    )

                    # If heuristics didn't catch anything dangerous and SDK available,
                    # ask Claude for deeper review
                    if approved and self.available:
                        approved, reason, usage_tokens = self._ask_claude(
                            description, output,
                        )
                        if budget is not None:
                            budget.consume(1)
                            budget.record_usage(
                                tokens=usage_tokens, agent="PatchReviewer",
                            )
                    else:
                        usage_tokens = 0

                    reviews_this_step += 1

                    if approved:
                        results[st_name] = "approved"
                        alerts.append(
                            f"  {GREEN}[PatchReviewer]{RESET} "
                            f"{CYAN}{st_name}{RESET} approved (risk: {risk_score})"
                        )
                    else:
                        # Track rejection
                        if st_name not in self._rejections:
                            self._rejections[st_name] = {"count": 0, "reasons": []}
                        self._rejections[st_name]["count"] += 1
                        self._rejections[st_name]["reasons"].append(reason)
                        rej_count = self._rejections[st_name]["count"]

                        if rej_count >= self.max_rejections:
                            # Escalate: move to Review instead of Pending
                            st_data["status"]      = "Review"
                            st_data["shadow"]      = "Pending"
                            st_data["last_update"] = step
                            st_data.setdefault("history", []).append(
                                {"status": "Review", "step": step,
                                 "note": f"PatchReviewer escalated after "
                                         f"{rej_count} rejections: {reason}"}
                            )
                            add_memory_snapshot(
                                memory_store, branch_name,
                                f"{st_name}_rejection_limit_reached", step,
                            )
                            results[st_name] = "escalated"
                            self.threshold_hits += 1
                            alerts.append(
                                f"  {ALERT_REJECTION_LIMIT} "
                                f"{CYAN}{st_name}{RESET} rejected {rej_count}x "
                                f"→ moved to Review (needs human attention)"
                            )
                        else:
                            # Normal reject: reset to Pending for retry
                            st_data["status"]      = "Pending"
                            st_data["shadow"]      = "Pending"
                            st_data["last_update"] = step
                            st_data.setdefault("history", []).append(
                                {"status": "Pending", "step": step,
                                 "note": f"PatchReviewer rejected ({rej_count}/"
                                         f"{self.max_rejections}): {reason}"}
                            )
                            add_memory_snapshot(
                                memory_store, branch_name,
                                f"{st_name}_patch_rejected", step,
                            )
                            results[st_name] = "rejected"
                            alerts.append(
                                f"  {RED}[PatchReviewer]{RESET} "
                                f"{CYAN}{st_name}{RESET} rejected ({rej_count}/"
                                f"{self.max_rejections}): {reason}"
                            )

        return results

    # ── Heuristic review ─────────────────────────────────────────────────
    def _check_heuristics(
        self, description: str, output: str,
    ) -> Tuple[bool, str, int]:
        """
        Check output for dangerous patterns without calling Claude.
        Returns (approved: bool, reason: str, risk_score: int).

        Risk score: 0 (safe) to 100 (dangerous).
        """
        risk_score = 0

        # Check for regex patterns
        output_upper = output.upper()
        for pattern in _DANGEROUS_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}", 100

        # Check for dangerous keywords
        for keyword in _DANGEROUS_KEYWORDS:
            if keyword in output_upper:
                return False, f"Dangerous keyword detected: {keyword}", 100

        # Check for empty output
        if not output or not output.strip():
            return False, "Output is empty", 10

        # Check for excessive deletions (heuristic: >50% of expected content)
        if description and len(output) < len(description) * 0.2:
            risk_score += 30

        # Check for suspicious error patterns
        if any(err in output_upper for err in ["ERROR", "EXCEPTION", "FAILED", "FATAL"]):
            risk_score += 25

        return True, "", risk_score

    # ── Claude interaction ───────────────────────────────────────────────
    def _ask_claude(
        self, description: str, output: str,
    ) -> Tuple[bool, str, int]:
        """
        Send the patch to Claude for review.

        Returns (approved: bool, reason: str, usage_tokens: int).

        CRITICAL FIX: On SDK failure, return (False, ...) NOT (True, ...).
        A failed review should NOT auto-approve; the subtask stays in its
        current state rather than being silently approved.
        """
        prompt = _REVIEW_PROMPT.format(
            description=description or "(no description)",
            output=output or "(empty output)",
        )
        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            reply = msg.content[0].text.strip()
            usage_tokens = getattr(msg.usage, "input_tokens", 0) + \
                           getattr(msg.usage, "output_tokens", 0)
        except Exception as exc:
            # CRITICAL FIX: On SDK failure, reject instead of auto-approve
            # This ensures the subtask doesn't get silently marked Verified
            return (
                False,
                f"SDK review unavailable — manual review required ({str(exc)[:100]})",
                0
            )

        approved, reason = self._parse_verdict(reply)
        return approved, reason, usage_tokens

    @staticmethod
    def _parse_verdict(reply: str) -> Tuple[bool, str]:
        """Parse Claude's APPROVED / REJECTED response."""
        line = reply.strip().splitlines()[0].strip() if reply.strip() else ""
        upper = line.upper()

        if upper.startswith("APPROVED"):
            return True, ""
        if upper.startswith("REJECTED"):
            reason = line.split(":", 1)[1].strip() if ":" in line else "no reason given"
            return False, reason

        # Ambiguous response — reject to avoid silent approval
        return False, f"ambiguous response (requires manual review): {line[:80]}"
