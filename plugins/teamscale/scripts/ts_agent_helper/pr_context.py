"""Resolve PR context for the current Git branch.

Encapsulates the branch lookup, merge-request lookup, and base-branch
fallback shared by `findings for-pr` and `test-gaps for-pr`.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .config import TeamscaleConfig
from .merge_requests import resolve_unique_merge_request


@dataclass(frozen=True)
class PrContext:
    """Resolved PR context.

    `mode` is either `"merge-request"` (an open MR matched the current
    branch) or `"branch"` (no MR matched, comparison is against the
    repository's default branch).
    """

    mode: str
    branch: str
    source: str
    target: str
    merge_request_id: Optional[str]
    merge_request: Optional[dict[str, Any]]


def current_git_branch(repo_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise SystemExit("error: 'git' is not available on PATH") from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        raise SystemExit(
            f"error: failed to determine current Git branch in {repo_dir}: {stderr}"
        ) from e
    branch = result.stdout.strip()
    if not branch:
        raise SystemExit(
            f"error: no current Git branch in {repo_dir} (detached HEAD?)"
        )
    # Branches go into '{branch}:HEAD' query strings; a colon in the
    # branch would yield 'foo:bar:HEAD', which the server parses as a
    # different revision (or rejects). Git's own ref-format rules
    # forbid ':' in branch names, but be defensive against worktrees or
    # exotic configurations that smuggle one in.
    if ":" in branch:
        raise SystemExit(
            f"error: current Git branch {branch!r} contains ':', "
            f"which is not a valid Teamscale branch name"
        )
    return branch


def repo_root(start_dir: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise SystemExit("error: 'git' is not available on PATH") from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        raise SystemExit(
            f"error: not a Git repository at {start_dir}: {stderr}"
        ) from e
    return Path(result.stdout.strip())


def _branch_exists(repo_dir: Path, ref: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise SystemExit("error: 'git' is not available on PATH") from e
    return result.returncode == 0


_DEFAULT_BRANCH_CANDIDATES = ("master", "main", "develop", "trunk", "dev")


def _detect_default_branch(repo_dir: Path) -> str:
    """Determine the repository's default branch.

    Tries `origin/HEAD` first, then a list of common local branch names.
    Errors out if none exist — without an explicit base we cannot scope a
    branch-mode comparison.
    """
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise SystemExit("error: 'git' is not available on PATH") from e
    if result.returncode == 0:
        full = result.stdout.strip()  # e.g. "origin/master"
        if full.startswith("origin/"):
            return full[len("origin/"):]
        return full

    for candidate in _DEFAULT_BRANCH_CANDIDATES:
        if _branch_exists(repo_dir, candidate):
            return candidate

    raise SystemExit(
        f"error: cannot determine the default branch in {repo_dir}: "
        f"'origin/HEAD' is not set and none of "
        f"{', '.join(_DEFAULT_BRANCH_CANDIDATES)} exists. "
        f"Run 'git remote set-head origin --auto' or create one of those branches."
    )


def resolve_pr_context(
    config: TeamscaleConfig,
    user: str,
    key: str,
    repo_dir: Path,
) -> PrContext:
    """Resolve the PR context for the current Git branch in `repo_dir`.

    Looks up an open MR for the branch. If exactly one matches, returns a
    merge-request context. If none match, falls back to a branch context
    against the repository's default branch. Raises SystemExit if multiple
    MRs match (ambiguous).
    """
    branch = current_git_branch(repo_dir)
    mr = resolve_unique_merge_request(config, user, key, branch)
    if mr is not None:
        source_branch = mr.get("sourceBranch")
        target_branch = mr.get("targetBranch")
        identifier = mr.get("identifier") or {}
        merge_request_id = identifier.get("idWithRepository")

        if not source_branch or not target_branch:
            raise SystemExit(
                f"error: pull request for '{branch}' is missing source or "
                f"target branch information"
            )
        return PrContext(
            mode="merge-request",
            branch=branch,
            source=f"{source_branch}:HEAD",
            target=f"{target_branch}:HEAD",
            merge_request_id=merge_request_id if merge_request_id else None,
            merge_request=mr,
        )

    base = _detect_default_branch(repo_dir)
    return PrContext(
        mode="branch",
        branch=branch,
        source=f"{branch}:HEAD",
        target=f"{base}:HEAD",
        merge_request_id=None,
        merge_request=None,
    )


def print_resolution_banner(ctx: PrContext) -> None:
    """Write a two-line resolution banner to stderr.

    The banner is informational only — JSON output continues to go to
    stdout. The Claude Code skill relays this to the user so the chosen
    mode is visible.
    """
    if ctx.mode == "merge-request":
        sys.stderr.write(
            f"ts-agent-helper: resolved as pull request {ctx.merge_request_id}\n"
        )
    else:
        sys.stderr.write(
            f"ts-agent-helper: no pull request for branch '{ctx.branch}'; "
            f"comparing against base\n"
        )
    sys.stderr.write(f"  source={ctx.source} target={ctx.target}\n")
    sys.stderr.flush()
