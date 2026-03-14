#!/usr/bin/env python3
"""
tests/test_policy_engine.py — Tests for the PolicyEngine module.

Covers:
    - Blocked path enforcement
    - Allowed path enforcement (allowlist mode)
    - Critical path review gating
    - Patch size limits (files, lines, patch_size)
    - Path extraction from output text
    - Combined evaluate_patch decisions
    - Pattern matching edge cases
    - Stats serialization/deserialization
    - Backward compatibility with missing policy config

Run:
    python -m pytest tests/test_policy_engine.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.policy_engine import PolicyEngine, PolicyDecision


class TestPathMatching(unittest.TestCase):
    """PolicyEngine._match covers glob, directory prefix, basename patterns."""

    def test_glob_star(self):
        self.assertTrue(PolicyEngine._match("config/foo.yaml", "config/*"))

    def test_glob_extension(self):
        self.assertTrue(PolicyEngine._match("secrets.pem", "*.pem"))

    def test_directory_prefix(self):
        self.assertTrue(PolicyEngine._match(
            "infrastructure/terraform/main.tf", "infrastructure/*"
        ))

    def test_basename_match(self):
        self.assertTrue(PolicyEngine._match("Makefile", "Makefile"))

    def test_deep_basename(self):
        self.assertTrue(PolicyEngine._match("build/Makefile", "Makefile"))

    def test_no_match(self):
        self.assertFalse(PolicyEngine._match("src/app.py", "config/*"))

    def test_star_slash_recursive(self):
        self.assertTrue(PolicyEngine._match(
            "app/db/migrations/001.sql", "*/migrations/*"
        ))

    def test_double_star_env(self):
        self.assertTrue(PolicyEngine._match(".env", ".env"))
        self.assertTrue(PolicyEngine._match(".env.local", ".env.*"))

    def test_dockerfile_glob(self):
        self.assertTrue(PolicyEngine._match("Dockerfile", "Dockerfile*"))
        self.assertTrue(PolicyEngine._match("Dockerfile.prod", "Dockerfile*"))


class TestBlockedPaths(unittest.TestCase):
    """Blocked paths result in 'blocked' decisions."""

    def setUp(self):
        self.pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [
                "config/*",
                "ci/*",
                "infrastructure/*",
                "*.pem",
                ".env",
            ],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
        })

    def test_blocked_config(self):
        d = self.pe.evaluate_path("config/database.yaml")
        self.assertEqual(d.action, "blocked")
        self.assertIn("config/*", d.reason)

    def test_blocked_infra(self):
        d = self.pe.evaluate_path("infrastructure/main.tf")
        self.assertEqual(d.action, "blocked")

    def test_blocked_pem(self):
        d = self.pe.evaluate_path("certs/server.pem")
        self.assertEqual(d.action, "blocked")

    def test_blocked_env(self):
        d = self.pe.evaluate_path(".env")
        self.assertEqual(d.action, "blocked")

    def test_allowed_src(self):
        d = self.pe.evaluate_path("src/app.py")
        self.assertEqual(d.action, "allowed")

    def test_blocked_increments_counter(self):
        self.pe.evaluate_path("config/x.yaml")
        self.pe.evaluate_path("config/y.yaml")
        self.assertEqual(self.pe.blocked_count, 2)


class TestAllowedPaths(unittest.TestCase):
    """When ALLOWED_AUTONOMOUS_PATHS is set, only those paths pass."""

    def setUp(self):
        self.pe = PolicyEngine({
            "ALLOWED_AUTONOMOUS_PATHS": ["src/*", "tests/*"],
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
        })

    def test_allowed_src(self):
        d = self.pe.evaluate_path("src/app.py")
        self.assertEqual(d.action, "allowed")

    def test_allowed_tests(self):
        d = self.pe.evaluate_path("tests/test_foo.py")
        self.assertEqual(d.action, "allowed")

    def test_blocked_other(self):
        d = self.pe.evaluate_path("config/settings.json")
        self.assertEqual(d.action, "blocked")
        self.assertIn("not in allowed paths", d.reason)

    def test_blocked_root_file(self):
        d = self.pe.evaluate_path("README.md")
        self.assertEqual(d.action, "blocked")


class TestCriticalPaths(unittest.TestCase):
    """Critical path patterns trigger requires_review."""

    def setUp(self):
        self.pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [
                "*/migrations/*",
                "requirements*.txt",
                "pyproject.toml",
            ],
            "REQUIRE_HUMAN_REVIEW_FOR_CRITICAL_PATHS": True,
        })

    def test_migrations_critical(self):
        d = self.pe.evaluate_path("app/db/migrations/001_initial.py")
        self.assertEqual(d.action, "requires_review")
        self.assertIn("migrations", d.reason)

    def test_requirements_critical(self):
        d = self.pe.evaluate_path("requirements.txt")
        self.assertEqual(d.action, "requires_review")

    def test_requirements_dev_critical(self):
        d = self.pe.evaluate_path("requirements-dev.txt")
        self.assertEqual(d.action, "requires_review")

    def test_pyproject_critical(self):
        d = self.pe.evaluate_path("pyproject.toml")
        self.assertEqual(d.action, "requires_review")

    def test_normal_file_allowed(self):
        d = self.pe.evaluate_path("src/utils.py")
        self.assertEqual(d.action, "allowed")

    def test_critical_increments_counter(self):
        self.pe.evaluate_path("requirements.txt")
        self.pe.evaluate_path("pyproject.toml")
        self.assertEqual(self.pe.critical_review_count, 2)

    def test_critical_disabled(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": ["requirements*.txt"],
            "REQUIRE_HUMAN_REVIEW_FOR_CRITICAL_PATHS": False,
        })
        d = pe.evaluate_path("requirements.txt")
        self.assertEqual(d.action, "allowed")


class TestBlockedBeforeCritical(unittest.TestCase):
    """Blocked paths take priority over critical patterns."""

    def test_blocked_wins_over_critical(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": ["*.toml"],
            "CRITICAL_PATH_PATTERNS": ["pyproject.toml"],
        })
        d = pe.evaluate_path("pyproject.toml")
        self.assertEqual(d.action, "blocked")


class TestPatchSizeLimits(unittest.TestCase):
    """Patch size checks trigger requires_review."""

    def test_files_limit(self):
        pe = PolicyEngine({"MAX_FILES_MODIFIED_PER_SUBTASK": 3})
        d = pe.evaluate_patch_size(files_touched=5)
        self.assertEqual(d.action, "requires_review")
        self.assertIn("files touched", d.reason)

    def test_lines_limit(self):
        pe = PolicyEngine({"MAX_LINES_MODIFIED_PER_SUBTASK": 100})
        d = pe.evaluate_patch_size(lines_changed=200)
        self.assertEqual(d.action, "requires_review")
        self.assertIn("lines changed", d.reason)

    def test_patch_size_limit(self):
        pe = PolicyEngine({"MAX_PATCH_SIZE": 500})
        d = pe.evaluate_patch_size(patch_size=1000)
        self.assertEqual(d.action, "requires_review")
        self.assertIn("patch size", d.reason)

    def test_within_limits(self):
        pe = PolicyEngine({
            "MAX_FILES_MODIFIED_PER_SUBTASK": 10,
            "MAX_LINES_MODIFIED_PER_SUBTASK": 500,
            "MAX_PATCH_SIZE": 2000,
        })
        d = pe.evaluate_patch_size(files_touched=5, lines_changed=100, patch_size=500)
        self.assertEqual(d.action, "allowed")

    def test_zero_means_unlimited(self):
        pe = PolicyEngine({
            "MAX_FILES_MODIFIED_PER_SUBTASK": 0,
            "MAX_LINES_MODIFIED_PER_SUBTASK": 0,
            "MAX_PATCH_SIZE": 0,
        })
        d = pe.evaluate_patch_size(files_touched=999, lines_changed=99999, patch_size=999999)
        self.assertEqual(d.action, "allowed")

    def test_oversized_increments_counter(self):
        pe = PolicyEngine({"MAX_FILES_MODIFIED_PER_SUBTASK": 2})
        pe.evaluate_patch_size(files_touched=5)
        pe.evaluate_patch_size(files_touched=3)
        self.assertEqual(pe.oversized_patch_count, 2)


class TestPathExtraction(unittest.TestCase):
    """extract_paths finds file paths in output text."""

    def test_basic_paths(self):
        text = "Modified src/app.py and tests/test_app.py"
        paths = PolicyEngine.extract_paths(text)
        self.assertIn("src/app.py", paths)
        self.assertIn("tests/test_app.py", paths)

    def test_quoted_paths(self):
        text = 'Updated "config/settings.json" successfully'
        paths = PolicyEngine.extract_paths(text)
        self.assertIn("config/settings.json", paths)

    def test_no_duplicates(self):
        text = "Read src/app.py, then wrote src/app.py again"
        paths = PolicyEngine.extract_paths(text)
        self.assertEqual(paths.count("src/app.py"), 1)

    def test_empty_output(self):
        paths = PolicyEngine.extract_paths("")
        self.assertEqual(paths, [])


class TestEvaluateOutput(unittest.TestCase):
    """evaluate_output scans text for paths and returns most restrictive."""

    def test_blocked_path_in_output(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": ["config/*"],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
        })
        d = pe.evaluate_output("Modified config/database.yaml and src/app.py")
        self.assertEqual(d.action, "blocked")

    def test_critical_path_in_output(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": ["requirements*.txt"],
        })
        d = pe.evaluate_output("Updated requirements.txt with new deps")
        self.assertEqual(d.action, "requires_review")

    def test_clean_output(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": ["config/*"],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
        })
        d = pe.evaluate_output("Modified src/app.py")
        self.assertEqual(d.action, "allowed")


class TestEvaluatePatch(unittest.TestCase):
    """evaluate_patch combines path and size checks."""

    def test_blocked_path_trumps_size(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [".env"],
            "MAX_FILES_MODIFIED_PER_SUBTASK": 0,  # unlimited
        })
        d = pe.evaluate_patch("Changed .env file")
        self.assertEqual(d.action, "blocked")

    def test_oversized_triggers_review(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
            "MAX_PATCH_SIZE": 10,  # very small
        })
        d = pe.evaluate_patch("x" * 100)
        self.assertEqual(d.action, "requires_review")

    def test_clean_small_patch(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
            "MAX_PATCH_SIZE": 10000,
        })
        d = pe.evaluate_patch("Updated src/app.py with fix")
        self.assertEqual(d.action, "allowed")


class TestStatsSerializaton(unittest.TestCase):
    """Stats persist and restore correctly."""

    def test_stats_dict(self):
        pe = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": ["config/*"],
            "CRITICAL_PATH_PATTERNS": ["requirements*.txt"],
            "ALLOWED_AUTONOMOUS_PATHS": [],
        })
        pe.evaluate_path("config/x.yaml")
        pe.evaluate_path("requirements.txt")
        pe.evaluate_patch_size(files_touched=999)

        stats = pe.stats_dict()
        self.assertEqual(stats["policy_block_count"], 1)
        self.assertEqual(stats["critical_path_review_count"], 1)
        self.assertEqual(stats["oversized_patch_count"], 1)

    def test_load_stats(self):
        pe = PolicyEngine()
        pe.load_stats({
            "policy_block_count": 10,
            "critical_path_review_count": 5,
            "oversized_patch_count": 3,
        })
        self.assertEqual(pe.blocked_count, 10)
        self.assertEqual(pe.critical_review_count, 5)
        self.assertEqual(pe.oversized_patch_count, 3)

    def test_load_stats_missing_keys(self):
        pe = PolicyEngine()
        pe.load_stats({})
        self.assertEqual(pe.blocked_count, 0)
        self.assertEqual(pe.critical_review_count, 0)
        self.assertEqual(pe.oversized_patch_count, 0)


class TestBackwardCompatibility(unittest.TestCase):
    """PolicyEngine works with empty or missing config."""

    def test_no_config(self):
        pe = PolicyEngine()
        # Should use defaults but not crash
        d = pe.evaluate_path("src/app.py")
        self.assertEqual(d.action, "allowed")

    def test_none_config(self):
        pe = PolicyEngine(None)
        d = pe.evaluate_path("src/app.py")
        self.assertEqual(d.action, "allowed")

    def test_empty_config(self):
        pe = PolicyEngine({})
        d = pe.evaluate_path("src/app.py")
        self.assertEqual(d.action, "allowed")

    def test_defaults_block_env(self):
        pe = PolicyEngine({})
        d = pe.evaluate_path(".env")
        self.assertEqual(d.action, "blocked")

    def test_defaults_critical_requirements(self):
        pe = PolicyEngine({})
        d = pe.evaluate_path("requirements.txt")
        self.assertEqual(d.action, "requires_review")

    def test_empty_path(self):
        pe = PolicyEngine()
        d = pe.evaluate_path("")
        self.assertEqual(d.action, "allowed")

    def test_empty_output(self):
        pe = PolicyEngine()
        d = pe.evaluate_output("")
        self.assertEqual(d.action, "allowed")


class TestPolicyDecisionNamedTuple(unittest.TestCase):
    """PolicyDecision is a proper NamedTuple."""

    def test_fields(self):
        d = PolicyDecision("allowed", "")
        self.assertEqual(d.action, "allowed")
        self.assertEqual(d.reason, "")

    def test_equality(self):
        d1 = PolicyDecision("blocked", "reason")
        d2 = PolicyDecision("blocked", "reason")
        self.assertEqual(d1, d2)


if __name__ == "__main__":
    unittest.main()
