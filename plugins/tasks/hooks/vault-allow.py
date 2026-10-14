#!/usr/bin/env python3
"""tasks plugin PermissionRequest hook: approve file tools whose every path is inside one vault.

Vaults: the ones registered in vaults.json (see vaults.py), else CLAUDE_PLUGIN_OPTION_VAULTPATH,
$VAULT or ~/vault; symlinks resolved. Approves for this session only and adds that one vault as a
working directory. Anything else — Bash, other tools, a path outside, paths spanning two vaults,
no vault, unreadable input — prints nothing, so the normal permission prompt appears. Always exits 0.
"""
import json
import os
import sys

import vaults

# tool -> keys in tool_input holding a path; a missing optional key means cwd.
PATH_KEYS = {
    "Read": ("file_path",),
    "Edit": ("file_path",),
    "Write": ("file_path",),
    "NotebookEdit": ("notebook_path",),
    "Glob": ("path",),
    "Grep": ("path",),
}
CWD_DEFAULT = {"Glob", "Grep"}
# Glob patterns are resolved under the path, so one that is absolute or climbs out escapes it.
PATTERN_KEYS = {"Glob": "pattern", "Grep": "glob"}


def vault_roots():
    """Every registered vault that exists, symlinks resolved, deepest first (a vault nested in another wins)."""
    config = vaults.load_config(os.environ, os.path.expanduser("~"))
    roots = {os.path.realpath(v.path) for v in config.vaults}
    return sorted((r for r in roots if os.path.isdir(r)), key=len, reverse=True)


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


def pattern_escapes(pattern):
    return pattern.startswith(("/", "~")) or ".." in pattern.replace("\\", "/").split("/")


def paths_of(tool, tool_input, cwd):
    found = []
    for key in PATH_KEYS[tool]:
        value = tool_input.get(key)
        if value:
            found.append(value)
        elif tool in CWD_DEFAULT:
            found.append(cwd)
    return [os.path.realpath(os.path.join(cwd, os.path.expanduser(p))) for p in found]


def main():
    try:
        request = json.load(sys.stdin)
    except ValueError:
        return
    tool = request.get("tool_name")
    if tool not in PATH_KEYS:
        return
    roots = vault_roots()
    if not roots:
        return
    tool_input = request.get("tool_input") or {}
    try:
        paths = paths_of(tool, tool_input, request.get("cwd") or os.getcwd())
        pattern = tool_input.get(PATTERN_KEYS.get(tool, ""), "") or ""
        if pattern and pattern_escapes(pattern):
            return
    except (AttributeError, TypeError):
        return  # malformed input: leave it to the normal prompt
    root = next((r for r in roots if paths and all(inside(p, r) for p in paths)), None)
    if root is None:
        return
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PermissionRequest",
        "decision": {
            "behavior": "allow",
            "updatedPermissions": [{"type": "addDirectories", "directories": [root], "destination": "session"}],
        },
    }}, sys.stdout)


if __name__ == "__main__":
    main()
