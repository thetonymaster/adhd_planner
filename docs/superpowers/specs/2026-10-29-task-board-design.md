# Task board: kanban view of task notes

Date: 2026-10-29. Status: ready for Q's approval (builder check done, Q's answers folded in).

## Why

Q wants to glance at a vault and see what is in flight, what is waiting and what just finished, both in Obsidian (browsing notes) and in Claude Code (mid-session). Today every task note has `status:` frontmatter, but the value lies: skills default new notes to `active`, `task-park` only sets `parked` when switching or stopping, so personal has 7–11 "active" tasks at once and arryved 8. A board built on that would show a wall of "Doing". The work is two halves: make `status` mean something, then show it in two places.

## Goals

- `status:` in a task note's frontmatter is the single source of truth, read by both views. Neither view keeps its own copy.
- Three columns: **Parked** (`parked`, also the backlog/todo), **Doing** (`active`), **Done** (`done`, finished in the last 7 days).
- Every status change is made by a skill and writes a `## Log` line, or by dragging a card in Obsidian.
- Doing stays short: only tasks with a session working on them. Parking (including park-then-clear) and ending a session move a task back to Parked.

## Non-goals

- No separate `todo` status. Parked is the backlog.
- No writing from the Claude Code board (read-only).
- No custom Obsidian plugin. A community Bases board plugin renders the Obsidian side.
- No cross-vault board in one view. One vault at a time.

## Anti-goals (would make this a failure even if it works)

- Two sources of truth (a board file, a JSON cache) that drift from the notes.
- New notes landing in Doing by default again.
- The board guessing dates from file modification time (the cleanup rewrites every file).

## Lifecycle

