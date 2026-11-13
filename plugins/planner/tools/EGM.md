# planner tools

## Overview

Seed copy of the Python scripts behind the `planner` plugin's skills. An installed
plugin is read-only, so `/planner:setup` copies this folder into the user's planner
folder, and skills run `python3 tools/…` there. A change to a tool belongs here: this
is what users get. Standard library only, except the PDF generators
(`make_daily.py`, `make_insert.py` via `planner_common.py`), which need `reportlab`.
The human guide is [README.md](./README.md).

The scripts do file mechanics only. Judgment (triage buckets, estimates) and every
calendar call (the Google Calendar MCP) stay with Claude: scripts read JSON that
Claude saved and write JSON that Claude passes on. The one exception is
`task_queue.py`, which reads task notes, read-only, from vault paths the skill passes.

## Interface

| Script | CLI | Used by skill |
|---|---|---|
| `triage.py` | `parse [--inbox]`, `apply --decisions F [--inbox] [--date]`, `carry --items F [--inbox]` | capture-triage, eod-shutdown, morning-startup, schedule-workflow, setup |
| `plan_day.py` | `--tasks F [--busy F] [--date] [--work] [--lunch] [--work-min] [--break-min] [--long-min] [--long-every] [--out-dir]` | plan-day, morning-startup, eod-shutdown, setup |
| `plan_week.py` | `--tasks F [--busy F] [--week-start] [--work] [--lunch] [--load 0.75] [--include-weekend] [--out-dir]` | plan-week |
| `make_daily.py` | `--events F [--date] [--tasks F] [--start 6] [--end 23] [--out]` | daily-page, morning-startup, eod-shutdown, setup |
| `make_insert.py` | `<page>\|all [--size a5\|a6] [--out]`, `--list` | blank-page, setup |
| `habits.py` | `list`, `log [--done ids] [--date]`, `status [--days 7]`, `week [--date]` | habit-tracker, setup |
| `add_event.py` | `spec.json [--json out]` | add-event |
| `task_queue.py` | `--vault NAME=PATH [--vault ...] [--week-start D \| --date D] [--include-weekend] [--out F]` | none yet (the planning skills adopt it) |
| `setup_check.py` | no arguments; read-only checklist | setup |

Library modules:

- `planner_config.py`: `load(path=PATH) -> {timezone, work, lunch, pomodoro}`,
  `parse_range`, `DEFAULTS`, `ConfigError`, `monday_of`, `plan_days(today,
  week_start, include_weekend) -> (monday, [ISO days])` (shared by `plan_week.py`
  and `task_queue.py`, so both plan the same days). Reads `calendars.json` beside it.
- `planner_common.py`: A5/A6 drawing primitives on reportlab: `Sheet`,
  `new_canvas(path, size)`, palette constants (`INK`, `MUTED`, `LINE`, `ACCENT`,
  `ACCENT_SOFT`, `DOT`), `TAGS`, `MARGIN`, `A5`, `A6`, `mm`.

Seed data files (templates, copied by setup):

- `calendars.json`: `timezone`, `calendars` routing map, `type_defaults` (required by
  `add_event.py`), `work`, `lunch`, `pomodoro`.
- `habits.json`, `inbox.md`: copied to the planner folder **root**, not `tools/`.

## Invariants

- Path layout is fixed relative to the script: `calendars.json` is read from
  `tools/`; `habits.json`, `habits-log.json`, `inbox.md` and `inbox-archive.md`
  from the parent folder (`ROOT = dirname(tools/)`). Generated files go to
  `tools/out/` unless `--out`/`--out-dir` is given.
- Config precedence for day settings: command-line flag, then `calendars.json`,
  then `planner_config.DEFAULTS` (UTC, 09:00-18:00, lunch 14:00-15:00, 25/5/30/4).
  `"lunch": null` or `""` means no protected lunch.
