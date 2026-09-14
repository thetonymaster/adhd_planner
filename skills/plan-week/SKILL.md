---
name: plan-week
description: >
  Plan the whole week: take a backlog of tasks and spread it across the week's
  days by each day's free capacity around meetings, respecting deadlines and any
  fixed days, leaving slack so the week stays realistic. Produces a day-by-day
  weekly plan plus a ready-to-schedule task list for each day. Use when the user
  wants to look at the week rather than one day: "plan my week", "what should I
  work on which day", "map out this week", "spread these tasks across the week",
  "weekly plan/review/setup". For a single day's hour-by-hour time-blocking use
  plan-day; for today's full morning routine use morning-startup. Triggers:
  plan my week, map out the week, weekly plan, what do I do which day this week,
  spread my tasks across the week, sunday planning, weekly review.
---

# Plan the week

Distributes a task backlog across the week's days (Mon–Fri by default) around
real meetings — the weekly-level companion to `plan-day` (which blocks one day)
and `morning-startup` (which sets up today). Run commands from the planner folder.

## Inputs

- **tasks.json** — `[{"title": "...", "minutes": 90}, ...]`. Optional per task:
  `"deadline": "YYYY-MM-DD"` (won't be placed after that day) and
  `"day": "tue"` (pins it to that weekday). Build this from the user's backlog —
  the Today/Soon items from **capture-triage**, the inbox, or a list they give you.
- The **week start** (the Monday). Default is the current week.
- Working hours (default `09:00-18:00`), lunch (`14:00-15:00`), and a **load
  factor** (default `0.75` — plan only 75% of free time, leaving slack for the
  overruns and surprises ADHD weeks always bring).

## Steps

1. **Pull the week's meetings.** Google Calendar `list_events` from the Monday
   00:00 to the following Monday, across the calendars that hold real
   commitments. Save the raw output to `tools/out/busy-week.json`. All-day events
   are ignored for capacity. If no calendar access, skip `--busy` (every day gets
   full working hours).

2. **Right-size the backlog.** Any task bigger than a single day's usable
   capacity (~4–6 h) can't land on one day — decompose it first with
   **break-down-task** and feed the subtasks in. Add deadlines/pinned days where
   the user has them.

3. **Distribute across the week:**

   ```
   python3 tools/plan_week.py --tasks tools/out/tasks.json \
       --busy tools/out/busy-week.json --week-start <YYYY-MM-DD> \
       --work 09:00-18:00 --lunch 14:00-15:00 --load 0.75
   ```

   Add `--include-weekend` to use Sat/Sun too.

4. **Show the weekly plan** (`tools/out/weekly-plan-<week-start>.md`): each day's
   meetings, free vs. planned capacity, and the tasks assigned to it. Call out
   anything under "Didn't fit this week" and offer to defer it, decompose it, or
   extend hours.

5. **Offer the next moves** (don't auto-run):
   - **Time-block a specific day** — hand that day's `tools/out/tasks-<date>.json`
     to **plan-day** for hour-by-hour Pomodoro blocks.
   - **Print the week on paper** — generate the blank Weekly Schedule insert with
     **planner-insert** (`weekly-schedule`) to copy the plan into by hand.

## Behavior notes

- Each day's capacity = working window − lunch − that day's meetings, then × the
  load factor. A heavy-meeting day gets fewer tasks automatically.
- Placement respects deadlines (never after) and pinned days; among eligible
  days it picks the one with the most room, so work spreads out rather than
  piling on Monday.
- This is planning-level: it doesn't create calendar events. Day-level calendar
  push happens later, per day, via plan-day (propose-first).

## Scheduled run (how to automate)

A good weekly cadence is Sunday evening or Monday morning. Use schedule-workflow /
`create_scheduled_task` with e.g. **cron `0 17 * * 0`** (Sun 17:00) and a
self-contained prompt: pull the coming week's calendar → build the backlog from
`inbox.md`/triage → run `plan_week.py` → post the weekly plan and offer to
time-block Monday. Confirm the time first.
