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
- Bump `version` in a plugin's `.claude-plugin/plugin.json` when it changes; run
  `claude plugin validate plugins/<name>` after every edit under it.
- `planner.plugin` (repo root) is built from `plugins/planner` by
  `bash scripts/build-plugin.sh`; never edit it by hand.

## Global Side Effects

- User's Obsidian vault: task notes (including `status:` flips by `park_on_end.py` at
  session end), `Tasks/.active`, `Tasks/.session/*`, `Tasks/.pomo.json` (and its lock file `Tasks/.pomo.flock`, or folder `Tasks/.pomo.lock` without perl), daily notes
  (`Daily/<date>.md` focus lines from task-track).
- task-track's `/task` pane "Open in Obsidian" button runs `open obsidian://open?path=…`.
- User's planner folder: `inbox.md`, `inbox-archive.md`, `habits-log.json`, and `tools/out/`
  files written by the planner tools.
- Google Calendar through the calendar MCP (planner skills only; scripts never call it).

## System Verification

- Run (repo root): `python3 -m unittest discover -s tests`
- Run: `cd plugins/task-track && claude plugin test .`
- Run: `claude plugin validate plugins/planner`, `plugins/tasks`, `plugins/task-track`
