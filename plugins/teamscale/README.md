# Teamscale Plugin for Claude Code

Skills and MCP configuration to make Teamscale's quality information
available to Claude Code. Detect and fix findings, close test gaps on a
pull request, and run pre-commit analysis on local changes.

## Setup

Run the setup skill once:

- `/teamscale:check-setup`: verifies Python 3.9+, the `teamscale-dev` CLI, the
  presence of `.teamscale.toml`, and that credentials are set in the
  environment.

The plugin ships a `bin/ts-agent-helper` launcher that the skills invoke by
bare name (no path). Claude Code adds each plugin's `bin/` directory to the
`PATH` of the shells it spawns, so this works out of the box.

## Skills

The `Auto-invoke` column indicates whether Claude may trigger the skill on its
own. Skills marked `no` set `disable-model-invocation: true` and must be
invoked explicitly via the slash-command syntax shown.

| Skill                                | Source                | Scope                                             | Auto-invoke |
|--------------------------------------|-----------------------|---------------------------------------------------|-------------|
| `/teamscale:check-setup`             | Local environment     | Python, `teamscale-dev`, `.teamscale.toml`, creds | no          |
| `/teamscale:pr-fix-findings`         | Teamscale PR view     | open PR for current branch, else branch vs. base  | no          |
| `/teamscale:pr-close-test-gaps`      | Teamscale PR view     | open PR for current branch, else branch vs. base  | no          |
| `/teamscale:fix-findings <files>`    | Server analysis       | listed files                                      | yes         |
| `/teamscale:local-fix-findings`      | Pre-commit analysis   | local uncommitted changes                         | no          |

The `pr-` prefix means the skill operates on the open pull request whose
source branch is the current Git branch. If no such PR exists, the helper
falls back to comparing the current branch against the repository's default
branch (`origin/HEAD`, then local `master`/`main`).
The `local-` prefix means the skill operates on uncommitted edits in the
working tree. The prefix-less `fix-findings` takes mandatory file arguments
and works on Teamscale's existing analysis of those files (with a coverage
gate that warns before cleaning up code with low coverage).
