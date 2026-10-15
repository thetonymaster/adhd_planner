#!/usr/bin/env python3
"""tasks plugin PermissionRequest hook: approve note reads and writes inside one vault.

Vaults: the ones registered in vaults.json (see vaults.py), else CLAUDE_PLUGIN_OPTION_VAULTPATH,
$VAULT or ~/vault; symlinks resolved. Reads and searches are approved unless a path segment under
the vault starts with '.'. Claude Code's Grep searches hidden files too (rg --hidden), so Grep is
approved only for a single existing note file, or with an anchored glob like `Projects/*.md`
(literal folders; see GREP_GLOB): vault-wide `*.md` searches get the normal prompt, and so does
`Projects/*.md` while Projects/ holds a hidden `.x.md`. Writes are
approved only for *.md / *.canvas outside dot-folders (never CLAUDE.md / CLAUDE.local.md, any
case) and for Tasks/.active, Tasks/.pomo.json, Tasks/.session/<id>, and never when the new text
holds code Obsidian plugins run (a dataviewjs fence, even inside a quote or list, Templater `<%`,
inline `$=`). That content
check is a best-effort tripwire, not a guarantee: it cannot see code split across writes.
Each call is decided on its own: no working directory is added.
No root is trusted if it is relative, '/', home or an ancestor of it, or inside/equal to
~/.claude or $CLAUDE_CONFIG_DIR (as written and `~`-expanded); nothing is approved when
vaults.json has an error or lies inside a vault. Anything else prints nothing, so the normal
permission prompt appears.
Always exits 0.
"""
import json
import os
import pathlib
import re
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


def unsafe_root(root, guarded):
    """A root that would expose home, the filesystem, or Claude's own config."""
    return root == "/" or any(inside(g, root) or inside(root, g) for g in guarded[1:]) or inside(guarded[0], root)


def vault_roots(env, home):
    """Trusted vault roots, symlinks resolved, deepest first. Empty when the config is broken,
    lives inside a vault, or a root is relative, `/`, home or an ancestor, or Claude's config."""
    config = vaults.load_config(env, home)
    if config.error:
        return []
    claude_dirs = [os.path.join(home, ".claude")]
    if env.get("CLAUDE_CONFIG_DIR"):
        # settings.json `env` does not expand `~`, so guard the value as written and as expanded.
        claude_dirs += [env["CLAUDE_CONFIG_DIR"], vaults.expand(env["CLAUDE_CONFIG_DIR"], home)]
    guarded = [os.path.realpath(home)] + [os.path.realpath(d) for d in claude_dirs]
    roots = set()
    for v in config.vaults:
        if not os.path.isabs(v.path):
            return []
        root = os.path.realpath(v.path)
        if os.path.isdir(root) and not unsafe_root(root, guarded):
            roots.add(root)
    where = os.path.realpath(vaults.config_path(env, home))
    if any(inside(where, r) for r in roots):
        return []
    return sorted(roots, key=len, reverse=True)


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


def pattern_escapes(pattern):
    """Absolute, home-relative, brace-expanding, or reaching a dot-segment (`..`, `.obsidian`)."""
    if pattern.startswith(("/", "~")) or "{" in pattern:
        return True
    return any(seg.startswith(".") for seg in pattern.replace("\\", "/").split("/"))


# NotebookEdit is listed so it is decided (refused: no .ipynb suffix) rather than ignored.
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
# Files Claude loads as instructions; compared lowercased (macOS volumes are case-insensitive).
STEERING_NAMES = {"claude.md", "claude.local.md"}
NOTE_SUFFIXES = (".md", ".canvas")
# Dot-files the tasks skills and the task-track mod write.
STATE_FILES = {("Tasks", ".active"), ("Tasks", ".pomo.json")}


# Note content that Dataview / Templater execute when Obsidian renders it.
CODE_MARKERS = ("<%", "`$=")
# A fence may sit behind Markdown containers (`> `, `- `, `1. `, nested): Obsidian still runs it.
CONTAINER = r"(?:[ \t]*(?:>|[-*+]|\d+[.)]))*"
DATAVIEWJS_FENCE = re.compile(
    rf"^{CONTAINER}[ \t]*(`{{3,}}|~{{3,}})[ \t]*dataviewjs", re.IGNORECASE | re.MULTILINE)
