"""HTTP request helpers and credential lookup."""

from __future__ import annotations

import base64
import functools
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from . import args_file


# Page size used internally when paging through results. The server caps a
# single response at 300 elements (see openapi.json: `max` default).
PAGE_SIZE = 300

# Pinned Teamscale API version. Used in the `/api/v{API_VERSION}/...` path of
# versioned endpoints. Bump when the plugin requires newer endpoint behavior.
API_VERSION = "2026.2"

# Environment variables — mirror the `teamscale-dev` CLI (see
# `ide/cli/.../servers/env/ServersEnvironmentVariables.java`).
USER_ENV = "TEAMSCALE_DEV_USER"
ACCESSKEY_ENV = "TEAMSCALE_DEV_ACCESSKEY"
SERVERS_ENV = "TEAMSCALE_DEV_SERVERS"

# Fragment in a credentials URL that opts the server out of TLS verification,
# matching the CLI's `CredentialsUrlUtils` constant of the same name.
_TRUST_ALL_CERTIFICATES_FRAGMENT = "trust-all-certificates"

@dataclass(frozen=True)
class TeamscaleCredentials:
    """Resolved credentials for a single Teamscale server."""

    username: str
    accesskey: str
    trust_all_certificates: bool = False


def get_credentials(server_url: str) -> TeamscaleCredentials:
    """Return credentials for the given Teamscale `server_url`.

    Resolution mirrors the credential sources of the `teamscale-dev` CLI
    (see `ServersOptions`). A per-server match always wins over the
    fallback user/accesskey pair, and within each tier the environment
    variables win over the args file:

    1. `TEAMSCALE_DEV_SERVERS` — whitespace-separated credentials URLs of the
       form `https://user:accesskey@host[:port][/path][#trust-all-certificates]`.
       If an entry matches `server_url`, its credentials and TLS flag are
       used.
    2. `~/.teamscale-dev.args` `--server` entries — same URL format, but
       supplied via the CLI's args file. Consulted when `TEAMSCALE_DEV_SERVERS`
       carries no match.
    3. `TEAMSCALE_DEV_USER` / `TEAMSCALE_DEV_ACCESSKEY` — fallback credentials
       applied when no per-server entry matches.
    4. `~/.teamscale-dev.args` `--user` / `--accesskey` (also `-u` / `-k`) —
       fallback credentials from the args file, consulted last.
    """
    target = _normalize_server_url(server_url)

    raw_servers = os.environ.get(SERVERS_ENV)
    if raw_servers and raw_servers.strip():
        env_match = _lookup_in_servers_env(raw_servers, target)
        if env_match is not None:
            return env_match

    args_file_servers, args_file_user, args_file_accesskey = _read_args_file()
    args_file_match = args_file_servers.get(target)
    if args_file_match is not None:
        return args_file_match

    user = os.environ.get(USER_ENV)
    key = os.environ.get(ACCESSKEY_ENV)
    if user and key:
        return TeamscaleCredentials(username=user, accesskey=key)

    if args_file_user and args_file_accesskey:
        return TeamscaleCredentials(
            username=args_file_user, accesskey=args_file_accesskey
        )

    raise SystemExit(
        f"error: no credentials configured for Teamscale server <{server_url}>. "
        f"Set {USER_ENV} and {ACCESSKEY_ENV}, or include the server in "
        f"{SERVERS_ENV}, or place equivalent `--server`/`--user`/`--accesskey` "
        f"options in ~/{args_file.ARGS_FILE_NAME}."
    )


def _lookup_in_servers_env(
    raw: str, target_server_url: str
) -> Optional[TeamscaleCredentials]:
    """Look up `target_server_url` in `TEAMSCALE_DEV_SERVERS`.

    Validates every entry (consistent with the CLI's eager parsing) so the
    user gets a clear error for a malformed env var even when the configured
    server URL happens to match a later valid entry.
    """
    parsed_entries: dict[str, TeamscaleCredentials] = {}
    for entry in raw.split():
        normalized, credentials = _parse_credentials_url(entry)
        existing = parsed_entries.get(normalized)
        if existing is not None and existing != credentials:
            raise SystemExit(
                f"error: environment variable {SERVERS_ENV} defines "
                f"inconsistent 'username:accesskey' credentials for "
                f"Teamscale URL <{normalized}>."
            )
        parsed_entries[normalized] = credentials
    return parsed_entries.get(target_server_url)


