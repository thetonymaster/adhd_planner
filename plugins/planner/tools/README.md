# Planner tools

The Python behind the `planner` plugin's skills. Pure standard library except for
the two PDF generators, which need `reportlab`.

| script | used by |
|---|---|
| `triage.py` | capture-triage, eod-shutdown |
| `plan_day.py` | plan-day, morning-startup, eod-shutdown |
| `plan_week.py` | plan-week |
| `make_daily.py` | daily-page, morning-startup, eod-shutdown |
| `make_insert.py` | blank-page |
| `habits.py` | habit-tracker |
| `add_event.py` | add-event |
| `task_queue.py` | ranked list of open task notes across vaults (read-only; vault paths passed with `--vault`) |
| `setup_check.py` | setup |
| `planner_common.py` | shared A5 drawing primitives (reportlab) |

## Data files

These live alongside `tools/` in the planner folder and are read *and written* by the
scripts — they are your data, not part of the plugin:

- `tools/calendars.json` — timezone + calendar routing map. Edit this first.
  `work`, `lunch`, `pomodoro` — your day; `plan_day.py` and `plan_week.py` read them (flags override).
- `habits.json` / `habits-log.json` — tracked habits and their daily marks.
- `inbox.md` / `inbox-archive.md` — capture inbox and its archive.
- `tools/out/` — generated PDFs, plans and task files (git-ignored), including
  `task_queue.py`'s `queue-run-*.json` files, which it deletes after a day.

`task_queue.py` is the one script that reads a vault, and only reads it:

```
python3 tools/task_queue.py --vault "vault=$HOME/vault" [--date 2026-11-18] [--out queue.json]
```

## Quick start

```
uv venv .venv && uv pip install --python .venv reportlab   # needed by the PDF generators
# without uv: python3 -m venv .venv && .venv/bin/pip install reportlab; then run the tools with .venv/bin/python3
.venv/bin/python3 tools/setup_check.py                  # what's ready, what's missing
.venv/bin/python3 tools/make_insert.py --list           # available blank pages
.venv/bin/python3 tools/make_insert.py priority-matrix  # one A5 insert
```
