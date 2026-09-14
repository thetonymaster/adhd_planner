---
name: capture-triage
description: >
  Use whenever someone dumps out many mixed, unsorted items — to-dos, thoughts,
  worries, reminders, whether swirling in their head or jotted on a list — and
  wants help deciding what actually matters and what to do first. Take the whole
  jumble and hand back a prioritized plan: each item ranked by when (today / this
  week / later) and by priority (do now / schedule / hand off / drop), with rough
  time estimates. This is the go-to for "clear my head," "organize everything on
  my mind," "what should I actually work on," triaging a brain dump, or sorting a
  raw list of random things into a priority matrix. Not for tidying files, adding
  calendar events, or summarizing text. To break one big task into steps use
  break-down-task; to time-block an already-sorted list use plan-day.
---

# Capture & triage

The intake front door: messy capture in, sorted plan out.

## Inputs

- **inbox.md** (repo root) — the user jots one thought per line (`- ...`) all day.
- **Live dump** — anything the user types now. Add those lines to inbox.md first
  (so they're archived too), or include them in the item list you classify.

## Steps

1. **Parse the inbox:**

   ```
   python3 tools/triage.py parse
   ```

   Prints the raw items as JSON. If empty and there's no live dump, tell the
   user there's nothing to triage and stop.

2. **Classify every item** (this is your judgment). For each, decide:
   - **bucket**: `today` (must move today), `soon` (this week), `eventually`.
   - **quadrant**: `do` (important & urgent), `schedule` (important, not urgent),
     `delegate` (urgent, not important — a quick handoff/call), `delete` (drop /
     someday-maybe, low value).
   - **minutes**: a rough estimate for real tasks (pad ~25%). Round toward 25/50/75.
   - optional **note**: why it's urgent, a deadline, etc.

   ADHD guidance: be honest about what's actually *today* — cap Today at what
   fits the remaining hours. Push the rest to Soon. Actively mark low-value
   items `delete` so the list stays short.

3. **Write a decisions.json** (list of `{item, bucket, quadrant, minutes, note}`)
   to `tools/out/decisions.json`, then apply:

   ```
   python3 tools/triage.py apply --decisions tools/out/decisions.json --date <today>
   ```

   This writes `triage-<date>.md` (summary + matrix), `tasks-<date>.json`
   (Today's do/schedule items, for plan-day), archives the inbox to
   `inbox-archive.md`, and clears inbox.md.

4. **Show the summary** in chat: the three buckets and the matrix, and call out
   what you dropped and why.

5. **Offer the next step** — hand `tasks-<date>.json` to the **plan-day** skill
   to time-block Today's items around the calendar, and/or the **daily-page**
   skill to print the page. Don't auto-run; ask.

## Scheduled run (daily 18:00)

A scheduled task runs this at end of workday. When triggered with no user
present: parse, classify, apply, and leave the summary + `tasks-<date>.json`
ready. Keep it self-contained — read inbox.md, don't wait for input.
