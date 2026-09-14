---
name: habit-tracker
description: >
  Track daily habits with streaks across sleep/bedtime, eating/fuel, and your
  active commitments (from the planner's Sustain + Commitments layouts). Log what
  you did today, see current streaks and 7-day marks, and get a weekly adherence
  review. Use when the user wants to check off habits, "did I keep my streak",
  log a habit, or review how the week went. Triggers: habits, streak, log my
  habits, did I do, habit check-in, weekly habit review, track my routine.
---

# Habit tracker

Daily habit logging with streaks, for sleep, eating, and commitments.

## Files

- `habits.json` (repo root) — the habits being tracked, grouped by `area`
  (`sleep` / `eating` / `commitment`). Edit freely; set the two commitment
  placeholders to the user's real 1–3 commitments before first use.
- `habits-log.json` (repo root) — the daily marks. Managed by the script.

## Commands

```
python3 tools/habits.py list                          # show habits + ids
python3 tools/habits.py log --done sleep-bedtime,eat-morning   # log TODAY
python3 tools/habits.py log --done eat-midday --date 2026-07-01
python3 tools/habits.py status --days 7                # streaks + recent marks
python3 tools/habits.py week --date 2026-07-01         # 7-day grid
```

A `log` records the **whole day**: ids you pass are done (✓); every other habit
is counted as missed (✗) for that date. So log once, at the end of the day, with
everything you actually did.

## Daily check-in flow

1. Show the habit list (or the areas the user cares about) and ask which they did
   today — sleep, eating, and each commitment.
2. Run `habits.py log --done <ids>` for today.
3. Show the returned streak view; call out streaks worth protecting and any habit
   slipping (low 30-day %). Keep it encouraging, not judgy.

## Weekly review

Run `habits.py week` (and `status`) at the end of the week: read the grid, name
the wins (longest streaks, best-kept area), pick **one** habit to focus on next
week. Tie environment tweaks back to the Eating-strategies / Sleep pages.

## Fits with other skills

- **eod-shutdown** is the natural place to run the daily check-in — add a
  "log today's habits" step there.
- Reviewing commitments here pairs with a periodic commitments check-in.

## Scheduled run (how to automate)

For an automatic daily habit check-in, use schedule-workflow / `create_scheduled_task`
with **cron `0 21 * * *`** (21:00 daily) and a self-contained prompt:

> Run the habit check-in for the ADHD planner at <PLANNER_DIR>
> (timezone <YOUR_TIMEZONE>, today's date). Post today's habit list from
> `python3 tools/habits.py list`, ask which sleep / eating / commitment habits were
> done today, then `python3 tools/habits.py log --done <ids>` and show the streak
> view. On Sundays also run `python3 tools/habits.py week` and give a short weekly
> review with one focus habit for next week. Follow skills/habit-tracker/SKILL.md.

Confirm the time before creating. Nothing is scheduled until the user asks.
