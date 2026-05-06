"""HTTP request helpers and credential lookup."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


# Page size used internally when paging through results. The server caps a
# single response at 300 elements (see openapi.json: `max` default).
PAGE_SIZE = 300

# Pinned Teamscale API version. Used in the `/api/v{API_VERSION}/...` path of
# versioned endpoints. Bump when the plugin requires newer endpoint behavior.
API_VERSION = "2026.2"


def get_credentials() -> tuple[str, str]:
    user = os.environ.get("TEAMSCALE_DEV_USER")
    key = os.environ.get("TEAMSCALE_DEV_ACCESSKEY")
    if not user or not key:
        raise SystemExit(
            "error: environment variables TEAMSCALE_DEV_USER and "
            "TEAMSCALE_DEV_ACCESSKEY must both be set"
        )
    return user, key


def _send_request(
    server_url: str,
    api_path: str,
    user: str,
    key: str,
    method: str,
    params: Optional[dict[str, Any]],
    json_body: Any,
    accept: str,
) -> str:
    query_items: list[tuple[str, Any]] = [
        (k, v) for k, v in (params or {}).items() if v is not None and v != ""
    ]
    query = urllib.parse.urlencode(query_items, doseq=True)
    url = f"{server_url}{api_path}"
    if query:
        url += "?" + query

    body_bytes: Optional[bytes] = None
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")

    auth = base64.b64encode(f"{user}:{key}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(url, data=body_bytes, method=method)
    request.add_header("Authorization", f"Basic {auth}")
    request.add_header("Accept", accept)
    if body_bytes is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace").strip()
        message = f"HTTP {e.code} {e.reason} from {url}"
        if body:
            message += f"\n{body}"
        if e.code in (401, 403):
            message += (
                "\nCheck that TEAMSCALE_DEV_USER and TEAMSCALE_DEV_ACCESSKEY are valid."
            )
        raise SystemExit(message) from e
    except urllib.error.URLError as e:
        raise SystemExit(f"failed to reach {url}: {e.reason}") from e


def api_request(
    server_url: str,
    api_path: str,
    user: str,
    key: str,
    method: str = "GET",
    params: Optional[dict[str, Any]] = None,
    json_body: Any = None,
) -> Any:
    """Issue a JSON-accepting request and parse the response as JSON.

    Returns `None` for empty bodies (e.g. HTTP 204).
    """
    raw = _send_request(
        server_url, api_path, user, key, method, params, json_body,
        accept="application/json",
    )
    return json.loads(raw) if raw else None


def api_request_text(
    server_url: str,
    api_path: str,
    user: str,
    key: str,
    method: str = "GET",
    params: Optional[dict[str, Any]] = None,
    accept: str = "text/csv",
) -> str:
    """Issue a request and return the raw decoded response body as text."""
    return _send_request(
        server_url, api_path, user, key, method, params, json_body=None,
        accept=accept,
    )
