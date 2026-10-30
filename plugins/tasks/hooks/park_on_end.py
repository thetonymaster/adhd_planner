#!/usr/bin/env python3
"""tasks plugin SessionEnd hook: parks the task this session was on.

Sets `status: active` -> `status: parked` in the note named by Tasks/.session/<session_id> (any vault) and
appends a Log line, so a task board's Doing column only holds tasks a live session is on. Skips `/clear`
(hook input `reason: "clear"`): task-start and task-switch tell the user to run it right after activating a
task, and that task must stay active; park-then-clear still parks because task-park writes `parked` itself.
Never blocks session end: main returns 0 whatever happens; problems go to stderr.
"""
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping
from typing import TextIO

import vaults

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---(?=\n|\Z)", re.S)
ACTIVE = re.compile(r"^status:[ \t]*\"?active\"?[ \t]*$", re.M)
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")
WRITE_TRIES = 3


def park(text: str, stamp: str) -> str | None:
    """The note parked and logged, or None when its frontmatter status is not `active`. Keeps CRLF notes CRLF."""
    if not text.startswith("---\r\n"):
        return _park_lf(text, stamp)
    out = _park_lf(text.replace("\r\n", "\n"), stamp)
    return None if out is None else out.replace("\n", "\r\n")


def _park_lf(text: str, stamp: str) -> str | None:
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


class NoteChanged(Exception):
    """The note was written by someone else after it was read."""


def version(path: pathlib.Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_mtime_ns, st.st_size


def write_atomic(path: pathlib.Path, text: str, read_at: tuple[int, int]) -> None:
    """Replaces `path` with `text`; raises NoteChanged instead when `path` moved past `read_at` (its version when read)."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        shutil.copymode(path, tmp)  # mkstemp makes 0600; keep the note's own mode
        # Narrows, not closes, the race with /note or Obsidian: a write between this check and the replace is still lost.
        if version(path) != read_at:
            raise NoteChanged(path)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def main(stdin: str | TextIO, env: Mapping[str, str], home: str) -> int:
    """Always 0: a hook must never block session end. `stdin` is the hook input text, or a stream read here."""
    try:
        try:
            raw = stdin if isinstance(stdin, str) else stdin.read()
        except (OSError, ValueError) as e:  # UnicodeDecodeError is a ValueError
            print(f"park_on_end: read hook input: {type(e).__name__}: {e}", file=sys.stderr)
            return 0
        _park_session(raw, env, home)
    except Exception as e:  # noqa: BLE001 - reported, never raised
        print(f"park_on_end: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
    return 0


def _park_session(stdin: str, env: Mapping[str, str], home: str) -> None:
    try:
        data = json.loads(stdin or "{}")
    except ValueError as e:
        print(f"park_on_end: parse hook input: {e}", file=sys.stderr)
        return
    if not isinstance(data, dict) or data.get("reason") == "clear":
        return
    sid = str(data.get("session_id") or "")
    if not SESSION_ID.match(sid):
        return
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
        _park_note(note, stamp)


def _park_note(note: pathlib.Path, stamp: str) -> None:
    """Parks `note`, re-reading it when it changes under us; gives up (stderr) after WRITE_TRIES."""
    for _ in range(WRITE_TRIES):
        try:
            read_at = version(note)
        except OSError as e:
            print(f"park_on_end: read note: {note}: {e}", file=sys.stderr)
            return
        text = _read(note)
        parked = park(text, stamp) if text else None
        if parked is None:
            return
        try:
            write_atomic(note, parked, read_at)
            return
        except NoteChanged:
            continue
        except (OSError, ValueError) as e:
            print(f"park_on_end: write note: {note}: {e}", file=sys.stderr)
            return
    print(f"park_on_end: note kept changing, left active: {note}", file=sys.stderr)


def _read(path: pathlib.Path) -> str:
    try:
        with open(path, encoding="utf-8", newline="") as f:  # newline="": a CRLF note reaches park() as CRLF
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"park_on_end: read note: {path}: {e}", file=sys.stderr)
        return ""


if __name__ == "__main__":
    sys.exit(main("" if sys.stdin.isatty() else sys.stdin, os.environ, os.path.expanduser("~")))
