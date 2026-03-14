"""
utils/safety.py
Dynamic Task Safety Guard — prevents runaway task generation, duplicate
findings, infinite retry loops, and uncontrolled AI usage.

Components:
    FindingHistory  — persistent dedup store for RepoAnalyzer
    StepBudget      — per-step AI call counter
    normalize_finding_key() — stable key generation for dedup
"""

import json
import os
import re
from typing import Any, Dict, Tuple


# ── Finding normalization ────────────────────────────────────────────────────

# Strip line-number prefixes like "L123 " from TODO details
_LINE_NUM_RE = re.compile(r"^L\d+\s*")
# Collapse whitespace
_WS_RE = re.compile(r"\s+")


def normalize_finding_key(category: str, filepath: str, detail: str) -> str:
    """
    Produce a stable dedup key for a finding.

    Normalization:
        - category: lowercased
        - filepath: as-is (already relative)
        - detail:
            - TODO/FIXME: strip line number prefix, lowercase, collapse whitespace
            - missing_docstring: extract function name only
            - missing_test: extract source filename only
            - large_file: use filepath only (line count may change)
    """
    cat = category.lower()
    norm_detail = detail.strip()

    if cat == "todo":
        # Strip "L123 " prefix, lowercase, collapse ws
        norm_detail = _LINE_NUM_RE.sub("", norm_detail)
        norm_detail = _WS_RE.sub(" ", norm_detail.lower()).strip()
    elif cat == "missing_docstring":
        # Extract just the function name: "foo() at line 42" → "foo"
        m = re.match(r"(\w+)\(\)", norm_detail)
        norm_detail = m.group(1) if m else norm_detail.lower()
    elif cat == "missing_test":
        # Extract source basename: "no test_{} found for foo.py" → "foo.py"
        m = re.search(r"for\s+(\S+\.py)", norm_detail)
        norm_detail = m.group(1) if m else norm_detail.lower()
    elif cat == "large_file":
        # Line count changes shouldn't generate new findings
        norm_detail = ""

    return f"{cat}::{filepath}::{norm_detail}"


# ── Persistent Finding History ───────────────────────────────────────────────

class FindingHistory:
    """
    Persistent dedup store for RepoAnalyzer findings.

    Saves to a sidecar JSON file alongside the state directory.
    Each entry records the normalized key and the step it was first seen.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join("state", "finding_history.json")
        self._entries: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> bool:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    def is_known(self, category: str, filepath: str, detail: str) -> bool:
        """Return True if this finding (or a normalized equivalent) was already seen."""
        key = normalize_finding_key(category, filepath, detail)
        return key in self._entries

    def record(self, category: str, filepath: str, detail: str, step: int) -> None:
        """Record a finding as known."""
        key = normalize_finding_key(category, filepath, detail)
        if key not in self._entries:
            self._entries[key] = {"first_seen": step, "category": category,
                                  "filepath": filepath}

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()


# ── Per-Step AI Budget ───────────────────────────────────────────────────────

class StepBudget:
    """
    Tracks AI-backed calls within a single pipeline step.
    Once the budget is exhausted, agents should defer work.
    """

    def __init__(self, max_calls: int = 0) -> None:
        self.max_calls = max_calls   # 0 = unlimited
        self.used      = 0
        self.deferred  = 0           # count of work items deferred

    @property
    def exhausted(self) -> bool:
        if self.max_calls <= 0:
            return False
        return self.used >= self.max_calls

    def consume(self, n: int = 1) -> bool:
        """
        Try to consume n calls from the budget.
        Returns True if allowed, False if budget exhausted.
        """
        if self.max_calls <= 0:
            self.used += n
            return True
        if self.used + n > self.max_calls:
            self.deferred += n
            return False
        self.used += n
        return True

    @property
    def remaining(self) -> int:
        if self.max_calls <= 0:
            return -1   # unlimited
        return max(0, self.max_calls - self.used)
