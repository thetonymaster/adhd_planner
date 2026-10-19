---
name: task-start
description: Start a new task note in ~/vault/Tasks and make it the active task. Use when the user runs /tasks:task-start <slug> or "start a task for X".
disable-model-invocation: true
---

Start task: $ARGUMENTS

The vault root is the path on the session-start `Vault:` line; without that line, the `default` vault in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`) when that file loads; otherwise the plugin's vault path option `${user_config.vaultPath}` (skip it when empty), else `$VAULT`, else `~/vault`, the session-start hook's order. Every `~/vault` path below means that root. When `vaults.json` registers several vaults (the `Vault name:` line lists the others), `<vault>:<slug>` names a task in another vault, and `<vault>` is the vault's name in `vaults.json`, and its root is that entry's `path`.

1. An argument `<vault>:<slug>` targets that vault: strip the prefix before making the slug, and in steps 1–4 and 6–7 read `~/vault` as that vault's `path` from `vaults.json` (step 5 parks the current vault's task, so it stays on the current vault); otherwise use the current vault. When it is not the current vault, also delete `<current vault>/Tasks/.session/$CLAUDE_CODE_SESSION_ID` in step 6 (as task-switch does), and add `Vault now: <name> (<path>)` to the reply. Slug = kebab-case of the argument. If `~/vault/Tasks/<slug>.md` exists, say so and offer `/tasks:task-switch <slug>` instead (`/tasks:task-switch <vault>:<slug>` when a vault prefix was given).
2. Ask the user in ONE message: goal (one line), project/area it belongs to, first action. Skip what the argument already answers.
3. Confirm the project/area hub exists in `Projects/` or `Areas/` (obsidian-vault rule 3). Missing → ask before creating it.
4. Copy `~/vault/Templates/Task.md` to `~/vault/Tasks/<slug>.md`; fill `up`, `started` (today: the date on the latest `Now:` line), `aliases`, Goal, Next (as `- [ ]` with a time estimate). Set `repo:` to `git rev-parse --show-toplevel` of the current directory, written with `~` for `$HOME`; leave it empty outside a git repo.
5. If another task is active, run `/tasks:task-park` for it first.
6. Write the slug to `~/vault/Tasks/.active` and to `~/vault/Tasks/.session/$CLAUDE_CODE_SESSION_ID` (create `.session/`). If `CLAUDE_CODE_SESSION_ID` is empty, write only `.active` and say the choice applies to every session.
7. Append `- [[<slug>]] started` under `## Log` in today's daily note (create from `Templates/Daily.md` if missing).
8. Verify per obsidian-vault (unresolved, backlinks on the hub). Reply: the Next action, nothing else. With several vaults registered, start it with `<vault>:`; on a cross-vault start, put step 1's `Vault now: <name> (<path>)` line before it.
