# task-track types

## Overview

Type declarations for the `task-track` mod, referenced from the manifest
(`"types": "./types/index.d.ts"` in `.claude-plugin/plugin.json`). One file,
`index.d.ts`; no runtime code. Imported (type-only) by `note.ts`, `pomo.ts`,
`project.ts`, `summary.ts`, `register.tsx` and `tests/task-track.test.ts`.

## Interface

- `NextItem` — `{ text, isDone }`, one `## Next` checkbox.
- `TaskView` — a parsed task note: `slug`, `path`, `title`, `up`, `goal`, `next`,
  `openLoops`, `log` (last 5 lines), `logCount`, `mtimeMs`. Built by
  `parseNote` in [../hooks/note.ts](../hooks/note.ts).
- `ProjectTask` — `{ slug, title, status: 'active' | 'parked', mtimeMs }`, one row of
  the project-tasks pane; any status but `active` lists as `parked`.
- `ProjectList` — `{ repo, tasks }`: the session's repo (last path segment of the
  deepest `repo:` root holding the cwd; `''` when no note names it) and its non-`done`
  tasks, active first, then newest. Built by `projectTasks` in
  [../hooks/project.ts](../hooks/project.ts).
- `BoardTarget` — `{ name, path, hasOthers }`: the vault a `/board` pane shows, by its
  `vaults.json` name and path; `hasOthers` = 2+ vaults are registered, so
  `/board <vault>` can switch. Built by `boardTarget` in
  [../hooks/register.tsx](../hooks/register.tsx).
- `PomoFile` — the on-disk schema of `vault/Tasks/.pomo.json` (`version: 1`):
  block fields (`slug`, `blockStartedAt`, `blockOpenedAt`, `breakUntil`,
  `isLongBreak`, `pausedAt`, `isStopped`), activity (`lastActiveAt`,
  `blockActivity`, `blockSnapshot`), announcement (`lastNotifiedBlock`,
  `notifiedBy`), and day totals (`day`, `dayMs`, `dayBlocks`, `blocksDone`,
  `creditedUntil`, `logged`). Writers hold the timer lock (see
  [../hooks/EGM.md](../hooks/EGM.md)); the file itself carries no lock or claim fields.
- Module augmentation `declare module 'claude-code'` → `PluginState['task-track']`:
  `task`, `problem`, `pomo`, `isBandHidden`, `isLoopsOpen`, `isLogOpen`, `source`,
  `vaultName`, `configError`, `toldBreakUntil`, `toldMvFailed`, `projectList`,
  `isProjectMoreOpen`, `board` (`BoardTarget | null`, null until `/board` runs).

## Invariants

- `PomoFile` is shared by every session and synced machine: a field change is a file
  format change. `parsePomo` in [../hooks/pomo.ts](../hooks/pomo.ts) accepts only
  `version: 1` and fills missing fields from `emptyPomo`, so an added field needs a
  default there; a removed, renamed or re-typed field needs a version bump.
- Epoch-ms fields use `0` for "none" (`blockStartedAt`, `breakUntil`, `pausedAt`,
  `blockOpenedAt`).
- `PluginState['task-track']` keys must match the atoms declared in
  [../hooks/register.tsx](../hooks/register.tsx) (14 atoms, `task` … `board`).
- `source` holds a `VaultPick.reason` from [../hooks/resolve.ts](../hooks/resolve.ts):
  `this session`, `project: <folder>`, `folder <path>`, `default` or `global`.
- `lastActiveAt` is set by the user's prompts, presses and commands, and also by
  Claude's tool calls while a block is running (`markActive($, true)` in
  `register.tsx`): tool calls keep a running block alive but never start one. The
  doc comment on `lastActiveAt` in `index.d.ts` says the same.

## Side Effects

- None (declarations only).

## Verification

- Run: `cd plugins/task-track && claude plugin test .`
- Run: `claude plugin validate plugins/task-track`
