---
name: task-start
description: Start a new task note in ~/vault/Tasks and make it the active task. Use when Q says /tasks:task-start <slug> or "start a task for X".
disable-model-invocation: true
---

Start task: $ARGUMENTS

The vault root is the path on the session-start `Vault:` line (it follows the plugin's `vaultPath`); without that line, `$VAULT` when set, else `~/vault`. Every `~/vault` path below means that root.

1. Slug = kebab-case of the argument. If `~/vault/Tasks/<slug>.md` exists, say so and offer `/tasks:task-switch <slug>` instead.
2. Ask Q in ONE message: goal (one line), project/area it belongs to, first action. Skip what the argument already answers.
3. Confirm the project/area hub exists in `Projects/` or `Areas/` (obsidian-vault rule 3). Missing → ask before creating it.
4. Copy `~/vault/Templates/Task.md` to `~/vault/Tasks/<slug>.md`; fill `up`, `started`, `aliases`, Goal, Next (as `- [ ]` with a time estimate). Set `repo:` to `git rev-parse --show-toplevel` of the current directory, written with `~` for `$HOME`; leave it empty outside a git repo.
5. If another task is active, run `/tasks:task-park` for it first.
6. Write the slug to `~/vault/Tasks/.active` and to `~/vault/Tasks/.session/$CLAUDE_CODE_SESSION_ID` (create `.session/`). If `CLAUDE_CODE_SESSION_ID` is empty, write only `.active` and say the choice applies to every session.
7. Append `- [[<slug>]] started` under `## Log` in today's daily note (create from `Templates/Daily.md` if missing).
8. Verify per obsidian-vault (unresolved, backlinks on the hub). Reply: the Next action, nothing else.
