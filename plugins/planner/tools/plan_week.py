#!/usr/bin/env python3
"""Weekly planner — distribute a task backlog across the week's days.

Where plan_day.py time-blocks a single day, this spreads a list of tasks across
Mon–Fri (or Mon–Sun) by each day's *free capacity* — the working hours left after
meetings and lunch — leaving some slack unplanned so the week stays realistic.
It respects per-task deadlines and optional fixed days.

Output:
  * weekly-plan-<week-start>.md  — day-by-day plan + capacity + overflow
  * tasks-<YYYY-MM-DD>.json       — one file per planned day, ready for plan_day.py

Usage:
  python3 tools/plan_week.py --tasks tasks.json --busy busy-week.json \
      --week-start 2026-07-06 [--load 0.75] [--include-weekend]
  --work / --lunch override calendars.json.

tasks.json: [{"title":"...","minutes":90,"deadline":"2026-07-08","day":"tue"}]
  deadline and day are optional. day is a weekday name/abbrev pinning the task.
busy.json:  raw calendar list_events output (object or list) spanning the week.
"""
import argparse
import datetime as dt
import json
import os
import sys

WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday",
                 "saturday", "sunday"]
ABBR = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planner_config  # noqa: E402

try:
    CFG = planner_config.load()
except planner_config.ConfigError as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(2)

def parse_hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def parse_range(s):
    a, b = s.split("-")
    return parse_hm(a), parse_hm(b)


def hm(minutes):
    return f"{minutes // 60}h{minutes % 60:02d}" if minutes % 60 else f"{minutes // 60}h"


def load_busy_by_day(path):
    """Return {date_iso: total_meeting_minutes} and {date_iso: [titles]}."""
    mins, titles = {}, {}
    if not path or not os.path.exists(path):
        return mins, titles
    data = json.load(open(path, encoding="utf-8"))
    blobs = data if isinstance(data, list) else [data]
    for blob in blobs:
        for ev in (blob.get("events", []) if isinstance(blob, dict) else []):
            start, end = ev.get("start", {}), ev.get("end", {})
            if "dateTime" not in start:
                continue  # skip all-day
            d = start["dateTime"][:10]
            s = parse_hm(start["dateTime"].split("T")[1][:5])
            e = parse_hm(end["dateTime"].split("T")[1][:5]) if "dateTime" in end else s + 30
            mins[d] = mins.get(d, 0) + max(0, e - s)
            titles.setdefault(d, []).append(ev.get("summary", "(busy)"))
    return mins, titles


def monday_of(date):
    return date - dt.timedelta(days=date.weekday())


def distribute(tasks, day_dates, capacity):
    """Assign tasks to days. capacity: {date_iso: usable_minutes} (mutated).
    Returns {date_iso: [task,...]}, overflow list."""
    plan = {d: [] for d in day_dates}
    remaining = dict(capacity)
    overflow = []

    # pinned tasks first
    pinned, free = [], []
    for t in tasks:
        (pinned if t.get("day") else free).append(t)

    def place(task, day):
        plan[day].append(task)
        remaining[day] -= int(task.get("minutes", 25))

    for t in pinned:
        idx = ABBR.get(str(t["day"]).lower()[:3])
        target = None
        if idx is not None:
            for d in day_dates:
                if dt.date.fromisoformat(d).weekday() == idx:
                    target = d
                    break
        if target:
            place(t, target)
        else:
            overflow.append(t)

    # free tasks: deadline asc (none last), then largest first for tighter packing
    def sort_key(t):
        dl = t.get("deadline") or "9999-99-99"
        return (dl, -int(t.get("minutes", 25)))

    for t in sorted(free, key=sort_key):
        mins = int(t.get("minutes", 25))
        dl = t.get("deadline")
        eligible = [d for d in day_dates if (not dl or d <= dl)]
        # prefer the eligible day with the MOST remaining capacity that still fits
        fits = [d for d in eligible if remaining[d] >= mins]
        if fits:
            target = max(fits, key=lambda d: remaining[d])
            place(t, target)
        else:
            overflow.append(t)
    return plan, overflow


