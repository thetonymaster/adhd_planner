"""Create week and month notes (period notes) in vaults that opted in with Recurring.md.

    period_note.py ensure --vault NAME=PATH [--vault ...] \\
        (--date YYYY-MM-DD | --plan-week [--week-start YYYY-MM-DD])

For each vault with a Recurrence list (`<vault>/Recurring.md`): every month note the
week touches (`Monthly/<YYYY-MM>.md`), then the week note (`Weekly/<GGGG-Www>.md`),
each filled with that period's occurrences. A vault without Recurring.md is never
written. Spec: docs/designs/week-month-notes.md, §3-§5.

Output (stdout, one line per event): `Week <label> (Monday <date>)` first, then
`Wrote`, `Unchanged`, `Off`, `Skipped` and `Warning` lines. Exit 0, 1 when a note
was Skipped (the rest is still processed), 2 on bad arguments.
"""
import argparse
import calendar
import collections
import datetime as dt
import os
import re
import sys

import planner_config

Rule = collections.namedtuple("Rule", "id text kind spec")
Occurrence = collections.namedtuple("Occurrence", "id text date")

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
MONTH_ABBR = [m[:3] for m in MONTH_NAMES]

_LINE = re.compile(r"^- \[[ xX]\] (?P<text>.+?) — every: (?P<rule>.+?) #id/(?P<id>[a-z0-9][a-z0-9-]*)\s*$")
_LINE_NO_ID = re.compile(r"^- \[[ xX]\] .+? — every: .+$")
_MONTH_N = re.compile(r"^month (\d+)$")
_MONTH_FIRST = re.compile(r"^month first-(mon|tue|wed|thu|fri|sat|sun)$")


def is_fence(line):
    """A fenced code block opens and closes with a line starting at column 0 with ``` or ~~~."""
    return line.startswith("```") or line.startswith("~~~")


def parse_rule(rule):
    """A rule's text → (kind, spec), or a warning reason string."""
    if rule in WEEKDAYS:
        return "week", WEEKDAYS.index(rule)
    if rule == "month last":
        return "month", ("last",)
    m = _MONTH_FIRST.match(rule)
    if m:
        return "month", ("first", WEEKDAYS.index(m[1]))
    m = _MONTH_N.match(rule)
    if m:
        n = int(m[1])
        if not 1 <= n <= 31:
            return f"month {m[1]} out of range 1–31"
        return "month", ("day", n)
    return f"unknown rule '{rule}'"


def parse_recurring(text):
    """Recurring.md text → (rules in file order, warnings). Each warning is the text
    after `<vault>:` on its `Warning` line, e.g. `Recurring.md:3: missing #id/`."""
    found, warnings, fenced = [], [], False
    for n, line in enumerate(text.splitlines(), 1):
        if is_fence(line):
            fenced = not fenced
            continue
        if fenced or "every:" not in line:
            continue
        m = _LINE.match(line)
        if not m:
            reason = "missing #id/" if "#id/" not in line and _LINE_NO_ID.match(line) \
                else "does not match the line format"
            warnings.append(f"Recurring.md:{n}: {reason}")
            continue
        parsed = parse_rule(m["rule"])
        if isinstance(parsed, str):
            warnings.append(f"Recurring.md:{n}: {parsed}")
            continue
        found.append((n, Rule(m["id"], m["text"], *parsed)))
    lines_by_id = collections.defaultdict(list)
    for n, rule in found:
        lines_by_id[rule.id].append(n)
    for rid, ns in lines_by_id.items():
        if len(ns) > 1:
            warnings.append(f"Recurring.md: id '{rid}' on lines {', '.join(map(str, ns))}; all skipped")
    return [r for _, r in found if len(lines_by_id[r.id]) == 1], warnings


def week_monday(label):
    """"2026-W48" → the Monday of that ISO week."""
    year, week = label.split("-W")
    return dt.date.fromisocalendar(int(year), int(week), 1)


