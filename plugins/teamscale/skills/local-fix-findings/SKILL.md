---
name: local-fix-findings
description: Run pre-commit analysis on local uncommitted changes via Teamscale, then fix the resulting findings. This works for local uncommitted changes.
argument-hint: "[<path> ...]"
---

# Fix findings on local uncommitted changes

Send the user's uncommitted working-tree edits to Teamscale for pre-commit
analysis, then fix the findings introduced by those edits.

## Steps

1. **Determine which paths to analyse.** Default to the repository root. 
   The user may also pass specific paths if they want to narrow the scope.

2. **Invoke pre-commit analysis** by running the `teamscale-dev` CLI:

   ```
   teamscale-dev pre-commit --only-uncommitted-changes --only-pre-commit-findings <paths>
   ```

   - `--only-uncommitted-changes` uploads only the files with uncommitted
     changes; pre-existing issues are out of scope.
   - `--only-pre-commit-findings` reports only findings actually introduced by
     the local edits, not findings already present on the server side.
   - `<paths>` are the paths chosen in step 1.
   - Add `--severity` or `--category` only when the user explicitly asks for
     that filtering.

   Before running the command, read ../../shared/teamscale-dev-credentials.md
   and follow it to determine how credentials reach `teamscale-dev`.

   On stdout the command prints one line per finding in the GCC diagnostics
   format:

   ```
   <file>:<line>:<column>: <error|warning>: <message>
   ```

   `error` marks a red finding, `warning` a yellow one. A line tagged `note`
   belongs to the finding printed above it and marks a secondary location of
   that same finding.

   If the command exits with a non-zero status, stop the skill and surface its
   output verbatim to the user. Do not guess findings, fall back to other
   tools, or retry — the user needs to see the real error (typically a setup,
   network, or configuration problem).

2a. If the user requests to fix findings on the latest commit (that was not yet pushed), modify the command as follows:

   - `<paths>` must be the list of files from the latest commit, which can be retrieved via `git diff-tree --no-commit-id --name-only -r HEAD`
   - replace `--only-uncommitted-changes` with `--no-change-detection`

3. **Triage and fix the returned findings.**

To understand finding priorities and fixing strategies, read ../../shared/finding-priorities.md

To get additional information about findings (finding type descriptions) read ../../shared/finding-type-descriptions.md

Do not attempt to tolerate or flag findings.

4. **Summarise.** Print two buckets — fixed and skipped — as described in
   the priorities snippet. The "tolerated" bucket from the snippet does not
   apply here: this skill does not flag findings, so omit it.

5. **Suggest re-running** after the fixes so the user can confirm the
   introduced findings are gone before committing.
