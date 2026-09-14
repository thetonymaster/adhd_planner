---
name: daily-page
description: >
  Use when someone wants one day of their actual Google Calendar printed as a
  paper page to fill in by hand. The defining combination: their real meetings
  on a timeline PLUS open space to handwrite tasks, notes, or a journal entry —
  printed or made into a page. This is what people mean by a "daily page",
  "daily sheet", "daily layout", or paper day page, for today, tomorrow, or
  a named weekday. Trigger on asks like "print my day", "make a printable daily
  sheet for tomorrow with my events", "print today's calendar so I can
  jot/journal by hand", or "daily page with meetings on the left and room for
  tasks". The page must be filled from real events — send a blank/empty template
  to planner-insert and the full morning plan-and-print routine to
  morning-startup; not for merely listing, adding, scheduling, or time-blocking
  events.
---

# Calendar → planner daily page

Turns a day of Google Calendar events into a print-ready A5 daily page that
matches the A5 planner's daily layout. Run commands from the planner folder so
`tools/` resolves; `pip install reportlab` if it isn't already.

## Steps

1. **Resolve the date.** Default to today (in the user's timezone). Confirm if
   the user said "tomorrow", a weekday, etc.

2. **Fetch events** with the Google Calendar `list_events` tool for the target
   day, using the user's primary calendar. To include birthdays, family, etc.,
   also query those calendars and combine the results. Use a window of
   `YYYY-MM-DDT00:00:00` to `YYYY-MM-DDT23:59:59`.

3. **Save the raw results to JSON.** Write the tool output to a file. The
   script accepts either a single `{summary, events:[...]}` object or a JSON
   **list** of them (one per calendar), e.g. `tools/out/events.json`.

4. **(Optional) Build a tasks file** with subtasks for the right column. Run the
   **break-down-task** skill, then save as `tools/out/day-tasks.json`:

   ```json
   [
     {"title":"Draft Q3 planning doc","subtasks":["Outline","Intro","Review pass"]},
     {"title":"Review pull requests","subtasks":["PR #12","PR #15"]}
   ]
   ```

5. **Render** the page:

   ```
   python3 tools/make_daily.py --date <YYYY-MM-DD> --events tools/out/events.json \
       --tasks tools/out/day-tasks.json
   ```

   Useful flags: `--start 5 --end 24` to widen the timeline (default 6–23),
   `--out path.pdf` to choose the output. `--tasks` is optional.

6. **Share** the resulting `tools/out/daily-<date>.pdf` with present_files.

## Layout

Two columns under the date header + all-day banner:

- **Left — Schedule:** hourly timeline showing only meetings/calendar events
  as labeled blocks (time range, title, location/video-call).
- **Right:** a blank **Top 3 today**, then **Tasks** — each task with a checkbox
  and its subtasks nested as smaller checkboxes — then a dot-grid **Notes** area
  filling the remaining space.

Print at 100% on A5 (or two-up on A4 and cut) so it tucks into the A5 planner.
Tasks that don't fit are dropped so Notes always has room.

## Automating it

Offer to schedule this every morning (e.g. 6:00) so a fresh daily page is ready
each day — fetch the day's events, render, and present the PDF.

## Implementation

`tools/make_daily.py` (+ shared `tools/planner_common.py`). Pure Python +
reportlab. It parses event start/end from ISO datetimes (offset-aware) and
all-day `date` fields; the wall-clock time as written on the calendar is what
gets placed on the timeline.
