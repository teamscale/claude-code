# Teamscale Plugin for Claude Code

Skills that make Teamscale's quality information available to Claude Code.
Detect and fix findings, close test gaps on a pull request or for a ticket,
run pre-commit analysis on local changes, and select the tests impacted by
local changes.

## Setup

Run the setup skill once:

- `/teamscale:check-setup`: verifies Python 3.9+, the `teamscale-dev` CLI, the
  presence of `.teamscale.toml`, and that credentials are set in the
  environment.

The plugin requires Python 3.9+, the `teamscale-dev` CLI, and `git` on PATH.
The helper shells out to `git` to resolve the repository root and the current
branch, so the pull-request and local-change skills cannot work without it; on
Windows that means installing [Git for Windows](https://gitforwindows.org/).
What the plugin does not require is a POSIX shell: it runs the same way under
Claude Code's PowerShell tool, which is what a Windows host without Git for
Windows offers.

The plugin ships a `bin/ts-agent-helper` launcher that the skills invoke by
bare name (no path). Claude Code adds each plugin's `bin/` directory to the
`PATH` of its Bash tool, so the bare name resolves there. Copilot CLI adds
nothing to `PATH`, so the skills additionally tell the agent that the launcher
lives in the teamscale plugin's `bin/` directory and is to be run by absolute
path when the bare name is not found. `/teamscale:check-setup` checks this and
reports which of the two applied.

## Skills

The `Auto-invoke` column indicates whether Claude may trigger the skill on its
own. Skills marked `no` set `disable-model-invocation: true` and must be
invoked explicitly via the slash-command syntax shown.

| Skill                                       | Source               | Scope                                             | Auto-invoke |
|---------------------------------------------|----------------------|---------------------------------------------------|-------------|
| `/teamscale:check-setup`                    | Local environment    | Python, `teamscale-dev`, `.teamscale.toml`, creds | no          |
| `/teamscale:pr-fix-findings`                | Teamscale PR view    | open PR for current branch, else branch vs. base  | yes         |
| `/teamscale:pr-close-test-gaps`             | Teamscale PR view    | open PR for current branch, else branch vs. base  | yes         |
| `/teamscale:issue-close-test-gaps <ticket>` | Teamscale issue view | commits linked to the given ticket                | yes         |
| `/teamscale:fix-findings <files>`           | Server analysis      | listed files                                      | yes         |
| `/teamscale:local-fix-findings`             | Pre-commit analysis  | local uncommitted changes                         | yes         |
| `/teamscale:local-select-tests`             | Pre-commit analysis  | test suggestions for local uncommitted changes    | yes         |

The `pr-` prefix means the skill operates on the open pull request whose
source branch is the current Git branch. If no such PR exists, the helper
falls back to comparing the current branch against the repository's default
branch (`origin/HEAD`, then local `master`/`main`).
The `issue-` prefix means the skill takes a ticket number and operates on the
commits Teamscale has linked to that issue, so it also works in a repository
that does not contain the code under test (for example a separate
test-automation repository).
The `local-` prefix means the skill operates on uncommitted edits in the
working tree. The prefix-less `fix-findings` takes mandatory file arguments
and works on Teamscale's existing analysis of those files (with a coverage
gate that warns before cleaning up code with low coverage).
