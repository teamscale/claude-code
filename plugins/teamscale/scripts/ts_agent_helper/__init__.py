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

import sys

# Minimum interpreter, checked here because Python runs a package's
# `__init__.py` before any of its submodules: this one check covers every
# entry point and nothing can be imported without passing it. Consequence:
# this module must stay within Python 3.6 syntax -- no `from __future__ import
# annotations`, no walrus operator, no unquoted `dict[str, str]` -- because an
# interpreter that cannot parse it never reaches the check and reports a
# `SyntaxError` instead, which is the failure this exists to prevent.
# Raising the minimum means updating the plugin README and check-setup skill.
MINIMUM_PYTHON_VERSION = (3, 9)

if sys.version_info < MINIMUM_PYTHON_VERSION:
    sys.stderr.write(
        "Error: the Teamscale plugin requires Python %d.%d or newer "
        "(found %d.%d.%d at %s).\n"
        % (MINIMUM_PYTHON_VERSION + tuple(sys.version_info[:3]) + (sys.executable,))
    )
    sys.stderr.write(
        "Install a newer Python and make sure it is the interpreter found on PATH.\n"
    )
    raise SystemExit(1)