def month_date(year, month, spec):
    last = calendar.monthrange(year, month)[1]
    if spec[0] == "last":
        return dt.date(year, month, last)
    if spec[0] == "day":
        return dt.date(year, month, min(spec[1], last))
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(spec[1] - first.weekday()) % 7)


def occurrences(rules, kind, period):
    """The occurrences `period` should have: weekly rules for a week label ("2026-W48"),
    monthly rules for a month label ("2026-11"). Rule order is kept."""
    if kind == "week":
        monday = week_monday(period)
        date_of = lambda spec: monday + dt.timedelta(days=spec)  # noqa: E731
    else:
        year, month = map(int, period.split("-"))
        date_of = lambda spec: month_date(year, month, spec)  # noqa: E731
    return [Occurrence(f"{r.id}-{period.lower()}", r.text, date_of(r.spec))
            for r in rules if r.kind == kind]


# --- new notes (§3) -----------------------------------------------------------

PLAN_START, PLAN_END = "<!-- planner:plan-week:start -->", "<!-- planner:plan-week:end -->"
REC_START, REC_END = "<!-- planner:recurring:start -->", "<!-- planner:recurring:end -->"


def _day(d, with_year):
    text = f"{MONTH_ABBR[d.month - 1]} {d.day}"
    return f"{text}, {d.year}" if with_year else text


def title_week(monday):
    """`Week 48 · Nov 23 – Nov 29, 2026`; the year goes on both ends only when the
    week spans two years. Fixed English names, never locale-dependent strftime."""
    sunday = monday + dt.timedelta(days=6)
    week = monday.isocalendar()[1]
    two_years = monday.year != sunday.year
    return f"Week {week} · {_day(monday, two_years)} – {_day(sunday, True)}"


def title_month(label):
    year, month = map(int, label.split("-"))
    return f"{MONTH_NAMES[month - 1]} {year}"


def occurrence_line(occ):
    return f"- [ ] {occ.text} — {occ.date.isoformat()} ^{occ.id}"


def _ledger(occs):
    return f"added: [{', '.join(o.id for o in occs)}]"


def _recurring_section(occs):
    return ["## Recurring", REC_START, *map(occurrence_line, occs), REC_END, "", "## Notes"]


def new_week_note(monday, occs):
    lines = ["---", f"period: {planner_config.iso_week(monday)}",
             f'month: "[[{planner_config.week_month(monday)}]]"', _ledger(occs), "tags: [weekly]", "---",
             f"# {title_week(monday)}", "",
             "Months: " + " · ".join(f"[[{m}]]" for m in planner_config.months_touched(monday)), "",
             "## Plan", PLAN_START, PLAN_END, "", *_recurring_section(occs)]
    return "\n".join(lines) + "\n"


def new_month_note(label, occs):
    lines = ["---", f"period: {label}", _ledger(occs), "tags: [monthly]", "---",
             f"# {title_month(label)}", "", *_recurring_section(occs)]
    return "\n".join(lines) + "\n"


# --- existing notes -------------------------------------------------------------

def update_note(text, kind, occs):
    """One existing note → (new text, or None when Skipped; lines to print).

    Creating notes only, for now: an existing note is returned as it is, so it is
    reported `Unchanged` and never rewritten. The §4 merge (markers, ledger, line
    endings; read_added / write_added / count_markers / apply_occurrences) slots in
    here without changing ensure()."""
    return text, []


# --- the vault side (IO) -----------------------------------------------------------

def read_text(path):
    """UTF-8 text with every line ending kept; UnicodeDecodeError / OSError propagate."""
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def write_if_changed(path, text):
    """`Wrote` or `Unchanged`. An unchanged file is not written, so its mtime stays."""
    if os.path.exists(path) and read_text(path) == text:
        return "Unchanged"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    planner_config.write_atomic(path, text, prefix=".period-")
    return "Wrote"


