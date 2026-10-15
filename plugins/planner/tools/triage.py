#!/usr/bin/env python3
"""Capture & triage helper.

Two phases (classification itself is done by Claude between them):

  parse  — pull the raw items out of inbox.md so Claude can classify them.
  apply  — take Claude's classification decisions and write the sorted outputs
           (Today/Soon/Eventually + priority matrix), a plan-day task list, a
           readable summary, then archive the `- ` items and clear them from the
           inbox (lines that aren't `- ` items are kept).

Deterministic file mechanics live here; the judgment (bucket / quadrant /
estimate) is supplied in decisions.json.

Usage:
  python3 tools/triage.py parse  [--inbox inbox.md]
  python3 tools/triage.py apply  --decisions decisions.json [--inbox inbox.md] [--date YYYY-MM-DD]

decisions.json — a list, one object per item:
  {"item": "...", "bucket": "today|soon|eventually",
   "quadrant": "do|schedule|delegate|delete", "minutes": 25, "note": ""}
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

BUCKETS = ["today", "soon", "eventually"]
QUAD_LABEL = {"do": "Do first (important & urgent)",
              "schedule": "Schedule (important, not urgent)",
              "delegate": "Delegate (urgent, not important)",
              "delete": "Drop (not important, not urgent)"}
QUAD_TAG = {"do": "DO", "schedule": "SCHED", "delegate": "DELEG", "delete": "DROP"}


# What apply writes as the fresh inbox. Its lines, and the seed inbox.md's
# shorter second line, are never archived or kept as unparsed text.
INBOX_TEMPLATE = ("# Capture inbox\n\n"
                  "Jot anything here through the day — one thought per line, "
                  "starting with `- `.\nBig or small, tasks or ideas. At the end of the workday the "
                  "triage skill sorts and clears this.\n\n- \n")
BOILERPLATE = set(INBOX_TEMPLATE.splitlines()) | {"Big or small, tasks or ideas."}
BULLET = re.compile(r"\s*-\s+(.*\S)\s*$")


def split_inbox(path):
    """(bullet lines, other lines), both verbatim. Blank lines, the empty `- `
    placeholder and the template's own lines are neither."""
    if not os.path.exists(path):
        return [], []
    bullets, unparsed = [], []
    with open(path, encoding="utf-8") as f:
        for line in f.read().splitlines():
            if not line.strip() or line.rstrip() in BOILERPLATE or re.fullmatch(r"\s*-\s*", line):
                continue
            (bullets if BULLET.match(line) else unparsed).append(line)
    return bullets, unparsed


def read_items(path):
    return [BULLET.match(line).group(1) for line in split_inbox(path)[0]]


def cmd_parse(args):
    items = read_items(args.inbox)
    unparsed = split_inbox(args.inbox)[1]
    print(json.dumps({"count": len(items), "items": items, "unparsed": unparsed},
                     indent=2, ensure_ascii=False))
    if not items:
        print("\n(inbox empty — nothing to triage)", file=sys.stderr)


