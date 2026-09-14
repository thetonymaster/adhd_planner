# Planner Skills

A set of ADHD-friendly planning skills for Claude (Cowork). They turn a paper
A5 planner + Google Calendar into one workflow: capture and triage what's on your
mind, break tasks down, time-block them around your real meetings, print a daily
page, add events to the right calendar, and track habits with streaks.

Everything runs locally with small Python scripts; no accounts or servers.

## What's inside

**Skills** (`skills/`)

| skill | what it does |
|---|---|
| `capture-triage` | Sort a brain dump into Today/Soon/Eventually + a priority matrix |
| `break-down-task` | Split a big task into ~25-min startable subtasks with estimates |
| `plan-day` | Time-block tasks into free gaps around your meetings (Pomodoro 25/5) |
| `plan-week` | Spread a task backlog across the week's days by each day's free capacity |
| `add-event` | Add meetings/events/important days, routed to the right calendar |
| `daily-page` | Print an A5 daily page: meetings on the left, tasks + notes on the right |
| `planner-insert` | Print blank A5 planner-page inserts (priority matrix, sleep, etc.) |
| `habit-tracker` | Log daily habits (sleep, eating, commitments) with streaks |
| `morning-startup` | Chain: calendar → Top 3 → break down → plan-day → print |
| `eod-shutdown` | Review the day, migrate leftovers, wind down, seed tomorrow |
| `schedule-workflow` | Put any of the above on an automatic schedule |

**Tools** (`tools/`) — the Python scripts the skills call, plus:
- `calendars.json` — your calendar routing map (edit this).
- **Data files** (`habits.json`, `inbox.md`) — your editable planner data.

## Requirements

- The Claude desktop app with **Cowork**.
- **Python 3.10+** and **reportlab**: `pip install reportlab`
- A **Google Calendar** connector enabled in Claude (for calendar features).
- In Claude **Settings → Capabilities**, turn on **Code execution and file creation**.

## Install (Cowork)

1. **Put this folder somewhere permanent** on your computer, e.g.
   `~/planner-skills`.

2. **Connect it as your Cowork folder.** In Cowork, select/allow this folder as
   the working folder. The skills run `python3 tools/…` relative to it, so it
   must be the folder Claude is working in.

3. **Install the skills.** Either:
   - **Upload:** Settings → Capabilities → Skills → add each folder inside
     `skills/`, **or**
   - **Copy:** put each folder from `skills/` into `~/.claude/skills/`
     (so you have `~/.claude/skills/plan-day/SKILL.md`, etc.). Personal skills
     there are auto-discovered.

4. **Configure your calendars.** Edit `tools/calendars.json`:
   - set `"timezone"` to your IANA zone (e.g. `America/New_York`, `Europe/Madrid`),
   - fill each calendar's `"id"` (Google Calendar → Settings → *Integrate calendar*
     → *Calendar ID*), or ask Claude "list my calendars and wire the ids".
   Add or rename tags freely.

5. **Set your habits & commitments.** Edit `habits.json` — reword habits and
   replace the two commitment placeholders with your real 1–3 commitments.

## Try it

With the folder connected, just ask Claude things like:
- "Print a priority-matrix insert" → `planner-insert`
- "Sort my inbox" (after jotting lines in `inbox.md`) → `capture-triage`
- "Break down 'ship the report' and plan my day" → `break-down-task` + `plan-day`
- "Add a dentist appointment Thursday 9am" → `add-event`
- "Print tomorrow's daily page" → `daily-page`
- "Log my habits: bedtime, morning fuel" → `habit-tracker`

## Automating (optional)

The `schedule-workflow` skill sets up recurring runs (e.g. morning startup at
08:30, EOD shutdown at 18:00). Each skill's **"Scheduled run"** section has a
ready-to-use cron and prompt. In the scheduled prompts, replace `<PLANNER_DIR>`
with the real path to this folder on your machine. Scheduled tasks run only while
the desktop app is open.

## Notes

- All calendar-writing is **propose-first**: Claude shows what it will create and
  waits for your confirmation.
- `tools/out/` is scratch output (PDFs, JSON) and is safe to delete anytime.
- The scripts have no third-party dependencies except `reportlab` (for PDFs).

## Sources for the install steps

- [Use skills in Claude — Help Center](https://support.claude.com/en/articles/12512180-use-skills-in-claude)
- [How to create custom skills — Help Center](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
- [Extend Claude with skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
