"""Create week and month notes (period notes) in vaults that opted in with Recurring.md.

    period_note.py ensure --vault NAME=PATH [--vault ...] \\
        (--date YYYY-MM-DD | --plan-week [--week-start YYYY-MM-DD])

For each vault with a Recurrence list (`<vault>/Recurring.md`): every month note the
week touches (`Monthly/<YYYY-MM>.md`), then the week note (`Weekly/<GGGG-Www>.md`),
each filled with that period's occurrences. An existing note is merged: new
occurrences go inside its Recurring section, and the `added:` ledger keeps deleted ones
out; your ticks, notes and deletions are never undone. A vault without Recurring.md is
never written. Spec: docs/designs/week-month-notes.md, §3-§5.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import planner_config  # noqa: E402

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


def unfenced(lines):
    """(index, line) for every line outside fenced code; fence lines are left out."""
    fenced = False
    for i, line in enumerate(lines):
        if is_fence(line):
            fenced = not fenced
        elif not fenced:
            yield i, line


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
    found, warnings = [], []
    for i, line in unfenced(text.splitlines()):
        n = i + 1
        if "every:" not in line:
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

AddedKey = collections.namedtuple("AddedKey", "ids start end")
MarkerCount = collections.namedtuple("MarkerCount", "start end start_idx end_idx")

_LINE_SPLIT = re.compile(r".*?(?:\r\n|\n|\r)|.+", re.S)
_BLOCK_ITEM = re.compile(r"^\s*-\s+(.*)$")
MISSING_ADDED = "added: missing; rebuilt from the body, so earlier deletions may come back"


def split_lines(text):
    """Text → lines, each keeping its own ending (\\r\\n, \\n or \\r; the last may have none)."""
    return _LINE_SPLIT.findall(text)


def content(line):
    return line.rstrip("\r\n")


def ending(lines):
    """The ending an inserted or rewritten line takes: the first line's, else \\n."""
    first = lines[0] if lines else ""
    return first[len(content(first)):] or "\n"


def frontmatter_end(lines):
    """Index of the closing `---` when line 0 is `---`, else None (no frontmatter)."""
    if not lines or content(lines[0]) != "---":
        return None
    for i in range(1, len(lines)):
        if content(lines[i]) == "---":
            return i
    return None


def read_added(lines, close):
    """The `added:` key between line 0 (`---`) and `lines[close]` (the closing `---`) →
    AddedKey(ids, start, end), indexes into `lines` with `end` exclusive, or None when the
    key is missing. Reads a flow list (on one line or several), a block list, an empty
    value, `[]`, a scalar and quoted IDs; values follow `planner_config.scalar`."""
    for i in range(1, close):
        text = content(lines[i])
        if not text.startswith("added:"):
            continue
        value = planner_config.scalar(text[len("added:"):])
        end = i + 1
        if value.startswith("["):
            while not value.endswith("]") and end < close:
                value += " " + planner_config.scalar(content(lines[end]))
                end += 1
            ids = [planner_config.scalar(v) for v in value.strip("[]").split(",")]
            return AddedKey([v for v in ids if v], i, end)
        if value:
            return AddedKey([value], i, end)
        ids = []
        while end < close and (m := _BLOCK_ITEM.match(content(lines[end]))):
            if planner_config.scalar(m[1]):
                ids.append(planner_config.scalar(m[1]))
            end += 1
        return AddedKey(ids, i, end)
    return None


def write_added(lines, close, ids, key):
    """The note's lines → lines with `added:` as one flow-list line. `key` is read_added's
    result on the same lines; with None the line goes after `month:`, else after `period:`,
    else last in the frontmatter (`lines[close]` is the closing `---`)."""
    line = f"added: [{', '.join(ids)}]" + ending(lines)
    if key is not None:
        return lines[:key.start] + [line] + lines[key.end:]
    keys = [content(l).split(":", 1)[0] for l in lines[1:close]]
    for name in ("month", "period"):
        if name in keys:
            at = keys.index(name) + 2
            return lines[:at] + [line] + lines[at:]
    return lines[:close] + [line] + lines[close:]


def count_markers(body_lines, name):
    """The `planner:<name>` start/end markers on their own lines, outside fenced code."""
    start_m, end_m = f"<!-- planner:{name}:start -->", f"<!-- planner:{name}:end -->"
    starts, ends = [], []
    for i, line in unfenced(body_lines):
        if content(line).strip() == start_m:
            starts.append(i)
        elif content(line).strip() == end_m:
            ends.append(i)
    return MarkerCount(len(starts), len(ends), starts[0] if starts else None, ends[0] if ends else None)


