# tasks hooks

## Overview

Claude Code / Cowork hooks for the `tasks` plugin, wired in [hooks.json](./hooks.json).
They inject the current time and the session's active Obsidian task note at session
start, stamp `Now:` on every prompt, park the session's task when the session ends, and
auto-approve file tools inside a registered vault. Python 3 with a bash fallback (the
SessionEnd hook does nothing without `python3`); standard library only.

## Interface

Hook entry points (`hooks.json`):

- `SessionStart` (matcher `startup|resume|clear|compact`, 10 s) → `load-task.sh`.
  Reads the hook JSON on stdin and execs `session_task.py` with it in `HOOK_INPUT`.
  Without `python3`: prints `Now:` from `date`, the vault from
  `CLAUDE_PLUGIN_OPTION_VAULTPATH` → `$VAULT` → `~/vault`, and `Tasks/.active`'s note.
- `UserPromptSubmit` (5 s) → `now.py`: prints `Now: <Day> YYYY-MM-DD HH:MM` in the
  vaults.json timezone, else `$TZ`, else the system clock (falls back to `date`).
- `SessionEnd` (5 s) → `park_on_end.py` when `python3` exists: in every vault whose
  `Tasks/.session/<session_id>` exists, sets the named note's frontmatter
  `status: active` → `status: parked` and appends `- [[YYYY-MM-DD]] HH:MM — parked: session ended`
  to its `## Log` (creating the section when missing). Prints nothing on stdout.
- `PermissionRequest` for `Read|Edit|Write|NotebookEdit|Glob|Grep` (5 s) →
  `vault-allow.py`: prints
  `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}`
  or nothing (normal prompt).

Modules:

- `vaults.py` (shared library): `load_config(env, home) -> Config`, `parse`,
  `implicit`, `config_path`, `read_state(vault, sid) -> (State, skipped)`,
  `pick(config, states, cwd, home) -> Pick | None`, `zone_for`, `now`, `is_zone`,
  `slug_or_empty`, `norm`, `within`, `expand`; dataclasses `Vault`, `Config`, `Note`,
  `State`, `Pick`; `NAME` slug regex.
- `session_task.py`: `main() -> list[str]` (the injected lines), `now_line()`,
  `prune(tasks)`, `sections(text)`, `fallback(...)`.
- `park_on_end.py`: `main(stdin, env, home) -> int`, `park(text, stamp) -> str | None`,
  `write_atomic(path, text, read_at)`, `version(path) -> (mtime_ns, size)`, exception
  `NoteChanged`; constants `FRONTMATTER`, `ACTIVE`, `SESSION_ID`, `WRITE_TRIES`.
- `vault-allow.py`: `main()`, `vault_roots`, `may_read`, `may_write`,
  `plants_code`, `grep_is_visible_only`, `pattern_escapes`, `unsafe_root`, `inside`,
  `hidden_note_in`, `parts_under`, `hidden`, `paths_of`; constants `PATH_KEYS`,
  `GREP_GLOB`, `DATAVIEWJS_FENCE`, `STATE_FILES`, `CODE_MARKERS`, `STEERING_NAMES`.

Output shape of `session_task.py`: `Now:`, `Vault: <path>`, (with vaults.json)
`Vault name: <name> (<reason>)`, `Active task: <slug> (<reason>) — full note: <path>`,
then the note's `## Goal`, `## Next`, `## Open loops` sections (list items starting
`- ~~` or `- [x] ~~` dropped, at most 40 lines). Also, when they apply:
`Vault config error|warning: …`, `(skipped vault …)`, a ` · others: …` suffix on
`Vault name:`, `No active task…`, `Active task '<slug>' … has no note`,
`(skipped unreadable notes…)` and `(could not prune …)`.

## Invariants

- **Shared contract with task-track.** `vaults.py` + `session_task.py` implement the
  same vault and task resolution as
  [plugins/task-track/hooks/resolve.ts](../../task-track/hooks/resolve.ts); both are
  checked against `plugins/task-track/tests/fixtures/vault-cases.ts` (Python side:
  `tests/test_load_task.py`). Change both together, and the prose in the `tasks` skills.
  Known gap: `norm` resolves symlinks (`realpath`) for the cwd, `repo:` and `folders`;
  `resolve.ts` does not, so symlinked paths can pick differently.
