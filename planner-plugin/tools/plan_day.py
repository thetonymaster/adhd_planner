#!/usr/bin/env python3
"""Break-down-to-schedule engine with a meetings reconciler.

Takes a list of subtasks (with minute estimates) and a day of existing calendar
events, then lays Pomodoro focus blocks into the FREE gaps around those
meetings and a protected lunch — inside normal working hours. Emits:

  * a timed checklist to hand-copy into a planner (stdout + .md)
  * schedule.json        (every block, for inspection)
  * gcal-events.json     (focus blocks only, ready to push to Google Calendar)

Pomodoro defaults: 25 min work / 5 min break, a 30 min long break after every
4 focus sessions. All configurable.

Usage:
  python3 tools/plan_day.py --tasks tasks.json --busy busy.json --date 2026-06-30
  python3 tools/plan_day.py --tasks tasks.json --date 2026-06-30 \
      --work 09:00-18:00 --lunch 14:00-15:00 --work-min 25 --break-min 5 \
      --long-min 30 --long-every 4

tasks.json: [{"title": "...", "minutes": 60}, {"title": "...", "minutes": 25}]
busy.json:  the raw output of the calendar list_events tool (object or list).
"""
import argparse
import datetime as dt
import json
import os
import sys

def _load_timezone():
    """Read the IANA timezone from calendars.json (edit that file to set yours)."""
    import json as _json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendars.json")
    try:
        with open(path, encoding="utf-8") as _f:
            return _json.load(_f).get("timezone", "UTC")
    except Exception:
        print(f"WARNING: could not read a timezone from {path}; falling back to UTC. "
              f"Times will be wrong unless you are actually in UTC.", file=sys.stderr)
        return "UTC"


TZ_NAME = _load_timezone()


def hm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def parse_range(s):
    a, b = s.split("-")
    return parse_hm(a), parse_hm(b)


def load_busy(path, date_iso):
    """Extract fixed busy blocks (title, start_min, end_min) for the date."""
    if not path or not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    blobs = data if isinstance(data, list) else [data]
    out = []
    for blob in blobs:
        for ev in (blob.get("events", []) if isinstance(blob, dict) else []):
            start, end = ev.get("start", {}), ev.get("end", {})
            if "dateTime" not in start:
                continue  # skip all-day; they don't block time-of-day
            if not start["dateTime"].startswith(date_iso):
                continue
            s = _clock_min(start["dateTime"])
            e = _clock_min(end["dateTime"]) if "dateTime" in end else s + 30
            out.append([ev.get("summary", "(busy)"), s, e])
    return out


def _clock_min(iso):
    # take the wall-clock HH:MM as written on the calendar
    t = iso.split("T")[1]
    return parse_hm(t[:5])


def subtract(intervals, block):
    """Remove block [bs,be) from a list of free intervals."""
    bs, be = block
    result = []
    for s, e in intervals:
        if be <= s or bs >= e:
            result.append((s, e))
            continue
        if bs > s:
            result.append((s, bs))
        if be < e:
            result.append((be, e))
    return result


def schedule(tasks, busy, work, lunch, cfg):
    work_s, work_e = work
    fixed = []
    for title, s, e in busy:
        s, e = max(s, work_s), min(e, work_e)
        if e > s:
            fixed.append(("meeting", title, s, e))
    if lunch:
        ls, le = lunch
        fixed.append(("lunch", "Lunch", max(ls, work_s), min(le, work_e)))
    fixed.sort(key=lambda x: x[2])

    free = [(work_s, work_e)]
    for _, _, s, e in fixed:
        free = subtract(free, (s, e))
    free.sort()

    # task queue: list of [title, remaining_minutes]
    queue = [[t["title"], int(t.get("minutes", cfg["work"]))] for t in tasks]
    ti = 0
    session_count = 0
    last_title = None
    blocks = []  # (kind, title, start, end)

    for (fs, fe) in free:
        cursor = fs
        while ti < len(queue):
            room = fe - cursor
            if room < 5:
                break
            title, rem = queue[ti]
            L = min(cfg["work"], room, rem)
            # avoid silly slivers: only place <10 min if it finishes the task
            if L < 10 and L != rem:
                break
            if L < 5:
                break
            cont = (title == last_title)
            blocks.append(("focus", title + (" (cont.)" if cont else ""),
                           cursor, cursor + L))
            cursor += L
            rem -= L
            queue[ti][1] = rem
            session_count += 1
            last_title = title
            if rem <= 0:
                ti += 1
            # break, only if more work remains
            if ti < len(queue):
                brk = cfg["long"] if session_count % cfg["long_every"] == 0 else cfg["short"]
                kind = "longbreak" if brk == cfg["long"] else "break"
                if cursor + brk <= fe:
                    blocks.append((kind, "Long break" if kind == "longbreak" else "Break",
                                   cursor, cursor + brk))
                    cursor += brk
                else:
                    break

    for kind, title, s, e in fixed:
        blocks.append((kind, title, s, e))
    blocks.sort(key=lambda b: b[2])

    unscheduled = [(t[0], t[1]) for t in queue[ti:] if t[1] > 0]
    return blocks, unscheduled


