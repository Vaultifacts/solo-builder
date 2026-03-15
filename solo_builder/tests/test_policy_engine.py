"""Tests for utils/policy_engine.py — execution-time file/patch safety layer."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.policy_engine import PolicyDecision, PolicyEngine


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------

class TestPolicyDecision(unittest.TestCase):

    def test_named_tuple_fields(self):
        d = PolicyDecision("allowed", "")
        self.assertEqual(d.action, "allowed")
        self.assertEqual(d.reason, "")

    def test_blocked_decision(self):
        d = PolicyDecision("blocked", "matches .env")
        self.assertEqual(d.action, "blocked")
        self.assertIn(".env", d.reason)


# ---------------------------------------------------------------------------
# evaluate_path — blocked patterns
# ---------------------------------------------------------------------------

class TestEvaluatePathBlocked(unittest.TestCase):

    def setUp(self):
        self.engine = PolicyEngine()

    def test_env_file_blocked(self):
        d = self.engine.evaluate_path(".env")
        self.assertEqual(d.action, "blocked")

    def test_env_variant_blocked(self):
        d = self.engine.evaluate_path(".env.production")
        self.assertEqual(d.action, "blocked")

    def test_pem_file_blocked(self):
        d = self.engine.evaluate_path("certs/server.pem")
        self.assertEqual(d.action, "blocked")

    def test_key_file_blocked(self):
        d = self.engine.evaluate_path("secrets/private.key")
        self.assertEqual(d.action, "blocked")

    def test_dockerfile_blocked(self):
        d = self.engine.evaluate_path("Dockerfile")
        self.assertEqual(d.action, "blocked")

    def test_docker_compose_blocked(self):
        d = self.engine.evaluate_path("docker-compose.yml")
        self.assertEqual(d.action, "blocked")

    def test_github_workflow_blocked(self):
        d = self.engine.evaluate_path(".github/workflows/ci.yml")
        self.assertEqual(d.action, "blocked")

    def test_makefile_blocked(self):
        d = self.engine.evaluate_path("Makefile")
        self.assertEqual(d.action, "blocked")

    def test_infrastructure_dir_blocked(self):
        d = self.engine.evaluate_path("infrastructure/main.tf")
        self.assertEqual(d.action, "blocked")

    def test_blocked_counter_increments(self):
        self.engine.evaluate_path(".env")
        self.engine.evaluate_path("Makefile")
        self.assertEqual(self.engine.blocked_count, 2)


# ---------------------------------------------------------------------------
# evaluate_path — critical patterns (requires_review)
# ---------------------------------------------------------------------------

class TestEvaluatePathCritical(unittest.TestCase):

    def setUp(self):
        self.engine = PolicyEngine()

    def test_requirements_txt_critical(self):
        d = self.engine.evaluate_path("requirements.txt")
        self.assertEqual(d.action, "requires_review")

    def test_pyproject_toml_critical(self):
        d = self.engine.evaluate_path("pyproject.toml")
        self.assertEqual(d.action, "requires_review")

    def test_package_json_critical(self):
        d = self.engine.evaluate_path("package.json")
        self.assertEqual(d.action, "requires_review")

    def test_migrations_critical(self):
        d = self.engine.evaluate_path("db/migrations/001_init.sql")
        self.assertEqual(d.action, "requires_review")

    def test_setup_py_critical(self):
        d = self.engine.evaluate_path("setup.py")
        self.assertEqual(d.action, "requires_review")

    def test_pipfile_lock_critical(self):
        d = self.engine.evaluate_path("Pipfile.lock")
        self.assertEqual(d.action, "requires_review")

    def test_critical_counter_increments(self):
        self.engine.evaluate_path("requirements.txt")
        self.engine.evaluate_path("pyproject.toml")
        self.assertEqual(self.engine.critical_review_count, 2)

    def test_critical_disabled(self):
        engine = PolicyEngine({"REQUIRE_HUMAN_REVIEW_FOR_CRITICAL_PATHS": False})
        d = engine.evaluate_path("requirements.txt")
        self.assertEqual(d.action, "allowed")


# ---------------------------------------------------------------------------
# evaluate_path — allowed
# ---------------------------------------------------------------------------

class TestEvaluatePathAllowed(unittest.TestCase):

    def setUp(self):
        self.engine = PolicyEngine()

    def test_normal_python_file_allowed(self):
        d = self.engine.evaluate_path("src/app.py")
        self.assertEqual(d.action, "allowed")

    def test_normal_js_file_allowed(self):
        d = self.engine.evaluate_path("api/static/dashboard.js")
        self.assertEqual(d.action, "allowed")

    def test_empty_path_allowed(self):
        d = self.engine.evaluate_path("")
        self.assertEqual(d.action, "allowed")

    def test_whitespace_path_allowed(self):
        d = self.engine.evaluate_path("   ")
        self.assertEqual(d.action, "allowed")


# ---------------------------------------------------------------------------
# evaluate_path — allowlist mode
# ---------------------------------------------------------------------------

class TestEvaluatePathAllowlist(unittest.TestCase):

    def test_path_in_allowlist_passes(self):
        engine = PolicyEngine({"ALLOWED_AUTONOMOUS_PATHS": ["src/*.py"]})
        d = engine.evaluate_path("src/app.py")
        self.assertEqual(d.action, "allowed")

    def test_path_not_in_allowlist_blocked(self):
        engine = PolicyEngine({"ALLOWED_AUTONOMOUS_PATHS": ["src/*.py"]})
        d = engine.evaluate_path("lib/util.py")
        self.assertEqual(d.action, "blocked")

    def test_blocked_takes_priority_over_allowlist(self):
        engine = PolicyEngine({
            "ALLOWED_AUTONOMOUS_PATHS": ["*"],
            "BLOCKED_AUTONOMOUS_PATHS": [".env"],
        })
        d = engine.evaluate_path(".env")
        self.assertEqual(d.action, "blocked")


# ---------------------------------------------------------------------------
# evaluate_patch_size
# ---------------------------------------------------------------------------

class TestEvaluatePatchSize(unittest.TestCase):

    def setUp(self):
        self.engine = PolicyEngine()

    def test_within_limits_allowed(self):
        d = self.engine.evaluate_patch_size(files_touched=3, lines_changed=100)
        self.assertEqual(d.action, "allowed")

    def test_exceeds_max_files(self):
        d = self.engine.evaluate_patch_size(files_touched=15)
        self.assertEqual(d.action, "requires_review")
        self.assertIn("files touched", d.reason)

    def test_exceeds_max_lines(self):
        d = self.engine.evaluate_patch_size(lines_changed=600)
        self.assertEqual(d.action, "requires_review")
        self.assertIn("lines changed", d.reason)

    def test_exceeds_max_patch_size(self):
        d = self.engine.evaluate_patch_size(patch_size=3000)
        self.assertEqual(d.action, "requires_review")
        self.assertIn("patch size", d.reason)

    def test_zero_limits_means_unlimited(self):
        engine = PolicyEngine({
            "MAX_FILES_MODIFIED_PER_SUBTASK": 0,
            "MAX_LINES_MODIFIED_PER_SUBTASK": 0,
            "MAX_PATCH_SIZE": 0,
        })
        d = engine.evaluate_patch_size(files_touched=999, lines_changed=9999)
        self.assertEqual(d.action, "allowed")

    def test_oversized_counter_increments(self):
        self.engine.evaluate_patch_size(files_touched=15)
        self.engine.evaluate_patch_size(lines_changed=600)
        self.assertEqual(self.engine.oversized_patch_count, 2)


# ---------------------------------------------------------------------------
# extract_paths
# ---------------------------------------------------------------------------

class TestExtractPaths(unittest.TestCase):

    def test_extracts_python_files(self):
        text = "Modified src/app.py and tests/test_app.py"
        paths = PolicyEngine.extract_paths(text)
        self.assertIn("src/app.py", paths)
        self.assertIn("tests/test_app.py", paths)

    def test_extracts_dotfiles(self):
        text = "Also touched .env and .gitignore"
        paths = PolicyEngine.extract_paths(text)
        self.assertIn(".env", paths)
        self.assertIn(".gitignore", paths)

    def test_deduplicates(self):
        text = "Changed src/app.py then read src/app.py again"
        paths = PolicyEngine.extract_paths(text)
        self.assertEqual(paths.count("src/app.py"), 1)

    def test_empty_input(self):
        self.assertEqual(PolicyEngine.extract_paths(""), [])

    def test_no_paths(self):
        paths = PolicyEngine.extract_paths("just some text with no files")
        self.assertEqual(paths, [])


# ---------------------------------------------------------------------------
# evaluate_output
# ---------------------------------------------------------------------------

class TestEvaluateOutput(unittest.TestCase):

    def setUp(self):
        self.engine = PolicyEngine()

    def test_output_with_blocked_path(self):
        d = self.engine.evaluate_output("Writing to .env with secrets")
        self.assertEqual(d.action, "blocked")

    def test_output_with_critical_path(self):
        d = self.engine.evaluate_output("Updated requirements.txt with new dep")
        self.assertEqual(d.action, "requires_review")

    def test_output_with_safe_paths(self):
        d = self.engine.evaluate_output("Edited src/utils.py")
        self.assertEqual(d.action, "allowed")

    def test_empty_output(self):
        d = self.engine.evaluate_output("")
        self.assertEqual(d.action, "allowed")

    def test_none_output(self):
        d = self.engine.evaluate_output(None)
        self.assertEqual(d.action, "allowed")


# ---------------------------------------------------------------------------
# evaluate_patch (combined)
# ---------------------------------------------------------------------------

class TestEvaluatePatch(unittest.TestCase):

    def setUp(self):
        self.engine = PolicyEngine()

    def test_blocked_path_in_output(self):
        d = self.engine.evaluate_patch("Modified .env file")
        self.assertEqual(d.action, "blocked")

    def test_oversized_output(self):
        big = "line\n" * 600 + "edited src/app.py"
        d = self.engine.evaluate_patch(big)
        self.assertEqual(d.action, "requires_review")

    def test_safe_small_patch(self):
        d = self.engine.evaluate_patch("Fixed typo in src/app.py")
        self.assertEqual(d.action, "allowed")


# ---------------------------------------------------------------------------
# estimate_output_size
# ---------------------------------------------------------------------------

class TestEstimateOutputSize(unittest.TestCase):

    def test_counts_lines(self):
        engine = PolicyEngine()
        result = engine.estimate_output_size("line1\nline2\nline3")
        self.assertEqual(result["lines_changed"], 3)

    def test_counts_patch_size(self):
        engine = PolicyEngine()
        text = "hello world"
        result = engine.estimate_output_size(text)
        self.assertEqual(result["patch_size"], len(text))


# ---------------------------------------------------------------------------
# stats_dict / load_stats
# ---------------------------------------------------------------------------

class TestStatsSerialization(unittest.TestCase):

    def test_roundtrip(self):
        engine = PolicyEngine()
        engine.blocked_count = 5
        engine.critical_review_count = 3
        engine.oversized_patch_count = 1
        stats = engine.stats_dict()

        engine2 = PolicyEngine()
        engine2.load_stats(stats)
        self.assertEqual(engine2.blocked_count, 5)
        self.assertEqual(engine2.critical_review_count, 3)
        self.assertEqual(engine2.oversized_patch_count, 1)

    def test_load_empty_dict(self):
        engine = PolicyEngine()
        engine.load_stats({})
        self.assertEqual(engine.blocked_count, 0)


# ---------------------------------------------------------------------------
# _match helper
# ---------------------------------------------------------------------------

class TestMatch(unittest.TestCase):

    def test_fnmatch_wildcard(self):
        self.assertTrue(PolicyEngine._match("src/app.py", "*.py"))

    def test_directory_prefix(self):
        self.assertTrue(PolicyEngine._match("config/foo.py", "config/"))

    def test_basename_match(self):
        self.assertTrue(PolicyEngine._match("deep/nested/Makefile", "Makefile"))

    def test_star_slash_prefix(self):
        self.assertTrue(PolicyEngine._match("db/migrations/001.sql", "*/migrations/*"))

    def test_no_match(self):
        self.assertFalse(PolicyEngine._match("src/app.py", "*.js"))

    def test_backslash_normalized(self):
        self.assertTrue(PolicyEngine._match("src\\app.py", "*.py"))


# ---------------------------------------------------------------------------
# is_path_blocked convenience
# ---------------------------------------------------------------------------

class TestIsPathBlocked(unittest.TestCase):

    def test_blocked_returns_true(self):
        engine = PolicyEngine()
        self.assertTrue(engine.is_path_blocked(".env"))

    def test_allowed_returns_false(self):
        engine = PolicyEngine()
        self.assertFalse(engine.is_path_blocked("src/app.py"))


# ---------------------------------------------------------------------------
# Custom settings
# ---------------------------------------------------------------------------

class TestCustomSettings(unittest.TestCase):

    def test_custom_blocked_paths(self):
        engine = PolicyEngine({"BLOCKED_AUTONOMOUS_PATHS": ["secrets/*"]})
        d = engine.evaluate_path("secrets/api_key.txt")
        self.assertEqual(d.action, "blocked")
        # Default .env no longer blocked
        d2 = engine.evaluate_path(".env")
        self.assertEqual(d2.action, "allowed")

    def test_custom_critical_patterns(self):
        engine = PolicyEngine({"CRITICAL_PATH_PATTERNS": ["*.sql"]})
        d = engine.evaluate_path("db/schema.sql")
        self.assertEqual(d.action, "requires_review")
        # Default requirements.txt no longer critical
        d2 = engine.evaluate_path("requirements.txt")
        self.assertEqual(d2.action, "allowed")

    def test_custom_size_limits(self):
        engine = PolicyEngine({
            "MAX_FILES_MODIFIED_PER_SUBTASK": 3,
            "MAX_LINES_MODIFIED_PER_SUBTASK": 50,
        })
        d = engine.evaluate_patch_size(files_touched=4)
        self.assertEqual(d.action, "requires_review")

    def test_none_settings(self):
        engine = PolicyEngine(None)
        self.assertIsInstance(engine, PolicyEngine)


if __name__ == "__main__":
    unittest.main()
