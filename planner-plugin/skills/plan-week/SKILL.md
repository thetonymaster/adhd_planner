---
name: plan-week
description: >
  Spread a backlog of tasks across the coming week's days by each day's free
  capacity around real meetings, respecting deadlines and pinned days and leaving
  slack so the week stays realistic. Produces a day-by-day plan plus a
  ready-to-schedule task list for each day. Use when the user is looking at the
  week rather than one day: "plan my week", "what should I work on which day",
  "map out this week", "spread these tasks across the week", "sunday planning",
  "weekly review of my tasks". Not for a sales pipeline review or a standup
  summary, which are different weekly rituals entirely. For one day's hour-by-hour
  time-blocking use plan-day; for today's full morning routine use
  morning-startup.
---

# Plan the week

Distributes a task backlog across the week's days (Mon–Fri by default) around
real meetings — the weekly-level companion to `plan-day` (which blocks one day)
and `morning-startup` (which sets up today). Run commands from the planner folder.

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
   cd ~/mnt/<planner-folder> && python3 tools/plan_week.py --tasks tools/out/tasks.json \
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
     **blank-page** (`weekly-schedule`) to copy the plan into by hand.

## Behavior notes

- Each day's capacity = working window − lunch − that day's meetings, then × the
  load factor. A heavy-meeting day gets fewer tasks automatically.
- Placement respects deadlines (never after) and pinned days; among eligible
  days it picks the one with the most room, so work spreads out rather than
  piling on Monday.
- This is planning-level: it doesn't create calendar events. Day-level calendar
  push happens later, per day, via plan-day (propose-first).

## Running this on a schedule

Create it with `create_trigger` (`update_trigger` to change one, `list_triggers` to
see what's already set). Three things decide whether a firing actually does anything:

- **Cron is evaluated in UTC**, not local time. Convert first. America/Lisbon is
  UTC−6 year-round, so Sunday 17:00 is `0 23 * * 0`.
- **Pass `requires_local_device: true`** and name the planner folder. Each firing
  starts a fresh session in the cloud; without this it can't reach `tools/` at all and
  will quietly accomplish nothing.
- **Approvals stop an unattended run.** If the task isn't set to approve
  automatically, the firing halts at the first prompt with nobody there. Say this when
  you create it, and point at the task's own settings.

Each firing starts fresh with no memory of this conversation, so the prompt has to
carry everything — the folder, the date rule, the skill to follow, the exact commands,
and that it must not wait for input:

> Plan the coming week for the ADHD planner. Work in the connected planner folder;
> every command is `cd ~/mnt/<planner-folder> && …`. Use the timezone from
> `tools/calendars.json`; week start = the coming Monday. 1) Pull that week's calendar
> (Mon 00:00 to the following Mon) → `tools/out/busy-week.json`. 2) Build the backlog
> from `inbox.md` / the most recent `tools/out/tasks-*.json`. 3) `python3
> tools/plan_week.py --tasks tools/out/tasks.json --busy tools/out/busy-week.json
> --week-start <monday> --work 09:00-18:00 --lunch 14:00-15:00 --load 0.75`. 4) Post
> the weekly plan, call out anything that didn't fit, and offer — don't run —
> time-blocking Monday. Follow the planner:plan-week skill. Self-contained; don't wait
> for input.

Confirm the time with the user before creating it. Nothing is scheduled unless they ask.
