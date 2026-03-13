"""Tests for cache blueprint — GET/DELETE /cache, GET /cache/history, GET /cache/export (TASK-393)."""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._cache_dir = Path(self._tmp) / "cache"
        self._cache_dir.mkdir()
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "CACHE_DIR",      new=self._cache_dir),
            patch.object(app_module, "SETTINGS_PATH",  new=self._settings_path),
            patch.object(app_module, "STATE_PATH",     new=Path(self._tmp) / "state.json"),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read  = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_stats(self, data: dict):
        path = self._cache_dir / "session_stats.json"
        path.write_text(json.dumps(data), encoding="utf-8")

    def _make_cache_files(self, n: int):
        for i in range(n):
            (self._cache_dir / f"entry_{i}.json").write_text("{}", encoding="utf-8")


# ---------------------------------------------------------------------------
# GET /cache
# ---------------------------------------------------------------------------

class TestCacheStatsEndpoint(_Base):

    def test_cache_stats_returns_200(self):
        self.assertEqual(self.client.get("/cache").status_code, 200)

    def test_cache_stats_has_entries_key(self):
        data = self.client.get("/cache").get_json()
        self.assertIn("entries", data)

    def test_cache_stats_empty_dir_entries_zero(self):
        data = self.client.get("/cache").get_json()
        self.assertEqual(data["entries"], 0)

    def test_cache_stats_counts_json_files_excluding_stats_file(self):
        self._make_cache_files(3)
        # stats file should NOT be counted
        (self._cache_dir / "session_stats.json").write_text("{}", encoding="utf-8")
        data = self.client.get("/cache").get_json()
        self.assertEqual(data["entries"], 3)

    def test_cache_stats_cumulative_hits_from_stats_file(self):
        self._write_stats({"cumulative_hits": 42, "cumulative_misses": 8})
        data = self.client.get("/cache").get_json()
        self.assertEqual(data["cumulative_hits"], 42)
        self.assertEqual(data["cumulative_misses"], 8)

    def test_cache_stats_hit_rate_computed_correctly(self):
        self._write_stats({"cumulative_hits": 3, "cumulative_misses": 1})
        data = self.client.get("/cache").get_json()
        self.assertEqual(data["cumulative_hit_rate"], 75.0)

    def test_cache_stats_hit_rate_none_when_no_requests(self):
        data = self.client.get("/cache").get_json()
        self.assertIsNone(data["cumulative_hit_rate"])

    def test_cache_stats_has_cache_dir_key(self):
        data = self.client.get("/cache").get_json()
        self.assertIn("cache_dir", data)


# ---------------------------------------------------------------------------
# DELETE /cache
# ---------------------------------------------------------------------------

class TestCacheClearEndpoint(_Base):

    def test_delete_cache_returns_200(self):
        self.assertEqual(self.client.delete("/cache").status_code, 200)

    def test_delete_cache_ok_true(self):
        self.assertTrue(self.client.delete("/cache").get_json()["ok"])

    def test_delete_cache_empty_dir_deleted_zero(self):
        data = self.client.delete("/cache").get_json()
        self.assertEqual(data["deleted"], 0)

    def test_delete_cache_removes_json_files(self):
        self._make_cache_files(3)
        data = self.client.delete("/cache").get_json()
        self.assertEqual(data["deleted"], 3)
        remaining = list(self._cache_dir.glob("*.json"))
        self.assertEqual(len(remaining), 0)

    def test_delete_cache_preserves_stats_file(self):
        self._make_cache_files(2)
        self._write_stats({"cumulative_hits": 10})
        self.client.delete("/cache")
        self.assertTrue((self._cache_dir / "session_stats.json").exists())

    def test_delete_cache_nonexistent_dir_ok(self):
        import shutil
        shutil.rmtree(self._cache_dir)
        data = self.client.delete("/cache").get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["deleted"], 0)


# ---------------------------------------------------------------------------
# GET /cache/history
# ---------------------------------------------------------------------------

class TestCacheHistoryEndpoint(_Base):

    def test_cache_history_returns_200(self):
        self.assertEqual(self.client.get("/cache/history").status_code, 200)

    def test_cache_history_no_file_returns_empty_sessions(self):
        data = self.client.get("/cache/history").get_json()
        self.assertEqual(data["sessions"], [])
        self.assertEqual(data["cumulative_hits"], 0)
        self.assertEqual(data["cumulative_misses"], 0)

    def test_cache_history_sessions_numbered_from_one(self):
        self._write_stats({"sessions": [{"hits": 5, "misses": 2}]})
        data = self.client.get("/cache/history").get_json()
        self.assertEqual(data["sessions"][0]["session"], 1)

    def test_cache_history_hit_rate_computed(self):
        self._write_stats({"sessions": [{"hits": 3, "misses": 1}]})
        data = self.client.get("/cache/history").get_json()
        self.assertEqual(data["sessions"][0]["hit_rate"], 75.0)

    def test_cache_history_hit_rate_none_when_zero(self):
        self._write_stats({"sessions": [{"hits": 0, "misses": 0}]})
        data = self.client.get("/cache/history").get_json()
        self.assertIsNone(data["sessions"][0]["hit_rate"])

    def test_cache_history_since_filters_earlier_sessions(self):
        self._write_stats({"sessions": [
            {"hits": 1, "misses": 0},
            {"hits": 2, "misses": 0},
            {"hits": 3, "misses": 0},
        ]})
        data = self.client.get("/cache/history?since=1").get_json()
        # sessions 2 and 3 only
        self.assertEqual(len(data["sessions"]), 2)
        self.assertEqual(data["sessions"][0]["session"], 2)

    def test_cache_history_cumulative_totals_from_file(self):
        self._write_stats({"sessions": [], "cumulative_hits": 99, "cumulative_misses": 11})
        data = self.client.get("/cache/history").get_json()
        self.assertEqual(data["cumulative_hits"], 99)
        self.assertEqual(data["cumulative_misses"], 11)


