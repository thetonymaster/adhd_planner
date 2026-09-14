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
  at Y, book the dentist, save this birthday, remind me every year, put it on my
  <name> calendar.
---

# Add events to Google Calendar (with routing)

Creates calendar entries on the correct calendar, tagged and recurring as needed.

## Calendars (tags)

Defined in `tools/calendars.json`. Type a **tag**; it resolves to the real
calendar + default color:

| tag         | calendar   | good for                      |
|-------------|------------|-------------------------------|
| `work`      | Work       | meetings, work — default      |
| `personal`  | Personal   | personal events, appointments |
| `family`    | Family     | family                        |
| `birthdays` | Birthdays  | birthdays, important dates     |

Add your own tags in `tools/calendars.json`. Each tag needs a real calendar
`id` — until it's filled in, `add_event.py` refuses to create on it (a safety
guard). Get an id from Google Calendar > Settings > Integrate calendar >
Calendar ID, or run `list_calendars` and paste it in.

## Types (pick defaults automatically)

- **meeting** → Work, timed, 30-min reminder, may have guests + Google Meet.
- **event** → Personal, timed, 30-min reminder.
- **important** → Birthdays, all-day, **repeats yearly**, reminder the day before.

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
   python3 tools/add_event.py tools/out/new-events.json
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

- Times are wall-clock in `<YOUR_TIMEZONE>`; the `timeZone` field makes
  Google interpret them correctly regardless of offset.
- Birthdays/anniversaries: use `type: "important"` for an all-day yearly event.
  For a one-off important date, add `"recurring": null`.
- To add several dates at once (e.g. a list of birthdays), put them all in the
  spec list — one confirmation, one batch.
- Update `tools/calendars.json` if a calendar id changes or you add a new tag.
