# Task priority and ranked project hubs

*   **Author:** Antonio Cabrera
*   **Status:** In Review (all five review stages run; revised after each)
*   **Date:** 2026-11-12

--------------------------------------------------------------------------------

## Overview

Task notes in the vault gain two optional frontmatter fields, `priority` and
`due`. With those in place, a project hub can list its open tasks in the order
they should be done, and `plan-week` / `plan-day` can place tasks from one
ordered list that covers every project and every registered vault.

The change touches two plugins, the starter vault and the installer:

*   `tasks`: `create-task` and `task-start` write the new fields; `task-note`
    can change them on an existing task.
*   `planner`: a new tool, `task_queue.py`, builds the ordered list;
    `plan_week.py` gains a mode that places tasks in that order; the four
    planning skills (`plan-week`, `plan-day`, `morning-startup`, `eod-shutdown`)
    use it.
*   `examples/vault-starter` and `setup`: the Task and Project templates, and an
    update path for vaults that already exist.

`task-track`, the Claude Code plugin that provides the `/board` and
`/project-tasks` panes, is not changed.

Terms used below:

*   **Hub**: a project or area note in `Projects/` or `Areas/`. A task note
    points at its hub with `up:`.
*   **Registered vault**: a vault listed in `vaults.json`, or the single vault
    the plugins resolve when that file is absent.
*   **Priority**: the value of the `priority` field. **Rank**: a task's position
    in the ordered list, computed from priority, due date and start date.
*   **Next work**: the open steps under a task's `## Next` heading. Their
    estimates add up to the minutes the planner reserves for the task.
*   **Unattended run**: a scheduled firing of a planner skill. The skills
    already detect this and skip their vault section.

## The Problem

A task note today records a status (`parked`, `active`, `done`) and a link to
its hub. Nothing records which task matters more or which has a date limit.

*   **A hub cannot be used to plan.** Its Tasks section is one line that points
    at the backlinks pane. Reading a hub does not tell the user what is open,
    how urgent it is, or what to do first.
*   **The planners rebuild the order on every run.** `plan-week` collects open
    `## Next` steps from task notes and the model decides what to include and
    estimates any step that has no time. Two runs on the same vault can produce
    different weeks.
*   **The backlog is flat.** Measured on 2026-11-12 in the author's vaults: 97
    open task notes in 3 vaults and 13 hubs, 89 of them `parked`. The two
    largest hubs hold 21 and 24 open tasks with nothing to tell them apart.
*   **Steps are scheduled one by one.** Each open step is its own planner row,
    so one task's steps can land on different days, in any order.

The proposed solution: make the task the planner's row, give each task a
priority and an optional due date in its own note, and have the hub view and
the planners order tasks by one stated rule.

## Goals

*   A task note holds its own priority and due date. `priority` takes `p0` to
    `p5`, with `p0` the highest; a note with no `priority`, or an invalid one,
    is read as `p3` and is never hidden. `due` is an optional date and a hard
    limit when present.
*   The ordering rule is implemented in one function and unit-tested: `p0`
    tasks; then tasks whose `due` falls on or before the end of the planning
    window, by date and then priority; then the rest by priority; ties by
    `started`, then by `<vault>:<slug>`.
*   Each hub shows its open tasks with priority, due date and status inside
    Obsidian, ordered by the hub's approximation of that rule (a fixed 7-day
    window, and no `started` or slug tie-break).
*   `plan-week` and `plan-day` place one row per task from the ordered list. Two
    runs on an unchanged vault give the same order.
*   No task is dropped silently or given an assumed duration. A task with a step
    that has no estimate, a task with no open step, a task that did not fit, and
    an overdue task are each named in the planner's output.
*   Setting priority at creation adds no question to `create-task` when the user
    accepts the default.
*   The user can change the priority or due date of an existing task without
    opening Obsidian.
*   Existing vaults can adopt the change through an update that backs up, can be
    dry-run, and asks before it replaces anything. Notes without the new fields
    keep working unchanged.

## Non-Goals

*   Enforcing a task size. `create-task` is told to keep a task small enough to
    finish within one working day and to offer a split when the work is plainly
    larger, but nothing measures or rejects a large task, and split tasks get no
    naming convention or link between them.
*   A stored size for a task. The planner reserves the minutes of the next work,
    not of the whole task.
*   Priority, due dates or scheduling on individual `## Next` steps.
*   A view inside Obsidian that spans vaults. Bases work per vault.
*   A stored or hand-edited list of ranked tasks. The ordered list is computed
    on each run; files under `tools/out/` are disposable.
*   A new view in `Tasks.base`. The per-hub list is the only new view.
*   Computed scores, priority decay, or re-ranking without the user's
    confirmation.
*   New task statuses, or changes to how a vault or the active task is resolved.
*   Changing the order used by `/board`, `/project-tasks`, `task-switch` or
    `task-list`.
*   A bulk pass that assigns a priority to every existing note. Existing notes
    are `p3` until the user changes them.
*   Reminders, recurrence, or calendar events created from `due`.
*   Vault reads in unattended planner runs.

## Open Questions

*   **Base sort behaviour**: Untested. Can a Base formula default a missing
    `priority` to `p3`, can one view sort on more than one key, and where does a
    note with an empty `due` land when sorting by it? Step 0 of the
    implementation plan answers these before any file changes, and states what
    each failure changes.

## Critical User Journeys (CUJs)

### CUJ 1: Create a task with a priority

*   **Given**: A registered vault with a hub.
*   **When**: The user runs `create-task` and names no priority and no date.
*   **Then**: One task note is created with `priority: p3`, an empty `due`, and
    at least one `## Next` step with a time estimate. The user was asked nothing
    beyond what `create-task` asks today.

### CUJ 2: Change the priority of an existing task

*   **Given**: An open task note with `priority: p3`.
*   **When**: The user asks `task-note` to set that task to `p1`.
*   **Then**: The note's frontmatter reads `priority: p1`, and `## Log` has a
    new line with the old and new value. The next planner run and the hub view
    reflect it.

### CUJ 3: Read a hub to see what is next

*   **Given**: A hub with open tasks, some with `priority` and `due`, some with
    neither.
*   **When**: The user opens the hub note in Obsidian.
*   **Then**: The hub lists its open tasks with priority, due date and status,
    in the hub's approximation of the ordering rule. Tasks with no `priority`
    appear as `p3`.

### CUJ 4: Plan a week across vaults

*   **Given**: Three registered vaults with open tasks, and the user present in
    the session.
*   **When**: The user runs `plan-week`.
*   **Then**: The plan places one row per task in rank order on the earliest day
    that has room. A task due inside the week is placed on or before its date.
    An overdue task is treated as due on the first planned day. The output names
    every task that did not fit, has a step with no estimate, or has no open
    step.

### CUJ 5: Plan a day after the week was planned

*   **Given**: A week plan made on Monday. On Wednesday the user creates a `p0`
    task and finishes another task.
