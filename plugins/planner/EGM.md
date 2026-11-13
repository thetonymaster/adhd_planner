# planner plugin

## Overview

The `planner` plugin (manifest `.claude-plugin/plugin.json`, name `planner`): ADHD
planning skills for Claude Code and Cowork, plus a seed copy of the Python tools they
run. Skills carry the know-how; the scripts run from the user's planner folder, which
`/planner:setup` seeds from [tools/](./tools/EGM.md). Human guide: [README.md](./README.md).

## Subdirectories & Boundaries

- tools: [./tools/EGM.md](./tools/EGM.md) - seed copy of the Python scripts
  (`triage.py`, `plan_day.py`, `plan_week.py`, `task_queue.py`, `make_daily.py`,
  `make_insert.py`, `habits.py`, `add_event.py`, `setup_check.py`) and the `planner_config` /
  `planner_common` libraries, plus template data (`calendars.json`, `habits.json`,
  `inbox.md`).
- skills: twelve `SKILL.md` files, no code. Each runs `python3 tools/…` in the
  planner folder.
  - [add-event](./skills/add-event/SKILL.md) - `add_event.py`, then the calendar MCP
  - [blank-page](./skills/blank-page/SKILL.md) - `make_insert.py`
  - [break-down-task](./skills/break-down-task/SKILL.md)
  - [capture-triage](./skills/capture-triage/SKILL.md) - `triage.py`
  - [daily-page](./skills/daily-page/SKILL.md) - `make_daily.py`
  - [eod-shutdown](./skills/eod-shutdown/SKILL.md) - `triage.py`, `task_queue.py`, `plan_day.py`, `make_daily.py`
  - [habit-tracker](./skills/habit-tracker/SKILL.md) - `habits.py`
  - [morning-startup](./skills/morning-startup/SKILL.md) - `triage.py`, `task_queue.py`, `plan_day.py`, `make_daily.py`
  - [plan-day](./skills/plan-day/SKILL.md) - `task_queue.py`, `plan_day.py` (printing the day is a pointer to `make_daily.py`)
  - [plan-week](./skills/plan-week/SKILL.md) - `task_queue.py`, `plan_week.py --keep-order`
  - [schedule-workflow](./skills/schedule-workflow/SKILL.md) - scheduled prompt runs `triage.py`
  - [setup](./skills/setup/SKILL.md) - seeds the planner folder, `setup_check.py`, then a smoke
    test of `make_insert.py`, `triage.py`, `habits.py`, `plan_day.py`, `make_daily.py`
  - Every skill opens with the same `<!-- shared: where-this-runs -->` block (planner
    folder = Claude Code project dir or Cowork's `$HOME/mnt/<name>`; `.venv/bin/python3`
    when present; a missing `tools/planner_config.py` means stale tools → offer
    `planner:setup`).
- Cross-plugin: the skills hand off to the `tasks` plugin when it is installed, never
  require it. capture-triage suggests `/tasks:create-task` (backlog) or
  `/tasks:task-start` (start now) for a multi-step item; eod-shutdown runs
  `/tasks:task-park` for this vault's current task and routes "close one task" to
  `/tasks:task-finish`; `obsidian-vault` is used for vault writes.

## Invariants

- An installed plugin is read-only; every data file the scripts write lives in the
  user's planner folder, never here. Seeding never overwrites the user's data files
  (`calendars.json`, `habits.json`, `habits-log.json`, `inbox.md`) but does replace older
  tool scripts; this is a rule in `skills/setup/SKILL.md`, not enforced by code.
- Tool changes go in `tools/` here (what users get). Rebuild `planner.plugin` with
  `bash scripts/build-plugin.sh` after any change under `plugins/planner`; never edit
  `planner.plugin` by hand. The build excludes every `EGM.md`, so this file and
  `tools/EGM.md` never ship inside `planner.plugin`; editing only them needs no rebuild.
- Skill `description` fields carry routing ("not X, use Y"); check the sibling skills
  named when editing one, then run the `skill-trigger-reviewer` agent.
- Bump `version` in `.claude-plugin/plugin.json` when the plugin changes.
- The vault is optional: without one, every skill still works. Scheduled runs never
  touch the vault (the skills' "Vault (optional)" sections skip on an unattended run;
  schedule-workflow's EOD prompt says "Don't read or write the Obsidian vault").
- Attended runs with a vault (plan-week, plan-day, morning-startup, eod-shutdown) take
  their vault task list from `task_queue.py`, one row per task in rank order, and tell
  the user its `not_placed` rows and warnings; each checks first that
  `tools/task_queue.py` exists (stale tools → offer `planner:setup`). Unattended runs
  still do not read the vault; morning-startup's scheduled prompt leaves out week-plan
  rows marked `"source": "vault"`.
- Multi-vault (multi-vault spec, amended 2026-10-16; `docs/setup.md` "Several vaults"):
  with 2+ vaults registered in `$ADHD_PLANNER_VAULTS` / `~/.config/adhd-planner/vaults.json`,
  the six day-planning skills (morning-startup, plan-day, plan-week, eod-shutdown,
  capture-triage, break-down-task) use every registered vault that has `Tasks/` and
  `Daily/`, label items `<vault>:<slug>: …`, and write each item back to its own vault;
  items from no vault go to the current vault (the session-start `Vault:` line, else
  `default`). One vault: the `Vault:` line, else a connected folder named `vault`, else
  `$VAULT`, else `~/vault`. This prose is repeated per skill, not shared code.
- [README.md](./README.md) states the same multi-vault behaviour (items from no vault,
  such as calendar events and the planner's `inbox.md`, go to the current vault) and
  names the companion skills the skills use when installed: `obsidian-vault`,
  `/tasks:create-task`, `/tasks:task-start`, `/tasks:task-park`, `/tasks:task-finish`;
  none ships with this plugin, and each step works without them.

## Side Effects

- Through the skills: Google Calendar events (calendar MCP, always propose-first),
  planner-folder files (see [tools/EGM.md](./tools/EGM.md)), and, when a vault is
  connected, in each affected vault: the daily note (`## Plan`, Top 3, `## Shutdown`,
  `## Log` lines), task notes (`## Next` check-offs and subtasks, `## Log` lines; parking
  via `/tasks:task-park`) and the vault inbox (emptied by capture-triage).
- Setup seeds the planner folder (the eleven `.py` files, `calendars.json`, `habits.json`,
  `inbox.md`) and may create `.venv` there; it never touches the user's data files.

## Verification

- Run (repo root): `python3 -m unittest discover -s tests`
- Run: `claude plugin validate plugins/planner`
- Build: `bash scripts/build-plugin.sh` (validates, runs `tests/`, zips this folder
  minus `EGM.md`, `.DS_Store`, `__pycache__`, `*.pyc` into `planner.plugin`)
- After editing a skill `description`: run the `skill-trigger-reviewer` agent
  (`.claude/skills/planner-dev/agents/skill-trigger-reviewer.md`).
