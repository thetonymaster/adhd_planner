#!/usr/bin/env python3
"""Task queue: the ranked list of open task notes across one or more vaults.

Reads every Tasks/*.md whose status is not `done` in each vault given with
--vault (read-only; it writes nothing in a vault), applies the ordering rule
and writes a `task-queue/1` JSON file. The planning skills hand its `tasks`
rows to plan_week.py / plan_day.py. The last line printed is always
`Wrote <path>`.

Usage:
  python3 tools/task_queue.py --vault <name>=<path> [--vault ...]
      [--week-start YYYY-MM-DD | --date YYYY-MM-DD] [--include-weekend] [--out FILE]

--date D plans one day (until = D + 6 days). --week-start, or neither flag,
plans a week with planner_config.plan_days (until = the last planned day).
Without --out the file is a new tools/out/queue-run-<random>.json; old
queue-run-*.json files (more than a day old) are deleted on each run.
"""
import argparse
import datetime as dt
import glob
import json
import math
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from planner_config import plan_days  # noqa: E402

FORMAT = "task-queue/1"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
RUN_PREFIX, RUN_SUFFIX = "queue-run-", ".json"
MAX_AGE_S = 24 * 60 * 60
PRIORITIES = ("p0", "p1", "p2", "p3", "p4", "p5")
DEFAULT_PRIORITY = "p3"
FAR = "9999-12-31"

NEEDS_ESTIMATE, NO_NEXT, UNREADABLE = "needs an estimate", "no Next item", "unreadable note"
REASONS = (NEEDS_ESTIMATE, NO_NEXT, UNREADABLE)
PRIORITY_DETAIL = "expected p0..p5, read as p3"
DUE_DETAIL = "expected YYYY-MM-DD, read as no due date"

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_OPEN_ITEM = re.compile(r"^\s*- \[ \] (?=\S)(.*)$")
_ESTIMATE = re.compile(r"\s*\(~\s*(\d+(?:\.\d+)?)\s*(min|h)\)\s*$")
_COMMENT = re.compile(r"(^|\s)#.*$")
_KEY = re.compile(r"^([A-Za-z_][\w-]*):(.*)$")


def iso_date(text):
    """`text` as a YYYY-MM-DD string when it is a real date, else None."""
    if not _DATE.match(text):
        return None
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


# --- reading a note (pure: text in, values out) -------------------------------

