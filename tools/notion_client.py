"""
notion_client.py — thin Notion REST API client with retry/backoff.

Retry policy
------------
Retryable status codes : 408, 409, 429, 500, 502, 503, 504
Max retries            : 3  (4 total attempts)
Backoff                : exponential — 1 s, 2 s, 4 s
Retry-After header     : respected when present (overrides backoff)
Default timeout        : 30 s per request
Non-retryable errors   : 400, 401, 403, 404 — raised immediately as RuntimeError

All public methods raise RuntimeError on permanent failure with:
    "<METHOD> <path> → HTTP <status>  <truncated body>"
"""
import sys
import time
import requests
from notion_config import NOTION_TOKEN, NOTION_VERSION

BASE = "https://api.notion.com/v1"

_TIMEOUT     = 30          # seconds per request
_MAX_RETRIES = 3           # attempts beyond the first
_BACKOFF     = (1.0, 2.0, 4.0)   # wait seconds before attempt 2, 3, 4
_RETRYABLE   = {408, 409, 429, 500, 502, 503, 504}


class NotionClient:
    def __init__(self, token: str = NOTION_TOKEN):
        if not token:
            print(
                "ERROR: NOTION_INTEGRATION_TOKEN is not set.\n"
                "Export it before running:\n"
                "  PowerShell: $env:NOTION_INTEGRATION_TOKEN = '<your-token>'\n"
                "  Bash:       export NOTION_INTEGRATION_TOKEN='<your-token>'",
                file=sys.stderr,
            )
            sys.exit(1)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Central request helper
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Execute one HTTP request against the Notion API.

        Retries on transient failures up to _MAX_RETRIES times.
        Raises RuntimeError (never requests.HTTPError) on permanent failure.
        """
        url = f"{BASE}{path}"
        kwargs.setdefault("timeout", _TIMEOUT)

        for attempt in range(_MAX_RETRIES + 1):
            try:
                r = requests.request(method, url, headers=self._headers, **kwargs)
            except requests.exceptions.Timeout:
                if attempt < _MAX_RETRIES:
                    time.sleep(_BACKOFF[attempt])
                    continue
                raise RuntimeError(
                    f"Notion API timeout after {_MAX_RETRIES + 1} attempts: "
                    f"{method} {path}"
                )
            except requests.exceptions.ConnectionError as exc:
                if attempt < _MAX_RETRIES:
                    time.sleep(_BACKOFF[attempt])
                    continue
                raise RuntimeError(
                    f"Notion API connection error: {method} {path} — {exc}"
                ) from exc

            if r.status_code in _RETRYABLE and attempt < _MAX_RETRIES:
                # Respect Retry-After when the server sends it (e.g. 429)
                wait = _BACKOFF[attempt]
                raw_ra = r.headers.get("Retry-After", "")
                if raw_ra.isdigit():
                    wait = min(float(raw_ra), 60.0)
                time.sleep(wait)
                continue

            if not r.ok:
                body = r.text[:300].replace("\n", " ")
                raise RuntimeError(
                    f"Notion API error: {method} {path} "
                    f"-> HTTP {r.status_code}  {body}"
                )

            return r

        # Exhausted all retries with a retryable status
        raise RuntimeError(
            f"Notion API: {method} {path} failed after "
            f"{_MAX_RETRIES + 1} attempts (last status in retryable set)"
        )

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def get_page(self, page_id: str) -> dict:
        return self._request("GET", f"/pages/{page_id}").json()

    def patch_page_properties(self, page_id: str, properties: dict) -> dict:
        return self._request(
            "PATCH", f"/pages/{page_id}", json={"properties": properties}
        ).json()

    def create_page(self, parent: dict, properties: dict, children: list = None) -> dict:
        body: dict = {"parent": parent, "properties": properties}
        if children:
            body["children"] = children
        return self._request("POST", "/pages", json=body).json()

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    def get_block_children(self, block_id: str, page_size: int = 100) -> list:
        params: dict = {"page_size": page_size}
        results = []
        while True:
            data = self._request(
                "GET", f"/blocks/{block_id}/children", params=params
            ).json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            params["start_cursor"] = data["next_cursor"]
        return results

    def patch_block(self, block_id: str, payload: dict) -> dict:
        return self._request("PATCH", f"/blocks/{block_id}", json=payload).json()

    # ------------------------------------------------------------------
    # Databases
    # ------------------------------------------------------------------

    def query_database(self, db_id: str, filter_body: dict = None, sorts: list = None) -> list:
        body: dict = {}
        if filter_body:
            body["filter"] = filter_body
        if sorts:
            body["sorts"] = sorts
        results = []
        while True:
            data = self._request(
                "POST", f"/databases/{db_id}/query", json=body
            ).json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            body["start_cursor"] = data["next_cursor"]
        return results

    def create_database(self, parent: dict, title: str, properties: dict) -> dict:
        body = {
            "parent": parent,
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        return self._request("POST", "/databases", json=body).json()

    def search(self, query: str, filter_type: str = None) -> list:
        """Search the workspace. filter_type: 'page' | 'database' | None (both)."""
        body: dict = {"query": query}
        if filter_type:
            body["filter"] = {"value": filter_type, "property": "object"}
        return self._request("POST", "/search", json=body).json().get("results", [])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def plain_text(rich_text: list) -> str:
        """Collapse a rich_text array to a plain string."""
        return "".join(rt.get("plain_text", "") for rt in rich_text)

    @staticmethod
    def rich_text(content: str, bold: bool = False, italic: bool = False) -> list:
        """Minimal rich_text array with one text segment."""
        return [
            {
                "type": "text",
                "text": {"content": content},
                "annotations": {
                    "bold": bold,
                    "italic": italic,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default",
                },
            }
        ]
