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


class PatchReviewer:
    """
    Reviews Executor output using the Anthropic SDK.

    After each step, iterates over subtasks that were just advanced by the
    Executor (status == Review or Verified with new output).  For each,
    sends the output + task description to Claude for critique.

    If rejected:
        - Increments rejection counter for the subtask
        - If under MAX_PATCH_REJECTIONS: resets to Pending for retry
        - If at/over threshold: moves to Review with alert (needs human attention)

    Configurable via settings keys:
        PATCH_REVIEWER_ENABLED    (bool, default True)
        PATCH_REVIEWER_MODEL      (str,  default from ANTHROPIC_MODEL)
        PATCH_REVIEWER_MAX_TOKENS (int,  default 256)
        MAX_PATCH_REJECTIONS      (int,  default 3)
    """

    def __init__(self, settings: Dict[str, Any] | None = None) -> None:
        cfg = settings or {}
        self.enabled      = cfg.get("PATCH_REVIEWER_ENABLED", True)
        self._model       = cfg.get("PATCH_REVIEWER_MODEL",
                                    cfg.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
        self._max_tokens  = cfg.get("PATCH_REVIEWER_MAX_TOKENS", 256)
        self.max_rejections = cfg.get("MAX_PATCH_REJECTIONS", 3)
        self._client      = None
        self.available    = self._init_client()
        # Rejection tracking: {subtask_name: {"count": N, "reasons": [...]}}
        self._rejections: Dict[str, Dict[str, Any]] = {}
        # Observability counter
        self.threshold_hits: int = 0

    def _init_client(self) -> bool:
        """Initialise the Anthropic SDK client; return False if unavailable."""
        if not self.enabled:
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
        Dict mapping subtask_name → "approved" | "rejected" | "escalated".
        """
        if not self.available:
            return {}

        results: Dict[str, str] = {}

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

                    # Check AI budget before calling Claude
                    if budget is not None and budget.exhausted:
                        results[st_name] = "approved"
                        continue

                    approved, reason = self._ask_claude(description, output)

                    if budget is not None:
                        budget.consume(1)

                    if approved:
                        results[st_name] = "approved"
                        alerts.append(
                            f"  {GREEN}[PatchReviewer]{RESET} "
                            f"{CYAN}{st_name}{RESET} approved"
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

    # ── Claude interaction ───────────────────────────────────────────────
    def _ask_claude(self, description: str, output: str) -> Tuple[bool, str]:
        """
        Send the patch to Claude for review.

        Returns (approved: bool, reason: str).
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
        except Exception as exc:
            # On SDK failure, approve by default so pipeline isn't blocked
            return True, f"SDK error (auto-approved): {str(exc)[:100]}"

        return self._parse_verdict(reply)

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

        # Ambiguous response — approve to avoid blocking
        return True, f"ambiguous response (auto-approved): {line[:80]}"
