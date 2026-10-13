#!/usr/bin/env python3
"""Merge settings.snippet.json into ~/.claude/settings.json.

Adds only what is missing and keeps everything else as it is:
  - env: adds CLAUDE_CODE_PLUGIN_DIRS, or appends the task-track folder to an existing value.
    The snippet's "@TASK_TRACK@" is this checkout's task-track folder, wherever it lives.
  - permissions.additionalDirectories / permissions.allow: union, order kept.
    "~/vault" becomes $VAULT when that is set.
  - hooks: adds each snippet hook whose command is not already configured;
    removes the old ~/.claude/hooks/end-task.sh hook (the task-track mod replaced it)

Backs up the current file to settings.json.bak.<timestamp> before writing.
Prints which keys changed, never their values (settings can hold secrets).

Usage:
  python3 merge-settings.py            # merge
  python3 merge-settings.py --dry-run  # show what would change, write nothing
  python3 merge-settings.py --settings PATH --snippet PATH
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK_TRACK = str(HERE / "task-track")
# Exact commands, compared after expanding ~ and $HOME: a user's own hook that merely
# shares the file name is never touched.
RETIRED_COMMANDS = ("~/.claude/hooks/end-task.sh",)


def same_path(a: str, b: str) -> bool:
    expand = lambda p: os.path.normpath(os.path.expandvars(os.path.expanduser(p.strip())))
    return expand(a) == expand(b)


def is_retired(command: str) -> bool:
    return any(same_path(command, r) for r in RETIRED_COMMANDS)


def resolve(snippet: dict) -> dict:
    """The snippet with this machine's paths filled in."""
    text = json.dumps(snippet).replace("@TASK_TRACK@", TASK_TRACK)
    vault = os.environ.get("VAULT")
    if vault:
        text = text.replace('"~/vault"', json.dumps(vault))
    return json.loads(text)


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    if not text.strip():
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as err:
        sys.exit(f"{path} is not valid JSON ({err}). Fix it first; nothing was changed.")
    if not isinstance(value, dict):
        sys.exit(f"{path} is not a JSON object; nothing was changed.")
    return value


def commands_of(groups: list) -> set[str]:
    return {h.get("command", "") for g in groups for h in g.get("hooks", [])}


def merge(settings: dict, snippet: dict) -> list[str]:
    changes: list[str] = []

    # env: path-list join for the plugin dirs, add-if-missing for anything else
    env = settings.setdefault("env", {})
    for key, value in snippet.get("env", {}).items():
        if key == "CLAUDE_CODE_PLUGIN_DIRS" and env.get(key):
            parts = env[key].split(os.pathsep)
            if not any(same_path(p, value) for p in parts):
                env[key] = os.pathsep.join(parts + [value])
                changes.append(f"env.{key}: appended the task-track folder")
        elif key not in env:
            env[key] = value
            changes.append(f"env.{key}: added")
    if not env:
        settings.pop("env")

    # permissions: union of lists
    perms = settings.setdefault("permissions", {})
    for key, values in snippet.get("permissions", {}).items():
        current = perms.setdefault(key, [])
        added = [v for v in values if v not in current]
        current.extend(added)
        for v in added:
            changes.append(f"permissions.{key}: added {v}")

    # hooks: add missing commands, drop retired ones
    hooks = settings.setdefault("hooks", {})
    for event, groups in list(hooks.items()):
        kept = []
        for group in groups:
            inner = [h for h in group.get("hooks", []) if not is_retired(h.get("command", ""))]
            if len(inner) != len(group.get("hooks", [])):
                changes.append(f"hooks.{event}: removed the retired end-task.sh hook")
            if inner:
                kept.append({**group, "hooks": inner})
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    for event, groups in snippet.get("hooks", {}).items():
        existing = hooks.setdefault(event, [])
        have = commands_of(existing)
        for group in groups:
            missing = [h for h in group.get("hooks", []) if h.get("command", "") not in have]
            if missing:
                existing.append({**group, "hooks": missing})
                for h in missing:
                    changes.append(f"hooks.{event}: added {h['command']}")
    return changes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--settings", type=Path, default=Path.home() / ".claude" / "settings.json")
    ap.add_argument("--snippet", type=Path, default=HERE / "settings.snippet.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.snippet.exists():
        sys.exit(f"Snippet not found: {args.snippet}")
    settings = load(args.settings)
    snippet = resolve(load(args.snippet))
    changes = merge(settings, snippet)

    if not changes:
        print(f"Nothing to merge: {args.settings} already has everything.")
        return
    print(("Would change" if args.dry_run else "Changed") + f" {args.settings}:")
    for c in changes:
        print(f"  - {c}")
    if args.dry_run:
        return

    args.settings.parent.mkdir(parents=True, exist_ok=True)
    if args.settings.exists():
        backup = args.settings.with_name(f"settings.json.bak.{time.strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(args.settings, backup)
        print(f"Backup: {backup}")
    tmp = args.settings.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n")
    json.loads(tmp.read_text())  # never leave a broken settings file
    tmp.replace(args.settings)
    print("Done. Start a new `claude` session to load the hooks and the task-track mod.")


if __name__ == "__main__":
    main()