def ensure_note(name, root, rel, kind, occs, make_new):
    """Find or create one period note. → (lines to print, skipped?)."""
    path = os.path.join(root, *rel.split("/"))
    try:
        if os.path.exists(path):
            new, printed = update_note(read_text(path), kind, occs)
            if new is None:
                return printed, True
        else:
            new, printed = make_new(), []
        return printed + [f"{write_if_changed(path, new)} {name}:{rel}"], False
    except UnicodeDecodeError:
        return [f"Skipped {name}:{rel}: not UTF-8"], True
    except OSError as e:
        return [f"Skipped {name}:{rel}: {e.strerror}"], True


def ensure(vaults, monday, out):
    """Find or create the week's period notes in every opted-in vault. → exit code."""
    week = planner_config.iso_week(monday)
    print(f"Week {week} (Monday {monday.isoformat()})", file=out)
    skipped = False

    for name, root in vaults.items():
        rec = os.path.join(root, "Recurring.md")
        if not os.path.exists(rec):
            print(f"Off {name}: no Recurring.md", file=out)
            continue
        try:
            rules, warnings = parse_recurring(read_text(rec))
        except UnicodeDecodeError:
            print(f"Skipped {name}:Recurring.md: not UTF-8", file=out)
            skipped = True
            continue
        except OSError as e:
            print(f"Skipped {name}:Recurring.md: {e.strerror}", file=out)
            skipped = True
            continue
        for w in warnings:
            print(f"Warning {name}:{w}", file=out)

        months = planner_config.months_touched(monday)
        for m in months:
            occs = occurrences(rules, "month", m)
            lines, s = ensure_note(name, root, f"Monthly/{m}.md", "month", occs,
                                   lambda m=m, occs=occs: new_month_note(m, occs))
            print(*lines, sep="\n", file=out)
            skipped |= s

        rel = f"Weekly/{week}.md"
        missing = [m for m in months if not os.path.isfile(os.path.join(root, "Monthly", f"{m}.md"))]
        if missing and not os.path.exists(os.path.join(root, "Weekly", f"{week}.md")):
            print(f"Skipped {name}:{rel}: month note Monthly/{missing[0]}.md missing", file=out)
            skipped = True
            continue
        occs = occurrences(rules, "week", week)
        lines, s = ensure_note(name, root, rel, "week", occs, lambda: new_week_note(monday, occs))
        print(*lines, sep="\n", file=out)
        skipped |= s
    return 1 if skipped else 0


def main(argv=None, today=None):
    p = argparse.ArgumentParser(prog="period_note.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    e = sub.add_parser("ensure", help="find or create the week's period notes")
    e.add_argument("--vault", action="append", default=[], metavar="NAME=PATH")
    e.add_argument("--date", metavar="YYYY-MM-DD", help="use the week that contains this date")
    e.add_argument("--plan-week", action="store_true",
                   help="use the week plan_week.py plans today (next week on a weekend)")
    e.add_argument("--week-start", metavar="YYYY-MM-DD", help="with --plan-week: this Monday's week")
    args = p.parse_args(argv)

    if not args.vault:
        planner_config.fail("ensure needs at least one --vault NAME=PATH")
    if (args.date is None) == (not args.plan_week):
        planner_config.fail("give exactly one of --date YYYY-MM-DD or --plan-week, got "
                            + ("both" if args.plan_week else "neither"))
    if args.week_start is not None and not args.plan_week:
        planner_config.fail(f"--week-start {args.week_start} needs --plan-week")
    vaults = planner_config.parse_vaults(args.vault)
    if args.plan_week:
        week_start = None
        if args.week_start is not None:
            week_start = planner_config.parse_day(args.week_start, "--week-start")
            if week_start.weekday() != 0:
                planner_config.fail(f"--week-start {args.week_start} is not a Monday")
        monday = planner_config.plan_days(today, week_start, include_weekend=False)[0]
    else:
        monday = planner_config.monday_of(planner_config.parse_day(args.date, "--date"))
    return ensure(vaults, monday, sys.stdout)


if __name__ == "__main__":
    sys.exit(main(today=dt.date.today()))
