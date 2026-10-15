#!/usr/bin/env python3
"""Daily habit tracker with streaks — sleep, eating, and commitments.

Habits are defined in habits.json (repo root). Daily marks are stored in
habits-log.json as { "YYYY-MM-DD": { "habit-id": true|false } }. A logged day
records every habit: those you did (true) and, implicitly, the rest as missed.
Logging the same day again adds to it; nothing done is un-done.

Commands:
  python3 tools/habits.py list
  python3 tools/habits.py log  --done sleep-bedtime,eat-morning [--date YYYY-MM-DD]
  python3 tools/habits.py status [--days 7]        # streaks + recent marks
  python3 tools/habits.py week   [--date YYYY-MM-DD]
"""
import argparse
import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "habits.json")
LOG = os.path.join(ROOT, "habits-log.json")
AREA_ORDER = ["sleep", "eating", "commitment"]
AREA_LABEL = {"sleep": "Sleep", "eating": "Eating / fuel", "commitment": "Commitments"}


def load_cfg():
    with open(CFG, encoding="utf-8") as f:
        return json.load(f)["habits"]


def load_log():
    if not os.path.exists(LOG):
        return {}
    with open(LOG, encoding="utf-8") as f:
        return json.load(f)


def save_log(log):
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False, sort_keys=True)


def by_area(habits):
    groups = {}
    for h in habits:
        groups.setdefault(h["area"], []).append(h)
    return groups


def cmd_list(args):
    groups = by_area(load_cfg())
    for area in AREA_ORDER:
        if area not in groups:
            continue
        print(f"\n{AREA_LABEL.get(area, area)}")
        for h in groups[area]:
            print(f"  {h['id']:<16} {h['label']}")


def cmd_log(args):
    habits = load_cfg()
    ids = {h["id"] for h in habits}
    done = [x.strip() for x in (args.done or "").split(",") if x.strip()]
    unknown = [d for d in done if d not in ids]
    if unknown:
        print("Unknown habit id(s): " + ", ".join(unknown))
        print("Run `habits.py list` to see valid ids.")
        return
    log = load_log()
    before = log.get(args.date, {})
    # Merge: a later check-in the same day adds to it; what was done stays done.
    day = {h["id"]: bool(before.get(h["id"])) or h["id"] in done for h in habits}
    log[args.date] = day
    save_log(log)
    n = sum(day.values())
    print(f"Logged {args.date}: {n}/{len(habits)} habits done.")
    _print_status(habits, log, days=7)


def _streak(habit_id, log, end_date):
    """Consecutive days done, counting back from end_date."""
    d = dt.date.fromisoformat(end_date)
    streak = 0
    while True:
        key = d.isoformat()
        if key in log and log[key].get(habit_id):
            streak += 1
            d -= dt.timedelta(days=1)
        else:
            break
    return streak


def _recent_marks(habit_id, log, dates):
    out = []
    for key in dates:
        if key in log:
            out.append("✓" if log[key].get(habit_id) else "✗")
        else:
            out.append("·")
    return "".join(out)


def _adherence(habit_id, log, dates):
    logged = [k for k in dates if k in log]
    if not logged:
        return None
    done = sum(1 for k in logged if log[k].get(habit_id))
    return round(100 * done / len(logged))


def _print_status(habits, log, days=7):
    today = dt.date.today()
    recent = [(today - dt.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    last30 = [(today - dt.timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    groups = by_area(habits)
    print(f"\nLast {days} days (oldest→today):  ✓ done  ✗ missed  · no log\n")
    for area in AREA_ORDER:
        if area not in groups:
            continue
        print(AREA_LABEL.get(area, area))
        for h in groups[area]:
            marks = _recent_marks(h["id"], log, recent)
            streak = _streak(h["id"], log, today.isoformat())
            adh = _adherence(h["id"], log, last30)
            adh_s = f"{adh}%" if adh is not None else "—"
            flame = f"🔥{streak}" if streak else "  ·"
            print(f"  {marks}  {flame:>5}  {adh_s:>4} 30d  {h['label']}")
        print()


def cmd_status(args):
    _print_status(load_cfg(), load_log(), days=args.days)


def cmd_week(args):
    habits = load_cfg()
    log = load_log()
    end = dt.date.fromisoformat(args.date)
    dates = [(end - dt.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    hdr = "  ".join(d[5:] for d in dates)
    print(f"Week ending {args.date}\n            {hdr}")
    groups = by_area(habits)
    for area in AREA_ORDER:
        if area not in groups:
            continue
        print(AREA_LABEL.get(area, area))
        for h in groups[area]:
            row = "  ".join(
                (" ✓ " if log.get(d, {}).get(h["id"]) else
                 (" ✗ " if d in log else " · ")) for d in dates)
            print(f"  {row}  {h['label']}")
        print()


def main():
    ap = argparse.ArgumentParser(description="Daily habit tracker with streaks")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    lg = sub.add_parser("log")
    lg.add_argument("--done", default="", help="comma-separated habit ids done today")
    lg.add_argument("--date", default=dt.date.today().isoformat())
    lg.set_defaults(func=cmd_log)

    st = sub.add_parser("status")
    st.add_argument("--days", type=int, default=7)
    st.set_defaults(func=cmd_status)

    wk = sub.add_parser("week")
    wk.add_argument("--date", default=dt.date.today().isoformat())
    wk.set_defaults(func=cmd_week)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
