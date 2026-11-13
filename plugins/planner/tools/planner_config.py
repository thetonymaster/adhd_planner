"""Day settings from calendars.json: timezone, working hours, lunch, Pomodoro.

A key missing from the file falls back to DEFAULTS (the values every planner had
before these keys existed). Command-line flags on plan_day.py / plan_week.py win
over the file. "lunch": null (or "") means no protected lunch.
"""
import datetime as dt
import json
import os
import re
import sys
import zoneinfo

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendars.json")
DEFAULTS = {
    "timezone": "UTC",
    "work": "09:00-18:00",
    "lunch": "14:00-15:00",
    "pomodoro": {"work": 25, "break": 5, "long": 30, "long_every": 4},
}
_RANGE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")


class ConfigError(ValueError):
    pass


def parse_range(s, key, path=PATH):
    """"HH:MM-HH:MM" → (start_min, end_min); ConfigError naming `key` otherwise."""
    m = _RANGE.match(s) if isinstance(s, str) else None
    if not m:
        raise ConfigError(f'{path}: expected "{key}" like "09:00-18:00", got {s!r}')
    start, end = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
    if end <= start:
        raise ConfigError(f'{path}: "{key}" ends before it starts: {s!r}')
    return start, end


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as e:
        print(f"WARNING: could not read {path} ({e}); using the defaults "
              f"(UTC, work {DEFAULTS['work']}, lunch {DEFAULTS['lunch']}).", file=sys.stderr)
        data = {}
    except OSError as e:
        raise ConfigError(f"{path}: could not read it ({e})") from e
    except ValueError as e:
        raise ConfigError(f"{path}: not valid JSON ({e})") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a JSON object, got {type(data).__name__}")
    pomo_in = data.get("pomodoro", {})
    if not isinstance(pomo_in, dict):
        raise ConfigError(f'{path}: expected "pomodoro" to be an object, got {pomo_in!r}')
    pomodoro = dict(DEFAULTS["pomodoro"])
    for k, v in pomo_in.items():
        if k not in pomodoro:
            raise ConfigError(f'{path}: unknown key "pomodoro.{k}" (known: {", ".join(pomodoro)})')
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            what = "a whole number ≥ 1" if k == "long_every" else "a whole number of minutes ≥ 1"
            raise ConfigError(f'{path}: expected "pomodoro.{k}" to be {what}, got {v!r}')
        pomodoro[k] = v
    tz = data.get("timezone", DEFAULTS["timezone"])
    if not isinstance(tz, str) or not tz:
        raise ConfigError(f'{path}: expected "timezone" to be a string like "Europe/Madrid", got {tz!r}')
    if "timezone" in data:
        try:
            zoneinfo.ZoneInfo(tz)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError) as e:
            raise ConfigError(f'{path}: "timezone" {tz!r} is not an IANA timezone like "Europe/Madrid" '
                              f"(or this Python has no timezone database)") from e
    lunch = data.get("lunch", DEFAULTS["lunch"])
    return {
        "timezone": tz,
        "work": parse_range(data.get("work", DEFAULTS["work"]), "work", path),
        "lunch": None if lunch is None or lunch == "" else parse_range(lunch, "lunch", path),
        "pomodoro": pomodoro,
    }


def monday_of(date):
    return date - dt.timedelta(days=date.weekday())


def plan_days(today, week_start, include_weekend):
    """(Monday, ISO dates to plan). No week_start: this week from today on, or
    next week on a Saturday or Sunday. An explicit week_start plans all of it."""
    n_days = 7 if include_weekend else 5
    if week_start is None:
        week_start = monday_of(today)
        if today.weekday() >= 5:
            week_start += dt.timedelta(days=7)
        first = max(today, week_start)
    else:
        first = week_start
    days = [week_start + dt.timedelta(days=i) for i in range(n_days)]
    return week_start, [d.isoformat() for d in days if d >= first]
