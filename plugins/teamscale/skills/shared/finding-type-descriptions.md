## How to look up finding-type descriptions

If you encounter a finding for which you need more information, fetch a description and examples before deciding how
to fix it. Use the helper:

```
ts-agent-helper findings type-descriptors --scope <scope> <typeId> [<typeId> ...]
```

`ts-agent-helper` ships in the teamscale plugin's `bin/` directory. Some
hosts put that directory on the PATH of the shell they spawn, so the bare
name above resolves; others do not. If the shell reports that the command
is not found, locate the launcher in the teamscale plugin's `bin/`
directory and run it by its absolute path (`ts-agent-helper.cmd` on
Windows).

The `<scope>` is the finding's code-scope name (it is part of each finding
object returned by the API). 

Only fetch descriptions for types that actually appear in the current finding
set. Do not bulk-fetch the whole catalog — it is large.
