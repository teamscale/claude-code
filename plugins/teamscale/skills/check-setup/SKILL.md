---
name: check-setup
description: Checks the setup of the Teamscale integration, especially whether Python and the plugin's helper work, whether a `.teamscale.toml` file is present, whether credentials are configured and whether the Teamscale server is reachable.
disable-model-invocation: true
---

# Check Teamscale Setup

Verify the Teamscale integration is configured correctly. Run the steps below in order.
If a step fails, give the user the instructions for that step and stop. Do not continue to later steps until the issue
is resolved (the user may want to fix it and re-run the skill).

When reporting results, briefly tell the user what each check found. Do not skip steps.

Where a step gives both a POSIX and a Windows command, run only the one matching the user's platform.

On Windows, when a step finds a required tool missing, search the web for the correct `winget` command
to install it and give the user that command to run. If no winget package exists, fall back to the
installation instructions given in that step.

## Step 1: Python 3.9+

On Linux/macOS, run:

```bash
python3 --version
```

On Windows:

```powershell
py --version
```

If `py` is not found, fall back to `python --version`.

If no interpreter is found, or the version is below 3.9, tell the user that the Teamscale plugin requires Python 3.9
or newer and ask them to install it (e.g. via their package manager or from https://www.python.org/downloads/).


## Step 2: `git` available

Run:

```
git --version
```

If the command is not found, tell the user that `git` must be installed and on
PATH, and stop.

On Windows, `git` comes from [Git for Windows](https://gitforwindows.org/).


## Step 3: `ts-agent-helper` reachable

Run:

```
ts-agent-helper --help
```

The usage text must appear. `ts-agent-helper` is the launcher the
finding and test-gap skills call, and it ships in the teamscale plugin's
`bin/` directory.

If the command is not found, the agent host does not put that directory on the
PATH of the shell it spawns. That is not an error the user has to fix: locate
the launcher in the teamscale plugin's `bin/` directory, run it by its absolute
path to confirm it works, and report the path.


## Step 4: `.teamscale.toml` present

Check whether `.teamscale.toml` exists at the repository root (the current working directory).

- If it exists, continue.
- If it is missing, offer to create one. Ask the user for the Teamscale server URL and the project ID (these are the minimum required fields). A minimal file looks like:

```toml
version = 1.0
root = true

[server]
url = "https://teamscale.example.com/"

[project]
id = "my-project"
path = "/"
```

Refer the user to https://docs.teamscale.com/reference/teamscale-toml/ for the full format and additional options. Only create the file after the user confirms the values.

## Step 5: Credentials available

Credentials can be supplied in three ways:

- The per-server `TEAMSCALE_DEV_SERVERS` environment variable (a whitespace-separated list of `https://user:accesskey@host/path` URLs).
- The `TEAMSCALE_DEV_USER` / `TEAMSCALE_DEV_ACCESSKEY` environment variables (used as a fallback for any server URL not covered by `TEAMSCALE_DEV_SERVERS`).
- An args file at `~/.teamscale-dev.args` containing `--server`, `--user`, and/or `--accesskey` lines. The environment variables take precedence over the args file.

At least one of these sources must provide credentials for the server URL configured in `.teamscale.toml`.

Check what's available, **without ever printing or otherwise exposing the credential values**. Use presence-only checks such as:

On Linux/macOS:

```bash
[ -n "${TEAMSCALE_DEV_USER+x}" ] && echo "TEAMSCALE_DEV_USER: set" || echo "TEAMSCALE_DEV_USER: not set"
[ -n "${TEAMSCALE_DEV_ACCESSKEY+x}" ] && echo "TEAMSCALE_DEV_ACCESSKEY: set" || echo "TEAMSCALE_DEV_ACCESSKEY: not set"
[ -n "${TEAMSCALE_DEV_SERVERS+x}" ] && echo "TEAMSCALE_DEV_SERVERS: set" || echo "TEAMSCALE_DEV_SERVERS: not set"
[ -f "${HOME}/.teamscale-dev.args" ] && echo "~/.teamscale-dev.args: present" || echo "~/.teamscale-dev.args: missing"
```

On Windows, use `Test-Path`, which reports only whether the variable or file exists and never reads the value:

```powershell
$argsFile = "$env:USERPROFILE\.teamscale-dev.args"
"TEAMSCALE_DEV_USER: $(if (Test-Path Env:TEAMSCALE_DEV_USER) { 'set' } else { 'not set' })"
"TEAMSCALE_DEV_ACCESSKEY: $(if (Test-Path Env:TEAMSCALE_DEV_ACCESSKEY) { 'set' } else { 'not set' })"
"TEAMSCALE_DEV_SERVERS: $(if (Test-Path Env:TEAMSCALE_DEV_SERVERS) { 'set' } else { 'not set' })"
"${argsFile}: $(if (Test-Path $argsFile) { 'present' } else { 'missing' })"
```

The braces in `${argsFile}` are required: without them PowerShell would read the trailing colon as part of a
drive-qualified variable name.

Do **not** echo `$TEAMSCALE_DEV_USER`, `$TEAMSCALE_DEV_ACCESSKEY`, or `$TEAMSCALE_DEV_SERVERS`, do not `cat` `~/.teamscale-dev.args`, do not pass these values to other commands, and do not include them in any output to the user.
The same applies to the PowerShell equivalents: do not print `$env:TEAMSCALE_DEV_USER`, `$env:TEAMSCALE_DEV_ACCESSKEY`
or `$env:TEAMSCALE_DEV_SERVERS`, and do not `Get-Content` the args file.

If none of these sources is configured, instruct the user:

1. Obtain an access key from Teamscale, by visiting the URL "<URL>/user/access-key", where "<URL>" is the `[server].url` field from `.teamscale.toml`.
   Alternatively, the user can open the Teamscale server in a browser, click the avatar in the upper right corner, and choose **Access Keys**.
2. Configure the credentials via **one** of the following:

    - Set environment variables in their shell profile (e.g. `~/.bashrc`, `~/.zshrc`) on Linux/macOS:

      ```bash
      export TEAMSCALE_DEV_USER="<username>"
      export TEAMSCALE_DEV_ACCESSKEY="<access-key>"
      ```

      On Windows follow these steps to set up a user-specific environment variable.

        - Click Start button
        - Search for Accounts
        - Open User Accounts
        - Go to Tasks > Change my environment variables
        - Add a new environment called TEAMSCALE_DEV_USER with value of your username.
        - Add a new environment called TEAMSCALE_DEV_ACCESSKEY with the value of your access key.

    - Or create `~/.teamscale-dev.args` (`%USERPROFILE%\.teamscale-dev.args` on Windows) with one option per line:

      ```
      --server https://<username>:<access-key>@<host>
      ```

      On Linux/macOS, restrict access with `chmod 600 ~/.teamscale-dev.args` so the file is only readable by the user.

3. Restart the shell (and the agent host: Claude Code or Copilot CLI) so any
   new variables are picked up.


## Step 6: Verify configuration against the server

Run:

```
ts-agent-helper verify-config
```

If the command is not found, run the launcher by the absolute path found in Step 3.

The command checks that the server is reachable and runs Teamscale 2026.2 or newer, that the credentials work, and
that the project, the branch and the current directory exist on the server. On success, it prints
`Verification successful.` and exits with code 0.

If the command prints an error, relay the error message to the user verbatim so they can act on it.
If the server is unreachable, also tell the user to verify the `url` in `.teamscale.toml` and their network/VPN
connection. If the server is too old, tell the user that the Teamscale server needs to be upgraded.

## Step 7: Report success

If all previous steps passed, tell the user the Teamscale setup looks fine. Add a note that **if they changed environment variables or the `.teamscale.toml`, they may need to restart the agent host (Claude Code or Copilot CLI)** for the changes to take effect.
