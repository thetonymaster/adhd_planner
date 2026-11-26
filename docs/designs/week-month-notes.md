# Week Notes, Month Notes and Recurring Items

*   **Author:** Antonio Cabrera
*   **Status:** Proposed (EGM review complete, Stages 5–9)
*   **Date:** 2026-11-17

--------------------------------------------------------------------------------

## Overview

A vault that opts in gets two new kinds of dated notes next to `Daily/`:

*   **Week notes**, such as `Weekly/2026-W48.md`: one per ISO week, starting Monday.
*   **Month notes**, such as `Monthly/2026-11.md`: one per month.

A vault opts in by having a **Recurrence list**, `Recurring.md`, at its root. Each line of the list is one item that repeats every week or every month, with a rule and a stable ID.

When `plan-week` or `morning-startup` runs interactively:

1.  A new tool, `period_note.py ensure`, finds or creates the period notes for the week.
2.  The tool adds that period's recurring items to the notes.
3.  `plan-week` then writes that vault's share of the week's plan into the week note, the same way `morning-startup` already writes the Daily note's `## Plan`.

Obsidian is the source of truth. Calendar sync is out of scope (Non-Goal 2).

### Terms

*   **Period note**: a week note or a month note.
*   **Owned section**: a part of a period note between two HTML-comment markers. Only the planner writes inside it. There are two:
    *   **Plan section**: between `<!-- planner:plan-week:start -->` and `<!-- planner:plan-week:end -->`. The `plan-week` skill replaces it on every run, so edits made inside it are lost.
    *   **Recurring section**: between `<!-- planner:recurring:start -->` and `<!-- planner:recurring:end -->`. `period_note.py` only adds lines to it, so ticks and deletions survive.
*   **Occurrence**: one dated line in a Recurring section, made from one Recurrence list rule for one period.
*   **Ledger**: the `added:` frontmatter key of a period note. It lists the IDs of every occurrence the tool has added, so a deleted occurrence is never added again.
*   **In play**: a vault the skill passes with `--vault`. That is every registered vault with `Tasks/` and `Daily/` (`plugins/planner/skills/plan-week/SKILL.md`, "Find the vaults once").
*   **Current vault**: the vault on the session-start `Vault:` line, else `default`.
*   **`Now:` line**: the date and time the session hooks print, in `vaults.json`'s timezone.
*   **Cowork**: the Claude desktop app's agent mode. Vaults appear there as mounted folders, and Obsidian may not be running.

## The Problem

1.  **The weekly plan is not kept in the vault.**
    *   `plan-week` writes the plan to `tools/out/weekly-plan-<week-start>.md` in the planner folder (`plugins/planner/skills/plan-week/SKILL.md`, "In this skill").
    *   That folder is git-ignored and outside every vault (`plugins/planner/tools/EGM.md`). The plan is not synced to other devices and nothing links to it.
    *   A re-run for the same week overwrites it, so you can't add notes to this week's plan or browse past weeks' plans in Obsidian.
2.  **Monthly and weekly routines have no home in the vault.**
    *   Things like paying rent on the 1st, a monthly SLO review or a weekly review are not recorded in any vault note.
    *   Task notes have `priority:` and `due:` but no repeat rule (`plugins/EGM.md`, "Task priority").
    *   A monthly item also needs a page for its month: the place where you see what's due this month, tick it, and write the month's notes. That is why month notes exist alongside week notes.
3.  **Re-runs would duplicate or erase content.** `plan-week` and `morning-startup` run more than once a week.
    *   A writer that appends on each run fills the notes with copies.
    *   A writer that rewrites whole notes erases your ticks and your own writing.

The proposal:

*   One Python tool, `period_note.py`, covered by tests. It creates period notes and writes the Recurring section, which holds state you change (ticks, deletions).
*   The `plan-week` skill writes the Plan section with Edit, following the Daily `## Plan` precedent (`plugins/planner/skills/morning-startup/SKILL.md`, "After step 4"). The Plan section is replaced whole, so no state of yours has to be merged.

## Goals

1.  **The weekly plan is kept.** An interactive `plan-week` run writes each opted-in vault's share of the plan into that vault's week note, inside the Plan section. Text outside the section is never changed.
2.  **Running `ensure` twice changes nothing.** Two `ensure` runs with the same inputs and the same vault content leave every file byte-identical and print `Unchanged`. Tests cover:
    *   creating a new note;
    *   updating an existing note;
    *   a deleted occurrence;
    *   a missing or broken marker;
    *   ISO week 53 (2026-W53);
    *   a week that spans two months (2026-W49).
3.  **Month notes exist and are linked.**
    *   `Monthly/YYYY-MM.md` holds that month's monthly occurrences.
    *   Each week note's `month:` key points to the month that contains the week's Thursday.
    *   Each week note's body links every month the week touches.
4.  **Recurring items are defined once and appear once.**
    *   **Weekly items** become one occurrence line in each week note.
    *   **Monthly items** become one occurrence line in the month note of the month that contains their date.
    *   **An occurrence is frozen once written.** Edits to its rule affect only notes for periods not created yet.
    *   **An occurrence you delete is never re-added.**
5.  **A skipped week still gets its notes.** An interactive `morning-startup` run calls `period_note.py ensure` for today's week. That creates the period notes and adds occurrences. It doesn't write a Plan section.
6.  **Existing vaults adopt it only on purpose.**
    *   `planner-setup update-vaults` asks once for each vault before adding a starter `Recurring.md`. It never asks when `Recurring.md` exists.
    *   `Weekly/` and `Monthly/` are created the first time a note needs them.
    *   A vault without `Recurring.md` is never written.

## Non-Goals

1.  **Scheduled (unattended) runs writing to the vault.** The rule "Scheduled runs never touch the vault" (`plugins/planner/EGM.md`) stays. Scheduled `plan-week` and `morning-startup` keep writing only to `tools/out`.
2.  **Google Calendar or iCal sync.** A recurring meeting in `Recurring.md` is a reminder line. Free time still comes only from the calendar.
3.  **Cross-vault notes.** Each vault has its own notes and gets only its own rows. There are no links across vaults and no combined view.
4.  **Recurring items in the plan.** Occurrences don't enter the task pool, `task_queue.py`'s ranked list, the board, the status lifecycle or capacity. Feeding them into the week plan is a Future Improvement.
5.  **Two copies of a monthly item.** Monthly items live only in month notes. A week note links to its months; it never repeats their lines.
6.  **Replacing `tools/out`.** `plan-day` and `morning-startup` keep reading `week-tasks-<date>.json`. The week note is the copy you keep.
7.  **Editable layout templates and Base views.** The tool creates notes from built-in text. Vault templates for period notes and Obsidian Base views are Future Improvements.
8.  **Renamed period notes and sync-conflict copies.** A period note is found only by its canonical filename. A renamed note is not found, and a new one is created.
9.  **Community plugins.** Periodic Notes and Templater are not required. A Periodic Notes user is told to set its weekly format to `GGGG-[W]WW`, so both tools use the same filename.
10. **More rule types.** "Every 2 weeks", quarterly and yearly rules are out. Unrecognized rules are skipped with a warning.

## Open Questions

None open. Questions answered while drafting:

*   ~~**Which date names the week, given two timezone settings?**~~ Answered in Technical Plan §4, "Dates". `ensure` uses the same date source as `plan_week.py` when planning, and the `Now:` date in `morning-startup`. No new setting is needed.
*   ~~**What happens when two Recurrence list lines share one `#id/`?**~~ Answered in §3: both lines are skipped with a warning, because picking one of them would be a guess.

## Critical User Journeys (CUJs)

The CUJs use two vaults: `arryved` (opted in) and `personal` (no `Recurring.md`).

### CUJ 1: Sunday planning stores the week

*   **Given**:
    *   It is Sunday 2026-11-22, in ISO week W47.
    *   `arryved` has no `Weekly/` or `Monthly/` folder.
    *   arryved's `Recurring.md` has the line `- [ ] Weekly review (~30 min) — every: mon #id/weekly-review`.
*   **When**: You run `/planner:plan-week`.
*   **Then**:
    *   `ensure --plan-week` picks W48 (Nov 23–29), the same week `plan_week.py` plans on a Sunday.
    *   It creates `Monthly/2026-11.md`, then `Weekly/2026-W48.md` with `period: 2026-W48`, `month: "[[2026-11]]"` and `added: [weekly-review-2026-w48]`.
    *   The week note's Recurring section has `- [ ] Weekly review (~30 min) — 2026-11-23 ^weekly-review-2026-w48`.
    *   The tool prints:

        ```text
        Week 2026-W48 (Monday 2026-11-23)
        Wrote arryved:Monthly/2026-11.md
        Wrote arryved:Weekly/2026-W48.md
        Off personal: no Recurring.md
        ```
    *   The skill writes the plan rows titled `arryved:…` into arryved's Plan section. It tells you that personal's rows were not stored, because personal hasn't opted in.

