"""ts-agent-helper: helper command for AI agents to interact with Teamscale.

Reads server connection details from a `.teamscale.toml` configuration file
hierarchy (see ADR 0016) and uses Basic Auth credentials from the environment
variables `TEAMSCALE_DEV_USER` and `TEAMSCALE_DEV_ACCESSKEY`.

Designed for Python 3.10+ using only the standard library.
"""
