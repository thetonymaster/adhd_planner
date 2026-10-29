---
name: task-list
description: >
  List the task notes of one project, read-only ([project] = a Projects/ or
  Areas/ hub their up: links to). For "tasks on [project]", "what's open in [project]",
  "list [project] tasks". Not one task's detail or Next items, or every open
  task across projects (task-note); to schedule them, plan-week; new task:
  /tasks:task-start.
---

Works in Claude Code and Cowork. Read-only: it lists tasks and does nothing else. It never
edits, creates, parks or switches a task, and never offers to.

## Find the vault

First match wins:
1. The session-start `Vault: <path>` line, else the folder above `Tasks/` in its `Active task: … — full note: <path>` line.
2. The `default` vault's `path` in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`), when that file exists and parses.
3. A connected or working folder named `vault`, or one holding both `Tasks/` and `Daily/`.
4. `$VAULT`.
5. `~/vault`.

`<vault>:<project>` → that vault from `vaults.json`. None has `Tasks/` → say
"No vault found (looked in: <each place checked>)" and stop.

## Pick the project

- The user named one → match the file stem in `Projects/` (then `Areas/`), else a hub whose
  `aliases` contains the name (case-insensitive). Several match → list them and ask.
- The user named none → the `up:` project of the session's active task, first match wins:
  the task this session last started or switched to (`/tasks:task-start`, `/tasks:task-switch`),
  else the session-start `Active task:` note, else `Tasks/.session/$CLAUDE_CODE_SESSION_ID` when
  that variable is set, else `Tasks/.active`. None → list the `Projects/` and `Areas/` hubs and ask.
- No hub matches → say "No project `<name>` in <vault>/Projects or <vault>/Areas" and list the hubs.

## List

A task belongs to the project when its frontmatter `up:` links to the hub (`[[Name]]`,
`[[Name|alias]]` or `[[Projects/Name]]`). Skip notes whose `status` is `done` unless the user
asks for done or all tasks.

Print one line per task, `active` first, then the rest by `started` (newest first):

`slug — status — first open Next item`

Open Next item = the first `- [ ]` under `## Next` not struck through with `~~`; none → `—`.
Head the list with `<project> (<n> tasks)`. No tasks → `<project>: no open tasks`.
