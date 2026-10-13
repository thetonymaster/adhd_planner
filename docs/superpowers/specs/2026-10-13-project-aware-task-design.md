# Project-aware `/task` — design

Date: 2026-10-13 · Status: approved in chat, spec under review

## Goal

Each Claude Code session shows the task that belongs to it. A session started in a
repo shows that repo's task. `/task-switch` changes the task for that session only.
Sessions with neither fall back to today's global `Tasks/.active`. The Pomodoro stays
one timer for the person, not one per task.

Today every session reads the single `Tasks/.active`, so two sessions in two repos
show the same task, and the band, pane, injected context and focus credit are all
wrong for one of them.

## Decisions (from the brainstorm)

| Question | Decision |
| --- | --- |
| What binds a session to a task? | Repo, with a per-session override. Fallback: global `.active`. |
| Pomodoro with sessions on different tasks | One timer for the person. Switching task keeps the block running; minutes go to the task of the latest activity. |
| Explicit pause/stop of the Pomodoro | Out of scope. Next task, its own spec (adds `pausedAt` to `.pomo.json`). |

## 1. Resolution: which task a session shows

Inputs: the vault root, the session id, the session's working directory (`cwd`).
First match wins:

1. **Session override.** `Tasks/.session/<session-id>` exists and holds a slug whose
   note exists. Same session id on `--resume`, so the override survives a resume; a
   `/clear` starts a new id and falls through to 2.
2. **Repo binding.** Task notes (`Tasks/*.md`) whose frontmatter has `repo: <path>`
   and `status:` other than `done`, where `<path>` (after expanding `~`) equals `cwd`
   or is an ancestor of it. Ties break by:
   1. the deepest `repo` path (most specific),
   2. `status: active` over `parked`,
   3. the most recently modified note.
3. **Global.** `Tasks/.active`, as today.

Nothing resolved → "No active task", as today.

The rule is implemented twice, once in the shell hook and once in the mod, because
they run in different runtimes. Both are tested against the same cases (section 6).

## 2. Writers

- **`/task-start <slug>`** — as today, plus:
  - sets `repo:` in the new note to the git top-level of the current directory
    (`git rev-parse --show-toplevel`, written with `~` for `$HOME`); omits it outside
    a git repo;
  - writes the slug to `Tasks/.session/$CLAUDE_CODE_SESSION_ID` and to `Tasks/.active`.
- **`/task-switch <slug>`** — as today (parks the current one), and writes the slug to
  both `Tasks/.session/$CLAUDE_CODE_SESSION_ID` and `Tasks/.active`.
- `Tasks/.active` keeps its meaning for everything else: "the task the person last
  chose". The planner skills and eod-shutdown keep reading it unchanged.
- Without `CLAUDE_CODE_SESSION_ID` (an older Claude Code, another tool), the skills
  write only `.active` and say that the choice applies to all sessions.

`repo:` can be added or edited by hand in any existing note; that is how an existing
task gets bound to a repo.

## 3. The SessionStart hook (`load-task.sh`)

- Reads `session_id` and `cwd` from the hook's JSON on stdin; resolves per section 1;
  injects that task's Goal / Next / Open loops (struck-through lines still filtered).
- The "Active task:" line says why: `(this session)`, `(repo ~/work/infra-app)` or
  `(global)`, so a wrong binding is visible at once.
- Deletes `Tasks/.session/*` files older than 14 days.
- Missing `jq` or malformed stdin → falls back to the global `.active` and says so in
  the injected text; it never blocks session start.

## 4. The task-track mod

- `load()` resolves per section 1 using `$.session.id()` and `$.session.cwd()`, with
  `$.fs.list` over `Tasks/` and a frontmatter read of each note. The scan reruns only
  when `Tasks/` or `.session/<id>` changed (mtime), not on every 15 s poll.
- The band, the pane and `/note` `/done` `/openloop` act on the session's task.
- The pane header shows the binding source in muted text: `this session`, `repo` or
  `global`.

### Pomodoro: one timer for the person

`hooks/pomo.ts` `touch()` changes; the `.pomo.json` format does not (no new fields;
`slug` now means "the task the latest activity was on").

- Activity on a different task than `slug`: credit the time up to `now` to the old
  `slug`, then set `slug` to the new task. `blockStartedAt`, `blocksDone` and
  `lastNotifiedBlock` are left alone: the block keeps running.
- `blocksDone` counts the person's blocks for the day, so the long break comes every
  4th block whatever the tasks. `dayBlocks[slug]` still records which task a finished
  block counts for: the task active when the block completes.
- Breaks are still announced once across sessions (`notifiedBy` unchanged).

## 5. Docs touched

`CLAUDE.md` (Task notes section), `obsidian-vault` skill (`Tasks/` row: `.session/`
and `repo:`), `Templates/Task.md` (`repo:` field), task-track `README.md`,
`Notes/How this vault works.md` in the vault starter.

## 6. Testing

Mod (`claude plugin test`):
- each resolution step alone; override beats repo beats global;
- deepest repo wins; active beats parked; a `done` note never binds;
- two engines with different session ids and cwds show different tasks in the band;
- a dangling override (note deleted) falls through to the repo binding;
- Pomodoro: a block continues across a task switch; time before the switch goes to the
  first task, after it to the second; a block finishing after the switch counts for
  the second; the 4th block of the day asks for the long break across two tasks.

Hook (`tests/test_load_task.py`, stdlib `unittest`, runs `load-task.sh` against a
scratch vault with JSON on stdin):
- the same resolution cases as the mod, plus the 14-day pruning and the no-`jq`
  fallback.

## Out of scope

- Explicit pause / resume / stop of the Pomodoro (next task).
- A per-session Pomodoro.
- Showing several tasks at once in one pane.
- Changing the planner plugin.

## Risks

- **Two implementations of one rule** (shell and mod) can drift. Mitigation: the
  shared case list in section 6 is run against both.
- **Repo binding surprises**: a session in a repo shows a task the person forgot was
  bound. Mitigation: the binding source is shown in the hook line and the pane header;
  `/task-switch` overrides.
- **`.session/` clutter** in the vault: pruned after 14 days; add `Tasks/.session/`
  to the vault starter's `.gitignore`.
