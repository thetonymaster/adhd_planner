# Vault timezone — design

Date: 2026-10-16 · Status: approved in chat

## Problem

Every time and date the plugins write follows the machine's local clock: task-track's
focus lines (`stamp()` in `note.ts`), the `Now:` lines from the tasks hooks (`date`), and
the Log lines and daily-note dates the model writes from `Now:` / `date +%F`. A machine
whose clock is UTC (a WSL box with no timezone set) stamps every line 6 h off for
America/Mexico_City and can file late-evening work under tomorrow's daily note.
Seen 2026-10-16: the `vail` vault's daily note, written from WSL at 11:37–13:26 local,
holds lines stamped 17:37–19:26.

## Decision

One optional setting, read by every writer: a top-level `"timezone"` (IANA name) in
`vaults.json`, next to `"default"` and `"vaults"`.

```json
{ "timezone": "America/Mexico_City", "default": "personal", "vaults": { ... } }
```

Zone used, first that applies: `vaults.json` `timezone` → `$TZ` → the system clock.
A machine with the right system clock needs nothing.

## Rules

1. **Parse** (`vaults.py`, `resolve.ts`, same words): `timezone` absent → `''`. Present but not
   a string, or not a zone the runtime knows (`zoneinfo.ZoneInfo` / `Intl.DateTimeFormat`) →
   the vaults are still used, the timezone is ignored, and a warning names it, on its own
   `Vault config warning:` line (the error line would claim the vaults were dropped) and in
   the mod's config-problem text: `<file>: timezone 'Mars/Base' is not an IANA zone; using $TZ
   or the system clock`. A wrong zone never costs the session its vault.
2. **Stamps** (task-track): `stamp(date, timeZone)` formats in the zone (`Intl`, 24 h);
   every call site passes the configured zone (`''` = runtime local, today's behaviour).
   The day roll-over (`today()`) uses the same zone, so a focus day ends at local midnight.
3. **`Now:` lines** (tasks hooks): SessionStart prints `Now:` from `session_task.py` in the
   zone; UserPromptSubmit runs a small `now.py` that does the same. Without python3, both
   fall back to `date`, which already honours `$TZ`.
4. **Model-written stamps** (task skills and the planner's Vault section): the date and time
   come from the latest `Now:` line; `date +%F` only when there is none (Cowork without hooks).
5. **Setup**: `planner-setup timezone <IANA>` writes the field (validated), keeping the
   rest of `vaults.json`; `add-vault` keeps an existing `timezone`. With no `vaults.json`,
   `timezone` creates one holding the implicit vault as `personal`, the way `add-vault` does.
6. **Docs**: `docs/setup.md` documents the field and when it is needed.

## Out of scope

Per-vault zones (one person, one clock); the planner's `tools/calendars.json` `timezone`
(calendar math, read by the Python tools; unchanged); converting lines already written.

## Tests

- Shared fixture cases (`vault-cases.ts`, run by both suites): zone set, absent, invalid
  (vaults kept, error named), non-string.
- task-track: `stamp` in `Asia/Tokyo` and `America/Mexico_City` from one fixed instant;
  a focus flush and the day roll-over under a configured zone with a UTC runtime.
- Python: `now.py` and the SessionStart `Now:` line under a configured zone with
  `TZ=UTC`; the python3-less fallback still prints `Now:`.
- setup: `timezone` writes, validates, and survives `add-vault`.
