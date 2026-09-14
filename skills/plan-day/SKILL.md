---
name: plan-day
description: >
  Time-blocking and focus-block scheduling for a task list the user already
  has. Use this to answer "when do I do each of these today?" — taking several
  tasks or a to-do list and laying them out as timed work sessions that fit
  into the free gaps around the user's meetings, calls, and lunch so nothing
  overlaps. Typical asks: schedule these tasks, block out focus time for these,
  build me a time-blocked plan, lay my to-dos out as focus blocks, fit these
  around my calendar, protect my lunch, or order and time them so they don't
  collide. It uses Pomodoro-style blocks within working hours and, once
  confirmed, adds them to Google Calendar. Not for booking a single meeting or
  event, the full morning routine (morning-startup), sorting a raw brain dump
  into tasks (capture-triage), or splitting one big task into subtasks
  (break-down-task).
---

# Plan the day (schedule + meetings reconciler)

Slots focus work around real meetings and produces a paper-ready plan.

Run everything from the planner folder so `tools/` resolves. `pip install
reportlab` is only needed if you'll also print the page (step 5), not for the
scheduler itself.

## Inputs

- **tasks.json** — `[{"title": "...", "minutes": 50}, ...]`. Write this from the
  user's task list. If they gave you loose text, turn it into that shape (title +
  a rough minute estimate each). If they have one big fuzzy task, run
  **break-down-task** first; if they have a messy pile of thoughts, run
  **capture-triage** first (it emits this file).
- The user's **working hours** (default `09:00-18:00`) and **lunch**
  (default `14:00-15:00`).
- **Pomodoro config** (defaults): 25 min work, 5 min break, 30 min long break
  after every 4 focus sessions.

## Before scheduling: right-size the tasks

The scheduler places one block per task, so tasks that are too big or vague
schedule badly — a 3-hour "write the report" becomes one undifferentiated slab
you'll bounce off of. Before building `tasks.json`, scan the tasks and **decompose
any that are big or fuzzy** (rule of thumb: longer than ~50 min, or not a concrete
next action). Follow the **break-down-task** skill to split each one into
concrete subtasks with estimates (roughly 10–90 min each — the scheduler slices
anything over 25 min into consecutive Pomodoros automatically), then feed those
subtasks — not the original — into `tasks.json`. Tasks that are already small and
concrete pass through untouched.

This keeps decomposition in one place (break-down-task owns *how* to split;
plan-day just calls it when a task needs it), so the two skills compose cleanly
rather than duplicating logic.

## Steps

1. **Fetch the day's meetings** with the Google Calendar `list_events` tool for
   the target date, across the calendars that hold real commitments (ask which,
   or use the user's primary). Save the raw output to `tools/out/busy.json`
   (a single object or a list of them — either works). All-day events like
   birthdays are ignored for time-blocking automatically. If there's no calendar
   access, skip this and omit `--busy` — the scheduler then uses the whole
   working day.

2. **Run the scheduler** (use the actual target date, e.g. today):

   ```
   python3 tools/plan_day.py --tasks tools/out/tasks.json \
       --busy tools/out/busy.json --date <YYYY-MM-DD> \
       --work 09:00-18:00 --lunch 14:00-15:00
   ```

   Config flags: `--work-min 25 --break-min 5 --long-min 30 --long-every 4`.
   (Omit `--busy` if you have no meetings file.)

3. **Show the timed checklist** (printed to stdout, also `tools/out/plan-<date>.md`).
   This is the copy-to-planner output — read it back to the user. If any task
   "didn't fit", tell them and offer to extend hours or carry it over.

4. **Push to Google Calendar — propose first.** The run also writes
   `tools/out/gcal-events-<date>.json` (focus blocks only, tagged as Focus Time,
   Blueberry color). Show the proposed blocks and ask for confirmation. On "yes",
   create each with the calendar `create_event` tool:
   - `summary`, `startTime`, `endTime`, `timeZone` come straight from the JSON,
   - use `eventType: "FOCUS_TIME"` and `colorId: "9"`,
   - default to the primary calendar unless the user picked a dedicated one.
   Never create events without explicit confirmation.

## Behavior notes

- The reconciler never overlaps meetings or lunch; breaks are dropped when they'd
  collide with a fixed block or the end of a gap.
- Blocks shorter than 10 min are skipped (left as buffer) unless they finish a task.
- Long meetings simply shrink the available focus time; overflow is reported.

## Companion

To also print the day as a planner daily **page** (not just the checklist),
feed `gcal-events-<date>.json` — merged with `busy.json` — to
`tools/make_daily.py` (see the planner-daily skill).
