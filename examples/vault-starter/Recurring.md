# Recurring

This file turns on week and month notes for this vault; the planner adds each rule's items to `Weekly/` and `Monthly/` notes.
Each rule is one line in the format shown in the block below; lines inside a fenced code block are ignored.
Copy an example out of the block (and give it a unique `#id/`) to start using it.

```text
- [ ] Weekly review (~30 min) — every: mon #id/weekly-review
- [ ] Pay rent — every: month 1 #id/rent
```

Rules: `mon`..`sun` (weekly), `month <N>`, `month last`, `month first-<mon..sun>` (monthly).
