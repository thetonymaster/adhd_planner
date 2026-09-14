# Planner tools

Print + sync tooling that turns the ADHD planner into a paper A5 planner
workflow and a live calendar dashboard.

## Contents

- `planner_common.py` — shared A5 drawing primitives (reportlab).
- `make_insert.py` — generate A5/A6 PDF inserts of the planner pages.
- `make_daily.py` — render a planner-style daily page from Google Calendar JSON.
- `out/` — generated PDFs (git-ignored).

## Requirements

```
pip install reportlab
```

## Quick start

```
python3 tools/make_insert.py --list           # see page ids
python3 tools/make_insert.py all              # all inserts, one PDF
python3 tools/make_insert.py priority-matrix  # a single insert

# daily page: save calendar list_events output to out/events.json first, then:
python3 tools/make_daily.py --date 2026-06-27 --events tools/out/events.json
```

## Skills

Installable skill drafts live in `../skills/`:
- `planner-insert` — drives `make_insert.py`
- `daily-page` — fetches calendar events and drives `make_daily.py`

The live dashboard is a Cowork artifact (`planner-dashboard`), not a file here.
