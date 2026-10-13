---
name: task-park
description: Save the active task's state to its note so the session can be cleared or the task switched. Use on /task-park, "park this", when context is noisy, before switching tasks, or when wrapping up.
---

The vault root is `$VAULT` when set, else `~/vault`; every `~/vault` path below means that root.

1. Read `~/vault/Tasks/.active`; open that note. None active → say so, stop.
2. Rewrite `## Next` with the 1–3 concrete next actions as `- [ ]` with time estimates. Someone with no memory of this session must be able to start from line 1.
3. Add new questions to `## Open loops`; strike through resolved ones with the answer.
4. Append one line to `## Log`: `- [[YYYY-MM-DD]] HH:MM — <what got done, what was learned>`.
5. If Q is switching or stopping for the day, set `status: parked` (or `done` if finished). Keep `.active` unless switching.
6. Durable lessons (not task state) → auto memory, not the note.
7. Verify per obsidian-vault. Reply: `Parked <slug>. Next: <first action>. Run /clear when ready.`
