# Stage 6: Comprehension Test

* **Target:** `docs/designs/task-priority-ranked-hubs.md` (FeatureRange 1-543,
  DetailedRange 544-850)
* **Reviewer:** egm-comprehension, fresh context
* **Standard:** re-implementation-standard
* **Date:** 2026-11-12
* **Verdict:** Does not yet pass. A reader could not rebuild the feature from
  the text alone. 2 Blockers, 8 Major, 5 Nit. Statements about Obsidian Bases
  are untested and not judged.

## Blockers

### B1. The one-day limit has no formula (lines 58-59, 263-265)

"Usable capacity for a day with no meetings (about 360 minutes)" is never
computed. In `plan_week.py` it is (work window minus lunch) times `--load`
(default 0.75), with the windows read from `calendars.json`. The document names
none of these, so a reader must guess the formula, and whether "larger than one
day" means greater than or greater than or equal.

### B2. How `create-task` splits work is not specified (lines 122-124, 206-209, 339-341, 743-745)

The document gives the trigger and the slug shape `<work>-N-<part>`, but not:

* how steps are grouped into sibling tasks;
* how `<work>` and `<part>` are derived;
* what each sibling's Goal and title contain;
* what happens when the user declines the split;
* what a single step larger than one day does.

Slugs sort as strings, so `-10-` comes before `-2-`. No zero-padding or cap on
the number of parts is stated.

## Major

### M1. The ordering key leaves cases open (lines 217-223)

* The comment says "dated inside the period, or overdue" but gives no lower
  bound. State that a `due` before the start of the period ranks first.
* An empty or absent `started` has no defined position.
* The tie-break `<vault>:<slug>` makes the vault name outrank sibling order
  across vaults. Say whether that is intended.

### M2. The `## Next` reading rules are incomplete (lines 187-189)

* No exact estimate pattern (only `(~N min)`? hours? anywhere on the line?).
* Nested checkboxes and where the section ends are not covered.
* Whether a note with only the template placeholder is "no next step".
* `unreadable note` (line 292) is never defined and has no row in the table
  that the test plan says must be fully covered.

### M3. The `task_queue.py` output is under-defined (lines 260-297)

* No default for `--out`; only the diagram mentions `tools/out/queue-<from>.json`.
* The text summary format is missing.
* No success exit code; no behaviour for `from` after `to` or a duplicate vault
  name.
* `name` and `hub` have no stated source.
* `next` is not defined (the first open step?).
* `deadline` when `due` is empty: null, omitted or an empty string?
* Whether `not_placed` rows carry `minutes`, which pinning an oversized task
  needs.

### M4. `--keep-order` gaps (lines 305-314)

* "Eligible day" is undefined; in the code it means on or before the deadline.
* The wording of the overdue mark and of the priority shown in the plan.
* The document never says `week-tasks-<date>.json` is one file per day.
* `deadline` and `name` are absent on most rows; null or omitted is not stated.
* It is not said that `plan_week.py` ignores the queue's other keys.

### M5. Daily skills (lines 329-332, 696-705)

"The same ordered list" for the Top 3 is ambiguous between the week file and the
queue. The dates for a one-day period are not given, nor which day
`eod-shutdown` plans (tomorrow?). Whether these skills also check that
`task_queue.py` exists is not stated.

### M6. Unattended runs (lines 316-318, 689)

Nothing says how a skill knows a run is unattended. Lines 319-320 hold a broken
paragraph that joins two unrelated topics.

### M7. Installer (lines 384-392, 787-801)

* "The original one-line pointer" is not quoted, and the match rule (exact or
  tolerant of whitespace) is not given.
* Where the missing keys go in a customised `Templates/Task.md`.
* "Offer" per hub (line 390) conflicts with "a prompt per vault" (line 799).
* Behaviour under the existing `--yes` flag.
* `Templates/Project.md` is updated in the file list but is not one of the
  three steps in section 9.

### M8. The fallback is incomplete (lines 103-104, 556-557)

If the Obsidian test fails, only the hub goal is reworded. User journey 3, the
`Ranked` view and the `soon` formula depend on it too. Result (c), where an
empty `due` lands, has no stated consequence.

## Nit

* **N1 (line 26 and throughout):** `task-track`, `/board`, `/project-tasks`,
  "Board drag", `/done`, `vault-allow.py`, the `Now:` line, "registered vault",
  "hub" and "inbox" are used without a definition or link.
* **N2 (line 503):** `task-note` is listed as a writer of the new keys but is
  missing from section 7; it first appears at line 754.
* **N3 (lines 198, 746):** "has no marker" and "a Log line saying so" read as
  contradictory; the Log line has no wording.
* **N4 (line 380):** "a test pins as adjacent" does not name the test.
* **N5 (line 581):** `Health.md` does have a Tasks section; say it is changed.

## Checked and fine

The three links under Additional Resources resolve. The named skills, tools and
the `update-vaults` command exist.

## Untested (Obsidian Bases, not judged)

Formula syntax, multi-key sort, placement of an empty `due`,
`today() + "7 days"`, and `this.file` inside an embedded block.
