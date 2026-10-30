"""Implementation of `ts-agent-helper verify-config`.

Checks the `.teamscale.toml` against the Teamscale server: the server is
reachable and recent enough, the credentials work, and the project, branch
and path exist there.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from pathlib import Path
from typing import Optional

from .api import (
    API_VERSION,
    TeamscaleCredentials,
    TeamscaleHttpError,
    api_request,
    api_request_text,
    get_credentials,
    get_server_version,
)
from .config import read_config_or_exit, to_uniform_path
from .precommit import git_branch, git_toplevel

# Raising the minimum means updating the plugin README and check-setup skill.
MINIMUM_SERVER_VERSION = (2026, 2)


def cmd_verify_config(args: argparse.Namespace) -> int:
    directory = Path(args.config_dir or ".").resolve(strict=False)
    if not directory.is_dir():
        raise SystemExit(f"error: not a directory: {directory}")
    config = read_config_or_exit(directory)
    sys.stdout.write(
        f"configuration: project '{config.project_id}' on {config.server_url}\n"
    )
    credentials = get_credentials(config.server_url)

    server_version = get_server_version(config.server_url, credentials)
    sys.stdout.write("server version: %d.%d\n" % server_version)
    if server_version < MINIMUM_SERVER_VERSION:
        raise SystemExit(
            "error: the Teamscale plugin requires Teamscale %d.%d or newer"
            % MINIMUM_SERVER_VERSION
        )

    branch = config.project_branch
    if not branch:
        repo = git_toplevel(directory)
        branch = git_branch(repo) if repo is not None else None
    project = urllib.parse.quote(config.project_id, safe="")

    try:
        _verify_branch(config.server_url, project, credentials, branch)
        uniform_path = to_uniform_path(config, directory)
        if uniform_path:
            commit = "HEAD"
            if branch:
                commit = f"{branch}:HEAD"
            resource_type = api_request_text(
                config.server_url,
                f"/api/v{API_VERSION}/projects/{project}/resource-type",
                credentials,
                params={"t": commit, "uniform-path": uniform_path},
                accept="text/plain",
            ).strip().strip('"')
            if resource_type != "CONTAINER":
                raise SystemExit(
                    f"error: {directory} maps to '{uniform_path}' in project "
                    f"'{config.project_id}', which is not a directory on the "
                    f"Teamscale server. Check project.path in .teamscale.toml."
                )
    except TeamscaleHttpError as e:
        if e.status == 404:
            raise SystemExit(
                f"error: project '{config.project_id}' not found on the "
                f"Teamscale server <{config.server_url}>. Check project.id in "
                f".teamscale.toml."
            ) from e
        raise

    sys.stdout.write("Verification successful.\n")
    return 0


def _verify_branch(
    server_url: str,
    project: str,
    credentials: TeamscaleCredentials,
    branch: Optional[str],
) -> None:
    """Raise `SystemExit` unless the branch is live on the server."""
    if branch is None:
        sys.stdout.write("branch: none (detached HEAD); using the default branch\n")
        # Still checks credentials and project, as the branch lookup would.
        api_request(
            server_url,
            f"/api/v{API_VERSION}/projects/{project}/branches",
            credentials,
            params={"limit": 1},
        )
        return
    response = api_request(
        server_url,
        f"/api/v{API_VERSION}/projects/{project}/branches",
        credentials,
        params={"exact-filter": branch, "only-live-branches": "true"},
    )
    live_branches = response.get("liveBranches") if isinstance(response, dict) else None
    if branch not in (live_branches or []):
        raise SystemExit(
            f"error: branch '{branch}' is not known to the Teamscale server. "
            f"Push the branch and wait for Teamscale to analyze it, or set "
            f"project.branch in .teamscale.toml."
        )
    sys.stdout.write(f"branch: {branch}\n")
