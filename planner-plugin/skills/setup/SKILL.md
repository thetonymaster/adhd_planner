---
name: setup
description: >
  First run for the planner: verify the planner folder and its tools, install what's
  missing, set the timezone and wire up the user's real Google calendars, record
  their commitments, smoke-test every script, and confirm the whole thing works.
  Use when someone is getting started with THIS planner — "set up the planner",
  "configure my planner", "onboard me to the planner", "the planner isn't working",
  "check my planner install" — or when another planner skill finds the folder
  unconfigured. Not for setting up Claude, Cowork, plugins or anything else: this
  skill only ever touches the planner folder and its config files.
---

# Planner setup

Configures and verifies all the other planner skills in one pass. Walk the user
through it conversationally; confirm before writing files.

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

1. **Run the doctor** to see what's ready and what's missing:

   ```
   cd ~/mnt/<planner-folder> && python3 tools/setup_check.py
   ```

   Read the checklist back. It reports Python, reportlab, the tool scripts, the
   timezone, calendar ids, commitments, and the inbox. Address items top to bottom.

2. **Dependencies.** If reportlab is missing:

   ```
   pip install reportlab        # or: pip install reportlab --break-system-packages
   ```

   (Python 3.10+ is required — if that fails, the user needs a newer Python.)

3. **Timezone.** Ask the user's city / IANA timezone and set `"timezone"` in
   `tools/calendars.json` (e.g. `America/New_York`, `Europe/Madrid`,
   `America/Lisbon`, `Europe/Madrid`).

4. **Calendars.** If the Google Calendar connector is available, call
   `list_calendars`, show the user their calendars, and map each to a tag in
   `tools/calendars.json` — fill in the `id` for each tag they want (work,
   personal, family, birthdays, or custom ones they name). Confirm the mapping,
   then write it. If no connector is connected, tell them calendar features are
   optional and they can paste ids later (Google Calendar → Settings → Integrate
   calendar → Calendar ID).

5. **Commitments & habits.** Ask for their 1–3 current commitments and reword any
   habit labels they want; write them into `habits.json`, replacing the
   `<edit me>` placeholders. Keep the sleep/eating starter habits unless they
   want changes.

6. **Smoke-test every tool** (each should produce output with no error):

   ```
   cd ~/mnt/<planner-folder> && python3 tools/make_insert.py priority-matrix
   cd ~/mnt/<planner-folder> && python3 tools/triage.py parse
   cd ~/mnt/<planner-folder> && python3 tools/habits.py list
   printf '[{"title":"Test task","minutes":25}]' > tools/out/_setup_tasks.json
   cd ~/mnt/<planner-folder> && python3 tools/plan_day.py --tasks tools/out/_setup_tasks.json --date $(date +%F)
   cd ~/mnt/<planner-folder> && python3 tools/make_daily.py --date $(date +%F) --events tools/out/_setup_tasks.json
   ```

   (make_daily on a tasks-only file just renders an empty schedule — fine for the
   test.) If any step errors, fix it before continuing.

7. **Re-run the doctor** and confirm it reports ready:

   ```
   cd ~/mnt/<planner-folder> && python3 tools/setup_check.py
   ```

8. **Hand off.** Tell the user what to try first, mapped to the skills:
   - jot lines in `inbox.md`, then "sort my inbox" → capture-triage
   - "break down <task> and plan my day" → break-down-task + plan-day
   - "print a priority-matrix insert" / "print today's daily page"
   - "add a dentist appointment Thursday 9am" → add-event
   - "log my habits" → habit-tracker
   And mention `schedule-workflow` for automating morning/EOD runs.

## What this skill can't do

Installing the skills into Cowork and enabling **Settings → Capabilities → Code
execution and file creation** are one-time app steps the user does themselves —
point them to the README. This skill handles everything inside the project folder.
