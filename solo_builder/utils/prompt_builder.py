"""Prompt builder — TASK-337 (AI-002).

Provides a structured way to assemble Claude prompts that are consistent with
the Prompt Engineering Standard (docs/PROMPT_STANDARD.md).

A PromptTemplate wraps a fixed instruction block and renders it with
per-call context variables.  All templates are registered in the module-level
REGISTRY so that regression tests can verify every template's structure
without needing to construct a prompt.

Usage:
    from utils.prompt_builder import PromptTemplate, build_subtask_prompt

    # Build the standard subtask execution prompt
    prompt = build_subtask_prompt(
        project_context="Context: Solo Builder is…",
        description="Implement the login endpoint",
    )
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------

REGISTRY: dict[str, "PromptTemplate"] = {}

_BLANK_RE = re.compile(r"\{\s*\}")  # detect empty placeholders


@dataclass
class PromptTemplate:
    """Immutable prompt template with named {placeholder} slots.

    Parameters
    ----------
    name:           Registry key — must be unique.
    template:       Template string.  Use {variable} for runtime values.
    required_vars:  Variable names that must be supplied on render().
    optional_vars:  Variable names that may be omitted (default to "").

    Raises
    ------
    ValueError  if the template contains empty {} placeholders.
    """

    name:          str
    template:      str
    required_vars: list[str] = field(default_factory=list)
    optional_vars: list[str] = field(default_factory=list)

    _instances: ClassVar[dict[str, "PromptTemplate"]] = REGISTRY

    def __post_init__(self) -> None:
        if _BLANK_RE.search(self.template):
            raise ValueError(
                f"PromptTemplate '{self.name}' contains empty '{{}}' placeholder. "
                "Use named placeholders like {variable_name}."
            )
        if self.name in self._instances:
            raise ValueError(f"PromptTemplate name '{self.name}' is already registered.")
        self._instances[self.name] = self

    def render(self, **kwargs: str) -> str:
        """Render the template with the supplied keyword arguments.

        Missing required variables raise ValueError.
        Missing optional variables default to empty string.
        Extra keyword arguments are silently ignored.
        """
        values: dict[str, str] = {}
        for var in self.required_vars:
            if var not in kwargs:
                raise ValueError(
                    f"PromptTemplate '{self.name}': missing required variable '{var}'."
                )
            values[var] = str(kwargs[var])
        for var in self.optional_vars:
            values[var] = str(kwargs.get(var, ""))
        # Include any extra kwargs that appear in the template
        for key, val in kwargs.items():
            if key not in values:
                values[key] = str(val)
        return self.template.format_map(values)

    @property
    def placeholder_names(self) -> set[str]:
        """Return the set of {placeholder} names found in the template string."""
        return set(re.findall(r"\{(\w+)\}", self.template))


# ---------------------------------------------------------------------------
# Standard templates (registered at import time)
# ---------------------------------------------------------------------------

SUBTASK_EXECUTION = PromptTemplate(
    name="subtask_execution",
    template=(
        "{project_context}"
        "Task: {description}\n"
        "Complete this task. Return only the result — no preamble, no explanation."
    ),
    required_vars=["project_context", "description"],
)

SUBTASK_VERIFICATION = PromptTemplate(
    name="subtask_verification",
    template=(
        "{project_context}"
        "You previously executed: {description}\n"
        "Output was:\n{output}\n\n"
        "Did the output fully satisfy the task? "
        "Reply with exactly 'YES' or 'NO', then one sentence of explanation."
    ),
    required_vars=["project_context", "description", "output"],
)

STALL_RECOVERY = PromptTemplate(
    name="stall_recovery",
    template=(
        "{project_context}"
        "Subtask '{subtask_name}' has been stuck in '{current_status}' "
        "for {stall_steps} steps.\n"
        "Original description: {description}\n"
        "Last output (if any): {last_output}\n\n"
        "Diagnose the stall and provide a corrected approach. "
        "Be concise — one paragraph maximum."
    ),
    required_vars=["project_context", "subtask_name", "current_status",
                   "stall_steps", "description"],
    optional_vars=["last_output"],
)


# ---------------------------------------------------------------------------
# Public convenience functions
# ---------------------------------------------------------------------------

def build_subtask_prompt(project_context: str, description: str) -> str:
    """Assemble the standard subtask execution prompt."""
    return SUBTASK_EXECUTION.render(
        project_context=project_context,
        description=description,
    )


def build_verification_prompt(project_context: str, description: str,
                               output: str) -> str:
    """Assemble the standard subtask verification prompt."""
    return SUBTASK_VERIFICATION.render(
        project_context=project_context,
        description=description,
        output=output,
    )


def build_stall_recovery_prompt(project_context: str, subtask_name: str,
                                 current_status: str, stall_steps: int,
                                 description: str, last_output: str = "") -> str:
    """Assemble the stall-recovery prompt."""
    return STALL_RECOVERY.render(
        project_context=project_context,
        subtask_name=subtask_name,
        current_status=current_status,
        stall_steps=str(stall_steps),
        description=description,
        last_output=last_output,
    )
