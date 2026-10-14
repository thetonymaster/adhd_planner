# planner

ADHD-friendly planning for Cowork. Twelve skills that turn an A5 paper planner plus
Google Calendar into one workflow: capture and triage what's on your mind, break big
tasks into startable steps, time-block them around your real meetings, print pages to
fill in by hand, and track habits with streaks.

Install: see [docs/setup.md](../../docs/setup.md) (Claude Code: `claude plugin install planner@adhd-planner`; Cowork: add the marketplace `thetonymaster/adhd_planner`).

## How it's put together

| Lives in this plugin | Lives in your planner folder |
|---|---|
| the 12 skills | `tools/*.py` (the scripts that actually run) |
| a seed copy of `tools/` | `calendars.json`, `habits.json`, `habits-log.json` |
| | `inbox.md`, `inbox-archive.md`, `tools/out/` |

The split matters: a plugin is read-only once installed, and every one of those data
files gets **written** — `setup` edits `calendars.json`, `triage.py` clears `inbox.md`,
`habits.py` appends to the log. So the plugin carries the know-how and a template, and
your folder carries your data and the running code.

Practically: connect your planner folder to the session, and the skills run
`python3 tools/…` there. If you don't have a folder yet, run **`/planner:setup`** — it
seeds one from the copies bundled here and walks you through configuring it.

## Obsidian vault (optional)

If your Obsidian vault is connected (a folder named `vault`, or `$VAULT` / `~/vault`
with `Tasks/` and `Daily/`), the planning skills use it too: morning-startup and
plan-day write the Top 3 and the timed plan into today's daily note, capture-triage
also empties the vault inbox, break-down-task writes subtasks into the task note,
plan-week pulls open Next items from task notes, and eod-shutdown reads the day's log,
parks the active task and seeds tomorrow's note. With several vaults in `~/.config/adhd-planner/vaults.json`, the skills use the session's vault (the `Vault:` line) and only that one. Without a vault nothing changes.
Scheduled (unattended) runs never touch the vault. The skills also use
`obsidian-vault`, `/tasks:task-start` and `/tasks:task-park` when they're installed; none of
them ships with this plugin, and each step works without them.

## The skills

| skill | what it does |
|---|---|
| `capture-triage` | Sort a brain dump into Today/Soon/Eventually + a priority matrix |
| `break-down-task` | Split one big task into ~25-min startable subtasks with estimates |
| `plan-day` | Time-block a task list into the gaps around your meetings (Pomodoro 25/5) |
| `plan-week` | Spread a backlog across the week by each day's free capacity |
| `add-event` | Add meetings/appointments/birthdays, routed to the right calendar |
| `daily-page` | Print an A5 day: your real meetings left, tasks + notes right |
| `blank-page` | Print blank A5 inserts (priority matrix, sleep, weekly…) to fill in by hand |
| `habit-tracker` | Log sleep / eating / commitment habits with streaks |
| `morning-startup` | Chain: calendar → Top 3 → break down → plan-day → print |
| `eod-shutdown` | Review the day, migrate leftovers, wind down, seed tomorrow |
| `schedule-workflow` | Put any of the above on an automatic schedule |
| `setup` | First-run: check requirements, wire your calendars, smoke-test everything |

## Requirements

- A connected planner folder (this is where everything reads and writes).
- **Python 3.10+** and **reportlab** (`pip install reportlab`) on the machine holding
  that folder — only needed for the two printing skills.
- A **Google Calendar** connector, for anything that touches your real schedule.
  Everything else works without it.