*   **When**: The user runs `plan-day` or `morning-startup` on Wednesday.
*   **Then**: The day's list of vault tasks is rebuilt from the notes. The new
    `p0` task is first and the finished task is absent.

### CUJ 6: Adopt the change in an existing vault

*   **Given**: A vault created before this change, with hub notes the user has
    edited.
*   **When**: The user runs `planner-setup update-vaults`.
*   **Then**: After a backup, the Task template gains the two keys without a
    prompt, and unedited hubs gain the task list after one confirmation per
    vault. A hub whose Tasks
    section was edited is listed and left alone. Before the update runs, and if
    the user declines it, existing notes plan as `p3` with no error.

## Technical Plan (Architecture)

### 1. The note contract

Two keys are added to task-note frontmatter. Both are optional and plain
scalars. The existing readers (`vaults.py`, `resolve.ts`) pick fields by name,
so unknown keys do not affect them.

```yaml
status: parked
up: "[[Some Project]]"
priority: p3        # p0 (highest) .. p5. Absent, empty or invalid = p3
due:                # YYYY-MM-DD, or empty. A hard limit when present
repo:
started: 2026-11-12
finished:
```

How a value is read:

| Value read | Treated as | Reported |
|---|---|---|
| `priority` absent or empty | p3 | no |
| `priority` not exactly one of `p0`..`p5` (for example `P1`, `high`) | p3 | warning naming the note and the value |
| `due` absent or empty | no date limit | no |
| `due` not a valid `YYYY-MM-DD` | no date limit | warning naming the note and the value |
| `started` absent, empty or not a date | sorts after every dated `started` | no |

What each priority level means:

| Level | Meaning |
|---|---|
| p0 | Do first, ahead of everything, including tasks with a due date |
| p1 | High |
| p2 | Above normal |
| p3 | Normal (the default) |
| p4 | Low: when there is room |
| p5 | Someday |

**Next work.** The planner does not know how long a whole task is. It reserves
the minutes of the task's next work: the sum of the estimates on the open steps
under `## Next`. `create-task` and `task-start` ask for the first action, and
`task-park` rewrites `## Next` to the next one to three actions, so this number
is "what to do next on this task", not the size of the task. Work left after
that comes back on the next planner run with whatever `## Next` then holds.

Reading rules for `## Next`:

*   The section runs from the `## Next` heading to the next line that starts
    with `## `, or to the end of the file.
*   An open step is a line whose text, after any indentation, starts with
    `- [ ] ` followed by at least one non-space character. Nested steps count.
    Ticked lines (`- [x]`) and the template's empty `- [ ] ` do not.
*   A step's estimate is `(~N min)` or `(~N h)` at the end of the line. Spaces
    after `~` and before the unit are optional, and N is a positive integer or
    decimal, so `(~30min)` and `(~1.5 h)` both match. Hours are converted to
    minutes for each step and rounded up for each step.

| State of `## Next` | Minutes | Planner behaviour |
|---|---|---|
| At least one open step, every one with an estimate | the sum | placed |
| At least one open step has no estimate | none | not placed; listed as `needs an estimate` |
| No open step, or no `## Next` section | none | not placed; listed as `no next step` |

Reading rules for frontmatter:

*   Frontmatter is the lines between a first line `---` and the next `---`
    line. A file in `Tasks/` that does not start with `---`, or is not UTF-8, is
    listed as `unreadable note` whatever its status, and is not placed.
*   A scalar value is the text after `key:`, trimmed, with a trailing
    ` # comment` removed and one pair of matching quotes removed.
*   `aliases`: an inline list `[a, b]` gives `a`; a block list gives the first
    `- ` line under the key; an empty value gives none.
*   `up`: the text between the first `[[` and `]]`, without anything from `|`
    on and without a folder prefix up to the last `/`. `[[]]` or no link gives
    an empty hub name.

### 2. The ordering rule

The rule takes a task and `until`, the end of the planning window: the last
planned day of a week, or six days after the day being planned for a daily run,
so a task due tomorrow is not ranked as undated.

```text
tier(task) = 0  if priority is p0
             1  if task.due is set and task.due <= until   # includes overdue
             2  otherwise

key(task) = (
    tier(task),
    task.due if tier(task) < 2 and task.due is set else "9999-12-31",
    priority as an integer 0..5,     # missing or invalid = 3
    task.started or "9999-12-31",    # older first; undated last
    "<vault>:<slug>",                # final tie-break
)
```

*   A `due` before the first planned day (overdue) is in tier 1 and sorts ahead
    of later dates.
*   A `due` after `until` has no effect on the rank of a `p1`..`p5` task: it is
    in tier 2, where the date element is a constant and priority decides.
*   Among `p0` tasks, one with a `due` (any date) sorts ahead of one without.
*   Status (`active` or `parked`) does not affect rank; both are open.
*   The final tie-break compares the vault name first. Across vaults it only
    makes the order stable; it carries no meaning.

Consequence to accept: a `p5` task due inside the period ranks above an undated
`p1`. That follows from `due` being a hard limit. Only `p0` goes ahead of dated
tasks.

### 3. Data flow

```text
 Obsidian vault(s)                        planner folder
 ┌────────────────────────┐               ┌──────────────────────────────────────┐
 │ Tasks/<slug>.md        │  vault paths  │ tools/task_queue.py   (new)          │
 │   priority, due,       │  passed by    │   reads frontmatter and ## Next      │
 │   status, up, ## Next  │──────────────▶│   applies the ordering rule          │
 │                        │  the skill    │   writes tools/out/queue.json         │
 │ Projects/<hub>.md      │               └───────────────┬──────────────────────┘
 │   embedded base block  │                               │ tasks[] in rank order
 │   (approximate order)  │         week                  │                 day
 └────────────────────────┘      ┌────────────────────────┴───────────┐
        ▲                        ▼                                    ▼
        │ create-task,   ┌──────────────────────────┐   ┌──────────────────────────┐
        │ task-start,    │ plan_week.py --keep-order│   │ plan_day.py (unchanged)  │
        │ task-note      │   earliest day with room │   │   rows the user confirms │
        │ write the keys └──────────────────────────┘   └──────────────────────────┘
```

The skill, not the tool, finds the vaults. The planner skills already carry a
"Vault (optional)" block that lists every registered vault that has `Tasks/` and
`Daily/`; that definition of a vault applies. The tool receives the paths as
arguments, so no plugin imports another and vault resolution is not implemented
a third time.

### 4. New tool: `task_queue.py`

**Command**

```text
task_queue.py --vault <name>=<path> [--vault ...]
              (--week-start YYYY-MM-DD | --date YYYY-MM-DD | neither)
              [--include-weekend] [--out FILE]
```