def write_atomic(path, text):
    """Write a fresh temp file beside `path`, then rename it over: a crash mid-write
    can't truncate `path`, and a leftover or linked temp name is never reused."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".inbox-", suffix=".tmp")
    try:
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)  # mkstemp makes 0600; keep the inbox's mode
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_apply(args):
    with open(args.decisions, encoding="utf-8") as f:
        decisions = json.load(f)
    date = args.date
    os.makedirs(OUT, exist_ok=True)

    by_bucket = {b: [] for b in BUCKETS}
    for d in decisions:
        b = d.get("bucket", "eventually")
        if b not in by_bucket:
            b = "eventually"
        by_bucket[b].append(d)

    # --- summary markdown ---
    lines = [f"# Triage — {date}", ""]
    for b in BUCKETS:
        rows = by_bucket[b]
        lines.append(f"## {b.capitalize()}  ({len(rows)})")
        if not rows:
            lines.append("_nothing_")
        for d in rows:
            q = d.get("quadrant", "schedule")
            mins = d.get("minutes")
            tag = QUAD_TAG.get(q, "SCHED")
            extra = f" · ~{mins}m" if mins else ""
            note = f" — {d['note']}" if d.get("note") else ""
            lines.append(f"- [{tag}] {d['item']}{extra}{note}")
        lines.append("")
    # matrix view
    lines.append("## Priority matrix")
    for q in ["do", "schedule", "delegate", "delete"]:
        picks = [d["item"] for d in decisions if d.get("quadrant") == q]
        lines.append(f"**{QUAD_LABEL[q]}**")
        lines += ([f"- {p}" for p in picks] or ["- —"])
        lines.append("")
    summary = "\n".join(lines)

    # --- plan-day task list: Today items that are do/schedule ---
    tasks = [{"title": d["item"], "minutes": int(d.get("minutes") or 25)}
             for d in by_bucket["today"]
             if d.get("quadrant") in ("do", "schedule")]
    tasks_path = os.path.join(OUT, f"tasks-{date}.json")
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    # The summary goes last: morning-startup trusts tasks-<date>.json only when
    # triage-<date>.md is at least as new (a later merged pool is newer than both).
    summ_path = os.path.join(OUT, f"triage-{date}.md")
    with open(summ_path, "w", encoding="utf-8") as f:
        f.write(summary + "\n")

    # --- archive bullets verbatim; keep what isn't a bullet in the fresh inbox ---
    bullets, unparsed = split_inbox(args.inbox)
    archive = os.path.join(ROOT, "inbox-archive.md")
    if bullets:
        with open(archive, "a", encoding="utf-8") as f:
            f.write(f"\n## {date}\n")
            for line in bullets:
                f.write(line + "\n")
    write_atomic(args.inbox, INBOX_TEMPLATE + "".join(line + "\n" for line in unparsed))

    print(summary)
    print("\n---")
    print(f"Summary  → {summ_path}")
    print(f"Tasks    → {tasks_path}  ({len(tasks)} for plan-day)")
    cleared = "inbox cleared" if not unparsed else "items cleared from inbox"
    print(f"Archived → {len(bullets)} item(s) to inbox-archive.md; {cleared}")
    if unparsed:
        print(f"Kept {len(unparsed)} line(s) in inbox.md that don't start with `- `; "
              "make them `- ` items to triage them next time:")
        for line in unparsed:
            print("  " + line)


def cmd_carry(args):
    """Append unfinished items back into the inbox for re-triage tomorrow.
    Accepts a JSON list of strings or of objects with a 'title' key."""
    with open(args.items, encoding="utf-8") as f:
        data = json.load(f)
    titles = []
    for it in data:
        if isinstance(it, dict):
            t = it.get("title")
        else:
            t = str(it)
        if t:
            titles.append(t)
    if not titles:
        print("nothing to carry")
        return
    with open(args.inbox, "a", encoding="utf-8") as f:
        for t in titles:
            f.write(f"- {t}\n")
    print(f"Carried {len(titles)} item(s) into {args.inbox}:")
    for t in titles:
        print("  - " + t)


def main():
    ap = argparse.ArgumentParser(description="Capture & triage helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_inbox = os.path.join(ROOT, "inbox.md")

    p = sub.add_parser("parse")
    p.add_argument("--inbox", default=default_inbox)
    p.set_defaults(func=cmd_parse)

    cr = sub.add_parser("carry")
    cr.add_argument("--items", required=True, help="JSON list of leftover tasks")
    cr.add_argument("--inbox", default=default_inbox)
    cr.set_defaults(func=cmd_carry)

    a = sub.add_parser("apply")
    a.add_argument("--decisions", required=True)
    a.add_argument("--inbox", default=default_inbox)
    a.add_argument("--date", default=dt.date.today().isoformat())
    a.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
