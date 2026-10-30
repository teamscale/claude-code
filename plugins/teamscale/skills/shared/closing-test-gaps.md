## How to close test gaps

The test-gap CSV lists methods that were changed but are not covered by a
test. When there are none, the helper prints a plain-text message instead of
a CSV; relay that message and stop, rather than looking for something to
test. The skill that invoked this document states which messages its helper
command can produce and what each one means.

Otherwise, work through the rows as follows.

1. **Decide which gaps to close.** Each row in the CSV is a candidate
   gap. Pick the ones most worth covering.
   We give no prior ordering; use your judgement based on the change
   content (e.g. new public APIs, branchy logic, error paths).

2. **Detect the test framework and conventions** by reading existing
   test files in the repo. Do not assume a framework — match what the
   project already uses (unit vs integration vs other; folder layout;
   naming). If the repo's `CLAUDE.md` or test directory makes the
   convention obvious, follow it.

3. **Generate tests** for the chosen gaps. Run them after generating to
   confirm they pass.

4. **Summarise.** Report which gaps were closed (with test file + test
   name) and which were skipped (with a one-sentence reason).

Note: Test gaps are computed on the Teamscale server based on coverage from the CI pipeline, once the new tests have been 
pushed to Git. Hence, fetching the test-gap information right after creating the tests does not work. Instead, instruct 
the user to check the test-gap information once the CI pipeline has finished. 
