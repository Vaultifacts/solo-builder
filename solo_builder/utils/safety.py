"""
utils/safety.py
Dynamic Task Safety Guard — prevents duplicate findings and uncontrolled task generation.

Components:
    FindingHistory  — persistent dedup store for repo analysis
    normalize_finding_key() — stable key generation for dedup
"""

import json
import logging
import os
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


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
    Persistent dedup store for repository analysis findings.

    Saves to a sidecar JSON file alongside the state directory.
    Each entry records the normalized key and the step it was first seen.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join("state", "finding_history.json")
        self._entries: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> bool:
        """Load finding history from disk. Returns True on success."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
            return True
        except FileNotFoundError:
            return False
        except json.JSONDecodeError as e:
            logger.warning(
                f"Corrupt finding_history.json at {self.path}: {e}. Starting fresh."
            )
            self._entries = {}
            return False

    def save(self) -> None:
        """Save finding history to disk."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    def has_seen(self, category: str, filepath: str, detail: str) -> bool:
        """Return True if this finding (or a normalized equivalent) was already seen."""
        key = normalize_finding_key(category, filepath, detail)
        return key in self._entries

    def record(self, category: str, filepath: str, detail: str, step: int = 0) -> None:
        """Record a finding as known."""
        key = normalize_finding_key(category, filepath, detail)
        if key not in self._entries:
            self._entries[key] = {
                "first_seen": step,
                "category": category,
                "filepath": filepath,
            }

    def count(self) -> int:
        """Return the number of recorded findings."""
        return len(self._entries)

    def clear(self) -> None:
        """Clear all recorded findings."""
        self._entries.clear()
