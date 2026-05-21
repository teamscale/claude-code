"""ts-agent-helper: helper command for AI agents to interact with Teamscale.

Reads server connection details from a `.teamscale.toml` configuration file
hierarchy (see ADR 0016) and looks up Basic Auth credentials from the same
sources as the `teamscale-dev` CLI, in this order:

1. `TEAMSCALE_DEV_SERVERS` environment variable (per-server URL match),
2. `--server` entries in `~/.teamscale-dev.args` (per-server URL match),
3. `TEAMSCALE_DEV_USER` / `TEAMSCALE_DEV_ACCESSKEY` (fallback),
4. `--user` / `--accesskey` in `~/.teamscale-dev.args` (fallback).

Designed for Python 3.9+ using only the standard library.
"""
