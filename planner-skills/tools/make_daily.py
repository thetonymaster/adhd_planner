#!/usr/bin/env python3
"""Render a A5-planner-style daily page (A5) from Google Calendar events.

Pipeline (paper-first):
  1. Claude fetches events via the calendar MCP and saves them as JSON.
  2. This script renders a print-ready daily page for a given date.

The JSON file is the raw output of the calendar `list_events` tool — either a
single object with an "events" array, or a list of such objects (one per
calendar). All-day events appear in a banner; timed events are placed on the
hourly timeline. Top 3 + notes areas are left blank to write by hand.

Usage:
  python3 tools/make_daily.py --date 2026-06-27 --events tools/events.json
  python3 tools/make_daily.py --date 2026-06-27 --events e.json --start 5 --end 24
"""
import argparse
import datetime as dt
import json
import os
import sys

from reportlab.lib.units import mm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from planner_common import (  # noqa: E402
    new_canvas, A5, INK, MUTED, LINE, ACCENT, ACCENT_SOFT, DOT)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def parse_iso(s):
    """Parse an ISO datetime that may carry a timezone offset (e.g. -05:00)."""
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        # tolerate trailing Z
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_events(path):
    with open(path) as f:
        data = json.load(f)
    blobs = data if isinstance(data, list) else [data]
    out = []
    for blob in blobs:
        cal = blob.get("summary", "") if isinstance(blob, dict) else ""
        for ev in (blob.get("events", []) if isinstance(blob, dict) else []):
            out.append((cal, ev))
    return out


def event_times(ev):
    """Return (start_dt_or_None, end_dt_or_None, date_str_or_None, all_day)."""
    start, end = ev.get("start", {}), ev.get("end", {})
    if "dateTime" in start:
        s = parse_iso(start["dateTime"])
        e = parse_iso(end["dateTime"]) if "dateTime" in end else None
        return s, e, s.date().isoformat(), False
    if "date" in start:  # all-day
        return None, None, start["date"], True
    return None, None, None, False


def fmt_hm(d):
    return d.strftime("%H:%M")