| Skill | Status written | Also |
|---|---|---|
| **`create-task`** (new, `tasks` plugin) | `parked` | Creates one note or many in one go (e.g. a batch from a plan or review). Uses the Task template. Does not touch `.active` or `.session/`. |
| `task-start` (existing) | `active` | Unchanged: starting a task means doing it. |
| `task-switch` (existing) | old → `parked`, new → `active` | Unchanged except the old task is always parked (via task-park). |
| `task-park` (existing, changed) | `parked`, always | Writes `## Next`, `## Open loops` and a Log line, as now. Today it only sets `parked` when switching or stopping (`plugins/tasks/skills/task-park/SKILL.md:12`); drop that condition. Q decided: parking always means "not doing", including park-then-`/clear`; the parked task stays bound to the session (`.session/<id>`), so `/task` still shows it, but it sits in the Parked column until started or switched to again. |
| **SessionEnd hook** (new, `tasks` plugin) | session's task → `parked` | When a session ends (any reason except `/clear`, which `task-start` and `task-switch` tell the user to run right after activating a task; the hook input's `reason` is `"clear"`), if `Tasks/.session/<id>` names a task whose status is `active`, set it to `parked` and append a Log line `parked: session ended`. Leaves `.session/<id>` in place. Fails silently-but-logged (stderr) on unreadable notes, never blocks session end. Q chose this to keep Doing short over time. Builder's call: whether to skip parking when another session file written after this one names the same task. |
| **finish skill** (new, `tasks` plugin) | `done` + `finished: YYYY-MM-DD` | Writes a closing Log line with the outcome and any details the user adds (PR link, what shipped, what was dropped). Clears every `Tasks/.session/*` file that names this task (not only this session's), and `.active` when it names it, so no other session keeps showing a done task. (Our call: keeps the fix inside the skill instead of changing resolution.) |

Naming (builder's call, constraint): the finish skill must not collide with task-track's `/done`, which checks off a Next item. `task-finish` is the working name. Skill descriptions must route cleanly between `create-task`, `task-start`, the finish skill, `task-note` and `obsidian-vault` (run the `skill-trigger-reviewer` agent after editing descriptions).

`create-task` is how every non-started task gets made, including when Claude creates tasks while following `obsidian-vault`; `obsidian-vault`'s task-note guidance should point at it. `task-list` stops sorting `active` first by status alone only if that conflicts; it does change its "new task" pointer to `create-task`. (Our call.)

Obsidian installer in use is 1.11.7, so Bases board plugins (1.10+) work.

### Template

`examples/vault-starter/Templates/Task.md` changes `status: active` → `status: parked` and gains an empty `finished:` field. `task-start` sets `active` explicitly. (Our call: a note made any other way lands in the backlog.)

## Claude Code view: `/board` pane (task-track)

Option A from the mockups, with titles. A pane like `/task`, opened by a `/board` command with no model turn.

- Three columns: Doing · Parked · Done, each headed with a count.
- Card text = the note's first `# ` heading (all 68 current notes have one); fall back to the slug when absent.
- Cards grouped by project (`up:` link target, shown as the hub name); notes with no `up:` go under "No project".
- The session's task (same resolution as the `/task` pane) is highlighted.
- Done = `status: done` and `finished` within the last 7 days (inclusive of today, in the user's zone task-track already uses). Done notes with no `finished` are not shown.
- Header: vault name and the three counts. Vault = the session's vault (existing resolution). `/board <vault>` shows another vault from `vaults.json`.
- Long columns truncate with "… N more"; the builder picks the limit from pane height.
- Read-only. No buttons that change status.

Mockup: `.superpowers/brainstorm/91164-1793312096/content/board-pane-v2.html`.

## task-track resolution change

Today, among repo-matching notes, `resolve.ts` (and `vaults.py` / `session_task.py` in step) rank `active` above `parked` (`resolve.ts:50`, `:196`). With most notes parked, that ranking now means little. Q's direction: the shown task is the session's task, else the global `.active`. The repo match must no longer rank by status.

Open for the builder to confirm against tests: whether the repo-match step stays (unranked by status, still skipping `done`) or is removed. Our reading: keep it, drop the status tie-break, so a parked task bound to the repo still resolves. The Python and TypeScript sides and `plugins/task-track/tests/fixtures/vault-cases.ts`, `tests/test_vaults.py`, `tests/test_load_task.py` change together, and the prose in the `tasks` skills that restates the order is updated to match (AGENTS.md "Vault resolution").

## Obsidian view

- `Tasks.base` (starter and each vault) gains a board view grouped by `status`, column order parked → active → done, card title from the note title. The Done view and the board's done column filter on `finished` within the last 7 days, matching `/board`.
- The existing table views stay.
- Dragging a card rewrites `status:` in the note; that is the plugin's job. Dragging to Done does not set `finished` or write a Log line; the board will not show it under Done until `finished` is set. (Our call: accept this gap rather than build an Obsidian plugin. The finish skill is the proper path.)

### Setup installs the plugin

Setup covers new vaults (seed) and gains an **update existing vaults** step for vaults already in `vaults.json` (Q decided). For an existing vault:

- `Tasks.base`: merge the board view (and the `finished`-filtered Done view) into the existing file, keeping its other views, sorts and properties (personal has a custom `sort: started DESC`). If a merge isn't possible (unparseable YAML, a view with the same name but different content), ask before replacing; replace only after a backup.
- Plugin download: ask before downloading third-party code, per vault, with the plugin name, version and source URL.
- Existing community plugins (arryved has `meetings-plus`) are preserved in `community-plugins.json`.

Install steps, new or existing vault:

- Download a pinned release (`manifest.json`, `main.js`, `styles.css` if present) from the plugin's GitHub releases into `<vault>/.obsidian/plugins/<id>/`.
- Add `<id>` to `<vault>/.obsidian/community-plugins.json`.
- Back up any file it changes (existing `files.backup` helper).
- Tell the user Obsidian must be reloaded, and that community plugins must be allowed (restricted mode off) if they are not already.
- Skip with a clear message when offline or the release fetch fails; never half-install.

Plugin choice is the builder's, with these criteria: works with the Obsidian version in use (check `.obsidian` / installer; Bases board plugins need 1.10+), groups by a text property, drag rewrites the property, shows note title, maintained (release in the last 6 months), MIT or similar. Candidates: Kanban Bases View (zenobi-us), Bases Kanban, Kanban Base. Record the pick and the pinned version in the plan.

Docs: `docs/setup.md` documents the plugin install and the reload step.

## One-time cleanup of existing vaults

Notes today: personal 7 active / 12 parked / 6 done (live count changes), arryved 8 / 20 / 7, vail 3 / 4 / 1.

- A script or skill step lists every `active` note across all registered vaults (title, project, started, last Log date) and asks Q which stay in Doing. Nothing is written before Q approves the list.
- Others become `parked`, each gaining a Log line `- [[YYYY-MM-DD]] HH:MM — parked by status cleanup`.
- Every `done` note without `finished` gets `finished:` from the date of its last Log line; no Log date → leave empty and report it.
- Vault writes follow the `obsidian-vault` skill. Never delete Log or Open-loop lines.
- Not shipped to users as a recurring feature unless the builder finds it cheap to keep as a `create-task`/setup subcommand; Q's vaults need it once. Ongoing hygiene is the SessionEnd hook above.

## Versions and checks

- Bump `tasks` (0.5.0) and `task-track` (0.4.0) minor versions; bump `planner` only if its skills change (`plan-week` reads `active`/`parked`, unaffected).
- `claude plugin validate plugins/<name>` after each plugin edit; `python3 -m unittest discover -s tests`; `cd setup && uv run pytest`; `cd plugins/task-track && claude plugin test .`.
- `planner.plugin` rebuild only if `plugins/planner` changes.
- Add `.superpowers/brainstorm/` to `.gitignore` (mockups are scratch).

## Left to the builder

- Finish skill's final name.
- `/board` truncation limits, colors, keyboard handling.
- Board plugin pick and pinned version (criteria above).
- Whether cleanup is a script or an interactive skill run.
