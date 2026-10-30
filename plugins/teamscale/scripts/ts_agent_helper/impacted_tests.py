"""Implementation of `ts-agent-helper impacted-tests`.

Prints the tests impacted by the latest commit on a branch, one uniform path
per line, ordered by the server's ranking.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from .api import API_VERSION, api_request, get_credentials, get_server_version
from .config import read_config_or_exit
from .pr_context import current_git_branch
from .precommit import git_toplevel, pre_commit_base_branch, pre_commit_branch_name

STRATEGY_AUTO = "AUTO"
STRATEGY_COVERAGE = "COVERAGE"
STRATEGY_SIMILARITY = "SIMILARITY"

# Oldest server that offers the `tests/related-to` service.
SIMILARITY_MINIMUM_SERVER_VERSION = (2026, 5)


def cmd_impacted_tests(args: argparse.Namespace) -> int:
    target = Path(args.path or ".").resolve(strict=False)
    if not target.exists():
        raise SystemExit(f"error: path does not exist: {target}")
    search_dir = target if target.is_dir() else target.parent
    config = read_config_or_exit(search_dir)
    credentials = get_credentials(config.server_url)

    if args.on_pre_commit_branch:
        base_branch = pre_commit_base_branch(config, git_toplevel(search_dir))
        branch = pre_commit_branch_name(credentials.username, base_branch)
    elif config.project_branch:
        branch = config.project_branch
    else:
        branch = current_git_branch(search_dir)
    end = f"{branch}:HEAD"
    baseline = f"{branch}:HEADp1"
    project = urllib.parse.quote(config.project_id, safe="")

    strategy = args.strategy
    if strategy in (STRATEGY_AUTO, STRATEGY_COVERAGE):
        partitions = api_request(
            config.server_url,
            f"/api/projects/{project}/test-coverage/testwise/partitions",
            credentials,
            params={"t": end},
        )
        if partitions:
            strategy = STRATEGY_COVERAGE
        elif strategy == STRATEGY_COVERAGE:
            raise SystemExit(
                "error: the Teamscale server has no test-wise coverage. "
                "Use '--strategy SIMILARITY' instead."
            )
        else:
            sys.stderr.write(
                "note: the Teamscale server has no test-wise coverage; "
                "selecting tests by source-code similarity\n"
            )
            strategy = STRATEGY_SIMILARITY

    if strategy == STRATEGY_COVERAGE:
        tests = api_request(
            config.server_url,
            f"/api/v{API_VERSION}/projects/{project}/impacted-tests",
            credentials,
            params={"baseline": baseline, "end": end, "partitions": partitions},
        )
        test_paths = [test.get("uniformPath") for test in _as_list(tests)]
        if args.max_count is not None:
            test_paths = test_paths[: args.max_count]
    else:
        server_version = get_server_version(config.server_url, credentials)
        if server_version < SIMILARITY_MINIMUM_SERVER_VERSION:
            raise SystemExit(
                "error: selecting tests by similarity requires Teamscale "
                "%d.%d or newer; the server runs %d.%d"
                % (SIMILARITY_MINIMUM_SERVER_VERSION + server_version)
            )
        response = api_request(
            config.server_url,
            f"/api/v2026.5/projects/{project}/tests/related-to",
            credentials,
            params={
                "baseline": baseline,
                "end": end,
                "provide-top-contributing-terms": 0,
                "limit": args.max_count,
            },
        )
        if not isinstance(response, dict):
            raise SystemExit(f"unexpected response (not an object): {response!r}")
        test_paths = [
            test.get("testImplementation")
            for test in _as_list(response.get("matchingTestImplementations"))
        ]

    sys.stderr.write(f"note: selected by {strategy.lower()} on branch {branch}\n")
    for test_path in test_paths:
        if test_path:
            sys.stdout.write(test_path + "\n")
    return 0


def _as_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SystemExit(f"unexpected response (not a list): {value!r}")
    return [item for item in value if isinstance(item, dict)]
