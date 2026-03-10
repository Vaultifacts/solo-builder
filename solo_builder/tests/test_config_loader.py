"""Unit tests for solo_builder/config/loader.py (TD-ARCH-001 Phase 1).

Verifies that all 12 read-only constants are:
  - Exported from config.loader
  - Of the correct type
  - Non-empty / non-negative where applicable
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config.loader as loader


class TestConfigLoaderExports(unittest.TestCase):

    def test_dag_update_interval_is_positive_int(self):
        self.assertIsInstance(loader.DAG_UPDATE_INTERVAL, int)
        self.assertGreater(loader.DAG_UPDATE_INTERVAL, 0)

    def test_bar_width_is_positive_int(self):
        self.assertIsInstance(loader.BAR_WIDTH, int)
        self.assertGreater(loader.BAR_WIDTH, 0)

    def test_max_alerts_is_positive_int(self):
        self.assertIsInstance(loader.MAX_ALERTS, int)
        self.assertGreater(loader.MAX_ALERTS, 0)

    def test_exec_max_per_step_is_positive_int(self):
        self.assertIsInstance(loader.EXEC_MAX_PER_STEP, int)
        self.assertGreater(loader.EXEC_MAX_PER_STEP, 0)

    def test_max_subtasks_per_branch_is_positive_int(self):
        self.assertIsInstance(loader.MAX_SUBTASKS_PER_BRANCH, int)
        self.assertGreater(loader.MAX_SUBTASKS_PER_BRANCH, 0)

    def test_max_branches_per_task_is_positive_int(self):
        self.assertIsInstance(loader.MAX_BRANCHES_PER_TASK, int)
        self.assertGreater(loader.MAX_BRANCHES_PER_TASK, 0)

    def test_claude_timeout_is_positive_int(self):
        self.assertIsInstance(loader.CLAUDE_TIMEOUT, int)
        self.assertGreater(loader.CLAUDE_TIMEOUT, 0)

    def test_anthropic_model_is_nonempty_str(self):
        self.assertIsInstance(loader.ANTHROPIC_MODEL, str)
        self.assertTrue(loader.ANTHROPIC_MODEL)

    def test_anthropic_max_tokens_is_positive_int(self):
        self.assertIsInstance(loader.ANTHROPIC_MAX_TOKENS, int)
        self.assertGreater(loader.ANTHROPIC_MAX_TOKENS, 0)

    def test_review_mode_is_bool(self):
        self.assertIsInstance(loader.REVIEW_MODE, bool)

    def test_pdf_output_path_is_absolute_str(self):
        self.assertIsInstance(loader.PDF_OUTPUT_PATH, str)
        self.assertTrue(os.path.isabs(loader.PDF_OUTPUT_PATH),
                        f"PDF_OUTPUT_PATH should be absolute, got: {loader.PDF_OUTPUT_PATH!r}")

    def test_project_context_is_nonempty_str(self):
        self.assertIsInstance(loader._PROJECT_CONTEXT, str)
        self.assertIn("Solo Builder", loader._PROJECT_CONTEXT)


class TestConfigLoaderImportedInCLI(unittest.TestCase):
    """Re-imported names in solo_builder_cli must equal loader values."""

    def test_cli_imports_dag_update_interval(self):
        import solo_builder_cli as cli
        self.assertEqual(cli.DAG_UPDATE_INTERVAL, loader.DAG_UPDATE_INTERVAL)

    def test_cli_imports_pdf_output_path(self):
        import solo_builder_cli as cli
        self.assertEqual(cli.PDF_OUTPUT_PATH, loader.PDF_OUTPUT_PATH)

    def test_cli_imports_max_alerts(self):
        import solo_builder_cli as cli
        self.assertEqual(cli.MAX_ALERTS, loader.MAX_ALERTS)

    def test_cli_imports_anthropic_model(self):
        import solo_builder_cli as cli
        self.assertEqual(cli.ANTHROPIC_MODEL, loader.ANTHROPIC_MODEL)

    def test_cli_imports_project_context(self):
        import solo_builder_cli as cli
        self.assertEqual(cli._PROJECT_CONTEXT, loader._PROJECT_CONTEXT)


if __name__ == "__main__":
    unittest.main()