def block_ids(body_lines):
    """Every `^ID` that is the last token of a line outside fenced code."""
    found = set()
    for _, line in unfenced(body_lines):
        tokens = line.split()
        if tokens and tokens[-1].startswith("^"):
            found.add(tokens[-1][1:])
    return found


def apply_occurrences(body_lines, ledger, occs, nl):
    """The §4 ledger table. → (new body lines, new ledger). `ledger` is the ID list read
    from `added:`; an occurrence in it is never re-added, even when its line is gone."""
    present = block_ids(body_lines)
    ledger, new = list(ledger), []
    for occ in occs:
        if occ.id in ledger:
            continue
        ledger.append(occ.id)
        if occ.id not in present:
            new.append(occurrence_line(occ) + nl)
    at = count_markers(body_lines, "recurring").end_idx
    return body_lines[:at] + new + body_lines[at:], ledger


def update_note(text, kind, occs):
    """One existing note → (new text, or None when Skipped; [(event, reason), …]) where
    event is `Warning` or `Skipped`, printed as `<event> <vault>:<path>: <reason>`."""
    lines = split_lines(text)
    close = frontmatter_end(lines)
    if close is None:
        return None, [("Skipped", "no frontmatter (note not created by the planner)")]
    body, events = lines[close + 1:], []
    if kind == "week":
        plan = count_markers(body, "plan-week")
        if (plan.start, plan.end) != (1, 1):
            events.append(("Warning", "expected one plan-week start/end marker pair, "
                                      f"found start={plan.start} end={plan.end}"))
    recurring = count_markers(body, "recurring")
    if (recurring.start, recurring.end) != (1, 1):
        return None, events + [("Skipped", "expected one recurring start/end marker pair, "
                                           f"found start={recurring.start} end={recurring.end}")]
    if recurring.end_idx < recurring.start_idx:
        return None, events + [("Skipped", "recurring end marker comes before start marker")]

    key = read_added(lines, close)
    if key is None:
        events.append(("Warning", MISSING_ADDED))
    old = key.ids if key else []
    new_body, ledger = apply_occurrences(body, old, occs, ending(lines))
    if key is not None and ledger == old:
        return "".join(lines[:close + 1] + new_body), events
    return "".join(write_added(lines[:close + 1], close, ledger, key) + new_body), events


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
            new, events = update_note(read_text(path), kind, occs)
            printed = [f"{event} {name}:{rel}: {reason}" for event, reason in events]
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
        recurring_path = os.path.join(root, "Recurring.md")
        if not os.path.exists(recurring_path):
            print(f"Off {name}: no Recurring.md", file=out)
            continue
        try:
            rules, warnings = parse_recurring(read_text(recurring_path))
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
            lines, note_skipped = ensure_note(name, root, f"Monthly/{m}.md", "month", occs,
                                              lambda m=m, occs=occs: new_month_note(m, occs))
            print(*lines, sep="\n", file=out)
            skipped |= note_skipped

        rel = f"Weekly/{week}.md"
        missing = [m for m in months if not os.path.isfile(os.path.join(root, "Monthly", f"{m}.md"))]
        if missing and not os.path.exists(os.path.join(root, "Weekly", f"{week}.md")):
            print(f"Skipped {name}:{rel}: month note Monthly/{missing[0]}.md missing", file=out)
            skipped = True
            continue
        occs = occurrences(rules, "week", week)
        lines, note_skipped = ensure_note(name, root, rel, "week", occs, lambda: new_week_note(monday, occs))
        print(*lines, sep="\n", file=out)
        skipped |= note_skipped
    return 1 if skipped else 0


def main(argv=None, today=None):
    parser = argparse.ArgumentParser(prog="period_note.py", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    ensure_cmd = sub.add_parser("ensure", help="find or create the week's period notes")
    ensure_cmd.add_argument("--vault", action="append", default=[], metavar="NAME=PATH")
    ensure_cmd.add_argument("--date", metavar="YYYY-MM-DD", help="use the week that contains this date")
    ensure_cmd.add_argument("--plan-week", action="store_true",
                            help="use the week plan_week.py plans today (next week on a weekend)")
    ensure_cmd.add_argument("--week-start", metavar="YYYY-MM-DD", help="with --plan-week: this Monday's week")
    args = parser.parse_args(argv)

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
