---
name: task-park
description: Save the active task's state to its note (Next, Open loops, a Log line) so the session can be cleared or the task picked up later. Use on /tasks:task-park, "park this", or when context is noisy. One task note, not the day: a whole-day wrap-up is planner:eod-shutdown, which parks the active task itself. To move to another task, suggest /tasks:task-switch, which parks first.
---

The vault root is the path on the session-start `Vault:` line; without that line, the `default` vault in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`) when that file loads; otherwise the plugin's vault path option `${user_config.vaultPath}` (skip it when empty), else `$VAULT`, else `~/vault`, the session-start hook's order. Every `~/vault` path below means that root.

1. Pick the task, first match wins: (a) the task this session last started or switched to with `/tasks:task-start` or `/tasks:task-switch`, at `<its vault>/Tasks/<slug>.md`; (b) else the session-start `Active task:` line's `full note:` path; (c) else `~/vault/Tasks/.active`. The `Active task:` line is written once at session start, so after a mid-session switch it still names the old task: (a) comes first. Open that note. None active → say so, stop.
2. Rewrite `## Next` with the 1–3 concrete next actions as `- [ ]` with time estimates. Someone with no memory of this session must be able to start from line 1.
3. Add new questions to `## Open loops`; strike through resolved ones with the answer.
4. Append one line to `## Log`: `- [[YYYY-MM-DD]] HH:MM — <what got done, what was learned>`.
5. If the user is switching or stopping for the day, set `status: parked` (or `done` if finished). Keep `.active` unless switching.
6. Durable lessons (not task state) → auto memory, not the note.
7. Verify per obsidian-vault. Reply: `Parked <slug>. Next: <first action>. Run /clear when ready.`
