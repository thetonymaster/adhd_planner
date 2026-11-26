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
| `task_queue.py` | plan-week, plan-day, morning-startup, eod-shutdown |
| `period_note.py` | plan-week, morning-startup |
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

Two tools touch a vault, only at the `--vault` paths the skill passes: `task_queue.py`
reads task notes and never writes them; `period_note.py` creates period notes and writes
their Recurring sections, only in vaults that have `Recurring.md`. `period_note.py` is
the one tool that writes in a vault, and it writes period notes only.

```
python3 tools/task_queue.py --vault "vault=$HOME/vault" [--date 2026-11-18] [--out queue.json]
```

## Week and month notes

A vault opts in by having `Recurring.md` at its root: one repeat rule per line.

```
- [ ] Weekly review (~30 min) — every: mon #id/weekly-review
- [ ] Pay rent — every: month 1 #id/rent
- [ ] Close books — every: month last #id/close-books
- [ ] SLO review — every: month first-tue #id/slo-review
```

Rules: `mon`..`sun` (weekly), `month <1-31>` (past the month's end, its last day),
`month last`, `month first-<mon..sun>`. Lines inside fenced code blocks are ignored.

```
python3 tools/period_note.py ensure --vault "vault=$HOME/vault" --plan-week   # the week plan_week.py plans
python3 tools/period_note.py ensure --vault "vault=$HOME/vault" --date 2026-12-07
```

It creates `Monthly/<YYYY-MM>.md` for each month the week touches, then
`Weekly/<GGGG-Www>.md`, each with that period's occurrences, and prints one line per
note (`Wrote`, `Unchanged`, `Off`, `Skipped`, `Warning`). A vault without
`Recurring.md` is reported `Off` and never written. Exit 1 when a note was Skipped,
2 on bad arguments.

## Shared helpers

`planner_config.py` holds what several tools must agree on: `load()` for
`calendars.json`, `monday_of` and `plan_days` (which days a week plan covers), the ISO
week helpers `iso_week`, `week_month` (the month of the week's Thursday) and
`months_touched`, `write_atomic(path, text, prefix)`, and the argument checks `fail`,
`iso_date`, `parse_day` and `parse_vaults(values, require=())`.

## Quick start

```
uv venv .venv && uv pip install --python .venv reportlab   # needed by the PDF generators
# without uv: python3 -m venv .venv && .venv/bin/pip install reportlab; then run the tools with .venv/bin/python3
.venv/bin/python3 tools/setup_check.py                  # what's ready, what's missing
.venv/bin/python3 tools/make_insert.py --list           # available blank pages
.venv/bin/python3 tools/make_insert.py priority-matrix  # one A5 insert
```
