"""Implementation of `ts-agent-helper pre-commit`.

Uploads local changes to the Teamscale pre-commit service, polls for the
analysis result and prints the findings in the GCC diagnostics format.
"""

from __future__ import annotations

import argparse
import locale
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .api import API_VERSION, TeamscaleCredentials, TeamscaleHttpError, api_request, get_credentials
from .config import (
    ConfigError,
    ConfigNotFoundError,
    TeamscaleConfig,
    read_config,
    to_local_path,
    to_uniform_path,
)

PRE_COMMIT_BRANCH_PREFIX = "__precommit__"

# Base branch name for changes outside any Git branch (detached HEAD, or no
# Git repository at all). The server only uses it to name the pre-commit
# branch, so any fixed name works.
NO_BRANCH_NAME = "local"

POLL_INTERVAL_SECONDS = 1.0

POLL_TIMEOUT_SECONDS = 180.0

# The server bases the upload on the first of these commits it has analyzed.
# More hints cover a longer run of unpushed local commits, but each one
# lengthens the request URL.
MAX_REVISION_HINTS = 50

# Number of leading bytes searched for a NUL byte to detect a binary file,
# the same heuristic Git uses.
_BINARY_SNIFF_BYTES = 8000

# Errors of this type only mean that the server ignores the file.
_FILE_EXCLUDED_ERROR = "FILE_EXCLUDED_BY_PROJECT_CONFIGURATION"

# Cap on the sibling locations printed per finding. Matches `teamscale-dev`.
_MAX_SIBLING_LOCATIONS = 5


def _run_git(directory: Path, git_args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *git_args],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as e:
        raise SystemExit("error: 'git' is not available on PATH") from e


