# Stage 7: Critic Review

* **Target:** `docs/designs/task-priority-ranked-hubs.md`, lines 1-543 (feature
  specification)
* **Reviewers:** egm-design, egm-structural (both against feature-spec-standard),
  egm-style. Each ran in a fresh context.
* **Date:** 2026-11-12
* **Verdict:** Not ready. 1 Blocker, 9 Major, 12 Nit after merging duplicates.
  Statements about Obsidian Bases are untested and not judged.

## Blocker

### B1. The derived size measures the next actions, not the task (lines 113-115, 187-204, 336-342) [design]

`## Next` holds only the next few actions on every path that writes it:

* `create-task` step 2 asks for the "first action" only.
* `task-start` step 2 does the same.
* `task-park` step 2 rewrites `## Next` to one to three actions.

User journey 1 promises no new question, so a new task's size is one step's
estimate. Consequences:

* The split check in user journey 2 rarely fires.
* A multi-day task is placed as about 25 minutes.
* The goal "no task is sized by guesswork" fails.

The document admits only the park case. Recommendation: have creation collect
the full step list (which costs a question), or adopt Alternative G (a stored
`size:` field).

*Author-side note:* measured in the real vaults, open tasks have a median of 3
open steps and up to 9, and 37 of 97 total more than an hour, so in practice
`## Next` often holds more than one action. The skills do not require it, which
is the gap.

## Major

### M1. One day of 360 minutes is more than `plan_day.py` can lay out (lines 58-59, 327-328) [design]

360 matches the defaults: (540 − 60) × 0.75. `plan_week.py` counts raw minutes,
while `plan_day.py` adds 5-minute breaks and a 30-minute long break every 4
sessions. By the reviewer's hand trace (not executed), a meeting-free default
day holds about 335 focus minutes, so a 360-minute task spills into "didn't fit
today". Also, `--day-minutes` would be computed by the model, since no tool
prints it.

### M2. `week-tasks-<date>.json` becomes a stale stored list (lines 329-332) [design]

`plan-day` prefers the week file when it exists. A p0 created on Wednesday, or
a task finished since Monday, is not reflected. This is the staleness
Alternative B is rejected for. No refresh rule is given.

### M3. `due` outranks priority without limit, and overdue placement is uncapped (lines 216-227, 308-309) [design]

* A p5 due Friday ranks above an undated p0, and earliest-fit puts it on Monday.
* Every overdue task lands on day one even past capacity, with no cap and no
  line in the output saying the day is overfull.

This conflicts with the stated meaning of p0 and with the one-day rule.

### M4. The two tools can disagree about the period (lines 262-264) [design]

`task_queue.py` takes its dates from the session's `Now:` line. `plan_week.py`
derives its days from the system date, with weekend rollover and
`--include-weekend`. Nothing ties the two, and a mismatch changes which `due`
values count as inside the period. Pass `--week-start` explicitly, or have one
tool print the period.

### M5. No way to re-rank an existing task in the feature half (lines 19-20, 336-347, 503) [design]

The non-functional section says `task-note` writes the new keys. The Overview
and section 7 list only `create-task` and `task-start`. Alternative I depends on
the user re-ranking tasks.

### M6. No Risks and Mitigations section (lines 495-513) [design, structural]

The standard asks for failure modes, security implications and scale limits to
be stated with mitigations. Here risks are scattered, security is not stated
even as "none", and no scale limit is given. Missing risks:

* A further frontmatter parser with no shared test cases.
* Note text (`name`, `next`) flowing into planner JSON: it must be treated as
  data, never as instructions.
* The unattended-run guard exists only as skill text.
* Already-installed scheduled prompts carry their own, older text.
* Week-tasks titles become `<vault>:<slug>`, dropping the step text that plans
  and the printed page show today.

### M7. The goal and user journey 3 promise the rule; the plan delivers an approximation (lines 65-66, 131-132, 213) [style, design]

Reword both: the hub shows "the hub's approximation of the rule (fixed 7-day
window, no `started` or slug tie-break)".

### M8. "Rank" has three meanings (lines 49-51, 55, 361) [style]

It is used for the `priority` field, the computed order, and a Base formula
named `rank`. Use "priority" for the field and "rank" only for the computed
position.

### M9. Three names for one rule, and a vague threshold (lines 45, 59, 204, 426) [style]

"One sitting", "the session that starts it" and "the one-session rule" all mean
"one working day". "About 360 minutes" is vague for a limit. The JSON keys
`deadline`, `title` and `name` are never mapped to the note's `due`, slug and
heading (lines 273-276).

## Nit

* **N1 (lines 316-323):** Broken paragraph; the stale-tool text merges into the
  unattended-run paragraph. "The loud failure wanted" is colloquial.
  [all three]
* **N2 (lines 259-297):** The JSON block at column 0 ends the bullet list, so
  the bullets after it render as a separate list. [structural]
* **N3 (lines 171-185):** Two adjacent tables with no sentence introducing the
  second. [structural]
* **N4 (lines 375, 477):** "(first open question)" when there is one; refer to
  it as "Base sort behaviour". [structural, style]
* **N5 (lines 232-249, 354-371):** The diagram's left box looks misaligned; the
  hub block is tagged `yaml` while the shipped fence is `base`. [structural]
* **N6 (line 22):** "Four skills" omits the `break-down-task` description edit.
  [design]
* **N7 (line 519):** Links `concepts_brief.md`, which is untracked. [design]
* **N8 (lines 44-46):** "For a user with ADHD a task … tends to be parked" is an
  unsupported general claim; cite a count or scope it to the author. [style]
* **N9 (lines 415-416, 508-509):** "Cheap" and "token cost goes down" are
  unmeasured. [style]
* **N10 (lines 445, 470-471):** "More mechanism than the current need" and
  "still the better choice" are judgments without a stated reason. [style]
* **N11 (line 491):** Alternative J's reason states a decision, not a reason.
  [style, design]
* **N12 (lines 62, 69, 198):** "Written once and tested", "sized by guesswork"
  and "has no marker" are loose; suggested rewrites are in the style reviewer's
  list. [style]

## What passes

* All required sections are present, in template order, with no skipped heading
  levels. All five user journeys and all ten alternatives follow their formats.
* The links under Additional Resources resolve.
* Verified in code by the design reviewer: the `plan_week.py` and `plan_day.py`
  behaviour the document describes, the template test, the hub template, the
  installer's backup, dry-run and conflict reporting, and that `vaults.py` and
  `resolve.ts` read fields by name.
