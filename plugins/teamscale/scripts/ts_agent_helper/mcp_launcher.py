"""Launcher used by `.mcp.json` to start `teamscale-dev mcp`.

Why this exists: the `mcp` subcommand of `teamscale-dev` does not accept
`--server`, `--user` or `--accesskey` as CLI options, so picocli's
`@<path>` at-file expansion cannot be used to inject credentials from
`~/.teamscale-dev.args` directly on the command line. This launcher
parses that file and translates the recognized options into the
environment variables `teamscale-dev` also reads, then `execvpe`s the
real binary with the original argv unchanged.

Precedence: an environment variable already present in the parent
process wins over the args file. `TEAMSCALE_DEV_SERVERS` is the only
list-valued variable; entries from the env and from the args file are
concatenated (env first) so both sets of servers remain reachable. A
collision on the same server URL is left for `teamscale-dev` to report,
matching the validation it already performs on `TEAMSCALE_DEV_SERVERS`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from . import args_file

# Env vars consumed by `teamscale-dev` — mirror the names in `api.py`
# (kept inline rather than imported to avoid pulling in the HTTP stack
# just to start the MCP server).
SERVERS_ENV = "TEAMSCALE_DEV_SERVERS"
USER_ENV = "TEAMSCALE_DEV_USER"
ACCESSKEY_ENV = "TEAMSCALE_DEV_ACCESSKEY"

# Name of the binary we delegate to. Looked up via `PATH` (same
# expectation as the previous bash wrapper).
_TEAMSCALE_DEV_BINARY = "teamscale-dev"


def main() -> "Optional[int]":
    env = dict(os.environ)
    path = args_file.default_args_file_path()
    if path.is_file():
        _apply_args_file_to_env(path, env)
    os.execvpe(_TEAMSCALE_DEV_BINARY, [_TEAMSCALE_DEV_BINARY, *sys.argv[1:]], env)


def _apply_args_file_to_env(path: Path, env: "dict[str, str]") -> None:
    servers: "list[str]" = []
    user: Optional[str] = None
    accesskey: Optional[str] = None

    for name, value in args_file.iter_credential_options(path):
        if name == "--server":
            servers.append(value)
        elif name in ("--user", "-u"):
            user = value
        elif name in ("--accesskey", "-k"):
            accesskey = value

    if servers:
        existing = env.get(SERVERS_ENV, "").strip()
        env[SERVERS_ENV] = " ".join([existing, *servers]) if existing else " ".join(servers)
    if user and USER_ENV not in env:
        env[USER_ENV] = user
    if accesskey and ACCESSKEY_ENV not in env:
        env[ACCESSKEY_ENV] = accesskey


if __name__ == "__main__":
    sys.exit(main() or 0)
