---
name: task-switch
description: Park the current task and make another existing task note active. Use on /task-switch <slug> or "switch to X".
disable-model-invocation: true
---

Switch to: $ARGUMENTS

The vault root is `$VAULT` when set, else `~/vault`; every `~/vault` path below means that root.

1. No argument → list notes in `~/vault/Tasks/` with `status: active` or `parked` (max 5, most recent first) and ask which.
2. Run `/task-park` on the current active task.
3. Resolve the target: exact slug, else match `aliases`. Not found → offer `/task-start`.
4. Set target `status: active`; write its slug to `~/vault/Tasks/.active`.
5. Reply: `Switched to <slug>. Run /clear to load it fresh.` The SessionStart hook loads its Next + Open loops after /clear.
