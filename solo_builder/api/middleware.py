"""API middleware — security headers and rate limiting (TASK-322).

Provides two reusable classes:

  SecurityHeadersMiddleware  — apply security response headers to every response
  ApiRateLimiter             — sliding-window in-memory per-IP rate limiter
"""
import collections
import time
import uuid

try:
    from flask import request as _flask_request
except ImportError:  # pragma: no cover — only absent in pure-unit tests
    _flask_request = None  # type: ignore[assignment]

API_VERSION = "1"


class SecurityHeadersMiddleware:
    """Apply security response headers to every Flask response.

    Headers set:
      X-Frame-Options          DENY
      X-Content-Type-Options   nosniff
      Referrer-Policy          strict-origin-when-cross-origin
      Content-Security-Policy  (see CSP constant)
      Strict-Transport-Security  max-age=31536000; includeSubDomains  (HSTS)
      Access-Control-Allow-Origin  *
      Access-Control-Allow-Headers  Content-Type
      X-Request-ID             UUID per request (echoed from incoming header if present)
      X-API-Version            API version string (currently "1")
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    HSTS = "max-age=31536000; includeSubDomains"

    def apply(self, response):
        """Attach headers to a Flask response object and return it."""
        h = response.headers
        h["Access-Control-Allow-Origin"]  = "*"
        h["Access-Control-Allow-Headers"] = "Content-Type"
        h["X-Frame-Options"]              = "DENY"
        h["X-Content-Type-Options"]       = "nosniff"
        h["Referrer-Policy"]              = "strict-origin-when-cross-origin"
        h["Content-Security-Policy"]      = self.CSP
        h["Strict-Transport-Security"]    = self.HSTS
        h["X-API-Version"]                = API_VERSION
        # Echo incoming X-Request-ID if present; otherwise generate a new UUID4.
        req_id = None
        if _flask_request is not None:
            try:
                req_id = _flask_request.headers.get("X-Request-ID")
            except RuntimeError:
                pass  # outside request context (e.g. direct unit-test calls)
        if not req_id:
            req_id = str(uuid.uuid4())
        h["X-Request-ID"] = req_id
        return response


class ApiRateLimiter:
    """Sliding-window in-memory per-IP rate limiter.

    Maintains two counters per IP address:
      - read  counter (GET/HEAD/OPTIONS): default 120 requests per 60 seconds
      - write counter (POST/DELETE/PUT/PATCH): default 30 requests per 60 seconds

    Usage:
        limiter = ApiRateLimiter()
        allowed = limiter.check(ip="127.0.0.1", is_write=False)
    """

    READ_METHODS  = frozenset(("GET", "HEAD", "OPTIONS"))
    WRITE_METHODS = frozenset(("POST", "DELETE", "PUT", "PATCH"))

    def __init__(self, read_limit: int = 120, write_limit: int = 30,
                 window: float = 60.0) -> None:
        self.read_limit  = read_limit
        self.write_limit = write_limit
        self.window      = window
        self._read:  collections.defaultdict = collections.defaultdict(collections.deque)
        self._write: collections.defaultdict = collections.defaultdict(collections.deque)

    def check(self, ip: str, is_write: bool) -> bool:
        """Return True if the request is within limit; record it as a side-effect.

        Prunes expired timestamps from the deque on each call.
        """
        store = self._write if is_write else self._read
        limit = self.write_limit if is_write else self.read_limit
        now   = time.time()
        dq    = store[ip]
        while dq and dq[0] < now - self.window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

    def current_count(self, ip: str, is_write: bool) -> int:
        """Return current request count in the window for an IP (for testing/monitoring)."""
        store = self._write if is_write else self._read
        now   = time.time()
        dq    = store[ip]
        while dq and dq[0] < now - self.window:
            dq.popleft()
        return len(dq)
