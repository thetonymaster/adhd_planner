# Task priority and ranked project hubs

* **Author:** Antonio Cabrera
* **Date:** 2026-11-12
* **Status:** Brainstorm, after three reviewer rounds. The six questions round 3 required are
  answered under "Key Decisions"; the brief is ready for a design draft. Reviewer file citations were relayed, not re-checked. No reviewer
  could run Obsidian, so every statement about Obsidian Bases is untested.

> This is the brainstorm record. The design that came out of it is
> [task-priority-ranked-hubs.md](../task-priority-ranked-hubs.md), which is the
> current source. Later review reversed some decisions listed here: the one-day
> size rule and numbered sibling slugs were cut, `p0` now ranks ahead of dated
> tasks, and overdue tasks respect capacity.

## Overview

Today a task note has a status (`parked`, `active`, `done`) and a link to its
project hub, and nothing that says which task comes first. A hub shows only task
names, so it cannot be used to plan, and `plan-week` / `plan-day` work out what
comes next on every run.

The concept has three parts.

1. **A task is one self-contained unit.** It is sized to go from start to done
   within one working day. `create-task` splits larger work into several sibling
   task notes. Parking a started task is the exception.
2. **Each task carries a rank.** Frontmatter gains `priority` (p0 to p5; a note
   without one is read as p3) and an optional `due` date, which is a hard limit
   when present.
3. **Hubs and planners read that rank.** Each hub shows its open tasks in rank
   order through an Obsidian Base view. The planners place whole tasks, not
   steps, from one ordered list of open tasks across projects and vaults. That
   list is computed on each run by a new planner tool; it is not a stored file.

The user is one person with ADHD who reads hubs in Obsidian and creates tasks
through `create-task`. Setting a priority has to take a few seconds.

## Analysis

### Measured in the user's vaults (2026-11-12)

* 3 vaults, 13 hubs with open tasks, 97 open task notes (89 parked, 8 active).
  The two largest hubs hold 21 and 24.
* All 97 have at least one open `## Next` step. 21 have at least one step with
  no time estimate.
* Sum of open step estimates per task: 60 tasks are 60 minutes or less, 23 are
  61 to 120, 11 are 121 to 240, 3 are over 240 (largest: 425 minutes, 7 steps).
  Totals are understated where estimates are missing.

### Findings from the first two rounds that still apply

1. **The planners schedule steps today, not tasks.** `plan-week` builds its
   backlog from open `## Next` items and their `(~N min)` estimates, and
   `plan_week.py` needs `minutes` per row, defaulting to 25. Planning per task
   reverses this: the tool needs a size per task, and a rule for a task whose
   steps have no estimate.
2. **`plan_week.py` does not know priority.** It sorts by deadline, then by
   size, picks the day with the most room, and sends a row whose deadline is
   before the first planned day to "Didn't fit this week". The file it hands to
   `plan-day` keeps only title and minutes. Dated-first then priority is close
   to the current sort, but priority, overdue handling and the hand-off all need
   tool changes.
3. **The ordered list has no existing home.** Planner tools know nothing about
   vaults and take a JSON list the model wrote. Plugins may not import each
   other's code. The planner must keep working with no vault. A new tool would
   be a fourth frontmatter reader in the repo and needs a written note-format
   contract with shared test cases.
4. **Several surfaces already order tasks differently** (task-list by start
   date, `/board` by title, `/project-tasks` by last edit, task-switch by
   recency). The rule should be simple enough to be a Base sort, so a hub and a
   plan agree inside a vault.
5. **Existing vaults get nothing without a migration.** Setup skips an existing
   vault and its update step only merges two fixed views. Editing an existing
   view's text triggers a whole-file replace prompt; adding new named views
   avoids that. The 13 real hubs keep their one-line Tasks section.
6. **An installed older copy of the planner tools ignores `priority` without
   any error.** The only staleness signal today is a missing file.
7. **A scheduled run writes the same plan files from the inbox**, so it can
   overwrite a plan made in an attended session. `plan-day` offers only active
   tasks today, so it would bypass the ordered list.
8. **A second priority vocabulary.** `capture-triage` already sorts into today /
   soon / eventually and four quadrants, and that judgment is lost at hand-off
   to `create-task`. The planner's existing field for a date limit is
   `deadline`.
9. **`create-task` already asks three things in one message** (goal, project,
   first action). Priority, due and splitting add to that.
10. **Status `done` is set by `task-finish` and also by dragging a card on the
    Board view.** The ordered list should follow the status value.

### Round 3 findings on per-task planning and the one-day rule

1. **A full-day task cannot be placed today.** `plan_week.py` places a row only
   if one day's remaining room holds it. Usable capacity is free time times
   0.75, about 360 minutes on a day with no meetings. Anything larger goes to
   "Didn't fit". Against 360 minutes at most 3 existing tasks break the one-day
   rule; against two hours, 14 do.
2. **Rank does not decide the day.** Placement picks the emptiest eligible day,
   and a task that does not fit is skipped while smaller, lower-ranked tasks
   still land. The concept has not said whether it wants skip or stop.
3. **There is no "one block" in `plan-day`.** `plan_day.py` slices a task into
   Pomodoros and silently drops a task of zero minutes. A missing estimate
   becomes 25 minutes in both tools; 21 tasks are affected.
4. **Four skills assume per-step planning** and need rewriting: `plan-week`,
   `plan-day`, `morning-startup`, `break-down-task`.
5. **`task-park` rewrites `## Next` to one to three actions**, so a size taken
   from the open steps changes every time a task is parked.
