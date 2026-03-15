"""
utils/policy_engine.py
Human Oversight & Policy Engine — lightweight safety layer governing
which files and change sizes autonomous agents may modify.

Responsibilities:
    - Load policy configuration from settings (with safe defaults)
    - Evaluate file paths against allowed/blocked/critical patterns
    - Evaluate patch size against configurable limits
    - Return policy decisions: allowed / blocked / requires_review

Usage:
    policy = PolicyEngine(settings_dict)
    decision = policy.evaluate_path("src/app.py")
    decision = policy.evaluate_output(output_text)
    decision = policy.evaluate_patch_size(files_touched=5, lines_changed=200)

Decisions are returned as PolicyDecision named tuples with:
    action: "allowed" | "blocked" | "requires_review"
    reason: human-readable explanation (empty when allowed)
"""

import fnmatch
import re
from typing import Any, Dict, List, NamedTuple, Optional


class PolicyDecision(NamedTuple):
    """Result of a policy evaluation."""
    action: str      # "allowed" | "blocked" | "requires_review"
    reason: str      # explanation (empty when allowed)


# ── Defaults ────────────────────────────────────────────────────────────────

_DEFAULT_ALLOWED_PATHS: List[str] = []   # empty = allow all
_DEFAULT_BLOCKED_PATHS: List[str] = [
    ".github/workflows/*",
    ".gitlab-ci*",
    "Dockerfile*",
    "docker-compose*",
    "Makefile",
    "infrastructure/*",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
]
_DEFAULT_CRITICAL_PATTERNS: List[str] = [
    "*/migrations/*",
    "requirements*.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
]

_DEFAULT_MAX_FILES = 10
_DEFAULT_MAX_LINES = 500
_DEFAULT_MAX_PATCH_SIZE = 2000

# Pattern to extract file paths from executor output
_FILE_PATH_RE = re.compile(
    r'(?:^|[\s\'"`(])([a-zA-Z0-9_./-]+\.[a-zA-Z]{1,10})\b'
)
# Pattern to extract dotfiles like .env, .gitignore
_DOTFILE_RE = re.compile(
    r'(?:^|[\s\'"`(])(\.(?:env|gitignore|dockerignore|editorconfig|'
    r'env\.\w+|flake8|pylintrc|prettierrc|eslintrc)[a-zA-Z0-9_.]*)\b'
)


