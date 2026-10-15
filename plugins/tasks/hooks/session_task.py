#!/usr/bin/env python3
"""tasks plugin SessionStart resolver, run by load-task.sh after it prints `Now:`.

Prints the session's vault, its task and that task's Goal / Next / Open loops. Prints nothing
when no vault is usable. Never fails session start: a resolver error is named, and the default
vault's .active is used.
"""
import json
import os
import pathlib
import re
import time

import vaults

STRUCK = re.compile(r"^\s*- (\[.\] )?~~")
SECTION = re.compile(r"^## (Goal|Next|Open loops)")


def prune(tasks: pathlib.Path) -> list[str]:
    """Drops .session/ overrides older than 14 days; returns the ones it could not remove."""
    sessions = tasks / ".session"
    unpruned = []
    if sessions.is_dir():
        cutoff = time.time() - 14 * 86400
        for f in sessions.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
            except FileNotFoundError:
                pass  # another session pruned it first
            except OSError as e:
                unpruned.append(f"{f.name} ({type(e).__name__})")
    return unpruned


def sections(text: str) -> list[str]:
    """Goal, Next and Open loops, without struck-through lines (~~done~~), at most 40 lines."""
    lines, on = [], False
    for line in text.splitlines():
        if SECTION.match(line):
            on = True
            lines.append(line)
        elif line.startswith("## "):
            on = False
        elif on and not STRUCK.match(line):
            lines.append(line)
    return lines[:40]


def fallback(config, usable, why):
    for v in usable:
        if v.name == config.default:
            active = pathlib.Path(v.path) / "Tasks" / ".active"
            return vaults.Pick(v, vaults.slug_or_empty(active.read_text()) if active.is_file() else "", why)
    return None


def main() -> list[str]:
    home = os.path.expanduser("~")
    try:
        data = json.loads(os.environ.get("HOOK_INPUT") or "{}")
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    sid = str(data.get("session_id") or "")
    cwd = str(data.get("cwd") or os.getcwd())
    config = vaults.load_config(os.environ, home)
    out = []
    if config.error:
        out.append(f"Vault config error: {config.error}; using {config.vaults[0].path}")
    usable = [v for v in config.vaults if (pathlib.Path(v.path) / "Tasks").is_dir()]
    if not config.implicit:
        out += [f"(skipped vault {v.name}: no Tasks/ at {v.path})" for v in config.vaults if v not in usable]
    skipped, unpruned = [], []
    try:
        states = []
        for v in usable:
            unpruned += prune(pathlib.Path(v.path) / "Tasks")
            state, bad = vaults.read_state(v, sid)
            states.append(state)
            skipped += bad
        picked = vaults.pick(config, states, cwd, home)
    except Exception as e:
        # Never block session start: say what broke, then use the default vault's .active.
        error = f"{type(e).__name__}: {e}"
        picked = fallback(config, usable, f"{'global' if config.implicit else 'default'} (resolver error: {error})")
        if picked is None:  # the default vault is unusable too: the error line is all there is to say
            out.append(f"Task resolver error: {error}")
    if picked is None:
        return out
    out.append(f"Vault: {picked.vault.path}")
    if not config.implicit:
        others = [v.name for v in usable if v != picked.vault]
        out.append(f"Vault name: {picked.vault.name} ({picked.reason})" + (f" · others: {', '.join(others)}" if others else ""))
    if not picked.slug:
        out.append("No active task. Ask Q what we're working on, or suggest /tasks:task-start.")
        return out
    note = pathlib.Path(picked.vault.path) / "Tasks" / f"{picked.slug}.md"
    if not note.is_file():
        out.append(f"Active task '{picked.slug}' ({picked.reason}) has no note at {note}.")
        return out
    out.append(f"Active task: {picked.slug} ({picked.reason}) — full note: {note}")
    if skipped:
        out.append(f"(skipped unreadable notes: {', '.join(skipped)})")
    if unpruned:
        out.append(f"(could not prune .session/{', .session/'.join(unpruned)})")
    try:
        return out + sections(note.read_text())
    except (OSError, UnicodeDecodeError) as e:
        return out + [f"(could not read {note}: {type(e).__name__}: {e})"]


if __name__ == "__main__":
    try:
        lines = main()
    except Exception as e:  # last resort: the time is already printed, say why nothing else is
        lines = [f"Task resolver failed: {type(e).__name__}: {e}"]
    if lines:
        print("\n".join(lines))
