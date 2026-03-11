"""Tests for webhook blueprint — POST /webhook (TASK-399)."""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

def _make_dag():
    return {
        "T0": {
            "branches": {
                "b0": {
                    "subtasks": {
                        "s1": {"status": "Verified"},
                        "s2": {"status": "Verified"},
                    }
                }
            }
        }
    }


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
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

    def _write_state(self, dag=None, step=5):
        state = {"step": step, "dag": dag if dag is not None else _make_dag()}
        self._state_path.write_text(json.dumps(state), encoding="utf-8")

    def _write_settings(self, **kwargs):
        self._settings_path.write_text(json.dumps(kwargs), encoding="utf-8")


# ---------------------------------------------------------------------------
# POST /webhook — no WEBHOOK_URL configured
# ---------------------------------------------------------------------------

class TestWebhookNoUrl(_Base):

    def test_returns_200_when_no_url(self):
        self._write_state()
        r = self.client.post("/webhook")
        self.assertEqual(r.status_code, 200)

    def test_ok_false_when_no_url(self):
        self._write_state()
        data = self.client.post("/webhook").get_json()
        self.assertFalse(data["ok"])

    def test_reason_includes_webhook_url(self):
        self._write_state()
        data = self.client.post("/webhook").get_json()
        self.assertIn("WEBHOOK_URL", data["reason"])

    def test_settings_file_missing_treated_as_no_url(self):
        self._write_state()
        self._settings_path.unlink()
        data = self.client.post("/webhook").get_json()
        self.assertFalse(data["ok"])


# ---------------------------------------------------------------------------
# POST /webhook — invalid URL (not http/https)
# ---------------------------------------------------------------------------

class TestWebhookInvalidUrl(_Base):

    def test_ftp_url_rejected(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="ftp://example.com/hook")
        data = self.client.post("/webhook").get_json()
        self.assertFalse(data["ok"])
        self.assertIn("http", data["reason"])

    def test_bare_hostname_rejected(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="example.com/hook")
        data = self.client.post("/webhook").get_json()
        self.assertFalse(data["ok"])


# ---------------------------------------------------------------------------
# POST /webhook — valid URL, network success
# ---------------------------------------------------------------------------

class TestWebhookSuccess(_Base):

    def _mock_urlopen(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_ok_true_on_success(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen()):
            data = self.client.post("/webhook").get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["sent"])

    def test_url_echoed_in_response(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen()):
            data = self.client.post("/webhook").get_json()
        self.assertEqual(data["url"], "https://example.com/hook")

    def test_http_url_accepted(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="http://localhost:9000/hook")
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen()):
            data = self.client.post("/webhook").get_json()
        self.assertTrue(data["ok"])

    def test_payload_includes_pct(self):
        self._write_state()  # 2 Verified / 2 total = 100%
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        captured_req = {}

        def fake_urlopen(req, timeout=10):
            captured_req["data"] = json.loads(req.data.decode())
            return self._mock_urlopen()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.client.post("/webhook")
        self.assertEqual(captured_req["data"]["pct"], 100.0)
        self.assertEqual(captured_req["data"]["event"], "complete")

    def test_payload_includes_step(self):
        self._write_state(step=7)
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["step"] = json.loads(req.data.decode())["step"]
            return self._mock_urlopen()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.client.post("/webhook")
        self.assertEqual(captured["step"], 7)


# ---------------------------------------------------------------------------
# POST /webhook — valid URL, network failure
# ---------------------------------------------------------------------------

class TestWebhookNetworkError(_Base):

    def test_ok_false_on_network_error(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            data = self.client.post("/webhook").get_json()
        self.assertFalse(data["ok"])
        self.assertFalse(data["sent"])

    def test_error_message_in_response(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            data = self.client.post("/webhook").get_json()
        self.assertIn("error", data)
        self.assertIn("timeout", data["error"])

    def test_still_returns_200_on_network_error(self):
        self._write_state()
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        with patch("urllib.request.urlopen", side_effect=OSError("fail")):
            r = self.client.post("/webhook")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# POST /webhook — pct calculation edge cases
# ---------------------------------------------------------------------------

class TestWebhookPctCalc(_Base):

    def test_pct_zero_when_none_verified(self):
        dag = {
            "T0": {
                "branches": {
                    "b0": {"subtasks": {"s1": {"status": "Pending"}}}
                }
            }
        }
        self._write_state(dag=dag)
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["pct"] = json.loads(req.data.decode())["pct"]
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.client.post("/webhook")
        self.assertEqual(captured["pct"], 0.0)

    def test_pct_zero_when_empty_dag(self):
        self._write_state(dag={})
        self._write_settings(WEBHOOK_URL="https://example.com/hook")
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["pct"] = json.loads(req.data.decode())["pct"]
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.client.post("/webhook")
        self.assertEqual(captured["pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
