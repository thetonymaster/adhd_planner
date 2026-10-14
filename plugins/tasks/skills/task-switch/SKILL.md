---
name: task-switch
description: Park the current task and make another existing task note active. Use on /tasks:task-switch <slug> or "switch to X".
disable-model-invocation: true
---

Switch to: $ARGUMENTS

The vault root is the path on the session-start `Vault:` line (it follows the plugin's `vaultPath`); without that line, `$VAULT` when set, else `~/vault`. Every `~/vault` path below means that root.

1. No argument → list notes in `~/vault/Tasks/` with `status: active` or `parked` (max 5, most recent first) and ask which.
2. Run `/tasks:task-park` on the current active task.
3. Resolve the target: exact slug, else match `aliases`. Not found → offer `/tasks:task-start`.
4. Set target `status: active`; write its slug to `~/vault/Tasks/.active` and to `~/vault/Tasks/.session/$CLAUDE_CODE_SESSION_ID` (create `.session/`). If `CLAUDE_CODE_SESSION_ID` is empty, write only `.active` and say the choice applies to every session.
   If the target's `repo:` is empty and the current directory is in a git repo, set `repo:` to `git rev-parse --show-toplevel`, written with `~` for `$HOME`: with the old task parked, the active target wins this repo after `/clear`. If `repo:` already names another folder, leave it.
5. Reply: `Switched to <slug>. Run /clear to load it fresh.` Add `Bound to <repo>.` when step 4 set `repo:`. When `repo:` names another folder and this repo has its own task, add: `After /clear this repo shows <that task>; /tasks:task-switch again or stay in this session.`
