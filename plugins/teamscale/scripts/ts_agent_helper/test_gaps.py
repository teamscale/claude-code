"""Subcommands `ts-agent-helper test-gaps for-pr` and `... for-issue`.

Both call Teamscale's `/api/projects/{project}/test-gaps.csv` endpoint and
return the filtered CSV (alongside resolution metadata) so the skills can
pick out untested methods directly from method-level rows. They differ only
in how the scope is established: `for-pr` resolves the PR context of the
current Git branch and queries in merge-request mode, while `for-issue`
passes an issue ID and lets the server derive baseline and branch from the
commits linked to that issue.
"""

from __future__ import annotations

import argparse
import csv
import functools
import io
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable, NamedTuple, Optional

from .api import TeamscaleCredentials, api_request_text, get_credentials
from .config import ConfigError, TeamscaleConfig, read_config
from .pr_context import (
    print_resolution_banner,
    repo_root,
    resolve_pr_context,
)

CSV_DELIMITER = ";"
# Columns the server is required to provide. The header check is a
# subset check (see _filter_test_gap_csv): the server may add columns
# or reorder them, but we only forward the ones listed here in this
# fixed order. That keeps downstream consumers stable when the server
# evolves the schema.
REQUIRED_COLUMNS = [
    "Uniform Path",
    "Method Name",
    "Method Region Lines",
    "Test State",
]
TEST_STATE_COLUMN = "Test State"
TESTED_STATE = "Tested"

# By default the server also reports methods that did not change in the
# queried scope (test states "Unchanged" and "Not executed"). We ask it to
# leave those out for two reasons: they are not test gaps, and dropping them
# makes the number of returned rows exactly the number of methods the scope
# changed. That count is what tells a scope without any changes apart from a
# scope whose changes are fully tested.
EXCLUDE_UNCHANGED_METHODS_PARAMETER = "exclude-unchanged-methods"


class TestGapCsv(NamedTuple):
    """The forwarded CSV together with the counts it was derived from."""

    filtered_csv: str
    """CSV holding the required columns and the untested methods only."""

    changed_method_count: int
    """Methods the queried scope changed, tested and untested alike."""

    untested_method_count: int
    """Methods the queried scope changed that are not covered by a test."""


def _filter_test_gap_csv(csv_text: str) -> TestGapCsv:
    """Validate the header, project to required columns, and drop tested rows."""
    reader = csv.reader(io.StringIO(csv_text), delimiter=CSV_DELIMITER)
    try:
        header = next(reader)
    except StopIteration:
        raise SystemExit("error: test-gap CSV is empty (no header row)") from None

    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise SystemExit(
            "error: test-gap CSV is missing expected column(s): "
            f"{', '.join(missing)}\n"
            f"  got header: {CSV_DELIMITER.join(header)}"
        )

    keep_indices = [header.index(name) for name in REQUIRED_COLUMNS]
    test_state_index = header.index(TEST_STATE_COLUMN)

    changed_method_count = 0
    untested_method_count = 0
    output = io.StringIO()
    writer = csv.writer(output, delimiter=CSV_DELIMITER, lineterminator="\n")
    writer.writerow(REQUIRED_COLUMNS)
    for row in reader:
        # A blank line in the response is not a method and must not be
        # counted as one.
        if not row:
            continue
        changed_method_count += 1
        if len(row) > test_state_index and row[test_state_index] == TESTED_STATE:
            continue
        untested_method_count += 1
        # Rows can be shorter than the header when trailing fields are
        # empty (some CSV writers omit them). Pad missing trailing
        # cells with "" so the output always has one cell per
        # REQUIRED_COLUMNS entry.
        writer.writerow([row[i] if i < len(row) else "" for i in keep_indices])
    return TestGapCsv(
        filtered_csv=output.getvalue(),
        changed_method_count=changed_method_count,
        untested_method_count=untested_method_count,
    )


def _read_config_for_command(
    config_dir_argument: Optional[str],
) -> tuple[Path, TeamscaleConfig]:
    """Resolve the config directory and read the configuration found there."""
    config_dir = (
        Path(config_dir_argument).resolve(strict=False)
        if config_dir_argument
        else Path.cwd()
    )
    if not config_dir.is_dir():
        raise SystemExit(f"error: --config-dir is not a directory: {config_dir}")
    try:
        return config_dir, read_config(config_dir)
    except ConfigError as e:
        raise SystemExit(f"error: {e}") from e


# Printed instead of a header-only CSV. An empty result is a legitimate
# outcome and the consumer is an agent: a bare header row reads like missing
# data, while these messages state the outcome. `for-pr` reports every empty
# outcome with the single message below; `for-issue` tells the two apart via
# _describe_empty_issue_result, because a ticket whose scope holds no changed
# code at all usually points at a query the user can correct.
NO_TEST_GAPS_MESSAGE = "No test gaps in the queried scope.\n"

ISSUE_ALL_TESTED_TEMPLATE = (
    "No test gaps: all {methods} changed for this ticket are covered by tests.\n"
)

ISSUE_NO_CHANGED_CODE_MESSAGE = """No changed code found for this ticket.

Teamscale found no method that was added or modified in the commits it links
to this ticket, so there is nothing to assess. Likely causes:
  - the ticket's commits are not on the queried branch, for example after a
    force-push or a reset; pass the right branch with --branch
  - no commit message references the ticket, so Teamscale cannot attribute any
    change to it
  - the commits only touch files Teamscale does not analyze, such as
    documentation or configuration
"""

# Appended to the cause list only when the query excluded child issues, so
# that every cause the user reads applies to the query that actually ran.
ISSUE_NO_CHANGED_CODE_CHILD_ISSUE_CAUSE = (
    "  - the implementation work sits on this ticket's child issues, which\n"
    "    --exclude-child-issues left out of the query\n"
)


