"""Merge-request lookup helpers.

Pure functions; no CLI subcommand is exposed. Callers are
`ts_agent_helper.pr_context` (resolves the unique open MR for a branch
during PR-context detection).
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional

from .api import PAGE_SIZE, api_request
from .config import TeamscaleConfig


def _regex_escape_for_java(value: str) -> str:
    """Escape `value` for use as a literal in a Java regex pattern.

    Python's `re.escape` over-escapes compared to Java but is never wrong: any
    character that matters in Java regex is also escaped here, and the extra
    backslashes are tolerated by Java's regex engine.
    """
    return re.escape(value)


def find_merge_requests_for_branch(
    config: TeamscaleConfig, user: str, key: str, branch: str
) -> list[dict[str, Any]]:
    """Return the list of open merge requests whose `sourceBranch == branch`.

    The server-side `filter` is a fuzzy regex match across several fields, so
    a server hit does not guarantee that `branch` is the merge request's
    source. We post-filter locally for an exact match.
    """
    api_path = (
        f"/api/projects/"
        f"{urllib.parse.quote(config.project_id, safe='')}"
        f"/merge-requests"
    )
    server_filter = _regex_escape_for_java(branch)

    start = 0
    matches: list[dict[str, Any]] = []
    while True:
        response = api_request(
            config.server_url,
            api_path,
            user,
            key,
            params={
                "filter": server_filter,
                "status": "OPEN",
                "start": start,
                "max": PAGE_SIZE,
            },
        )
        if not isinstance(response, dict) or "mergeRequests" not in response:
            raise SystemExit(
                f"unexpected response shape (missing 'mergeRequests'): {response!r}"
            )
        page = response.get("mergeRequests") or []
        if not isinstance(page, list):
            raise SystemExit(
                f"unexpected response shape ('mergeRequests' is not a list): "
                f"{page!r}"
            )

        for entry in page:
            mr = (entry or {}).get("mergeRequest") or {}
            if mr.get("sourceBranch") == branch:
                matches.append(mr)

        if len(page) < PAGE_SIZE:
            break
        start += len(page)

    return matches


def resolve_unique_merge_request(
    config: TeamscaleConfig, user: str, key: str, branch: str
) -> Optional[dict[str, Any]]:
    """Return the single open MR for `branch`, or `None` if none exists.

    Raises SystemExit on the ambiguous case (multiple MRs match) — callers
    cannot proceed without disambiguation, and silently picking one would
    hide the problem.
    """
    matches = find_merge_requests_for_branch(config, user, key, branch)
    if not matches:
        return None
    if len(matches) > 1:
        raise SystemExit(
            f"error: multiple open merge requests found for source branch "
            f"'{branch}' ({len(matches)}); cannot disambiguate automatically"
        )
    return matches[0]