6. **Sibling order by descending priority does not work** (five of six
   reviewers). A `due` on a later sibling jumps it ahead; only p4 and p5 sit
   below the default; re-ranking one sibling reorders the chain; nothing marks
   notes as siblings. Two alternatives: siblings share one priority and get
   numbered slugs, with the slug as the last tie-break (no new field, but
   inserting in the middle needs a rename); or an `after: "[[slug]]"` link, the
   only option that enforces "B after A" in placement (about 20 lines in the
   placement code plus cycle and dangling-link checks).
7. **Two skills own "too big".** `create-task` sends splitting to
   `break-down-task`, which has its own 10 to 90 minute limit and writes steps,
   not notes. `task-start` also creates notes, with no size check or priority.
8. **The ordering rule is one sort key in Python** (`due` missing last, `due`,
   priority with missing as 3, `started`, slug) but probably not a plain Base
   sort: "missing means p3" needs a formula and where an empty `due` sorts is
   unknown. Untested.
9. **Dated-first is absolute as written.** A p5 due in three months beats an
   undated p0.
10. **"Parking is rare" clashes with the data model.** `parked` is the backlog
    status that `create-task` writes; 89 of 97 open notes have it. The rule must
    be worded as "pausing a started task is rare".
11. **Corrections.** A hub does not show task names: it shows one line pointing
    at the backlinks pane. `deadline` is not a hard limit for rows the user has
    pinned to a day.

### What can be reused

* The hub's Meetings section already embeds a Base block filtered to the current
  note; the same shape can show tasks.
* Existing frontmatter readers ignore unknown keys, so new keys are additive.
* `plan_week.py` already treats `deadline` as a hard placement limit.
* The board work left a propose-then-approve bulk edit pattern and setup
  migration code with backup and dry-run.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * `priority` and `due` are plain frontmatter on task notes and the only source
    of rank. A missing or invalid `priority` is read as p3 and never hides a
    task.
  * `create-task` produces tasks that fit one working day, splitting larger work
    into sibling notes, and sets priority (default p3) and `due` when a date is
    given, without adding more than one question.
  * One ordering rule, written once and tested: dated tasks first by date, then
    priority, then start date.
  * Each hub shows its open tasks with priority, due and status in that order.
  * The planners place whole tasks from one ordered cross-vault list built by a
    planner tool; overdue tasks and tasks without a usable size are reported,
    never dropped or given a guessed size.
  * Existing vaults get an update that backs up, can be dry-run, and prompts
    before replacing anything.
* **Out-of-Scope Non-Goals:**
  * Priority, due or scheduling on individual steps.
  * A cross-vault view inside Obsidian (Bases work per vault).
  * A stored or hand-edited list file; per-run JSON stays disposable.
  * Scores, decay, or automatic re-ranking without confirmation.
  * New statuses or changes to vault and task resolution.
  * Changing the order of `/board`, `/project-tasks`, task-switch and task-list.
  * Reminders, recurrence or calendar events from `due`.
  * Forcing every existing note to get an explicit priority.

## Key Decisions & Staging for Next Steps

Decided:

* Rank lives on task notes; the hub displays it.
* The scope stays whole: fields, `create-task`, hub views, migration, planner
  tool. No split into two specs.
* A task is self-contained and fits one working day; `create-task` splits what
  does not. Work that cannot be split is a marked exception. Pausing a started task is rare.
* `## Next` is the ordered steps inside a task. It tells the user or an agent
  what comes first; it is not what the planners schedule.
* Planning is per task. The planner reserves the task's whole remaining size.
* Scale is p0 to p5; default and missing both mean p3.
* `due`, when present, is a hard limit. A dated task beats an undated task of
  higher priority for the same capacity.
* Tasks fill a plan in rank order until capacity is full; no fixed cap.
* A task leaves the list when its status is `done`. A task with every step
  ticked stays listed until then.
* Existing notes are not bulk-ranked; they are p3 until touched. A ranking skill
  is optional.
* Assumed, not objected to: the list is built by a planner tool that is handed
  vault paths; scheduled runs do not read the vault.

Decided after round 3 (accepted by the author on 2026-11-12):

* One working day is the planner's usable capacity, about 360 minutes. A task
  larger than that must be split.
* Sibling tasks from one split share one priority and get numbered slugs
  (`<work>-1-<part>`, `<work>-2-<part>`). The slug is the last tie-break in the
  ordering rule. No new frontmatter field. Inserting a part in the middle means
  renaming the later ones.
* A `due` date outranks priority only when it falls inside the period being
  planned. Outside it, priority decides.
* A task whose open steps lack estimates, or whose steps are all ticked, is not
  placed. It appears in a "needs an estimate" or "no next step" list. No guessed
  size.
* When the next task in rank order does not fit, it is skipped and named in the
  output. Overdue tasks go on the first planned day even if that overfills it.
* `create-task` owns splitting work into notes. `break-down-task` keeps writing
  steps inside one note. `task-start` applies the same size check and the same
  priority default.

Ordering rule as it now stands: tasks with `due` inside the planned period, by
date; then priority (missing or invalid = p3); then `started`; then slug.

Left to the design draft, with proposed defaults: confirm p0 is highest and
write one line per level; how unsplittable work is marked; a stale tool fails
with a named message; a scheduled run does not overwrite an attended plan;
`plan-day` reads the same list; `due` maps to the planner's `deadline`; the
migration adds views and prompts before replacing a hub's Tasks section; an
Obsidian test of the Base sort with empty `due` values.