def _read_args_file(
    path: Optional[Path] = None,
) -> tuple[dict[str, TeamscaleCredentials], Optional[str], Optional[str]]:
    """Parse `--server`, `--user` and `--accesskey` from the args file.

    Returns `(servers, fallback_user, fallback_accesskey)`. When the file is
    absent, all three are empty.
    """
    if path is None:
        path = args_file.default_args_file_path()
    if not path.is_file():
        return {}, None, None

    servers: dict[str, TeamscaleCredentials] = {}
    fallback_user: Optional[str] = None
    fallback_accesskey: Optional[str] = None

    for name, value in args_file.iter_credential_options(path):
        if name == "--server":
            normalized, credentials = _parse_credentials_url(value)
            existing = servers.get(normalized)
            if existing is not None and existing != credentials:
                raise SystemExit(
                    f"error: {path} defines inconsistent 'username:accesskey' "
                    f"credentials for Teamscale URL <{normalized}>."
                )
            servers[normalized] = credentials
        elif name in ("--user", "-u"):
            fallback_user = value
        elif name in ("--accesskey", "-k"):
            fallback_accesskey = value

    return servers, fallback_user, fallback_accesskey


def _parse_credentials_url(raw: str) -> tuple[str, TeamscaleCredentials]:
    """Parse a Teamscale credentials URL.

    Returns the normalized server URL (no userinfo, no fragment, no trailing
    slash) and the credentials it carries.
    """
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError as e:
        raise SystemExit(f"error: not a valid URL: <{raw}>: {e}") from e

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise SystemExit(f"error: Teamscale URL <{raw}> must be HTTP(S).")
    if not parsed.hostname:
        raise SystemExit(f"error: Teamscale URL <{raw}> must include a host.")
    # `urlparse` returns `username is None` when there's no `@` in the
    # netloc, and `password is None` when there's no `:` in the userinfo —
    # the same distinction the CLI's `CredentialsUrlUtils.deserialize`
    # surfaces with two separate error messages.
    if parsed.username is None:
        raise SystemExit(
            f"error: no 'username:accesskey' given in Teamscale URL <{raw}>."
        )
    if parsed.password is None:
        raise SystemExit(
            f"error: no 'accesskey' given in Teamscale URL <{raw}>."
        )

    trust_all = parsed.fragment == _TRUST_ALL_CERTIFICATES_FRAGMENT
    server_url = _build_normalized_url(
        scheme, parsed.hostname, parsed.port, parsed.path
    )
    # `parsed.username` / `parsed.password` are returned raw (no URL decoding).
    # `unquote_plus` matches the CLI's `URLDecoder.decode(value, UTF_8)`, which
    # also treats `+` as a space — a quirk inherited from form-encoded data
    # that the CLI's `CredentialsUrlUtils` relies on.
    return server_url, TeamscaleCredentials(
        username=urllib.parse.unquote_plus(parsed.username),
        accesskey=urllib.parse.unquote_plus(parsed.password),
        trust_all_certificates=trust_all,
    )


def _normalize_server_url(server_url: str) -> str:
    """Normalize a plain server URL (no userinfo) for credential matching."""
    parsed = urllib.parse.urlparse(server_url)
    return _build_normalized_url(
        parsed.scheme.lower(), parsed.hostname, parsed.port, parsed.path
    )


def _build_normalized_url(
    scheme: str, hostname: Optional[str], port: Optional[int], path: str
) -> str:
    netloc = (hostname or "").lower()
    if port is not None:
        netloc = f"{netloc}:{port}"
    return f"{scheme}://{netloc}{path.rstrip('/')}"


# macOS combines its OpenSSL-readable system roots in `cert.pem` with the
# administrator-managed trust anchors in the System keychain. Python's `ssl`
# module reads neither location automatically (it ships with its own bundled
# OpenSSL whose default verify paths don't exist), so we assemble both into a
# single verify store ourselves.
_MACOS_SYSTEM_CERT_BUNDLE = "/etc/ssl/cert.pem"
_MACOS_SYSTEM_KEYCHAIN = "/Library/Keychains/System.keychain"


