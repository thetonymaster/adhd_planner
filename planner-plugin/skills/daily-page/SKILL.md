---
name: daily-page
description: >
  Print one day of the user's real Google Calendar as an A5 paper page to fill in
  by hand — their actual meetings on a timeline, plus open space to handwrite
  tasks, notes or a journal entry. This is what "daily page", "daily sheet",
  "daily layout" or "paper day page" means, for today, tomorrow or a named
  weekday. Trigger on "print my day", "a printable daily sheet for tomorrow with
  my events", "print today's calendar so I can journal by hand". The page must be
  filled from real events: a blank template is blank-page, and the full
  plan-and-print morning routine is morning-startup. This skill owns planner-page
  PDFs end to end — the value is the A5 layout, not PDF handling, so prefer it
  over any general-purpose PDF skill whenever the output is a planner page.
---

# Calendar → planner daily page

Turns a day of Google Calendar events into a print-ready A5 daily page that
matches the A5 planner's daily layout. Run commands from the planner folder so
`tools/` resolves; `pip install reportlab` if it isn't already.

## Where this runs

`tools/` and the data it reads and writes (`calendars.json`, `habits.json`,
`inbox.md`) live in the **connected planner folder on the user's computer**, not in
this plugin — a plugin is read-only, and these files get written. So every command
below runs there, via the device shell.

Each device shell call is a fresh shell with no memory of the last one's working
directory, so the `cd` has to ride along on every command, exactly as written below.
Substitute the real folder name for `<planner-folder>` (check what's connected).

If no planner folder is connected, say so and stop rather than guessing a path —
`planner:setup` seeds a new one from the copies bundled with this plugin.

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
   cd ~/mnt/<planner-folder> && python3 tools/make_daily.py --date <YYYY-MM-DD> --events tools/out/events.json \
       --tasks tools/out/day-tasks.json
   ```

   Useful flags: `--start 5 --end 24` to widen the timeline (default 6–23),
   `--out path.pdf` to choose the output. `--tasks` is optional.

6. **Deliver it.** The PDF is written straight into `tools/out/` in the planner folder on the
   user's computer, so it is **already delivered** — tell them the filename and where it
   landed, and they can open it from there. Only stage and send a copy into the chat if
   they ask for one (say, they're away from that machine).

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
