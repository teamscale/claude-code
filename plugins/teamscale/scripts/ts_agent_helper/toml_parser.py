"""Minimal TOML parser sufficient for `.teamscale.toml` v1.0.

A full TOML implementation is in the standard library only as of Python 3.11
(`tomllib`). This script targets 3.10, so we implement just the subset needed
here: top-level keys, `[section]` headers, dotted keys, string/bool/integer
values, and `#` line comments.
"""

from __future__ import annotations

from typing import Any, Optional


class TomlParseError(Exception):
    pass


def parse_toml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_section: dict[str, Any] = result

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_toml_comment(raw_line).strip()
        if not line:
            continue

        if line.startswith("["):
            if not line.endswith("]"):
                raise TomlParseError(f"line {lineno}: unterminated section header")
            path = [s.strip() for s in line[1:-1].split(".")]
            if any(not s for s in path):
                raise TomlParseError(f"line {lineno}: empty segment in section header")
            current_section = result
            for segment in path:
                next_section = current_section.setdefault(segment, {})
                if not isinstance(next_section, dict):
                    raise TomlParseError(
                        f"line {lineno}: '{segment}' already defined as non-section"
                    )
                current_section = next_section
            continue

        if "=" not in line:
            raise TomlParseError(f"line {lineno}: expected '='")
        key_part, _, value_part = line.partition("=")
        key_chain = [k.strip() for k in key_part.strip().split(".")]
        if any(not k for k in key_chain):
            raise TomlParseError(f"line {lineno}: empty key segment")

        target = current_section
        for segment in key_chain[:-1]:
            next_section = target.setdefault(segment, {})
            if not isinstance(next_section, dict):
                raise TomlParseError(
                    f"line {lineno}: '{segment}' already defined as non-section"
                )
            target = next_section
        target[key_chain[-1]] = _parse_toml_value(value_part.strip(), lineno)

    return result


def _strip_toml_comment(line: str) -> str:
    """Strip a trailing `# comment`, ignoring `#` inside quoted strings."""
    in_quote: Optional[str] = None
    i = 0
    while i < len(line):
        c = line[i]
        if in_quote is not None:
            if in_quote == '"' and c == "\\" and i + 1 < len(line):
                i += 2
                continue
            if c == in_quote:
                in_quote = None
        elif c in ('"', "'"):
            in_quote = c
        elif c == "#":
            return line[:i]
        i += 1
    return line


def _parse_toml_value(raw: str, lineno: int) -> Any:
    if not raw:
        raise TomlParseError(f"line {lineno}: missing value")
    if raw == "true":
        return True
    if raw == "false":
        return False
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        inner = raw[1:-1]
        if raw[0] == '"':
            return _decode_basic_string(inner, lineno)
        return inner
    try:
        if "." in raw or "e" in raw or "E" in raw:
            return float(raw)
        return int(raw)
    except ValueError as e:
        raise TomlParseError(f"line {lineno}: cannot parse value '{raw}'") from e


_BASIC_STRING_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "/": "/",
    "b": "\b",
    "f": "\f",
}


def _decode_basic_string(s: str, lineno: int) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in _BASIC_STRING_ESCAPES:
                out.append(_BASIC_STRING_ESCAPES[nxt])
                i += 2
                continue
            raise TomlParseError(f"line {lineno}: unsupported escape sequence \\{nxt}")
        out.append(c)
        i += 1
    return "".join(out)
