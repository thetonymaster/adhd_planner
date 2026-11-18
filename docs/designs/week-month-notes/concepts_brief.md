# Week and Month Notes in the Vault

* **Author:** Antonio Cabrera
* **Date:** 2026-11-17

## Overview

`plan-week` builds a weekly plan, but the plan is written to `tools/out/weekly-plan-<week-start>.md` in the planner folder, outside any vault. Once the week ends it is gone. Things that happen every month have nowhere to live.

This feature gives each vault two kinds of dated notes next to `Daily/`:

- `Weekly/2026-W47.md`: one note per ISO week, starting Monday.
- `Monthly/2026-11.md`: one note per month.

When `plan-week` runs, it finds the note for the week it is planning, or creates it from a template, and replaces only a section it owns. That section sits between two HTML-comment markers. Text you write outside the markers is never touched. A second run in the same week changes the same section of the same file. It never creates a second file or a second copy of an item.

Recurring weekly and monthly items are defined once per vault. Each week note or month note gets that period's dated copies of them.

Obsidian is the source of truth. Google Calendar and iCal sync come later.

## Analysis

Six Goldfish reviewers covered design, codebase details, scope, comprehension, implementation readiness and structure. All six agreed the concept fits the existing Daily-note pattern. All six also agreed it cannot ship as one piece.

### Blockers

1. **Scheduled runs writing to the vault reverses a written rule.** Four places say a scheduled run writes nothing to a vault:
   - `plugins/planner/EGM.md:55`: "Scheduled runs never touch the vault"
   - `plan-week/SKILL.md:95`: skip the vault section when the run is unattended
   - `plan-week/SKILL.md:156`: the week plan "stays in tools/out"
   - `plugins/planner/tools/EGM.md:76,103`: no planner tool writes to a vault

   On top of that, unattended cloud runs get no `Vault:` line, and `vault-allow.py` auto-approves only file tools. A Python tool that writes to the vault through Bash would stop at a permission prompt that nobody is there to answer. Either change all of these on purpose, or leave scheduled writes for a later slice.
2. **"No duplicates" cannot be tested yet.** An item needs an identity that stays the same between runs. Matching on a line's text breaks as soon as you edit the line. If you delete an occurrence and the next run puts it back, that is a duplicate in spirit, so the tool must also remember deleted occurrences (a "tombstone").
3. **Replacing a section erases what you did inside it.** Ticked `[x]` boxes and notes you typed inside the owned section would be wiped on the next run. The proposed fix is two separate marked sections:
   - a **plan section** the tool replaces every run, treated as read-only output;
   - an **occurrences section** the tool only adds to, keyed by an ID, so ticks survive.
4. **The rules belong in one tested tool, not in skill prose.** Proposed: `tools/period_note.py`. It creates files atomically, writes each change to a temp file and then renames it into place, takes a lock, and has tests under `tests/`. The ISO week and Thursday helpers go in `planner_config.py`. It would be the first planner tool that writes to a vault. Users' copied `tools/` folders will be out of date, so a skill that can't find the tool stops and offers `planner:setup`. That is the same guard `task_queue.py` already uses.
5. **The tool needs a rule for broken markers.** Cases include zero markers, a single marker, two pairs, markers in the wrong order, and markers inside a code block. Rule: anything other than exactly one well-formed pair means write nothing and warn. Marker shape: `<!-- planner:plan-week:start -->` / `<!-- planner:plan-week:end -->`.

### Major

- **Recurring meetings would be counted twice.** `plan-week` already reads meetings from Google Calendar to work out each day's free time. If meetings are also defined in the vault, they count twice and the two copies drift apart. Until calendar sync exists, a vault meeting is a reminder only and never counts against free time. The other option is to keep meetings out of the vault entirely for now.
- **"Hub" already means something.** The glossary defines a hub as the project or area note that a task's `up:` points to. The note that defines recurring items needs another name, such as "Recurrence list". That note must also not look like a period note, so `Weekly/Weekly.md` is out.
- **One plan across several vaults has to be split.** `plan_week.py` builds one plan whose rows carry `<vault>:<slug>`. Each vault's week note gets only its own rows. Rows from the calendar or the inbox go to the default vault. Week notes never link across vaults.
- **Which week, by which clock.** On Saturday and Sunday, `plan-week` plans *next* week. For example, a run on Sunday 2026-11-22, which is in W47, writes the plan into `2026-W48.md`. So the note follows the planned week's start date, not today's date. There are also two timezone settings (`vaults.json` and `calendars.json`), while `plan_week.py` uses the system date. Pick one setting and pass the date in explicitly.
- **ISO year edge cases.** Use `isocalendar()` / `%G-W%V`, never `%Y-W%W`. 2026 has a week 53 (Dec 28 to Jan 3). The Obsidian Periodic Notes plugin's default format, `gggg-[W]ww`, depends on locale and would create a second file, so recommend `GGGG-[W]WW` if you use that plugin. Sync conflict copies such as `2026-W47 2.md` must be detected and never written to. A `period: 2026-W47` frontmatter key gives the tool a second way to identify the note if the file is renamed.
- **Existing vaults.** `seed_vault` never overwrites anything. An additive `update-vaults` step adds the new templates, with a backup and a dry run, and the tool falls back to a built-in template if none is present. `Weekly/` and `Monthly/` are created only when first needed, and vault detection keeps checking only `Tasks/` and `Daily/`.
- **`tools/out` stays.** `morning-startup` and `plan-day` read `week-tasks-<date>.json`. The vault note is the copy you keep, and it is a snapshot of the plan, not a binding schedule.
- **Occurrences start as checklist lines, not task notes.** Task notes would add every occurrence to the task pool, the board, the status lifecycle and the priority ordering, and the backlog would grow every week.

