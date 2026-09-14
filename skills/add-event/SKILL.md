---
name: add-event
description: >
  Add meetings, events, appointments, and important/recurring days to Google
  Calendar, routed to the right calendar with the right color, recurrence,
  all-day handling, and reminders. Use when the user wants to schedule a
  meeting, add an appointment or event, save a birthday/anniversary/important
  date, or block time — including "put it on my Personal/Family/work calendar".
  Triggers: add to calendar, schedule a meeting, new event, save this birthday,
  remind me every year, put on my <calendar> calendar, book time.
---

# Add events to Google Calendar (with routing)

Creates calendar entries on the correct calendar, tagged and recurring as needed.

## Calendars (tags)

Defined in `tools/calendars.json`. Type a **tag**; it resolves to the real
calendar + default color:

| tag        | calendar        | good for                         |
|------------|-----------------|----------------------------------|
| `formal`   | Formal (primary)| meetings, work — default         |
| `personal`     | Personal            | personal events, appointments    |
| `family`  | Family         | family                           |
| `birthdays`| Birthdays     | birthdays, important dates       |
| `community` | Community        | community / church               |
| `hobby`| Hobby       | hobby events                 |
| `acme`| Acme       | work (id not set yet)            |
| `side`     | Side            | Side (id not set yet)            |

`acme` and `side` are placeholders — their `id` in `tools/calendars.json`
is empty, so `add_event.py` will refuse to create on them until the calendars
exist and are shared with this Google account. Once they're visible, run
`list_calendars` and paste the ids into `calendars.json`.

## Types (pick defaults automatically)

- **meeting** → Formal, timed, 30-min reminder, may have guests + Google Meet.
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
     {"type":"meeting","title":"1:1 with Sel","date":"2026-07-02",
      "start":"15:00","end":"15:45","attendees":["friend@example.com"],"meet":true},
     {"type":"important","title":"Birthdays de Mariana","date":"2026-07-10"},
     {"type":"event","title":"Dentist","date":"2026-07-03","start":"09:00",
      "end":"10:00","tag":"personal","location":"Main Street Clinic"}
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

- Times are wall-clock in `America/Lisbon`; the `timeZone` field makes
  Google interpret them correctly regardless of offset.
- Birthdays/anniversaries: use `type: "important"` for an all-day yearly event.
  For a one-off important date, add `"recurring": null`.
- To add several dates at once (e.g. a list of birthdays), put them all in the
  spec list — one confirmation, one batch.
- Update `tools/calendars.json` if a calendar id changes or you add a new tag.