def git_toplevel(directory: Path) -> Optional[Path]:
    """Return the root of the Git working tree containing `directory`.

    Returns `None` if `directory` is not inside a Git working tree.
    """
    result = _run_git(directory, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def git_branch(repo: Path) -> Optional[str]:
    """Return the checked-out branch, or `None` for a detached HEAD."""
    result = _run_git(repo, ["branch", "--show-current"])
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        return None
    return branch


def pre_commit_base_branch(config: TeamscaleConfig, repo: Optional[Path]) -> str:
    """Return the branch name the pre-commit branch is named after.

    Prefers `project.branch` from `.teamscale.toml` over the checked-out Git
    branch, as all other subcommands do.
    """
    if config.project_branch:
        return config.project_branch
    if repo is not None:
        branch = git_branch(repo)
        if branch:
            return branch
    return NO_BRANCH_NAME


def pre_commit_branch_name(username: str, base_branch: str) -> str:
    """Return the name of the pre-commit branch the server creates for a user.

    The server stores user names in lower case.
    """
    return f"{PRE_COMMIT_BRANCH_PREFIX}{username.lower()}__branch__{base_branch}"


def _revision_hints(repo: Optional[Path]) -> list[str]:
    """Return the most recent commits of HEAD, newest first.

    Returns an empty list outside Git or before the first commit. The server
    then bases the upload on the default branch.
    """
    if repo is None:
        return []
    result = _run_git(repo, ["rev-list", f"--max-count={MAX_REVISION_HINTS}", "HEAD"])
    if result.returncode != 0:
        return []
    return result.stdout.split()


def _uncommitted_files(paths: list[Path]) -> list[Path]:
    """Return the added, modified, deleted and untracked files below `paths`.

    Git-ignored files are not included.
    """
    paths_by_repo: dict[Path, list[Path]] = {}
    for path in paths:
        repo = git_toplevel(path if path.is_dir() else path.parent)
        if repo is None:
            raise SystemExit(f"error: not under Git version control: {path}")
        paths_by_repo.setdefault(repo, []).append(path)

    changed: set[Path] = set()
    for repo, repo_paths in paths_by_repo.items():
        result = _run_git(repo, [
            "status", "--porcelain=v1", "-z", "--untracked-files=all",
            "--no-renames", "--ignore-submodules=all",
            "--", *(str(path) for path in repo_paths),
        ])
        if result.returncode != 0:
            raise SystemExit(
                f"error: 'git status' failed in {repo}: {result.stderr.strip()}"
            )
        # Each entry is "XY <path>", with the path relative to the repository root.
        for entry in result.stdout.split("\0"):
            if len(entry) > 3:
                changed.add(repo / entry[3:])
    return sorted(changed)


def _all_files(paths: list[Path]) -> list[Path]:
    """Return all regular files below `paths`, skipping `.git` directories."""
    files: set[Path] = set()
    for path in paths:
        if path.is_file():
            files.add(path)
            continue
        for candidate in path.rglob("*"):
            if ".git" in candidate.relative_to(path).parts:
                continue
            if candidate.is_file() and not candidate.is_symlink():
                files.add(candidate)
    return sorted(files)


def _read_text(path: Path) -> Optional[str]:
    """Return the content of a text file, or `None` for a binary file.

    Decodes UTF-8 and falls back to the platform encoding. A leading byte
    order mark is dropped.
    """
    data = path.read_bytes()
    if b"\0" in data[:_BINARY_SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode(locale.getpreferredencoding(False), errors="replace")


@dataclass
class _UploadGroup:
    """Files sent in a single request: same server, project and branch."""

    config: TeamscaleConfig
    credentials: TeamscaleCredentials
    base_branch: str
    revision_hints: list[str]
    contents: dict[str, Optional[str]] = field(default_factory=dict)
    local_paths: dict[str, Path] = field(default_factory=dict)

    def api_path(self, suffix: str = "") -> str:
        project = urllib.parse.quote(self.config.project_id, safe="")
        return f"/api/v{API_VERSION}/projects/{project}/pre-commit{suffix}"

    def display_path(self, uniform_path: str) -> str:
        """Return the local path for a uniform path, or the uniform path itself."""
        local_path = self.local_paths.get(uniform_path)
        if local_path is None:
            local_path = to_local_path(self.config, uniform_path)
        if local_path is None:
            return uniform_path
        return str(local_path)


def _existing_ancestor(directory: Path) -> Path:
    """Return `directory` or its nearest existing parent.

    The directory of a deleted file may be deleted as well.
    """
    while not directory.is_dir() and directory.parent != directory:
        directory = directory.parent
    return directory


def _build_upload_groups(files: list[Path]) -> list[_UploadGroup]:
    configs: dict[Path, Optional[TeamscaleConfig]] = {}
    repos: dict[Path, Optional[Path]] = {}
    groups: dict[tuple[str, str, str, Optional[Path]], _UploadGroup] = {}
    skipped_binary = 0

    for file in files:
        directory = file.parent
        if directory not in configs:
            try:
                configs[directory] = read_config(directory)
            except ConfigNotFoundError:
                configs[directory] = None
            except ConfigError as e:
                raise SystemExit(f"error: {e}") from e
        config = configs[directory]
        if config is None:
            sys.stderr.write(f"warning: no .teamscale.toml covers {file}; skipped\n")
            continue

        if file.is_symlink():
            continue
        if file.exists():
            content = _read_text(file)
            if content is None:
                skipped_binary += 1
                continue
        else:
            # The server treats a null content as a deletion.
            content = None

        if directory not in repos:
            repos[directory] = git_toplevel(_existing_ancestor(directory))
        repo = repos[directory]
        base_branch = pre_commit_base_branch(config, repo)
        key = (config.server_url, config.project_id, base_branch, repo)
        group = groups.get(key)
        if group is None:
            group = _UploadGroup(
                config=config,
                credentials=get_credentials(config.server_url),
                base_branch=base_branch,
                revision_hints=_revision_hints(repo),
            )
            groups[key] = group
        uniform_path = to_uniform_path(config, file)
        group.contents[uniform_path] = content
        group.local_paths[uniform_path] = file

    if skipped_binary:
        sys.stderr.write(f"note: skipped {skipped_binary} binary file(s)\n")
    return list(groups.values())


class _ErrorCounter:
    def __init__(self) -> None:
        self.excluded_files = 0

    def check(self, result: dict[str, Any]) -> None:
        """Report the errors of a server result.

        Raises `SystemExit` for an error that invalidates the whole result.
        """
        for error in result.get("detailedErrors") or []:
            error_type = error.get("type")
            if error_type == _FILE_EXCLUDED_ERROR:
                self.excluded_files += 1
                continue
            message = error.get("message") or error_type
            path = error.get("affectedUniformPath")
            if path is None and error.get("resultsInvalid"):
                raise SystemExit(f"error: pre-commit analysis failed: {message}")
            prefix = f"{path}: " if path else ""
            sys.stderr.write(f"warning: {prefix}{message}\n")


def _run_pre_commit(groups: list[_UploadGroup]) -> list[tuple[_UploadGroup, dict[str, Any]]]:
    """Upload each group and wait for its findings."""
    errors = _ErrorCounter()
    findings: list[tuple[_UploadGroup, dict[str, Any]]] = []
    pending: list[tuple[_UploadGroup, str]] = []

    def collect(group: _UploadGroup, result: Any) -> None:
        if not isinstance(result, dict):
            raise SystemExit(f"unexpected response (not an object): {result!r}")
        errors.check(result)
        token = result.get("token")
        if token:
            pending.append((group, token))
            return
        for finding in result.get("findings") or []:
            findings.append((group, finding))

    for group in groups:
        try:
            api_request(
                group.config.server_url,
                group.api_path(),
                group.credentials,
                method="DELETE",
                params={"branch": group.base_branch},
            )
        except TeamscaleHttpError as e:
            if e.status != 404:
                raise

    for group in groups:
        result = api_request(
            group.config.server_url,
            group.api_path(),
            group.credentials,
            method="POST",
            params={"branch": group.base_branch, "revision-hint": group.revision_hints},
            json_body=group.contents,
        )
        collect(group, result)

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while pending:
        if time.monotonic() >= deadline:
            raise SystemExit(
                f"error: pre-commit analysis timed out after "
                f"{POLL_TIMEOUT_SECONDS:.0f} seconds"
            )
        time.sleep(POLL_INTERVAL_SECONDS)
        polled = list(pending)
        pending.clear()
        for group, token in polled:
            result = api_request(
                group.config.server_url,
                group.api_path("/" + urllib.parse.quote(token, safe="")),
                group.credentials,
            )
            collect(group, result)

    if errors.excluded_files:
        sys.stderr.write(
            f"note: {errors.excluded_files} file(s) excluded by the project's "
            f"include/exclude patterns\n"
        )
    return findings


def _is_selected(finding: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.only_pre_commit_findings:
        birth_branch = (finding.get("birth") or {}).get("branchName") or ""
        if not birth_branch.startswith(PRE_COMMIT_BRANCH_PREFIX):
            return False
    if args.severity and finding.get("assessment") != args.severity:
        return False
    if args.category:
        categories = {
            category.strip().lower()
            for value in args.category
            for category in value.split(",")
        }
        if (finding.get("categoryName") or "").lower() not in categories:
            return False
    return True


def _line_range(location: dict[str, Any]) -> tuple[int, int]:
    """Return the 1-based line range, with 0 for an unknown line."""
    start = max(location.get("rawStartLine") or 0, 0)
    end = max(location.get("rawEndLine") or start, start)
    return start, end


def _format_findings(findings: list[tuple[_UploadGroup, dict[str, Any]]]) -> list[str]:
    """Return GCC diagnostics lines, sorted by file, line, severity and message.

    A `note` line marks a secondary or sibling location of the finding above it.
    """
    entries = []
    for group, finding in findings:
        location = finding.get("location") or {}
        uniform_path = location.get("uniformPath") or ""
        path = group.display_path(uniform_path)
        message = finding.get("message") or finding.get("typeId") or ""
        is_red = finding.get("assessment") == "RED"
        start, end = _line_range(location)

        lines = [f"{path}:{start}:1: {'error' if is_red else 'warning'}: {message}"]
        secondary = sorted(
            _line_range(secondary_location)
            for secondary_location in finding.get("secondaryLocations") or []
            if secondary_location.get("uniformPath") == uniform_path
        )
        for secondary_start, _ in secondary:
            lines.append(f"{path}:{secondary_start}:1: note: ... {message}")
        for sibling in (finding.get("siblingLocations") or [])[:_MAX_SIBLING_LOCATIONS]:
            sibling_path = group.display_path(sibling.get("uniformPath") or "")
            lines.append(
                f"{sibling_path}:{_line_range(sibling)[0]}:1: note: ... {message}"
            )
        entries.append(((path, start, end, 0 if is_red else 1, message), lines))

    entries.sort(key=lambda entry: entry[0])
    return [line for _, lines in entries for line in lines]


def cmd_pre_commit(args: argparse.Namespace) -> int:
    paths = [Path(path).resolve(strict=False) for path in (args.paths or ["."])]
    for path in paths:
        if not path.exists():
            raise SystemExit(f"error: path does not exist: {path}")

    if args.no_change_detection:
        files = _all_files(paths)
    else:
        files = _uncommitted_files(paths)

    groups = [group for group in _build_upload_groups(files) if group.contents]
    if not groups:
        sys.stderr.write("note: no changed files to analyze\n")
        return 0

    findings = [
        (group, finding)
        for group, finding in _run_pre_commit(groups)
        if _is_selected(finding, args)
    ]
    for line in _format_findings(findings):
        sys.stdout.write(line + "\n")
    return 0
