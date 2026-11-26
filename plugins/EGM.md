# plugins

## Overview

The three plugins of the `adhd-planner` marketplace
(`.claude-plugin/marketplace.json` at the repo root). `planner` and `tasks` work in
Claude Code and Cowork; `task-track` is a Claude Code–only mod. They share the user's
Obsidian vault (task notes under `Tasks/`, daily notes under `Daily/`) but import no
code from each other: each is installed and versioned on its own.

## Subdirectories & Boundaries

- planner: [./planner/EGM.md](./planner/EGM.md) - twelve planning skills plus the
  seed copy of their Python tools ([planner/tools/EGM.md](./planner/tools/EGM.md)),
  which `/planner:setup` copies into the user's planner folder.
- tasks: [./tasks/EGM.md](./tasks/EGM.md) - eight task-note skills (create-task,
  task-start, task-switch, task-park, task-finish, task-note, task-list, obsidian-vault)
  and hooks: session-start task injection, `Now:` stamps, parking the session's task on
  session end, vault permission auto-approval ([tasks/hooks/EGM.md](./tasks/hooks/EGM.md)).
- task-track: [./task-track/EGM.md](./task-track/EGM.md) - band, `/task`, `/board` and
  `/project-tasks` panes, `/note` `/done` `/openloop` `/pomo` and the shared Pomodoro
  ([hooks](./task-track/hooks/EGM.md), [types](./task-track/types/EGM.md)).

## Global Invariants

- Vault and task resolution is one contract implemented twice:
  `tasks/hooks/vaults.py` + `session_task.py` (Python) and
  `task-track/hooks/resolve.ts` (TypeScript), with shared cases in
  `task-track/tests/fixtures/vault-cases.ts`, and restated in prose at the top of the
  `tasks` skills create-task, task-start, task-switch, task-park, task-finish and
  obsidian-vault. Order: vault from `$ADHD_PLANNER_VAULTS` / `~/.config/adhd-planner/vaults.json`
  (session choice → `repo:` match → `folders` match → `default`), else `vaultPath`
  option → `$VAULT` → `~/vault`; task from `Tasks/.session/<session-id>` → non-`done`
  note whose `repo:` holds the cwd → `Tasks/.active`. `vault-cases.ts` is run by the TS tests
  and `tests/test_load_task.py`. Known gap: `vaults.py` resolves symlinks, `resolve.ts` does not
  (accepted: the mod API has no realpath). task-note and task-list (Cowork has no hook) find
  the vault by the multi-vault spec's lookup instead: `Vault:` line → `vaults.json` default →
  a folder named `vault` or holding `Tasks/` and `Daily/` → `$VAULT` → `~/vault` (no
  `vaultPath` step).
- A task slug read from a vault file (`.active`, `.session/*`, `.pomo.json`) or used to build a
  note path matches `^[a-z0-9][a-z0-9-]*$` on every production path (`slug_or_empty` in Python,
  including `park_on_end.py`; `isSlug`/`taskNotePath` in TypeScript, and `projectTasks` filters
  candidates by `isSlug`; the test-only `pickTask` does not check). The board lists notes by
  file name and builds no path from a slug.
- Task status lifecycle, one vocabulary across plugins: frontmatter `status:` is `active`
  (task-start, task-switch), `parked` (create-task, task-park, task-switch via task-park,
  `park_on_end.py` on session end except `/clear`) or `done` with `finished: YYYY-MM-DD`
  (task-finish). Resolution skips `done` notes; the task-track board shows Doing (`active`),
  Parked (`parked`) and Done (`done` finished in the last 7 days, today included); the
  project-tasks pane lists any non-`done` status other than `active` as parked.
- Task priority, one note contract across plugins (spec:
  `docs/designs/task-priority-ranked-hubs.md`, Technical Plan §1–2). Frontmatter keys, both
  optional plain scalars, `priority:` written directly after `up:` (no `up:` → after
  `status:`; neither → first frontmatter line) and `due:` directly after `priority:`
  (`setup` `_with_priority_keys` and `task-note` follow this): `priority:` is exactly one of `p0`
  (do first, ahead of dated tasks) .. `p5` (someday), absent/empty/invalid read as `p3`
  (invalid values warned about); `due:` is `YYYY-MM-DD` or empty, a hard limit on placement,
  invalid read as no date (warned). Frontmatter is the lines between a first-line `---` and
  the next `---`; a scalar is the text after `key:`, trimmed, trailing ` # comment` and one
  pair of matching quotes removed. A task's next work is the open Next items under `## Next`
  (up to the next `## ` line): lines starting, after indentation, with `- [ ] ` plus text,
  nested ones included, each estimated as a trailing `(~N min)` or `(~N h)` (hours to
  minutes, rounded up per item); any open item without an estimate means `needs an
  estimate`, none means `no Next item`. Ordering key: tier (0 `p0`, 1 `due` <= end of the
  planning window including overdue, 2 otherwise), then `due` for tiers 0–1, then priority
  number, then `started` (older first, undated last), then `<vault>:<slug>`. Writers:
  `create-task` and `task-start` write `priority` (default `p3`, never asked for) and `due`
  only when given; `task-note` sets either on an existing note. Readers must not choke on
  unknown keys (`vaults.py`, `resolve.ts` pick fields by name).
  `plugins/planner/tools/task_queue.py` holds the only coded copy of the ordering rule.
