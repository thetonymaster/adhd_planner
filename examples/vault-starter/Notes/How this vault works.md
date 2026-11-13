---
up: "[[Home]]"
created: 2026-10-12
tags: [note]
---
# How this vault works

## Summary
Folders say what a note is. `up:` links say where it belongs. Tags say its status or type.

## Details
- **00 Inbox** — capture fast, sort later. New notes land here by default.
- **Daily** — one note per day: Top 3, brain dump, log. Claude appends session lines to the Log.
- **Tasks** — one note per task. Claude reads `Next` + `Open loops` at session start. A session shows its own task: the one it switched to, else the task whose `repo:` is the folder it runs in, else `.active`.
- **Projects** (has an end) / **Areas** (ongoing) — hubs. Everything links up to one.
- **Notes** — knowledge worth keeping: concepts, runbooks, decisions.
- **People** — who you work with and what's open with them.

Graph colors: orange projects · purple areas · blue tasks · green notes · teal people · gray daily.

## Task priority
A task note has two optional keys, right after `up:`:
- `priority:` — `p0` (highest) to `p5`. Empty, missing or anything else (`high`, `P1`, `p9`) counts as `p3`.
- `due:` — `YYYY-MM-DD`, or empty. A hard limit: the planner won't place the task's next work after it.

| Level | Meaning |
|---|---|
| p0 | Do first, ahead of everything, including tasks with a due date |
| p1 | High |
| p2 | Above normal |
| p3 | Normal (the default) |
| p4 | Low: when there is room |
| p5 | Someday |

**What a hub shows.** The `## Tasks` list on a project or area lists the open tasks whose `up:` is that hub, with priority, due date and status. Order: `p0` tasks first, then tasks due within 7 days (soonest first), then the rest by priority; a task with no priority shows as `p3`. It approximates the planner's order; a plan can differ slightly.

**Changing a task's priority.** Ask Claude (the `task-note` skill: "set [task] to p1"), or edit `priority:` in the note's properties in Obsidian.

## Related
- [[Home]]