def render(plan, day_dates, cap_free, cap_usable, meet_titles, overflow, week_start):
    lines = [f"# Week of {week_start.strftime('%A, %B %d, %Y')}", ""]
    for d in day_dates:
        date = dt.date.fromisoformat(d)
        planned = sum(int(t.get("minutes", 25)) for t in plan[d])
        header = f"## {date.strftime('%a %b %d')}"
        lines.append(header)
        mt = meet_titles.get(d, [])
        if mt:
            lines.append(f"_Meetings ({len(mt)}): " + ", ".join(mt) + "_")
        lines.append(f"_Free {hm(cap_free[d])} · planning up to {hm(cap_usable[d])} · "
                     f"assigned {hm(planned)}_")
        if plan[d]:
            for t in plan[d]:
                dl = f" (due {t['deadline']})" if t.get("deadline") else ""
                lines.append(f"- [ ] {t['title']} — {t.get('minutes',25)}m{dl}")
        else:
            lines.append("- (open — no tasks assigned)")
        lines.append("")
    if overflow:
        lines.append("## Didn't fit this week")
        for t in overflow:
            lines.append(f"- [ ] {t['title']} — {t.get('minutes',25)}m"
                         + (f" (due {t['deadline']})" if t.get("deadline") else ""))
        lines.append("")
    total_assigned = sum(int(t.get('minutes',25)) for d in day_dates for t in plan[d])
    lines.append(f"_Planned {hm(total_assigned)} of focus work across "
                 f"{len(day_dates)} days; {len(overflow)} task(s) overflowed._")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Distribute tasks across the week")
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--busy", default=None, help="calendar list_events JSON for the week")
    ap.add_argument("--week-start", default=None, help="Monday date YYYY-MM-DD (default this week)")
    ap.add_argument("--work", default=None, help="HH:MM-HH:MM (default: calendars.json, else 09:00-18:00)")
    ap.add_argument("--lunch", default=None, help='HH:MM-HH:MM, or "" for none (default: calendars.json)')
    ap.add_argument("--load", type=float, default=0.75,
                    help="fraction of free time to fill (rest left as slack)")
    ap.add_argument("--include-weekend", action="store_true")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    if args.week_start:
        week_start = dt.date.fromisoformat(args.week_start)
    else:
        week_start = monday_of(dt.date.today())
    n_days = 7 if args.include_weekend else 5
    day_dates = [(week_start + dt.timedelta(days=i)).isoformat() for i in range(n_days)]

    work_s, work_e = CFG["work"] if args.work is None else parse_range(args.work)
    lunch = CFG["lunch"] if args.lunch is None else (parse_range(args.lunch) if args.lunch else None)
    lunch_min = (min(lunch[1], work_e) - max(lunch[0], work_s)) if lunch else 0
    lunch_min = max(0, lunch_min)
    day_window = (work_e - work_s) - lunch_min

    meet_min, meet_titles = load_busy_by_day(args.busy)
    cap_free = {d: max(0, day_window - meet_min.get(d, 0)) for d in day_dates}
    cap_usable = {d: int(cap_free[d] * args.load) for d in day_dates}

    tasks = json.load(open(args.tasks, encoding="utf-8"))
    plan, overflow = distribute(tasks, day_dates, dict(cap_usable))

    out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)
    md = render(plan, day_dates, cap_free, cap_usable, meet_titles, overflow, week_start)
    md_path = os.path.join(out_dir, f"weekly-plan-{week_start.isoformat()}.md")
    open(md_path, "w", encoding="utf-8").write(md + "\n")

    made = []
    for d in day_dates:
        if plan[d]:
            p = os.path.join(out_dir, f"tasks-{d}.json")
            json.dump([{"title": t["title"], "minutes": int(t.get("minutes", 25))}
                       for t in plan[d]], open(p, "w", encoding="utf-8"),
                      indent=2, ensure_ascii=False)
            made.append(os.path.basename(p))

    print(md)
    print("\n---")
    print(f"Wrote {md_path}")
    print(f"Per-day task files for plan_day.py: {', '.join(made) if made else '(none)'}")
    if overflow:
        print(f"⚠ {len(overflow)} task(s) didn't fit — decompose, extend the week, or defer.")


if __name__ == "__main__":
    main()
