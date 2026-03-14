"""Tests for WebSocket broadcaster (api/blueprints/ws.py) — TASK-416."""
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_ws():
    ws = MagicMock()
    ws.send = MagicMock()
    ws.receive = MagicMock(side_effect=Exception("closed"))
    return ws


class TestBroadcast(unittest.TestCase):
    """_broadcast() sends to all connected clients and purges dead ones."""

    def setUp(self):
        import importlib
        import api.blueprints.ws as ws_mod
        importlib.reload(ws_mod)
        self.mod = ws_mod

    def test_broadcast_sends_to_all(self):
        ws1, ws2 = _make_ws(), _make_ws()
        with self.mod._clients_lock:
            self.mod._clients.update({ws1, ws2})
        self.mod._broadcast('{"type":"change","step":5}')
        ws1.send.assert_called_once_with('{"type":"change","step":5}')
        ws2.send.assert_called_once_with('{"type":"change","step":5}')

    def test_broadcast_removes_dead_clients(self):
        ws_good = _make_ws()
        ws_dead = _make_ws()
        ws_dead.send.side_effect = Exception("connection lost")
        with self.mod._clients_lock:
            self.mod._clients.update({ws_good, ws_dead})
        self.mod._broadcast("ping")
        with self.mod._clients_lock:
            self.assertIn(ws_good, self.mod._clients)
            self.assertNotIn(ws_dead, self.mod._clients)

    def test_broadcast_empty_set_is_noop(self):
        with self.mod._clients_lock:
            self.mod._clients.clear()
        # Should not raise
        self.mod._broadcast("whatever")

    def test_client_count(self):
        with self.mod._clients_lock:
            self.mod._clients.clear()
        self.assertEqual(self.mod.client_count(), 0)
        ws = _make_ws()
        with self.mod._clients_lock:
            self.mod._clients.add(ws)
        self.assertEqual(self.mod.client_count(), 1)


class TestReadStep(unittest.TestCase):
    """_read_step() reads and parses step.txt correctly."""

    def setUp(self):
        import importlib
        import api.blueprints.ws as ws_mod
        importlib.reload(ws_mod)
        self.mod = ws_mod

    def _patch_path(self, text):
        p = MagicMock()
        p.read_text.return_value = text
        self.mod._step_path = p
        return p

    def test_reads_step_number(self):
        self._patch_path("42,10,50,30,5,2")
        self.assertEqual(self.mod._read_step(), 42)

    def test_single_value(self):
        self._patch_path("7")
        self.assertEqual(self.mod._read_step(), 7)

    def test_missing_file_returns_minus_one(self):
        p = MagicMock()
        p.read_text.side_effect = FileNotFoundError()
        self.mod._step_path = p
        self.assertEqual(self.mod._read_step(), -1)

    def test_malformed_file_returns_minus_one(self):
        self._patch_path("not-a-number")
        self.assertEqual(self.mod._read_step(), -1)


class TestHandleWs(unittest.TestCase):
    """handle_ws() registers/deregisters client and sends hello."""

    def setUp(self):
        import importlib
        import api.blueprints.ws as ws_mod
        importlib.reload(ws_mod)
        self.mod = ws_mod

    def test_client_registered_then_removed(self):
        ws = _make_ws()
        # _read_step will return -1 (no path set), so no hello is sent
        self.mod._step_path = MagicMock()
        self.mod._step_path.read_text.side_effect = FileNotFoundError()
        with self.mod._clients_lock:
            self.mod._clients.clear()
        self.mod.handle_ws(ws)
        # After handle_ws returns, client must be removed
        with self.mod._clients_lock:
            self.assertNotIn(ws, self.mod._clients)

    def test_hello_sent_on_connect(self):
        ws = _make_ws()
        self.mod._step_path = MagicMock()
        self.mod._step_path.read_text.return_value = "99,0,5,5,0,0"
        self.mod.handle_ws(ws)
        args = [call.args[0] for call in ws.send.call_args_list]
        hello_msgs = [a for a in args if '"type": "hello"' in a or '"step": 99' in a]
        self.assertTrue(hello_msgs, "Expected a hello message to be sent")
        payload = json.loads(hello_msgs[0])
        self.assertEqual(payload["step"], 99)

    def test_no_hello_when_step_missing(self):
        ws = _make_ws()
        self.mod._step_path = MagicMock()
        self.mod._step_path.read_text.side_effect = FileNotFoundError()
        self.mod.handle_ws(ws)
        ws.send.assert_not_called()


class TestWsRoute(unittest.TestCase):
    """Smoke test: /ws endpoint is registered in app."""

    def test_ws_route_exists_in_app(self):
        from api import app as app_module
        routes = {r.rule for r in app_module.app.url_map.iter_rules()}
        self.assertIn("/ws", routes)


if __name__ == "__main__":
    unittest.main()