class PolicyEngine:
    """
    Evaluates file paths and patch sizes against configurable policies.

    All limits default to permissive values (0 = unlimited for size limits,
    empty allowed list = allow all) so existing behavior is preserved when
    policies are not configured.
    """

    def __init__(self, settings: Dict[str, Any] | None = None) -> None:
        cfg = settings or {}

        # Path policies
        self.allowed_paths: List[str] = cfg.get(
            "ALLOWED_AUTONOMOUS_PATHS", _DEFAULT_ALLOWED_PATHS
        )
        self.blocked_paths: List[str] = cfg.get(
            "BLOCKED_AUTONOMOUS_PATHS", _DEFAULT_BLOCKED_PATHS
        )
        self.critical_patterns: List[str] = cfg.get(
            "CRITICAL_PATH_PATTERNS", _DEFAULT_CRITICAL_PATTERNS
        )
        self.require_review_for_critical: bool = cfg.get(
            "REQUIRE_HUMAN_REVIEW_FOR_CRITICAL_PATHS", True
        )

        # Size policies (0 = unlimited)
        self.max_files: int = cfg.get(
            "MAX_FILES_MODIFIED_PER_SUBTASK", _DEFAULT_MAX_FILES
        )
        self.max_lines: int = cfg.get(
            "MAX_LINES_MODIFIED_PER_SUBTASK", _DEFAULT_MAX_LINES
        )
        self.max_patch_size: int = cfg.get(
            "MAX_PATCH_SIZE", _DEFAULT_MAX_PATCH_SIZE
        )

        # Counters for observability
        self.blocked_count: int = 0
        self.critical_review_count: int = 0
        self.oversized_patch_count: int = 0

    # ── Path evaluation ─────────────────────────────────────────────────

    def evaluate_path(self, filepath: str) -> PolicyDecision:
        """
        Evaluate a single file path against policy rules.

        Evaluation order:
            1. Check blocked paths → blocked
            2. Check allowed paths (if configured) → blocked if not matched
            3. Check critical patterns → requires_review
            4. Otherwise → allowed
        """
        normalized = filepath.replace("\\", "/").strip()
        if not normalized:
            return PolicyDecision("allowed", "")

        # 1. Blocked paths take priority
        for pattern in self.blocked_paths:
            if self._match(normalized, pattern):
                self.blocked_count += 1
                return PolicyDecision(
                    "blocked",
                    f"path '{normalized}' matches blocked pattern '{pattern}'"
                )

        # 2. Allowed paths (when configured, acts as allowlist)
        if self.allowed_paths:
            matched = any(
                self._match(normalized, p) for p in self.allowed_paths
            )
            if not matched:
                self.blocked_count += 1
                return PolicyDecision(
                    "blocked",
                    f"path '{normalized}' not in allowed paths"
                )

        # 3. Critical patterns → require review
        if self.require_review_for_critical:
            for pattern in self.critical_patterns:
                if self._match(normalized, pattern):
                    self.critical_review_count += 1
                    return PolicyDecision(
                        "requires_review",
                        f"path '{normalized}' matches critical pattern "
                        f"'{pattern}'"
                    )

        return PolicyDecision("allowed", "")

    def is_path_blocked(self, filepath: str) -> bool:
        """Quick check: is this path blocked by policy?"""
        return self.evaluate_path(filepath).action == "blocked"

    # ── Output evaluation ───────────────────────────────────────────────

    def evaluate_output(self, output: str) -> PolicyDecision:
        """
        Scan executor output text for file paths and evaluate each.

        Returns the most restrictive decision found:
            blocked > requires_review > allowed
        """
        if not output:
            return PolicyDecision("allowed", "")

        paths = self.extract_paths(output)
        worst = PolicyDecision("allowed", "")

        for path in paths:
            decision = self.evaluate_path(path)
            if decision.action == "blocked":
                return decision  # blocked is final
            if decision.action == "requires_review":
                worst = decision  # escalate to review

        return worst

    @staticmethod
    def extract_paths(text: str) -> List[str]:
        """Extract plausible file paths from output text."""
        candidates = _FILE_PATH_RE.findall(text)
        # Also capture dotfiles like .env, .gitignore
        candidates.extend(_DOTFILE_RE.findall(text))
        # Filter to paths that look like real files (contain / or common extensions)
        result: List[str] = []
        seen: set = set()
        for c in candidates:
            c = c.strip()
            if c in seen or len(c) < 3:
                continue
            seen.add(c)
            # Must contain a slash, start with dot, or have a recognizable extension
            if ("/" in c or c.startswith(".")
                    or c.endswith((".py", ".js", ".ts", ".json", ".yaml",
                                   ".yml", ".toml", ".cfg", ".ini",
                                   ".md", ".txt", ".html", ".css",
                                   ".sh", ".sql", ".xml"))):
                result.append(c)
        return result

    # ── Patch size evaluation ───────────────────────────────────────────

    def evaluate_patch_size(
        self,
        files_touched: int = 0,
        lines_changed: int = 0,
        patch_size: int = 0,
    ) -> PolicyDecision:
        """
        Evaluate patch dimensions against configured limits.

        Any exceeded limit triggers requires_review.
        All limits set to 0 means unlimited (always allowed).
        """
        reasons: List[str] = []

        if self.max_files > 0 and files_touched > self.max_files:
            reasons.append(
                f"files touched ({files_touched}) exceeds limit "
                f"({self.max_files})"
            )
        if self.max_lines > 0 and lines_changed > self.max_lines:
            reasons.append(
                f"lines changed ({lines_changed}) exceeds limit "
                f"({self.max_lines})"
            )
        if self.max_patch_size > 0 and patch_size > self.max_patch_size:
            reasons.append(
                f"patch size ({patch_size}) exceeds limit "
                f"({self.max_patch_size})"
            )

        if reasons:
            self.oversized_patch_count += 1
            return PolicyDecision(
                "requires_review",
                "; ".join(reasons),
            )

        return PolicyDecision("allowed", "")

    def estimate_output_size(self, output: str) -> Dict[str, int]:
        """
        Estimate patch dimensions from output text.

        Returns dict with files_touched, lines_changed, patch_size.
        """
        paths = self.extract_paths(output)
        lines = output.count("\n") + 1
        return {
            "files_touched": len(paths),
            "lines_changed": lines,
            "patch_size": len(output),
        }

    # ── Combined evaluation ─────────────────────────────────────────────

    def evaluate_patch(
        self,
        output: str,
        description: str = "",
    ) -> PolicyDecision:
        """
        Full policy evaluation of an executor output/patch.

        Checks paths and sizes. Returns the most restrictive decision.
        """
        # 1. Check file paths in output
        path_decision = self.evaluate_output(output)
        if path_decision.action == "blocked":
            return path_decision

        # 2. Check patch size
        size = self.estimate_output_size(output)
        size_decision = self.evaluate_patch_size(**size)

        # Return most restrictive
        if size_decision.action == "requires_review":
            return size_decision
        if path_decision.action == "requires_review":
            return path_decision

        return PolicyDecision("allowed", "")

    # ── Serialization ───────────────────────────────────────────────────

    def stats_dict(self) -> Dict[str, int]:
        """Return observability counters for persistence/display."""
        return {
            "policy_block_count": self.blocked_count,
            "critical_path_review_count": self.critical_review_count,
            "oversized_patch_count": self.oversized_patch_count,
        }

    def load_stats(self, data: Dict[str, Any]) -> None:
        """Restore counters from persisted state."""
        self.blocked_count = data.get("policy_block_count", 0)
        self.critical_review_count = data.get(
            "critical_path_review_count", 0
        )
        self.oversized_patch_count = data.get("oversized_patch_count", 0)

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _match(filepath: str, pattern: str) -> bool:
        """
        Match a filepath against a glob-like pattern.

        Supports:
            - fnmatch patterns: *.py, src/*.js
            - directory prefixes: config/ matches config/foo.py
            - ** for recursive matching
        """
        # Normalize
        fp = filepath.replace("\\", "/")
        pat = pattern.replace("\\", "/")

        # Direct fnmatch
        if fnmatch.fnmatch(fp, pat):
            return True

        # Directory prefix: "config/" matches "config/foo.py"
        if pat.endswith("/") and fp.startswith(pat):
            return True

        # Basename match for non-path patterns: "Makefile" matches "Makefile"
        if "/" not in pat and fnmatch.fnmatch(fp.rsplit("/", 1)[-1], pat):
            return True

        # Try with wildcard prefix for patterns starting with */
        if pat.startswith("*/"):
            # Match any directory prefix
            suffix = pat[2:]
            parts = fp.split("/")
            for i in range(len(parts)):
                candidate = "/".join(parts[i:])
                if fnmatch.fnmatch(candidate, suffix):
                    return True

        return False
