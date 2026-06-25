"""Subcommands under `ts-agent-helper findings`."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from .api import API_VERSION, PAGE_SIZE, api_request, get_credentials
from .config import ConfigError, TeamscaleConfig, read_config
from .pr_context import (
    current_git_branch,
    print_resolution_banner,
    repo_root,
    resolve_pr_context,
)


def _escape_path_segment(segment: str) -> str:
    """Backslash-escape forward slashes in a uniform-path segment."""
    return segment.replace("/", "\\/")


# Top-level finding fields that carry no information useful to an agent fixing
# the finding. Dropped to keep the JSON small enough for the consumer to
# process: 'birth' (when/where the finding first appeared), 'codeScopeName',
# 'analysisTimestamp' and 'tasksByStatus' are all server bookkeeping.
_DROPPED_FINDING_KEYS = frozenset(
    {
        "birth",
        "codeScopeName",
        "analysisTimestamp",
        "tasksByStatus",
    }
)

# Cap on the number of sibling locations retained per finding. A finding can
# carry many siblings (e.g. all clones of a code-duplication finding); a few
# examples are enough for an agent to act on without bloating the JSON.
_MAX_SIBLING_LOCATIONS = 3


def _simplify_location(location: Any) -> Any:
    """Collapse a finding location to a path plus start/end line.

    Drops the exact character offsets and the location type, which the
    consumer does not need. If the location carries none of the recognized
    fields (e.g. a non-text location), the original object is returned
    unchanged so positioning information is never silently lost.
    """
    if not isinstance(location, dict):
        return location
    compact: dict[str, Any] = {}
    path = location.get("uniformPath") or location.get("location")
    if path is not None:
        compact["path"] = path
    start_line = location.get("rawStartLine")
    end_line = location.get("rawEndLine")
    if start_line is not None:
        compact["startLine"] = start_line
    # Only emit endLine when it adds information beyond startLine.
    if end_line is not None and end_line != start_line:
        compact["endLine"] = end_line
    return compact or location


def _simplify_finding(finding: Any) -> Any:
    """Strip a finding down to the fields an agent needs to act on it."""
    if not isinstance(finding, dict):
        return finding
    simplified = {
        key: value
        for key, value in finding.items()
        if key not in _DROPPED_FINDING_KEYS
    }
    if "location" in simplified:
        simplified["location"] = _simplify_location(simplified["location"])
    sibling_locations = simplified.get("siblingLocations")
    if isinstance(sibling_locations, list):
        # Truncate long sibling lists; the consumer only needs a few examples.
        simplified["siblingLocations"] = [
            _simplify_location(location)
            for location in sibling_locations[:_MAX_SIBLING_LOCATIONS]
        ]
    # An empty properties map carries no information.
    if simplified.get("properties") == {}:
        simplified.pop("properties", None)
    return simplified


def _emit_findings(findings: list[Any]) -> None:
    """Write findings to stdout as a simplified JSON array."""
    json.dump([_simplify_finding(finding) for finding in findings], sys.stdout, indent=2)
    sys.stdout.write("\n")


def _build_uniform_path(config: TeamscaleConfig, target: Path) -> str:
    try:
        relative = target.relative_to(config.local_base_path)
    except ValueError as e:
        raise SystemExit(
            f"error: '{target}' is not below the configured local base path "
            f"'{config.local_base_path}'"
        ) from e
    relative_parts = [p for p in relative.parts if p not in ("", ".")]
    segments = config.project_path_segments + relative_parts
    return "/".join(_escape_path_segment(s) for s in segments)


def cmd_findings_list(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve(strict=False)
    if not target.exists():
        raise SystemExit(f"error: path does not exist: {target}")

    if args.config_dir:
        config_search_dir = Path(args.config_dir).resolve(strict=False)
        if not config_search_dir.is_dir():
            raise SystemExit(
                f"error: --config-dir is not a directory: {config_search_dir}"
            )
    else:
        config_search_dir = target if target.is_dir() else target.parent
    try:
        config = read_config(config_search_dir)
    except ConfigError as e:
        raise SystemExit(f"error: {e}") from e

    credentials = get_credentials(config.server_url)
    uniform_path = _build_uniform_path(config, target)
    api_path = (
        f"/api/v{API_VERSION}/projects/"
        f"{urllib.parse.quote(config.project_id, safe='')}"
        f"/findings/list"
    )

    branch: str | None
    if config.project_branch:
        branch = config.project_branch
    else:
        try:
            branch = current_git_branch(config_search_dir)
        except SystemExit:
            # Detached HEAD (or other failure): fall back to the project's
            # default branch on the server. Tell the user, otherwise the
            # response can silently mismatch what is on disk.
            sys.stderr.write(
                "warning: detached HEAD; querying project default branch on server\n"
            )
            sys.stderr.flush()
            branch = None

    # Hard cap to keep the JSON blob below something a model can actually
    # consume. Use --start/--limit to page beyond it.
    HARD_CAP = 100
    effective_limit = (
        HARD_CAP if args.limit is None else min(args.limit, HARD_CAP)
    )

    start = max(0, args.start)
    fetched = 0
    findings: list[Any] = []
    truncated = False

    while True:
        remaining = effective_limit - fetched
        if remaining <= 0:
            truncated = args.limit is None or args.limit > HARD_CAP
            break
        page_max = min(PAGE_SIZE, remaining)

        params: dict[str, Any] = {
            "uniform-path": uniform_path,
            "start": start,
            "max": page_max,
        }
        if branch:
            params["t"] = f"{branch}:HEAD"

        page = api_request(
            config.server_url, api_path, credentials, params=params
        )
        if not isinstance(page, list):
            raise SystemExit(f"unexpected response (not a list): {page!r}")

        findings.extend(page)
        fetched += len(page)

        # Server returned fewer items than requested -> no more pages.
        if len(page) < page_max:
            break
        start += len(page)

    if truncated:
        sys.stderr.write(
            f"warning: truncated to first {HARD_CAP} findings; "
            f"rerun with --start/--limit to page beyond it\n"
        )
        sys.stderr.flush()

    _emit_findings(findings)
    return 0


def _read_type_descriptors_body(args: argparse.Namespace) -> dict[str, list[str]]:
    if args.input is not None:
        if args.scope is not None or args.type_id:
            raise SystemExit(
                "error: --input cannot be combined with --scope or TYPE_ID arguments"
            )
        if args.input == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.input).read_text(encoding="utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SystemExit(f"error: --input does not contain valid JSON: {e}") from e
        if not isinstance(body, dict) or not all(
            isinstance(v, list) and all(isinstance(t, str) for t in v)
            for v in body.values()
        ):
            raise SystemExit(
                "error: --input must be a JSON object mapping scope names to "
                "arrays of finding-type IDs"
            )
        return body

    if args.scope is None:
        raise SystemExit("error: --scope is required when --input is not used")
    if not args.type_id:
        raise SystemExit(
            "error: at least one TYPE_ID is required when --input is not used"
        )
    # Preserve input order while removing duplicates.
    seen: set[str] = set()
    unique_ids: list[str] = []
    for type_id in args.type_id:
        if type_id not in seen:
            seen.add(type_id)
            unique_ids.append(type_id)
    return {args.scope: unique_ids}


def cmd_findings_for_pr(args: argparse.Namespace) -> int:
    """Fetch findings newly added on the current branch.

    Auto-detects whether an open merge request exists for the current Git
    branch. With an MR, queries the finding churn between the MR's source
    and target branches. Without an MR, falls back to comparing the current
    branch against the repository's default branch. Only the newly added
    findings are written to stdout, unless
    --include-findings-in-changed-code is given, in which case findings in
    changed code are merged in as well (deduplicated by finding ID).
    """
    config_dir = (
        Path(args.config_dir).resolve(strict=False) if args.config_dir else Path.cwd()
    )
    if not config_dir.is_dir():
        raise SystemExit(f"error: --config-dir is not a directory: {config_dir}")
    try:
        config = read_config(config_dir)
    except ConfigError as e:
        raise SystemExit(f"error: {e}") from e

    credentials = get_credentials(config.server_url)
    git_root = repo_root(config_dir)
    ctx = resolve_pr_context(config, credentials, git_root)
    print_resolution_banner(ctx)

    api_path = (
        f"/api/projects/"
        f"{urllib.parse.quote(config.project_id, safe='')}"
        f"/merge-requests/finding-churn"
    )
    response = api_request(
        config.server_url,
        api_path,
        credentials,
        params={"source": ctx.source, "target": ctx.target},
    )

    if not isinstance(response, dict):
        raise SystemExit(f"unexpected response (not an object): {response!r}")

    keys = ["addedFindings"]
    if args.include_findings_in_changed_code:
        keys.append("findingsInChangedCode")

    findings: list[Any] = []
    seen_ids: set[str] = set()
    for key in keys:
        group = response.get(key) or {}
        if not isinstance(group, dict):
            continue
        for finding in group.get("findings", []):
            finding_id = (
                finding.get("id") if isinstance(finding, dict) else None
            )
            if finding_id is not None:
                if finding_id in seen_ids:
                    continue
                seen_ids.add(finding_id)
            findings.append(finding)

    _emit_findings(findings)
    return 0


def cmd_findings_flag(args: argparse.Namespace) -> int:
    """Flag findings as FALSE_POSITIVE or TOLERATION."""
    config_dir = (
        Path(args.config_dir).resolve(strict=False) if args.config_dir else Path.cwd()
    )
    if not config_dir.is_dir():
        raise SystemExit(f"error: --config-dir is not a directory: {config_dir}")
    try:
        config = read_config(config_dir)
    except ConfigError as e:
        raise SystemExit(f"error: {e}") from e

    credentials = get_credentials(config.server_url)
    branch = config.project_branch
    if not branch:
        try:
            branch = current_git_branch(config_dir)
        except SystemExit as e:
            raise SystemExit(
                f"error: no current Git branch in {config_dir} (detached HEAD?); "
                f"set project.branch in .teamscale.toml"
            ) from e

    # Preserve input order while removing duplicates.
    seen: set[str] = set()
    unique_ids: list[str] = []
    for finding_id in args.finding_id:
        if finding_id not in seen:
            seen.add(finding_id)
            unique_ids.append(finding_id)

    body: dict[str, Any] = {"findingIds": unique_ids}
    if args.rationale is not None:
        body["blacklistInfo"] = {"rationale": args.rationale}

    params: dict[str, Any] = {
        "operation": "ADD",
        "type": args.type,
        "t": f"{branch}:HEAD",
    }

    api_path = (
        f"/api/v{API_VERSION}/projects/"
        f"{urllib.parse.quote(config.project_id, safe='')}"
        f"/findings/flagged"
    )
    response = api_request(
        config.server_url,
        api_path,
        credentials,
        method="PUT",
        params=params,
        json_body=body,
    )
    if response is not None:
        json.dump(response, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


def cmd_findings_type_descriptors(args: argparse.Namespace) -> int:
    config_dir = (
        Path(args.config_dir).resolve(strict=False) if args.config_dir else Path.cwd()
    )
    if not config_dir.is_dir():
        raise SystemExit(f"error: --config-dir is not a directory: {config_dir}")

    try:
        config = read_config(config_dir)
    except ConfigError as e:
        raise SystemExit(f"error: {e}") from e

    credentials = get_credentials(config.server_url)
    body = _read_type_descriptors_body(args)

    api_path = (
        f"/api/v{API_VERSION}/projects/"
        f"{urllib.parse.quote(config.project_id, safe='')}"
        f"/finding-type-descriptors"
    )
    response = api_request(
        config.server_url,
        api_path,
        credentials,
        method="POST",
        json_body=body,
    )

    json.dump(response, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0
