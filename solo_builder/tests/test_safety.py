"""Tests for utils/safety.py"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.safety import FindingHistory, normalize_finding_key


class TestNormalizeFindingKey(unittest.TestCase):
    """Test normalize_finding_key() function."""

    def test_todo_strips_line_number(self):
        key = normalize_finding_key("todo", "utils/foo.py", "L42 TODO: fix this")
        # Key is "todo::filepath::detail", detail should be lowercased and without L42
        self.assertNotIn("L42", key)
        self.assertIn("todo: fix this", key)

    def test_todo_lowercases_and_collapses_whitespace(self):
        key = normalize_finding_key("todo", "utils/foo.py", "TODO:  fix   THIS")
        self.assertIn("todo: fix this", key)

    def test_missing_docstring_extracts_function_name(self):
        key = normalize_finding_key(
            "missing_docstring", "utils/foo.py", "bar() at line 10"
        )
        self.assertIn("bar", key)
        self.assertNotIn("line", key)

    def test_missing_test_extracts_source_basename(self):
        key = normalize_finding_key(
            "missing_test", "utils/foo.py",
            "no test_{} found for bar.py"
        )
        self.assertIn("bar.py", key)
        self.assertNotIn("test_", key)

    def test_large_file_ignores_line_count(self):
        key1 = normalize_finding_key("large_file", "utils/foo.py", "500 lines")
        key2 = normalize_finding_key("large_file", "utils/foo.py", "600 lines")
        self.assertEqual(key1, key2)

    def test_key_includes_category_filepath_detail(self):
        key = normalize_finding_key("todo", "utils/foo.py", "TODO: fix")
        parts = key.split("::")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "todo")
        self.assertEqual(parts[1], "utils/foo.py")


class TestFindingHistoryBasics(unittest.TestCase):
    """Test FindingHistory basic operations."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.history_path = os.path.join(self.temp_dir, "finding_history.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_empty_history(self):
        h = FindingHistory(path=self.history_path)
        self.assertEqual(h.count(), 0)

    def test_record_adds_finding(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=1)
        self.assertEqual(h.count(), 1)

    def test_has_seen_returns_true_after_record(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=1)
        self.assertTrue(h.has_seen("todo", "utils/foo.py", "TODO: fix"))

    def test_has_seen_returns_false_for_unseen_finding(self):
        h = FindingHistory(path=self.history_path)
        self.assertFalse(h.has_seen("todo", "utils/foo.py", "TODO: fix"))

    def test_save_creates_file(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=1)
        h.save()
        self.assertTrue(os.path.exists(self.history_path))

    def test_load_reads_saved_findings(self):
        h1 = FindingHistory(path=self.history_path)
        h1.record("todo", "utils/foo.py", "TODO: fix", step=1)
        h1.save()

        h2 = FindingHistory(path=self.history_path)
        self.assertTrue(h2.has_seen("todo", "utils/foo.py", "TODO: fix"))

    def test_clear_removes_all_findings(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=1)
        h.record("todo", "utils/bar.py", "FIXME: test", step=2)
        self.assertEqual(h.count(), 2)
        h.clear()
        self.assertEqual(h.count(), 0)

    def test_record_duplicate_does_not_add_twice(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=1)
        h.record("todo", "utils/foo.py", "TODO: fix", step=2)
        self.assertEqual(h.count(), 1)
        # First step should be retained
        entry = h._entries[list(h._entries.keys())[0]]
        self.assertEqual(entry["first_seen"], 1)


class TestFindingHistoryPersistence(unittest.TestCase):
    """Test FindingHistory file persistence and error handling."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.history_path = os.path.join(self.temp_dir, "finding_history.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_returns_false_when_file_not_found(self):
        h = FindingHistory(path=self.history_path)
        result = h.load()
        self.assertFalse(result)

    def test_load_handles_corrupt_json_gracefully(self):
        # Write invalid JSON
        with open(self.history_path, "w") as f:
            f.write("{invalid json")

        # Should log warning and start fresh, not raise
        h = FindingHistory(path=self.history_path)
        self.assertEqual(h.count(), 0)

    def test_load_returns_false_for_corrupt_json(self):
        with open(self.history_path, "w") as f:
            f.write("{invalid json")

        h = FindingHistory(path=self.history_path)
        result = h.load()
        self.assertFalse(result)

    def test_save_creates_parent_dirs(self):
        nested_path = os.path.join(self.temp_dir, "a", "b", "c", "history.json")
        h = FindingHistory(path=nested_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=1)
        h.save()
        self.assertTrue(os.path.exists(nested_path))

    def test_saved_json_is_valid(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=1)
        h.save()

        with open(self.history_path) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_saved_json_preserves_metadata(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "TODO: fix", step=42)
        h.save()

        with open(self.history_path) as f:
            data = json.load(f)

        key = list(data.keys())[0]
        self.assertEqual(data[key]["first_seen"], 42)
        self.assertEqual(data[key]["category"], "todo")
        self.assertEqual(data[key]["filepath"], "utils/foo.py")


class TestFindingHistoryDedup(unittest.TestCase):
    """Test deduplication behavior with normalized keys."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.history_path = os.path.join(self.temp_dir, "finding_history.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_has_seen_dedupes_by_normalized_key(self):
        h = FindingHistory(path=self.history_path)
        # Record with line number
        h.record("todo", "utils/foo.py", "L42 TODO: fix this", step=1)

        # Query without line number should still match (normalized)
        result = h.has_seen("todo", "utils/foo.py", "TODO: fix this")
        self.assertTrue(result)

    def test_has_seen_ignores_large_file_line_count_changes(self):
        h = FindingHistory(path=self.history_path)
        h.record("large_file", "utils/foo.py", "500 lines", step=1)

        # Different line count should still be considered seen
        result = h.has_seen("large_file", "utils/foo.py", "600 lines")
        self.assertTrue(result)

    def test_different_categories_not_deduped(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "fix", step=1)

        # Different category, same filepath/detail → not a duplicate
        result = h.has_seen("large_file", "utils/foo.py", "fix")
        self.assertFalse(result)

    def test_different_files_not_deduped(self):
        h = FindingHistory(path=self.history_path)
        h.record("todo", "utils/foo.py", "fix", step=1)

        # Same category/detail but different file → not a duplicate
        result = h.has_seen("todo", "utils/bar.py", "fix")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
