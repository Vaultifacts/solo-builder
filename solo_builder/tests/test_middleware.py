"""Unit tests for SecurityHeadersMiddleware — TASK-331 (OM-041, BE-040)."""
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_response(headers=None):
    """Minimal dict-like response stub."""
    resp = MagicMock()
    resp.headers = {}
    if headers:
        resp.headers.update(headers)
    return resp


UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class TestSecurityHeadersMiddlewareCorrelation(unittest.TestCase):
    """X-Request-ID and X-API-Version behaviour (TASK-331)."""

    def setUp(self):
        from api.middleware import SecurityHeadersMiddleware
        self.mw = SecurityHeadersMiddleware()

    # ------------------------------------------------------------------
    # X-API-Version
    # ------------------------------------------------------------------
    def test_x_api_version_is_1(self):
        with patch("api.middleware._flask_request", None):
            resp = self.mw.apply(_make_response())
        self.assertEqual(resp.headers["X-API-Version"], "1")

    def test_x_api_version_on_post(self):
        """Header present regardless of HTTP method (simulated via apply() directly)."""
        with patch("api.middleware._flask_request", None):
            resp = self.mw.apply(_make_response())
        self.assertEqual(resp.headers["X-API-Version"], "1")

    # ------------------------------------------------------------------
    # X-Request-ID generation
    # ------------------------------------------------------------------
    def test_generates_uuid4_when_no_request_context(self):
        with patch("api.middleware._flask_request", None):
            resp = self.mw.apply(_make_response())
        req_id = resp.headers.get("X-Request-ID", "")
        self.assertRegex(req_id, UUID4_RE, f"Not a UUID4: {req_id!r}")

    def test_generates_different_id_each_call(self):
        with patch("api.middleware._flask_request", None):
            r1 = self.mw.apply(_make_response())
            r2 = self.mw.apply(_make_response())
        self.assertNotEqual(
            r1.headers["X-Request-ID"], r2.headers["X-Request-ID"]
        )

    def test_echoes_incoming_request_id(self):
        fake_req = MagicMock()
        fake_req.headers.get.return_value = "caller-trace-id-999"
        with patch("api.middleware._flask_request", fake_req):
            resp = self.mw.apply(_make_response())
        self.assertEqual(resp.headers["X-Request-ID"], "caller-trace-id-999")

    def test_generates_uuid_when_incoming_id_is_empty(self):
        fake_req = MagicMock()
        fake_req.headers.get.return_value = ""
        with patch("api.middleware._flask_request", fake_req):
            resp = self.mw.apply(_make_response())
        req_id = resp.headers.get("X-Request-ID", "")
        self.assertRegex(req_id, UUID4_RE)

    def test_generates_uuid_when_runtime_error(self):
        """Outside request context, RuntimeError is caught and ID is generated."""
        fake_req = MagicMock()
        fake_req.headers.get.side_effect = RuntimeError("no context")
        with patch("api.middleware._flask_request", fake_req):
            resp = self.mw.apply(_make_response())
        req_id = resp.headers.get("X-Request-ID", "")
        self.assertRegex(req_id, UUID4_RE)

    # ------------------------------------------------------------------
    # Existing headers still present
    # ------------------------------------------------------------------
    def test_existing_security_headers_intact(self):
        with patch("api.middleware._flask_request", None):
            resp = self.mw.apply(_make_response())
        h = resp.headers
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["Access-Control-Allow-Origin"], "*")


if __name__ == "__main__":
    unittest.main()
