# Multiple vaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register several Obsidian vaults in `~/.config/adhd-planner/vaults.json`. Each session resolves to one vault, which the hooks, the skills and the task-track mod all use; task lists and `/task-switch` see every vault.

**Architecture:**
- **Python side:** one module, `plugins/tasks/hooks/vaults.py`, parses the config and picks the vault and task (pure functions, plus a thin `read_state` IO edge). Two hooks use it: `session_task.py`, run by `load-task.sh`, and `vault-allow.py`.
- **Mod side:** the task-track mod has its own in-process copy in `resolve.ts`.
- **Parity:** both resolvers run the same cases from `plugins/task-track/tests/fixtures/vault-cases.ts`. That file's body after `= ` is strict JSON, so Python can parse it; the mod's test runner refuses `.json` imports (verified 2026-10-13).
- **No config file:** with no `vaults.json`, everything behaves as before.

**Tech Stack:**
- Python 3 stdlib for the hooks and tests (`python3 -m unittest`).
- The TypeScript mod on the `claude-code` engine (`claude plugin test .`).
- The `planner-setup` CLI (uv, pytest, questionary).

**Spec:** `docs/superpowers/specs/2026-10-13-multi-vault-design.md`

## Global Constraints

- **Config path:** `$ADHD_PLANNER_VAULTS` if set, else `~/.config/adhd-planner/vaults.json`.
- **Vault names:** kebab-case, matching `^[a-z0-9][a-z0-9-]*$`.
- **No config file:** behave exactly as today. One implicit vault named `default` at `CLAUDE_PLUGIN_OPTION_VAULTPATH` → `$VAULT` → `~/vault`, and the task reason stays `global`.
- **Invalid config:** print `Vault config error: <file>: <what>; using <fallback path>` and continue with the implicit vault. Never block session start.
- **`Vault: <path>` line:** stays byte-identical, because skills parse it. `Vault name: <name> (<reason>)[ · others: a, b]` follows it, and only when a config file is in use.
- **Pick order:** session override (newest across vaults) → repo note in any vault (deepest, then `active`, then newest; `done` never binds) → deepest bound folder (that vault's `.active`) → default vault's `.active`.
- **Per-vault state:** each vault keeps its own `Tasks/.active`, `Tasks/.session/<sid>`, `Tasks/.pomo.json` and 14-day `.session/` prune.
- **Mod prefix:** `<vault> · ` appears only when 2+ vaults are registered.
- **Baseline before Task 1:** `tests/` 35 OK · `setup` 40 passed · `task-track` 98 pass. Existing tests are never edited; they guard the no-config behaviour.
- **Commits:** add files individually (no `git add .`) and use no AI attribution lines (Q's CLAUDE.md).

## Review Focus

1. **A cross-vault `/task-switch` mid-session in the mod.** Focus minutes must land on the *old* task through the *old* vault's `.pomo.json`, not the new one. Pinned in Task 5, test "a switch to a task in another vault credits the old task on the old vault's timer".
2. **The same slug existing in two vaults.** The mod's note cache must not hand one vault's frontmatter to the other's note. Pinned in Task 5, test "the same slug in two vaults keeps each vault's own frontmatter".
3. **A `vaults.json` with a trailing-slash folder, or `~/` paths.** These must match the same as without the slash, in both resolvers. Pinned by shared case "a folder listed by two vaults" (`~/code` vs `~/code/`), Task 2.
4. **A vault path that is a symlink (iCloud).** `vault-allow` must approve paths under the resolved target and add the resolved target. Pinned in Task 3, test `test_symlinked_second_vault_is_resolved`.
5. **`planner-setup add-vault` run the first time.** Today's vault must not vanish from the registry, so it is added as the default. Pinned in Task 7, `test_add_vault_creates_the_file_with_the_current_vault_as_default`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `plugins/tasks/hooks/vaults.py` (new) | Config parsing, per-vault state reading, the pure vault and task pick. |
| `plugins/tasks/hooks/session_task.py` (new) | SessionStart output: prune, read states, pick, and print the lines after `Now:`. |
| `plugins/tasks/hooks/load-task.sh` | Prints `Now:`, then hands off to `session_task.py`; keeps the python3-missing path. |
| `plugins/tasks/hooks/vault-allow.py` | Approves file tools inside any one registered vault. |
| `plugins/task-track/hooks/resolve.ts` | Adds `implicitVault`, `parseVaults`, `defaultVault`, `pickVault` (pure). |
| `plugins/task-track/hooks/register.tsx` | Reads the config each load, picks a vault per load, prefixes, flushes on vault change. |
| `plugins/task-track/types/index.d.ts` | Adds the `vaultName` and `configError` atoms to `PluginState`. |
| `plugins/task-track/tests/fixtures/vault-case.ts`, `vault-cases.ts` (new) | The shared case type and the cases. |
| `tests/test_vaults.py` (new) | Unit tests for config parsing. |
| `setup/src/planner_setup/{paths,actions,cli}.py` | `vaults_file`, `tilde`, `add_vault`, the `add-vault` subcommand and menu item. |
| Skills (×12) and docs (×4) | Vault prefix, cross-vault list and switch, and the "find it once" chain. |

---

### Task 1: Config parsing (`vaults.py`)

**Files:**
- Create: `plugins/tasks/hooks/vaults.py`
- Test: `tests/test_vaults.py`

**Interfaces:**
- Produces:
  - `Vault(name: str, path: str, folders: tuple[tuple[str, str], ...])`. `path` is `~`-expanded and keeps any symlinks; `folders` pairs are (as written, realpath).
  - `Config(default: str, vaults: tuple[Vault, ...], implicit: bool, error: str)`.
  - Helpers: `expand(path, home)`, `norm(path, home)`, `within(path, root)`, `config_path(env, home)`.
  - Constructors: `implicit(env, home, error="") -> Config`, `parse(text, where, env, home) -> Config`, `load_config(env, home) -> Config`.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for plugins/tasks/hooks/vaults.py config parsing. Run: python3 -m unittest discover -s tests"""
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks"))
import vaults  # noqa: E402

HOME = "/home/q"


def parse(data, env=None):
    text = data if isinstance(data, str) else json.dumps(data)
    return vaults.parse(text, "vaults.json", env or {}, HOME)


class ConfigTest(unittest.TestCase):
    def test_two_vaults_with_folders(self):
        c = parse({"default": "personal", "vaults": {
            "personal": {"path": "~/vault"},
            "work": {"path": "~/work-vault/", "folders": ["~/acme"]}}})
        self.assertEqual(c.error, "")
        self.assertFalse(c.implicit)
        self.assertEqual(c.default, "personal")
        self.assertEqual([(v.name, v.path) for v in c.vaults], [("personal", "/home/q/vault"), ("work", "/home/q/work-vault")])
        self.assertEqual(c.vaults[1].folders[0][0], "~/acme")

    def test_one_vault_needs_no_default(self):
        self.assertEqual(parse({"vaults": {"main": {"path": "/v"}}}).default, "main")

    def test_errors_fall_back_to_the_implicit_vault_and_name_the_problem(self):
        cases = {
            "{not json": "vaults.json: not valid JSON (",
            json.dumps({"vaults": {}}): 'with at least one vault',
            json.dumps({"vaults": {"Work": {"path": "/w"}}}): "vault name 'Work' must be kebab-case (a-z, 0-9, -)",
            json.dumps({"vaults": {"w": {}}}): "vault 'w' has no \"path\"",
            json.dumps({"vaults": {"w": {"path": "/w", "folders": "~/x"}}}): "vault 'w': \"folders\" must be a list of paths",
            json.dumps({"vaults": {"a": {"path": "/a"}, "b": {"path": "/b"}}}): '"default" is required with 2 vaults',
            json.dumps({"default": "nope", "vaults": {"a": {"path": "/a"}}}): "\"default\" is 'nope', not one of: a",
            json.dumps({"default": "a", "vaults": {"a": {"path": "/a", "folders": ["~/code"]},
                                                   "b": {"path": "/b", "folders": ["~/code/"]}}}):
                "folder '~/code/' is listed by both 'a' and 'b'",
        }
        for text, why in cases.items():
            with self.subTest(why):
                c = vaults.parse(text, "vaults.json", {"VAULT": "~/notes"}, HOME)
                self.assertIn(why, c.error)
                self.assertTrue(c.implicit)
                self.assertEqual([(v.name, v.path) for v in c.vaults], [("default", "/home/q/notes")])

    def test_implicit_follows_option_then_env_then_home_vault(self):
        self.assertEqual(vaults.implicit({}, HOME).vaults[0].path, "/home/q/vault")
        self.assertEqual(vaults.implicit({"VAULT": "/n"}, HOME).vaults[0].path, "/n")
        self.assertEqual(vaults.implicit({"VAULT": "/n", "CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/o"}, HOME).vaults[0].path, "/home/q/o")

    def test_load_config_reads_the_env_path_or_returns_implicit(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "v.json")
        self.assertTrue(vaults.load_config({"ADHD_PLANNER_VAULTS": path}, d).implicit)
        pathlib.Path(path).write_text(json.dumps({"vaults": {"x": {"path": "/x"}}}))
        self.assertEqual(vaults.load_config({"ADHD_PLANNER_VAULTS": path}, d).default, "x")
        self.assertEqual(vaults.config_path({}, "/h"), "/h/.config/adhd-planner/vaults.json")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python3 -m unittest tests.test_vaults -v`
Expected: ERROR `ModuleNotFoundError: No module named 'vaults'`

- [ ] **Step 3: Write `plugins/tasks/hooks/vaults.py` (config half)**

```python
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
    return env.get("ADHD_PLANNER_VAULTS") or os.path.join(home, ".config", "adhd-planner", "vaults.json")


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
        folders = spec.get("folders", [])
        if not isinstance(folders, list) or not all(isinstance(f, str) and f.strip() for f in folders):
            raise ValueError(f"vault '{name}': \"folders\" must be a list of paths")
        pairs = []
        for written in folders:
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
    try:
        text = pathlib.Path(where).read_text()
    except FileNotFoundError:
        return implicit(env, home)
    except (OSError, UnicodeDecodeError) as e:
        return implicit(env, home, f"{where}: {type(e).__name__}: {e}")
    return parse(text, where, env, home)
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python3 -m unittest tests.test_vaults -v`
Expected: 5 tests OK. (On macOS `norm` resolves `/home/q/...` as-is because the path doesn't exist; that is fine for the duplicate-folder check.)

- [ ] **Step 5: Commit**

```bash
git add plugins/tasks/hooks/vaults.py tests/test_vaults.py
git commit -m "feat(tasks): parse vaults.json into a vault registry"
```

---

### Task 2: Shared cases + the Python resolver (`session_task.py`)

**Files:**
- Create: `plugins/task-track/tests/fixtures/vault-case.ts`, `plugins/task-track/tests/fixtures/vault-cases.ts`, `plugins/tasks/hooks/session_task.py`
- Modify: `plugins/tasks/hooks/vaults.py` (append the state and pick half), `plugins/tasks/hooks/load-task.sh` (whole file, 106 → ~25 lines)
- Test: `tests/test_load_task.py` (append one class; the existing tests stay untouched)

**Interfaces:**
- Consumes: Task 1's `Vault`, `Config`, `norm`, `within`, `load_config`.
- Produces:
  - `Note(slug, repo, status, mtime)`
  - `State(vault, slugs: frozenset[str], notes, override, override_mtime, active)`
  - `Pick(vault, slug, reason)`
  - `read_state(vault, sid) -> (State, list[str])`
  - `pick(config, states, cwd, home) -> Pick | None`
  - The fixture file format: `export const CASES: readonly VaultCase[] = <strict JSON array>`. Task 4 reads the same file.

- [ ] **Step 1: Write the case type** `plugins/task-track/tests/fixtures/vault-case.ts`

```ts
/** One shared vault-resolution case. Run by tests/task-track.test.ts and by tests/test_load_task.py. */
export type NoteSpec = { status?: string; repo?: string; mtime?: number }
export type VaultDir = { notes?: Record<string, NoteSpec>; active?: string; session?: { slug: string; mtime?: number } }
export type VaultCase = {
  name: string
  /** vaults.json: an object is written as JSON, a string as raw text, null means no file. */
  config: Record<string, unknown> | string | null
  /** Folders under home that exist with a Tasks/ inside, keyed like "vault" or "work". Session id is always s1. */
  vaults: Record<string, VaultDir>
  cwd: string
  /** vault null: nothing usable. nameLine and skipped are checked by Python only (the mod prints neither). */
  expect: { vault: string | null; slug?: string; reason?: string; error?: string; skipped?: string; nameLine?: string }
}
```

- [ ] **Step 2: Write the cases** `plugins/task-track/tests/fixtures/vault-cases.ts`

Everything after `= ` must stay strict JSON (double quotes, no trailing commas, no comments): `tests/test_load_task.py` parses it with `json.loads`.

```ts
import type { VaultCase } from './vault-case'

export const CASES: readonly VaultCase[] = [
  {"name": "no vaults.json: the single vault and its .active",
   "config": null, "vaults": {"vault": {"notes": {"g": {}}, "active": "g"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "global"}},
  {"name": "nothing matches: the default vault's .active",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"w": {}}, "active": "w"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "p", "reason": "default", "nameLine": "Vault name: personal (default) · others: work"}},
  {"name": "a repo note in another vault binds the session to that vault",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"deploy": {"repo": "~/code/sre"}}}}, "cwd": "~/code/sre/src",
   "expect": {"vault": "~/work", "slug": "deploy", "reason": "project: sre", "nameLine": "Vault name: work (project: sre) · others: personal"}},
  {"name": "a bound folder picks its vault's .active",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work", "folders": ["~/acme"]}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"w": {}}, "active": "w"}}, "cwd": "~/acme/new-repo",
   "expect": {"vault": "~/work", "slug": "w", "reason": "folder ~/acme"}},
  {"name": "a repo note beats a folder bound to another vault",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work", "folders": ["~/acme"]}}},
   "vaults": {"vault": {"notes": {"side": {"repo": "~/acme/side"}}}, "work": {"notes": {"w": {}}, "active": "w"}}, "cwd": "~/acme/side",
   "expect": {"vault": "~/vault", "slug": "side", "reason": "project: side"}},
  {"name": "the deepest bound folder wins",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault", "folders": ["~/code"]}, "work": {"path": "~/work", "folders": ["~/code/work"]}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"w": {}}, "active": "w"}}, "cwd": "~/code/work/api",
   "expect": {"vault": "~/work", "slug": "w", "reason": "folder ~/code/work"}},
  {"name": "a sibling prefix of a bound folder does not bind",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault", "folders": ["~/code"]}, "work": {"path": "~/work", "folders": ["~/code/work"]}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"w": {}}, "active": "w"}}, "cwd": "~/code/workshop",
   "expect": {"vault": "~/vault", "slug": "p", "reason": "folder ~/code"}},
  {"name": "a session override in another vault beats a repo match",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"bound": {"repo": "~/code/app"}}, "active": "bound"}, "work": {"notes": {"w2": {}}, "session": {"slug": "w2"}}}, "cwd": "~/code/app",
   "expect": {"vault": "~/work", "slug": "w2", "reason": "this session"}},
  {"name": "overrides in two vaults: the newer one wins",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"p": {}}, "session": {"slug": "p", "mtime": 10}}, "work": {"notes": {"w": {}}, "session": {"slug": "w", "mtime": 20}}}, "cwd": "~/x",
   "expect": {"vault": "~/work", "slug": "w", "reason": "this session"}},
  {"name": "an override naming a missing note falls through",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"w": {}}, "session": {"slug": "gone"}}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "p", "reason": "default"}},
  {"name": "a bound folder whose vault has no .active: the vault, no task",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work", "folders": ["~/acme"]}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"w": {}}}}, "cwd": "~/acme/x",
   "expect": {"vault": "~/work", "slug": "", "reason": "folder ~/acme", "nameLine": "Vault name: work (folder ~/acme) · others: personal"}},
  {"name": "done notes never bind, in any vault",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}, "work": {"notes": {"old": {"repo": "~/code/app", "status": "done"}}}}, "cwd": "~/code/app",
   "expect": {"vault": "~/vault", "slug": "p", "reason": "default"}},
  {"name": "the deepest repo wins across vaults",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"outer": {"repo": "~/r"}}}, "work": {"notes": {"inner": {"repo": "~/r/sub"}}}}, "cwd": "~/r/sub/x",
   "expect": {"vault": "~/work", "slug": "inner", "reason": "project: sub"}},
  {"name": "unparseable vaults.json: error, single-vault fallback",
   "config": "{not json", "vaults": {"vault": {"notes": {"g": {}}, "active": "g"}, "work": {"notes": {"w": {}}, "active": "w"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "global", "error": "not valid JSON"}},
  {"name": "default names no vault",
   "config": {"default": "nope", "vaults": {"personal": {"path": "~/vault"}}},
   "vaults": {"vault": {"notes": {"g": {}}, "active": "g"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "global", "error": "\"default\" is 'nope', not one of: personal"}},
  {"name": "a folder listed by two vaults",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault", "folders": ["~/code"]}, "work": {"path": "~/work", "folders": ["~/code/"]}}},
   "vaults": {"vault": {"notes": {"g": {}}, "active": "g"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "global", "error": "folder '~/code/' is listed by both 'personal' and 'work'"}},
  {"name": "two vaults without a default",
   "config": {"vaults": {"a": {"path": "~/vault"}, "b": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"g": {}}, "active": "g"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "global", "error": "\"default\" is required with 2 vaults"}},
  {"name": "a bad vault name",
   "config": {"default": "Work", "vaults": {"Work": {"path": "~/work"}}},
   "vaults": {"vault": {"notes": {"g": {}}, "active": "g"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "global", "error": "vault name 'Work' must be kebab-case"}},
  {"name": "a vault with no Tasks/ is skipped",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work", "folders": ["~/acme"]}}},
   "vaults": {"vault": {"notes": {"p": {}}, "active": "p"}}, "cwd": "~/acme/x",
   "expect": {"vault": "~/vault", "slug": "p", "reason": "default", "skipped": "work", "nameLine": "Vault name: personal (default)"}},
  {"name": "the only vault in vaults.json is the default",
   "config": {"vaults": {"main": {"path": "~/vault"}}},
   "vaults": {"vault": {"notes": {"g": {}}, "active": "g"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "default", "nameLine": "Vault name: main (default)"}},
  {"name": "no usable vault at all: nothing past Now",
   "config": {"default": "personal", "vaults": {"personal": {"path": "~/vault"}}},
   "vaults": {}, "cwd": "~/x",
   "expect": {"vault": null}}
]
```

- [ ] **Step 3: Write the failing shared-case test**

Append this to `tests/test_load_task.py`, after `class LoadTaskTest` and before `if __name__ == "__main__":`:

```python
CASES = HOOK.parent.parent.parent / "task-track" / "tests" / "fixtures" / "vault-cases.ts"
MARK = "export const CASES: readonly VaultCase[] = "


class SharedVaultCasesTest(unittest.TestCase):
    """The cases tests/task-track.test.ts also runs against resolve.ts: the two resolvers must agree."""

    def test_every_shared_case(self):
        cases = json.loads(CASES.read_text().split(MARK, 1)[1])
        self.assertGreater(len(cases), 15)
        for case in cases:
            with self.subTest(case["name"]):
                home = pathlib.Path(tempfile.mkdtemp())
                try:
                    self.check(home, case, self.run_case(home, case))
                finally:
                    shutil.rmtree(home)

    def run_case(self, home, case):
        if case["config"] is not None:
            cfg = home / ".config" / "adhd-planner" / "vaults.json"
            cfg.parent.mkdir(parents=True)
            cfg.write_text(case["config"] if isinstance(case["config"], str) else json.dumps(case["config"]))
        base = time.time() - 1000
        for rel, v in case["vaults"].items():
            tasks = home / rel / "Tasks"
            tasks.mkdir(parents=True)
            for slug, n in v.get("notes", {}).items():
                p = tasks / f"{slug}.md"
                p.write_text(NOTE.format(slug=slug, status=n.get("status", "active"),
                                         repo=f"repo: {n['repo']}\n" if n.get("repo") else ""))
                os.utime(p, (base + n.get("mtime", 0),) * 2)
            if "active" in v:
                (tasks / ".active").write_text(v["active"] + "\n")
            if "session" in v:
                (tasks / ".session").mkdir()
                s = tasks / ".session" / "s1"
                s.write_text(v["session"]["slug"] + "\n")
                os.utime(s, (base + v["session"].get("mtime", 0),) * 2)
        cwd = str(home) + case["cwd"][1:]
        env = {"HOME": str(home), "PATH": os.environ["PATH"]}
        out = subprocess.run(["bash", str(HOOK)], input=json.dumps({"session_id": "s1", "cwd": cwd}).encode(),
                             env=env, capture_output=True, timeout=10, check=True)
        return out.stdout.decode()

    def check(self, home, case, out):
        want = case["expect"]
        if "error" in want:
            self.assertIn("Vault config error: ", out)
            self.assertIn(want["error"], out)
        else:
            self.assertNotIn("Vault config error", out)
        if "skipped" in want:
            self.assertIn(f"(skipped vault {want['skipped']}: no Tasks/ at ", out)
        if want["vault"] is None:
            self.assertNotIn("Vault:", out)
            return
        self.assertIn(f"Vault: {home}{want['vault'][1:]}\n", out)
        if want["slug"]:
            self.assertIn(f"Active task: {want['slug']} ({want['reason']}) — full note: ", out)
        else:
            self.assertIn("No active task", out)
        if "nameLine" in want:
            self.assertIn(want["nameLine"] + "\n", out)
        if case["config"] is None or "error" in want:
            self.assertNotIn("Vault name:", out)
```

- [ ] **Step 4: Run it and watch it fail**

Run: `python3 -m unittest tests.test_load_task.SharedVaultCasesTest -v`
Expected: FAIL. Most subtests fail on `Vault: …/work` or `(default)`, because today's hook knows only one vault. The first case ("no vaults.json") passes.

- [ ] **Step 5: Append the state and pick half to `plugins/tasks/hooks/vaults.py`**

```python
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
        override, override_mtime = session.read_text().strip(), session.stat().st_mtime
    active = tasks / ".active"
    state = State(vault, frozenset(p.stem for p in paths), tuple(notes), override, override_mtime,
                  active.read_text().strip() if active.is_file() else "")
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
            if not n.repo or n.status == "done":
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
```

- [ ] **Step 6: Write `plugins/tasks/hooks/session_task.py`**

```python
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
import sys
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
            return vaults.Pick(v, active.read_text().strip() if active.is_file() else "", why)
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
        picked = fallback(config, usable, f"global (resolver error: {type(e).__name__}: {e})")
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
    return out + sections(note.read_text())


if __name__ == "__main__":
    try:
        lines = main()
    except Exception as e:  # last resort: the time is already printed, say why nothing else is
        lines = [f"Task resolver failed: {type(e).__name__}: {e}"]
    if lines:
        print("\n".join(lines))
```

- [ ] **Step 7: Replace `plugins/tasks/hooks/load-task.sh` with the hand-off**

```bash
#!/usr/bin/env bash
# tasks plugin SessionStart hook: inject time + this session's vault, task and its Next/Open loops.
# session_task.py picks the vault and task (vaults.json, see vaults.py). Without python3: the single
# vault from the vaultPath option / $VAULT / ~/vault, and its Tasks/.active.
echo "Now: $(date '+%a %Y-%m-%d %H:%M')"
# The hook's JSON arrives on stdin; run by hand in a terminal there is none, so don't wait for it.
input=""
[ -t 0 ] || input=$(cat)
if command -v python3 >/dev/null; then
  HOOK_INPUT="$input" exec python3 "$(dirname "$0")/session_task.py"
fi
VAULT="${CLAUDE_PLUGIN_OPTION_VAULTPATH:-${VAULT:-$HOME/vault}}"
case "$VAULT" in "~") VAULT=$HOME ;; "~/"*) VAULT="$HOME/${VAULT#\~/}" ;; esac
NOTES="$VAULT/Tasks"
# No vault here (e.g. Cowork without the folder connected): the time is all there is to say.
[ -d "$NOTES" ] || exit 0
echo "Vault: $VAULT"
slug="$(tr -d '[:space:]' < "$NOTES/.active" 2>/dev/null)"
[ -n "$slug" ] || { echo "No active task. Ask Q what we're working on, or suggest /tasks:task-start."; exit 0; }
f="$NOTES/$slug.md"
[ -f "$f" ] || { echo "Active task '$slug' (global (python3 missing)) has no note at $f."; exit 0; }
echo "Active task: $slug (global (python3 missing)) — full note: $f"
awk '/^## (Goal|Next|Open loops)/{p=1;print;next} /^## /{p=0} p && !/^[[:space:]]*- (\[.\] )?~~/' "$f" | head -40
```

- [ ] **Step 8: Run every hook test: the old ones (regression) and the shared cases**

Run: `python3 -m unittest tests.test_load_task -v`
Expected: all 16 tests OK (15 existing plus `test_every_shared_case`). If an existing test fails, the hand-off changed today's behaviour: fix `session_task.py` and never the test.

- [ ] **Step 9: Run the hook by hand once, as Q's session would**

Run: `echo '{"session_id":"x","cwd":"'"$PWD"'"}' | bash plugins/tasks/hooks/load-task.sh`
Expected: `Now: …`, then `Vault: ~/vault` and `Active task: …`, the same as this session's start. Q has no `vaults.json` yet, so there is no `Vault name:` line.

- [ ] **Step 10: Commit**

```bash
git add plugins/tasks/hooks/vaults.py plugins/tasks/hooks/session_task.py plugins/tasks/hooks/load-task.sh \
  plugins/task-track/tests/fixtures/vault-case.ts plugins/task-track/tests/fixtures/vault-cases.ts tests/test_load_task.py
git commit -m "feat(tasks): SessionStart picks the session's vault across registered vaults"
```

---

### Task 3: `vault-allow.py` approves inside any one registered vault

**Files:**
- Modify: `plugins/tasks/hooks/vault-allow.py:1-8` (docstring), `:27-30` (`vault_root`), `:60-73` (`main`)
- Test: `tests/test_vault_allow.py` (append tests; the existing ones stay)

**Interfaces:**
- Consumes: `vaults.load_config(env, home) -> Config` (Task 1).

- [ ] **Step 1: Write the failing tests**

Append inside `class VaultAllowTest`, after `test_missing_vault_or_bad_json_does_nothing`:

```python
    def two_vaults(self, work_path=None):
        work = work_path or self.home / "work"
        (work / "Tasks").mkdir(parents=True, exist_ok=True)
        cfg = self.home / "vaults.json"
        cfg.write_text(json.dumps({"default": "personal", "vaults": {
            "personal": {"path": str(self.vault)}, "work": {"path": str(work)}}}))
        return work, {"ADHD_PLANNER_VAULTS": str(cfg)}

    def test_a_path_in_the_second_vault_adds_that_vault(self):
        work, env = self.two_vaults()
        result = self.ask("Read", {"file_path": str(work / "Tasks" / "w.md")}, env_extra=env)
        self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [str(work)])
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "a.md")}, env_extra=env))

    def test_a_search_spanning_two_vaults_is_left_to_the_user(self):
        _, env = self.two_vaults()
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.home)}, env_extra=env))

    def test_symlinked_second_vault_is_resolved(self):
        real = self.home / "icloud" / "work"
        (real / "Tasks").mkdir(parents=True)
        os.symlink(real, self.home / "w")
        _, env = self.two_vaults(work_path=self.home / "w")
        result = self.ask("Read", {"file_path": str(real / "x.md")}, env_extra=env)
        self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [str(real)])

    def test_a_broken_config_uses_only_the_single_vault(self):
        cfg = self.home / "vaults.json"
        cfg.write_text("{not json")
        (self.home / "work" / "Tasks").mkdir(parents=True)
        env = {"ADHD_PLANNER_VAULTS": str(cfg)}
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "a.md")}, env_extra=env))
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "work" / "a.md")}, env_extra=env))
```

`self.two_vaults(work_path=self.home / "w")` creates `w/Tasks` through the symlink. That is fine: `real/Tasks` already exists, and `exist_ok=True` covers it.

- [ ] **Step 2: Run them and watch them fail**

Run: `python3 -m unittest tests.test_vault_allow -v`
Expected: `test_a_path_in_the_second_vault_adds_that_vault` and `test_symlinked_second_vault_is_resolved` FAIL (`TypeError: 'NoneType' object is not subscriptable`). The other two already pass. The existing 15 pass.

- [ ] **Step 3: Implement**

Replace the docstring's second paragraph (lines 2-7) with:

```python
"""tasks plugin PermissionRequest hook: approve file tools whose every path is inside one vault.

Vaults: the ones registered in vaults.json (see vaults.py), else CLAUDE_PLUGIN_OPTION_VAULTPATH,
$VAULT or ~/vault; symlinks resolved. Approves for this session only and adds that one vault as a
working directory. Anything else — Bash, other tools, a path outside, paths spanning two vaults,
no vault, unreadable input — prints nothing, so the normal permission prompt appears. Always exits 0.
"""
```

Add `import vaults` after `import sys`. (The hook runs as a script, so `sys.path[0]` is `hooks/`.)

Replace `vault_root()` with:

```python
def vault_roots():
    """Every registered vault that exists, symlinks resolved, deepest first (a vault nested in another wins)."""
    config = vaults.load_config(os.environ, os.path.expanduser("~"))
    roots = {os.path.realpath(v.path) for v in config.vaults}
    return sorted((r for r in roots if os.path.isdir(r)), key=len, reverse=True)
```

In `main()`, replace

```python
    root = vault_root()
    if root is None:
        return
```

with

```python
    roots = vault_roots()
    if not roots:
        return
```

and replace

```python
    if not paths or not all(inside(p, root) for p in paths):
        return
```

with

```python
    root = next((r for r in roots if paths and all(inside(p, r) for p in paths)), None)
    if root is None:
        return
```

- [ ] **Step 4: Run them and watch them pass**

Run: `python3 -m unittest tests.test_vault_allow -v`
Expected: 19 tests OK.

- [ ] **Step 5: Commit**

```bash
git add plugins/tasks/hooks/vault-allow.py tests/test_vault_allow.py
git commit -m "feat(tasks): vault-allow approves inside any one registered vault"
```

---
### Task 4: The mod's resolver (`resolve.ts`) runs the shared cases

**Files:**
- Modify: `plugins/task-track/hooks/resolve.ts` (append; `pickTask` stays, since its existing tests guard it)
- Test: `plugins/task-track/tests/task-track.test.ts` (append one `describe` block; change the import lines 9-10)

**Interfaces:**
- Consumes: `normalize`, `isWithin`, `Candidate` (already in `resolve.ts`), and the fixtures from Task 2.
- Produces (used by Task 5):
  - `type VaultSpec = { name: string; path: string; folders: readonly { written: string; root: string }[] }`
  - `type VaultConfig = { default: string; vaults: readonly VaultSpec[]; isImplicit: boolean; error: string }`
  - `type VaultState = { vault: VaultSpec; candidates: readonly Candidate[]; override: string; overrideMtimeMs: number; global: string }`
  - `type VaultPick = { vault: VaultSpec; slug: string; reason: string }`
  - `implicitVault(fallback: string, home: string, error?: string): VaultConfig`
  - `parseVaults(text: string, where: string, fallback: string, home: string): VaultConfig`
  - `defaultVault(config: VaultConfig): VaultSpec` (throws when the invariant breaks)
  - `pickVault(input: { config: VaultConfig; states: readonly VaultState[]; dir: string; home: string }): VaultPick | null`

- [ ] **Step 1: Write the failing test**

Replace lines 9-10 of `plugins/task-track/tests/task-track.test.ts`:

```ts
import { frontmatter, implicitVault, normalize, parseVaults, pickTask, pickVault } from '../hooks/resolve'
import type { Candidate, VaultState } from '../hooks/resolve'
import { CASES } from './fixtures/vault-cases'
import type { VaultCase } from './fixtures/vault-case'
```

Append at the end of the file:

```ts
describe('shared vault cases (tests/test_load_task.py runs the same ones)', () => {
  const HOME = '/home/q'
  function input(k: VaultCase) {
    const config =
      k.config === null
        ? implicitVault('~/vault', HOME)
        : parseVaults(typeof k.config === 'string' ? k.config : JSON.stringify(k.config), 'vaults.json', '~/vault', HOME)
    const states: VaultState[] = config.vaults.flatMap(v => {
      const dir = Object.entries(k.vaults).find(([rel]) => normalize(`~/${rel}`, HOME) === v.path)?.[1]
      if (!dir) return []
      const candidates = Object.entries(dir.notes ?? {}).map(([slug, n]) => ({
        slug,
        repo: n.repo ?? '',
        status: n.status ?? 'active',
        mtimeMs: (n.mtime ?? 0) * 1000,
      }))
      return [{ vault: v, candidates, override: dir.session?.slug ?? '', overrideMtimeMs: (dir.session?.mtime ?? 0) * 1000, global: dir.active ?? '' }]
    })
    return { config, states, dir: normalize(k.cwd, HOME), home: HOME }
  }

  test('there are enough cases to mean something', () => {
    expect(CASES.length).toBeGreaterThan(15)
  })

  for (const k of CASES) {
    test(k.name, () => {
      const args = input(k)
      if (k.expect.error) expect(args.config.error).toContain(k.expect.error)
      else expect(args.config.error).toBe('')
      const picked = pickVault(args)
      if (k.expect.vault === null) {
        expect(picked).toBeNull()
        return
      }
      expect(picked?.vault.path).toBe(normalize(k.expect.vault, HOME))
      expect(picked?.slug).toBe(k.expect.slug)
      expect(picked?.reason).toBe(k.expect.reason)
    })
  }
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd plugins/task-track && claude plugin test .`
Expected: the test file does not load, failing with `implicitVault` / `parseVaults` / `pickVault` not exported. 0 new passes.

- [ ] **Step 3: Implement (append to `plugins/task-track/hooks/resolve.ts`)**

```ts
// ── several vaults: mirrors plugins/tasks/hooks/vaults.py; both run tests/fixtures/vault-cases.ts ──

export type VaultSpec = { name: string; path: string; folders: readonly { written: string; root: string }[] }
export type VaultConfig = { default: string; vaults: readonly VaultSpec[]; isImplicit: boolean; error: string }
export type VaultState = { vault: VaultSpec; candidates: readonly Candidate[]; override: string; overrideMtimeMs: number; global: string }
export type VaultPick = { vault: VaultSpec; slug: string; reason: string }

const VAULT_NAME = /^[a-z0-9][a-z0-9-]*$/

/** No vaults.json, or a broken one: the single vault from the plugin option, $VAULT or ~/vault. */
export function implicitVault(fallback: string, home: string, error = ''): VaultConfig {
  return { default: 'default', vaults: [{ name: 'default', path: normalize(fallback, home), folders: [] }], isImplicit: true, error }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** vaults.json text → config; any problem → the implicit vault, with `error` naming the file and what is wrong. */
export function parseVaults(text: string, where: string, fallback: string, home: string): VaultConfig {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch (err) {
    return implicitVault(fallback, home, `${where}: not valid JSON (${err instanceof Error ? err.message : String(err)})`)
  }
  const parsed = vaultsFrom(data, home)
  return typeof parsed === 'string' ? implicitVault(fallback, home, `${where}: ${parsed}`) : parsed
}

/** The config, or what is wrong with it (same words as vaults.py). */
function vaultsFrom(data: unknown, home: string): VaultConfig | string {
  if (!isRecord(data) || !isRecord(data.vaults) || Object.keys(data.vaults).length === 0) {
    return 'expected {"vaults": {"<name>": {"path": "..."}}} with at least one vault'
  }
  const vaults: VaultSpec[] = []
  const owner = new Map<string, string>()
  for (const [name, spec] of Object.entries(data.vaults)) {
    if (!VAULT_NAME.test(name)) return `vault name '${name}' must be kebab-case (a-z, 0-9, -)`
    const path = isRecord(spec) ? spec.path : undefined
    if (typeof path !== 'string' || path.trim() === '') return `vault '${name}' has no "path"`
    const folders: unknown = isRecord(spec) ? (spec.folders ?? []) : []
    if (!Array.isArray(folders) || !folders.every((f): f is string => typeof f === 'string' && f.trim() !== '')) {
      return `vault '${name}': "folders" must be a list of paths`
    }
    const pairs: { written: string; root: string }[] = []
    for (const written of folders) {
      const root = normalize(written, home)
      const other = owner.get(root)
      if (other !== undefined && other !== name) return `folder '${written}' is listed by both '${other}' and '${name}'`
      owner.set(root, name)
      pairs.push({ written, root })
    }
    vaults.push({ name, path: normalize(path.trim(), home), folders: pairs })
  }
  const names = vaults.map(v => v.name)
  const chosen = data.default ?? (names.length === 1 ? names[0] : undefined)
  if (chosen === undefined) return `"default" is required with ${names.length} vaults`
  if (typeof chosen !== 'string' || !names.includes(chosen)) return `"default" is '${String(chosen)}', not one of: ${names.join(', ')}`
  return { default: chosen, vaults, isImplicit: false, error: '' }
}

/** The default vault; parseVaults and implicitVault guarantee it exists. */
export function defaultVault(config: VaultConfig): VaultSpec {
  const v = config.vaults.find(x => x.name === config.default)
  if (!v) throw new Error(`vault config: default '${config.default}' is not among: ${config.vaults.map(x => x.name).join(', ')}`)
  return v
}

/**
 * Session override (newest across vaults) → a repo note in any vault (deepest, then active, then
 * newest; done never binds) → the deepest bound folder (its vault's .active) → the default
 * vault's .active. `states` holds only vaults that have Tasks/; null when none of them answers.
 */
export function pickVault(input: { config: VaultConfig; states: readonly VaultState[]; dir: string; home: string }): VaultPick | null {
  const { config, states, home } = input
  const dir = normalize(input.dir, home)
  const over = states
    .filter(s => s.override !== '' && s.candidates.some(c => c.slug === s.override))
    .sort((a, b) => b.overrideMtimeMs - a.overrideMtimeMs)[0]
  if (over) return { vault: over.vault, slug: over.override, reason: 'this session' }
  const best = states
    .flatMap(s => s.candidates.filter(c => c.repo !== '' && c.status !== 'done').map(c => ({ s, c, root: normalize(c.repo, home) })))
    .filter(x => isWithin(dir, x.root))
    .sort(
      (a, b) =>
        b.root.length - a.root.length ||
        Number(b.c.status === 'active') - Number(a.c.status === 'active') ||
        b.c.mtimeMs - a.c.mtimeMs,
    )[0]
  if (best) return { vault: best.s.vault, slug: best.c.slug, reason: `project: ${best.root.split('/').pop()}` }
  const folder = states
    .flatMap(s => s.vault.folders.filter(f => isWithin(dir, f.root)).map(f => ({ s, f })))
    .sort((a, b) => b.f.root.length - a.f.root.length)[0]
  if (folder) return { vault: folder.s.vault, slug: folder.s.global, reason: `folder ${folder.f.written}` }
  const byDefault = states.find(s => s.vault.name === config.default)
  return byDefault ? { vault: byDefault.vault, slug: byDefault.global, reason: config.isImplicit ? 'global' : 'default' } : null
}
```

- [ ] **Step 4: Run them and watch them pass**

Run: `cd plugins/task-track && claude plugin test .`
Expected: 98 existing plus 1 count test plus 21 shared cases = 120 pass, 0 fail.

- [ ] **Step 5: Run the Python side too, to confirm the two still agree on the same file**

Run: `python3 -m unittest tests.test_load_task.SharedVaultCasesTest -v`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add plugins/task-track/hooks/resolve.ts plugins/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): pickVault mirrors the hook's vault resolution"
```

---

### Task 5: Mod wiring (`register.tsx`): one vault per load, its timer, its prefix

**Files:**
- Modify: `plugins/task-track/hooks/register.tsx`, at these anchors:
  - imports, line 28
  - atoms, lines 33-43
  - `let vault`, line 65
  - `resolveVault`, lines 85-91
  - `candidates`, lines 94-118
  - `load`, lines 124-166
  - every `resolveVault($)` call: lines 201, 262, 275, 281, 394, 432
  - band, line 663
  - pane, lines 698-705 and 760-766
  - pane title, line 465
- Modify: `plugins/task-track/types/index.d.ts:63-79` (`PluginState`)
- Test: `plugins/task-track/tests/task-track.test.ts` (append one `describe`)

**Interfaces:**
- Consumes (from Task 4): `implicitVault`, `parseVaults`, `defaultVault`, `pickVault`, `VaultConfig`, `VaultSpec`, `VaultState`.
- Produces: atoms `vaultName: string` ('' with a single vault) and `configError: string`.

- [ ] **Step 1: Write the failing tests**

Append to `plugins/task-track/tests/task-track.test.ts`:

```ts
describe('several vaults', () => {
  const CONFIG = '/home/q/.config/adhd-planner/vaults.json'
  const TWO = JSON.stringify({ default: 'personal', vaults: { personal: { path: '/v' }, work: { path: '/w', folders: ['~/acme'] } } })
  const WORK = NOTE.replace('# Set up vault', '# Deploy fix')
  const files = () => ({
    [CONFIG]: TWO,
    '/v/Tasks/.active': 'set-up-vault\n',
    [PATH]: NOTE,
    '/w/Tasks/.active': 'deploy-fix\n',
    '/w/Tasks/deploy-fix.md': WORK,
  })

  test('a session in a bound folder shows the work task, prefixed with its vault', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    fakeVault(on, files(), { root: '/home/q/acme/api' })
    expect((await run($, 'note', 'x')).text).toBe('Logged to deploy-fix.')
    const band = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
    expect(await band.find({ type: 'Text', text: /▶ work · deploy-fix/ })).toBeDefined()
    const pane = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'Pane', requestId: 'task-track', props: {} as never })
    expect(await pane.find({ type: 'Text', text: /work · folder ~\/acme/ })).toBeDefined()
  })

  test('with no vaults.json the band has no vault prefix', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE })
    await run($, 'note', 'x')
    const band = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
    expect(await band.find({ type: 'Text', text: /^▶ set-up-vault$/ })).toBeDefined()
  })

  test('each vault keeps its own timer', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: T0 })
    const written = fakeVault(on, files(), { root: '/home/q/acme/api' })
    await run($, 'openloop', 'load the task')
    await run($, 'note', 'activity')
    expect(parsePomo(written['/w/Tasks/.pomo.json'] ?? '')?.lastActiveAt).toBe(T0)
    expect(written['/v/Tasks/.pomo.json']).toBeUndefined()
  })

  test('a switch to a task in another vault credits the old task on the old vault\'s timer', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: T0 })
    const held = { ...emptyPomo('2026-10-13'), slug: 'set-up-vault', dayMs: { 'set-up-vault': 10 * MIN } }
    const written = fakeVault(on, { ...files(), '/v/Tasks/.pomo.json': serializePomo(held) }, { id: 's1', root: '/home/q/elsewhere' })
    expect((await run($, 'note', 'x')).text).toBe('Logged to set-up-vault.')
    written['/w/Tasks/.session/s1'] = 'deploy-fix\n'
    expect((await run($, 'note', 'y')).text).toBe('Logged to deploy-fix.')
    expect(written[PATH]).toMatch(/— focus /)
    expect(written['/w/Tasks/deploy-fix.md']).not.toMatch(/— focus /)
    expect(unlogged(parsePomo(written['/v/Tasks/.pomo.json'] ?? '') ?? emptyPomo(''), 'set-up-vault').ms).toBe(0)
  })

  test('the same slug in two vaults keeps each vault\'s own frontmatter', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    const bound = NOTE.replace('status: active\n', 'status: active\nrepo: ~/code/app\n')
    fakeVault(on, {
      [CONFIG]: TWO,
      '/v/Tasks/.active': 'other\n',
      '/v/Tasks/other.md': NOTE,
      [PATH]: NOTE,
      '/w/Tasks/set-up-vault.md': bound,
    }, { root: '/home/q/code/app' })
    expect((await run($, 'note', 'x')).text).toBe('Logged to set-up-vault.')
    const pane = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'Pane', requestId: 'task-track', props: {} as never })
    expect(await pane.find({ type: 'Text', text: /work · project: app/ })).toBeDefined()
  })

  test('a broken vaults.json is named in the pane and the single vault still works', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    fakeVault(on, { ...files(), [CONFIG]: '{not json' }, { root: '/home/q/acme/api' })
    expect((await run($, 'note', 'x')).text).toBe('Logged to set-up-vault.')
    const pane = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'Pane', requestId: 'task-track', props: {} as never })
    expect(await pane.find({ type: 'Text', text: /Vault config error: .*vaults\.json: not valid JSON/ })).toBeDefined()
  })
})
```

Add `unlogged` to the `../hooks/pomo` import on line 6 if it is not already there. (It is, as of `0affff0`.)

- [ ] **Step 2: Run them and watch them fail**

Run: `cd plugins/task-track && claude plugin test .`
Expected: 5 of the 6 new tests FAIL, for example `Logged to set-up-vault.` received where `deploy-fix` was expected. "with no vaults.json the band has no vault prefix" may already pass. The other 120 pass.

- [ ] **Step 3: Add the atoms to `types/index.d.ts`**

Inside `'task-track': { … }`, after `source: string`, add:

```ts
      /** The session's vault name while 2+ vaults are registered; '' with one, so nothing is prefixed. */
      vaultName: string
      /** Why vaults.json was ignored (shown in the pane); '' when it was used or absent. */
      configError: string
```

and change the `source` doc comment to say `this session`, `project: <folder>`, `folder <path>`, `default` or `global`.

- [ ] **Step 4: Wire `register.tsx`**

1. Line 28 import becomes:
   ```ts
   import { defaultVault, frontmatter, implicitVault, parseVaults, pickVault } from './resolve'
   ```
   and line 31 becomes:
   ```ts
   import type { Candidate, VaultConfig, VaultSpec, VaultState } from './resolve'
   ```
   `normalize` and `pickTask` are no longer used in `register.tsx`. Check with `grep -n "normalize\|pickTask" plugins/task-track/hooks/register.tsx` and drop them from the import.
2. After the `source` atom (line 40), add:
   ```ts
   const vaultName = atom({ plugin: 'task-track', key: 'vaultName' } as const, '')
   const configError = atom({ plugin: 'task-track', key: 'configError' } as const, '')
   ```
3. Above `let vault = ''`, add the comment `/** The vault this session resolved to on its last load; '' until the first load. */`.
4. Replace `resolveVault` (lines 85-91) with:
   ```ts
   /** vaults.json, read on every load so an edit applies without a restart; the implicit vault without one. */
   async function vaultConfig($: EngineInterface, home: string): Promise<VaultConfig> {
     const fallback = settings.vaultPath || (await $.env.get('VAULT')) || `${home}/vault`
     const path = (await $.env.get('ADHD_PLANNER_VAULTS')) || `${home}/.config/adhd-planner/vaults.json`
     if (!(await $.fs.exists(path))) return implicitVault(fallback, home)
     const text = await $.fs.read(path).catch((err: unknown) => new Error(err instanceof Error ? err.message : String(err)))
     return text instanceof Error ? implicitVault(fallback, home, `${path}: ${text.message}`) : parseVaults(text, path, fallback, home)
   }

   /** The vault this session resolved to on its last load; loads once if nothing has yet. */
   async function currentVault($: EngineInterface): Promise<string> {
     if (!vault) await load($)
     return vault
   }

   /** One vault's notes and pointer files; null when it has no Tasks/ (not mounted, not a vault). */
   async function vaultState($: EngineInterface, v: VaultSpec, sessionId: string): Promise<VaultState | null> {
     if (!(await $.fs.exists(`${v.path}/Tasks`))) return null
     const sessionFile = `${v.path}/Tasks/.session/${sessionId}`
     const [found, override, global] = await Promise.all([
       candidates($, v.path),
       readIfExists($, sessionFile),
       readIfExists($, `${v.path}/Tasks/.active`),
     ])
     const overrideMtimeMs = override ? (await $.fs.stat(sessionFile)).mtimeMs : 0
     return { vault: v, candidates: found, override, overrideMtimeMs, global }
   }
   ```
5. In `candidates()`, key the cache by path, since slugs repeat across vaults. Move `const path = \`${dir}/${entry.name}\`` above `let c`, and make it `let c = noteCache.get(path)` and `noteCache.set(path, c)`. Change the `noteCache` doc comment to "by note path".
6. Replace the top of `load()`, from `const root = await resolveVault($)` through the `if (prev && prev.slug !== slug) await flushFocus(...)` and the `logCount` check, with:
   ```ts
   async function load($: EngineInterface): Promise<TaskView | null> {
     const home = (await $.env.get('HOME')) ?? ''
     const config = await vaultConfig($, home)
     const [sessionId, dir] = await Promise.all([$.session.id(), $.session.root()])
     const states = (await Promise.all(config.vaults.map(v => vaultState($, v, sessionId)))).filter((s): s is VaultState => s !== null)
     const picked = pickVault({ config, states, dir, home })
     const root = picked?.vault.path ?? defaultVault(config).path
     const prev = await read($, task)
     // Credit the old task on the old vault's timer before this session moves to the new vault's.
     const isVaultChange = vault !== '' && root !== vault
     if (prev && isVaultChange) await flushFocus($, prev.slug, prev.path)
     vault = root
     await update($, source, () => picked?.reason ?? 'global')
     await update($, vaultName, () => (config.vaults.length > 1 && picked ? picked.vault.name : ''))
     await update($, configError, () => config.error)
     await refreshPomo($)
     const slug = picked?.slug ?? ''
     if (!slug) {
       if (prev && !isVaultChange) await flushFocus($, prev.slug, prev.path)
       const hasVault = await $.fs.exists(root)
       await update($, task, () => null)
       await update($, problem, () => (hasVault ? '' : `No vault at ${root}`))
       return null
     }
     const path = `${root}/Tasks/${slug}.md`
     const stat = await $.fs.stat(path).catch(() => undefined)
     if (!stat) {
       await update($, problem, () => `Active task "${slug}" has no note at ${path}`)
       return prev
     }
     if (prev && prev.path === path && prev.mtimeMs === stat.mtimeMs) return prev
     const view = parseNote(slug, path, await $.fs.read(path), stat.mtimeMs)
     if (prev && prev.path !== path && !isVaultChange) await flushFocus($, prev.slug, prev.path)
     if (view.logCount !== logSize || prev?.path !== path) {
   ```
   Everything after that `if (` line stays as it is.
7. Replace the six `await resolveVault($)` calls (lines 201, 262, 275, 281, 394, 432) with `await currentVault($)`. Then `grep -n resolveVault plugins/task-track/hooks/register.tsx` must print nothing.
8. Band (line 663): above the band's `return (`, add `const prefix = await read($, vaultName)`, then change `<Text bold color="claude">▶ {view.slug}</Text>` to:
   ```tsx
   <Text bold color="claude">▶ {prefix ? `${prefix} · ` : ''}{view.slug}</Text>
   ```
9. Pane title (line 465): `` title: view ? `Task · ${view.slug}` : 'Task' `` becomes
   ```ts
   title: view ? `Task · ${prefix ? `${prefix} · ` : ''}${view.slug}` : 'Task',
   ```
   with `const prefix = await read($, vaultName)` on the line above the `$.ui.open` call.
10. Pane, task branch (line ~765): `<Text color="subtle"> · {why}</Text>` becomes
    ```tsx
    <Text color="subtle"> · {vaultLabel ? `${vaultLabel} · ` : ''}{why}</Text>
    ```
    with `const vaultLabel = await read($, vaultName)` and `const configErr = await read($, configError)` next to `const why = await read($, source)`. Then, right after the `</Text>` closing that subtitle row and before `</Box>`, add:
    ```tsx
    {configErr ? <Text color="subtle" wrap="truncate-end">Vault config error: {configErr}</Text> : null}
    ```
11. Pane, no-task branch (lines 700-705): read `configError` the same way, and add the same line under `<Text>{why || 'No active task.'}</Text>`.

- [ ] **Step 5: Run the whole mod suite**

Run: `cd plugins/task-track && claude plugin test .`
Expected: 126 pass, 0 fail.

If an existing test fails, read it before touching anything. Each one encodes today's single-vault behaviour, which must not change.

A likely candidate: a test whose `fs.exists` mock answers only specific paths, so it would now get asked about `/home/q/.config/adhd-planner/vaults.json` too. That calls for fixing the wiring, not the test. If it truly cannot be fixed without editing the test, stop and tell Q, per RULE 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/task-track/hooks/register.tsx plugins/task-track/types/index.d.ts plugins/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): follow the session's vault: its timer, its prefix, focus on switch"
```

---
### Task 6: Skills and docs speak several vaults

Skills are prose, so this task has no unit tests. Its check is a grep for stale wording plus the manual smoke test in Task 8.

**Files:**
- Modify: `plugins/tasks/skills/{task-switch,task-start,task-park,task-note,obsidian-vault}/SKILL.md`
- Modify: `plugins/planner/skills/{break-down-task,capture-triage,eod-shutdown,morning-startup,plan-day,plan-week}/SKILL.md` (the "Find it once" bullet), `plugins/planner/skills/setup/SKILL.md` (step 8)
- Modify: `plugins/task-track/README.md`, `plugins/planner/README.md`, `docs/setup.md`, `plugins/tasks/.claude-plugin/plugin.json` and `plugins/task-track/.claude-plugin/plugin.json` (the `vaultPath` description)

**Interfaces:**
- Consumes: the SessionStart lines from Task 2 (`Vault: <path>`, `Vault name: <name> (<reason>) · others: a, b`) and the `vaults.json` schema from Task 1.

- [ ] **Step 1: The shared vault paragraph**

In `task-switch`, `task-start` and `task-park`, replace the paragraph beginning `The vault root is the path on the session-start `Vault:` line` with:

```markdown
The vault root is the path on the session-start `Vault:` line; without that line, the `default` vault in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`), else `$VAULT`, else `~/vault`. Every `~/vault` path below means that root. When `vaults.json` registers several vaults (the `Vault name:` line lists the others), `<vault>:<slug>` names a task in another vault, and `<vault>` is that vault's `path` from `vaults.json`.
```

- [ ] **Step 2: `task-switch` steps**

Replace step 1 with:

```markdown
1. No argument → list notes with `status: active` or `parked` in every vault's `Tasks/` (the current one, plus each vault in `vaults.json` whose path has `Tasks/`), max 5 overall, most recent first, each as `<vault>:<slug>` (plain `<slug>` when only one vault is registered), and ask which.
```

In step 3, append: `` A `<vault>:` prefix looks only in that vault; without one, look in the current vault first, then the others (several matches → list them and ask). ``

Replace step 4's first sentence with:

```markdown
4. Set target `status: active`; write its slug to `<target vault>/Tasks/.active` and to `<target vault>/Tasks/.session/$CLAUDE_CODE_SESSION_ID` (create `.session/`). If the target is in another vault than the current one, delete `<current vault>/Tasks/.session/$CLAUDE_CODE_SESSION_ID`, so the older override cannot win. If `CLAUDE_CODE_SESSION_ID` is empty, write only `.active` and say the choice applies to every session.
```

In step 5, append: `` When the vault changed, add `Vault now: <name> (<path>).` and use that path as the vault root for the rest of this session. ``

- [ ] **Step 3: `task-start`, `task-park`, `task-note`**

- `task-start` step 1: prefix it with `` An argument `<vault>:<slug>` creates the note in that vault; otherwise in the current vault. `` Step 8: append `` With several vaults registered, start the reply with `<vault>:`. ``
- `task-park` step 1: replace `Read `~/vault/Tasks/.active`` with `` Take the task from the session-start `Active task:` line (its `full note:` path), else read `~/vault/Tasks/.active` ``.
- `task-note`, under "Find the vault": insert as the new step 2, and renumber the rest:
  ```markdown
  2. The `default` vault's `path` in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`), when that file exists and parses.
  ```
  Then change the "list open tasks" row to: `` Every `Tasks/*.md` whose `status` is not `done`, in every vault `vaults.json` registers that has `Tasks/` (or the one vault): `<vault>:slug — status — first open Next item` (plain `slug` with one vault). `` Then add under "Pick the task": `` `<vault>:<slug>` → that vault's `Tasks/<slug>.md`. ``

- [ ] **Step 4: `obsidian-vault` and the planner skills**

- `obsidian-vault` line 8: replace the sentence with `` The vault is the path on the session-start `Vault:` line; without that line, the `default` vault in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`), else `$VAULT`, else `~/vault`. Every `~/vault` path in these skills means that root. With several vaults, read and write only that one; never link across vaults (a `[[link]]` resolves only inside its own vault). ``
- In each of the six planner skills with a **Find it once** bullet, replace its first sentence (up to `whichever the shell can see.`) with:
  ```markdown
  - **Find it once:** the session-start `Vault:` line, else a connected folder named `vault` (`~/mnt/vault` in the device shell), else the `default` vault's `path` in `~/.config/adhd-planner/vaults.json`, else `$VAULT`, else `~/vault`, whichever the shell can see. Only that one vault is read or written, even when several are registered.
  ```
  Keep the rest of the bullet (`It counts only if it has …`).
- `planner/skills/setup/SKILL.md` step 8: after `else `$VAULT`, else `~/vault`,` insert `` (or, when `~/.config/adhd-planner/vaults.json` exists, each vault it lists — report each as found or missing `Tasks/`) ``.

- [ ] **Step 5: Docs and option descriptions**

- Both `plugin.json` `vaultPath` descriptions become: `"Absolute path to the Obsidian vault, used when ~/.config/adhd-planner/vaults.json does not exist. Empty: $VAULT, else ~/vault."`
- `plugins/task-track/README.md`, in the options table: the `vaultPath` row becomes `` empty → `$VAULT`, else `~/vault`; ignored when `vaults.json` exists ``. Then add a section after the timer section:
  ```markdown
  ## Several vaults

  With `~/.config/adhd-planner/vaults.json` (see `docs/setup.md`), each session follows its own vault: the band and pane prefix `<vault> · ` (only with 2+ vaults), and each vault keeps its own timer in its `Tasks/.pomo.json`. A `/tasks:task-switch` to a task in another vault writes the old task's focus to its note first.
  ```
- `plugins/planner/README.md`, in "Obsidian vault (optional)": after the first sentence, add `` With several vaults in `~/.config/adhd-planner/vaults.json`, the skills use the session's vault (the `Vault:` line) and only that one. ``
- `docs/setup.md`: add a section before "## What each plugin needs":
  ````markdown
  ## Several vaults

  One vault needs nothing here. For more, list them in `~/.config/adhd-planner/vaults.json` (or run `planner-setup add-vault`):

  ```json
  {
    "default": "personal",
    "vaults": {
      "personal": { "path": "~/vault" },
      "work":     { "path": "~/work-vault", "folders": ["~/acme"] }
    }
  }
  ```

  Each session gets one vault: the one `/tasks:task-switch` last chose for it, else the vault holding a task whose `repo:` contains the folder, else the vault whose `folders` holds it, else `default`. Each vault keeps its own active task and timer. `/tasks:task-switch work:<slug>` moves a session to another vault. A broken file is named at session start and ignored (the single-vault settings apply).
  ````

- [ ] **Step 6: Check for stale wording**

Run: `grep -rn 'else `\$VAULT`, else `~/vault`' plugins/*/skills | grep -v vaults.json`
Expected: no output. Every chain now mentions `vaults.json`.

Run: `cd plugins/tasks && claude plugin validate . && cd ../task-track && claude plugin validate . && cd ../planner && claude plugin validate .`
Expected: each prints valid, with no errors.

- [ ] **Step 7: Commit**

```bash
git add plugins/tasks/skills/task-switch/SKILL.md plugins/tasks/skills/task-start/SKILL.md plugins/tasks/skills/task-park/SKILL.md \
  plugins/tasks/skills/task-note/SKILL.md plugins/tasks/skills/obsidian-vault/SKILL.md \
  plugins/planner/skills/break-down-task/SKILL.md plugins/planner/skills/capture-triage/SKILL.md plugins/planner/skills/eod-shutdown/SKILL.md \
  plugins/planner/skills/morning-startup/SKILL.md plugins/planner/skills/plan-day/SKILL.md plugins/planner/skills/plan-week/SKILL.md \
  plugins/planner/skills/setup/SKILL.md plugins/task-track/README.md plugins/planner/README.md docs/setup.md \
  plugins/tasks/.claude-plugin/plugin.json plugins/task-track/.claude-plugin/plugin.json
git commit -m "docs: skills and setup docs for several vaults"
```

---

### Task 7: `planner-setup add-vault`

**Files:**
- Modify: `setup/src/planner_setup/paths.py` (add `vaults_file`, `tilde`), `setup/src/planner_setup/actions.py` (add `add_vault`; module docstring says "six things", which becomes "seven"), `setup/src/planner_setup/cli.py` (subcommand and menu item)
- Test: `setup/tests/test_actions.py`, `setup/tests/test_cli.py` (append)

**Interfaces:**
- Produces:
  - `paths.vaults_file(env: Mapping[str, str], home: Path) -> Path`
  - `paths.tilde(path: Path, home: Path) -> str`
  - `actions.add_vault(ctx: Ctx, name: str, path: Path, folders: Sequence[str], existing_name: str = "personal") -> int`
- Writes the schema from Task 1. It must parse with `vaults.parse`, and the test checks that it does.

- [ ] **Step 1: Write the failing tests**

Append to `setup/tests/test_actions.py`:

```python
def vaults_json(ctx):
    return ctx.home / ".config" / "adhd-planner" / "vaults.json"


def test_add_vault_creates_the_file_with_the_current_vault_as_default(ctx):
    work = ctx.home / "work-vault"
    (work / "Tasks").mkdir(parents=True)
    assert actions.add_vault(ctx, "work", work, ["~/acme"]) == 0
    assert json.loads(vaults_json(ctx).read_text()) == {
        "default": "personal",
        "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work-vault", "folders": ["~/acme"]}},
    }


def test_add_vault_merges_and_keeps_every_existing_entry(ctx):
    vaults_json(ctx).parent.mkdir(parents=True)
    vaults_json(ctx).write_text(json.dumps({"default": "home", "vaults": {"home": {"path": "~/vault"}, "side": {"path": "/s"}}}))
    assert actions.add_vault(ctx, "work", ctx.home / "w", []) == 0
    data = json.loads(vaults_json(ctx).read_text())
    assert data["default"] == "home"
    assert list(data["vaults"]) == ["home", "side", "work"]
    assert data["vaults"]["work"] == {"path": "~/w"}


def test_add_vault_refuses_a_taken_or_bad_name_and_changes_nothing(ctx):
    assert actions.add_vault(ctx, "Work", ctx.home / "w", []) == 2
    assert not vaults_json(ctx).exists()
    assert actions.add_vault(ctx, "personal", ctx.home / "w", []) == 1
    assert not vaults_json(ctx).exists()
    assert "already has a vault named 'personal'" in text(ctx)


def test_add_vault_dry_run_writes_nothing(ctx):
    assert actions.add_vault(replace(ctx, dry_run=True), "work", ctx.home / "w", []) == 0
    assert not vaults_json(ctx).exists()
    assert "Would write" in text(ctx)


def test_add_vault_warns_when_the_vault_has_no_tasks_folder(ctx):
    assert actions.add_vault(ctx, "work", ctx.home / "w", []) == 0
    assert "has no Tasks/ yet" in text(ctx)


def test_the_written_file_parses_with_the_hook_parser(ctx):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins" / "tasks" / "hooks"))
    import vaults
    actions.add_vault(ctx, "work", ctx.home / "w", ["~/acme"])
    config = vaults.parse(vaults_json(ctx).read_text(), "vaults.json", {}, str(ctx.home))
    assert config.error == ""
    assert [v.name for v in config.vaults] == ["personal", "work"]
```

Add `from pathlib import Path` to the test file's imports if it is missing.

Append to `setup/tests/test_cli.py`:

```python
def test_add_vault_subcommand(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    assert cli.main(["--yes", "add-vault", "work", "--path", str(tmp_path / "w"), "--folder", "~/acme"]) == 0
    data = json.loads((tmp_path / ".config" / "adhd-planner" / "vaults.json").read_text())
    assert data["vaults"]["work"] == {"path": "~/w", "folders": ["~/acme"]}
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd setup && uv run pytest -q tests/test_actions.py tests/test_cli.py`
Expected: 7 new tests FAIL (`AttributeError: module 'planner_setup.actions' has no attribute 'add_vault'`, or argparse `invalid choice: 'add-vault'`).

- [ ] **Step 3: Implement**

`setup/src/planner_setup/paths.py`, after `vault()`:

```python
def vaults_file(env: Mapping[str, str], home: Path) -> Path:
    """The vault registry the hooks and the mod read (plugins/tasks/hooks/vaults.py)."""
    raw = env.get("ADHD_PLANNER_VAULTS")
    return Path(raw) if raw else home / ".config" / "adhd-planner" / "vaults.json"


def tilde(path: Path, home: Path) -> str:
    """`path` with `~` for home, the way vaults.json and `repo:` write paths."""
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)
```

`setup/src/planner_setup/actions.py`: add `import re` with the imports, `VAULT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")` under them, and this function after `seed_vault`:

```python
def add_vault(ctx: Ctx, name: str, path: Path, folders: Sequence[str], existing_name: str = "personal") -> int:
    """Registers another vault in vaults.json. The first time, today's vault goes in too, as the default."""
    for n in (name, existing_name):
        if not VAULT_NAME.match(n):
            ctx.say(f"Vault name {n!r} must be kebab-case (a-z, 0-9, -); nothing was changed.")
            return 2
    target = paths.vaults_file(ctx.env, ctx.home)
    current = files.load_json(target)
    vaults = dict(current.get("vaults") or {})
    if not vaults:
        vaults[existing_name] = {"path": paths.tilde(paths.vault(ctx.env, ctx.home), ctx.home)}
        current["default"] = existing_name
    if name in vaults:
        ctx.say(f"{target} already has a vault named {name!r} ({vaults[name].get('path')}); nothing was changed.")
        return 1
    entry: dict = {"path": paths.tilde(path, ctx.home)}
    if folders:
        entry["folders"] = list(folders)
    merged = {**current, "vaults": {**vaults, name: entry}}
    if not (path / "Tasks").is_dir():
        ctx.say(f"{path} has no Tasks/ yet: sessions skip this vault until it has one.")
    ctx.say(("Would write " if ctx.dry_run else "Will write ") + f"{target}:\n{json.dumps(merged, indent=2)}")
    if ctx.dry_run:
        return 0
    if not (ctx.yes or ctx.confirm("Write it?")):
        return 1
    files.write_json(target, merged, files.backup_dir(ctx.home), home=ctx.home)
    ctx.say(f"Wrote {target}. New sessions see vault {name!r}; /tasks:task-switch {name}:<slug> moves a session there.")
    return 0
```

`setup/src/planner_setup/cli.py`:
- In `MENU`, insert `"Add another vault"` after `"Vault starter"`.
- In `_parser()`, after the `vault` subparser:
  ```python
  p = sub.add_parser("add-vault", help="register another vault in ~/.config/adhd-planner/vaults.json")
  p.add_argument("name", help="kebab-case, e.g. work")
  p.add_argument("--path", type=Path, required=True)
  p.add_argument("--folder", action="append", default=[], help="a folder whose sessions use this vault (repeatable)")
  p.add_argument("--existing-name", default="personal", help="name for today's vault when the file is created")
  ```
- In `main()`'s dispatch dict:
  ```python
  "add-vault": lambda: actions.add_vault(ctx, args.name, Path(os.path.expanduser(str(args.path))).absolute(),
                                         args.folder, args.existing_name),
  ```
- In `_menu()`, before `elif choice == "Example CLAUDE.md":`:
  ```python
          elif choice == "Add another vault":
              name = questionary.text("Name (kebab-case, e.g. work)").ask()
              where = questionary.path("Vault path", only_directories=True).ask()
              folders = questionary.text("Folders whose sessions use it (comma-separated, optional)").ask() or ""
              if name and where:
                  actions.add_vault(ctx, name.strip(), Path(os.path.expanduser(where)).absolute(),
                                    [f.strip() for f in folders.split(",") if f.strip()])
  ```

- [ ] **Step 4: Run them and watch them pass**

Run: `cd setup && uv run pytest -q`
Expected: 47 passed.

- [ ] **Step 5: Commit**

```bash
git add setup/src/planner_setup/paths.py setup/src/planner_setup/actions.py setup/src/planner_setup/cli.py \
  setup/tests/test_actions.py setup/tests/test_cli.py
git commit -m "feat(setup): planner-setup add-vault registers another vault"
```

---

### Task 8: Whole-branch verification and a real two-vault smoke test

**Files:** none changed, unless a check fails. A fix goes into the task that owns the code, as its own commit.

- [ ] **Step 1: Every suite**

Run:
```bash
python3 -m unittest discover -s tests && (cd setup && uv run pytest -q) && (cd plugins/task-track && claude plugin test .)
```
Expected:
- `tests/`: 35 + 5 + 1 + 4 = 45 tests OK
- `setup`: 47 passed
- `task-track`: 126 pass / 0 fail

Write the three result lines into the PR description as `VERIFY: Ran … — Result: PASS`.

- [ ] **Step 2: Smoke test with a throwaway second vault (Q runs this; it touches the real `~/vault`)**

1. `mkdir -p /tmp/mv-smoke/work/Tasks && printf -- '---\nstatus: active\n---\n# Smoke\n\n## Next\n- [ ] it works\n' > /tmp/mv-smoke/work/Tasks/smoke.md && echo smoke > /tmp/mv-smoke/work/Tasks/.active`
2. `ADHD_PLANNER_VAULTS=/tmp/mv-smoke/vaults.json uv run --project setup planner-setup --yes add-vault work --path /tmp/mv-smoke/work --folder /tmp/mv-smoke/repo`
3. `mkdir -p /tmp/mv-smoke/repo && cd /tmp/mv-smoke/repo && ADHD_PLANNER_VAULTS=/tmp/mv-smoke/vaults.json claude`. The session start should show `Vault: /tmp/mv-smoke/work`, then `Vault name: work (folder /tmp/mv-smoke/repo) · others: personal`, then `Active task: smoke`, and the band should show `▶ work · smoke`.
4. In that session: `/tasks:task-switch personal:<a parked slug>`. The reply should end with `Vault now: personal (~/vault)`, and `/tmp/mv-smoke/work/Tasks/.session/` should be empty.
5. Clean up with `rm -r /tmp/mv-smoke` (scratch only; Q confirms first).

- [ ] **Step 3: Hand off**

Use superpowers:finishing-a-development-branch. Do not push or open a PR until Q says so.