CONTENT_KEYS = {"Write": "content", "Edit": "new_string"}


def plants_code(tool, tool_input):
    text = tool_input.get(CONTENT_KEYS.get(tool, ""))
    return isinstance(text, str) and (any(m in text for m in CODE_MARKERS) or bool(DATAVIEWJS_FENCE.search(text)))


# Grep runs rg --hidden and splits `glob` on spaces/commas; an unanchored (`*.md`) or wildcard-folder
# (`*/*.md`, `**/*.md`) glob reaches dot-folders and `!` excludes. So only literal, non-dot folders
# ending in a note file are safe: optional `/`, folders [A-Za-z0-9_-]+, then *.md, *.canvas or a name.
GREP_GLOB = re.compile(r"/?([A-Za-z0-9_-]+/)+(\*\.(md|canvas)|[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(md|canvas))")


def hidden_note_in(glob, base):
    """True when a `Folder/*.md` glob's folder holds a dot-file that `*.md` would match.

    Why checking the folder is sound: rg --hidden lets `*.md` match `.secret.md`, but every
    auto-approved write goes through may_write, which refuses dot-names, so this hook can never
    create such a file. One can only appear if the user approved the write (or made it
    themselves), and then the normal prompt is the right answer. A missing folder holds nothing.
    """
    folder, _, final = glob.lstrip("/").rpartition("/")
    if not final.startswith("*"):
        return False  # a literal file name cannot match a different (hidden) one
    suffix = final[1:]
    try:
        names = os.listdir(os.path.join(base, folder))
    except OSError:
        return False
    return any(n.startswith(".") and n.endswith(suffix) for n in names)


def grep_is_visible_only(paths, tool_input):
    """Grep runs ripgrep with --hidden: allow one regular file, or an anchored note glob."""
    glob = tool_input.get("glob")
    if isinstance(glob, str) and GREP_GLOB.fullmatch(glob):
        return len(paths) == 1 and not hidden_note_in(glob, paths[0])
    return len(paths) == 1 and os.path.isfile(paths[0])


def parts_under(path, root):
    """`path` (inside `root`) as segments relative to it; () for the root itself."""
    return () if path == root else pathlib.PurePosixPath(os.path.relpath(path, root)).parts


def hidden(parts):
    return any(p.startswith(".") for p in parts)


def may_read(parts):
    return not hidden(parts)


def may_write(parts):
    """Notes only, plus the task pointer files: nothing that runs code or steers Claude."""
    if parts in STATE_FILES or (len(parts) == 3 and parts[:2] == ("Tasks", ".session")):
        return True
    return bool(parts) and not hidden(parts) and parts[-1].endswith(NOTE_SUFFIXES) and parts[-1].lower() not in STEERING_NAMES


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
    if not isinstance(request, dict):
        return
    tool = request.get("tool_name")
    if tool not in PATH_KEYS:
        return
    roots = vault_roots(os.environ, os.path.expanduser("~"))
    if not roots:
        return
    tool_input = request.get("tool_input") or {}
    try:
        paths = paths_of(tool, tool_input, request.get("cwd") or os.getcwd())
        pattern = tool_input.get(PATTERN_KEYS.get(tool, ""), "") or ""
        if tool == "Glob" and pattern and pattern_escapes(pattern):
            return
    except (AttributeError, TypeError):
        return  # malformed input: leave it to the normal prompt
    root = next((r for r in roots if paths and all(inside(p, r) for p in paths)), None)
    if root is None:
        return
    if tool in CONTENT_KEYS and plants_code(tool, tool_input):
        return
    if tool == "Grep" and not grep_is_visible_only(paths, tool_input):
        return
    rule = may_write if tool in WRITE_TOOLS else may_read
    if not all(rule(parts_under(p, root)) for p in paths):
        return
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PermissionRequest",
        "decision": {"behavior": "allow"},
    }}, sys.stdout)


if __name__ == "__main__":
    main()
