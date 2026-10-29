---
name: task-finish
description: Finish, close or complete a whole task note (status done, finished date, closing Log line). For /tasks:task-finish, "this task is done", "close out X". Not check off a Next item (task-note or /done), pause it (task-park), or the whole day (eod-shutdown).
---

Finish: $ARGUMENTS

The vault root is the path on the session-start `Vault:` line; without that line, the `default` vault in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`) when that file loads; otherwise the plugin's vault path option `${user_config.vaultPath}` (skip it when empty), else `$VAULT`, else `~/vault`, the session-start hook's order. Every `~/vault` path below means that root. When `vaults.json` registers several vaults (the `Vault name:` line lists the others), `<vault>:<slug>` names a task in another vault, and `<vault>` is the vault's name in `vaults.json`, and its root is that entry's `path`.

1. Pick the task. Named → `<vault>:<slug>` reads `~/vault` below as that vault's `path`; else match the file stem in `Tasks/`, else `aliases` (several match → list them and ask). Not named → first match wins: (a) the task this session last started or switched to with `/tasks:task-start` or `/tasks:task-switch`; (b) else the session-start `Active task:` line's `full note:` path; (c) else `~/vault/Tasks/.active`. None → say so, stop. Already `status: done` → say so, stop.
2. Ask the user in ONE message for the outcome: what shipped, links (PR, doc), what was dropped. Skip what the user already said.
3. In the note's frontmatter set `status: done` and `finished: <today>`, written as `finished: YYYY-MM-DD` (today's date from the latest `Now:` line; the board hides values it cannot parse; add the `finished:` line after `started:` when missing). Leave `## Next` and `## Open loops` as they are; never delete lines.
4. Append one line to `## Log`: `- [[YYYY-MM-DD]] HH:MM — finished: <outcome>`, date and time from the latest `Now:` line (`date` only when there is none).
5. Unbind it everywhere, so no session keeps showing a done task: delete every `~/vault/Tasks/.session/*` file whose content is the slug (any session's, not only this one), and empty `~/vault/Tasks/.active` when it holds the slug.
6. Append `- [[<slug>]] finished` under `## Log` in today's daily note (create from `Templates/Daily.md` if missing).
7. Verify per obsidian-vault. Reply: `Finished <slug>.` and, when step 5 unbound this session, `Pick the next one with /tasks:task-switch.`
