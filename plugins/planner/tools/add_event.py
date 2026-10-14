#!/usr/bin/env python3
"""Normalize event specs into Google Calendar `create_event` arguments, with
calendar routing, colors, recurrence, all-day, and reminders applied.

This does NOT touch the calendar itself (a script can't call the MCP tool). It
turns a friendly spec into the exact kwargs Claude should pass to `create_event`,
plus a human-readable confirmation table to show the user first.

Spec input (JSON list). Each item:
  {
    "type": "meeting" | "event" | "important",   # picks defaults
    "title": "1:1 with Alex",
    "date": "2026-07-02",                          # YYYY-MM-DD
    "start": "15:00", "end": "15:45",              # omit for all-day
    "tag": "formal",                               # optional calendar override
    "attendees": ["a@b.com"],                       # meetings
    "meet": true,                                   # add Google Meet link
    "location": "Centro",
    "recurring": "yearly" | "monthly" | "weekly" | null,
    "reminderMin": 30,                              # override
    "notes": "agenda…"
  }

Usage:
  python3 tools/add_event.py events.json                 # print args + table
  python3 tools/add_event.py events.json --json out.json # also save kwargs
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RRULE = {"yearly": "RRULE:FREQ=YEARLY", "monthly": "RRULE:FREQ=MONTHLY",
         "weekly": "RRULE:FREQ=WEEKLY", "daily": "RRULE:FREQ=DAILY"}


def load_map():
    with open(os.path.join(HERE, "calendars.json")) as f:
        return json.load(f)


def next_day(date_iso):
    import datetime as dt
    d = dt.date.fromisoformat(date_iso) + dt.timedelta(days=1)
    return d.isoformat()


def resolve_tag(spec, cmap):
    typ = spec.get("type", "event")
    tdef = cmap["type_defaults"].get(typ, cmap["type_defaults"]["event"])
    tag = spec.get("tag") or tdef["tag"]
    if tag not in cmap["calendars"]:
        raise ValueError(f"unknown calendar tag '{tag}' (have: "
                         f"{', '.join(cmap['calendars'])})")
    if not cmap["calendars"][tag].get("id"):
        raise ValueError(
            f"calendar '{tag}' has no id yet — create or share the "
            f"'{cmap['calendars'][tag]['summary']}' calendar in Google Calendar, "
            f"then set its id in tools/calendars.json (or ask Claude to fetch it).")
    return tag, tdef


def build(spec, cmap):
    tag, tdef = resolve_tag(spec, cmap)
    cal = cmap["calendars"][tag]
    tz = cmap["timezone"]
    all_day = spec.get("allDay", tdef.get("allDay", False))
    date = spec["date"]

    kw = {
        "summary": spec["title"],
        "calendarId": cal["id"],
        "colorId": spec.get("colorId", cal["colorId"]),
        "timeZone": tz,
    }

    if all_day or not spec.get("start"):
        kw["allDay"] = True
        kw["startTime"] = f"{date}T00:00:00"
        kw["endTime"] = f"{next_day(date)}T00:00:00"
    else:
        kw["startTime"] = f"{date}T{spec['start']}:00"
        kw["endTime"] = f"{date}T{spec.get('end', spec['start'])}:00"

    if spec.get("type") == "meeting":
        kw["eventType"] = "DEFAULT"
    if spec.get("attendees"):
        kw["attendees"] = [{"email": e} for e in spec["attendees"]]
    if spec.get("meet"):
        kw["addGoogleMeetUrl"] = True
    if spec.get("location"):
        kw["location"] = spec["location"]
    if spec.get("notes"):
        kw["description"] = spec["notes"]

    rec = spec.get("recurring", tdef.get("recurring"))
    if rec:
        if rec not in RRULE:
            raise ValueError(f"unknown recurrence '{rec}'")
        kw["recurrenceData"] = [RRULE[rec]]

    rmin = spec.get("reminderMin", tdef.get("reminderMin"))
    if rmin is not None:
        kw["overrideReminders"] = [{"method": "popup", "minutes": int(rmin)}]

    return tag, cal["summary"], kw


def confirm_row(tag, cal_summary, kw):
    when = ("all day " + kw["startTime"][:10]) if kw.get("allDay") \
        else f"{kw['startTime'][:10]} {kw['startTime'][11:16]}–{kw['endTime'][11:16]}"
    bits = [when, f"→ {cal_summary}"]
    if kw.get("recurrenceData"):
        bits.append("repeats " + kw["recurrenceData"][0].split("FREQ=")[1].lower())
    if kw.get("attendees"):
        bits.append(f"{len(kw['attendees'])} guest(s)")
    if kw.get("addGoogleMeetUrl"):
        bits.append("Meet")
    return f"• {kw['summary']}\n    " + "  ·  ".join(bits)


def main():
    ap = argparse.ArgumentParser(description="Normalize events into create_event args")
    ap.add_argument("spec", help="JSON file: a list of event specs (or one object)")
    ap.add_argument("--json", default=None, help="save normalized kwargs here")
    args = ap.parse_args()

    with open(args.spec) as f:
        data = json.load(f)
    specs = data if isinstance(data, list) else [data]
    cmap = load_map()

    all_kw, rows = [], []
    for spec in specs:
        try:
            tag, cal_summary, kw = build(spec, cmap)
        except (KeyError, ValueError) as e:
            print(f"ERROR in spec {spec!r}: {e}", file=sys.stderr)
            sys.exit(1)
        all_kw.append(kw)
        rows.append(confirm_row(tag, cal_summary, kw))

    print("Proposed calendar entries (confirm before creating):\n")
    print("\n".join(rows))
    print(f"\n{len(all_kw)} entr{'y' if len(all_kw)==1 else 'ies'}. "
          "Pass each object below to create_event.\n")
    print(json.dumps(all_kw, indent=2, ensure_ascii=False))

    if args.json:
        with open(args.json, "w") as f:
            json.dump(all_kw, f, indent=2, ensure_ascii=False)
        print(f"\nSaved kwargs → {args.json}")


if __name__ == "__main__":
    main()
