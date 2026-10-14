---
name: task-note
description: Read or update an existing Obsidian task note — show a task, list open tasks, add a Log note, check or uncheck a Next item, add an Open loop. Use when Q says "add a note to <task>", "mark <item> done", "what's next on <task>", "which tasks are open", or in Cowork wherever /note, /done or /openloop would be used in Claude Code.
---

Works in Claude Code and Cowork. Edits notes that already exist; it never creates,
renames, moves or deletes a note (that is `/tasks:task-start`, and Q's job in Obsidian).

## Find the vault

First match wins:
1. The session-start `Vault: <path>` line, else the folder above `Tasks/` in its `Active task: … — full note: <path>` line.
2. A connected or working folder named `vault`, or one holding both `Tasks/` and `Daily/`.
3. `$VAULT`.
4. `~/vault`.

None has `Tasks/` → say "No vault found (looked in: <each place checked>)" and stop.

## Pick the task

- Q named one → match the file stem in `Tasks/`, else a note whose `aliases` contains the
  name (case-insensitive). Several match → list them and ask.
- Q named none → the task named in the session-start `Active task:` line, else `Tasks/.active`.
  Neither → list open tasks and ask.

## Actions

| Q asks | Do |
|---|---|
| show / what's next | Print `## Goal`, open `## Next` items numbered, `## Open loops`. Skip lines struck through with `~~`. |
| list open tasks | Every `Tasks/*.md` whose frontmatter `status` is not `done`: `slug — status — first open Next item`. |
| add a note | Append to `## Log`: `- [[YYYY-MM-DD]] HH:MM — <text>` (local date and time). |
| check / uncheck item | `- [ ]` ↔ `- [x]` on the item Q means (number from "show", or text match). Ambiguous → ask. |
| add an open loop | Append `- <text>` to `## Open loops`. |

Rules:
- Missing section → add it under the last existing `## ` section, in the order Goal, Next,
  Open loops, Parked, Log.
- Never delete a line. Obsolete → wrap in `~~…~~` and append ` — <why>`.
- Follow `obsidian-vault` for links and formatting when that skill is available.
- Change only the lines the action needs; re-read the note after writing and quote the
  changed line back.

Reply in one line: `<slug>: <what changed>` (e.g. `set-up-vault: logged "test"`).
