"""Where things are: the vault, the bundled examples, the marketplace source."""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

GITHUB = "thetonymaster/adhd_planner"
NAME = "adhd-planner"


def vault(env: Mapping[str, str], home: Path) -> Path:
    raw = env.get("VAULT") or "~/vault"
    return Path(str(home) + raw[1:]) if raw == "~" or raw.startswith("~/") else Path(raw)


def vaults_file(env: Mapping[str, str], home: Path) -> Path:
    """The vault registry the hooks and the mod read (plugins/tasks/hooks/vaults.py)."""
    raw = env.get("ADHD_PLANNER_VAULTS")
    return Path(norm(raw, home)) if raw else home / ".config" / "adhd-planner" / "vaults.json"


def tilde(path: Path, home: Path) -> str:
    """`path` with `~` for home, the way vaults.json and `repo:` write paths."""
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def norm(path: str, home: Path | str) -> str:
    """`~` → home, then normalised (no trailing slash, no `..`), for comparing paths as written."""
    if path == "~" or path.startswith("~/"):
        path = str(home) + path[1:]
    return os.path.normpath(path)


def examples() -> Path:
    bundled = Path(__file__).resolve().parent / "examples"
    if bundled.is_dir():
        return bundled
    checkout = Path(__file__).resolve().parents[3] / "examples"  # setup/src/planner_setup → repo
    if checkout.is_dir():
        return checkout
    raise SystemExit(f"examples/ not found (looked in {bundled} and {checkout}); reinstall planner-setup.")


def marketplace_source(cwd: Path) -> str:
    manifest = cwd / ".claude-plugin" / "marketplace.json"
    try:
        if json.loads(manifest.read_text()).get("name") == NAME:
            return str(cwd)
    except (OSError, ValueError):
        pass
    return GITHUB
