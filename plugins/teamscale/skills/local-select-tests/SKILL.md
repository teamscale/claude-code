---
name: local-select-tests
description: Select the tests most impacted by local code changes. Runs pre-commit analysis on the uncommitted working-tree edits, then asks Teamscale which tests are impacted (change-based test suggestion). This works for local uncommitted changes.
argument-hint: "[<path> ...]"
---

# Select impacted tests for local uncommitted changes

Send the user's uncommitted working-tree edits to Teamscale and ask which
tests are most impacted by those changes, so the user can run a focused
subset instead of the whole suite. See Teamscale's documentation on
[change-based test suggestions](https://docs.teamscale.com/reference/ui/test-suggestions/#change-based-test-suggestions)
for background.

## Steps

1. **Check that `teamscale-dev` supports `fetch-impacted-tests`.** This
   sub-command is only available in very recent versions. Verify it with:

   ```bash
   teamscale-dev -h | grep fetch-impacted-tests
   ```

   If the command prints nothing (no match), the installed `teamscale-dev`
   is too old. Stop the skill and tell the user to upgrade to at least
   **2026.5.0-beta**, pointing them to the installation guide at
   https://docs.teamscale.com/howto/integrating-with-your-ide/other-ides/#installing-teamscale-dev
   Do not continue to the analysis steps.

2. **Determine which paths to analyze.** Default to the repository root.
   The user may also pass specific paths if they want to narrow the scope.

3. **Invoke pre-commit analysis** via the existing Teamscale MCP tool
   `mcp__plugin_teamscale_teamscale__teamscale-dev_pre-commit`. If a tool
   with that exact name is not available, use the `pre-commit` tool exposed
   by the `teamscale` MCP server under whatever name your environment
   surfaces it. Pass these arguments:

   - `paths`: the paths chosen in step 2
   - `uploadScope`: `ONLY_UNCOMMITTED` — we only want findings on changes
     that are not yet committed; pre-existing issues are out of scope
   - `onlyPreCommitFindings`: `true` — only report findings actually
     introduced by the local edits, not findings already present on the
     server side
   - `severity` and `categories`: leave unset (no extra filtering) unless
     explicitly requested by the user.

   The pre-commit step uploads the local changes to a pre-commit branch on
   the Teamscale server. This is what makes the impacted-test lookup in the
   next step possible. We are not actually interested in the findings here, so
   there is no need to report them to the user.

   If the MCP tool returns an error, stop the skill and surface the error
   verbatim to the user. Do not guess findings, fall back to other tools,
   or retry — the user needs to see the real error (typically a setup,
   network, or configuration problem).

4. **Fetch the impacted tests** via the Teamscale MCP tool
   `mcp__plugin_teamscale_teamscale__teamscale-dev_fetch-impacted-tests`. If
   a tool with that exact name is not available, use the
   `fetch-impacted-tests` tool exposed by the `teamscale` MCP server under
   whatever name your environment surfaces it. Pass these arguments:

   - `path`: the same paths chosen in step 2
   - `onPreCommitBranch`: `true` — look at the pre-commit branch created by
     step 3 (the local changes), not the currently checked-out branch
   - `strategy`: `COVERAGE`. If this does not return results, try `SIMILARITY`,
     but beware that this requires a server version of at least 2026.5.0.

   If the MCP tool returns an error, stop the skill and surface the error
   verbatim to the user. Do not guess tests or retry.

5. **Report the impacted tests** to the user, in the order returned (the
   results are sorted by likely impact). If the list is empty, say so —
   it means Teamscale did not find tests impacted by the local changes.
   Do not run the tests unless requested by the user; just present the 
   suggestion so the user can decide what to execute.