*   `--vault` is required at least once. A repeated name, a path that is not a
    folder, or a folder with no `Tasks/` inside is an error (exit 2) naming the
    value. With no `vaults.json` the skill passes `--vault vault=<path>`, the
    name the installer already uses for a single unregistered vault.
*   `--date D` plans one day: `until` is `D` plus six days.
*   `--week-start D`, or neither flag, plans a week. The tool calls the same
    `plan_days` function `plan_week.py` uses (moved to `planner_config.py` so
    both import it) with the same arguments, so the planned days and the
    weekend rule cannot differ between the two tools. `until` is the last
    planned day. With neither flag both tools plan from today to the end of the
    week; with `--week-start` both plan every day of that week.
*   The tool reads every `Tasks/*.md` in each vault whose `status` is anything
    other than `done`, including a missing or misspelled status. This matches
    the hub view's filter and the way task resolution skips only `done` notes.
    It writes nothing in a vault.
*   `--out` defaults to `tools/out/queue.json`, a fixed name, so a skill knows
    which file to read back. Exit code is 0 on success, including when every
    task is in `not_placed`.

**How a skill calls it.** Every planning skill uses this one form, with one
`--vault` per vault in play:

```text
cd "<planner-path>" && python3 tools/task_queue.py --vault <name>=<vault-path> [--date <day>]
```

`<name>` is the vault's name in `vaults.json`, or `vault` when there is one
unregistered vault. The skill then reads `tools/out/queue.json`.

**Output file**

```json
{
  "format": "task-queue/1",
  "first_day": "2026-11-18",
  "until": "2026-11-20",
  "tasks": [
    {"title": "arryved:erp-pg17-rehearse: Restore last night's backup",
     "task": "arryved:erp-pg17-rehearse", "name": "Rehearse the clone",
     "source": "vault", "hub": "ERP Postgres 17 upgrade", "status": "parked",
     "priority": "p1", "deadline": "2026-11-18", "minutes": 180}
  ],
  "not_placed": [
    {"task": "vail:some-task", "name": "Some task",
     "reason": "needs an estimate",
     "detail": "2 of 4 open steps have no estimate"}
  ],
  "warnings": [
    {"task": "personal:other-task", "field": "priority", "value": "high",
     "detail": "expected p0..p5, read as p3"}
  ]
}
```

Where each key comes from:

| Key | Source |
|---|---|
| `task` | `<vault>:<slug>`; `<slug>` alone when one vault was passed |
| `title` | `<task>: <first open step, without its estimate>`. This is the label the planner skills already use for a step (`<vault>:<slug>: <item>`), so their rules for the printed page, the daily note and repeated titles apply unchanged |
| `name` | the first entry of `aliases`, else the note's first `# ` heading, else the slug |
| `source` | always `"vault"` |
| `hub` | the text of the `up:` wikilink without brackets or quotes; empty when there is none |
| `priority` | `p0`..`p5` after defaults are applied |
| `deadline` | the note's `due`; the key is omitted when there is no valid `due` |
| `minutes` | the sum defined in section 1 |
| `first_day` | the first planned day (for `--date`, that date) |

`tasks` is in rank order. Each row is a valid `plan_week.py` and `plan_day.py`
task; both tools ignore keys they do not use. `not_placed` reasons are exactly
`needs an estimate`, `no next step` and `unreadable note`. `not_placed` and
`warnings` are each sorted by `task`. The `detail` of a warning is
`expected p0..p5, read as p3` or `expected YYYY-MM-DD, read as no due date`.

A task with several open steps is still one row: its title shows the first step
and its minutes cover all of them.

The `detail` of a `not_placed` row is `N of M open steps have no estimate`,
`no open step under ## Next`, or, for an unreadable note, `not UTF-8` or
`no frontmatter`.

The tool also prints a text summary:

```text
p1 2026-11-18 180m arryved:erp-pg17-rehearse: Restore last night's backup
p3 - 25m personal:renew-domain: Log in to the registrar

Not placed (needs an estimate):
- vail:some-task: 2 of 4 open steps have no estimate

Warnings:
- personal:other-task: priority "high": expected p0..p5, read as p3
```

One line per row of `tasks`, a blank line, one `Not placed (<reason>):` group
per reason that occurs, then `Warnings:`. A group with no rows is left out.

The ordering rule is one pure function in this file with `until` as a
parameter. It is the only coded copy of the rule.

### 5. `plan_week.py`

A new flag, `--keep-order`, changes how unpinned tasks are placed. Without the
flag the tool behaves exactly as today, so a run from the inbox with no vault,
and unattended runs, are not affected.

An **eligible day** for a task is a planned day on or before its `deadline`, or
any planned day when it has none.

| Behaviour | Today | With `--keep-order` |
|---|---|---|
| Order of placement | deadline, then largest first | input order |
| Day chosen | eligible day with the most room | earliest eligible day with room for the task |
| `deadline` before the first planned day | "Didn't fit this week" | treated as due on the first planned day; shown with `(overdue)` |
| Task fits no eligible day | "Didn't fit this week" | the same list, and placement continues with the next task |
| Row with no `minutes` | assumed 25 | assumed 25, as today (queue rows always have minutes; inbox rows may not) |
| A row's `priority` | ignored | shown after the minutes in the plan, as `· p1` |
| `source` in `week-tasks-<date>.json` | not written | written when the input row has it |

Capacity is respected in every case; an overdue task that does not fit the
first day is listed under "Didn't fit this week" with `(overdue)`.

A plan line under the flag reads
`- [ ] <title> — <minutes>m · <priority> (due <deadline>) (overdue)`. Each of
the last three parts appears only when it applies, in that order. The same
form is used under "Didn't fit this week". Without the flag the tool's output
is byte for byte what it is now: no priority label, no `(overdue)` mark and no
`source` key.

Pinned rows (`day`) keep their current behaviour in both modes. The tool still
writes one `week-tasks-<date>.json` per planned day; each row keeps `title` and
`minutes`.

An older installed `plan_week.py` rejects the flag with a usage error, so a
stale tool fails visibly. The four planning skills also check for the new tool.
The check is the first bullet of the "In this skill" list in each skill's vault
block, worded: "If `<planner-path>/tools/task_queue.py` is missing, the folder's
tools predate this plugin version: say so, offer `planner:setup`, and stop. Do
not build the task list by hand." It does not go in the shared
`where-this-runs` block, which a test requires to be identical in all twelve
planner skills.

The `plan-week` skill gives both tools the same period flags: `--week-start`
and `--include-weekend` when the user asked for them, neither otherwise. It
never passes one tool a date taken from the other's output. Items that do not
come from a vault (the inbox, a list the user gives) are appended to the task
list after the queue's rows and are placed in that order, after the vault
tasks.

### 6. Daily planning

`plan_day.py` is not changed. It already keeps input order and lays one row's
minutes as consecutive focus blocks.