### CUJ 2: Re-plan on Wednesday keeps your edits

*   **Given**: `Weekly/2026-W48.md` exists. You have:
    *   ticked "Weekly review";
    *   deleted another occurrence line;
    *   written notes under `## Notes`.
*   **When**: You run `plan-week` again on Wednesday 2026-11-25.
*   **Then**:
    *   `ensure` prints `Unchanged arryved:Weekly/2026-W48.md`, and the file's bytes don't change.
    *   The deleted line is not re-added, because its ID is in `added:` but no line carries it.
    *   The skill replaces only the text between the plan-week markers.
    *   The ticked line and your notes are unchanged.

### CUJ 3: A monthly item in a week that belongs to the other month

*   **Given**:
    *   arryved's `Recurring.md` has the line `- [ ] Close books — every: month last #id/close-books`.
    *   The CUJ 1 run created `Monthly/2026-11.md`, so it already holds `- [ ] Close books — 2026-11-30 ^close-books-2026-11`.
    *   Mon 2026-11-30 is in W49, and W49's Thursday is Dec 3.
*   **When**: You run `plan-week` on Saturday 2026-11-28, which plans W49.
*   **Then**:
    *   `Monthly/2026-12.md` is created with December's monthly occurrences. `Monthly/2026-11.md` is `Unchanged`.
    *   `Weekly/2026-W49.md` has `month: "[[2026-12]]"` and a body line `Months: [[2026-11]] · [[2026-12]]`.
    *   The week note has no Close books line. You reach it through the November link.

### CUJ 4: A skipped week still gets its notes

*   **Given**: You didn't run `plan-week` for W50. It is Monday 2026-12-07.
*   **When**: You run `/planner:morning-startup` interactively.
*   **Then**:
    *   `ensure --date 2026-12-07` creates `Weekly/2026-W50.md` with its occurrences. `Monthly/2026-12.md` is `Unchanged`.
    *   The week note's Plan section is empty: the markers are present, with nothing between them.
    *   Today's Daily note writes happen as before.
    *   A scheduled `morning-startup` firing writes none of this.

### CUJ 5: A broken marker stops the write

*   **Given**: You deleted the `<!-- planner:recurring:end -->` line from `Weekly/2026-W48.md`. A new weekly rule was added since the last run.
*   **When**: `plan-week` runs.
*   **Then**:
    *   The tool writes nothing to that file and prints `Skipped arryved:Weekly/2026-W48.md: expected one recurring start/end marker pair, found start=1 end=0`.
    *   `Monthly/2026-11.md` and other vaults are still processed.
    *   The process exits 1.
    *   The skill names the file and the fix, which is to restore the end marker line. It still writes the Plan section, because the plan-week markers are intact.

## Technical Plan (Architecture)

### 1. Components