def render(date, events, tasks, start_h, end_h, out_path):
    c = new_canvas(out_path, A5)
    w, h = A5
    margin = 12 * mm
    weekday = WEEKDAYS[date.weekday()]

    # collect this date's events
    timed, allday = [], []
    for cal, ev in events:
        s, e, dstr, ad = event_times(ev)
        if dstr != date.isoformat():
            continue
        title = ev.get("summary", "(no title)")
        if ad:
            allday.append((title, cal))
        elif s is not None:
            timed.append((s, e, title, ev.get("location", ""),
                          bool(ev.get("conferenceUrl")), cal))
    timed.sort(key=lambda t: t[0])

    # --- header ---
    y = h - margin
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(margin, y - 24, date.strftime("%d"))
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin + 22 * mm, y - 12, weekday)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(margin + 22 * mm, y - 24, f"{MONTHS[date.month - 1]} {date.year}")
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.line(margin, y - 32, w - margin, y - 32)
    y -= 40

    # --- all-day banner ---
    if allday:
        c.setFillColor(ACCENT_SOFT)
        bh = 7 * mm
        c.roundRect(margin, y - bh, w - 2 * margin, bh, 3, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 8)
        txt = "  •  ".join(t for t, _ in allday)
        c.drawString(margin + 5, y - bh + 2.5 * mm, _truncate(c, "All day: " + txt,
                     "Helvetica-Bold", 8, w - 2 * margin - 10))
        y -= bh + 4 * mm

    # --- layout: meetings timeline (left) + tasks sidebar (right) ---
    gap = 6 * mm
    tl_w = (w - 2 * margin) * 0.50
    sb_x = margin + tl_w + gap
    sb_w = (w - 2 * margin) - tl_w - gap
    col_top = y
    grid_bottom = margin

    # column headings
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, col_top - 8, "Schedule")
    c.drawString(sb_x, col_top - 8, "Top 3 today")

    grid_top = col_top - 14
    n_hours = end_h - start_h
    row_h = (grid_top - grid_bottom) / n_hours

    # hour lines + labels
    c.setFont("Helvetica", 7)
    for i in range(n_hours + 1):
        yy = grid_top - i * row_h
        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        c.line(margin, yy, margin + tl_w, yy)
        if i < n_hours:
            c.setFillColor(MUTED)
            c.drawString(margin, yy - 8, f"{start_h + i}:00")

    def y_for(d):
        hh = d.hour + d.minute / 60.0
        hh = max(start_h, min(end_h, hh))
        return grid_top - (hh - start_h) * row_h

    # event blocks
    block_x = margin + 9 * mm
    block_w = tl_w - 9 * mm
    for s, e, title, loc, has_call, cal in timed:
        yt = y_for(s)
        yb = y_for(e) if e else yt - row_h * 0.75
        bh = max(yt - yb, 5 * mm)
        c.setFillColor(ACCENT_SOFT)
        c.roundRect(block_x, yt - bh, block_w, bh, 2, stroke=0, fill=1)
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.2)
        c.line(block_x + 0.6, yt - bh + 1, block_x + 0.6, yt - 1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 7.5)
        label = fmt_hm(s) + ("–" + fmt_hm(e) if e else "") + "  " + title
        c.drawString(block_x + 3, yt - 8, _truncate(c, label, "Helvetica-Bold", 7.5, block_w - 6))
        extra = []
        if has_call:
            extra.append("video call")
        if loc:
            extra.append(loc)
        if extra and bh > 9 * mm:
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 6.5)
            c.drawString(block_x + 3, yt - 16, _truncate(c, " · ".join(extra),
                         "Helvetica", 6.5, block_w - 6))

    # --- right column: Top 3 -> Tasks & subtasks -> Notes ---
    sy = grid_top  # heading already drawn at col_top
    # Top 3 checkbox lines
    for _ in range(3):
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.8)
        c.rect(sb_x, sy - 9, 8, 8, stroke=1, fill=0)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(sb_x + 12, sy - 9, sb_x + sb_w, sy - 9)
        sy -= 10 * mm

    # Tasks & subtasks
    if tasks:
        sy -= 3 * mm
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(sb_x, sy - 8, "Tasks")
        sy -= 15
        for task in tasks:
            if sy < grid_bottom + 30 * mm:
                break  # leave room for notes
            title = task.get("title", "") if isinstance(task, dict) else str(task)
            subs = task.get("subtasks", []) if isinstance(task, dict) else []
            # task line: checkbox + bold title
            c.setStrokeColor(ACCENT)
            c.setLineWidth(1.0)
            c.rect(sb_x, sy - 9, 9, 9, stroke=1, fill=0)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(sb_x + 13, sy - 7,
                         _truncate(c, title, "Helvetica-Bold", 8.5, sb_w - 15))
            sy -= 7 * mm
            # subtasks: small hollow box + text, indented
            for sub in subs:
                if sy < grid_bottom + 26 * mm:
                    break
                c.setStrokeColor(MUTED)
                c.setLineWidth(0.7)
                c.rect(sb_x + 13, sy - 8, 6.5, 6.5, stroke=1, fill=0)
                c.setFillColor(INK)
                c.setFont("Helvetica", 7.5)
                c.drawString(sb_x + 23, sy - 7,
                             _truncate(c, str(sub), "Helvetica", 7.5, sb_w - 25))
                sy -= 6 * mm
            sy -= 2 * mm

    # Notes (dot grid) fills whatever remains
    sy -= 2 * mm
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(sb_x, sy - 8, "Notes")
    sy -= 12
    c.setFillColor(DOT)
    step = 5 * mm
    gx = sb_x + 1
    while gx < sb_x + sb_w:
        gy = sy
        while gy > grid_bottom:
            c.circle(gx, gy, 0.35, stroke=0, fill=1)
            gy -= step
        gx += step

    c.showPage()
    c.save()
    return len(timed), len(allday)


def _truncate(c, text, font, size, max_w):
    t = text
    while c.stringWidth(t, font, size) > max_w and len(t) > 3:
        t = t[:-2]
    return t + ("…" if t != text else "")


def main():
    ap = argparse.ArgumentParser(description="planner daily page from calendar")
    ap.add_argument("--date", default=dt.date.today().isoformat(),
                    help="YYYY-MM-DD (default today)")
    ap.add_argument("--events", required=True, help="path to calendar JSON (meetings)")
    ap.add_argument("--tasks", default=None,
                    help="optional tasks JSON: [{\"title\":..,\"subtasks\":[..]}]")
    ap.add_argument("--start", type=int, default=6, help="first hour (default 6)")
    ap.add_argument("--end", type=int, default=23, help="last hour (default 23)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    date = dt.date.fromisoformat(args.date)
    events = load_events(args.events)
    tasks = []
    if args.tasks and os.path.exists(args.tasks):
        with open(args.tasks) as f:
            tasks = json.load(f)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)
    out_path = args.out or os.path.join(out_dir, f"daily-{args.date}.pdf")
    nt, na = render(date, events, tasks, args.start, args.end, out_path)
    print(f"Wrote {out_path}  ({nt} timed, {na} all-day events, {len(tasks)} tasks)")


if __name__ == "__main__":
    main()
