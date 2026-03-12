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


class TestApiRateLimiter(unittest.TestCase):
    """ApiRateLimiter — sliding-window behaviour and app-level override."""

    def setUp(self):
        from api.middleware import ApiRateLimiter
        self._cls = ApiRateLimiter

    def test_default_read_limit_is_120(self):
        lim = self._cls()
        self.assertEqual(lim.read_limit, 120)

    def test_default_write_limit_is_30(self):
        lim = self._cls()
        self.assertEqual(lim.write_limit, 30)

    def test_app_rate_limiter_read_limit_is_300(self):
        import api.app as app_module
        self.assertEqual(app_module._rate_limiter.read_limit, 300)

    def test_allows_requests_within_read_limit(self):
        lim = self._cls(read_limit=5, window=60.0)
        for _ in range(5):
            self.assertTrue(lim.check("127.0.0.1", is_write=False))

    def test_blocks_request_over_read_limit(self):
        lim = self._cls(read_limit=3, window=60.0)
        for _ in range(3):
            lim.check("127.0.0.1", is_write=False)
        self.assertFalse(lim.check("127.0.0.1", is_write=False))

    def test_write_limit_enforced_independently(self):
        lim = self._cls(read_limit=100, write_limit=2, window=60.0)
        for _ in range(2):
            lim.check("127.0.0.1", is_write=True)
        self.assertFalse(lim.check("127.0.0.1", is_write=True))
        # reads still allowed
        self.assertTrue(lim.check("127.0.0.1", is_write=False))

    def test_different_ips_tracked_separately(self):
        lim = self._cls(read_limit=1, window=60.0)
        lim.check("1.1.1.1", is_write=False)
        self.assertFalse(lim.check("1.1.1.1", is_write=False))
        self.assertTrue(lim.check("2.2.2.2", is_write=False))

    def test_window_expiry_allows_new_requests(self):
        import time
        lim = self._cls(read_limit=1, window=0.05)
        lim.check("127.0.0.1", is_write=False)
        self.assertFalse(lim.check("127.0.0.1", is_write=False))
        time.sleep(0.1)
        self.assertTrue(lim.check("127.0.0.1", is_write=False))


class TestRateLimiterCurrentCount(unittest.TestCase):
    """Tests for ApiRateLimiter.current_count (monitoring helper)."""

    def setUp(self):
        from solo_builder.api.middleware import ApiRateLimiter
        self.lim = ApiRateLimiter(read_limit=10, write_limit=5, window=60.0)

    def test_current_count_read_increments(self):
        self.lim.check("10.0.0.1", is_write=False)
        self.lim.check("10.0.0.1", is_write=False)
        self.assertEqual(self.lim.current_count("10.0.0.1", is_write=False), 2)

    def test_current_count_write_tracked_separately(self):
        self.lim.check("10.0.0.2", is_write=True)
        self.assertEqual(self.lim.current_count("10.0.0.2", is_write=True), 1)
        self.assertEqual(self.lim.current_count("10.0.0.2", is_write=False), 0)

    def test_current_count_unseen_ip_returns_zero(self):
        self.assertEqual(self.lim.current_count("99.99.99.99", is_write=False), 0)


class TestETagResponse(unittest.TestCase):
    """ETag caching — after_request handler in app.py (TASK-413)."""

    def setUp(self):
        import api.app as app_mod
        self.app = app_mod.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_get_200_has_etag_header(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ETag", resp.headers)
        self.assertTrue(resp.headers["ETag"].startswith('"'))
        self.assertTrue(resp.headers["ETag"].endswith('"'))

    def test_etag_is_md5_of_body(self):
        import hashlib
        resp = self.client.get("/health")
        body = resp.get_data()
        expected = '"' + hashlib.md5(body).hexdigest() + '"'
        self.assertEqual(resp.headers["ETag"], expected)

    def test_if_none_match_returns_304(self):
        resp1 = self.client.get("/health")
        etag = resp1.headers["ETag"]
        resp2 = self.client.get("/health", headers={"If-None-Match": etag})
        self.assertEqual(resp2.status_code, 304)
        self.assertEqual(resp2.get_data(), b"")

    def test_if_none_match_mismatch_returns_200(self):
        resp = self.client.get("/health", headers={"If-None-Match": '"bogus"'})
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.get_data()), 0)

    def test_post_request_no_etag(self):
        resp = self.client.post("/run", content_type="application/json")
        self.assertNotIn("ETag", resp.headers)

    def test_non_200_no_etag(self):
        resp = self.client.get("/nonexistent-path-xyz")
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("ETag", resp.headers)

    def test_same_content_produces_same_etag(self):
        r1 = self.client.get("/health")
        r2 = self.client.get("/health")
        self.assertEqual(r1.headers["ETag"], r2.headers["ETag"])


if __name__ == "__main__":
    unittest.main()
