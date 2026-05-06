---
name: local-fix-findings
description: Run pre-commit analysis on local uncommitted changes via Teamscale, then fix the resulting findings.
argument-hint: "[<path> ...]"
disable-model-invocation: true
---

# Fix findings on local uncommitted changes

Send the user's uncommitted working-tree edits to Teamscale for pre-commit
analysis, then fix the findings introduced by those edits.

## Steps

1. **Determine which paths to analyse.** Default to the repository root. 
   The user may also pass specific paths if they want to narrow the scope.

2. **Invoke pre-commit analysis** via the existing Teamscale MCP tool
   `mcp__plugin_teamscale_teamscale__teamscale-dev_pre-commit`. If a tool
   with that exact name is not available, use the `pre-commit` tool exposed 
   by the `teamscale` MCP server under whatever name your environment surfaces it. 
   Pass these arguments:

   - `paths`: the paths chosen in step 1
   - `uploadScope`: `ONLY_UNCOMMITTED` — we only want findings on changes
     that are not yet committed; pre-existing issues are out of scope
   - `onlyPreCommitFindings`: `true` — only report findings actually
     introduced by the local edits, not findings already present on the
     server side
   - `severity` and `categories`: leave unset (no extra filtering) unless 
     explicitly requested by the user.

   If the MCP tool returns an error, stop the skill and surface the error
   verbatim to the user. Do not guess findings, fall back to other tools,
   or retry — the user needs to see the real error (typically a setup,
   network, or configuration problem).

3. **Triage and fix the returned findings.**

To understand finding priorities and fixing strategies, read ../../shared/finding-priorities.md

To get additional information about findings (finding type descriptions) read ../../shared/finding-type-descriptions.md

Do not attempt to tolerate or flag findings.

4. **Summarise.** Print two buckets — fixed and skipped — as described in
   the priorities snippet. The "tolerated" bucket from the snippet does not
   apply here: this skill does not flag findings, so omit it.

5. **Suggest re-running** after the fixes so the user can confirm the
   introduced findings are gone before committing.
