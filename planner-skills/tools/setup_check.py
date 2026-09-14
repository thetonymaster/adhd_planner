#!/usr/bin/env python3
"""Setup doctor for the planner skills.

Checks requirements, configuration, and data files, and prints a checklist with
what's ready and what still needs attention. Run it at the start and end of the
setup skill. Read-only: it changes nothing.

Usage:
  python3 tools/setup_check.py
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = os.path.join(HERE, "calendars.json")
HABITS = os.path.join(ROOT, "habits.json")
INBOX = os.path.join(ROOT, "inbox.md")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
MARK = {PASS: "✓", WARN: "⚠", FAIL: "✗"}


def check():
    out = []  # (level, message, hint)

    # 1. Python version
    v = sys.version_info
    if v >= (3, 10):
        out.append((PASS, f"Python {v.major}.{v.minor}", ""))
    else:
        out.append((FAIL, f"Python {v.major}.{v.minor}", "need 3.10+"))

    # 2. reportlab (PDF generation)
    if importlib.util.find_spec("reportlab"):
        out.append((PASS, "reportlab installed", ""))
    else:
        out.append((FAIL, "reportlab missing", "pip install reportlab"))

    # 3. Scripts present
    needed = ["make_insert.py", "make_daily.py", "plan_day.py", "plan_week.py",
              "add_event.py", "triage.py", "habits.py"]
    missing = [f for f in needed if not os.path.exists(os.path.join(HERE, f))]
    # shared drawing module
    if not os.path.exists(os.path.join(HERE, "planner_common.py")):
        missing.append("planner_common.py")
    if missing:
        out.append((FAIL, "tool scripts missing: " + ", ".join(missing), ""))
    else:
        out.append((PASS, f"all {len(needed) + 1} tool scripts present", ""))

    # 4. calendars.json — timezone
    cfg = None
    if os.path.exists(CFG):
        try:
            cfg = json.load(open(CFG, encoding="utf-8"))
        except Exception as e:
            out.append((FAIL, "calendars.json invalid JSON", str(e)))
    else:
        out.append((FAIL, "calendars.json not found", ""))

    if cfg is not None:
        tz = cfg.get("timezone", "")
        if not tz or tz == "UTC":
            out.append((WARN, f"timezone = {tz or 'unset'}",
                        "set your IANA zone, e.g. America/New_York"))
        else:
            out.append((PASS, f"timezone = {tz}", ""))

        cals = cfg.get("calendars", {})
        with_id = [k for k, v in cals.items() if v.get("id")]
        without = [k for k, v in cals.items() if not v.get("id")]
        if with_id:
            msg = f"{len(with_id)} calendar id(s) set: {', '.join(with_id)}"
            hint = ("still empty: " + ", ".join(without)) if without else ""
            out.append((PASS, msg, hint))
        else:
            out.append((WARN, "no calendar ids set",
                        "calendar features limited until you fill ids "
                        "(ask: 'list my calendars and wire the ids')"))

    # 5. habits.json — commitments configured
    if os.path.exists(HABITS):
        try:
            habits = json.load(open(HABITS, encoding="utf-8")).get("habits", [])
            placeholder = [h for h in habits
                           if "edit me" in h.get("label", "").lower()
                           or h.get("label", "").startswith("<")]
            if placeholder:
                out.append((WARN, f"{len(placeholder)} habit placeholder(s) unset",
                            "set your real commitments in habits.json"))
            else:
                out.append((PASS, f"{len(habits)} habits configured", ""))
        except Exception as e:
            out.append((FAIL, "habits.json invalid JSON", str(e)))
    else:
        out.append((WARN, "habits.json not found", "habit-tracker won't work"))

    # 6. inbox.md
    if os.path.exists(INBOX):
        out.append((PASS, "inbox.md present", ""))
    else:
        out.append((WARN, "inbox.md not found", "capture-triage needs it"))

    return out


def main():
    rows = check()
    print("Planner skills — setup check\n")
    for level, msg, hint in rows:
        line = f"  {MARK[level]} {msg}"
        if hint:
            line += f"   → {hint}"
        print(line)

    fails = sum(1 for l, _, _ in rows if l == FAIL)
    warns = sum(1 for l, _, _ in rows if l == WARN)
    print()
    if fails:
        print(f"✗ {fails} blocker(s) and {warns} warning(s). Fix blockers first.")
        sys.exit(1)
    if warns:
        print(f"⚠ Ready to run, {warns} thing(s) worth finishing for full features.")
        sys.exit(0)
    print("✓ All set — everything is configured.")
    sys.exit(0)


if __name__ == "__main__":
    main()