When a vault is present and the run is attended, `plan-day`, `morning-startup`
and `eod-shutdown` get the day's vault tasks from `task_queue.py --date <day>`
(`<day>` is today, or tomorrow for `eod-shutdown`), not from the steps of active
tasks and not from Monday's week file. They show the first ten rows; the user
confirms which ones go to `plan_day.py` and which are the Top 3.

Only `morning-startup` reads the week file, in its step 2 and in its scheduled
prompt. It still takes rows that did not come from a vault from that file. In
both places it leaves out rows marked `"source": "vault"`: an attended run has
just rebuilt them from the notes, and an unattended run does not plan vault
tasks, as now. `plan-day` and `eod-shutdown` do not read the week file.

Cost, stated plainly: for vault tasks the week plan is a preview of how the
ranked list fills the week. It does not fix a task to a day. Each day's list is
rebuilt in rank order.

### 7. Skills that write the keys

*   **`create-task`** adds priority and due to the one message it already sends,
    as optional items with `p3` shown as the default. It writes
    `priority: p3` without asking when the user names none, and writes `due`
    only when the user or the source gives a date. A batch shares one priority
    unless told otherwise. One sentence of guidance is added: keep a task small
    enough to finish within one working day, and when the work described is
    plainly larger, propose separate tasks and create them after the user
    confirms.
*   **`task-start`** writes the same two keys with the same default.
*   **`task-note`** gains one action: set `priority` or `due` on an existing
    task. It validates the value (`p0`..`p5`; a `YYYY-MM-DD` date, or empty to
    clear `due`), edits the one frontmatter line (a missing `priority` is added after
    `up:`; a missing `due` after `priority:`, or after `up:` when there is no
    `priority` line), and appends a `## Log` line:
    `- [[YYYY-MM-DD]] HH:MM — priority p3 → p1`,
    `… — due (none) → 2026-11-20` or `… — due 2026-11-20 → (none)`, with the
    date and time taken as the skill's other actions take them. On an invalid
    value it writes nothing and replies with the accepted values.

### 8. Hub view and templates

`Templates/Project.md` replaces its one-line Tasks section with an embedded
Base block, the same shape as the existing Meetings block. Sketch (the shipped
fence is `base`):

```yaml
filters:
  and:
    - file.inFolder("Tasks")
    - file.hasLink(this.file)
    - status != "done"
formulas:
  prio: if(priority, priority, "p3")
  first: priority == "p0"
  soon: if(due, due <= today() + "7 days", false)
views:
  - type: table
    name: Open tasks
    order: [file.name, formula.prio, due, status]
    sort:
      - {property: formula.first, direction: DESC}
      - {property: formula.soon, direction: DESC}
      - {property: due, direction: ASC}
      - {property: formula.prio, direction: ASC}
```

A hub has no planning period, so it uses the next 7 days, and it has no
`started` or slug tie-break. It is an approximation of the rule in section 2
and can differ from a plan in those two respects. The syntax above is untested;
see the open question "Base sort behaviour".

`Templates/Task.md` gains `priority: p3` and `due:` directly after `up:`.
`tests/test_skill_files.py` requires `started:` to sit directly above
`finished:`, so the keys cannot go between those two.

### 9. Existing vaults

`planner-setup update-vaults` gains two steps per vault, each using the existing
backup and dry-run:

1.  **Task template.** If `Templates/Task.md` lacks `priority:` or `due:`, add
    what is missing, without a prompt, as the existing Base merge does when it
    only adds. `priority: p3` goes after the `up:` line (after `status:` when
    there is no `up:`; first in the frontmatter with neither), and `due:` goes
    directly after `priority:`. A vault with no `Templates/Task.md`, or one
    whose file has no frontmatter, gets one message saying the keys were not
    added, and the update continues.
2.  **Hubs.** Collect `Templates/Project.md` and every `.md` file directly in
    `Projects/` and `Areas/` (subfolders are not searched) whose `## Tasks` section body, with surrounding blank lines
    removed, is exactly the original line
    ``Tasks link here via `up:` — see the backlinks pane, or [[Tasks.base]].``
    List them and, when the list is not empty, ask once for the vault:
    `Replace the Tasks section in <n> note(s) in <vault>? (backups kept)`,
    where `<vault>` is the vault's path, as in the existing prompts. On yes, replace that line with the Base block. On no, say so, write nothing,
    and leave the exit code unchanged. A note whose Tasks section already equals the Base block is counted, not
    listed: one line says how many notes already have the task list, so a
    second run reports nothing to do. Notes with a `## Tasks` section holding
    any other text are listed as "left unchanged". `--yes` accepts the prompt; `--dry-run` prints both lists
    and writes nothing.

Each file is backed up into a folder named after its parent folder (`Projects`,
`Areas` or `Templates`) under the vault's backup folder, so two hubs with the same file
name never share a backup path, including for a vault outside the home folder.

Existing task notes and `Tasks.base` are not edited. Without the update, notes
plan as `p3` and hubs keep their current text.

## Alternatives Considered

### Alternative A: Keep the ranked task list inside the hub note

*   **Pros**: One file to read, for the user and for a skill. Matches the
    original request ("read the project hub file").
*   **Cons**: Task notes already own status and steps, so the hub becomes a
    second copy. It goes stale the first time `/done`, `task-park` or a card
    dragged on the Board view changes a note. A per-hub list cannot rank across
    13 hubs and 3 vaults.
*   **Reason for Rejection**: Two sources of truth for the same state. The hub
    shows the order through a view instead.

### Alternative B: A stored queue file that skills read

*   **Pros**: Skills read one file and never scan the vault.
*   **Cons**: A cache that must be rebuilt after every note change, with no
    signal when it is stale. Earlier specs in this repo rule out a cache as a
    second source of truth.
*   **Reason for Rejection**: A scan reads 97 notes per run. A stale cache gives
    a wrong order with no signal. The list is computed on each run, and the
    daily skills do not reuse the week's copy of it for the same reason.

### Alternative C: Keep one planner row per step, ordered by the task's rank

*   **Pros**: No change to how `plan-week` builds its backlog.
*   **Cons**: A high-priority task with many steps fills the week before any
    other task is placed. Steps of one task land on different days, and step 2
    can be placed before step 1.
*   **Reason for Rejection**: It spreads a task over several days in an order
    the planner does not control. One row per task keeps the next work together.

### Alternative D: Enforce a one-day size limit, with numbered sibling tasks

*   **Pros**: Guarantees that every planned task can be finished in a day, which
    is the author's working rule.
*   **Cons**: Needs a size for the whole task, which no note has: `## Next`
    holds only the next actions. It also needs a split procedure, a slug
    convention, a capacity figure shared with `plan_day.py`, and a way to place
    work that cannot be split. Three of 97 open tasks exceed a day today.
*   **Reason for Rejection**: Four review findings, two of them blockers, came
    from this rule. It stays as guidance in `create-task`; nothing enforces it.

### Alternative E: A stored `size:` field on the task

