"""Tests for config blueprint — GET /config, POST /config, GET /config/export,
POST /config/reset, GET /shortcuts, POST /set (TASK-401)."""
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


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

_SAMPLE_SETTINGS = {
    "STALL_THRESHOLD": 5,
    "SNAPSHOT_INTERVAL": 10,
    "DAG_UPDATE_INTERVAL": 2,
}


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._set_trigger = sp / "set_trigger.json"

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "SET_TRIGGER", new=self._set_trigger),
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

    def _write_settings(self, data=None):
        d = data if data is not None else dict(_SAMPLE_SETTINGS)
        self._settings_path.write_text(json.dumps(d), encoding="utf-8")


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------

class TestGetConfig(_Base):

    def test_returns_200_with_settings(self):
        self._write_settings()
        r = self.client.get("/config")
        self.assertEqual(r.status_code, 200)

    def test_returns_settings_data(self):
        self._write_settings()
        data = self.client.get("/config").get_json()
        self.assertEqual(data["STALL_THRESHOLD"], 5)

    def test_404_when_settings_file_missing(self):
        r = self.client.get("/config")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.get_json())

    def test_500_on_invalid_json(self):
        self._settings_path.write_text("not json", encoding="utf-8")
        r = self.client.get("/config")
        self.assertEqual(r.status_code, 500)
        self.assertIn("error", r.get_json())


# ---------------------------------------------------------------------------
# POST /config
# ---------------------------------------------------------------------------

class TestUpdateConfig(_Base):

    def test_updates_known_key(self):
        self._write_settings()
        r = self.client.post("/config", json={"STALL_THRESHOLD": 10})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["STALL_THRESHOLD"], 10)

    def test_persists_updated_value(self):
        self._write_settings()
        self.client.post("/config", json={"STALL_THRESHOLD": 99})
        saved = json.loads(self._settings_path.read_text())
        self.assertEqual(saved["STALL_THRESHOLD"], 99)

    def test_unknown_key_returns_400(self):
        self._write_settings()
        r = self.client.post("/config", json={"NONEXISTENT_KEY": 1})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_empty_body_returns_400(self):
        self._write_settings()
        r = self.client.post("/config", json={})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_no_json_body_returns_400(self):
        self._write_settings()
        r = self.client.post("/config")
        self.assertEqual(r.status_code, 400)

    def test_404_when_settings_missing(self):
        r = self.client.post("/config", json={"STALL_THRESHOLD": 5})
        self.assertEqual(r.status_code, 404)

    def test_multiple_keys_updated(self):
        self._write_settings()
        r = self.client.post(
            "/config",
            json={"STALL_THRESHOLD": 7, "SNAPSHOT_INTERVAL": 20},
        )
        self.assertTrue(r.get_json()["ok"])
        saved = json.loads(self._settings_path.read_text())
        self.assertEqual(saved["STALL_THRESHOLD"], 7)
        self.assertEqual(saved["SNAPSHOT_INTERVAL"], 20)

    def test_read_error_returns_500(self):
        self._write_settings()
        with patch.object(Path, "read_text", side_effect=OSError("fail")):
            r = self.client.post("/config", json={"STALL_THRESHOLD": 5})
        self.assertEqual(r.status_code, 500)


# ---------------------------------------------------------------------------
# GET /config/export
# ---------------------------------------------------------------------------

class TestExportConfig(_Base):

    def test_returns_200(self):
        self._write_settings()
        r = self.client.get("/config/export")
        self.assertEqual(r.status_code, 200)

    def test_content_disposition_attachment(self):
        self._write_settings()
        r = self.client.get("/config/export")
        self.assertIn("attachment", r.headers.get("Content-Disposition", ""))
        self.assertIn("settings.json", r.headers.get("Content-Disposition", ""))

    def test_mimetype_json(self):
        self._write_settings()
        r = self.client.get("/config/export")
        self.assertIn("application/json", r.content_type)

    def test_content_is_settings(self):
        self._write_settings()
        r = self.client.get("/config/export")
        data = json.loads(r.data)
        self.assertEqual(data["STALL_THRESHOLD"], 5)

    def test_404_when_settings_missing(self):
        r = self.client.get("/config/export")
        self.assertEqual(r.status_code, 404)

    def test_500_on_read_error(self):
        self._write_settings()
        with patch.object(Path, "read_bytes", side_effect=OSError("fail")):
            r = self.client.get("/config/export")
        self.assertEqual(r.status_code, 500)


# ---------------------------------------------------------------------------
# POST /config/reset
# ---------------------------------------------------------------------------

class TestResetConfig(_Base):

    def test_returns_ok(self):
        self._write_settings()
        data = self.client.post("/config/reset").get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["restored"])

    def test_restores_defaults(self):
        self._write_settings({"STALL_THRESHOLD": 99, "SNAPSHOT_INTERVAL": 99})
        self.client.post("/config/reset")
        saved = json.loads(self._settings_path.read_text())
        # Defaults from app_module._CONFIG_DEFAULTS
        for k, v in app_module._CONFIG_DEFAULTS.items():
            if k in saved:
                self.assertEqual(saved[k], v)

    def test_config_key_in_response(self):
        self._write_settings()
        data = self.client.post("/config/reset").get_json()
        self.assertIn("config", data)

    def test_409_when_settings_missing(self):
        r = self.client.post("/config/reset")
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.get_json()["ok"])

    def test_500_on_write_error(self):
        self._write_settings()
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            r = self.client.post("/config/reset")
        self.assertEqual(r.status_code, 500)


# ---------------------------------------------------------------------------
# GET /shortcuts
# ---------------------------------------------------------------------------

class TestShortcuts(_Base):

    def test_returns_200(self):
        r = self.client.get("/shortcuts")
        self.assertEqual(r.status_code, 200)

    def test_response_keys(self):
        data = self.client.get("/shortcuts").get_json()
        self.assertIn("shortcuts", data)
        self.assertIn("count", data)

    def test_count_matches_shortcuts_length(self):
        data = self.client.get("/shortcuts").get_json()
        self.assertEqual(data["count"], len(data["shortcuts"]))

    def test_shortcuts_is_list(self):
        data = self.client.get("/shortcuts").get_json()
        self.assertIsInstance(data["shortcuts"], list)


# ---------------------------------------------------------------------------
# POST /set
# ---------------------------------------------------------------------------

class TestSetSetting(_Base):

    def test_returns_202_with_valid_body(self):
        self._set_trigger.parent.mkdir(parents=True, exist_ok=True)
        r = self.client.post("/set", json={"key": "STALL_THRESHOLD", "value": "10"})
        self.assertEqual(r.status_code, 202)

    def test_missing_key_returns_400(self):
        r = self.client.post("/set", json={"value": "10"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_missing_value_returns_400(self):
        r = self.client.post("/set", json={"key": "STALL_THRESHOLD"})
        self.assertEqual(r.status_code, 400)

    def test_trigger_file_written(self):
        self._set_trigger.parent.mkdir(parents=True, exist_ok=True)
        self.client.post("/set", json={"key": "STALL_THRESHOLD", "value": "10"})
        self.assertTrue(self._set_trigger.exists())

    def test_trigger_contains_key_and_value(self):
        self._set_trigger.parent.mkdir(parents=True, exist_ok=True)
        self.client.post("/set", json={"key": "STALL_THRESHOLD", "value": "10"})
        payload = json.loads(self._set_trigger.read_text())
        self.assertIn("key", payload)
        self.assertIn("value", payload)


if __name__ == "__main__":
    unittest.main()
