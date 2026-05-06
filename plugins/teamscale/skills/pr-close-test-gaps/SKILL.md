---
name: pr-close-test-gaps
description: Fetch test-gap information for the current branch (PR-scoped if a merge request exists, branch-vs-base otherwise) and generate tests to close the gaps.
disable-model-invocation: true
---

# Close test gaps on the current branch

Generate tests for methods introduced or modified on the current branch
that are not yet covered.

## Steps

1. **Fetch test-gap information for the current branch:**

   ```bash
   ts-agent-helper test-gaps for-pr
   ```

   The helper prints a one-paragraph resolution banner on stderr telling
   you which mode it resolved to:

   - `resolved as merge request <id>` — an open merge request was found
     for the current branch; test gaps are scoped to that MR.
   - `no merge request for branch '<name>'; comparing against base` —
     no MR matched; the current branch is compared against the
     repository's default branch (origin/HEAD, falling back to
     `master`/`main`).

   Relay the resolved mode to the user in your first response so they
   know which scope is being acted on.

   If `ts-agent-helper` exits with a non-zero status, stop the skill and
   surface its stderr verbatim to the user. Do not guess test gaps, fall
   back to other tools, or retry — the user needs to see the real error
   (typically a setup, network, or configuration problem).

   On stdout the helper returns CSV data with the following columns:

   - Uniform Path: The path containing the untested method
   - Method Name: The name of the untested method
   - Method Region Lines: The lines for the method as `[start - end]`
   - Test State: Whether this is an untested addition (new method) or untested change (modified method) 

2. **Decide which gaps to close.** Each row in the CSV is a candidate
   gap. Pick the ones most worth covering.
   We give no prior ordering; use your judgement based on the change
   content (e.g. new public APIs, branchy logic, error paths).

3. **Detect the test framework and conventions** by reading existing
   test files in the repo. Do not assume a framework — match what the
   project already uses (unit vs integration vs other; folder layout;
   naming). If the repo's `CLAUDE.md` or test directory makes the
   convention obvious, follow it.

4. **Generate tests** for the chosen gaps. Run them after generating to
   confirm they pass.

5. **Summarise.** Report which gaps were closed (with test file + test
   name) and which were skipped (with a one-sentence reason).
