# Recurring

This file turns on week and month notes for this vault; the planner adds each rule's items to `Weekly/` and `Monthly/` notes.
Each rule is one line in the format shown in the block below, its rule one of `mon`..`sun`, `month <N>`, `month last` or `month first-<mon..sun>`.
Lines inside a fenced code block are ignored: copy an example out of the block (and give it a unique `#id/`) to start using it.

```text
- [ ] Weekly review (~30 min) — every: mon #id/weekly-review
- [ ] Pay rent — every: month 1 #id/rent
```