*   **Pros**: A real task size that survives `task-park` trimming `## Next`.
*   **Cons**: A third value to fill in at creation, writer rules in three
    skills, and an update after partial work, or it reports work already done.
*   **Reason for Rejection**: The planner only needs the next work to fill a
    day. Listed under Future Improvements.

### Alternative F: An `after: "[[slug]]"` link between tasks

*   **Pros**: Enforces "B only after A" during placement.
*   **Cons**: A new field, a dependency check in the placement code, and
    handling for cycles and for links to notes that no longer exist.
*   **Reason for Rejection**: Adds a field and a dependency check for an order
    the user can already express with priority and due date. Listed under
    Future Improvements.

### Alternative G: Build the ordered list in skill text, with no tool

*   **Pros**: No new script and no further frontmatter reader.
*   **Cons**: The model re-derives the order on each run, so two runs can
    differ, which is the problem being solved. It cannot be unit-tested.
*   **Reason for Rejection**: The order must be reproducible and tested.

### Alternative H: Change `plan_week.py`'s default placement instead of adding a flag

*   **Pros**: One placement behaviour to maintain.
*   **Cons**: Changes the result for users with no vault and for unattended runs
    that plan from the inbox.
*   **Reason for Rejection**: A run with no vault has no ranked rows, so input
    order carries no meaning there; the current deadline-then-size packing stays
    for it. In a run with a vault, inbox rows follow the vault tasks.

### Alternative I: Rank by priority first, with `due` only as a placement limit

*   **Pros**: Removes the planning period from the rule, so the hub and the
    planner would order tasks identically.
*   **Cons**: A low-priority task with a date this week is placed after every
    higher-priority task and can run out of days before its date.
*   **Reason for Rejection**: `due` is a hard limit. Only `p0` goes ahead of a
    dated task.

### Alternative J: A separate "unranked" state plus a ranking skill for existing notes

*   **Pros**: "Never looked at" stays distinct from "decided p3".
*   **Cons**: Needs empty values to sort last in a Base view (see the open
    question "Base sort behaviour"). A bulk edit of 97 notes changes every
    note's last-edit time, which task resolution uses as a tie-break.
*   **Reason for Rejection**: Missing means `p3`. Existing notes need no edit
    and the user changes only the tasks that are not normal priority.

### Alternative K: Ship in two parts (fields and hub view first, planner later)

*   **Pros**: The readable hub arrives sooner.
*   **Cons**: Until the second part lands, the user sets priorities that the
    planners ignore, and the planners keep rebuilding the order on every run,
    which is half of the problem statement.
*   **Reason for Rejection**: With the size rule, the `Tasks.base` view and the
    week-file hand-off cut, the remaining change is one tool, one flag and skill
    text. It is small enough to ship together.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Rollout and rollback**: The new keys are optional and existing readers
    pick fields by name, so the plugins can be updated in any order and rolled
    back without touching notes. An older `tasks` plugin with a newer `planner`
    plans every note as `p3`. A newer skill with an older installed tool fails
    on the unknown flag; the skill checks for `tools/task_queue.py` first.
*   **Security and privacy**: No new credentials, network calls or data leaving
    the machine. Note text (`name`, `title`, `hub`) is copied into planner JSON
    and plans; the planner skills already state that note text is data and is
    never followed as an instruction, and that rule covers these fields.
