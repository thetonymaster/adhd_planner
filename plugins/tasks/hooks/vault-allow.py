#!/usr/bin/env python3
"""tasks plugin PermissionRequest hook: approve file tools whose every path is inside the vault.

Vault: CLAUDE_PLUGIN_OPTION_VAULTPATH, else $VAULT, else ~/vault (symlinks resolved).
Approves for this session only and adds the vault as a working directory. Anything else —
Bash, other tools, a path outside, no vault, unreadable input — prints nothing, so the
normal permission prompt appears. Always exits 0.
"""
import json
import os
import sys

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


def vault_root():
    raw = os.environ.get("CLAUDE_PLUGIN_OPTION_VAULTPATH") or os.environ.get("VAULT") or "~/vault"
    root = os.path.realpath(os.path.expanduser(raw))
    return root if os.path.isdir(root) else None


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
    root = vault_root()
    if root is None:
        return
    tool_input = request.get("tool_input") or {}
    try:
        paths = paths_of(tool, tool_input, request.get("cwd") or os.getcwd())
        pattern = tool_input.get(PATTERN_KEYS.get(tool, ""), "") or ""
        if pattern and pattern_escapes(pattern):
            return
    except (AttributeError, TypeError):
        return  # malformed input: leave it to the normal prompt
    if not paths or not all(inside(p, root) for p in paths):
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
