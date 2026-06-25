---
name: fix-findings
description: Fetch findings from Teamscale for the given files and fix the findings. This loads data from the Teamscale server, so the files should be committed and pushed to Git.
argument-hint: "<file> [<file> ...]"
---

# Fix findings on specific files

Targeted clean-up of one or more files using Teamscale's existing analysis.

## Steps

1. **Reject if no files were given.** This skill requires at least one
   file argument. If the user invoked it without one, ask them which files
   to clean up and stop. If the argument is a folder, make sure that not too 
   many files are to be processed (ask for confirmation if more than 20), and 
   run this skill for each of the files in the folder.

2. **Fetch findings for each file:**

   ```bash
   ts-agent-helper findings list <file>
   ```

   Same rule as step 2: if `ts-agent-helper` exits non-zero, stop and
   surface its stderr verbatim. Do not guess findings.

3. **Triage and fix.**

To understand finding priorities and fixing strategies, read ../../shared/finding-priorities.md

To get additional information about findings (finding type descriptions) read ../../shared/finding-type-descriptions.md

For flagging findings, read ../../shared/finding-flagging.md

4. **Summarise.** Print the three buckets (fixed / tolerated / skipped) as
   described in the priorities snippet.
