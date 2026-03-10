"""Tests for tools/config_drift.py (TASK-348, PW-010 to PW-015)."""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "config_drift", _TOOLS_DIR / "config_drift.py"
)
_mod = importlib.util.module_from_spec(_spec)
import sys as _sys
_sys.modules["config_drift"] = _mod
_spec.loader.exec_module(_mod)

detect_drift = _mod.detect_drift
DriftReport  = _mod.DriftReport
run          = _mod.run

_DEFAULTS = {"THRESHOLD": 5, "VERBOSITY": "INFO", "DEBUG": False}


# ---------------------------------------------------------------------------
# DriftReport
# ---------------------------------------------------------------------------

class TestDriftReport(unittest.TestCase):

    def test_no_drift_when_empty(self):
        r = DriftReport()
        self.assertFalse(r.has_drift)

    def test_missing_keys_alone_not_drift(self):
        r = DriftReport(missing_keys=["KEY_A"])
        self.assertFalse(r.has_drift)

    def test_overridden_keys_is_drift(self):
        r = DriftReport(overridden_keys=[{"key": "K", "default": 1, "live": 2}])
        self.assertTrue(r.has_drift)

    def test_unknown_keys_is_drift(self):
        r = DriftReport(unknown_keys=["NEW_KEY"])
        self.assertTrue(r.has_drift)

    def test_to_dict_structure(self):
        r = DriftReport(missing_keys=["A"], unknown_keys=["B"])
        d = r.to_dict()
        self.assertIn("has_drift", d)
        self.assertIn("missing_keys", d)
        self.assertIn("overridden_keys", d)
        self.assertIn("unknown_keys", d)


# ---------------------------------------------------------------------------
# detect_drift
# ---------------------------------------------------------------------------

class TestDetectDrift(unittest.TestCase):

    def _write_settings(self, tmp: Path, data: dict) -> Path:
        p = tmp / "settings.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_no_drift_when_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_settings(Path(tmp), dict(_DEFAULTS))
            report = detect_drift(settings_path=p, defaults=dict(_DEFAULTS))
        self.assertFalse(report.has_drift)
        self.assertEqual(report.missing_keys, [])
        self.assertEqual(report.overridden_keys, [])
        self.assertEqual(report.unknown_keys, [])

    def test_missing_key_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"THRESHOLD": 5}  # missing VERBOSITY and DEBUG
            p = self._write_settings(Path(tmp), data)
            report = detect_drift(settings_path=p, defaults=dict(_DEFAULTS))
        self.assertIn("VERBOSITY", report.missing_keys)
        self.assertIn("DEBUG", report.missing_keys)

    def test_overridden_key_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {**_DEFAULTS, "THRESHOLD": 99}
            p = self._write_settings(Path(tmp), data)
            report = detect_drift(settings_path=p, defaults=dict(_DEFAULTS))
        self.assertTrue(report.has_drift)
        keys = [e["key"] for e in report.overridden_keys]
        self.assertIn("THRESHOLD", keys)

    def test_override_entry_has_default_and_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {**_DEFAULTS, "THRESHOLD": 99}
            p = self._write_settings(Path(tmp), data)
            report = detect_drift(settings_path=p, defaults=dict(_DEFAULTS))
        entry = next(e for e in report.overridden_keys if e["key"] == "THRESHOLD")
        self.assertEqual(entry["default"], 5)
        self.assertEqual(entry["live"], 99)

    def test_unknown_key_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {**_DEFAULTS, "NEW_KEY": "value"}
            p = self._write_settings(Path(tmp), data)
            report = detect_drift(settings_path=p, defaults=dict(_DEFAULTS))
        self.assertIn("NEW_KEY", report.unknown_keys)

    def test_missing_file_returns_all_missing(self):
        report = detect_drift(
            settings_path="/nonexistent/settings.json",
            defaults=dict(_DEFAULTS),
        )
        # All keys are missing (live is empty)
        self.assertEqual(set(report.missing_keys), set(_DEFAULTS.keys()))

    def test_invalid_json_returns_all_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text("not json", encoding="utf-8")
            report = detect_drift(settings_path=p, defaults=dict(_DEFAULTS))
        self.assertEqual(set(report.missing_keys), set(_DEFAULTS.keys()))

    def test_exact_match_no_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_settings(Path(tmp), dict(_DEFAULTS))
            report = detect_drift(settings_path=p, defaults=dict(_DEFAULTS))
        self.assertFalse(report.has_drift)
        self.assertEqual(len(report.missing_keys), 0)


# ---------------------------------------------------------------------------
# run() — exit codes
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_on_no_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps(_DEFAULTS), encoding="utf-8")
            with patch.object(_mod, "_load_defaults", return_value=dict(_DEFAULTS)):
                code = run(quiet=True, settings_path=p)
        self.assertEqual(code, 0)

    def test_returns_1_on_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({**_DEFAULTS, "THRESHOLD": 99}), encoding="utf-8")
            with patch.object(_mod, "_load_defaults", return_value=dict(_DEFAULTS)):
                code = run(quiet=True, settings_path=p)
        self.assertEqual(code, 1)

    def test_json_output_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps(_DEFAULTS), encoding="utf-8")
            with patch.object(_mod, "_load_defaults", return_value=dict(_DEFAULTS)), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=True, settings_path=p)
                data = json.loads(mock_out.getvalue())
        self.assertIn("has_drift", data)
        self.assertIn("overridden_keys", data)
        self.assertIn("missing_keys", data)
        self.assertIn("unknown_keys", data)

    def test_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps(_DEFAULTS), encoding="utf-8")
            with patch.object(_mod, "_load_defaults", return_value=dict(_DEFAULTS)), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True, settings_path=p)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_text_output_shows_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({**_DEFAULTS, "THRESHOLD": 99}), encoding="utf-8")
            with patch.object(_mod, "_load_defaults", return_value=dict(_DEFAULTS)), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=False, settings_path=p)
                output = mock_out.getvalue()
        self.assertIn("THRESHOLD", output)
        self.assertIn("Drift", output)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_int(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps(_DEFAULTS), encoding="utf-8")
            with patch.object(_mod, "_load_defaults", return_value=dict(_DEFAULTS)):
                rc = _mod.main(["--quiet", "--settings", str(p)])
        self.assertIsInstance(rc, int)

    def test_main_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps(_DEFAULTS), encoding="utf-8")
            with patch.object(_mod, "_load_defaults", return_value=dict(_DEFAULTS)), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--json", "--settings", str(p)])
                data = json.loads(mock_out.getvalue())
        self.assertIn("has_drift", data)


if __name__ == "__main__":
    unittest.main()
