"""Registered Obsidian vaults, and which vault and task a session gets.

Config: $ADHD_PLANNER_VAULTS, else ~/.config/adhd-planner/vaults.json. No file → one implicit
vault (CLAUDE_PLUGIN_OPTION_VAULTPATH → $VAULT → ~/vault), exactly as before vaults.json existed.
Mirrors plugins/task-track/hooks/resolve.ts; both run plugins/task-track/tests/fixtures/vault-cases.ts.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def slug_or_empty(text: str) -> str:
    """A task slug read from a vault file, or '' when it is not one (it would name a path outside Tasks/)."""
    slug = text.strip()
    return slug if NAME.match(slug) else ""


@dataclass(frozen=True)
class Vault:
    name: str
    path: str  # `~` expanded, symlinks kept: the `Vault:` line prints it as written
    folders: tuple[tuple[str, str], ...] = ()  # (as written, `~` expanded and symlinks resolved)


@dataclass(frozen=True)
class Config:
    default: str
    vaults: tuple[Vault, ...]
    implicit: bool  # no usable vaults.json: the single vault from the option / $VAULT / ~/vault
    error: str = ""  # why vaults.json was ignored; '' when it was used or absent


def expand(path: str, home: str) -> str:
    return home + path[1:] if path == "~" or path.startswith("~/") else path


def norm(path: str, home: str) -> str:
    """For comparing: `~` expanded, symlinks resolved (iCloud checkouts bind like their target)."""
    return os.path.realpath(expand(path, home))


def within(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def config_path(env: Mapping[str, str], home: str) -> str:
    """$ADHD_PLANNER_VAULTS with `~` expanded (settings.json `env` does not expand it), else the default file."""
    raw = env.get("ADHD_PLANNER_VAULTS")
    return expand(raw, home) if raw else os.path.join(home, ".config", "adhd-planner", "vaults.json")


def implicit(env: Mapping[str, str], home: str, error: str = "") -> Config:
    raw = env.get("CLAUDE_PLUGIN_OPTION_VAULTPATH") or env.get("VAULT") or "~/vault"
    return Config("default", (Vault("default", expand(raw, home)),), True, error)


def parse(text: str, where: str, env: Mapping[str, str], home: str) -> Config:
    """vaults.json text → Config; any problem → the implicit vault, with `error` naming it."""
    try:
        data = json.loads(text)
    except ValueError as e:
        return implicit(env, home, f"{where}: not valid JSON ({e})")
    try:
        return _config(data, home)
    except ValueError as e:
        return implicit(env, home, f"{where}: {e}")


def _config(data: object, home: str) -> Config:
    if not isinstance(data, dict) or not isinstance(data.get("vaults"), dict) or not data["vaults"]:
        raise ValueError('expected {"vaults": {"<name>": {"path": "..."}}} with at least one vault')
    found: list[Vault] = []
    owner: dict[str, str] = {}
    for name, spec in data["vaults"].items():
        if not NAME.match(name):
            raise ValueError(f"vault name '{name}' must be kebab-case (a-z, 0-9, -)")
        path = spec.get("path") if isinstance(spec, dict) else None
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"vault '{name}' has no \"path\"")
        if not os.path.isabs(expand(path.strip(), home)):
            raise ValueError(f"vault '{name}': path '{path}' must be absolute or start with ~/")
        folders = spec.get("folders", [])
        if not isinstance(folders, list) or not all(isinstance(f, str) and f.strip() for f in folders):
            raise ValueError(f"vault '{name}': \"folders\" must be a list of paths")
        pairs = []
        for written in folders:
            if not os.path.isabs(expand(written.strip(), home)):
                raise ValueError(f"vault '{name}': folder '{written}' must be absolute or start with ~/")
            root = norm(written, home)
            if owner.get(root, name) != name:
                raise ValueError(f"folder '{written}' is listed by both '{owner[root]}' and '{name}'")
            owner[root] = name
            pairs.append((written, root))
        found.append(Vault(name, expand(path.strip(), home).rstrip("/") or "/", tuple(pairs)))
    names = [v.name for v in found]
    default = data.get("default")
    if default is None and len(names) == 1:
        default = names[0]
    if default is None:
        raise ValueError(f'"default" is required with {len(names)} vaults')
    if default not in names:
        raise ValueError(f"\"default\" is '{default}', not one of: {', '.join(names)}")
    return Config(default, tuple(found), False)


def load_config(env: Mapping[str, str], home: str) -> Config:
    where = config_path(env, home)
    if not os.path.isabs(where):
        # Relative to whichever folder the session started in: a different file per repo.
        return implicit(env, home, f"$ADHD_PLANNER_VAULTS must be an absolute path or start with ~/, got {where!r}")
    try:
        text = pathlib.Path(where).read_text()
    except FileNotFoundError:
        return implicit(env, home)
    except (OSError, UnicodeDecodeError) as e:
        return implicit(env, home, f"{where}: {type(e).__name__}: {e}")
    return parse(text, where, env, home)


@dataclass(frozen=True)
class Note:
    slug: str
    repo: str
    status: str
    mtime: float


@dataclass(frozen=True)
class State:
    vault: Vault
    slugs: frozenset[str]  # every Tasks/*.md stem, readable or not
    notes: tuple[Note, ...]  # the readable ones
    override: str  # Tasks/.session/<sid>; '' when absent
    override_mtime: float
    active: str  # Tasks/.active; '' when absent


@dataclass(frozen=True)
class Pick:
    vault: Vault
    slug: str  # '' when the chosen vault has no active task
    reason: str  # this session | project: <folder> | folder <as written> | default | global


def _field(block: str, name: str) -> str:
    m = re.search(rf'^{name}:\s*"?([^"\n]*?)"?\s*$', block, re.M)
    return m.group(1) if m else ""


def read_state(vault: Vault, sid: str) -> tuple[State, list[str]]:
    """One vault's notes and pointer files, plus the note files it could not read."""
    tasks = pathlib.Path(vault.path) / "Tasks"
    paths = sorted(tasks.glob("*.md"))
    notes, skipped = [], []
    for p in paths:
        try:
            text = p.read_text()
        except (OSError, UnicodeDecodeError):
            skipped.append(p.name)
            continue
        m = re.match(r"---\n(.*?)\n---", text, re.S)
        block = m.group(1) if m else ""
        notes.append(Note(p.stem, _field(block, "repo"), _field(block, "status"), p.stat().st_mtime))
    session = tasks / ".session" / sid
    override, override_mtime = "", 0.0
    if sid and session.is_file():
        override, override_mtime = slug_or_empty(session.read_text()), session.stat().st_mtime
    active = tasks / ".active"
    state = State(vault, frozenset(p.stem for p in paths), tuple(notes), override, override_mtime,
                  slug_or_empty(active.read_text()) if active.is_file() else "")
    return state, skipped


def pick(config: Config, states: list[State], cwd: str, home: str) -> Pick | None:
    """Session override → repo note in any vault → deepest bound folder → default vault. None: nothing usable."""
    here = norm(cwd, home)
    overrides = [s for s in states if s.override and s.override in s.slugs]
    if overrides:
        s = max(overrides, key=lambda s: s.override_mtime)
        return Pick(s.vault, s.override, "this session")
    bound = []
    for s in states:
        for n in s.notes:
            if not n.repo or n.status == "done" or not NAME.match(n.slug):
                continue
            root = norm(n.repo, home)
            if within(here, root):
                bound.append((len(root), n.status == "active", n.mtime, n.slug, s.vault, root))
    if bound:
        best = max(bound, key=lambda b: b[:4])
        return Pick(best[4], best[3], f"project: {os.path.basename(best[5])}")
    folders = [(len(root), written, s) for s in states for written, root in s.vault.folders if within(here, root)]
    if folders:
        _, written, s = max(folders, key=lambda f: f[0])
        return Pick(s.vault, s.active, f"folder {written}")
    for s in states:
        if s.vault.name == config.default:
            return Pick(s.vault, s.active, "global" if config.implicit else "default")
    return None