def _build_ssl_context(trust_all_certificates: bool) -> Optional[ssl.SSLContext]:
    if trust_all_certificates:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    if sys.platform == "darwin":
        return _macos_ssl_context_with_keychain()
    return None


@functools.lru_cache(maxsize=None)
def _macos_ssl_context_with_keychain() -> ssl.SSLContext:
    """Build an SSL context that trusts both system roots and the System keychain.

    Why: corporate root CAs pushed via MDM land in
    `/Library/Keychains/System.keychain`, which Python's `ssl` module does not
    consult. Without this fix, the first request to any internal HTTPS service
    fails with CERTIFICATE_VERIFY_FAILED. Combining `/etc/ssl/cert.pem` (Apple's
    bundled OpenSSL roots) with certificates exported from the System keychain
    via the `security` CLI covers both Apple's defaults and the MDM-pushed
    corporate trust anchors.
    """
    cafile = (
        _MACOS_SYSTEM_CERT_BUNDLE
        if Path(_MACOS_SYSTEM_CERT_BUNDLE).is_file()
        else None
    )
    context = ssl.create_default_context(cafile=cafile)
    keychain_certs = _dump_macos_system_keychain_certs()
    if keychain_certs:
        try:
            context.load_verify_locations(cadata=keychain_certs)
        except ssl.SSLError:
            # A malformed certificate in the keychain shouldn't break HTTPS
            # entirely; fall back to whatever was loaded from `cert.pem`.
            pass
    return context


def _dump_macos_system_keychain_certs() -> Optional[str]:
    """Return PEM-formatted certificates from the macOS System keychain.

    Shells out to the macOS `security` CLI. Returns `None` if the tool is
    unavailable or fails so the caller can fall back to the bundled roots
    alone.
    """
    try:
        result = subprocess.run(
            [
                "security", "find-certificate", "-a", "-p",
                _MACOS_SYSTEM_KEYCHAIN,
            ],
            capture_output=True, text=True, check=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout or None


def _send_request(
    server_url: str,
    api_path: str,
    credentials: TeamscaleCredentials,
    method: str,
    params: Optional[dict[str, Any]],
    json_body: Any,
    accept: str,
) -> str:
    query_items: list[tuple[str, Any]] = [
        (k, v) for k, v in (params or {}).items() if v is not None and v != ""
    ]
    query = urllib.parse.urlencode(query_items, doseq=True)
    url = f"{server_url}{api_path}"
    if query:
        url += "?" + query

    body_bytes: Optional[bytes] = None
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")

    auth = base64.b64encode(
        f"{credentials.username}:{credentials.accesskey}".encode("utf-8")
    ).decode("ascii")
    request = urllib.request.Request(url, data=body_bytes, method=method)
    request.add_header("Authorization", f"Basic {auth}")
    request.add_header("Accept", accept)
    if body_bytes is not None:
        request.add_header("Content-Type", "application/json")

    ssl_context = _build_ssl_context(credentials.trust_all_certificates)
    try:
        with urllib.request.urlopen(request, context=ssl_context) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace").strip()
        message = f"HTTP {e.code} {e.reason} from {url}"
        if body:
            message += f"\n{body}"
        if e.code in (401, 403):
            message += (
                f"\nCheck the credentials configured via {USER_ENV}/{ACCESSKEY_ENV} "
                f"or {SERVERS_ENV}."
            )
        raise SystemExit(message) from e
    except urllib.error.URLError as e:
        raise SystemExit(f"failed to reach {url}: {e.reason}") from e


def api_request(
    server_url: str,
    api_path: str,
    credentials: TeamscaleCredentials,
    method: str = "GET",
    params: Optional[dict[str, Any]] = None,
    json_body: Any = None,
) -> Any:
    """Issue a JSON-accepting request and parse the response as JSON.

    Returns `None` for empty bodies (e.g. HTTP 204).
    """
    raw = _send_request(
        server_url, api_path, credentials, method, params, json_body,
        accept="application/json",
    )
    return json.loads(raw) if raw else None


def api_request_text(
    server_url: str,
    api_path: str,
    credentials: TeamscaleCredentials,
    method: str = "GET",
    params: Optional[dict[str, Any]] = None,
    accept: str = "text/csv",
) -> str:
    """Issue a request and return the raw decoded response body as text."""
    return _send_request(
        server_url, api_path, credentials, method, params, json_body=None,
        accept=accept,
    )