def _as_method_count(count: int) -> str:
    """Render a method count together with a grammatically matching noun."""
    if count == 1:
        return "1 method"
    return f"{count} methods"


def _describe_empty_issue_result(
    changed_method_count: int, include_child_issues: bool
) -> str:
    """Word an issue query that produced no test gaps.

    Separates the two ways that happens: the ticket changed methods and all of
    them are tested, or the ticket changed no method that Teamscale analyzes.
    Only the first is a clean result, so the second names the causes the user
    can act on.
    """
    if changed_method_count > 0:
        return ISSUE_ALL_TESTED_TEMPLATE.format(
            methods=_as_method_count(changed_method_count)
        )
    if include_child_issues:
        return ISSUE_NO_CHANGED_CODE_MESSAGE
    return ISSUE_NO_CHANGED_CODE_MESSAGE + ISSUE_NO_CHANGED_CODE_CHILD_ISSUE_CAUSE


def _fetch_and_print_test_gaps(
    config: TeamscaleConfig,
    credentials: TeamscaleCredentials,
    params: dict[str, Any],
    describe_empty_result: Optional[Callable[[int], str]] = None,
) -> None:
    """Fetch the test-gap CSV for `params` and report the result on stdout.

    `describe_empty_result` receives the number of changed methods and returns
    the message for a result without gaps. Callers that do not distinguish the
    empty outcomes omit it and get NO_TEST_GAPS_MESSAGE.
    """
    api_path = (
        f"/api/projects/"
        f"{urllib.parse.quote(config.project_id, safe='')}"
        f"/test-gaps.csv"
    )
    csv_text = api_request_text(
        config.server_url, api_path, credentials, params=params
    )

    result = _filter_test_gap_csv(csv_text)
    if result.untested_method_count == 0:
        if describe_empty_result is None:
            sys.stdout.write(NO_TEST_GAPS_MESSAGE)
        else:
            sys.stdout.write(describe_empty_result(result.changed_method_count))
        return
    sys.stdout.write(result.filtered_csv)


def cmd_test_gaps_for_pr(args: argparse.Namespace) -> int:
    """Resolve PR context and emit the test-gap CSV for changed code."""
    config_dir, config = _read_config_for_command(args.config_dir)

    credentials = get_credentials(config.server_url)
    git_root = repo_root(config_dir)
    ctx = resolve_pr_context(config, credentials, git_root)
    print_resolution_banner(ctx)

    # `merge-request-mode=true` puts the server into MR semantics:
    # `baseline` is treated as the prospective MR's source revision and
    # `end` as its target. This matches our `ctx.source` / `ctx.target`
    # whether they came from a real MR or from the branch-vs-base
    # fallback, so we get test gaps for the changes on the feature branch
    # in both cases.
    params: dict[str, Any] = {
        "baseline": ctx.source,
        "end": ctx.target,
        "merge-request-mode": "true",
        "all-partitions": "true",
        "auto-select-branch": "false",
        "include-child-issues": "false",
        EXCLUDE_UNCHANGED_METHODS_PARAMETER: "true",
    }

    if ctx.merge_request_id:
        params["merge-request-identifier"] = ctx.merge_request_id

    _fetch_and_print_test_gaps(config, credentials, params)
    return 0


def _as_query_flag(value: bool) -> str:
    """Render a boolean as the lowercase string the Teamscale API expects."""
    if value:
        return "true"
    return "false"


def _print_issue_resolution_banner(
    issue_id: str, include_child_issues: bool, branch: Optional[str]
) -> None:
    """Write a two-line resolution banner to stderr.

    The banner is informational only, so CSV output continues to go to
    stdout. The Claude Code skill relays it to the user so the queried
    scope is visible.
    """
    sys.stderr.write(f"ts-agent-helper: resolved as issue {issue_id}\n")
    branch_description = branch if branch else "auto-selected"
    sys.stderr.write(
        f"  include-child-issues={_as_query_flag(include_child_issues)}"
        f" branch={branch_description}\n"
    )
    sys.stderr.flush()


def cmd_test_gaps_for_issue(args: argparse.Namespace) -> int:
    """Emit the test-gap CSV for the code changed in the context of an issue."""
    issue_id = args.issue_id.strip()
    if not issue_id:
        raise SystemExit("error: ISSUE_ID must not be empty")

    _, config = _read_config_for_command(args.config_dir)
    credentials = get_credentials(config.server_url)

    include_child_issues = not args.exclude_child_issues
    branch = args.branch.strip() if args.branch else None
    if args.branch is not None and not branch:
        raise SystemExit("error: --branch must not be empty")
    _print_issue_resolution_banner(issue_id, include_child_issues, branch)

    # No time interval is sent: for an issue query the server derives both
    # ends from the commits linked to the issue.
    params: dict[str, Any] = {
        "issue-id": issue_id,
        "include-child-issues": _as_query_flag(include_child_issues),
        "all-partitions": "true",
        EXCLUDE_UNCHANGED_METHODS_PARAMETER: "true",
    }

    if branch:
        params["auto-select-branch"] = "false"
        params["branch-name"] = branch
    else:
        # The server picks the branch the issue lives on from the commits
        # linked to it. Thus, unlike in `for-pr`, we don't need any Git
        # lookups.
        params["auto-select-branch"] = "true"

    _fetch_and_print_test_gaps(
        config,
        credentials,
        params,
        describe_empty_result=functools.partial(
            _describe_empty_issue_result, include_child_issues=include_child_issues
        ),
    )
    return 0
