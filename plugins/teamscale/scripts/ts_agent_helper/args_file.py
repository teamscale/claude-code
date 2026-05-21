"""Shared parser for the `~/.teamscale-dev.args` picocli at-file.

Two callers need to read the same set of credential-related options
from this file:

- `api.py` builds typed `TeamscaleCredentials` for in-process HTTP calls.
- `mcp_launcher.py` translates the same options into environment
  variables so they reach `teamscale-dev mcp`, which does not accept
  them as CLI options on its subcommand.

Both consumers share the low-level tokenization here so a change to the
options we recognize (e.g. adding `--proxy` later) lands in one place.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Iterator, Optional


# Filename of the args file in the user's home directory. The CLI also
# accepts arbitrary at-files via picocli's `@<path>` syntax, but the
# helper only auto-discovers this fixed location to match the
# documented setup workflow.
ARGS_FILE_NAME = ".teamscale-dev.args"


# Options the helper consumes from the args file. Anything else (e.g.
# `--insecure`, `--proxy`) is silently ignored — picocli's full grammar
# lives in `teamscale-dev` itself, and we only translate
# credential-related options here.
CREDENTIAL_OPTIONS = frozenset({
    "--server", "--user", "-u", "--accesskey", "-k",
})


def default_args_file_path() -> Path:
    """Return the canonical `~/.teamscale-dev.args` path."""
    return Path.home() / ARGS_FILE_NAME


def iter_credential_options(path: Path) -> Iterator[tuple[str, str]]:
    """Yield `(option, value)` pairs from `path` for credential options.

    Skips options the helper doesn't consume. Raises `SystemExit` for
    parse failures or missing arguments so the caller's command-line
    output stays clean.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"error: failed to read {path}: {e}") from e

    # Picocli's at-file syntax treats `#` as a line comment only at the
    # start of a line. Strip those lines ourselves rather than passing
    # `comments=True` to `shlex.split`, which would also eat `#` mid-token
    # and break URL fragments like `#trust-all-certificates`.
    stripped = "\n".join(
        line for line in content.splitlines() if not line.lstrip().startswith("#")
    )
    try:
        tokens = shlex.split(stripped, comments=False)
    except ValueError as e:
        raise SystemExit(f"error: failed to parse {path}: {e}") from e

    i = 0
    while i < len(tokens):
        name, value, consumed = _read_option(tokens, i, path)
        i += consumed
        if value is not None:
            yield name, value


def _read_option(
    tokens: "list[str]", i: int, path: Path
) -> "tuple[str, Optional[str], int]":
    """Return `(name, value, tokens_consumed)` for the option at `tokens[i]`.

    Supports `--option=VALUE` and `--option VALUE` forms (the latter pulls
    the next token). `value` is `None` for options the helper does not
    consume; the caller advances by `tokens_consumed` either way.
    """
    token = tokens[i]
    name, equals, embedded = token.partition("=")
    if name not in CREDENTIAL_OPTIONS:
        return name, None, 1
    if equals:
        return name, embedded, 1
    if i + 1 >= len(tokens):
        raise SystemExit(
            f"error: {path}: option {name} is missing its argument."
        )
    return name, tokens[i + 1], 2
