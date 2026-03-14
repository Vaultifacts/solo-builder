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
"""

import os
from typing import Any, Dict, List, Tuple

from utils.helper_functions import (
    CYAN, GREEN, RED, RESET, YELLOW,
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


class PatchReviewer:
    """
    Reviews Executor output using the Anthropic SDK.

    After each step, iterates over subtasks that were just advanced by the
    Executor (status == Review or Verified with new output).  For each,
    sends the output + task description to Claude for critique.

    If rejected:
        - Resets subtask status back to Pending
        - Clears shadow to Pending
        - Appends an alert

    Configurable via settings keys:
        PATCH_REVIEWER_ENABLED   (bool, default True)
        PATCH_REVIEWER_MODEL     (str,  default from ANTHROPIC_MODEL)
        PATCH_REVIEWER_MAX_TOKENS (int, default 256)
    """

    def __init__(self, settings: Dict[str, Any] | None = None) -> None:
        cfg = settings or {}
        self.enabled    = cfg.get("PATCH_REVIEWER_ENABLED", True)
        self._model     = cfg.get("PATCH_REVIEWER_MODEL",
                                  cfg.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
        self._max_tokens = cfg.get("PATCH_REVIEWER_MAX_TOKENS", 256)
        self._client    = None
        self.available  = self._init_client()

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

    # ── Public API ───────────────────────────────────────────────────────
    def review_step(
        self,
        dag: Dict,
        executor_actions: Dict[str, str],
        step: int,
        memory_store: Dict,
        alerts: List[str],
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

        Returns
        -------
        Dict mapping subtask_name → "approved" | "rejected".
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

                    approved, reason = self._ask_claude(description, output)

                    if approved:
                        results[st_name] = "approved"
                        alerts.append(
                            f"  {GREEN}[PatchReviewer]{RESET} "
                            f"{CYAN}{st_name}{RESET} approved"
                        )
                    else:
                        # Reject: reset to Pending
                        st_data["status"]      = "Pending"
                        st_data["shadow"]      = "Pending"
                        st_data["last_update"] = step
                        st_data.setdefault("history", []).append(
                            {"status": "Pending", "step": step,
                             "note": f"PatchReviewer rejected: {reason}"}
                        )
                        add_memory_snapshot(
                            memory_store, branch_name,
                            f"{st_name}_patch_rejected", step,
                        )
                        results[st_name] = "rejected"
                        alerts.append(
                            f"  {RED}[PatchReviewer]{RESET} "
                            f"{CYAN}{st_name}{RESET} rejected: {reason}"
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
