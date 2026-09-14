---
name: add-event
description: >
  Add specific meetings, appointments, events, and important/recurring dates
  (birthdays, anniversaries) to Google Calendar — routed to the right calendar
  (work / personal / family / birthdays) with the right color, recurrence,
  all-day handling, and reminders. Use whenever the user names a concrete thing
  to put on a calendar: schedule a meeting, book an appointment, save a birthday,
  add a deadline, put it on a specific calendar. This is for individual entries
  the user dictates — NOT for auto-scheduling a whole task list around meetings
  (use plan-day for that). Triggers: add to calendar, schedule a meeting with X
  at Y, book the dentist, save this birthday, remind me every year, put it on my work or
  family calendar.
---

# Add events to Google Calendar (with routing)

Creates calendar entries on the correct calendar, tagged and recurring as needed.

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

## Calendars (tags)

Defined in `tools/calendars.json`. Type a **tag**; it resolves to the real
calendar + default color:

The tag list is **not fixed** — it is whatever the user has in
`tools/calendars.json`. Read that file before routing anything and use the tags
you actually find; never assume a tag name from this document. Each entry maps a
tag to a real calendar id, a default colour, and the event types it serves
(`for: [...]`).

A tag whose `id` is still empty is a placeholder, and `add_event.py` refuses to
create on it. That guard is deliberate — surface it and offer to fill the id in
(`list_calendars`, or Google Calendar > Settings > Integrate calendar >
Calendar ID) rather than silently routing somewhere else.

## Types (pick defaults automatically)

The `type_defaults` block in `calendars.json` decides which tag each type routes
to, so read it rather than assuming:

- **meeting** → timed, 30-min reminder, may have guests + Google Meet.
- **event** → timed, 30-min reminder.
- **important** → all-day, **repeats yearly**, reminder the day before.

Any default can be overridden per entry (`tag`, `colorId`, `recurring`,
`reminderMin`, `allDay`).

## Steps

1. **Collect the details** from the user. Ask only for what's missing (title,
   date, and — if timed — start/end). Infer the type and tag; confirm the
   calendar if ambiguous.

2. **Write a spec file** — a JSON list, e.g. `tools/out/new-events.json`:

   ```json
   [
     {"type":"meeting","title":"1:1 with Alex","date":"2026-07-02",
      "start":"15:00","end":"15:45","attendees":["friend@example.com"],"meet":true},
     {"type":"important","title":"Sam's birthday","date":"2026-07-10"},
     {"type":"event","title":"Dentist","date":"2026-07-03","start":"09:00",
      "end":"10:00","tag":"personal","location":"Downtown clinic"}
   ]
   ```

3. **Normalize + preview:**

   ```
   cd ~/mnt/<planner-folder> && python3 tools/add_event.py tools/out/new-events.json
   ```

   This prints a confirmation table and the exact `create_event` argument
   objects (routing, color, recurrence, all-day, reminders applied). It never
   touches the calendar.

4. **Confirm, then create.** Show the confirmation table to the user. On "yes",
   call the calendar `create_event` tool once per object, passing its fields
   straight through (`summary`, `startTime`, `endTime`, `timeZone`,
   `calendarId`, `colorId`, and any of `allDay`, `attendees`, `addGoogleMeetUrl`,
   `location`, `description`, `recurrenceData`, `overrideReminders`,
   `eventType`). Report back links/success.

## Notes

- Times are wall-clock in the timezone set in `tools/calendars.json`; the `timeZone` field makes
  Google interpret them correctly regardless of offset.
- Birthdays/anniversaries: use `type: "important"` for an all-day yearly event.
  For a one-off important date, add `"recurring": null`.
- To add several dates at once (e.g. a list of birthdays), put them all in the
  spec list — one confirmation, one batch.
- Update `tools/calendars.json` if a calendar id changes or you add a new tag.
