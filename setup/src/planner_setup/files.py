"""Reading settings files and writing them back safely."""
from __future__ import annotations

import json
import shutil
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


def write_json(path: Path, data: dict, backups: Path, *, home: Path) -> Path | None:
    saved = backup(path, backups, home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    json.loads(tmp.read_text())  # never leave a broken settings file
    tmp.replace(path)
    return saved
