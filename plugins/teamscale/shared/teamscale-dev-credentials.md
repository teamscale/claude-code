# Credentials for `teamscale-dev`

`teamscale-dev` reads credentials from the environment on its own, but it does
not look at an args file unless that file is named on the command line. Decide
once, before the first `teamscale-dev` call, which of the two applies, and use
the same form for every later call in this skill run.

Check which credential source is configured, **without ever printing or
otherwise exposing the credential values**. Use presence-only checks.

On Linux/macOS:

```bash
[ -n "${TEAMSCALE_DEV_USER+x}" ] && echo "TEAMSCALE_DEV_USER: set" || echo "TEAMSCALE_DEV_USER: not set"
[ -n "${TEAMSCALE_DEV_ACCESSKEY+x}" ] && echo "TEAMSCALE_DEV_ACCESSKEY: set" || echo "TEAMSCALE_DEV_ACCESSKEY: not set"
[ -n "${TEAMSCALE_DEV_SERVERS+x}" ] && echo "TEAMSCALE_DEV_SERVERS: set" || echo "TEAMSCALE_DEV_SERVERS: not set"
[ -f "${HOME}/.teamscale-dev.args" ] && echo "~/.teamscale-dev.args: present" || echo "~/.teamscale-dev.args: missing"
```

On Windows:

```powershell
$argsFile = "$env:USERPROFILE\.teamscale-dev.args"
"TEAMSCALE_DEV_USER: $(if (Test-Path Env:TEAMSCALE_DEV_USER) { 'set' } else { 'not set' })"
"TEAMSCALE_DEV_ACCESSKEY: $(if (Test-Path Env:TEAMSCALE_DEV_ACCESSKEY) { 'set' } else { 'not set' })"
"TEAMSCALE_DEV_SERVERS: $(if (Test-Path Env:TEAMSCALE_DEV_SERVERS) { 'set' } else { 'not set' })"
"${argsFile}: $(if (Test-Path $argsFile) { 'present' } else { 'missing' })"
```

The braces in `${argsFile}` are required: without them PowerShell would read
the trailing colon as part of a drive-qualified variable name.

Then pick the invocation form:

- If `TEAMSCALE_DEV_SERVERS` is set, or both `TEAMSCALE_DEV_USER` and
  `TEAMSCALE_DEV_ACCESSKEY` are set, call `teamscale-dev` as the skill spells
  the command out. The environment already carries the credentials.

- Otherwise, if the args file is present, add it as a picocli at-file argument
  directly after the subcommand name. Naming it after the subcommand keeps it
  clear of the subcommand's own positional arguments.

  On Linux/macOS:

  ```bash
  teamscale-dev <subcommand> @"${HOME}/.teamscale-dev.args" <remaining arguments>
  ```

  On Windows:

  ```powershell
  teamscale-dev <subcommand> @"$env:USERPROFILE\.teamscale-dev.args" <remaining arguments>
  ```

Pass the at-file only when the environment variables are absent. Supplying
both sources risks a conflict for the same server URL, which `teamscale-dev`
rejects with an "inconsistent credentials" error.

Never `cat` or `Get-Content` the args file, never echo `$TEAMSCALE_DEV_USER`,
`$TEAMSCALE_DEV_ACCESSKEY` or `$TEAMSCALE_DEV_SERVERS` (or their
`$env:`-prefixed PowerShell equivalents), and never include any of these
values in output to the user.

If none of the sources is configured, stop and tell the user to run
`/teamscale:check-setup`, which walks through obtaining an access key and
configuring it.
