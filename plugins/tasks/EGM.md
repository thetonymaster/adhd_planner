# tasks plugin

## Overview

The `tasks` plugin: Obsidian task notes for Claude Code and Cowork. Hooks inject the
session's active task (Goal, Next, Open loops) at session start, stamp `Now:` on each
prompt, park the session's task when the session ends, and auto-approve file tools
inside a registered vault; skills create, start, park, switch, finish, list and edit
task notes. A note's frontmatter `status:` follows one lifecycle: `parked` (backlog,
the default) → `active` (a session is on it) → `parked` again → `done`. Manifest:
`.claude-plugin/plugin.json` (option `vaultPath`, used when `vaults.json` is absent or
invalid).

## Subdirectories & Boundaries

- hooks: [./hooks/EGM.md](./hooks/EGM.md) - `hooks.json` wiring `SessionStart` →
  `load-task.sh` / `session_task.py`, `UserPromptSubmit` → `now.py`, `SessionEnd` →
  `park_on_end.py`, `PermissionRequest` → `vault-allow.py`; shared resolver library
  `vaults.py`.
- skills: `SKILL.md` files, no code. All eight restate a vault order in prose:
  `create-task`, `task-start`, `task-park`, `task-switch`, `task-finish` and
  `obsidian-vault` the hook's fallback (`Vault:` line → `default` → `vaultPath` →
  `$VAULT` → `~/vault`); `task-list` and `task-note` a variant that skips `vaultPath`
  and adds a connected folder named `vault` (or holding `Tasks/` and `Daily/`), as the
  marketplace and multi-vault specs give it for Cowork. Only `task-switch` restates the
  hook's task pick order; `task-park` and `task-finish` use their own (last
  started/switched → `Active task:` line → `.active`), `task-note` a shorter one
  (`Active task:` line → `.active`).
  - [create-task](./skills/create-task/SKILL.md) - make one or many backlog notes
    (`status: parked`)
  - [obsidian-vault](./skills/obsidian-vault/SKILL.md) - rules for any vault write
  - [task-finish](./skills/task-finish/SKILL.md) - close a task (`status: done`,
    `finished:`)
  - [task-list](./skills/task-list/SKILL.md) - one project's tasks, read-only
  - [task-note](./skills/task-note/SKILL.md) - read or update an existing task note
  - [task-park](./skills/task-park/SKILL.md) - save the active task's state, always
    `status: parked`
  - [task-start](./skills/task-start/SKILL.md) - create a task note and make it active
  - [task-switch](./skills/task-switch/SKILL.md) - park, then activate another note

## Invariants

- Vault/task resolution is a shared contract across `hooks/vaults.py` +
  `hooks/session_task.py`,
  [plugins/task-track/hooks/resolve.ts](../task-track/hooks/resolve.ts), and the prose
  in the skills. Change all of them together. A repo-bound pick is deepest `repo:`,
  then newest note; `status` only matters in that `done` never binds. Known gaps:
  symlinks (resolved in Python only; accepted, the mod API has no realpath) and the
  `task-list` / `task-note` vault order.
- Status lifecycle (in this plugin; the user can also drag a card on the vault's
  Obsidian Board view): only `task-start` and `task-switch` write `status: active`;
  `create-task`, `task-park` and the `SessionEnd` hook write `parked`; only
  `task-finish` writes `done` (with `finished: YYYY-MM-DD`). `create-task` never writes
  `Tasks/.active` or `Tasks/.session/`.
- `park_on_end.py` never blocks session end (always exits 0) and skips
  `reason: "clear"`, so `/clear` right after a start or switch keeps the task active.
- Skill `description` fields carry routing; check named siblings when editing one.
- Bump `version` in `.claude-plugin/plugin.json` when the plugin changes.

## Side Effects

- Hooks: prune old `Tasks/.session/*` files; on session end (not `/clear`) rewrite the
  note named by `Tasks/.session/<session-id>` in each vault from `status: active` to
  `parked` and append a `parked: session ended` Log line (atomic replace, re-read up
  to 3 times when the note changes under it); change permission outcomes for vault
  file tools.
- Skills: write task notes; `task-start` and `task-switch` also write `Tasks/.active`
  and `Tasks/.session/<session-id>`, and delete the other vault's `.session/<id>` on a
  cross-vault move. `task-start` and `task-finish` append to (and may create) today's
  daily note; `task-switch` writes the target's `status:` and `repo:` frontmatter.
  `task-finish` deletes every `Tasks/.session/*` file naming the slug and empties
  `Tasks/.active` when it holds it. `create-task` writes only new notes. `task-list`
  is read-only.

## Verification

- Run (repo root): `python3 -m unittest discover -s tests` (hooks: `test_vaults`,
  `test_load_task`, `test_now`, `test_park_on_end`, `test_vault_allow`; skill text:
  `test_skill_files`)
- Run: `claude plugin validate plugins/tasks`