*   **Vault writes**: Only `create-task`, `task-start` and `task-note` write the
    new keys, through the Edit and Write tools that `vault-allow.py` (the tasks
    plugin's permission hook) approves inside a registered vault.
    `task_queue.py` only reads. The installer writes after a backup.
*   **Scale**: One read of each open task note per planning run. At 97 notes
    this is well under a second of file reads; nothing in the design changes
    with a few thousand notes.

### Risks and Mitigations

*   **A fourth reader of task-note frontmatter.** `task_queue.py` reads fields
    that `vaults.py`, `resolve.ts` and `park_on_end.py` also read. Mitigation:
    it reads only `status`, `up`, `priority`, `due`, `started` and `aliases`,
    and the note contract is written once in `plugins/EGM.md` with the test
    cases in section 1 as its checks.
*   **Next work understates a large task.** A task with one 30-minute step and
    days of work behind it is planned as 30 minutes. Mitigation: this is the
    stated meaning of the number; the remaining work returns on the next run.
*   **An unattended `plan-week` run overwrites the week plan file.** It plans
    from the inbox only and writes the same `weekly-plan-<week-start>.md`.
    Mitigation: none in this change. For vault tasks the week plan is only a
    preview, and attended daily runs rebuild from the notes; re-running
    `plan-week` restores the preview.
*   **A daily run shows ten rows of a longer list.** A dated task is in the
    first ten only if fewer than ten `p0` or earlier-dated tasks exist.
    Mitigation: tasks due within seven days sort ahead of every undated
    `p1`..`p5` task, and the skill states how many rows it did not show.
*   **The hub order can differ from a plan.** Mitigation: the goal and CUJ 3
    say "approximation"; the two differences are named in section 8.
*   **Six priority levels may be more than the user uses.** Mitigation: the
    default covers the common case; narrowing the scale is under Future
    Improvements.

--------------------------------------------------------------------------------

### Additional Resources

*   [2026-10-29-task-board-design.md](../superpowers/specs/2026-10-29-task-board-design.md):
    the Board view, the `Tasks.base` merge and the status lifecycle this builds
    on.
*   [plugins/EGM.md](../../plugins/EGM.md) and
    [plugins/planner/tools/EGM.md](../../plugins/planner/tools/EGM.md): the
    contracts amended below.
*   Review reports for this document, in the repository root:
    `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`,
    `intermediate_zoom_out_report.md`.

### Future Improvements

*   **A stored task size**: a `size:` field, and a size limit in the planner, if
    planning by next work proves misleading.
*   **An `after:` link between tasks**: enforce "B only after A" in placement.
*   **Priority in the Claude Code panes**: show or sort by priority in `/board`
    and `/project-tasks`.
*   **A `Ranked` view in `Tasks.base`**: one list across all hubs of a vault.
*   **Protecting an attended week plan** from an unattended run.
*   **Fewer levels**: narrow the scale if the six levels collapse to two or
    three used values after a month of use.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Work order: step 0 first. Groups 1 and 2 are independent of each other; groups
3, 4 and 5 follow in order. Checks along the way:

*   After group 2: `python3 -m unittest discover -s tests`.
*   After groups 3 and 4: the same command, then `claude plugin validate` on the
    plugin that changed.
*   After group 5: `cd setup && uv run pytest`.
*   The version bumps (files 18 and 23) and the rebuild of `planner.plugin`
    (file 19) come last.

### Step 0: Obsidian test (manual, before any file changes)

In a copy of the starter vault, add five task notes linked to one hub: one
`p0`, one with `due` in three days, one with `due` in a month, one with
`priority: high` (invalid), one with neither key. Paste the block from Technical
Plan section 8 into the hub and run checks (a) to (e). Record the working block
in section 8 of this document before starting group 1. The fallbacks below are
as untested as the block itself.

| Check | If it fails |
|---|---|
| (a) A formula can default a missing `priority` to `p3` | The view shows the raw `priority` column and sorts on it; notes with no priority sort wherever Bases puts empty values, and section 8 says so |
| (b) A view can sort on more than one key | The view sorts ascending on one formula, `order`, that joins four parts into one string: `"0"` for a `p0` task and `"1"` otherwise; `"0"` for a task due within 7 days and `"1"` otherwise; the `due` date or `9999-12-31`; and `prio`. If formulas cannot build that string, the view sorts by priority only and shows `due` as a column |
| (c) Notes with an empty `due` sort after dated notes when ascending | Sort on a formula `dueKey` in place of `due`: the `due` date when set, the date `9999-12-31` otherwise |
| (d) `today() + "7 days"` is accepted in a formula | Drop `soon`; the hub orders by `first`, then `due`, then priority, and section 8 names the difference |
| (e) `this.file` resolves in a block embedded in a hub | Blocker for the hub view: stop and revise section 8 before any other work, since the existing Meetings block relies on the same expression |

If (a), (b) or (d) fails, reword the hub goal and CUJ 3 to describe the order
the hub can show.

### Target Files to Create/Modify

#### Group 1: Note contract and starter vault

##### 1. `examples/vault-starter/Templates/Task.md` (Modify)

*   **Type / Scope**: Vault template.
*   **Proposed Changes**: Add `priority: p3` directly after `up:` and an empty
    `due:` directly after it. Leave `started:` directly above `finished:`.
    `create-task` and `task-start` copy this file, so new notes carry the keys.

##### 2. `examples/vault-starter/Templates/Project.md` (Modify)

*   **Type / Scope**: Vault template.
*   **Proposed Changes**: Replace the one-line `## Tasks` pointer with the Base
    block confirmed in step 0, in a `base` fence, under the same heading. The
    installer (file 25) reads the block from this file.

##### 3. `examples/vault-starter/Projects/ADHD Planner.md` and `examples/vault-starter/Areas/Health.md` (Modify)

*   **Type / Scope**: Starter hub notes. Both have the one-line Tasks section.
*   **Proposed Changes**: Apply the file 2 replacement to each.

##### 4. `examples/vault-starter/Tasks/set-up-vault.md` (Modify)

*   **Type / Scope**: Starter task note.
*   **Proposed Changes**: Add `priority: p3` and `due:` after `up:`.

##### 5. `examples/vault-starter/Notes/How this vault works.md` (Modify)

*   **Type / Scope**: User-facing vault guide.
*   **Proposed Changes**: Add a section with the two keys, the table of levels
    from Technical Plan section 1, what the hub list shows, and how to change a
    task's priority (`task-note`, or the frontmatter in Obsidian).

##### 6. `plugins/EGM.md` (Modify)

*   **Type / Scope**: Cross-plugin contract.
*   **Proposed Changes**: Add a "Task priority" invariant beside the status
    lifecycle: the two keys with their values and defaults, the reading rules
    for frontmatter and `## Next`, the ordering rule, the skills that write the
    keys, and the statement that `plugins/planner/tools/task_queue.py` holds the
    only coded copy of the rule.

##### 7. `AGENTS.md` (Modify)

*   **Type / Scope**: Agent guide.
*   **Proposed Changes**: Add one paragraph after "Vault resolution" pointing at
    the new invariant in `plugins/EGM.md`.

#### Group 2: Planner tools

##### 8. `plugins/planner/tools/planner_config.py` (Modify)

*   **Type / Scope**: Python library module.
*   **Proposed Changes**: Move `monday_of` and `plan_days` here from
    `plan_week.py` with their bodies unchanged, and add the `datetime` import
    they need. `task_queue.py` and `plan_week.py` then share one definition of
    the planned days.

##### 9. `plugins/planner/tools/task_queue.py` (Create)

*   **Type / Scope**: Python script, standard library only.
*   **Proposed Changes**: Implement Technical Plan sections 1, 2 and 4.
    Components:
    *   the command line, its defaults and its exit-2 errors (section 4);
    *   a frontmatter reader for `status`, `up`, `priority`, `due`, `started`
        and `aliases`, following the frontmatter reading rules (section 1);
    *   a `## Next` reader following the reading rules (section 1);
    *   `sort_key(task, until)` as a pure function (section 2);
    *   the JSON file and the text summary (section 4).

    It imports `planner_config` for `plan_days` and reads the system date only
    to compute the default week, as `plan_week.py` does.

##### 10. `plugins/planner/tools/plan_week.py` (Modify)

*   **Type / Scope**: Python script.
*   **Proposed Changes**:
    *   Import `plan_days` and `monday_of` from `planner_config`. The names stay
        available as `plan_week.plan_days`, which the existing tests call.
    *   Add `--keep-order`, passed to placement as
        `distribute(tasks, day_dates, capacity, keep_order=False)`. The default
        keeps the existing positional call in `tests/test_plan_week.py` working.
    *   With the flag: the placement rules of the table in Technical Plan
        section 5, the plan-line form given under that table, and `source`
        carried into `week-tasks-<date>.json`.
    *   Without the flag: output byte for byte as it is now.

##### 11. `plugins/planner/tools/setup_check.py` (Modify)

*   **Type / Scope**: Python script.
*   **Proposed Changes**: Add `task_queue.py` to the list of required scripts.

##### 12. `plugins/planner/tools/EGM.md` and `plugins/planner/tools/README.md` (Modify)

*   **Type / Scope**: Tool contract and human guide.
*   **Proposed Changes**: Add the `task_queue.py` row and its output file; the
    `--keep-order` flag; `plan_days` in `planner_config.py`; and the invariant
    that `task_queue.py` is the one tool that reads a vault, read-only, from
    paths given by the caller. In `EGM.md`, amend the Overview sentence that
    says scripts read only JSON that Claude saved, and add `test_task_queue`
    and `test_setup_check` to the test list under Verification.

##### 13. `tests/test_task_queue.py` (Create)

*   **Type / Scope**: Unit tests (`unittest`) against a temporary vault folder.
*   **Proposed Changes**: One named test for each of these.
    *   Each row of the "How a value is read" table in section 1.
    *   Each row of the "State of `## Next`" table in section 1.
    *   `## Next` reading: nested steps count; ticked lines and the empty
        placeholder do not; the section ends at the next `## ` heading.
    *   Estimates: `(~30 min)`, `(~30min)`, `(~2 h)`, `(~1.5 h)` giving 90, and
        rounding up per step.
    *   Frontmatter: quoted scalars; a trailing comment; `aliases` inline and as
        a block list; `up` with an alias, with a folder, and as `[[]]`.
    *   `unreadable note` for a file that is not UTF-8 and for one with no
        frontmatter.
    *   The `name` chain: alias, then heading, then slug.
    *   Ordering: each tier; overdue ahead of later dates; a `due` after `until`
        not affecting a `p1`..`p5` task; a dated `p0` ahead of an undated `p0`;
        the `started` tie-break; the `<vault>:<slug>` tie-break.
    *   `done` notes excluded; two vaults merged into one order.
    *   `task` as a bare slug with one vault and `<vault>:<slug>` with two.
    *   A task with three open steps giving one row titled with the first step
        and minutes covering all three.
    *   `--date D` giving `until` of `D` plus six days; `--week-start` and no
        flag giving the same days as `plan_days`; `--include-weekend` extending
        `until` to Sunday.
    *   `--out` writing to the given file, and the default writing
        `tools/out/queue.json`.
    *   A note with a missing or misspelled `status` included; `not_placed` and
        `warnings` sorted by `task`.
    *   Exit 2 for a duplicate vault name, a missing path, and a folder with no
        `Tasks/`. Exit 0 when every task is in `not_placed`.
    *   The content of `warnings`; each `detail` string; the text summary.
    *   Every key of an output row; identical output for two runs on the same
        input.

##### 14. `tests/test_plan_week.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Add one named test per row of the table in Technical
    Plan section 5, plus: the plan-line form with and without each optional
    part; a pinned row under the flag; `source` present in the week files with
    the flag and absent without it; and one test pinning the current order and
    output without the flag. The existing `plan_days` tests stay unchanged.

##### 15. `tests/test_setup_check.py` (Create)

*   **Type / Scope**: Unit test.
*   **Proposed Changes**: Copy the tools folder to a temporary folder, remove
    `task_queue.py`, run `setup_check.py` there, and expect the missing script
    to be reported.

#### Group 3: Planner skills

The stale-tool check from Technical Plan section 5 is added, with the wording
given there, as the first bullet of the "In this skill" list in the vault block
of files 16, 17a, 17b and 17c. The shared `where-this-runs` block and the label
rules in the vault block are not edited in any skill.

In the replacement texts below, "the queue command" stands for this text, which
is written out in full in each skill:
`cd "<planner-path>" && python3 tools/task_queue.py --vault <name>=<vault-path>` with one `--vault` per vault in play (`<name>` is the vault's name
in `vaults.json`, or `vault` when there is one unregistered vault), then read
`tools/out/queue.json`. Daily skills add `--date <day>`; `plan-week` adds the
same `--week-start` value and `--include-weekend` it gives `plan_week.py`, or
neither.

##### 16. `plugins/planner/skills/plan-week/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions.
*   **Proposed Changes**:
    *   In the vault block's "In this skill" list, replace the Backlog bullet
        ("add the open Next items of every task note … Ask before including
        parked ones if there are many.") with: run the queue command; put its
        `tasks` first in `tasks.json`, then
        any inbox or user items; run `plan_week.py --keep-order`; give both
        tools the same `--week-start` value and `--include-weekend`, or
        neither; tell the user the `not_placed` rows and the warnings.
    *   After the step 3 command, add one line: a vault run adds `--keep-order`.
    *   In "Behavior notes", extend the placement bullet with: "In a vault run,
        tasks go in rank order on the earliest day with room."
    *   At the end of step 2 ("Right-size the backlog", which sends oversized
        tasks to break-down-task), add one sentence: "Rows from `task_queue.py`
        are not decomposed here."
    *   Do not write the literal `--week-start <YYYY-MM-DD>` anywhere in this
        skill; `tests/test_skill_files.py` forbids it.
    *   The no-vault and unattended paths keep their current text.

##### 17a. `plugins/planner/skills/plan-day/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions.
*   **Proposed Changes**: Replace the bullet "**Inputs:** when no task list is
    given, offer the open Next items of every vault's active task as the task
    list." with: "**Inputs:** when no task list is given, run [the queue command
    with `--date <target date>`] and offer its first ten rows as the task list;
    say how many rows were not shown."

##### 17b. `plugins/planner/skills/morning-startup/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions, including the scheduled prompt.
*   **Proposed Changes**:
    *   Replace the bullet "**Step 2, candidates for the Top 3:** add the open
        Next items of every vault's active task (and of any task note the user
        names) to the pool, titled as above. Prefer them over generic inbox
        items when the user is mid-task." with: "**Step 2, candidates for the
        Top 3:** run [the queue command with `--date <today>`]. Add the rows the user confirms from its first ten rows (and the
        row of any task note the user names) to the pool, with the titles the
        tool wrote; say how many rows were not shown."
    *   In step 2 and in the scheduled prompt, after "whichever exist," add:
        "leaving out week-plan rows marked `"source": "vault"`,". In the
        scheduled prompt those two words are split across a quoted line break.
    *   Do not repeat the week file's path, the pool phrase or the
        `plan_day.py --tasks` command in the new text:
        `tests/test_skill_files.py` pins each at exactly two occurrences.

##### 17c. `plugins/planner/skills/eod-shutdown/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions.
*   **Proposed Changes**: Add a bullet to the vault block's "In this skill"
    list, before the existing "**Step 6:**" bullet: "**Step 6, tomorrow's
    tasks:** run [the queue command with `--date <tomorrow>`] and offer its
    first ten rows as candidates for the Top 3; say how many rows were not
    shown. Add the rows the user confirms to the task list that step 6 passes
    to `plan_day.py` for tomorrow."

##### 17d. `plugins/planner/skills/setup/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions.
*   **Proposed Changes**: Change the script count from ten to eleven in all
    three places it appears, and name `task_queue.py` beside
    `planner_config.py` both in the sentence that lists the bundled scripts and
    in the sentence about a folder that has all its scripts yet is stale.

##### 18. `plugins/planner/EGM.md`, `plugins/planner/README.md`, `plugins/planner/.claude-plugin/plugin.json` (Modify)

*   **Type / Scope**: Plugin contract, guide and manifest.
*   **Proposed Changes**: In `EGM.md`: add `task_queue.py` to the tool list and
    to the skill-to-tool lines, change the script count from ten to eleven, and
    record that attended runs with a vault take their task list from
    `task_queue.py`, one row per task, while unattended runs still do not read
    the vault. In `README.md`: replace the sentence that says plan-week "pulls
    open Next items", and the one that says the planning skills "pull each
    vault's active task and inbox", with the same statement. Bump the version from 0.5.5 to
    0.6.0.

##### 19. `planner.plugin` (Rebuild)

*   **Type / Scope**: Build output.
*   **Proposed Changes**: Rebuild with `bash scripts/build-plugin.sh` after the
    planner changes. Never edit it by hand.

#### Group 4: Task skills

##### 20. `plugins/tasks/skills/create-task/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions.
*   **Proposed Changes**: Step 2 lists priority (default `p3`) and due date as
    optional items in the same single message. Step 4 writes `priority` and,
    when given, `due`. Add the one sentence of size guidance from Technical Plan
    section 7. The description is unchanged.

##### 21. `plugins/tasks/skills/task-start/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions.
*   **Proposed Changes**: Step 4 writes `priority` (`p3` unless the user named
    one) and `due` when given.

##### 22. `plugins/tasks/skills/task-note/SKILL.md` (Modify)

*   **Type / Scope**: Skill instructions.
*   **Proposed Changes**: Under "Actions", add "set priority or due" with the
    validation, the frontmatter edit with its rule for a missing key, the three
    Log line forms and the invalid-value reply of Technical
    Plan section 7. If the description changes, keep it within the
    400-character test limit.

##### 23. `plugins/tasks/EGM.md`, `plugins/tasks/.claude-plugin/plugin.json` (Modify)

*   **Type / Scope**: Plugin contract and manifest.
*   **Proposed Changes**: Add which skills write `priority` and `due`, beside
    the status writer rules. Bump the version from 0.6.1 to 0.7.0.

##### 24. `tests/test_skill_files.py` (Modify)

*   **Type / Scope**: Unit tests over skill and template text.
*   **Proposed Changes**: Add assertions that:
    *   the Task template has `priority:` and `due:` and still has `started:`
        directly above `finished:`;
    *   `create-task`, `task-start` and `task-note` mention both keys;
    *   `task-note` contains `priority p3 → p1` and `→ (none)`;
    *   the four planning skills contain
        `tools/task_queue.py --vault <name>=<vault-path>` and
        `tools/out/queue.json` outside the shared block;
    *   the starter `Templates/Project.md` and both starter hubs no longer
        contain the original Tasks pointer line and have a `base` fence under
        `## Tasks`;
    *   `plan-week` names `--keep-order` and no longer says "estimate when an
        item has none";
    *   `plan-day`, `morning-startup` and `eod-shutdown` contain "first ten
        rows";
    *   `morning-startup` contains `"source": "vault"` exactly twice.

    New assertions on skill text use the file's `flat()` helper, so a phrase
    wrapped across lines still matches. The existing assertions, including the
    three counts of two in `MorningStartupTest`, stay unchanged and must still
    pass.

#### Group 5: Installer and docs

##### 25. `setup/src/planner_setup/actions.py` (Modify)

*   **Type / Scope**: Python module (installer actions).
*   **Proposed Changes**: In `update_vaults`, after `_merge_tasks_base` and
    before `_board_plugin`, call two new functions that implement Technical Plan section 9, and update
    the `update_vaults` docstring.
    *   `_add_priority_keys(ctx, vault, backups)`: step 1. No prompt; it says
        "Add" or, on dry-run, "Would add".
    *   `_replace_hub_tasks(ctx, vault, backups)`: step 2, with the prompt text
        given there. The original hub line is a constant in this module,
        because file 2 removes it from the starter. The Base block is the text
        under the `## Tasks` heading of the starter `Templates/Project.md` to
        the end of the file, fences included, trimmed.
    *   Both use `files.backup`, `ctx.dry_run`, `ctx.yes` and `ctx.confirm` as
        `_merge_tasks_base` does. For a hub, the backup folder passed to
        `files.backup` ends with the file's parent folder name.

##### 26. `setup/tests/test_actions.py` (Modify)

*   **Type / Scope**: `pytest` unit tests.
*   **Proposed Changes**: Add tests for:
    *   a Task template with neither key, with `priority` only, with both, with
        no `up:` line, with no frontmatter, and a vault with no
        `Templates/Task.md`;
    *   no prompt for the template step;
    *   a hub with the original line replaced; a hub with other text left and
        listed; a hub with no Tasks section ignored; a hub in a subfolder
        ignored; no prompt when there is nothing to replace; the vault's own
        `Templates/Project.md` replaced like a hub;
    *   a second run after a yes: no prompt, nothing written, and one line
        counting the notes that already have the task list;
    *   the exact prompt text; a declined prompt writing nothing; `--yes`
        skipping the prompt; `--dry-run` writing nothing;
    *   backups, using a vault outside the home folder with `Projects/X.md` and
        `Areas/X.md`, modelled on the existing
        `test_update_vaults_keeps_separate_backups_for_vaults_outside_home`;
    *   CRLF line endings kept.

    The existing `test_update_vaults_asks_before_download` must pass unchanged:
    its fixture has no `Templates/` or `Projects/` folder, so the new steps add
    no prompt there.

##### 27. Installer contracts and documentation (Modify)

*   **Type / Scope**: Help text, contracts and user documentation that describe
    `update-vaults` as adding the task board only.
*   **Proposed Changes**: State that the update also adds the Task template keys
    and the hub task list, in each of:
    *   `setup/src/planner_setup/cli.py` (the `update-vaults` help text only;
        the menu label "Update existing vaults (task board)" stays, because
        `setup/tests/test_cli.py` pins it);
    *   `setup/EGM.md`, `setup/src/EGM.md`, `setup/src/planner_setup/EGM.md`
        and the root `EGM.md`, wherever each describes `update_vaults` or its
        vault writes;
    *   `docs/setup.md`, which also gains the two keys, the levels, the hub
        list, the prompt, and how to change a task's priority.

### Verification Plan

*   **Compilation/Build**: `bash scripts/build-plugin.sh` (validates, runs
    `tests/`, rebuilds `planner.plugin`); `cd setup && uv build`.
*   **Unit Tests**: `python3 -m unittest discover -s tests`;
    `cd setup && uv run pytest`.
*   **Static Analysis & Linting**: `claude plugin validate plugins/planner`;
    `claude plugin validate plugins/tasks`. Run the `skill-trigger-reviewer`
    agent only if a skill description was edited (file 22).
*   **Test Coverage Requirement**: every row of the tables in Technical Plan
    sections 1 and 5, and every bullet of files 13, 14 and 26, has a named test.
*   **E2E/Integration** (manual, on a copy of a real vault):
    1.  `task_queue.py` over every registered vault: every open note appears
        exactly once, in `tasks` or `not_placed`.
    2.  Run it twice; the two output files are identical.
    3.  `plan-week` end to end: a task due inside the week is on or before its
        date; an overdue task is marked; every unplaced task is named.
    4.  Create a `p0` task after planning the week; `plan-day` lists it first.
    5.  `create-task` with no priority asks nothing new and writes
        `priority: p3`.
    6.  `task-note` sets a task to `p1`; the note and its Log show the change.
    7.  Open a hub in Obsidian: open tasks appear in the order recorded in
        step 0. This check is manual because a rendered Base view cannot be
        exercised by the repo's test suites.
    8.  `planner-setup update-vaults --dry-run` on a vault with one edited hub
        writes nothing and lists both groups; a real run leaves the edited hub
        untouched and creates backups.

--------------------------------------------------------------------------------

*Drafted with EGM*
