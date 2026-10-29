---
name: task-note
description: >
  Read or update an existing Obsidian task note: show a task, list all open tasks,
  add a Log note, check or uncheck a Next item, add an Open loop. For "add a
  note to [task]", "what's next on [task]", and in Cowork wherever /note, /done
  or /openloop would be used in Claude Code. Not one project's tasks
  (task-list), habits (habit-tracker) or saving state (task-park); new task:
  /tasks:task-start.
---

Works in Claude Code and Cowork. Edits notes that already exist; it never creates,
renames, moves or deletes a note (that is `/tasks:task-start`, and the user's job in Obsidian).

## Find the vault

First match wins:
1. The session-start `Vault: <path>` line, else the folder above `Tasks/` in its `Active task: … — full note: <path>` line.
2. The `default` vault's `path` in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`), when that file exists and parses.
3. A connected or working folder named `vault`, or one holding both `Tasks/` and `Daily/`.
4. `$VAULT`.
5. `~/vault`.

None has `Tasks/` → say "No vault found (looked in: <each place checked>)" and stop.

## Pick the task

- The user named one → match the file stem in `Tasks/`, else a note whose `aliases` contains the
  name (case-insensitive). Several match → list them and ask.
- `<vault>:<slug>` → that vault's `Tasks/<slug>.md`.
- The user named none → the task named in the session-start `Active task:` line, else `Tasks/.active`.
  Neither → list open tasks and ask.

## Actions

| The user asks | Do |
|---|---|
| show / what's next | Print `## Goal`, open `## Next` items numbered, `## Open loops`. Skip lines struck through with `~~`. |
| list open tasks | Every `Tasks/*.md` whose `status` is not `done`, in every vault `vaults.json` registers that has `Tasks/` (or the one vault): `<vault>:slug — status — first open Next item` (plain `slug` with one vault). |
| add a note | Append to `## Log`: `- [[YYYY-MM-DD]] HH:MM — <text>`, date and time from the latest `Now:` line (`date` only when there is none). |
| check / uncheck item | `- [ ]` ↔ `- [x]` on the item the user means (number from "show", or text match). Ambiguous → ask. |
| add an open loop | Append `- <text>` to `## Open loops`. |

Rules:
- Missing section → add it under the last existing `## ` section, in the order Goal, Next,
  Open loops, Parked, Log.
- Never delete a line. Obsolete → wrap in `~~…~~` and append ` — <why>`.
- Follow `obsidian-vault` for links and formatting when that skill is available.
- Change only the lines the action needs; re-read the note after writing and quote the
  changed line back.

Reply in one line: `<slug>: <what changed>` (e.g. `set-up-vault: logged "test"`).
