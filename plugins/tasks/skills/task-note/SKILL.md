---
name: task-note
description: >
  Read or update an existing task note: show it, list open tasks, log a note,
  check a Next item, add an Open loop. For "add a note to [task]", "what's
  next on [task]", and in Cowork in place of /note, /done or /openloop. Not
  one project's tasks (task-list), habits (habit-tracker), saving state
  (task-park) or closing the task (task-finish); new task: create-task
  (backlog) or task-start (start now).
---

Works in Claude Code and Cowork. Edits notes that already exist; it never creates,
renames, moves or deletes a note (creating is create-task or `/tasks:task-start`; renaming and moving are the user's job in Obsidian).

## Find the vault

First match wins:
1. The session-start `Vault: <path>` line, else the folder above `Tasks/` in its `Current task: … — full note: <path>` line.
2. The `default` vault's `path` in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`), when that file exists and parses.
3. A connected or working folder named `vault`, or one holding both `Tasks/` and `Daily/`.
4. `$VAULT`.
5. `~/vault`.

None has `Tasks/` → say "No vault found (looked in: <each place checked>)" and stop.

## Pick the task

- The user named one → match the file stem in `Tasks/`, else a note whose `aliases` contains the
  name (case-insensitive). Several match → list them and ask.
- `<vault>:<slug>` → that vault's `Tasks/<slug>.md`.
- The user named none → first match wins: the task this session last started or switched to
  (`/tasks:task-start`, `/tasks:task-switch`), else the task named in the session-start
  `Current task:` line, else `Tasks/.active`. That line is written once at session start, so
  after a mid-session switch it names the old task.
  Neither → list open tasks and ask.

## Actions

| The user asks | Do |
|---|---|
| show / what's next | Print `## Goal`, open `## Next` items numbered, `## Open loops`. Skip lines struck through with `~~`. |
| list open tasks | Every `Tasks/*.md` whose `status` is not `done`, in every vault `vaults.json` registers that has `Tasks/` (or the one vault): `<vault>:slug — status — first open Next item` (plain `slug` with one vault). |
| add a note | Append to `## Log`: `- [[YYYY-MM-DD]] HH:MM — <text>`, date and time from the latest `Now:` line (`date` only when there is none). |
| check / uncheck item | `- [ ]` ↔ `- [x]` on the item the user means (number from "show", or text match). Ambiguous → ask. |
| add an open loop | Append `- <text>` to `## Open loops`. |
| set priority or due | See "Set priority or due" below. |

Rules:
- Missing section → add it under the last existing `## ` section, in the order Goal, Next,
  Open loops, Parked, Log.
- Never delete a line. Obsolete → wrap in `~~…~~` and append ` — <why>`.
- Follow `obsidian-vault` for links and formatting when that skill is available.
- Change only the lines the action needs; re-read the note after writing and quote the
  changed line back.

### Set priority or due

1. Validate first. `priority` is exactly one of `p0`..`p5`; `due` is a `YYYY-MM-DD` date, or
   empty to clear it. Invalid → writes nothing and replies
   `<slug>: not changed — priority takes p0..p5; due takes YYYY-MM-DD or empty to clear`.
2. Edit the one frontmatter line (`priority: p1`, `due: 2026-11-20`, or `due:` to clear).
   Missing key: add `priority:` on the line after `up:` (no `up:` → after `status:`; neither →
   as the first frontmatter line); add `due:` on the line directly after `priority:`, or where
   `priority:` would go when there is no `priority` line.
3. Append to `## Log`, date and time as for "add a note", old value `(none)` when the key
   was missing or empty:
   - `- [[YYYY-MM-DD]] HH:MM — priority p3 → p1`
   - `- [[YYYY-MM-DD]] HH:MM — due (none) → 2026-11-20`
   - `- [[YYYY-MM-DD]] HH:MM — due 2026-11-20 → (none)`

Reply in one line: `<slug>: <what changed>` (e.g. `set-up-vault: logged "test"`).
