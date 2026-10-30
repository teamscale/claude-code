---
name: local-select-tests
description: Select the existing tests that are most impacted by local code changes. Runs pre-commit analysis on the uncommitted working-tree edits, then asks Teamscale which tests are impacted (change-based test suggestion). This works for local uncommitted changes.
argument-hint: "[<path> ...]"
---

# Select existing impacted tests for local uncommitted changes

Send the user's uncommitted working-tree edits to Teamscale and ask which
of the existing tests are most impacted by those changes, so the user can
run a focused subset instead of the whole suite. See Teamscale's
documentation on
[change-based test suggestions](https://docs.teamscale.com/reference/ui/test-suggestions/#change-based-test-suggestions)
for background.

## Steps

1. **Determine which paths to analyze.** Default to the repository root.
   The user may also pass specific paths if they want to narrow the scope.

2. **Invoke pre-commit analysis:**

   ```
   ts-agent-helper pre-commit --only-pre-commit-findings <paths>
   ```

   If the shell reports that the command is not found, locate the launcher
   in the teamscale plugin's `bin/` directory and run it by its absolute
   path, as in step 1. Do the same in step 4.

   - By default, the command uploads only the files with uncommitted
     changes.
   - `--only-pre-commit-findings` reports only findings actually introduced by
     the local edits, not findings already present on the server side.
   - `<paths>` are the paths chosen in step 2.

   This uploads the local changes to a pre-commit branch on the Teamscale
   server, which is what makes the impacted-test lookup in the next step
   possible. The command waits for the analysis, which can take up to three
   minutes. The findings it prints are not of interest here, so there is no
   need to report them to the user.

   If the command exits with a non-zero status, stop the skill and surface its
   output verbatim to the user. Do not fall back to other tools or retry — the
   user needs to see the real error (typically a setup, network, or
   configuration problem).

3. **Fetch the impacted tests:**

   ```
   ts-agent-helper impacted-tests --on-pre-commit-branch --max-count 50 <path>
   ```

   - `--on-pre-commit-branch` looks at the pre-commit branch created by step 3
     (the local changes), not at the currently checked-out branch.
   - `--max-count 50` keeps the list reviewable. Raise it if the user asks for
     more.
   - `<path>` is a single path; use the first of the paths chosen in step 2.

   The command picks the selection strategy itself: it uses test-wise coverage
   when the Teamscale server has any, and falls back to source-code similarity
   when it has none. Pass `--strategy COVERAGE` or `--strategy SIMILARITY` only
   when the user asks for a specific one. The similarity strategy requires a
   server version of at least 2026.5.

   On stdout the command prints the uniform path of one impacted test per line,
   sorted by likely impact. Messages about the strategy go to stderr.

   If the command exits with a non-zero status, stop the skill and surface its
   output verbatim to the user. Do not guess tests or retry.

4. **Report the impacted tests** to the user, in the order returned (the
   results are sorted by likely impact). If the list is empty, say so —
   it means Teamscale did not find tests impacted by the local changes.
   Do not run the tests unless requested by the user; just present the 
   suggestion so the user can decide what to execute.
