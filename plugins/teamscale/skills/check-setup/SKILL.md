---
name: check-setup
description: Checks the setup of the Teamscale integration, especially whether the `teamscale-dev` tool is installed properly, whether a `.teamscale.toml` file is present and whether the Teamscale server is reachable.
disable-model-invocation: true
---

# Check Teamscale Setup

Verify the Teamscale integration is configured correctly. Run the steps below in order. 
If a step fails, give the user the instructions for that step and stop. Do not continue to later steps until the issue 
is resolved (the user may want to fix it and re-run the skill).

When reporting results, briefly tell the user what each check found. Do not skip steps.

## Step 1: Python 3.10+

Run:

```bash
python3 --version
```

If `python3` is not on the PATH, or the version is below 3.10, tell the user that the Teamscale plugin requires Python 3.10 
or newer and ask them to install it (e.g. via their package manager or from https://www.python.org/downloads/).


## Step 2: `teamscale-dev` installed and recent

Run:

```bash
teamscale-dev --version
```

The required minimum version is **2026.3.0**. If the command is not found, or the version is older than 2026.3.0, point 
the user to the installation guide at https://docs.teamscale.com/howto/integrating-with-your-ide/other-ides/#installing-teamscale-dev


## Step 3: `.teamscale.toml` present

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

## Step 4: Teamscale server version

Read the `[server].url` from `.teamscale.toml` and fetch the public version endpoint (no authentication required):

```bash
curl -fsS "<URL>/api/version"
```

Replace `<URL>` with the value from the file (strip any trailing `/` so the path becomes `<URL>/api/version`). Example response:

```json
{"maxApiVersion":{"major":2026,"minor":3,"patch":2},"minApiVersion":{"major":5,"minor":7,"patch":0},"adminContact":"..."}
```

Inspect `maxApiVersion`. The minimum required version is **2026.2** (i.e. `major > 2026`, or `major == 2026 && minor >= 2`). If it is older, tell the user the Teamscale server needs to be upgraded and stop.

If the request fails (connection refused, timeout, non-2xx status), tell the user the server is unreachable and to verify the `url` in `.teamscale.toml` and their network/VPN connection. Stop on failure.

## Step 5: Credentials in environment

Check that `TEAMSCALE_DEV_USER` and `TEAMSCALE_DEV_ACCESSKEY` are set, **without ever printing or otherwise exposing their values**. Use a presence-only check such as:

```bash
[ -n "${TEAMSCALE_DEV_USER+x}" ] && echo "TEAMSCALE_DEV_USER: set" || echo "TEAMSCALE_DEV_USER: not set"
[ -n "${TEAMSCALE_DEV_ACCESSKEY+x}" ] && echo "TEAMSCALE_DEV_ACCESSKEY: set" || echo "TEAMSCALE_DEV_ACCESSKEY: not set"
```

Do **not** echo `$TEAMSCALE_DEV_USER` or `$TEAMSCALE_DEV_ACCESSKEY`, do not pass them to other commands, and do not include them in any output to the user.

If either variable is missing, instruct the user:

1. Obtain an access key from Teamscale, by visiting the URL "<URL>/user/access-key", where "<URL>" is the `[server].url` field from `.teamscale.toml`.
   Alternatively, the user can open the Teamscale server in a browser, click the avatar in the upper right corner, and choose **Access Keys**.
2. Set the variables in their shell profile (e.g. `~/.bashrc`, `~/.zshrc`) on Linux/macOS:

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

3. Restart the shell (and Claude Code) so the new variables are picked up.


## Step 6: Verify configuration against the server

Run:

```bash
teamscale-dev verify-config
```

If the command prints an error, relay the error message to the user verbatim so they can act on it. 
Common causes are an unreachable server, a wrong project ID in `.teamscale.toml`, or invalid credentials.

More information can be found here: https://docs.teamscale.com/reference/cli/teamscale-dev/#the-verify-configuration-command

## Step 7: Report success

If all previous steps passed, tell the user the Teamscale setup looks fine. Add a note that **if they changed environment variables, the `.teamscale.toml`, or installed/upgraded `teamscale-dev`, they may need to restart Claude Code** for the changes to take effect.