- Vault config: `$ADHD_PLANNER_VAULTS` (absolute or `~/`), else
  `~/.config/adhd-planner/vaults.json`. Absent → one implicit vault from the
  `vaultPath` option → `$VAULT` → `~/vault`. Unreadable or invalid → implicit vault
  plus a named `error`.
- Pick order (`vaults.pick`): this session's `Tasks/.session/<session-id>` (newest
  mtime across vaults, must name an existing note) → a non-`done` note whose `repo:`
  holds the cwd (deepest repo, then newest mtime; status is not ranked) → deepest
  vault `folders` entry holding the cwd (its `Tasks/.active`) → the `default` vault's
  `Tasks/.active`.
- Slugs must match `^[a-z0-9][a-z0-9-]*$` (`slug_or_empty`); anything else is
  treated as empty so it cannot name a path outside `Tasks/`. `load-task.sh` applies
  the same rule.
- Session start never fails: a resolver exception is named and the default vault's
  `.active` is used; `Now:` is printed before resolution so a crash keeps it.
- `park_on_end.py` never blocks session end: `main` returns 0 whatever happens and
  reports problems on stderr. It does nothing for hook input `reason: "clear"` (task-start
  and task-switch tell the user to `/clear` right after activating a task), for a
  `session_id` not matching `^[A-Za-z0-9_-]+$`, or for a pointer that is not a valid slug.
  It changes only a frontmatter `status: active` (a body `status:` line is left), keeps a
  CRLF note CRLF and the note's file mode, and replaces the note atomically only if its
  mtime and size still match the read; otherwise it re-reads, up to `WRITE_TRIES` (3), then
  leaves the note active. The check narrows, not closes, the race with another writer.
- `vault-allow.py` only ever allows; it never denies. It exits 0 on well-formed and
  malformed input: `main` catches `AttributeError`, `TypeError` and `ValueError` (a NUL
  byte in a path or the cwd) around `paths_of` / `pattern_escapes` and leaves the
  decision to the normal prompt. It trusts no root that is relative, `/`, home or an
  ancestor of it, or inside, equal to or an ancestor of `~/.claude` or
  `$CLAUDE_CONFIG_DIR`; returns no roots if any vault path is relative; approves
  nothing when vaults.json has an error or lies inside a vault. Reads: any path without a dot-segment under the vault.
  Writes: `*.md` / `*.canvas` outside dot-folders (never `CLAUDE.md` /
  `CLAUDE.local.md`), plus `Tasks/.active`, `Tasks/.pomo.json`,
  `Tasks/.session/<id>`; refused when the new text holds Obsidian-executed code
  (`dataviewjs` fence, Templater `<%`, inline `` `$= ``). Grep only for one regular
  file without a dot-segment (any extension) or an anchored folder glob with no hidden
  notes. Glob is refused when its pattern is absolute, starts with `~`, contains `{`
  or reaches a dot-segment (`pattern_escapes`). Each call is decided alone.

## Side Effects

- `session_task.py` deletes `Tasks/.session/*` files older than 14 days in each
  usable vault (`prune`); it reports any it could not remove only when the picked
  task's note exists (earlier returns skip the report).
- `park_on_end.py` rewrites the session's task note (status and one Log line) via a
  temp file `.<name>.*` in `Tasks/`, removed on failure; it leaves `Tasks/.session/<id>`
  and `Tasks/.active` in place. It reads `vaults.json` (vaults and timezone for the stamp).
- Reads: `session_task.py` reads `vaults.json`, task note frontmatter (`repo:`,
  `status:`), `Tasks/.active` and `Tasks/.session/<id>`; `now.py` reads only
  `vaults.json`; `vault-allow.py` reads `vaults.json` and lists directories; the bash
  fallback in `load-task.sh` reads only `Tasks/.active` and its note. Output goes to
  stdout only (`park_on_end.py`: stderr only).
- `vault-allow.py` changes the permission outcome of file tool calls inside a vault.
- `__pycache__/` appears from imports of `vaults.py`; it is not source.

## Verification

- Run (repo root): `python3 -m unittest discover -s tests`
  (`tests/test_vaults.py`, `tests/test_load_task.py`, `tests/test_now.py`,
  `tests/test_vault_allow.py`, `tests/test_park_on_end.py`).
- Single test: `python3 -m unittest tests.test_vaults.<Class>.<method>`
- Run: `claude plugin validate plugins/tasks`
- After touching resolution, also run `cd plugins/task-track && claude plugin test .`
