# task-track plugin

## Overview

The `task-track` plugin: a Claude Code–only mod (not Cowork) that keeps the session's
active Obsidian task note in view (band above the prompt, `/task` pane), lists this
repo's tasks in the `/project-tasks` pane (a click fills `/tasks:task-switch [<vault>:]<slug>` into
the chat box, never sends), shows a read-only `/board` of the vault's task notes (Doing ·
Parked · Done, grouped by project), runs one Pomodoro shared across sessions through
`vault/Tasks/.pomo.json` (`/pomo [start|pause|resume|stop]`), and writes to the note
with `/note`, `/done`, `/openloop` without a model turn. Manifest:
`.claude-plugin/plugin.json` (options `vaultPath`, `focusMinutes`, `breakMinutes`,
`longBreakEvery`, `longBreakMinutes`, `staleEdits`, `notesToClaude`,
`breakSummaryAI`). Human guide: [README.md](./README.md).

## Subdirectories & Boundaries

- hooks: [./hooks/EGM.md](./hooks/EGM.md) - `register.tsx` (all IO: commands,
  lifecycle, band, the task / project-tasks / board panes, Pomodoro file writes) and
  pure modules `resolve.ts`, `note.ts`, `pomo.ts`, `summary.ts`, `project.ts` (this
  repo's tasks for the project-tasks pane) and `board.ts` (task-note frontmatter →
  board columns).
- types: [./types/EGM.md](./types/EGM.md) - `index.d.ts`: `TaskView`, `NextItem`,
  `PomoFile` (the `.pomo.json` schema), `ProjectTask`, `ProjectList`, `BoardTarget`
  and the `PluginState['task-track']` augmentation.
- tests (not documented here): `task-track.test.ts`, the shared vault-resolution
  fixtures `tests/fixtures/vault-cases.ts` (also run by `tests/test_load_task.py`) and
  their `VaultCase` type in `tests/fixtures/vault-case.ts`.

## Invariants

- `hooks/resolve.ts` must stay in sync with
  [plugins/tasks/hooks/vaults.py](../tasks/hooks/vaults.py) and `session_task.py`.
  Since the task-board change neither side ranks `status: active` above other
  non-`done` notes when picking a repo-bound task (deepest root, then newest).
  Known gap (accepted, multi-vault spec §4): `vaults.py` resolves symlinks and
  `resolve.ts` does not.
- The project-tasks pane only fills the chat box: it never submits, and never
  overwrites a typed draft.
- The board pane is read-only: it reads `Tasks/*.md` of the named vault (or the
  session's) on every draw and writes nothing.
- Bump `version` in `.claude-plugin/plugin.json` when the plugin changes.
- For live development set `CLAUDE_CODE_PLUGIN_DIRS=plugins/task-track`.

## Side Effects

- Writes task notes, daily notes and `Tasks/.pomo.json` in the session's vault, every
  timer write under an OS `flock` on `Tasks/.pomo.flock` held by a `perl` helper (where perl
  can't run, the folder lock `Tasks/.pomo.lock`, made with `mkdir`, removed after;
  where `mkdir` fails 5 times in a row with the lock confirmed gone each time (`mkdir`
  can't work there, or rarely a lock taken and released between every try) the session
  says so once and writes unlocked, so writes are not serialized then;
  can leave a `Tasks/.pomo.json.<id>.tmp` when `mv` fails), reads `Templates/Daily.md`,
  appends pane notes to the session as user messages, and writes `focus:*` keys in the
  plugin store (details in [hooks/EGM.md](./hooks/EGM.md)).
- Reads every `Tasks/*.md` of a vault for the project-tasks and board panes (`/board
  <vault>` can read a vault other than the session's), fills the chat box via
  `$.prompt.fill` (project-tasks pane), submits `/tasks:task-park` (Park button) and
  runs `open obsidian://…` (Open in Obsidian).

## Verification

- Run: `cd plugins/task-track && claude plugin test .` (local only, not in CI)
- Run: `claude plugin validate plugins/task-track`
