"""Tests for live_summary blueprint — GET /health/live-summary."""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        self._state_path.write_text("{}", encoding="utf-8")
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "CACHE_DIR", new=Path(self._tmp) / "cache"),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestLiveSummaryAllPass(_Base):
    def test_all_checks_pass(self):
        from api.blueprints import live_summary as ls_mod
        mock_tm = MagicMock()
        mock_tm.run_checks.return_value = 0
        mock_cw = MagicMock()
        mock_cw.check.return_value = 0
        mock_slo = MagicMock()
        mock_slo._load_records.return_value = []
        mock_slo.METRICS_PATH = "fake"
        mock_slo.DEFAULT_MIN_RECORDS = 10

        with patch.object(ls_mod, "_load_tool", side_effect=lambda n: {
            "threat_model_check": mock_tm,
            "context_window_check": mock_cw,
            "slo_check": mock_slo,
        }[n]):
            r = self.client.get("/health/live-summary")
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["passed"], 3)
        self.assertEqual(d["total"], 3)
        self.assertEqual(len(d["checks"]), 3)


class TestLiveSummaryThreatModelFails(_Base):
    def test_threat_model_failure(self):
        from api.blueprints import live_summary as ls_mod
        mock_tm = MagicMock()
        mock_tm.run_checks.return_value = 1
        mock_cw = MagicMock()
        mock_cw.check.return_value = 0
        mock_slo = MagicMock()
        mock_slo._load_records.return_value = []
        mock_slo.METRICS_PATH = "fake"
        mock_slo.DEFAULT_MIN_RECORDS = 10

        with patch.object(ls_mod, "_load_tool", side_effect=lambda n: {
            "threat_model_check": mock_tm,
            "context_window_check": mock_cw,
            "slo_check": mock_slo,
        }[n]):
            r = self.client.get("/health/live-summary")
        d = r.get_json()
        self.assertFalse(d["ok"])
        self.assertEqual(d["passed"], 2)
        threat = next(c for c in d["checks"] if c["name"] == "threat-model")
        self.assertFalse(threat["ok"])


class TestLiveSummarySloWithRecords(_Base):
    def test_slo_with_enough_records(self):
        from api.blueprints import live_summary as ls_mod
        mock_tm = MagicMock()
        mock_tm.run_checks.return_value = 0
        mock_cw = MagicMock()
        mock_cw.check.return_value = 0
        mock_slo = MagicMock()
        records = [{"elapsed_s": 1.0}] * 15
        mock_slo._load_records.return_value = records
        mock_slo.METRICS_PATH = "fake"
        mock_slo.DEFAULT_MIN_RECORDS = 10
        mock_slo._check_slo003.return_value = {"status": "ok"}
        mock_slo._check_slo005.return_value = {"status": "ok"}

        with patch.object(ls_mod, "_load_tool", side_effect=lambda n: {
            "threat_model_check": mock_tm,
            "context_window_check": mock_cw,
            "slo_check": mock_slo,
        }[n]):
            r = self.client.get("/health/live-summary")
        d = r.get_json()
        self.assertTrue(d["ok"])

    def test_slo_failing(self):
        from api.blueprints import live_summary as ls_mod
        mock_tm = MagicMock()
        mock_tm.run_checks.return_value = 0
        mock_cw = MagicMock()
        mock_cw.check.return_value = 0
        mock_slo = MagicMock()
        records = [{"elapsed_s": 1.0}] * 15
        mock_slo._load_records.return_value = records
        mock_slo.METRICS_PATH = "fake"
        mock_slo.DEFAULT_MIN_RECORDS = 10
        mock_slo._check_slo003.return_value = {"status": "fail"}
        mock_slo._check_slo005.return_value = {"status": "ok"}

        with patch.object(ls_mod, "_load_tool", side_effect=lambda n: {
            "threat_model_check": mock_tm,
            "context_window_check": mock_cw,
            "slo_check": mock_slo,
        }[n]):
            r = self.client.get("/health/live-summary")
        d = r.get_json()
        self.assertFalse(d["ok"])
        slo = next(c for c in d["checks"] if c["name"] == "slo")
        self.assertFalse(slo["ok"])


class TestLiveSummaryCachedModule(_Base):
    def test_cached_module_path(self):
        from api.blueprints import live_summary as ls_mod
        mock_mod = MagicMock()
        mock_mod.run_checks.return_value = 0
        mock_mod.check.return_value = 0
        mock_mod._load_records.return_value = []
        mock_mod.METRICS_PATH = "fake"
        mock_mod.DEFAULT_MIN_RECORDS = 10

        with patch.dict(sys.modules, {
            "threat_model_check": mock_mod,
            "context_window_check": mock_mod,
            "slo_check": mock_mod,
        }):
            r = self.client.get("/health/live-summary")
        self.assertEqual(r.status_code, 200)


class TestLoadToolFreshImport(_Base):
    """Cover _load_tool lines 39-43 — importlib.util fresh load path."""

    def test_load_tool_fresh_import(self):
        from api.blueprints import live_summary as ls_mod
        import tempfile, os
        mod_name = "_test_ls_fresh_dummy"
        sys.modules.pop(mod_name, None)
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("MARKER = 'live_summary_test'\n")
            tmp_path = f.name
        try:
            from pathlib import Path as P
            tools_dir = P(tmp_path).parent
            file_name = P(tmp_path).stem
            with patch.object(ls_mod, "_TOOLS_DIR", new=tools_dir):
                result = ls_mod._load_tool(file_name)
            self.assertEqual(result.MARKER, "live_summary_test")
            self.assertIn(file_name, sys.modules)
        finally:
            os.unlink(tmp_path)
            sys.modules.pop(file_name, None)

    def test_load_tool_returns_cached(self):
        from api.blueprints import live_summary as ls_mod
        mod_name = "_test_ls_cached"
        fake = MagicMock()
        sys.modules[mod_name] = fake
        try:
            result = ls_mod._load_tool(mod_name)
            self.assertIs(result, fake)
        finally:
            sys.modules.pop(mod_name, None)


if __name__ == "__main__":
    unittest.main()