MARK = {"focus": "▢", "break": "☕", "longbreak": "🌿", "meeting": "📅", "lunch": "🍽"}


def render_checklist(blocks, date, unscheduled):
    lines = [f"# Plan — {date.strftime('%A, %B %d, %Y')}", ""]
    for kind, title, s, e in blocks:
        mark = MARK.get(kind, "•")
        if kind == "focus":
            lines.append(f"{hm(s)}–{hm(e)}  {mark} Focus: {title}")
        else:
            lines.append(f"{hm(s)}–{hm(e)}  {mark} {title}")
    if unscheduled:
        lines += ["", "## Didn't fit today (carry over)"]
        for title, mins in unscheduled:
            lines.append(f"  ▢ {title} (~{mins} min left)")
    focus_n = sum(1 for b in blocks if b[0] == "focus")
    focus_min = sum(e - s for k, t, s, e in blocks if k == "focus")
    lines += ["", f"_Focus sessions: {focus_n} · {focus_min} min of deep work planned_"]
    return "\n".join(lines)


def gcal_events(blocks, date_iso):
    out = []
    for kind, title, s, e in blocks:
        if kind != "focus":
            continue
        out.append({
            "summary": "Focus: " + title.replace(" (cont.)", ""),
            "startTime": f"{date_iso}T{hm(s)}:00",
            "endTime": f"{date_iso}T{hm(e)}:00",
            "timeZone": TZ_NAME,
            "eventType": "FOCUS_TIME",
            "colorId": "9",  # Blueberry
        })
    return out


def daily_events(blocks, date_iso):
    """A list_events-shaped file that make_daily.py can render into a PDF page:
    includes focus blocks and meetings (skips breaks/lunch)."""
    events = []
    for kind, title, s, e in blocks:
        if kind in ("break", "longbreak", "lunch"):
            continue
        summ = ("Focus: " + title.replace(" (cont.)", "")) if kind == "focus" else title
        events.append({
            "summary": summ,
            "start": {"dateTime": f"{date_iso}T{hm(s)}:00"},
            "end": {"dateTime": f"{date_iso}T{hm(e)}:00"},
        })
    return {"summary": "Plan", "events": events}


def main():
    ap = argparse.ArgumentParser(description="Day scheduler + meetings reconciler")
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--busy", default=None, help="calendar list_events JSON")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--work", default="09:00-18:00")
    ap.add_argument("--lunch", default="14:00-15:00")
    ap.add_argument("--work-min", type=int, default=25)
    ap.add_argument("--break-min", type=int, default=5)
    ap.add_argument("--long-min", type=int, default=30)
    ap.add_argument("--long-every", type=int, default=4)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    date = dt.date.fromisoformat(args.date)
    with open(args.tasks) as f:
        tasks = json.load(f)
    busy = load_busy(args.busy, args.date)
    cfg = {"work": args.work_min, "short": args.break_min,
           "long": args.long_min, "long_every": args.long_every}

    blocks, unscheduled = schedule(
        tasks, busy, parse_range(args.work),
        parse_range(args.lunch) if args.lunch else None, cfg)

    out_dir = args.out_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)

    checklist = render_checklist(blocks, date, unscheduled)
    md_path = os.path.join(out_dir, f"plan-{args.date}.md")
    with open(md_path, "w") as f:
        f.write(checklist + "\n")
    with open(os.path.join(out_dir, f"schedule-{args.date}.json"), "w") as f:
        json.dump([{"kind": k, "title": t, "start": hm(s), "end": hm(e)}
                   for k, t, s, e in blocks], f, indent=2, ensure_ascii=False)
    gcal = gcal_events(blocks, args.date)
    with open(os.path.join(out_dir, f"gcal-events-{args.date}.json"), "w") as f:
        json.dump(gcal, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, f"daily-events-{args.date}.json"), "w") as f:
        json.dump(daily_events(blocks, args.date), f, indent=2, ensure_ascii=False)

    print(checklist)
    print("\n---")
    print(f"Wrote {md_path}")
    print(f"Focus blocks ready to push: {len(gcal)}  "
          f"(out/gcal-events-{args.date}.json)")
    if unscheduled:
        print(f"⚠ {len(unscheduled)} task(s) didn't fit — carry over or extend the day.")


if __name__ == "__main__":
    main()
