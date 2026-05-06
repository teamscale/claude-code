"""Argument parsing and top-level command dispatch."""

from __future__ import annotations

import argparse
from typing import Optional

from .coverage import cmd_coverage_for_file
from .findings import (
    cmd_findings_flag,
    cmd_findings_for_pr,
    cmd_findings_list,
    cmd_findings_type_descriptors,
)
from .test_gaps import cmd_test_gaps_for_pr


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ts-agent-helper",
        description=(
            "Helper command for AI agents to interact with a Teamscale server "
            "configured via .teamscale.toml."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    findings = subparsers.add_parser("findings", help="findings-related commands")
    findings_subparsers = findings.add_subparsers(dest="subcommand", required=True)

    list_parser = findings_subparsers.add_parser(
        "list",
        help="list findings for a local file or directory",
        description=(
            "List Teamscale findings for the given local file or directory. "
            "The local path is mapped to a uniform path on the Teamscale server "
            "via the surrounding .teamscale.toml configuration. By default the "
            "config lookup starts at the directory of the given path; pass "
            "--config-dir to override. Results are paged internally and "
            "printed as a single JSON array on stdout. Output is capped at "
            "100 findings so the JSON stays digestible; use --start/--limit "
            "to page beyond that cap."
        ),
    )
    list_parser.add_argument("path", help="local file or directory to query")
    list_parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="0-based index of the first finding to fetch (default: 0)",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "maximum total findings to fetch across pages "
            "(default: 100, capped at 100 unless paging via --start)"
        ),
    )
    list_parser.add_argument(
        "--config-dir",
        default=None,
        help=(
            "directory from which to start the .teamscale.toml lookup "
            "(default: the directory of the given path)"
        ),
    )
    list_parser.set_defaults(func=cmd_findings_list)

    descriptors_parser = findings_subparsers.add_parser(
        "type-descriptors",
        help="get human-readable descriptions for finding type IDs",
        description=(
            "Fetch human-readable name and description for one or more finding "
            "type IDs, grouped by code scope. Either provide --scope together "
            "with one or more TYPE_ID arguments, or use --input to pass a full "
            "JSON request body of shape {\"<scope>\": [\"<typeId>\", ...]}. "
            "The server response is printed as JSON on stdout."
        ),
    )
    descriptors_parser.add_argument(
        "type_id",
        nargs="*",
        metavar="TYPE_ID",
        help="finding-type IDs to look up (used together with --scope)",
    )
    descriptors_parser.add_argument(
        "--scope",
        default=None,
        help="code-scope name to associate the given TYPE_IDs with",
    )
    descriptors_parser.add_argument(
        "--input",
        default=None,
        help=(
            "path to a JSON file containing the full request body, or '-' to "
            "read from stdin (mutually exclusive with --scope/TYPE_ID)"
        ),
    )
    descriptors_parser.add_argument(
        "--config-dir",
        default=None,
        help=(
            "directory from which to start the .teamscale.toml lookup "
            "(default: current working directory)"
        ),
    )
    descriptors_parser.set_defaults(func=cmd_findings_type_descriptors)

    for_pr_parser = findings_subparsers.add_parser(
        "for-pr",
        help="list newly added findings for the current branch's PR (or branch vs base)",
        description=(
            "Fetch the findings newly added on the current Git branch. If "
            "exactly one open merge request has the current branch as its "
            "source, the comparison is made against that MR's target "
            "branch. Otherwise the current branch is compared against the "
            "repository's default branch (origin/HEAD, falling back to "
            "local 'master' or 'main'). The resolved mode is printed as a "
            "banner on stderr; the JSON array of newly added findings is "
            "printed on stdout."
        ),
    )
    for_pr_parser.add_argument(
        "--config-dir",
        default=None,
        help=(
            "directory from which to start the .teamscale.toml lookup "
            "(default: current working directory)"
        ),
    )
    for_pr_parser.set_defaults(func=cmd_findings_for_pr)

    flag_parser = findings_subparsers.add_parser(
        "flag",
        help="flag findings as false-positive or tolerated",
        description=(
            "Flag the given findings on the Teamscale server as either a "
            "FALSE_POSITIVE or a TOLERATION. An optional --rationale is "
            "stored as the blacklist rationale. The branch used for the "
            "request is taken from project.branch in .teamscale.toml when "
            "set, otherwise from the current Git branch in --config-dir. "
            "The server returns no content on success."
        ),
    )
    flag_parser.add_argument(
        "finding_id",
        nargs="+",
        metavar="FINDING_ID",
        help="one or more finding IDs to flag",
    )
    flag_parser.add_argument(
        "--type",
        choices=["FALSE_POSITIVE", "TOLERATION"],
        required=True,
        help="type of flagging to apply",
    )
    flag_parser.add_argument(
        "--rationale",
        default=None,
        help="rationale to store with the flagging operation",
    )
    flag_parser.add_argument(
        "--config-dir",
        default=None,
        help=(
            "directory from which to start the .teamscale.toml lookup "
            "(default: current working directory)"
        ),
    )
    flag_parser.set_defaults(func=cmd_findings_flag)

    coverage = subparsers.add_parser(
        "coverage", help="coverage-related commands"
    )
    coverage_subparsers = coverage.add_subparsers(dest="subcommand", required=True)

    coverage_for_file = coverage_subparsers.add_parser(
        "for-file",
        help="fetch line-coverage data for a single local file or directory",
        description=(
            "Fetch line-coverage data for a local file or directory. The local "
            "path is mapped to a uniform path via the surrounding "
            ".teamscale.toml; by default the config lookup starts at the "
            "directory of the given path. The server response is summarised "
            "as a coverage percentage on stdout."
        ),
    )
    coverage_for_file.add_argument("path", help="local file or directory to query")
    coverage_for_file.add_argument(
        "--config-dir",
        default=None,
        help=(
            "directory from which to start the .teamscale.toml lookup "
            "(default: the directory of the given path)"
        ),
    )
    coverage_for_file.set_defaults(func=cmd_coverage_for_file)

    test_gaps = subparsers.add_parser(
        "test-gaps", help="test-gap related commands"
    )
    test_gaps_subparsers = test_gaps.add_subparsers(dest="subcommand", required=True)

    test_gaps_for_pr = test_gaps_subparsers.add_parser(
        "for-pr",
        help="fetch the test-gap CSV for the current branch's PR (or branch vs base)",
        description=(
            "Resolve the PR context for the current Git branch (open merge "
            "request if one exists, otherwise comparison against the "
            "repository's default branch) and fetch the test-gap CSV from "
            "the Teamscale '/test-gaps.csv' endpoint in merge-request mode "
            "scoped to that context. The resolved mode is printed as a "
            "banner on stderr; the filtered CSV (already-tested rows and "
            "internal columns dropped) is printed on stdout."
        ),
    )
    test_gaps_for_pr.add_argument(
        "--config-dir",
        default=None,
        help=(
            "directory from which to start the .teamscale.toml lookup "
            "(default: current working directory)"
        ),
    )
    test_gaps_for_pr.set_defaults(func=cmd_test_gaps_for_pr)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
