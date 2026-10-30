"""Teamscale configuration handling.

Mirrors the lookup strategy implemented in
`ide/config/src/main/java/com/teamscale/ide/config/TeamscaleConfigReader.java`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from .toml_parser import TomlParseError, parse_toml


CONFIG_FILE_NAME = ".teamscale.toml"

# Exit codes shared by every subcommand.
EXIT_NOT_CONFIGURED = 3


class ConfigError(Exception):
    pass


class ConfigNotFoundError(ConfigError):
    """Raised when no `.teamscale.toml` exists anywhere in the search path."""


class TeamscaleConfig:
    def __init__(
        self,
        server_url: str,
        project_id: str,
        project_branch: Optional[str],
        project_path_segments: list[str],
        local_base_path: Path,
    ) -> None:
        self.server_url = server_url
        self.project_id = project_id
        self.project_branch = project_branch
        self.project_path_segments = project_path_segments
        self.local_base_path = local_base_path


def parse_code_path(raw: str) -> list[str]:
    """Parse a uniform path string into unescaped segments.

    Mirrors `CodePath.parse` from `ide/config`. A leading slash is optional.
    The empty string and a bare `/` (i.e. the root) both return an empty list.

    The only escape recognised is `\\/`, which yields a literal `/` inside a
    segment. No other backslash escapes are supported, so `\\\\` in TOML stays
    a literal `\\\\` here. Internal empty segments (e.g. `a//b`) and a trailing
    `/` (e.g. `a/b/`) are rejected as configuration errors.
    """
    if raw.startswith("/"):
        raw = raw[1:]
    if not raw:
        return []

    segments: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw) and raw[i + 1] == "/":
            current.append("/")
            i += 2
            continue
        if c == "/":
            if not current:
                raise ConfigError(f"empty segment in code path: {raw}")
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    if not current and segments:
        raise ConfigError(
            f"empty trailing segment in code path: {raw} "
            f"(drop the trailing '/')"
        )
    if current:
        segments.append("".join(current))
    return segments


def to_uniform_path(config: TeamscaleConfig, target: Path) -> str:
    """Return the uniform path on the Teamscale server for a local path.

    Raises `SystemExit` if `target` is not below the configured local base path.
    """
    try:
        relative = target.relative_to(config.local_base_path)
    except ValueError as e:
        raise SystemExit(
            f"error: '{target}' is not below the configured local base path "
            f"'{config.local_base_path}'"
        ) from e
    relative_parts = [p for p in relative.parts if p not in ("", ".")]
    segments = config.project_path_segments + relative_parts
    return "/".join(segment.replace("/", "\\/") for segment in segments)


def to_local_path(config: TeamscaleConfig, uniform_path: str) -> Optional[Path]:
    """Return the local path for a uniform path on the Teamscale server.

    Returns `None` if the uniform path is outside the configured project path.
    """
    try:
        segments = parse_code_path(uniform_path)
    except ConfigError:
        return None
    prefix = config.project_path_segments
    if segments[: len(prefix)] != prefix:
        return None
    return config.local_base_path.joinpath(*segments[len(prefix):])


def read_config(start_dir: Path) -> TeamscaleConfig:
    server_url: Optional[str] = None
    project_id: Optional[str] = None
    project_branch: Optional[str] = None
    project_path: Optional[list[str]] = None
    local_base_path: Optional[Path] = None
    found_any = False

    cur: Optional[Path] = start_dir
    while cur is not None:
        config_file = cur / CONFIG_FILE_NAME
        if config_file.is_file():
            found_any = True
            try:
                data = parse_toml(config_file.read_text(encoding="utf-8"))
            except TomlParseError as e:
                raise ConfigError(f"failed to parse {config_file}: {e}") from e

            version = str(data.get("version", "1.0"))
            if not version.startswith("1."):
                raise ConfigError(
                    f"unsupported config version in {config_file}: {version}"
                )

            server_section = data.get("server", {}) or {}
            project_section = data.get("project", {}) or {}

            if server_url is None and "url" in server_section:
                server_url = str(server_section["url"]).strip()
            if project_id is None and "id" in project_section:
                project_id = str(project_section["id"])
            if project_branch is None and "branch" in project_section:
                project_branch = str(project_section["branch"])
                # Branches go into '{branch}:HEAD' query strings; a colon
                # in the branch would yield 'foo:bar:HEAD', which the
                # server parses as a different revision (or rejects).
                # Refuse upfront with an explicit error.
                if ":" in project_branch:
                    raise ConfigError(
                        f"project.branch in {config_file} contains ':', "
                        f"which is not a valid Teamscale branch name: "
                        f"{project_branch!r}"
                    )
            if project_path is None and "path" in project_section:
                project_path = parse_code_path(str(project_section["path"]))
                local_base_path = cur
            elif project_path is None and "id" in project_section:
                # Implicit: setting `project.id` without `project.path` maps the
                # current folder to the project root (see ADR 0016).
                project_path = []
                local_base_path = cur

            if bool(data.get("root", False)):
                break

        parent = cur.parent
        if parent == cur:
            break
        cur = parent

    if not found_any:
        raise ConfigNotFoundError(
            f"no {CONFIG_FILE_NAME} found from {start_dir} upwards to filesystem root"
        )
    if not server_url:
        raise ConfigError("server.url is missing in the configuration hierarchy")
    if not project_id:
        raise ConfigError("project.id is missing in the configuration hierarchy")
    if project_path is None or local_base_path is None:
        raise ConfigError("project.path is missing in the configuration hierarchy")

    return TeamscaleConfig(
        server_url=server_url.rstrip("/"),
        project_id=project_id,
        project_branch=project_branch,
        project_path_segments=project_path,
        local_base_path=local_base_path,
    )


def _not_configured_message(start_dir: Path) -> str:
    """Guidance printed when no `.teamscale.toml` is found."""
    return (
        f"not-configured: no {CONFIG_FILE_NAME} found from {start_dir} upwards "
        "to the filesystem root.\n"
        "\n"
        "This repository is not set up for Teamscale, so Teamscale skills "
        "(findings, test selection, test gaps) cannot run here yet.\n"
        "\n"
        "Explain this to the user, then ask whether this project is already "
        "set up on a Teamscale server:\n"
        f"  - If yes, or they are unsure: the {CONFIG_FILE_NAME} is just "
        "missing locally. Suggest running /teamscale:check-setup, which will "
        "offer to create one.\n"
        "  - If no: this repository is not on Teamscale yet, so stop here.\n"
    )


def read_config_or_exit(start_dir: Path) -> TeamscaleConfig:
    """Read the Teamscale config, or exit the process with an actionable message."""
    try:
        return read_config(start_dir)
    except ConfigNotFoundError:
        sys.stderr.write(_not_configured_message(start_dir))
        raise SystemExit(EXIT_NOT_CONFIGURED)
    except ConfigError as e:
        raise SystemExit(f"error: {e}") from e