- Period notes, one vault contract (spec: `docs/designs/week-month-notes.md`, Technical
  Plan §3–§4). Opt-in: only a vault with a Recurrence list (`<vault>/Recurring.md`) gets
  period notes; any other vault is never written. Paths: week note `Weekly/<GGGG-Www>.md`
  (ISO label `%G-W%V`, e.g. `2026-W48`), month note `Monthly/<YYYY-MM>.md`. Thursday rule:
  a week note's `month:` is the month of the week's Thursday; its `Months:` line links every
  month the week touches, and those month notes are created before the week note. Owned
  sections, each between one start and one end marker on their own lines outside fenced
  code (a line starting at column 0 with ```` ``` ```` or `~~~`): the Plan section
  (`<!-- planner:plan-week:start -->` … `:end -->`, week notes only) is written by the
  `plan-week` skill, which replaces it whole; the Recurring section
  (`<!-- planner:recurring:start -->` … `:end -->`) is written only by
  `plugins/planner/tools/period_note.py`, which skips a note whose recurring markers aren't
  exactly one start then one end, or that has no frontmatter. The rest of a period note is
  the user's. Recurrence list line: `- [ ] <text> — every: <rule> #id/<id>` (`<rule>`:
  `mon`..`sun`, `month <1-31>`, `month last`, `month first-<mon..sun>`). Occurrence line:
  `- [ ] <text> — <YYYY-MM-DD> ^<id>-<period>`, `<period>` the lowercased label
  (`^weekly-review-2026-w48`, `^close-books-2026-11`); a line carries an ID only when `^ID`
  is its last token outside fenced code. Ledger: frontmatter `added:` lists every occurrence
  ID ever added (read as a flow list on one line or several, a block list (comments and blank
  lines between items allowed), empty, a scalar, quoted IDs as in "Task priority"; written back
  as one flow-list line; a flow list whose `]` never comes before the next key or the end of
  the frontmatter makes the note Skipped, never guessed); an ID in the ledger is never re-added, so
  a deleted occurrence stays deleted. `period_note.py` keeps each line's ending and leaves
  unchanged files untouched. "Scheduled runs never touch the vault"
  (`planner/EGM.md`) still holds: only interactive `plan-week` and `morning-startup` run
  `period_note.py`.
- Bump `version` in a plugin's `.claude-plugin/plugin.json` when it changes; run
  `claude plugin validate plugins/<name>` after every edit under it.
- `planner.plugin` (repo root) is built from `plugins/planner` by
  `bash scripts/build-plugin.sh`; never edit it by hand.

## Global Side Effects

- User's Obsidian vault: task notes (including `status:` flips by `park_on_end.py` at
  session end), `Tasks/.active`, `Tasks/.session/*`, `Tasks/.pomo.json` (and its lock file `Tasks/.pomo.flock`, or folder `Tasks/.pomo.lock` without perl), daily notes
  (`Daily/<date>.md` focus lines from task-track), period notes `Weekly/` and `Monthly/`
  (`period_note.py` and the `plan-week` skill, only in a vault that has `Recurring.md`) and
  `Recurring.md` itself (written by the user, or seeded by `planner-setup`).
- task-track's `/task` pane "Open in Obsidian" button runs `open obsidian://open?path=…`.
- User's planner folder: `inbox.md`, `inbox-archive.md`, `habits-log.json`, and `tools/out/`
  files written by the planner tools.
- Google Calendar through the calendar MCP (planner skills only; scripts never call it).

## System Verification

- Run (repo root): `python3 -m unittest discover -s tests`
- Run: `cd plugins/task-track && claude plugin test .`
- Run: `claude plugin validate plugins/planner`, `plugins/tasks`, `plugins/task-track`
