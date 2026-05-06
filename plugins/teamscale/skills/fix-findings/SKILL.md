---
name: fix-findings
description: Fetch findings and coverage from Teamscale for the given files and fix the findings, after warning if coverage is low.
argument-hint: "<file> [<file> ...]"
---

# Fix findings on specific files

Targeted clean-up of one or more files using Teamscale's existing analysis.

## Steps

1. **Reject if no files were given.** This skill requires at least one
   file argument. If the user invoked it without one, ask them which files
   to clean up and stop.

2. **Coverage gate.** For each file, fetch coverage:

   ```bash
   ts-agent-helper coverage for-file <file>
   ```

   If `ts-agent-helper` exits with a non-zero status, stop the skill and
   surface its stderr verbatim to the user. Do not guess coverage, fall
   back to other tools, or retry — the user needs to see the real error
   (typically a setup, network, or configuration problem).

   If any file's coverage is low (no clear universal threshold — use your
   judgement; below ~50% line coverage is a strong signal), warn the user:

   > Coverage on `<file>` is low (X%). Cleaning up findings without
   > regression tests is risky — refactors may silently break behaviour.
   > Consider running `/teamscale:pr-close-test-gaps` first, or adding
   > characterisation tests by hand.

   Ask whether to continue anyway. Stop if the user declines.

3. **Fetch findings for each file:**

   ```bash
   ts-agent-helper findings list <file>
   ```

   Same rule as step 2: if `ts-agent-helper` exits non-zero, stop and
   surface its stderr verbatim. Do not guess findings.

4. **Triage and fix.**

To understand finding priorities and fixing strategies, read ../../shared/finding-priorities.md

To get additional information about findings (finding type descriptions) read ../../shared/finding-type-descriptions.md

For flagging findings, read ../../shared/finding-flagging.md

5. **Summarise.** Print the three buckets (fixed / tolerated / skipped) as
   described in the priorities snippet.
