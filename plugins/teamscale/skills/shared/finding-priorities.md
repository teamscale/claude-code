## How to triage findings

Teamscale assigns each finding a colored severity:

- **Red** findings are serious (e.g. likely bugs, security issues, blocking
  quality violations). Treat these as must-fix unless the user marks them as
  false positives.
- **Yellow** findings are warnings (e.g. style, maintainability, suspicious
  patterns). Fix when straightforward; otherwise propose a toleration.

Static analysis can produce **false positives**. If after reading the code you
believe a finding is wrong, do not silently skip it: flag it as a candidate
for toleration and explain why. The user can then decide whether to tolerate
it (mark as false positive) in Teamscale.

### Handling of specific types of findings

Certain findings are based on thresholds (e.g. long files, long methods). For those, 
a small deviation can often be tolerated (e.g. length 32 instead of 30). However, the
decision depends on the complexity of the method. If the method looks complex or can 
easily be decomposed into smaller self-contained methods, then refactoring (and fixing 
the finding) should be preferred. Similarly, redundancy in the code (code clones) don't
have to be resolved at all costs. If a refactoring would introduce methods with many 
parameters or the similarity is purely structural, then a clone finding nca be ignored.

### Summary

When fixing:

1. Always handle red findings before yellow.
2. Group fixes that touch the same file or the same root cause.
3. Be conservative: if a fix risks changing behaviour, prefer a smaller,
   surgical change and leave a comment explaining why the finding's pattern
   is necessary here (and propose toleration instead).

When summarising at the end, report three buckets:

- **Fixed**: short list of finding IDs and what was changed.
- **Tolerated (proposed false positives)**: finding ID + one-sentence reason.
- **Skipped**: finding ID + reason (e.g. out of scope, needs design decision).