def scalar(raw):
    """Text after `key:`: trailing ` # comment` removed, trimmed, one pair of matching quotes removed.
    A `#` inside the quotes is part of the value."""
    v = raw.strip()
    if v[:1] in ("\"", "'"):
        end = v.find(v[0], 1)
        rest = v[end + 1:] if end > 0 else ""
        if end > 0 and _COMMENT.sub("", rest).strip() == "":
            return v[1:end]
    v = _COMMENT.sub("", v).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def split_frontmatter(text):
    """(frontmatter lines, body lines), or None when the text has no frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return lines[1:i], lines[i + 1:]
    return None


def read_frontmatter(lines):
    """{key: scalar} for top-level keys, plus `aliases` as its first entry or None."""
    fields, aliases = {}, None
    for i, line in enumerate(lines):
        m = _KEY.match(line)
        if not m:
            continue
        key, raw = m[1], m[2]
        if key != "aliases":
            fields[key] = scalar(raw)
            continue
        value = scalar(raw)
        if value.startswith("["):
            first = value.strip("[]").split(",")[0]
            aliases = scalar(first) or None
        elif value:
            aliases = value
        else:
            for nxt in lines[i + 1:]:
                if _KEY.match(nxt):
                    break
                item = re.match(r"^\s*- (.*)$", nxt)
                if item:
                    aliases = scalar(item[1]) or None
                    break
    fields["aliases"] = aliases
    return fields


def hub_name(up):
    """Text of the first [[...]] link: no `|alias`, no folder prefix; '' without a link."""
    m = re.search(r"\[\[(.*?)\]\]", up)
    if not m:
        return ""
    return m[1].split("|")[0].rsplit("/", 1)[-1].strip()


def next_items(body):
    """Open Next items under `## Next` as (text, minutes or None)."""
    items, inside = [], False
    for line in body:
        if line.startswith("## "):
            if inside:
                break
            inside = line.rstrip() == "## Next"
            continue
        if not inside:
            continue
        m = _OPEN_ITEM.match(line)
        if not m:
            continue
        text = m[1].rstrip()
        est = _ESTIMATE.search(text)
        minutes = None
        if est and float(est[1]) > 0:
            n = float(est[1]) * (60 if est[2] == "h" else 1)
            minutes = math.ceil(round(n, 6))
            text = text[:est.start()].rstrip()
        elif est:
            text = text[:est.start()].rstrip()
        items.append((text, minutes))
    return items


def read_note(data, vault, slug):
    """One task note from its bytes. Returns a dict with `kind` set to
    "done", "unreadable" or "open"."""
    base = {"vault": vault, "slug": slug, "key": f"{vault}:{slug}"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {**base, "kind": "unreadable", "detail": "not UTF-8"}
    parts = split_frontmatter(text)
    if parts is None:
        return {**base, "kind": "unreadable", "detail": "no frontmatter"}
    front, body = parts
    f = read_frontmatter(front)
    status = f.get("status", "")
    if status == "done":
        return {**base, "kind": "done"}
    warnings = []
    priority = f.get("priority", "")
    if priority and priority not in PRIORITIES:
        warnings.append({"field": "priority", "value": priority, "detail": PRIORITY_DETAIL})
    if priority not in PRIORITIES:
        priority = DEFAULT_PRIORITY
    due_raw = f.get("due", "")
    due = iso_date(due_raw) if due_raw else None
    if due_raw and due is None:
        warnings.append({"field": "due", "value": due_raw, "detail": DUE_DETAIL})
    heading = next((l[2:].strip() for l in body if l.startswith("# ")), "")
    return {**base, "kind": "open", "status": status, "priority": priority, "due": due,
            "started": iso_date(f.get("started", "")),
            "name": f["aliases"] or heading or slug,
            "hub": hub_name(f.get("up", "")),
            "items": next_items(body), "warnings": warnings}


# --- the ordering rule (the only coded copy) ----------------------------------

def sort_key(task, until):
    """Rank of an open task. `task` needs priority, due, started, key; `until` is
    the last day of the planning window (ISO)."""
    due = task["due"]
    if task["priority"] == "p0":
        tier = 0
    elif due is not None and due <= until:
        tier = 1
    else:
        tier = 2
    return (tier,
            due if tier < 2 and due is not None else FAR,
            PRIORITIES.index(task["priority"]),
            task["started"] or FAR,
            task["key"])


# --- building the output (pure) ------------------------------------------------

def build(notes, first_day, until, single_vault):
    """notes: read_note results. Returns the task-queue/1 document."""
    def label(n):
        return n["slug"] if single_vault else n["key"]

    open_notes = [n for n in notes if n["kind"] == "open"]
    tasks, not_placed, warnings = [], [], []
    for n in sorted(open_notes, key=lambda n: sort_key(n, until)):
        for w in n["warnings"]:
            warnings.append({"task": label(n), **w})
        items = n["items"]
        missing = sum(1 for _, m in items if m is None)
        if not items:
            not_placed.append({"task": label(n), "name": n["name"], "reason": NO_NEXT,
                               "detail": "no open Next item under ## Next"})
            continue
        if missing:
            not_placed.append({"task": label(n), "name": n["name"], "reason": NEEDS_ESTIMATE,
                               "detail": f"{missing} of {len(items)} open Next items have no estimate"})
            continue
        row = {"title": f"{label(n)}: {items[0][0]}", "task": label(n), "name": n["name"],
               "source": "vault", "hub": n["hub"], "status": n["status"],
               "priority": n["priority"]}
        if n["due"]:
            row["deadline"] = n["due"]
        row["minutes"] = sum(m for _, m in items)
        if n["due"] and n["due"] < first_day:
            row["overdue"] = True
        tasks.append(row)
    for n in notes:
        if n["kind"] == "unreadable":
            not_placed.append({"task": label(n), "name": n["slug"], "reason": UNREADABLE,
                               "detail": n["detail"]})
    not_placed.sort(key=lambda r: r["task"])
    warnings.sort(key=lambda r: (r["task"], r["field"]))
    return {"format": FORMAT, "first_day": first_day, "until": until,
            "tasks": tasks, "not_placed": not_placed, "warnings": warnings}


def summary(doc):
    """The text summary printed before `Wrote <path>`."""
    blocks = []
    if doc["tasks"]:
        blocks.append([f"{r['priority']} {r.get('deadline', '-')}"
                       f"{' (overdue)' if r.get('overdue') else ''} {r['minutes']}m {r['title']}"
                       for r in doc["tasks"]])
    for reason in REASONS:
        rows = [r for r in doc["not_placed"] if r["reason"] == reason]
        if rows:
            blocks.append([f"Not placed ({reason}):"] + [f"- {r['task']}: {r['detail']}" for r in rows])
    if doc["warnings"]:
        blocks.append(["Warnings:"] + [f"- {w['task']}: {w['field']} \"{w['value']}\": {w['detail']}"
                                       for w in doc["warnings"]])
    return "\n\n".join("\n".join(b) for b in blocks)


# --- IO edge -------------------------------------------------------------------

def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_vaults(values):
    vaults = {}
    for v in values:
        name, sep, path = v.partition("=")
        if not sep or not name or not path:
            fail(f"--vault expects <name>=<path>, got {v!r}")
        if name in vaults:
            fail(f"--vault name {name!r} given twice")
        if not os.path.isdir(path):
            fail(f"--vault {v!r}: {path!r} is not a folder")
        if not os.path.isdir(os.path.join(path, "Tasks")):
            fail(f"--vault {v!r}: {path!r} has no Tasks/ folder")
        vaults[name] = path
    return vaults


def parse_day(value, flag):
    day = iso_date(value)
    if day is None:
        fail(f"{flag} expects YYYY-MM-DD, got {value!r}")
    return dt.date.fromisoformat(day)


def window(args, today):
    """(first_day, until) as ISO strings."""
    if args.date:
        d = parse_day(args.date, "--date")
        return d.isoformat(), (d + dt.timedelta(days=6)).isoformat()
    start = parse_day(args.week_start, "--week-start") if args.week_start else None
    _, days = plan_days(today, start, args.include_weekend)
    return days[0], days[-1]


def read_vault(name, path):
    tasks_dir = os.path.join(path, "Tasks")
    notes = []
    for f in sorted(os.listdir(tasks_dir)):
        full = os.path.join(tasks_dir, f)
        if f.endswith(".md") and os.path.isfile(full):
            with open(full, "rb") as fh:
                notes.append(read_note(fh.read(), name, f[:-3]))
    return notes


def clean_old_runs(out_dir, now):
    for p in glob.glob(os.path.join(out_dir, f"{RUN_PREFIX}*{RUN_SUFFIX}")):
        try:
            if now - os.path.getmtime(p) > MAX_AGE_S:
                os.remove(p)
        except FileNotFoundError:
            pass  # another run removed it first


def write_output(doc, out):
    payload = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(payload)
        return out
    fd, path = tempfile.mkstemp(prefix=RUN_PREFIX, suffix=RUN_SUFFIX, dir=OUT_DIR)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(payload)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ranked list of open task notes across vaults.")
    ap.add_argument("--vault", action="append", required=True, metavar="NAME=PATH",
                    help="a vault to read; repeat for several")
    when = ap.add_mutually_exclusive_group()
    when.add_argument("--week-start", help="plan this week, YYYY-MM-DD (default: this week from today on)")
    when.add_argument("--date", help="plan one day, YYYY-MM-DD")
    ap.add_argument("--include-weekend", action="store_true")
    ap.add_argument("--out", help="write here instead of a new tools/out/queue-run-*.json")
    args = ap.parse_args(argv)

    vaults = parse_vaults(args.vault)
    first_day, until = window(args, dt.date.today())
    notes = [n for name, path in vaults.items() for n in read_vault(name, path)]
    doc = build(notes, first_day, until, single_vault=len(vaults) == 1)

    os.makedirs(OUT_DIR, exist_ok=True)
    clean_old_runs(OUT_DIR, time.time())
    path = write_output(doc, args.out)
    text = summary(doc)
    if text:
        print(text)
        print()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