| Piece | Kind | Role |
|---|---|---|
| `tools/period_note.py` | new CLI, standard library only | The only code that creates period notes or writes Recurring sections. One subcommand, `ensure`. |
| `tools/planner_config.py` | library, extended | ISO helpers shared by every tool: `iso_week(date) -> "2026-W48"`, `week_month(monday) -> "2026-12"` (the month of the week's Thursday) and `months_touched(monday) -> ["2026-11", "2026-12"]`. |
| `Recurring.md` | vault note, new | The Recurrence list, and the opt-in signal. |
| `plan-week` skill | prose, extended | Runs `ensure`, then writes each opted-in vault's Plan section with Edit. |
| `morning-startup` skill | prose, extended | Runs `ensure` for today. |
| `planner-setup update-vaults` | installer, extended | Asks before adding a starter `Recurring.md`. |
| `setup_check.py`, the `setup` skill | existing, updated | Know about the twelfth script, so a planner folder without `period_note.py` is reported as out of date. |

`task_queue.py`, `plan_week.py`, `plan_day.py` and the `tasks` plugin hooks don't change.

### 2. Data flow

```text
plan-week (interactive)
  1. period_note.py ensure --plan-week [--week-start D] --vault A=… --vault B=…
       └─► per vault with Recurring.md: Monthly/<M>.md (each month the week touches), Weekly/<W>.md
           per vault without it:        "Off <vault>: no Recurring.md"
  2. task_queue.py → tasks.json → plan_week.py   (unchanged)
  3. skill: for each vault ensure did not report as Off,
            Edit Weekly/<W>.md between the plan-week markers with that vault's rows

morning-startup (interactive)
  period_note.py ensure --date <Now: date> --vault A=… --vault B=…
       └─► same note creation; Plan sections untouched
```

Within a `plan-week` run, `ensure` runs first. The week note then exists before the skill writes to it, and the skill learns from `ensure`'s output which vaults opted in.

### 3. Note formats

#### Recurrence list (`Recurring.md`, vault root)

The tool reads only lines that match the pattern below. Headings, blank lines, other text and lines inside fenced code blocks are ignored. You can group and comment the list freely.

```text
^- \[[ xX]\] (?P<text>.+?) — every: (?P<rule>.+?) #id/(?P<id>[a-z0-9][a-z0-9-]*)\s*$

<rule> := mon|tue|wed|thu|fri|sat|sun        weekly, on that day
        | month <N>, 1 ≤ N ≤ 31               monthly; past the month's end, the month's last day
        | month last                          the month's last day
        | month first-<mon..sun>              the first such weekday of the month
```

*   **Separator:** it is ` — ` (an em dash with a space on each side). Rule keywords are lowercase.
*   **Text:** `<text>` is copied into each occurrence as-is. An estimate such as `(~30 min)` is plain text to this tool.
*   **The box:** a `- [ ]` or `- [x]` box in `Recurring.md` has no meaning, and ticking it does nothing. It is there so the line looks like the occurrences it makes.
*   **Problem lines:**
    *   A line that contains `every:` but doesn't match is skipped. The tool prints a warning naming the line number.
    *   Two lines with the same `#id/` are both skipped, with one warning.

#### Occurrence line, inside a Recurring section

```text
- [ ] <text> — <YYYY-MM-DD> ^<id>-<period>
```

*   `<period>` is the lowercased period label:
    *   for weekly rules, the week label (`^weekly-review-2026-w48`);
    *   for monthly rules, the month label (`^close-books-2026-11`).

    Every block ID therefore matches `[a-z0-9-]+`.
*   The date is that period's date for the rule. It is written when the occurrence is created and is never recomputed.
*   A ticked line is `- [x]`.

#### Week note, `Weekly/2026-W48.md`

```text
---
period: 2026-W48
month: "[[2026-11]]"
added: [weekly-review-2026-w48]
tags: [weekly]
---
# Week 48 · Nov 23 – Nov 29, 2026

Months: [[2026-11]]

## Plan
<!-- planner:plan-week:start -->
<!-- planner:plan-week:end -->

## Recurring
<!-- planner:recurring:start -->
- [ ] Weekly review (~30 min) — 2026-11-23 ^weekly-review-2026-w48
<!-- planner:recurring:end -->

## Notes
```

*   **The title** uses the week number without padding. Day and month names come from a fixed English table, not from locale-dependent `strftime`:
    *   a week inside one month and year: `Week 48 · Nov 23 – Nov 29, 2026`;
    *   a week that spans two months: `Week 49 · Nov 30 – Dec 6, 2026`;
    *   a week that spans two years: `Week 53 · Dec 28, 2026 – Jan 3, 2027`.
*   **`Months:`** lists every month the week touches (`months_touched`), joined by ` · `.
*   **`month:`** is the month of the week's Thursday (`week_month`). It is the single "parent month" property that Obsidian search and future views can query. No code in this design reads it.
*   **Every link resolves.** The tool creates the month notes before the week note, and a month note that exists but is Skipped still exists, so every link points to a real note. If a month note the week links to still doesn't exist after the month step (for example, `Monthly` is a file), a new week note is not created and is reported as `Skipped <vault>:<path>: month note Monthly/<YYYY-MM>.md missing`. There are no links to Daily notes, which may never be written.

#### Month note, `Monthly/2026-11.md`

```text
---
period: 2026-11
added: [close-books-2026-11]
tags: [monthly]
---
# November 2026

## Recurring
<!-- planner:recurring:start -->
- [ ] Close books — 2026-11-30 ^close-books-2026-11
<!-- planner:recurring:end -->

## Notes
```

#### Plan section, written by the `plan-week` skill

The skill builds the section from `tools/out/weekly-plan-<week-start>.md`, the file it already shows you. Each line of that file written by `plan_week.py` (`render` and `plan_line`) becomes one of the following:

| Line in `weekly-plan-<week-start>.md` | In the Plan section |
|---|---|
| `## Mon Nov 23` (a day header) | `### Mon Nov 23` |
| `## Didn't fit this week` | `### Didn't fit this week` |
| `- [ ] <title> — <N>m …` (a row) | `- <title without its vault label> — <N>m …`. The `- [ ] ` prefix is dropped; the rest of the row, such as ` · p1`, ` (due …)` or ` (overdue)`, is kept as written. |
| a line starting with `_` (meetings, capacity, the totals footer) | dropped |
| `- (open — no tasks assigned)` | dropped |
| `# Week of …` and blank lines | dropped |

After routing, a day header with no rows left for that vault is dropped. For example, for vault `arryved`:

```text
<!-- planner:plan-week:start -->
### Mon Nov 23
- billing: write migration plan — 90m · p1
- Draft the Q4 summary — 30m
### Didn't fit this week
- infra: rotate certs — 60m · p2
<!-- planner:plan-week:end -->
```

*   **Which vault a row goes to:** by the row's origin in `tools/out/tasks.json`, not by the text of its title.
    *   A row is a vault row when it starts with `- [ ] <title> — `, where `<title>` is the `title` of a `tasks.json` row with `"source": "vault"`. It goes to the vault named before the first `:` of that row's `task` field (`arryved:billing` → `arryved`), and the `<vault>:` label is removed from the title.
    *   Every other row (inbox, calendar or user items) goes to the current vault with its title unchanged, even when the title begins with another vault's name and a colon. For example, a user item `personal:budget: renew` planned from the `arryved` session stays in `arryved` as written.
    *   With one vault, every row goes to that vault.
    *   `plan_week.py` needs no change: `task_queue.py` already writes `source` and `task` on every vault row, and the skill already wrote `tasks.json` itself in the same run.
*   **Which vaults get a section:** every vault that `ensure` did not report as `Off`. The week note usually exists for those vaults even when its Recurring section was Skipped. The skill skips a vault only when its week note can't be edited: `ensure` printed no line for it, or a `Skipped` line whose reason is `not UTF-8`, an OS error, or `month note … missing`. A note Skipped for broken recurring markers or missing frontmatter still gets its Plan section, subject to its own plan-week marker check. The skill tells you which vaults' rows were not stored.
*   **No capacity figures.** `plan_week.py`'s "assigned" figure counts every vault's rows, so it would be wrong next to one vault's rows. The full figures stay in `weekly-plan-<week-start>.md`.
*   **What the section never holds:**
    *   meeting titles, which are calendar data;
    *   checkboxes, so a Plan row and an occurrence can never be two separate tick boxes.
*   **Week check:** before writing, the skill compares the Monday on `ensure`'s first line (§4) with the date in the `weekly-plan-<week-start>.md` filename. If they differ, it writes nothing and tells the user to re-run.
*   **Exact bytes are not part of the contract**, because the whole section is replaced on every run.
*   **Broken plan-week markers:** the skill writes nothing to that note and names the file. It treats any count other than exactly one start and one end marker as broken.

### 4. Rules the tool enforces

#### Opt-in

A vault is written only if `<vault>/Recurring.md` exists. For any other vault, `ensure` prints `Off <vault>: no Recurring.md` and writes nothing. That line is not a skip and doesn't change the exit code.

#### Note identity

The note for period P is `Weekly/P.md` or `Monthly/P.md`:
*   If it exists, it is used.
*   Otherwise it is created, together with its folder.

No other file is ever read or written (Non-Goal 8).

#### Markers

The Recurring section is writable only when the note's body has exactly one start marker and one end marker:
*   in that order;
*   each on its own line;
*   outside any fenced code block.

A fenced code block opens and closes with a line that starts, at column 0, with ```` ``` ```` or `~~~`. The same rule applies to the Recurrence list and to the `^ID` search below.

Otherwise the tool writes nothing to that note (CUJ 5).

`ensure` also counts the plan-week markers in a week note (month notes have none). It never writes them, but it prints a warning when their count isn't one pair. A damaged Plan section is then reported on the next run, even though the tool doesn't own that section.

#### Ledger

`added:` is read in either list form:
*   a flow list, `added: [a, b]`;
*   a block list: `added:` followed by `  - a` lines. Obsidian's Properties editor writes this form.

The tool always writes it back as a one-line flow list. These values are read as follows, with no warning:
*   an empty value (`added:` with no items), or `added: []`, is an empty ledger;
*   a scalar such as `added: foo` is a one-ID list;
*   quoted IDs are unquoted with the same rules as task-note frontmatter (`plugins/EGM.md`, "Task priority").

A line counts as carrying `^ID` only if `^ID` is its last token and the line is outside any fenced code block.

For each occurrence the period should have:

| ID in `added:`? | A line ending in `^ID` anywhere in the body? | Action |
|---|---|---|
| no | no | Append the line just before the recurring end marker, and add the ID to `added:`. |
| no | yes | Add the ID to `added:`. Leave the line alone. |
| yes | yes | Leave everything alone. |
| yes | no | You deleted it. Do nothing. |

The second row covers a note whose `added:` key was lost. When the key is missing, the tool prints a warning, because deletions made before the key was lost can't be known. When the key exists but lacks the ID, it prints no warning.

#### Dates

*   `ensure --date D` uses the week that contains D. `morning-startup` passes the `Now:` date, the same date it uses for the Daily note.
*   `ensure --plan-week [--week-start D]` uses the Monday that `planner_config.plan_days()` returns, with the same `--week-start` that the skill gives `task_queue.py` and `plan_week.py`. `D` must be a Monday.
    *   Like those tools, it reads today's date from the device clock. All three therefore pick the same week, and the skill never passes a date taken from another tool's output (`plan-week/SKILL.md`, "In this skill").
    *   On Sunday 2026-11-22 that week is W48.
*   **One week, all its months.** For a week, `ensure` processes every month note the week touches (in order), then the week note. Monthly occurrences are added to the month note for the month that contains their date. Weekly occurrences are added to the week note.

#### Writes

*   **Atomic:** each changed file goes through `planner_config.write_atomic`, the routine `triage.py` already uses, moved into the shared library:
    *   the text is written as bytes to a dot-prefixed temp file (`.period-*.tmp`) in the same folder, then renamed over the target with `os.replace`;
    *   an existing file keeps its mode, and a new file gets `0o666 & ~umask`;
    *   the temp file is removed if anything fails.
*   **Unchanged files stay untouched:** if the new text equals the old text, the file is not written, so its modification time stays the same.
*   **Line endings:** the tool edits the text as lines and keeps every existing line's ending. A note without a trailing newline keeps that. An inserted or rewritten line takes the ending of the note's first line. If that line has no ending, it takes `\n`.
*   **New notes** are written exactly as in §3. A note with no occurrences gets `added: []` and nothing between its recurring markers. Every new note ends with `## Notes\n`.

#### Output lines and exit codes

All output goes to stdout, one line per event.

| Event | Line |
|---|---|
| Always first | `Week <GGGG-Www> (Monday <YYYY-MM-DD>)` |
| A note written | `Wrote <vault>:<path>` |
| A note unchanged | `Unchanged <vault>:<path>` |
| Vault not opted in | `Off <vault>: no Recurring.md` |
| Recurring markers not exactly one pair | `Skipped <vault>:<path>: expected one recurring start/end marker pair, found start=S end=E` |
| Recurring markers out of order | `Skipped <vault>:<path>: recurring end marker comes before start marker` |
| An existing note with no frontmatter | `Skipped <vault>:<path>: no frontmatter (note not created by the planner)` |
| A note or `Recurring.md` that isn't UTF-8 | `Skipped <vault>:<path>: not UTF-8`. If it is `Recurring.md`, nothing is written to that vault. |
| A read or write fails (`OSError`) | `Skipped <vault>:<path>: <strerror>` |
| Plan-week markers not exactly one pair | `Warning <vault>:<path>: expected one plan-week start/end marker pair, found start=S end=E` |
| A bad Recurrence list line | `Warning <vault>:Recurring.md:<line>: <reason>`. The reason is one of `unknown rule '<rule>'`, `month <N> out of range 1–31`, `missing #id/`, or `does not match the line format`. |
| A duplicate ID | `Warning <vault>:Recurring.md: id '<id>' on lines <a>, <b>[, …]; all skipped` |
| `added:` missing | `Warning <vault>:<path>: added: missing; rebuilt from the body, so earlier deletions may come back` |
| A new week note whose month note is missing | `Skipped <vault>:<path>: month note Monthly/<YYYY-MM>.md missing` |

Exit codes:
*   `0`: no `Skipped` line.
*   `1`: at least one `Skipped` line. The other notes and vaults are still processed.
*   `2`: bad arguments, with a message that names the bad value. The vault and date checks are the ones `task_queue.py` uses today, moved into `planner_config.py`. The cases are:
    *   no `--vault`;
    *   a malformed `NAME=PATH`;
    *   a `NAME` given twice;
    *   a `PATH` that isn't a folder;
    *   a date that isn't `YYYY-MM-DD`;
    *   both `--date` and `--plan-week`, or neither;
    *   `--week-start` without `--plan-week`;
    *   `--week-start <D> is not a Monday`.

A note created by Periodic Notes from your own template has no frontmatter or no markers, so it is Skipped. The fix is in `docs/setup.md`: add the frontmatter and sections shown in §3 above, or delete the note and let the tool create it.

### 5. CLI

```text
period_note.py ensure --vault NAME=PATH [--vault ...] (--date YYYY-MM-DD | --plan-week [--week-start YYYY-MM-DD])
```

`NAME` is the vault's name in `vaults.json`, or `vault` when there is one unregistered vault, the same as for `task_queue.py`.

### 6. Contract and doc homes

*   **`plugins/EGM.md`** gets a new invariant, "Period notes". It covers:
    *   paths and the ISO label format `%G-W%V`;
    *   the Thursday rule;
    *   the markers and who writes each section;
    *   the occurrence line and ID format;
    *   the ledger;
    *   opt-in through `Recurring.md`.

    It also states that "Scheduled runs never touch the vault" still holds.
*   **`plugins/planner/tools/EGM.md`** names `period_note.py` as the one tool that writes in a vault: period notes only.
*   **`GLOSSARY.md`** gets Period note, Week note, Month note, Recurrence list (*avoid: hub*) and Occurrence. Owned section, Plan section, Recurring section and Ledger describe the mechanism, so they go only in the `plugins/EGM.md` invariant.

## Alternatives Considered

### Alternative A: Keep the plan in `tools/out`, add a link from the Daily note

*   **Pros**: No new notes, folders or tool. Tools still never write to a vault.
*   **Cons**:
    *   The plan stays outside the vault: it is unsynced and git-ignored.
    *   A link to a file outside the vault doesn't work on another device or in Cowork.
    *   Monthly items still have no home.
*   **Reason for Rejection**: It solves neither problem. Obsidian is meant to be the source of truth (Overview).

### Alternative B: Recurring items as task notes with a `recurs:` key

*   **Pros**: Recurring items reuse what task notes already have: `priority:`, `due:`, the board, `task_queue.py` ordering and the `task-*` skills.
*   **Cons**:
    *   Every occurrence needs its own task note, so a new file every week or month, and the backlog grows on its own.
    *   Every occurrence enters the status, board and priority contracts, none of which know about periods.
    *   Reusing one task note across occurrences loses the record of which months were done.
*   **Reason for Rejection**: It needs one new file per occurrence and changes to three existing contracts. Non-Goal 4 keeps occurrences as checklist lines.

### Alternative C: Recurring definitions inside each project or area hub

*   **Pros**: An item sits next to its project, such as "SLO review" in the SRE hub.
*   **Cons**:
    *   The tool would scan every hub on every run.
    *   "Hub" already means the note a task's `up:` points to (`GLOSSARY.md`).
    *   An item that belongs to no project would have no home.
    *   An `#id/` conflict would span files.
*   **Reason for Rejection**: One `Recurring.md` per vault is one file to read, one place where IDs must be unique, and the opt-in signal. A line can still name its project in its text.

### Alternative D: Replace the whole period note on every run

*   **Pros**: It needs no merge logic, and the note is a pure function of its inputs.
*   **Cons**: Every tick and every note you write is erased on the next run.
*   **Reason for Rejection**: It defeats the reason the note exists. Only the Plan section, which holds nothing of yours, is replaced whole.

### Alternative E: Match occurrences by their text instead of an ID

*   **Pros**: No `#id/` to type.
*   **Cons**: Renaming "Pay rent" to "Pay rent + utilities", or fixing a typo in a period note, makes the next run add a second line.
*   **Reason for Rejection**: Goal 4 requires one appearance per item. A hand-typed ID is the cost of a key that doesn't change with the text.

### Alternative F: Fill occurrences only when a note is created, with no ledger

*   **Pros**: The note holds no state, there is no `added:` key to damage, and the tool needs no ledger rules or tests.
*   **Cons**: A rule added partway through a week or month first appears in the next period's note. A rule added on the 2nd of the month waits about four weeks.
*   **Reason for Rejection**: That delay is long for monthly items. With the ledger, a new rule appears on the next run.

### Alternative G: Keep the ledger outside the note (a `.period-state.json` file)

*   **Pros**: Frontmatter stays clean, and editing properties can't damage the ledger.
*   **Cons**:
    *   The note and its state can drift apart.
    *   Moving, copying or syncing the note leaves the state behind.
    *   Each vault gets a second file to back up.
*   **Reason for Rejection**: Keeping the ledger in the note's own frontmatter means the note carries its own state. A lost `added:` key is handled by the second ledger row and its warning.

### Alternative H: Show monthly items as checkboxes in the week note too, kept in sync

*   **Pros**: You can tick everything for the week in one note.
*   **Cons**: Two checkboxes for one item need sync rules: which tick wins, what a deletion of one copy means, and what happens when the tool can't see both notes. That is sync logic with its own failure cases, the same kind as calendar sync (Non-Goal 2).
*   **Reason for Rejection**: Non-Goal 5. A week note links to its month notes instead (CUJ 3).

### Alternative I: Let scheduled runs write the notes

*   **Pros**: The notes would exist even in weeks when you never open a session.
*   **Cons**:
    *   It reverses "Scheduled runs never touch the vault" (`plugins/planner/EGM.md`).
    *   Cloud runs get no `Vault:` line.
    *   `vault-allow.py` doesn't approve Bash, so the write would wait on a permission prompt that nobody is there to answer.
*   **Reason for Rejection**: Non-Goal 1. Any interactive `morning-startup` in a week covers that week (CUJ 4).

### Alternative J: `period_note.py` also writes the Plan section from a plan JSON

*   **Pros**: Plan-section output becomes byte-reproducible and unit-tested.
*   **Cons**:
    *   `plan_week.py` would need a new JSON output with a schema.
    *   `task_queue.py` rows would need a `vault` key, which they lack today (`task_queue.py`, `build`).
    *   There would be a second subcommand, routing rules and an exact rendering grammar.
*   **Reason for Rejection**: The Plan section is replaced whole and holds nothing of yours, so being able to reproduce it byte for byte has little value. The skill already writes the Daily `## Plan` this way, and `ensure` reports damaged plan-week markers.

### Alternative K: Extend the habit tracker (`habits.json`) with weekly and monthly cadence

*   **Pros**: `habits.py` already tracks recurring commitments by ID.
*   **Cons**: It lives in the planner folder, not the vault. It records daily marks, not dated occurrences you can tick and annotate in a note.
*   **Reason for Rejection**: It doesn't put anything in the vault (Problem 2).

### Alternative L: Lock the vault while writing (`fcntl.flock`)

*   **Pros**: Two `period_note.py` runs can't interleave their writes.
*   **Cons**:
    *   The lock doesn't stop the realistic concurrent writers, Obsidian and sync clients.
    *   `fcntl` is POSIX-only, and it is unverified on a Cowork mount.
    *   It adds a dotfile to `Tasks/`, which the `tasks` plugin owns.
*   **Reason for Rejection**: Two planner runs at once is not a scenario any CUJ describes. Writes are atomic and `ensure` is idempotent, so in that case the last writer wins with the same text. See Risks.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Data safety.** Writing to the vault is the main new risk. Four rules limit it:
    *   one tool, `period_note.py`, writes Recurring sections and creates notes;
    *   writes are atomic, and unchanged files aren't written;
    *   a broken marker or missing frontmatter means no write;
    *   `update-vaults` adds `Recurring.md` only after you say yes, and never overwrites a file.
*   **Security and privacy.**
    *   `python3 tools/period_note.py` is approved the same way `task_queue.py` already is: by your answer to Claude Code's Bash permission prompt. There is no new permission rule.
    *   The skill's Plan-section edits go through Edit inside the vault, which `vault-allow.py` already approves.
    *   A vault receives only the vault rows whose `tasks.json` origin names it, plus non-vault rows in the current vault. Work task titles therefore stay in the work vault, and an item whose title merely looks labelled (`personal:budget: renew`) is not sent to another vault.
    *   Known limit, Daily notes only: the Daily `## Plan` routing still routes by the title's `<vault>:` label, so it keeps that mislabel case. Applying the same origin rule there is a Future Improvement.
*   **Token cost.** `plan-week` gains one block of about 15 lines, which holds the Plan-section rules. `morning-startup` gains one bullet. There is no new skill and no change to any skill description.
*   **Rollback.** Remove the skill paragraphs and the tool. The notes remain plain Markdown, and the HTML-comment markers are invisible in reading view. Deleting `Recurring.md` from a vault turns the feature off there.

### Risks and Mitigations

*   **Obsidian or a sync client writes the note at the same moment.**
    *   **Risk:** the tool reads, then replaces, a note that Obsidian has open with unsaved typing. Either the typing or the tool's added lines can be lost. A user edit saved between the tool's read and its `os.replace` is lost, including an edit outside the Recurring section. The design accepts this: there is no lock and no re-check before the rename (Alternatives Considered).
    *   **Mitigation:**
        *   The window between read and replace is milliseconds.
        *   Obsidian saves the whole file, so if it overwrites the tool, the new occurrence line and its `added:` ID are lost together, and the next run adds them again.
        *   How Obsidian handles an external change to a file with unsaved edits has not been checked. It is a manual step in the Verification Plan.
*   **The skill damages a plan-week marker.**
    *   **Risk:** the model writes the Plan section and breaks a marker line.
    *   **Mitigation:** `ensure` warns on the next run, and the skill refuses to write to a note whose markers are broken.
*   **The `added:` key is lost.**
    *   **Risk:** a hand edit or a frontmatter tool deletes `added:`.
    *   **Mitigation:** the key is rebuilt from the body, so nothing is duplicated. Deletions made before the key was lost come back once, with a warning.
*   **The week changes at midnight between steps.**
    *   **Risk:** `ensure --plan-week` runs on a Friday at 23:59 and `plan_week.py` runs on Saturday at 00:00. They then pick different weeks.
    *   **Mitigation:** the skill compares the Monday on `ensure`'s first line, `Week … (Monday <date>)`, with the date in the `weekly-plan-<week-start>.md` filename. If they differ, it writes no Plan section and tells you to re-run.
*   **Folder growth.** `Weekly/` gains 52 or 53 notes a year. The tool opens only canonical paths and never scans the folder.

### Additional Resources

*   [Brainstorm record](./week-month-notes/concepts_brief.md)
*   [Task priority and ranked project hubs](./task-priority-ranked-hubs.md): defines `task_queue.py`, `plan_days()` and the date-flag rules this design reuses.
*   [GLOSSARY.md](../../GLOSSARY.md)
*   [plugins/EGM.md](../../plugins/EGM.md), [plugins/planner/EGM.md](../../plugins/planner/EGM.md), [plugins/planner/tools/EGM.md](../../plugins/planner/tools/EGM.md)
*   Review reports, Stages 5–9, in `./week-month-notes/`: `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`, `intermediate_zoom_out_report.md`, `implementation_readiness_report.md` and `goldfish_review_report.md`.

### Future Improvements

*   Scheduled runs writing period notes. This needs a decision on which vault, which permission rule and which timezone.
*   Recurring items in the week plan, with their minutes taken from capacity (Non-Goal 4).
*   Vault-editable layout templates for period notes, and Base views of a week's Daily notes or a month's weeks.
*   Google Calendar or iCal export of occurrences and week plans.
*   More rule types (every N weeks, quarterly, yearly) and `month last-<day>`.
*   Finding renamed period notes through their `period:` key.
*   Occurrences as task notes (Alternative B), if checklist lines lack needed fields such as priority or a log.
*   Daily `## Plan` routing by row origin, using the same `tasks.json` match as the week Plan section, so a user item titled like `personal:budget: renew` stays in the current vault there too.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Version bumps:

| Package | From | To | Reason |
|---|---|---|---|
| `planner` | 0.7.0 | 0.8.0 | new tool and skill behavior |
| `tasks` | 0.8.0 | 0.8.1 | `obsidian-vault` skill prose only |
| `setup` | 0.1.0 | 0.2.0 | new `update-vaults` step |

`task-track` is unchanged.

### Phases

Each phase leaves the repository green. Run its check before starting the next phase.

| Phase | Entries | Check |
|---|---|---|
| 1. Shared library and tool | 1, 2, 3, 4, 5, 6 | `python3 -m unittest discover -s tests` |
| 2. Contracts and docs | 7, 8, 9, 10, 11, 12, 13 | none (prose only) |
| 3. Skills | 14, 15, 16, 17, 18 | `python3 -m unittest discover -s tests`; `claude plugin validate plugins/planner`; `claude plugin validate plugins/tasks` |
| 4. Installer | 19, 20, 21, 22, 23 | `python3 -m unittest discover -s tests`; `cd setup && uv run --locked pytest`; `cd setup && uv build` |
| 5. Versions and build | 24, 25 | `cd setup && uv run --locked pytest`; `bash scripts/build-plugin.sh`; `claude plugin validate .` |

### Target Files to Create/Modify

#### Phase 1: shared library and tool

##### 1. `plugins/planner/tools/planner_config.py` (Modify)

*   **Type / Scope**: Python library.
*   **Proposed Changes**:
    *   **ISO helpers**, next to `monday_of` and `plan_days`. Each uses `date.isocalendar()` and never `%W`.
        *   `iso_week(d: date) -> str`, in the form `2026-W48` (`%G-W%V`).
        *   `week_month(monday: date) -> str`: the `YYYY-MM` of `monday + 3 days`.
        *   `months_touched(monday: date) -> list[str]`: the distinct `YYYY-MM` values from Monday to Sunday, in order.
    *   **`write_atomic(path, text, prefix)`**, moved from `triage.py:79-92` with these changes:
        *   It takes a `prefix` argument.
        *   It writes `text.encode("utf-8")` through `os.fdopen(fd, "wb")`, so `\r\n` is written as is.
        *   A new file gets mode `0o666 & ~umask`. To read the umask, call `os.umask(0)`, then restore it straight away.
        *   Kept from the original: an existing file's mode is preserved, and the temp file is removed on any exception.
    *   **Argument helpers**, moved from `task_queue.py:54-61,269-294`:
        *   `iso_date(text)` and `parse_day(value, flag)`;
        *   `parse_vaults(values, require=())`. Its error messages and exit code 2 stay the same. The old `Tasks/` check becomes `require=("Tasks",)`.
        *   `fail(msg)`, which the three helpers above call to print `ERROR: <msg>` to stderr and exit 2.
*   **Why**:
    *   Every tool that names a week must agree on the label. `plan_days` already lives here for the same reason.
    *   The atomic write and the argument checks exist once today. A second tool would otherwise copy them.

##### 2. `plugins/planner/tools/triage.py` and `plugins/planner/tools/task_queue.py` (Modify)

*   **Type / Scope**: Python CLIs.
*   **Proposed Changes**:
    *   `triage.py`: delete `write_atomic` and import it from `planner_config`. Its call at `:153` passes `prefix=".inbox-"`.
    *   `task_queue.py`: delete `iso_date`, `parse_day`, `parse_vaults` and `fail`, and import all four from `planner_config`. `main` calls `parse_vaults(args.vault, require=("Tasks",))`.
    *   `tests/test_triage.py` setUp (`:21`): also copy `planner_config.py` into the temporary `tools/` folder, the way `tests/test_task_queue.py:58` already does. Otherwise `triage.py` fails to import.
*   **Why**: Entry 1. Neither tool's behavior changes. `tests/test_task_queue.py` must pass unchanged, and `tests/test_triage.py` must pass with only the setUp change.

##### 3. `plugins/planner/tools/period_note.py` (Create)

*   **Type / Scope**: Python CLI, standard library plus `planner_config`.
*   **Proposed Changes**: Implements Technical Plan §3–§5. Everything except `main` and `write_if_changed` is pure and takes text or lines.
    *   `parse_recurring(text) -> (rules, warnings)`:
        *   uses the §3 regex;
        *   ignores lines inside a fenced code block (§4);
        *   a line that contains `every:` but doesn't match produces a warning with one of the §4 reasons;
        *   a duplicate ID skips every line that carries it, with one warning.
    *   `occurrences(rules, kind, period) -> list[Occurrence(id, text, date)]`:
        *   weekly rules for a week label, monthly rules for a month label;
        *   `month N` past the month's end falls on the month's last day.
    *   `title_week(monday) -> str` and `title_month(label) -> str`: the §3 title formats, using fixed English day and month tables.
    *   `new_week_note(monday, occs) -> str` and `new_month_note(label, occs) -> str`: the exact §3 text.
    *   `read_added(fm_lines) -> AddedKey(ids, start, end) | None`: reads every form listed in §4. `start` and `end` are the frontmatter line indexes that hold the key.
    *   `write_added(lines, ids, key) -> lines`:
        *   replaces the key's lines with one flow-list line;
        *   if `key` is None, inserts the line after `month:`, else after `period:`, else as the last frontmatter line;
        *   the new line takes the ending rule from §4.
    *   `count_markers(body_lines, name) -> MarkerCount(start, end, start_idx, end_idx)`: counts only lines outside fenced code blocks.
    *   `apply_occurrences(lines, occs) -> (lines, warnings)`: applies the four-row ledger table from §4.
    *   `update_note(text, kind, occs) -> (text | None, lines_to_print)`: runs the whole rule set for one existing note. `None` means Skipped.
    *   `write_if_changed(path, text) -> "Wrote" | "Unchanged"`: calls `planner_config.write_atomic(path, text, prefix=".period-")` only when the text differs.
    *   `ensure(vaults, monday, out) -> int`:
        *   prints the `Week …` line first;
        *   then, for each vault in argument order: the §4 opt-in, each month the week touches, then the week note;
        *   catches `UnicodeDecodeError` and `OSError` for each note (§4) and keeps going;
        *   returns the exit code.
    *   `main(argv=None, today=None) -> int`:
        *   argument parsing, using `planner_config.parse_vaults(values)` and `parse_day`;
        *   every exit-2 case listed in §4;
        *   `--plan-week` uses `plan_days(today, week_start, include_weekend=False)[0]`;
        *   `--date` uses `monday_of`.

        Only the `if __name__ == "__main__":` guard reads the clock: `sys.exit(main(today=dt.date.today()))`.
*   **Why**:
    *   Creating notes and writing the Recurring section must merge the user's ticks and deletions, so that work lives in one tested tool.
    *   The tool doesn't reuse `task_queue.split_frontmatter`, because that function drops line endings (`task_queue.py:83`).

##### 4. `plugins/planner/tools/setup_check.py` (Modify)

*   **Type / Scope**: Python CLI.
*   **Proposed Changes**: Add `"period_note.py"` to the `needed` list at `:49-51`.
*   **Why**: Without it, `planner:setup` reports a planner folder that lacks the tool as healthy.

##### 5. `tests/test_planner_config.py` (Modify)

*   **Type / Scope**: Unit tests (unittest).
*   **Proposed Changes**:
    *   `iso_week`:

        | Date | Expected |
        |---|---|
        | 2026-11-22 | `2026-W47` |
        | 2026-11-23 | `2026-W48` |
        | 2026-12-28 | `2026-W53` |
        | 2027-01-03 | `2026-W53` |
        | 2024-12-30 | `2025-W01` |

    *   `week_month` for Monday 2026-11-30 (W49) is `2026-12`.
    *   `months_touched`:

        | Week | Expected |
        |---|---|
        | W48 | `["2026-11"]` |
        | W49 | `["2026-11", "2026-12"]` |
        | W53 (Monday 2026-12-28) | `["2026-12", "2027-01"]` |

    *   `write_atomic`:
        *   keeps an existing file's mode;
        *   gives a new file `0o666 & ~umask`;
        *   writes CRLF text unchanged;
        *   leaves no temp file after a failed write. Simulate the failure by patching `os.replace` to raise.
    *   `parse_vaults`:
        *   with `require=("Tasks",)`, it exits 2 on a missing `Tasks/`, as before;
        *   with `require=()`, it accepts a folder that has no `Tasks/`.
*   **Why**: These are the shared helpers that phase 1 adds.

##### 6. `tests/test_period_note.py` (Create) and `tests/test_setup_check.py` (Modify)

*   **Type / Scope**: Unit and integration tests.
*   **Proposed Changes** for `test_period_note.py`: one test for each §4 rule and each grammar form.
    *   **Approach:** the tests call `period_note.main(argv, today=…)` in-process on temporary vault folders, and the pure functions directly. One subprocess test checks that the `__main__` guard runs.
    *   **Grammar:**
        *   each rule form;
        *   `month 31` in November falls on Nov 30;
        *   `month first-tue`;
        *   lines inside a fenced code block are ignored;
        *   each §4 warning reason, with its line number;
        *   three lines with one ID → one warning, all three skipped;
        *   a `- [x]` line is read.
    *   **Opt-in:** a vault without `Recurring.md` prints `Off <vault>: no Recurring.md`, creates no folders, and exits 0.
    *   **Markers:**
        *   These cases are Skipped with the §4 text and exit 1, while the other notes and vaults are still processed:
            *   no markers;
            *   a lone start marker or a lone end marker;
            *   two pairs;
            *   the end marker before the start marker;
            *   markers that appear only inside a fenced code block.
        *   Exactly one pair is written.
        *   A broken plan-week pair in a week note gives a Warning only.
        *   A month note never gets a plan-week Warning.
        *   A note with no frontmatter is Skipped.
    *   **Ledger:**
        *   each of the four table rows;
        *   a block-list `added:` is read and rewritten as a flow list;
        *   `added:` empty, `added: []`, `added: foo` and quoted IDs;
        *   a missing `added:` gives a Warning and no duplicate;
        *   a `^ID` inside a fenced code block doesn't count.
    *   **New notes:** the bytes of a new week note and a new month note equal the §3 text, including `added: []` when there are no occurrences.
    *   **Repeat runs:** two `ensure` runs give identical bytes and the same mtime, and print `Unchanged`.
    *   **Line endings:**
        *   a CRLF note keeps CRLF;
        *   an appended occurrence line ends in `\r\n`;
        *   a note with no trailing newline keeps none.
    *   **Errors:**
        *   a note that isn't UTF-8 → Skipped `not UTF-8`;
        *   a `Recurring.md` that isn't UTF-8 → nothing is written to that vault;
        *   `Weekly` existing as a file → Skipped with the `OSError` text;
        *   `Monthly` existing as a file → the month note is Skipped with the `OSError` text, and no new week note is created (`month note … missing`).
    *   **Arguments:** each exit-2 case in §4 exits 2 and names the bad value.
    *   **Dates:**
        *   `--plan-week` with `today=2026-11-22` prints `Week 2026-W48 (Monday 2026-11-23)`;
        *   `--date 2026-12-07` prints W50;
        *   `--week-start 2026-11-25` exits 2.
    *   **Titles:** W48, W49 (two months) and W53 (two years).
    *   **CUJs:**
        *   CUJs 1, 3, 4 and 5 end to end;
        *   CUJ 2's ledger part is covered by the ledger and repeat-run tests. Its Plan-section part is checked by hand (Verification step 3).
*   **Proposed Changes** for `test_setup_check.py`: a planner folder without `period_note.py` is reported as missing scripts.
*   **Why**: The Coverage rule in the Verification Plan.

#### Phase 2: contracts and docs

##### 7. `plugins/planner/tools/EGM.md` (Modify)

*   **Type / Scope**: Module contract.
*   **Proposed Changes**:
    *   **Overview (`:14-15`):** change "The one exception is `task_queue.py`, …" to:
        > Two tools touch a vault, only at the `--vault` paths the skill passes: `task_queue.py` reads task notes and never writes them; `period_note.py` creates period notes and writes their Recurring sections, only in vaults that have `Recurring.md`.
    *   **Interface table:** add `period_note.py`, used by `plan-week` and `morning-startup`.
    *   **`planner_config.py` list:** add `iso_week`, `week_month`, `months_touched`, `write_atomic`, `iso_date`, `parse_day`, `parse_vaults` and `fail`.
    *   **Invariants (`:76`):** replace "`task_queue.py` is the one tool that reads a vault: …" with:
        > `task_queue.py` and `period_note.py` are the tools that read a vault, only from the `--vault` paths the caller gives. `task_queue.py` writes nothing there. `period_note.py` writes only `Weekly/<label>.md` and `Monthly/<label>.md` in vaults that have `Recurring.md`, atomically, and never rewrites an unchanged file.
    *   **New invariant**, modelled on `:79-81`:
        > `period_note.py` exits 0 when nothing was Skipped, 1 when a note was Skipped (the other notes and vaults are still processed), and 2 on bad arguments.
    *   **Side Effects:** add "`period_note.py` creates `Weekly/` and `Monthly/` notes and writes their Recurring sections in opted-in vaults."
    *   **Verification:** add `test_period_note`.
*   **Why**: The contract currently says only `task_queue.py` touches a vault.

##### 8. `plugins/planner/tools/README.md` (Modify)

*   **Type / Scope**: Human guide.
*   **Proposed Changes**:
    *   Add the row `| period_note.py | plan-week, morning-startup |` to the script table at `:6-17`.
    *   Replace `:31`, "`task_queue.py` is the one script that reads a vault, and only reads it:", with the Overview sentence from entry 7.
    *   Add a section, "Week and month notes", with the `ensure` command and an example `Recurring.md`.
*   **Why**: This is the guide a user reads in their own planner folder.

##### 9. `plugins/planner/README.md` (Modify)

*   **Type / Scope**: Plugin guide.
*   **Proposed Changes**: In the vault paragraph that lists what each skill writes (`:27-45`), add:
    > `plan-week` and `morning-startup` create week and month notes in vaults that have `Recurring.md`, and `plan-week` stores each vault's share of the week plan in its week note.
*   **Why**: `plugins/planner/EGM.md` requires that paragraph to match what the skills write.

##### 10. `plugins/planner/EGM.md` (Modify)

*   **Type / Scope**: Plugin contract.
*   **Proposed Changes**:
    *   **Module map:**
        *   add `period_note.py` to the tools list at `:12-13`;
        *   add `period_note.py` to the morning-startup line (`:26`) and the plan-week line (`:28`).
    *   **Count:** change "eleven `.py` files" (`:85`) to "twelve".
    *   **Invariant `:58-61`:** after "checks first that `tools/task_queue.py` exists", add:
        > `plan-week` also checks for `tools/period_note.py` and stops if it is missing; `morning-startup` skips its week-note step instead.
    *   **New invariant:**
        > Interactive `plan-week` and `morning-startup` create period notes only through `period_note.py`; `plan-week` writes a week note's Plan section with Edit.
    *   **Unchanged:** "Scheduled runs never touch the vault" stays as is.
    *   **Side Effects:** add `Weekly/` and `Monthly/`.
*   **Why**: Records the new write path and the rule that limits it.

##### 11. `plugins/EGM.md` (Modify)

*   **Type / Scope**: Cross-plugin contract.
*   **Proposed Changes**:
    *   Add the "Period notes" invariant with the contents listed in Technical Plan §6, including the mechanism terms: owned section, Plan section, Recurring section and Ledger.
    *   Add `Weekly/`, `Monthly/` and `Recurring.md` to Global Side Effects.
*   **Why**: The `tasks` plugin's `obsidian-vault` skill and any future reader, such as a calendar sync, depend on these formats.

##### 12. `GLOSSARY.md` (Modify)

*   **Type / Scope**: Domain glossary.
*   **Proposed Changes**: Add a `## Period notes` section after `## Hubs`, in the file's `**Term**:` / `_Avoid_:` format:
    *   **Period note**: A week note or a month note, created by the planner in a vault that has a Recurrence list.
    *   **Week note**: One note per ISO week, `Weekly/2026-W48.md`, holding that week's plan and weekly occurrences.
    *   **Month note**: One note per month, `Monthly/2026-11.md`, holding that month's monthly occurrences.
    *   **Recurrence list**: The vault's `Recurring.md`, one repeat rule per line. Having one turns period notes on. _Avoid_: hub.
    *   **Occurrence**: One dated checklist line made from a Recurrence list rule for one week or month.
*   **Why**: Technical Plan §6.

##### 13. `setup/src/planner_setup/EGM.md`, `setup/EGM.md` and `setup/src/EGM.md` (Modify)

*   **Type / Scope**: Installer contracts.
*   **Proposed Changes**:
    *   **`setup/src/planner_setup/EGM.md`:**
        *   `:86`: add "adding `Recurring.md`" to the list of questions;
        *   `:111`: add `Recurring.md` to "Writes into vaults".
    *   **`setup/EGM.md`:**
        *   `:11-13`: add the bullet "offers `Recurring.md`, which turns on week and month notes";
        *   `:26`: change the version to `0.2.0`.
    *   **`setup/src/EGM.md`:** in the `update-vaults` sentence at `:11`, add "and offers `Recurring.md`".
*   **Why**: These files list exactly what `update-vaults` asks and writes.

#### Phase 3: skills

##### 14. `plugins/planner/skills/plan-week/SKILL.md` (Modify)

*   **Type / Scope**: Skill prose, under `## Vault (optional)` → "In this skill".
*   **Proposed Changes**:
    *   **Stale-tools guard:**
        *   Keep the existing `task_queue.py` sentence word for word; `tests/test_skill_files.py:51-55` asserts it.
        *   Add this bullet after it:
            > If `<planner-path>/tools/period_note.py` is missing, the folder's tools predate this plugin version: say so, offer `planner:setup`, and stop.
        *   The stop is deliberate even for a user who hasn't opted in: one setup run refreshes every tool.
    *   **Period flags:** replace "Give both tools the same period flags: … `--include-weekend` when the user asked for them …" (`:151-153`) with:
        > Give `task_queue.py`, `plan_week.py` and `period_note.py` the same `--week-start` value when the user asked for one, and `--include-weekend` to `task_queue.py` and `plan_week.py` only; never pass one tool a date taken from another's output.

        Don't write the literal `--week-start <YYYY-MM-DD>`, which `tests/test_skill_files.py:38-39` forbids.
    *   **Add before the Pool bullet:**
        > **Week notes:** run `cd "<planner-path>" && python3 tools/period_note.py ensure --plan-week`, with one quoted `--vault "<name>=<vault-path>"` per vault in play. Report its `Wrote`, `Skipped` and `Warning` lines, naming each file and its fix. If it exits 2, report the message and skip the Plan-section writes below; the rest of the skill runs as usual.
    *   **Add after the Pool bullet:**
        > **Plan section:** after `plan_week.py`, for each vault that `ensure` did not print as `Off`:
        > - Compare the Monday on `ensure`'s first line with the date in the `weekly-plan-<week-start>.md` file name. If they differ, write nothing and tell the user to re-run.
        > - Skip the vault and name it if `ensure` printed no line for its `Weekly/…` note, or a `Skipped` line for it ending in `not UTF-8`, `month note … missing`, or an OS error. Other `Skipped` reasons concern only the Recurring section: still write the Plan section.
> - In the `Weekly/…` note `ensure` printed for that vault, replace only the text between `<!-- planner:plan-week:start -->` and `<!-- planner:plan-week:end -->`. If there isn't exactly one of each, leave the note alone and name it.
        > - Build the text from the weekly plan file: `##` headers become `###`, including `## Didn't fit this week`, which keeps its rows so they read as unscheduled; keep only rows starting `- [ ] `, drop that prefix and the `<vault>:` label, and keep the rest of the row as written; drop lines starting with `_`, `- (open`, and the `#` title.
        > - Route by origin, not by title text. A row is a vault row only when it starts with `- [ ] <title> — ` and `<title>` is the `title` of a `tools/out/tasks.json` row with `"source": "vault"`; it goes to the vault named before the first `:` of that row's `task`. Every other row goes to the current vault unchanged, even if its title starts with another vault's name and a colon. With one vault, it gets every row.
        > - The Plan section has no checkboxes and no meeting titles. Drop a day header that has no rows left.
        >
        > Then name each vault printed as `Off` and say that its rows were not stored.
    *   **Replace** `:156-157` ("Don't write future daily notes; the week plan stays in …") with:
        > Don't write future daily notes. Each opted-in vault's share of the week plan goes into its week note's Plan section, and the full plan stays in `tools/out/weekly-plan-<week-start>.md`. Only `period_note.py` writes the Recurring section.
    *   **Keep** the unattended-skip sentence (`:94-96`) as it is.
*   **Why**: Goals 1–4. The Plan-section rules must be in the skill, because the skill can't read this design at runtime.

##### 15. `plugins/planner/skills/morning-startup/SKILL.md` (Modify)

*   **Type / Scope**: Skill prose, the "In this skill" list under `## Vault (optional)` (`:138-169`).
*   **Proposed Changes**:
    *   **Add one bullet** after the `task_queue.py` stale-tools bullet (`:140-142`), which must stay first; `tests/test_skill_files.py:84-87` asserts `"In this skill: - "` followed by it:
        > **Week notes:** once, before step 2, run `cd "<planner-path>" && python3 tools/period_note.py ensure --date <the Now: date>` with one quoted `--vault "<name>=<vault-path>"` per vault in play. Report only its `Skipped` and `Warning` lines. If `tools/period_note.py` is missing, say in one line that the tools are out of date and go on.
    *   **Don't touch** the existing week-plan row filter.
*   **Why**: Goal 5. Unlike `plan-week`, a missing tool doesn't stop this skill, because a missing week note shouldn't block planning the day.

##### 16. `plugins/planner/skills/setup/SKILL.md` (Modify)

*   **Type / Scope**: Skill prose.
*   **Proposed Changes**:
    *   Change "Eleven" (`:52`) and "eleven" (`:63`, `:66`) to "Twelve" and "twelve".
    *   At `:63-64`, change "including `planner_config.py` and `task_queue.py`" to "including `planner_config.py`, `task_queue.py` and `period_note.py`".
    *   Add `tools/period_note.py` to the "Tools older than the bundled ones" sentence (`:72`).
*   **Why**: Keeps the planner folder complete.

##### 17. `plugins/tasks/skills/obsidian-vault/SKILL.md` (Modify)

*   **Type / Scope**: Skill prose.
*   **Proposed Changes**:
    *   **Folder table (`:20`):** add two rows.

        | Folder | What | Template |
        |---|---|---|
        | `Weekly/` | `2026-W48.md` (ISO year, `W`, two-digit ISO week), one per week, created by the planner. No `up:`. | — |
        | `Monthly/` | `YYYY-MM.md`, one per month, created by the planner. No `up:`. | — |

    *   **Below the table:** add "Files at the vault root: `Recurring.md`, the Recurrence list (one repeat rule per line; having it turns on week and month notes)."
    *   **Linking rule:** add "Period notes and `Recurring.md` are the exceptions to 'every note links up once via `up:`'."
    *   **Verify step:** change the `deadends` comment (`:64`, "only Inbox may appear") to "only Inbox, Monthly/* and Recurring.md may appear", and the expected result (`:68`) to `VERIFY: unresolved=0, deadends=Inbox, Monthly/*, Recurring.md only`.
    *   **New rule:** "Never edit inside a period note's owned sections (between `<!-- planner:… -->` markers) or its `added:` key. Write outside them."
*   **Why**: The folder rule ("Don't invent new top-level folders") and the linking and verify rules would otherwise flag period notes as mistakes.

##### 18. `tests/test_skill_files.py` (Modify)

*   **Type / Scope**: Prose checks.
*   **Proposed Changes**:
    *   **`PlanWeekTest`:**
        *   `test_vault_block_checks_for_a_stale_tools_folder_first` stays unchanged.
        *   A new test asserts the `period_note.py` stale-tools sentence from entry 14 word for word.
        *   A new test asserts that the vault block contains `period_note.py ensure --plan-week`, `<!-- planner:plan-week:start -->`, "no checkboxes" and "Route by origin, not by title text".
        *   A new test asserts that `--include-weekend` is given "to `task_queue.py` and `plan_week.py` only".
        *   The unattended-skip test stays unchanged.
    *   **`MorningStartupTest`:**
        *   A new test asserts that the block contains `period_note.py ensure --date`.
        *   The count of `"source": "vault"` stays at two, because the week-plan row filter is unchanged.
    *   **`SetupSkillTest`** (a new class): the setup skill contains "twelve" and `period_note.py`, and `"eleven" not in text.lower()`.
    *   **`ObsidianVaultTest`** (a new class): the folder table lists `Weekly/` and `Monthly/`, and the skill names `Recurring.md`.
*   **Why**: Every existing test in this file asserts literal phrases. These assertions pin the phrases from entries 14–17.

#### Phase 4: installer

##### 19. `examples/vault-starter/Recurring.md` (Create)

*   **Type / Scope**: Vault note.
*   **Proposed Changes**:
    *   A header of three short lines saying what the file does and that each rule is one line, with the format shown in the block below.
    *   The header never contains `every:` outside a fenced code block.
    *   A fenced code block holds two example rules, so they aren't read:
        *   `- [ ] Weekly review (~30 min) — every: mon #id/weekly-review`
        *   `- [ ] Pay rent — every: month 1 #id/rent`
    *   No active rules.
*   **Test:** add to `tests/test_period_note.py` a test that this file produces no warnings and no rules. It belongs to this phase because the file doesn't exist before it.
*   **Why**: `seed_vault` copies the starter vault. A new vault is therefore opted in from the start, and the tool adds no occurrences until the user writes a rule.

##### 20. `setup/src/planner_setup/actions.py` (Modify)

*   **Type / Scope**: Installer.
*   **Proposed Changes**: Add a new step, `_add_recurring(ctx, vault)`, called from `update_vaults` after `_replace_hub_tasks` (`:391`). Messages go through `ctx.say`.
    *   **`<vault>/Recurring.md` exists:** say nothing and return.
    *   **`--dry-run`:** say `Would ask to add Recurring.md to <vault> (turns on week and month notes).`
    *   **Otherwise:** call `ctx.yes or ctx.confirm("Add Recurring.md to <vault>? This turns on week and month notes there.")`.
        *   On yes, `shutil.copyfile(paths.examples() / "vault-starter" / "Recurring.md", vault / "Recurring.md")`, then say `Added Recurring.md to <vault>.`
        *   On no, say `Kept <vault> without Recurring.md (week and month notes stay off).`
    *   **No backup:** the step only creates a file that is absent.
    *   **`update_vaults` docstring:** list the new step.
*   **Why**: Goal 6. The step follows the confirm and dry-run pattern of the existing steps (`:220-221`, `:359-362`).

##### 21. `setup/src/planner_setup/cli.py` (Modify)

*   **Type / Scope**: Installer CLI.
*   **Proposed Changes**: Add "offers Recurring.md (week and month notes)" to the `update-vaults` help text (`:34-36`). The menu label stays as it is.
*   **Why**: The help text lists what the command does.

##### 22. `setup/tests/test_actions.py` (Modify)

*   **Type / Scope**: Unit tests (pytest).
*   **Proposed Changes**:
    *   **Modify two tests so they compare only download questions,** with `[q for q in asked if q.startswith("Download ")]`, the same filtering pattern that `hub_questions` uses at `:684-685` (which filters on a different prefix):
        *   `test_update_vaults_asks_before_download` (assertion at `:440`);
        *   `test_update_vaults_adds_the_template_keys_without_a_prompt` (assertion at `:609`).
    *   **Add a `recurring_questions(asked)` helper and these tests:**
        *   On a yes, `Recurring.md` is added and its bytes equal the starter's.
        *   On a no, nothing is added and the "Kept … without Recurring.md" line is printed.
        *   With an existing `Recurring.md`, the file stays byte-identical and no Recurring question is asked.
        *   `--dry-run` writes nothing and prints the "Would ask" line.
        *   `--yes` adds the file.
*   **Why**: Goal 6. Without these changes, the new prompt would break the two existing tests.

##### 23. `docs/setup.md` (Modify)

*   **Type / Scope**: User docs.
*   **Proposed Changes**: Add one section covering:
    *   opting a vault in with `Recurring.md`;
    *   the line format;
    *   what `update-vaults` asks;
    *   the Periodic Notes `GGGG-[W]WW` advice;
    *   how to fix a Skipped note: add the §3 frontmatter and sections, or delete the note so the tool recreates it.
*   **Why**: `AGENTS.md` requires `docs/setup.md` to stay in step with `setup/`.

#### Phase 5: versions and build

##### 24. Version files (Modify)

*   `plugins/planner/.claude-plugin/plugin.json`: 0.8.0.
*   `plugins/tasks/.claude-plugin/plugin.json`: 0.8.1.
*   `setup/pyproject.toml`: 0.2.0.
*   Run `cd setup && uv lock`, and commit the regenerated `setup/uv.lock`. Never edit it by hand. CI runs `uv run --locked pytest`, which fails if the lock still says 0.1.0.
*   **Why**: `AGENTS.md` requires a version bump for every changed plugin, and `setup` gains a new step.

##### 25. `planner.plugin` (Rebuild)

*   Rebuild with `bash scripts/build-plugin.sh` after the planner changes. Never edit it by hand.
*   **Why**: `planner.plugin` is the committed Cowork upload and must match `plugins/planner`.

### Verification Plan

*   **Unit tests**:
    *   `python3 -m unittest discover -s tests`;
    *   `cd setup && uv run --locked pytest`.
*   **Build**:
    *   `cd setup && uv build`;
    *   `bash scripts/build-plugin.sh`.
*   **Static checks**:
    *   `claude plugin validate plugins/planner`;
    *   `claude plugin validate plugins/tasks`;
    *   `claude plugin validate .`.
*   **Manual, in a scratch copy of `examples/vault-starter`**:
    1. Add two weekly rules and one `month last` rule to `Recurring.md`. Use a second scratch vault too, and add a user item titled `<second-vault>:x: test` when `plan-week` asks for items.
    2. Run `plan-week` interactively twice. Check that the second run reports no `Wrote` lines from `ensure`, and that the Plan section is replaced, not appended. Check that the `<second-vault>:x: test` item is in the current vault's Plan section with its title unchanged, and not in the second vault's.
    3. Tick one weekly occurrence and delete the other, then copy the week note, then run `plan-week` again. Run `git diff --no-index <copy> Weekly/<label>.md` and check that only the Plan section changed (CUJ 2).
    4. In Obsidian, check that:
        *   the markers are hidden in reading view;
        *   the `Months:` and `month:` links resolve;
        *   after you edit a property, `added:` becomes a block list, and the next run reads it, writes it back as a flow list, and re-adds no deleted occurrence.
    5. With the week note open in Obsidian and unsaved typing in it, add a new rule and run `ensure`. Record what Obsidian does (Risks, first item).
*   **Coverage**: every ledger row, marker case, output line and exit-2 case in §4 has a test. Coverage is judged by that rule, not by a percentage.

*Drafted with EGM*