- `planner_config.load` raises `ConfigError` with the file path and bad value for
  invalid JSON, unknown `pomodoro.*` keys, non-positive minutes, bad `HH:MM-HH:MM`
  ranges and non-IANA timezones; a missing file only warns and uses defaults.
  `plan_day.py` / `plan_week.py` exit 2 on `ConfigError`. This covers `calendars.json` only:
  `--work` / `--lunch` flags go through each script's own `parse_range`, so a malformed flag
  is a traceback (exit 1) and a reversed range is accepted. `add_event.py` reads
  `calendars.json` with plain `json.load` (no `ConfigError`) and exits 1 on a bad spec.
- `planner_common.py` exits 2 with an install hint when `reportlab` is missing.
- `triage.py apply` rewrites `inbox.md` atomically (temp file + `os.replace`,
  keeping the file mode) as `INBOX_TEMPLATE` plus the kept lines: every `- ` item
  (decided or not; all are archived verbatim), blank lines, empty `- ` placeholders
  and template lines are dropped; any other line is kept. `carry` appends with a
  plain `open(..., "a")`, not atomically.
- `plan_week.py` writes `week-tasks-<date>.json`, never `tasks-<date>.json`
  (that name belongs to `triage.py`).
- `habits.py log` only adds marks for habits still in `habits.json`: the day is rebuilt
  from that file, so marks for removed ids are dropped. Unknown ids print an error and
  exit 0. `habits-log.json` is written directly (not atomic).
- `add_event.py` never calls the calendar; it prints `create_event` kwargs and a
  confirmation table for Claude to show first.
- `task_queue.py` is the one tool that reads a vault: read-only, only from the
  `--vault` paths the caller gives (it never resolves vaults itself), every
  `Tasks/*.md` whose `status` is not `done`. Its ordering rule `sort_key(task, until)`
  is the only coded copy. It exits 2 for a malformed, repeated, missing or
  `Tasks/`-less `--vault`, else 0 (also when every task is in `not_placed`). Its last
  output line is always `Wrote <path>`.
- `setup_check.py` is read-only; it exits 1 when any check is a blocker, else 0.
- Seeding by setup is additive: existing `calendars.json`, `habits.json`,
  `habits-log.json` and `inbox.md` are user data and are never overwritten. This is a
  rule in `skills/setup/SKILL.md`; nothing in `tools/` enforces it.

## Side Effects

- `triage.py apply`: writes `tasks-<date>.json` (Today do/schedule items, the
  plan-day input) then `triage-<date>.md` (written last: morning-startup trusts the
  task list only when the summary is at least as new) to `tools/out/`, appends archived items to `inbox-archive.md`, rewrites `inbox.md`.
  `carry` appends leftovers to `inbox.md`.
- `plan_day.py`: writes `plan-<date>.md`, `schedule-<date>.json`,
  `gcal-events-<date>.json`, `daily-events-<date>.json` to the out dir.
- `plan_week.py`: writes `weekly-plan-<week-start>.md` and one
  `week-tasks-<date>.json` per planned day; on a re-run, deletes the
  `week-tasks-<date>.json` of any day that now has no tasks.
- `make_daily.py`, `make_insert.py`: write PDFs to `tools/out/`.
- `task_queue.py`: writes one `task-queue/1` JSON file (`format`, `first_day`,
  `until`, `tasks`, `not_placed`, `warnings`): a new `tools/out/queue-run-<random>.json`
  allocated with `tempfile.mkstemp` (two runs never share one), or `--out F`. On each
  run it deletes `tools/out/queue-run-*.json` files more than a day old; other names
  are left alone. Writes nothing in a vault.
- `habits.py log`: rewrites `habits-log.json`.
- `add_event.py --json`: writes the normalized kwargs file.
- `tools/out/` and `__pycache__/` are git-ignored (`.gitignore`).

## Verification

- Run (repo root): `python3 -m unittest discover -s tests`
  (covers `test_triage`, `test_plan_day`, `test_plan_week`, `test_planner_config`,
  `test_task_queue`, `test_setup_check`, `test_habits`, `test_pdf_hint`, and `test_skill_files` for the `tools/out/` file
  names the skills hand each other, among others).
- Run: `claude plugin validate plugins/planner`
- After changing anything here, rebuild the Cowork upload: `bash scripts/build-plugin.sh`
  (it zips `plugins/planner`, leaving out `EGM.md` files).
