"""Subcommands under `ts-agent-helper coverage`."""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from .api import api_request, get_credentials
from .config import ConfigError, TeamscaleConfig, read_config
from .pr_context import current_git_branch


def _escape_path_segment(segment: str) -> str:
    """Backslash-escape forward slashes in a uniform-path segment."""
    return segment.replace("/", "\\/")


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


def cmd_coverage_for_file(args: argparse.Namespace) -> int:
    """Fetch line-coverage data for a single local file or directory."""
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
        f"/api/projects/"
        f"{urllib.parse.quote(config.project_id, safe='')}"
        f"/test-coverage/"
        f"{urllib.parse.quote(uniform_path, safe='')}"
    )
    params: dict[str, Any] = {"all-partitions": "true"}
    branch: str | None
    if config.project_branch:
        branch = config.project_branch
    else:
        try:
            branch = current_git_branch(config_search_dir)
        except SystemExit:
            branch = None
    if branch:
        params["t"] = f"{branch}:HEAD"

    response = api_request(config.server_url, api_path, credentials, params=params)
    if response is None:
        sys.stdout.write("N/A\n")
        return 0
    fully_covered = len(response.get("fullyCoveredLines", []))
    partially_covered = len(response.get("partiallyCoveredLines", []))
    uncovered = len(response.get("uncoveredLines", []))
    total = fully_covered + partially_covered + uncovered
    if total == 0:
        sys.stdout.write("N/A\n")
        return 0
    percentage = (fully_covered + partially_covered) / total * 100
    sys.stdout.write(f"{percentage:.1f}%\n")
    return 0
