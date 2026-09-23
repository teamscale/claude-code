---
name: issue-close-test-gaps
description: Fetch test-gap information for a ticket (issue) from Teamscale and generate tests to close the gaps. Takes a ticket number and does not use Git, so it also works in a repository that does not contain the code under test.
argument-hint: "<ticket-number>"
---

# Close test gaps for a ticket

Generate tests for the methods that were introduced or modified in the
context of a ticket and are not yet covered.

## Steps

1. **Fetch test-gap information for the ticket:**

   The ticket number is a mandatory argument, e.g. `TS-1234`. If the user
   did not supply one, ask for it. Do not derive it from the current Git
   branch, the working tree, the commit history, or any other source: this
   skill exists for repositories that do not contain the code under test,
   so anything Git knows about locally is unrelated to the ticket.

   ```bash
   ts-agent-helper test-gaps for-issue <TICKET>
   ```

   `ts-agent-helper` ships in the teamscale plugin's `bin/` directory. Some
   hosts put that directory on the PATH of the shell they spawn, so the bare
   name above resolves; others do not. If the shell reports that the command
   is not found, locate the launcher in the teamscale plugin's `bin/`
   directory and run it by its absolute path (`ts-agent-helper.cmd` on
   Windows).

   By default the query covers the ticket **and its child issues**, because
   the implementation work for a ticket is often committed against its
   sub-tasks. If the user asks to look at the given ticket alone, add the
   `--exclude-child-issues` flag:

   ```bash
   ts-agent-helper test-gaps for-issue <TICKET> --exclude-child-issues
   ```

   Teamscale reads coverage from the branch the ticket's commits are on. If
   the user names a branch they want the gaps for, pass it instead:

   ```bash
   ts-agent-helper test-gaps for-issue <TICKET> --branch <BRANCH>
   ```

   The helper prints a two-line resolution banner on stderr naming the
   ticket it queried, whether child issues were included, and which branch
   was used:

   ```
   ts-agent-helper: resolved as issue <TICKET>
     include-child-issues=true branch=auto-selected
   ```

   Relay that scope to the user in your first response so they know which
   scope is being acted on.

   If `ts-agent-helper` exits with a non-zero status, stop the skill and
   surface its stderr verbatim to the user. Do not guess test gaps, fall
   back to other tools, or retry — the user needs to see the real error
   (typically a setup, network, or configuration problem). Two errors are
   specific to this skill:

   - `HTTP 404` — the configured Teamscale project does not know the
     ticket. Either the ticket number is wrong, or no commit in the project
     references it, or the project has no issue connector for that tracker.
   - `HTTP 409` — the project has several issue connectors and the ticket
     number exists in more than one of them. The error names the connectors
     it found. Retry with the connector prepended, `<connector>|<TICKET>`
     (e.g. `issues|133742`), which the helper passes through unchanged.

   On stdout the helper returns CSV data with the following columns:

   - Uniform Path: The path containing the untested method
   - Method Name: The name of the untested method
   - Method Region Lines: The lines for the method as `[start - end]`
   - Test State: Whether this is an untested addition (new method) or untested change (modified method) 

   When there is no CSV to show, the helper prints one of two plain-text
   messages on stdout and still exits successfully, so the non-zero-exit rule
   above stays reserved for genuine failures. The two mean different things
   and must be handled differently:

   - `No test gaps: all N methods changed for this ticket are covered by
     tests.` — the ticket changed code and all of it is tested. Report that
     to the user and stop. Do not go looking for something else to test.

   - `No changed code found for this ticket.`, followed by a list of likely
     causes — Teamscale attributes no changed method to the ticket at all, so
     there was nothing to assess. Relay the message including its cause list
     verbatim and stop. Do not fall back to Git, the working tree, or the
     ticket description to guess what the ticket changed, and do not re-run
     the helper against a different branch on your own. You may suggest the
     listed causes to the user as next steps.

2. **Close the gaps.**

To understand how to select gaps, write the tests and report the result, read ../../shared/closing-test-gaps.md