# ---------------------------------------------------------------------------
# GET /cache/export
# ---------------------------------------------------------------------------

class TestCacheExportEndpoint(_Base):

    def test_cache_export_default_returns_csv(self):
        r = self.client.get("/cache/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_cache_export_csv_has_header_row(self):
        r = self.client.get("/cache/export")
        text = r.data.decode("utf-8")
        self.assertIn("session", text)
        self.assertIn("hits", text)
        self.assertIn("misses", text)

    def test_cache_export_json_format_returns_list(self):
        self._write_stats({"sessions": [{"hits": 1, "misses": 0}]})
        r = self.client.get("/cache/export?format=json")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)

    def test_cache_export_json_includes_session_data(self):
        self._write_stats({"sessions": [{"hits": 4, "misses": 1}]})
        data = self.client.get("/cache/export?format=json").get_json()
        self.assertEqual(data[0]["hits"], 4)
        self.assertEqual(data[0]["misses"], 1)

    def test_cache_export_since_filters_rows(self):
        self._write_stats({"sessions": [
            {"hits": 1, "misses": 0},
            {"hits": 2, "misses": 0},
            {"hits": 3, "misses": 0},
        ]})
        data = self.client.get("/cache/export?format=json&since=1").get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["session"], 2)

    def test_cache_export_limit_returns_most_recent(self):
        self._write_stats({"sessions": [
            {"hits": 1, "misses": 0},
            {"hits": 2, "misses": 0},
            {"hits": 3, "misses": 0},
        ]})
        data = self.client.get("/cache/export?format=json&limit=2").get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["session"], 2)
        self.assertEqual(data[1]["session"], 3)

    def test_cache_export_no_file_returns_empty_csv(self):
        r = self.client.get("/cache/export")
        self.assertEqual(r.status_code, 200)
        text = r.data.decode("utf-8")
        lines = [l for l in text.strip().splitlines() if l]
        self.assertEqual(len(lines), 1)  # header only

    def test_cache_export_no_file_json_returns_empty_list(self):
        data = self.client.get("/cache/export?format=json").get_json()
        self.assertEqual(data, [])

    def test_cache_export_csv_content_disposition_header(self):
        r = self.client.get("/cache/export")
        self.assertIn("cache.csv", r.headers.get("Content-Disposition", ""))


# ---------------------------------------------------------------------------
# Error paths — cache_stats (line 26-27), cache_clear (58-61), history (77-78), export (121-122)
# ---------------------------------------------------------------------------

class TestCacheStatsError(_Base):
    def test_cache_stats_error_when_cache_dir_unreadable(self):
        with patch.object(app_module, "CACHE_DIR", new=Path(self._tmp) / "nonexistent"):
            # exists() returns False → empty list, no error
            d = self.client.get("/cache").get_json()
            self.assertEqual(d["entries"], 0)

    def test_cache_stats_glob_exception_returns_500(self):
        from unittest.mock import PropertyMock
        bad = Path(self._tmp) / "bad_cache"
        bad.mkdir()
        with patch.object(app_module, "CACHE_DIR", new=bad), \
             patch.object(Path, "glob", side_effect=PermissionError("denied")):
            r = self.client.get("/cache")
            self.assertEqual(r.status_code, 500)
            self.assertIn("error", r.get_json())


class TestCacheClearError(_Base):
    def test_delete_cache_unlink_oserror_counts_errors(self):
        self._make_cache_files(2)
        orig_unlink = Path.unlink
        call_count = [0]
        def failing_unlink(self_path, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("locked")
            orig_unlink(self_path, *a, **kw)
        with patch.object(Path, "unlink", failing_unlink):
            data = self.client.delete("/cache").get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["errors"], 1)
        self.assertEqual(data["deleted"], 1)

    def test_delete_cache_glob_exception_returns_500(self):
        with patch.object(Path, "glob", side_effect=PermissionError("denied")):
            r = self.client.delete("/cache")
            self.assertEqual(r.status_code, 500)
            self.assertIn("error", r.get_json())


class TestCacheHistoryError(_Base):
    def test_cache_history_corrupt_stats_returns_500(self):
        stats_path = self._cache_dir / "session_stats.json"
        stats_path.write_text("NOT JSON", encoding="utf-8")
        r = self.client.get("/cache/history")
        self.assertEqual(r.status_code, 500)
        self.assertIn("error", r.get_json())


class TestCacheExportError(_Base):
    def test_cache_export_corrupt_stats_returns_500(self):
        stats_path = self._cache_dir / "session_stats.json"
        stats_path.write_text("NOT JSON", encoding="utf-8")
        r = self.client.get("/cache/export")
        self.assertEqual(r.status_code, 500)
        self.assertIn("error", r.get_json())


if __name__ == "__main__":
    unittest.main()
