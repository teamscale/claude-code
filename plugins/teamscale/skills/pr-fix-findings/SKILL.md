---
name: pr-fix-findings
description: Fetch findings introduced on the current branch from Teamscale (PR-scoped if a merge request exists, branch-vs-base otherwise) and fix them.
disable-model-invocation: true
---

# Fix findings on the current branch

Run a clean-up of the findings introduced on the current Git branch. Fetch
them from Teamscale, fix them, propose tolerations for false positives, and
report a summary at the end.

## Steps

1. **Fetch newly added findings for the current branch:**

   ```bash
   ts-agent-helper findings for-pr
   ```

   The helper prints a one-paragraph resolution banner on stderr telling
   you which mode it resolved to:

   - `resolved as merge request <id>` — an open merge request was found
     for the current branch; findings are scoped to that MR.
   - `no merge request for branch '<name>'; comparing against base` —
     no MR matched; findings are computed by comparing the current
     branch against the repository's default branch (origin/HEAD,
     falling back to `master`/`main`).

   Relay the resolved mode to the user in your first response so they
   know which scope is being acted on.

   On stdout the helper returns a JSON array of the findings newly added
   on the current branch.

   If `ts-agent-helper` exits with a non-zero status, stop the skill and
   surface its stderr verbatim to the user. Do not guess findings, fall
   back to other tools, or retry — the user needs to see the real error
   (typically a setup, network, or configuration problem).

2. **Triage and fix.**

To understand finding priorities and fixing strategies, read ../../shared/finding-priorities.md

To get additional information about findings (finding type descriptions) read ../../shared/finding-type-descriptions.md

For flagging findings, read ../../shared/finding-flagging.md

3. **Summarise.** At the end, print the three buckets (fixed / tolerated /
   skipped) as described in the priorities snippet.