### Small items

- Pin the template placeholders `{{week}}`, `{{month}}` and `{{monday}}`. The current replacers handle only `{{date}}` and `{{title}}`.
- The tool prints `Wrote <path>` or `Unchanged <path>` for each vault, so you can see a run that changed nothing in the run history.
- Release work:
  - version bumps for planner, tasks and setup;
  - rebuild `planner.plugin`;
  - update `docs/setup.md`;
  - add the Weekly and Monthly rows to the folder table in `obsidian-vault`;
  - extend `tests/test_skill_files.py`.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  1. Each vault gets one ISO-week note (`Weekly/GGGG-[W]WW.md`, Monday start) that holds `plan-week`'s output in a marked section. Text outside the section is never touched.
  2. A re-run in the same period changes nothing: no second file, no second section, no repeated item. A tested tool enforces this.
  3. Month notes (`Monthly/YYYY-MM.md`). A week links up to the month that contains its Thursday.
  4. Recurring weekly and monthly items are defined once per vault and added as dated checklist lines keyed by ID. This is a later slice.
  5. Existing vaults get the templates and folders through an additive `update-vaults` step.
* **Out-of-Scope Non-Goals:**
  1. Google Calendar and iCal sync. Vault meetings never count against free time.
  2. Merging, linking or rolling up across vaults.
  3. Occurrences as task notes.
  4. Replacing the `tools/out` JSON that `plan-day` and `morning-startup` read.
  5. Requiring the Periodic Notes or Templater community plugins.

## Key Decisions & Staging for Next Steps

**Decided with Q:**
- Obsidian first; calendar sync later.
- One set of notes per vault.
- ISO weeks, Monday start.
- A re-run replaces only the skill's own section.
- No duplicates, ever.
- Only interactive runs write to the vault in the first release. Scheduled runs keep writing only to `tools/out`, and the rule "scheduled runs never touch the vault" stays as written. Scheduled vault writes are slice 4 and need their own decision on the vault, the permission rule and the timezone.

**Proposed defaults, still to confirm:**
1. **Write mechanism.** A new `tools/period_note.py` that takes `--vault NAME=PATH`, writes atomically under a lock, and ends with the line `Wrote|Unchanged <path>`. The ISO helpers go in `planner_config.py`.
2. **Where the rules live.** A new "Period notes" rule in `plugins/EGM.md` covering paths, the Thursday rule, marker shape, ID format and which skills write. It also changes the rule that tools never write to a vault. New glossary terms: Week note, Month note, Owned section, Recurrence list, Occurrence.
3. **Markers.** HTML comments, one pair per skill. Anything other than exactly one well-formed pair: write nothing and warn.
4. **Section policy.** The plan section is replaced on every run. The occurrences section is add-only, keyed by an Obsidian block ID (`^r-<rule>-<YYYYMMDD>`), with tombstones for deleted occurrences.
5. **Which period.** The note follows the planned week's start date. The date comes from one timezone source and is passed in explicitly.

**Open questions:**
1. ~~Do scheduled runs write to the vault in the first release?~~ Decided: no, interactive runs only (see above).
2. What is the format of a recurrence definition (for example `monthly: 1 | last | first-mon`), and what is the note called?
3. When a definition is edited or deleted partway through a period, do occurrences already written stay as they are, while future ones are regenerated?
4. A monthly item can fall in a week that belongs to the other month (for example Mon 2026-11-30, which is in W49, a December week). Proposed: it goes into the month note by its own date. The Thursday rule is used only to link a week to its month.
5. Which skills write which sections? Do `morning-startup` and `eod-shutdown` write, or only read? Do week notes and Daily notes link to each other?

**Proposed slices:**
1. Period-note rules, `period_note.py`, the Weekly template, and `plan-week` writing when you run it yourself. This alone fixes the lost-plan problem.
2. Month notes and their sections.
3. Recurrence list, plus add-only occurrence lines keyed by ID.
4. Scheduled runs writing to the vault, after the rule change in Blocker 1.
5. Occurrences as task notes (possibly never).
