#!/usr/bin/env python3
"""tasks plugin SessionEnd hook: parks the task this session was on.

Sets `status: active` -> `status: parked` in the note named by Tasks/.session/<session_id> (any vault) and
appends a Log line, so a task board's Doing column only holds tasks a live session is on. Never blocks
session end: main returns 0 whatever happens; problems go to stderr.
"""
import json
import os
import pathlib
import re
import sys
import tempfile
from collections.abc import Mapping

import vaults

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---(?=\n|\Z)", re.S)
ACTIVE = re.compile(r"^status:[ \t]*\"?active\"?[ \t]*$", re.M)
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def park(text: str, stamp: str) -> str | None:
    """The note parked and logged, or None when its frontmatter status is not `active`."""
    m = FRONTMATTER.match(text)
    if not m or not ACTIVE.search(m.group(1)):
        return None
    block = ACTIVE.sub("status: parked", m.group(1), count=1)
    body = text[m.end():]
    line = f"- {stamp} — parked: session ended"
    lines = body.split("\n")
    start = next((i for i, l in enumerate(lines) if l.rstrip() == "## Log"), None)
    if start is None:
        body = body.rstrip("\n") + f"\n\n## Log\n{line}\n"
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        last = max(i for i in range(start, end) if i == start or lines[i].strip())
        lines.insert(last + 1, line)
        body = "\n".join(lines)
    return f"---\n{block}\n---{body}"


def write_atomic(path: pathlib.Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def main(stdin: str, env: Mapping[str, str], home: str) -> int:
    try:
        data = json.loads(stdin or "{}")
    except ValueError as e:
        print(f"park_on_end: parse hook input: {e}", file=sys.stderr)
        return 0
    sid = str(data.get("session_id") or "") if isinstance(data, dict) else ""
    if not SESSION_ID.match(sid):
        return 0
    config = vaults.load_config(env, home)
    stamp = vaults.now(vaults.zone_for(config, env)).strftime("[[%Y-%m-%d]] %H:%M")
    for vault in config.vaults:
        tasks = pathlib.Path(vault.path) / "Tasks"
        pointer = tasks / ".session" / sid
        if not pointer.is_file():
            continue
        note = tasks / f"{vaults.slug_or_empty(_read(pointer))}.md"
        if note.name == ".md":
            print(f"park_on_end: session file names no valid task: {pointer}", file=sys.stderr)
            continue
        text = _read(note)
        parked = park(text, stamp) if text else None
        if parked is None:
            continue
        try:
            write_atomic(note, parked)
        except OSError as e:
            print(f"park_on_end: write note: {note}: {e}", file=sys.stderr)
    return 0


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError) as e:
        print(f"park_on_end: read note: {path}: {e}", file=sys.stderr)
        return ""


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read() if not sys.stdin.isatty() else "", os.environ, os.path.expanduser("~")))
