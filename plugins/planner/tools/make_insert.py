#!/usr/bin/env python3
"""Generate A5 print-ready PDF inserts of the ADHD
planner pages. Blank/fillable, clean-neutral styling, dot-grid feel.

Usage:
    python3 tools/make_insert.py priority-matrix
    python3 tools/make_insert.py all                # one combined PDF
    python3 tools/make_insert.py sleep --size a6
    python3 tools/make_insert.py --list

Output goes to tools/out/ by default.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from planner_common import Sheet, new_canvas, A5, A6  # noqa: E402


def brain_dump(s):
    s.header("Brain Dump", "sort",
             "List everything here — big or small. Get it out of your head.")
    s.box("", height_mm=150, dots=True)


def things_to_do(s):
    s.header("Things To Do", "sort",
             "Decide what to do today, soon, or eventually.")
    s.box("Things I have to do TODAY", height_mm=40)
    s.box("Things I should do SOON", height_mm=40)
    s.box("Things I should do EVENTUALLY", height_mm=40)


def priority_matrix(s):
    s.header("Priority Matrix", "sort",
             "Sort tasks by importance and urgency.")
    s.quadrant([
        "Important & Urgent — Do first",
        "Important & Not Urgent — Schedule",
        "Not Important & Urgent — Delegate",
        "Not Important & Not Urgent — Delete",
    ])


def commitments(s):
    s.header("Commitments", "sort", "Choose 1–3 commitments to focus on.")
    s.cards(4, ["I will", "beginning", "To be successful I will need to",
                "This will help me"])


def goal_changes(s):
    s.header("Goal Changes", "sustain",
             "For each goal, choose one improvement to make this week.")
    s.table(
        ["Goal", "Social", "Temporal", "Environ.", "Cognitive"],
        [["1", "", "", "", ""], ["2", "", "", "", ""], ["3", "", "", "", ""]],
        row_h_mm=22)


def friend_files(s):
    s.header("Friend Files", "sustain",
             "Keep track of the people in your life.")
    s.cards(2, ["Name", "Basic info", "Important dates",
                "Interests / hobbies", "Good times", "Hard times",
                "Other notes", "Questions to ask", "Safe to share"])


def circles_of_trust(s):
    s.header("Circles of Trust", "sustain",
             "Fill in 2–3 people who belong in each layer.")
    s.box("Gen Pop / NPC", height_mm=22, dots=False)
    s.box("Shared Time / Space", height_mm=22, dots=False)
    s.box("Good Friend", height_mm=22, dots=False)
    s.box("Inner Circle", height_mm=22, dots=False)
    s.box("Strike Zone", height_mm=22, dots=False)


def sleep_activities(s):
    s.header("Sleep Activities", "sustain",
             "Plan for rest. Work backwards from wake-up to bedtime.")
    s.section("Sleep schedule")
    s.table(["Time of Day", "Time", "Notes"],
            [["End of day", "", ""], ["Bedtime routine", "", ""],
             ["Fall asleep", "", ""], ["Wake up", "", ""], ["Get up", "", ""]],
            row_h_mm=11)
    s.section("Bedroom management")
    s.checklist(["Dark curtains", "Comfortable bedding", "TV off", "No visible clock",
                 "Devices on DND", "White noise", "Sleep mask", "Lights off"],
                two_col=True)
    s.section("Bedtime routine")
    s.checklist(["Brush teeth", "Wash face", "Skincare", "Reading",
                 "Meditation", "Vitamins / meds", "Lock doors", "Charge devices",
                 "Set out clothes", "Pack bag", "Make lunch", "Find keys / wallet"],
                two_col=True)


def eating_strategies(s):
    s.header("Eating Habits — Strategies", "sustain",
             "Shape your environment. Check a few solutions to try.")
    s.section("Limit junk food")
    s.checklist(["Don't buy at the store", "Coffee stops without junk food",
                 "Back of the pantry", "Only as a reward", "Share with others"])
    s.section("Keep ideal food accessible")
    s.checklist(["\"Essentials\" grocery list", "Snacks in your bag",
                 "Snacks in your car", "Snacks in your desk",
                 "Bring ideal food to gatherings"])
    s.section("No screens during meals")
    s.checklist(["Screens + notifications off", "Devices out of the room",
                 "Sit where you can't see screens"])


def eating_schedule(s):
    s.header("Eating Habits — Schedule", "sustain",
             "Create habits to fuel your body so your brain shows up.")
    s.section("Meal schedule")
    s.table(["Food", "When", "Favorite options"],
            [["Morning fuel", "", ""], ["Mid-day fuel", "", ""],
             ["Evening fuel", "", ""]], row_h_mm=13)
    s.section("Emotional vulnerabilities")
    s.table(["I eat impulsively when I feel", "Instead I will"],
            [["Bored", ""], ["Stressed", ""], ["Sad", ""], ["Lonely", ""]],
            row_h_mm=13)


def weekly_schedule(s):
    s.header("Weekly Schedule", "schedule", "Plan your week hour by hour.")
    s.label_lines("Week of", n=1)
    days = ["Time", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    rows = [[f"{h}:00"] + [""] * 7 for h in range(6, 21)]
    s.table(days, rows, row_h_mm=8.5)


def monthly_calendar(s):
    s.header("Monthly Calendar", "schedule",
             "Map out your month, priorities, and notes.")
    s.label_lines("Month / Year", n=1)
    head = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    rows = [[""] * 7 for _ in range(6)]
    s.table(head, rows, row_h_mm=20, label_col=False)
    s.section("Top priorities")
    s.label_lines("1", n=1)
    s.label_lines("2", n=1)
    s.label_lines("3", n=1)


PAGES = {
    "brain-dump": brain_dump,
    "things-to-do": things_to_do,
    "priority-matrix": priority_matrix,
    "commitments": commitments,
    "goal-changes": goal_changes,
    "friend-files": friend_files,
    "circles-of-trust": circles_of_trust,
    "sleep-activities": sleep_activities,
    "eating-strategies": eating_strategies,
    "eating-schedule": eating_schedule,
    "weekly-schedule": weekly_schedule,
    "monthly-calendar": monthly_calendar,
}


def main():
    ap = argparse.ArgumentParser(description="A5 planner insert generator")
    ap.add_argument("page", nargs="?", help="page id, or 'all'")
    ap.add_argument("--size", choices=["a5", "a6"], default="a5")
    ap.add_argument("--out", default=None)
    ap.add_argument("--list", action="store_true", help="list page ids")
    args = ap.parse_args()

    if args.list or not args.page:
        print("Available pages:")
        for k in PAGES:
            print("  " + k)
        print("  all   (every page, combined)")
        return

    size = A5 if args.size == "a5" else A6
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)

    if args.page == "all":
        path = args.out or os.path.join(out_dir, f"planner-inserts-{args.size}.pdf")
        c = new_canvas(path, size)
        for fn in PAGES.values():
            fn(Sheet(c, size))
            c.showPage()
        c.save()
        print("Wrote " + path)
        return

    if args.page not in PAGES:
        print(f"Unknown page '{args.page}'. Use --list.", file=sys.stderr)
        sys.exit(1)

    path = args.out or os.path.join(out_dir, f"insert-{args.page}-{args.size}.pdf")
    c = new_canvas(path, size)
    PAGES[args.page](Sheet(c, size))
    c.showPage()
    c.save()
    print("Wrote " + path)


if __name__ == "__main__":
    main()
