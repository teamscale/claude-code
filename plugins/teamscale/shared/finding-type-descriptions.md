## How to look up finding-type descriptions

If you encounter a finding for which you need more information, fetch a description and examples before deciding how
to fix it. Use the helper:

```bash
ts-agent-helper findings type-descriptors --scope <scope> <typeId> [<typeId> ...]
```

The `<scope>` is the finding's code-scope name (it is part of each finding
object returned by the API). 

Only fetch descriptions for types that actually appear in the current finding
set. Do not bulk-fetch the whole catalog — it is large.
