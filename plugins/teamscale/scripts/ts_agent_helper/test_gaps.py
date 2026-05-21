"""Subcommand `ts-agent-helper test-gaps for-pr`.

Calls Teamscale's `/api/projects/{project}/test-gaps.csv` endpoint in
merge-request mode, scoped to the resolved PR context for the current
branch. Returns the raw CSV (alongside resolution metadata) so the skill
can pick out untested methods directly from method-level rows.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from .api import api_request_text, get_credentials
from .config import ConfigError, read_config
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


def _filter_test_gap_csv(csv_text: str) -> str:
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

    output = io.StringIO()
    writer = csv.writer(output, delimiter=CSV_DELIMITER, lineterminator="\n")
    writer.writerow(REQUIRED_COLUMNS)
    for row in reader:
        if len(row) > test_state_index and row[test_state_index] == TESTED_STATE:
            continue
        # Rows can be shorter than the header when trailing fields are
        # empty (some CSV writers omit them). Pad missing trailing
        # cells with "" so the output always has one cell per
        # REQUIRED_COLUMNS entry.
        writer.writerow([row[i] if i < len(row) else "" for i in keep_indices])
    return output.getvalue()


def cmd_test_gaps_for_pr(args: argparse.Namespace) -> int:
    """Resolve PR context and emit the test-gap CSV for changed code."""
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
        f"/test-gaps.csv"
    )
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
        "include-child-issues": "false"
    }

    if ctx.merge_request_id:
        params["merge-request-identifier"] = ctx.merge_request_id

    csv_text = api_request_text(
        config.server_url, api_path, credentials, params=params
    )

    sys.stdout.write(_filter_test_gap_csv(csv_text))
    return 0
