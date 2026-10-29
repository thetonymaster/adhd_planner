---
name: create-task
description: Create one or many task notes in ~/vault/Tasks as backlog (parked), e.g. a batch from a plan or review, without starting any. For "add a task for X", "make tasks from this plan". Not start working on it (task-start) or edit an existing task (task-note).
---

Create: $ARGUMENTS

The vault root is the path on the session-start `Vault:` line; without that line, the `default` vault in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`) when that file loads; otherwise the plugin's vault path option `${user_config.vaultPath}` (skip it when empty), else `$VAULT`, else `~/vault`, the session-start hook's order. Every `~/vault` path below means that root. When `vaults.json` registers several vaults (the `Vault name:` line lists the others), `<vault>:<slug>` names a task in another vault, and `<vault>` is the vault's name in `vaults.json`, and its root is that entry's `path`.

New tasks go to the backlog: `status: parked`. This skill never starts a task. Never writes `Tasks/.active` or `Tasks/.session/`, and never parks or changes another task.

1. Collect the tasks: one from the argument, or many from the plan, review or list the user points at (one task per item that is real work). A `<vault>:` prefix targets that vault for that task; read `~/vault` below as its `path` from `vaults.json`. Slug = kebab-case of the title. If `~/vault/Tasks/<slug>.md` exists, skip that task and say so.
2. Ask the user in ONE message for what is missing: goal (one line), project/area, first action, per task. A batch shares one project/area unless the user says otherwise. Skip what the argument or the source already answers.
3. Confirm each project/area hub exists in `Projects/` or `Areas/` (obsidian-vault rule 3). Missing → ask before creating it.
4. For each task, copy `~/vault/Templates/Task.md` to `~/vault/Tasks/<slug>.md`; set `status: parked`; fill `up`, `started` (today: the date on the latest `Now:` line), `aliases`, Goal, Next (as `- [ ]` with a time estimate); leave `finished:` empty. Set `repo:` only when the user says the task belongs to the current repo: `git rev-parse --show-toplevel`, written with `~` for `$HOME`. Otherwise leave it empty.
5. Append one line to each note's `## Log`: `- [[YYYY-MM-DD]] HH:MM — created`, adding the source when there is one (`created from <plan>`), date and time from the latest `Now:` line (`date` only when there is none).
6. Verify per obsidian-vault (unresolved, backlinks on the hub). Reply: one line per created task, `<slug> — <first Next item>` (`<vault>:<slug>` with several vaults registered), then `Skipped (exists): <slugs>` if any, then `Start one with /tasks:task-switch <slug>.`
