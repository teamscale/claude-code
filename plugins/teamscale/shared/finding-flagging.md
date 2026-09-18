## Flagging (or tolerating) findings

Once the user has agreed that a finding should be marked, flag it on the
server with:

```
ts-agent-helper findings flag --type <FALSE_POSITIVE|TOLERATION> --rationale "<why>" <FINDING_ID> [<FINDING_ID> ...]
```

`ts-agent-helper` ships in the teamscale plugin's `bin/` directory. Some
hosts put that directory on the PATH of the shell they spawn, so the bare
name above resolves; others do not. If the shell reports that the command
is not found, locate the launcher in the teamscale plugin's `bin/`
directory and run it by its absolute path (`ts-agent-helper.cmd` on
Windows).

Use `--type FALSE_POSITIVE` when the analyzer is wrong (the rule does not
actually apply to this code). Use `--type TOLERATION` when the rule applies
but the violation is acceptable in context (e.g. a threshold only marginally
exceeded, or a documented exception). Always pass `--rationale` with a
one-sentence reason so future reviewers can understand the decision.

Do not flag findings without explicit user agreement — propose them in the
summary and flag only after the user confirms.
