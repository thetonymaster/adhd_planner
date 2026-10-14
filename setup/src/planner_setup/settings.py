"""Pure functions over settings dicts: what setup wants, and merging it in."""
from __future__ import annotations

import copy

from .paths import norm

MARKETPLACE = "adhd-planner"
PLUGINS = ("planner", "tasks", "task-track")
VAULT_PLUGINS = ("tasks", "task-track")
OBSIDIAN_ALLOW = "Bash(obsidian:*)"


def desired(vault: str, *, permissions: bool) -> dict:
    wanted: dict = {"pluginConfigs": {
        f"{p}@{MARKETPLACE}": {"options": {"vaultPath": vault}} for p in VAULT_PLUGINS
    }}
    if permissions:
        wanted["permissions"] = {"additionalDirectories": [vault], "allow": [OBSIDIAN_ALLOW]}
    return wanted


def _child(parent: dict, key: str, kind: type, label: str):
    """parent[key], created empty if missing; a value of another type stops setup."""
    value = parent.setdefault(key, kind())
    if not isinstance(value, kind):
        raise SystemExit(f"settings.json {label} is a {type(value).__name__}, expected a {kind.__name__}; "
                         "fix it first; nothing was changed.")
    return value


def merge(current: dict, wanted: dict, *, home: str) -> tuple[dict, list[str]]:
    """Merge `wanted` into a copy of `current`. Change lines name keys, never values.

    Directories compare after `~` expansion and normalisation, so `~/vault/` and
    `/home/q/vault` count as the same entry."""
    out = copy.deepcopy(current)
    changes: list[str] = []

    configs = _child(out, "pluginConfigs", dict, "pluginConfigs")
    for plugin_id, block in wanted.get("pluginConfigs", {}).items():
        label = f'pluginConfigs["{plugin_id}"]'
        options = _child(_child(configs, plugin_id, dict, label), "options", dict, f"{label}.options")
        for key, value in block["options"].items():
            if key not in options:
                changes.append(f'pluginConfigs["{plugin_id}"].options.{key}: set')
            elif options[key] != value:
                changes.append(f'pluginConfigs["{plugin_id}"].options.{key}: change')
            else:
                continue
            options[key] = value
    if not configs:
        del out["pluginConfigs"]

    perms = wanted.get("permissions")
    if perms:
        have = _child(out, "permissions", dict, "permissions")
        for key, values in perms.items():
            current_list = _child(have, key, list, f"permissions.{key}")
            for v in values:
                if key == "additionalDirectories":
                    present = any(norm(d, home) == norm(v, home) for d in current_list if isinstance(d, str))
                else:
                    present = v in current_list
                if not present:
                    current_list.append(v)
                    # The vault path is a value too: name the key, not the path.
                    changes.append(f"permissions.{key}: add {v}" if key == "allow" else f"permissions.{key}: add vault")
    return out, changes
