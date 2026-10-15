"""Reading settings files and writing them back safely."""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists() or not path.read_text().strip():
        return {}
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise SystemExit(f"{path} is not valid JSON ({err}). Fix it first; nothing was changed.")
    if not isinstance(value, dict):
        raise SystemExit(f"{path} holds a JSON {type(value).__name__}, expected an object; nothing was changed.")
    return value


def backup_dir(home: Path) -> Path:
    """A backup folder no earlier run used: two runs in one second must not share one."""
    base = home / ".claude" / "backups" / time.strftime("%Y%m%d%H%M%S")
    candidate, n = base, 1
    while candidate.exists():
        candidate, n = base.with_name(f"{base.name}-{n}"), n + 1
    return candidate


def backup(path: Path, backups: Path, *, home: Path) -> Path | None:
    if not path.exists():
        return None
    try:
        rel = path.resolve().relative_to(home.resolve())
    except ValueError:
        rel = Path(path.name)
    dest = backups / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        shutil.copytree(path, dest)
    else:
        shutil.copy2(path, dest)
    return dest


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def write_json(path: Path, data: dict, backups: Path, *, home: Path) -> Path | None:
    saved = backup(path, backups, home=home)
    # A symlinked settings.json (dotfiles) stays a link: write the file it points at.
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    # A unique tmp beside the target (mkstemp: O_EXCL, never a link, never another run's file),
    # given the target's mode before any content lands in it, so a 0600 file is never briefly readable.
    existing = target.stat().st_mode if target.exists() else None
    fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    tmp = Path(name)
    try:
        try:
            os.fchmod(fd, stat.S_IMODE(existing) if existing is not None else 0o666 & ~_umask())
            body = memoryview((json.dumps(data, indent=2) + "\n").encode())
            while body:  # os.write may write less than asked
                body = body[os.write(fd, body):]
        finally:
            os.close(fd)
        json.loads(tmp.read_text())  # never leave a broken settings file
        tmp.replace(target)
    except BaseException:
        tmp.unlink(missing_ok=True)  # no half-written settings copy left beside the target
        raise
    return saved
