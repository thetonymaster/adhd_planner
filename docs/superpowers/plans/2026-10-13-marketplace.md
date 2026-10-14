# One Marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn this repo into one plugin marketplace (`adhd-planner`) with three plugins
(`planner`, `tasks`, `task-track`) whose hooks ship inside the plugins. A `uvx` menu
(`planner-setup`) handles what plugins cannot carry.

**Architecture:** `.claude-plugin/marketplace.json` at the repo root lists `./plugins/*`.
`tasks` owns the task-note skills and three hooks: SessionStart `load-task.sh`,
UserPromptSubmit `date`, and PermissionRequest `vault-allow.py`. `setup/` is a uv project
whose pure settings functions are separate from file IO and from the `claude` CLI wrapper.

**Tech Stack:** Claude Code plugins (skills, hooks, mod), bash + Python 3.10+ stdlib for
hooks, uv + hatchling + questionary + pytest for `setup/`.

**Spec:** `docs/superpowers/specs/2026-10-13-marketplace-design.md`

## Global Constraints

- Marketplace name `adhd-planner`. Plugin names `planner`, `tasks`, `task-track`.
- Plugin options live in `pluginConfigs["<plugin>@adhd-planner"].options` in
  `~/.claude/settings.json`. Hooks read them as `CLAUDE_PLUGIN_OPTION_<KEY uppercased>`;
  `vaultPath` becomes `CLAUDE_PLUGIN_OPTION_VAULTPATH`.
- Vault resolution everywhere: `vaultPath` option → `$VAULT` → `~/vault`.
- Hook commands use `${CLAUDE_PLUGIN_ROOT}`; hook scripts are executable.
- Hooks never fail a session: they exit 0 on every path, including no vault or no `python3`.
- `vault-allow.py` never approves Bash. It approves only when every path is inside the
  vault, and only with `destination: "session"`.
- Setup writes: list key names (never values) → confirm unless `--yes` → back up to
  `~/.claude/backups/<timestamp>/` → temp file, re-parse, rename.
- No silent fallbacks: invalid `settings.json` aborts with path + parse error; `claude`
  non-zero shows stderr verbatim.
- `requires-python = ">=3.10"` for `setup/`.
- Commits: add files individually, no `git add .`, no AI attribution lines (Q's CLAUDE.md).
- Do not touch: `~/.claude/CLAUDE.md`, root `tools/`, the HTML pages, `inbox.md`,
  `habits*.json`.

## Review Focus

1. **Vault path with `~`, a trailing slash, or a symlink** (e.g. the vault is an iCloud
   symlink). Expected: hook and setup treat them as the same directory. → Task 3 test
   `test_symlinked_vault_and_tilde_option`.
2. **`settings.json` holding keys setup doesn't know** (Q's real file has `enabledPlugins`,
   `extraKnownMarketplaces`, hooks…). Expected: every unknown key survives byte-for-byte in
   value. → Task 5 test `test_merge_keeps_unrelated_keys`.
3. **Running setup twice.** Expected: the second run reports nothing to change and writes
   no backup. → Task 5 test `test_second_apply_is_noop_and_skips_backup`.
4. **Glob/Grep with no `path`** (defaults to cwd). Expected: approved only if cwd is in
   the vault. → Task 3 test `test_glob_without_path_uses_cwd`.
5. **task-track's Park button after the rename.** Expected: it submits
   `/tasks:task-park`, which resolves. → Task 1 test update + Task 8 rollout check.

---

## File map

| Path | Responsibility | Task |
|---|---|---|
| `.claude-plugin/marketplace.json` | Lists the 3 plugins | 1 |
| `plugins/planner/` | moved from `planner-plugin/` | 1 |
| `plugins/task-track/` | moved from `claude-config/task-track/`; `/task-*` hints → `/tasks:task-*` | 1 |
| `examples/{CLAUDE.md,vault-starter/}` | moved from `claude-config/` | 1 |
| `plugins/tasks/.claude-plugin/plugin.json` | manifest + `vaultPath` userConfig | 2 |
| `plugins/tasks/skills/{task-start,task-park,task-switch,obsidian-vault}` | moved | 2 |
| `plugins/tasks/hooks/{hooks.json,load-task.sh}` | session context hook | 2 |
| `plugins/tasks/hooks/vault-allow.py` | PermissionRequest hook | 3 |
| `tests/test_vault_allow.py` | its tests | 3 |
| `plugins/tasks/skills/task-note/SKILL.md` | Cowork-safe note edits | 4 |
| `setup/pyproject.toml`, `setup/src/planner_setup/{settings,files}.py`, `setup/tests/` | pure merge + safe writes | 5 |
| `setup/src/planner_setup/{paths,claude_cli,actions}.py` | vault/example paths, CLI wrapper, the six actions | 6 |
| `setup/src/planner_setup/cli.py` | argparse + questionary menu | 7 |
| `examples/settings.example.json`, `docs/setup.md`, READMEs | docs; remove `claude-config/` leftovers | 7 |
| — | Q's machine: remove old install, install via uvx | 8 |
| — | Cowork check, decide `build-plugin.sh` | 9 |

---

### Task 1: Marketplace skeleton and moves

**Files:**
- Create: `.claude-plugin/marketplace.json`
- Move: `planner-plugin/` → `plugins/planner/`; `claude-config/task-track/` → `plugins/task-track/`; `claude-config/CLAUDE.md` → `examples/CLAUDE.md`; `claude-config/vault-starter/` → `examples/vault-starter/`
- Delete: `claude-config/skills/{autonomy-check,composition,handoff,investigation}/`, `claude-config/rules/`
- Modify: `plugins/task-track/hooks/register.tsx` (5 strings `/task-start <name>`, `/task-park`), `plugins/task-track/tests/task-track.test.ts:473`, `plugins/task-track/README.md`, `plugins/planner/.claude-plugin/plugin.json` (version), `scripts/build-plugin.sh:7` (src path)

**Interfaces:**
- Produces: marketplace root at the repo root, with plugins at `./plugins/<name>`. Later tasks add `plugins/tasks`.

- [ ] **Step 1: Move with git**

```bash
mkdir -p plugins examples
git mv planner-plugin plugins/planner
git mv claude-config/task-track plugins/task-track
git mv claude-config/CLAUDE.md examples/CLAUDE.md
git mv claude-config/vault-starter examples/vault-starter
git rm -r -q claude-config/skills/autonomy-check claude-config/skills/composition claude-config/skills/handoff claude-config/skills/investigation claude-config/rules
```

- [ ] **Step 2: Write `.claude-plugin/marketplace.json`**

`tasks` is added in Task 2; listing it now would fail validation.

```json
{
  "name": "adhd-planner",
  "description": "ADHD-friendly planning and Obsidian task notes for Claude Code and Cowork.",
  "owner": { "name": "Antonio Cabrera" },
  "plugins": [
    {
      "name": "planner",
      "source": "./plugins/planner",
      "description": "Brain-dump triage, task breakdown, time-blocking around real meetings, A5 pages, habits. Code and Cowork."
    },
    {
      "name": "task-track",
      "source": "./plugins/task-track",
      "description": "Claude Code only (a mod): task band, pane, shared Pomodoro, /note /done /openloop without a model turn."
    }
  ]
}
```

- [ ] **Step 3: Update the task-track test to the prefixed hint, run it, watch it fail**

In `plugins/task-track/tests/task-track.test.ts:473`, change
`'No active task. /task-start <name>'` → `'No active task. /tasks:task-start <name>'`.

Run: `cd plugins/task-track && claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `97 pass`, `1 fail`.

- [ ] **Step 4: Prefix the hints in `register.tsx`**

```bash
cd plugins/task-track
sed -i '' -e 's#/task-start <name>#/tasks:task-start <name>#g' \
          -e 's#/task-start &lt;name&gt;#/tasks:task-start \&lt;name\&gt;#' \
          -e "s#text: '/task-park'#text: '/tasks:task-park'#" \
          -e 's#label="Park (/task-park)"#label="Park (/tasks:task-park)"#' hooks/register.tsx
grep -n 'task-start\|task-park' hooks/register.tsx
```
Expected: every hit shows `/tasks:`.

- [ ] **Step 5: Run task-track tests + validate**

Run: `cd plugins/task-track && claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)' && claude plugin validate .`
Expected: `98 pass`, `0 fail`, `✔ Validation passed`.

- [ ] **Step 6: Fix paths in docs and scripts**

- `plugins/task-track/README.md`: replace the `CLAUDE_CODE_PLUGIN_DIRS` install snippet
  (line ~54) with `Install: see docs/setup.md (claude plugin install task-track@adhd-planner).`
  Settings heading: `pluginConfigs.task-track.options` → `pluginConfigs["task-track@adhd-planner"].options`.
  `/task-switch` → `/tasks:task-switch` in line 3.
- `plugins/planner/README.md:34` and the skills `capture-triage/SKILL.md:118` and
  `eod-shutdown/SKILL.md:113`: `/task-start` → `/tasks:task-start`, `/task-park` → `/tasks:task-park`.
- `plugins/planner/.claude-plugin/plugin.json`: `"version": "0.3.0"`.
- `scripts/build-plugin.sh`: `src="$repo/planner-plugin"` → `src="$repo/plugins/planner"`.
- `examples/CLAUDE.md`: insert as line 1: `> Example — copy to ~/.claude/CLAUDE.md and adapt. Skills come from the adhd-planner marketplace (\`/tasks:task-park\`…).`

- [ ] **Step 7: Validate marketplace + planner**

Run: `claude plugin validate . && claude plugin validate plugins/planner && bash scripts/build-plugin.sh`
Expected: three passes, the last ending with `Built …/planner.plugin (… files, version 0.3.0)`.

- [ ] **Step 8: Commit**

```bash
git add .claude-plugin/marketplace.json plugins/planner plugins/task-track examples scripts/build-plugin.sh planner.plugin
git status --short   # expect only renames/deletes from claude-config/ and planner-plugin/ besides the above
git commit -m "refactor(marketplace): one marketplace with planner and task-track under plugins/"
```

---

### Task 2: `tasks` plugin with the session hooks

**Files:**
- Create: `plugins/tasks/.claude-plugin/plugin.json`, `plugins/tasks/hooks/hooks.json`
- Move: `claude-config/skills/{task-start,task-park,task-switch,obsidian-vault}` → `plugins/tasks/skills/`; `claude-config/hooks/load-task.sh` → `plugins/tasks/hooks/load-task.sh`
- Modify: `plugins/tasks/hooks/load-task.sh:5` (vault) and `:94` (hint), the moved skills (prefix `/task-*`), `tests/test_load_task.py`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: Task 1's marketplace.
- Produces: `CLAUDE_PLUGIN_OPTION_VAULTPATH` honoured by `load-task.sh`. Task 3 adds a third hook to `hooks.json`.

- [ ] **Step 1: Move**

```bash
mkdir -p plugins/tasks/.claude-plugin plugins/tasks/skills
for s in task-start task-park task-switch obsidian-vault; do git mv claude-config/skills/$s plugins/tasks/skills/$s; done
git mv claude-config/hooks plugins/tasks/hooks
```

- [ ] **Step 2: Point the tests at the new path and add the new cases (failing)**

In `tests/test_load_task.py`, set line 1's path to `plugins/tasks/hooks/load-task.sh`
and line 11 to:

```python
HOOK = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks" / "load-task.sh"
```

Change `run_hook` to accept extra env:

```python
    def run_hook(self, payload=None, stdin=None, env_extra=None):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"], **(env_extra or {})}
        data = json.dumps(payload).encode() if payload is not None else None
        out = subprocess.run(["bash", str(HOOK)], input=data, stdin=stdin, env=env,
                             capture_output=True, timeout=10, check=True)
        return out.stdout.decode()
```

Append these tests to the class:

```python
    def test_plugin_option_beats_vault_env(self):
        other = self.home / "elsewhere" / "Tasks"
        other.mkdir(parents=True)
        (other / "opt.md").write_text(NOTE.format(slug="opt", status="active", repo=""))
        (other / ".active").write_text("opt\n")
        (self.tasks / ".active").write_text("ignored\n")
        out = self.run_hook({"session_id": "x", "cwd": "/"}, env_extra={
            "CLAUDE_PLUGIN_OPTION_VAULTPATH": str(self.home / "elsewhere"),
            "VAULT": str(self.home / "vault")})
        self.assertIn("Active task: opt (global)", out)

    def test_tilde_in_option_is_expanded(self):
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        out = self.run_hook({"session_id": "x", "cwd": "/"}, env_extra={"CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/vault"})
        self.assertIn("Active task: g (global)", out)

    def test_no_vault_prints_only_the_time(self):
        shutil.rmtree(self.home / "vault")
        out = self.run_hook({"session_id": "x", "cwd": "/"})
        self.assertRegex(out, r"^Now: .+\n$")

    def test_no_task_hint_uses_prefixed_skill(self):
        out = self.run_hook({"session_id": "x", "cwd": "/"})
        self.assertIn("/tasks:task-start", out)
```

Run: `python3 -m unittest tests.test_load_task -v 2>&1 | tail -15`
Expected: the 4 new tests FAIL (option ignored; no-vault prints the "No active task" line;
hint is `/task-start`); the existing 9 PASS.

- [ ] **Step 3: Implement in `load-task.sh`**

Replace line 5 (`VAULT="${VAULT:-$HOME/vault}"`) with:

```bash
VAULT="${CLAUDE_PLUGIN_OPTION_VAULTPATH:-${VAULT:-$HOME/vault}}"
case "$VAULT" in "~") VAULT=$HOME ;; "~/"*) VAULT="$HOME/${VAULT#\~/}" ;; esac
```

After `echo "Now: $(date '+%a %Y-%m-%d %H:%M')"` add:

```bash
# No vault here (e.g. Cowork without the folder connected): the time is all there is to say.
[ -d "$NOTES" ] || exit 0
```

Line 94 hint: `suggest /task-start.` → `suggest /tasks:task-start.`

Update the header comment (lines 1–4) so its first line is `# tasks plugin SessionStart hook: inject time + this session's task Next/Open loops.`

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 18 tests` … `OK`.

- [ ] **Step 5: Write `plugins/tasks/.claude-plugin/plugin.json`**

```json
{
  "name": "tasks",
  "version": "0.1.0",
  "description": "Obsidian task notes: start, park and switch tasks, see the active task's Next at session start, and add notes or check items from Code or Cowork.",
  "author": { "name": "Antonio Cabrera" },
  "keywords": ["adhd", "obsidian", "tasks"],
  "userConfig": {
    "vaultPath": {
      "type": "string",
      "title": "Vault path",
      "description": "Absolute path to the Obsidian vault. Empty: $VAULT, else ~/vault.",
      "default": ""
    }
  }
}
```

- [ ] **Step 6: Write `plugins/tasks/hooks/hooks.json`**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/load-task.sh", "args": [], "timeout": 10 }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "date '+Now: %H:%M'", "timeout": 5 }
        ]
      }
    ]
  }
}
```

- [ ] **Step 7: Prefix skill cross-references**

```bash
cd plugins/tasks/skills
sed -i '' -E 's#`/task-(start|park|switch)#`/tasks:task-\1#g; s#(Use on|says) /task-#\1 /tasks:task-#g' */SKILL.md
grep -n '/task-' */SKILL.md
```
Expected: every hit is `/tasks:task-…`.

- [ ] **Step 8: Add `tasks` to the marketplace and validate**

Insert into `.claude-plugin/marketplace.json` `plugins`, between `planner` and `task-track`:

```json
    {
      "name": "tasks",
      "source": "./plugins/tasks",
      "description": "Obsidian task notes: session-start context and vault access hooks, plus start/park/switch and note skills. Code and Cowork."
    },
```

Run: `test -x plugins/tasks/hooks/load-task.sh && claude plugin validate plugins/tasks && claude plugin validate .`
Expected: two `✔ Validation passed`.

- [ ] **Step 9: Commit**

```bash
git add tests/test_load_task.py plugins/tasks .claude-plugin/marketplace.json
git commit -m "feat(tasks): tasks plugin with session-start hook and vaultPath option"
```

---

### Task 3: `vault-allow.py` PermissionRequest hook

**Files:**
- Create: `plugins/tasks/hooks/vault-allow.py` (executable), `tests/test_vault_allow.py`
- Modify: `plugins/tasks/hooks/hooks.json`

**Interfaces:**
- Consumes: `CLAUDE_PLUGIN_OPTION_VAULTPATH`, `VAULT`, `HOME`. Stdin is the PermissionRequest JSON: `tool_name`, `tool_input`, `cwd`.
- Produces: on approval, stdout
  `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow","updatedPermissions":[{"type":"addDirectories","directories":["<vault realpath>"],"destination":"session"}]}}}`.
  Otherwise empty stdout. Exit 0 always.

The `updatedPermissions` entry shape comes from the hooks reference table. The docs show no
full example, so Task 8 step 4 confirms it live.

- [ ] **Step 1: Write the failing tests** — `tests/test_vault_allow.py`

```python
"""Tests for plugins/tasks/hooks/vault-allow.py. Run: python3 -m unittest discover -s tests"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks" / "vault-allow.py"


class VaultAllowTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp()).resolve()
        self.vault = self.home / "vault"
        (self.vault / "Tasks").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.home)

    def ask(self, tool, tool_input, cwd="/", env_extra=None, raw=None):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"], **(env_extra or {})}
        data = raw if raw is not None else json.dumps(
            {"hook_event_name": "PermissionRequest", "tool_name": tool, "tool_input": tool_input, "cwd": cwd}).encode()
        out = subprocess.run([str(HOOK)], input=data, env=env, capture_output=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def assertAllowed(self, result):
        self.assertIsNotNone(result)
        out = result["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PermissionRequest")
        self.assertEqual(out["decision"]["behavior"], "allow")
        self.assertEqual(out["decision"]["updatedPermissions"],
                         [{"type": "addDirectories", "directories": [str(self.vault)], "destination": "session"}])

    def test_read_inside_vault_is_allowed(self):
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "Tasks" / "a.md")}))

    def test_edit_write_notebook_grep_inside_are_allowed(self):
        self.assertAllowed(self.ask("Edit", {"file_path": str(self.vault / "x.md")}))
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "new" / "y.md")}))
        self.assertAllowed(self.ask("NotebookEdit", {"notebook_path": str(self.vault / "n.ipynb")}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": str(self.vault)}))

    def test_outside_vault_is_left_to_the_user(self):
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "secrets.txt")}))

    def test_sibling_prefix_is_outside(self):
        (self.home / "vault-old").mkdir()
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "vault-old" / "a.md")}))

    def test_dotdot_escape_is_outside(self):
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / ".." / "secrets.txt")}))

    def test_symlink_out_of_vault_is_outside(self):
        (self.home / "outside").mkdir()
        os.symlink(self.home / "outside", self.vault / "link")
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / "link" / "a.md")}))

    def test_bash_is_never_approved(self):
        self.assertIsNone(self.ask("Bash", {"command": f"cat {self.vault}/Tasks/a.md"}, cwd=str(self.vault)))

    def test_unknown_tool_is_left_to_the_user(self):
        self.assertIsNone(self.ask("WebFetch", {"url": "https://example.com"}, cwd=str(self.vault)))

    def test_glob_without_path_uses_cwd(self):
        self.assertAllowed(self.ask("Glob", {"pattern": "**/*.md"}, cwd=str(self.vault / "Tasks")))
        self.assertIsNone(self.ask("Glob", {"pattern": "**/*.md"}, cwd=str(self.home)))

    def test_relative_path_resolves_against_cwd(self):
        self.assertAllowed(self.ask("Read", {"file_path": "Tasks/a.md"}, cwd=str(self.vault)))

    def test_symlinked_vault_and_tilde_option(self):
        real = self.home / "icloud" / "vault"
        real.mkdir(parents=True)
        os.symlink(real, self.home / "v")
        result = self.ask("Read", {"file_path": str(real / "a.md")},
                          env_extra={"CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/v/"})
        self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [str(real)])

    def test_missing_vault_or_bad_json_does_nothing(self):
        self.assertIsNone(self.ask("Read", {"file_path": "/tmp/a"}, env_extra={"VAULT": str(self.home / "nope")}))
        self.assertIsNone(self.ask("Read", {}, raw=b"not json"))
```

Run: `python3 -m unittest tests.test_vault_allow 2>&1 | tail -3`
Expected: errors (`FileNotFoundError` / permission) because the hook does not exist yet.

- [ ] **Step 2: Implement `plugins/tasks/hooks/vault-allow.py`**

```python
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


def vault_root():
    raw = os.environ.get("CLAUDE_PLUGIN_OPTION_VAULTPATH") or os.environ.get("VAULT") or "~/vault"
    root = os.path.realpath(os.path.expanduser(raw))
    return root if os.path.isdir(root) else None


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


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
    paths = paths_of(tool, request.get("tool_input") or {}, request.get("cwd") or os.getcwd())
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
```

Run: `chmod +x plugins/tasks/hooks/vault-allow.py`

- [ ] **Step 3: Run the tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `Ran 30 tests` … `OK`.

- [ ] **Step 4: Register the hook**

Add to `plugins/tasks/hooks/hooks.json` under `"hooks"`:

```json
    "PermissionRequest": [
      {
        "matcher": "Read|Edit|Write|NotebookEdit|Glob|Grep",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/vault-allow.py", "args": [], "timeout": 5 }
        ]
      }
    ]
```

Run: `claude plugin validate plugins/tasks`
Expected: `✔ Validation passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/tasks/hooks/vault-allow.py plugins/tasks/hooks/hooks.json tests/test_vault_allow.py
git commit -m "feat(tasks): auto-approve file tools inside the vault for the session"
```

---

### Task 4: `task-note` skill

**Files:**
- Create: `plugins/tasks/skills/task-note/SKILL.md`

**Interfaces:**
- Consumes: the note format of `examples/vault-starter/Tasks/set-up-vault.md` (frontmatter
  `status`; sections `## Goal`, `## Next` with `- [ ]`, `## Open loops`, `## Log` lines
  `- [[YYYY-MM-DD]] HH:MM — text`), and the `obsidian-vault` skill.

- [ ] **Step 1: Write the skill**

```markdown
---
name: task-note
description: Read or update an existing Obsidian task note — show a task, list open tasks, add a Log note, check or uncheck a Next item, add an Open loop. Use when Q says "add a note to <task>", "mark <item> done", "what's next on <task>", "which tasks are open", or in Cowork wherever /note, /done or /openloop would be used in Claude Code.
---

Works in Claude Code and Cowork. Edits notes that already exist; it never creates,
renames, moves or deletes a note (that is `/tasks:task-start`, and Q's job in Obsidian).

## Find the vault

First match wins:
1. A connected or working folder named `vault`, or one holding both `Tasks/` and `Daily/`.
2. `$VAULT`.
3. `~/vault`.

None has `Tasks/` → say "No vault found (looked in: <each place checked>)" and stop.

## Pick the task

- Q named one → match the file stem in `Tasks/`, else a note whose `aliases` contains the
  name (case-insensitive). Several match → list them and ask.
- Q named none → `Tasks/.active`. Empty or missing → list open tasks and ask.

## Actions

| Q asks | Do |
|---|---|
| show / what's next | Print `## Goal`, open `## Next` items numbered, `## Open loops`. Skip lines struck through with `~~`. |
| list open tasks | Every `Tasks/*.md` whose frontmatter `status` is not `done`: `slug — status — first open Next item`. |
| add a note | Append to `## Log`: `- [[YYYY-MM-DD]] HH:MM — <text>` (local date and time). |
| check / uncheck item | `- [ ]` ↔ `- [x]` on the item Q means (number from "show", or text match). Ambiguous → ask. |
| add an open loop | Append `- <text>` to `## Open loops`. |

Rules:
- Missing section → add it under the last existing `## ` section, in the order Goal, Next,
  Open loops, Parked, Log.
- Never delete a line. Obsolete → wrap in `~~…~~` and append ` — <why>`.
- Follow `obsidian-vault` for links and formatting when that skill is available.
- Change only the lines the action needs; re-read the note after writing and quote the
  changed line back.

Reply in one line: `<slug>: <what changed>` (e.g. `set-up-vault: logged "test"`).
```

- [ ] **Step 2: Validate**

Run: `claude plugin validate plugins/tasks && claude plugin validate .`
Expected: two `✔ Validation passed`. Behaviour is checked live in Task 8 (Code) and Task 9 (Cowork).

- [ ] **Step 3: Commit**

```bash
git add plugins/tasks/skills/task-note/SKILL.md
git commit -m "feat(tasks): task-note skill to read and update task notes from Code or Cowork"
```

---

### Task 5: `setup/` package — settings merge and safe writes

**Files:**
- Create: `setup/pyproject.toml`, `setup/src/planner_setup/__init__.py`, `setup/src/planner_setup/settings.py`, `setup/src/planner_setup/files.py`, `setup/tests/test_settings.py`, `setup/tests/test_files.py`

**Interfaces:**
- Produces:
  - `settings.MARKETPLACE = "adhd-planner"`; `settings.PLUGINS = ("planner", "tasks", "task-track")`
  - `settings.desired(vault: str, *, permissions: bool) -> dict` — the fragment setup wants
  - `settings.merge(current: dict, wanted: dict) -> tuple[dict, list[str]]` — new dict plus
    change lines (key paths only); `current` is not mutated
  - `files.load_json(path: Path) -> dict` — `{}` if missing or blank; `SystemExit` naming the
    path on invalid JSON or a non-object
  - `files.write_json(path: Path, data: dict, backups: Path, *, home: Path) -> Path | None` —
    backs up an existing file to `backups/<path relative to home, or its name>`, writes
    atomically, returns the backup path (None when there was no file)
  - `files.backup_dir(home: Path) -> Path` — `home/.claude/backups/<YYYYmmddHHMMSS>`

- [ ] **Step 1: Write `setup/pyproject.toml` and the package init**

```toml
[project]
name = "planner-setup"
version = "0.1.0"
description = "Set up the adhd-planner marketplace for Claude Code and Cowork."
requires-python = ">=3.10"
dependencies = ["questionary>=2.0"]

[project.scripts]
planner-setup = "planner_setup.cli:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/planner_setup"]
```

`setup/src/planner_setup/__init__.py`:

```python
"""Setup helper for the adhd-planner marketplace."""
```

- [ ] **Step 2: Write the failing tests** — `setup/tests/test_settings.py`

```python
from planner_setup.settings import desired, merge


def test_desired_sets_vault_for_both_plugins_only():
    d = desired("/v", permissions=False)
    assert d == {"pluginConfigs": {
        "tasks@adhd-planner": {"options": {"vaultPath": "/v"}},
        "task-track@adhd-planner": {"options": {"vaultPath": "/v"}},
    }}


def test_desired_with_permissions():
    d = desired("/v", permissions=True)
    assert d["permissions"] == {"additionalDirectories": ["/v"], "allow": ["Bash(obsidian:*)"]}


def test_merge_keeps_unrelated_keys():
    current = {
        "enabledPlugins": {"x@y": True},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "say hi"}]}]},
        "permissions": {"allow": ["Bash(ls:*)"], "deny": ["Read(.env)"]},
        "pluginConfigs": {"tasks@adhd-planner": {"options": {"other": 1}}},
    }
    merged, changes = merge(current, desired("/v", permissions=True))
    assert merged["enabledPlugins"] == {"x@y": True}
    assert merged["hooks"] == current["hooks"]
    assert merged["permissions"]["deny"] == ["Read(.env)"]
    assert merged["permissions"]["allow"] == ["Bash(ls:*)", "Bash(obsidian:*)"]
    assert merged["pluginConfigs"]["tasks@adhd-planner"]["options"] == {"other": 1, "vaultPath": "/v"}
    assert current["permissions"]["allow"] == ["Bash(ls:*)"]  # input untouched
    assert "permissions.allow: add Bash(obsidian:*)" in changes
    assert 'pluginConfigs["tasks@adhd-planner"].options.vaultPath: set' in changes


def test_merge_replaces_a_different_vault_and_says_so():
    current = desired("/old", permissions=False)
    merged, changes = merge(current, desired("/new", permissions=False))
    assert merged["pluginConfigs"]["tasks@adhd-planner"]["options"]["vaultPath"] == "/new"
    assert 'pluginConfigs["tasks@adhd-planner"].options.vaultPath: change' in changes


def test_merge_is_idempotent():
    once, _ = merge({}, desired("/v", permissions=True))
    twice, changes = merge(once, desired("/v", permissions=True))
    assert twice == once and changes == []


def test_change_lines_never_contain_values():
    _, changes = merge({}, desired("/secret/vault", permissions=False))
    assert not any("/secret/vault" in c for c in changes)
```

`setup/tests/test_files.py`:

```python
import json

import pytest

from planner_setup.files import backup_dir, load_json, write_json


def test_load_missing_or_blank_is_empty(tmp_path):
    assert load_json(tmp_path / "nope.json") == {}
    (tmp_path / "blank.json").write_text("  \n")
    assert load_json(tmp_path / "blank.json") == {}


def test_load_invalid_json_aborts_naming_the_file(tmp_path):
    bad = tmp_path / "settings.json"
    bad.write_text("{ nope")
    with pytest.raises(SystemExit) as err:
        load_json(bad)
    assert str(bad) in str(err.value) and "nothing was changed" in str(err.value)


def test_load_non_object_aborts(tmp_path):
    arr = tmp_path / "settings.json"
    arr.write_text("[]")
    with pytest.raises(SystemExit):
        load_json(arr)


def test_write_backs_up_then_replaces(tmp_path):
    home = tmp_path
    target = home / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text('{"a": 1}')
    backups = backup_dir(home)
    saved = write_json(target, {"a": 2}, backups, home=home)
    assert json.loads(target.read_text()) == {"a": 2}
    assert saved == backups / ".claude" / "settings.json"
    assert json.loads(saved.read_text()) == {"a": 1}
    assert not list(target.parent.glob("*.tmp"))


def test_write_new_file_has_no_backup(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    assert write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path) is None
    assert target.read_text().endswith("\n")


def test_second_apply_is_noop_and_skips_backup(tmp_path):
    from planner_setup.settings import desired, merge
    target = tmp_path / ".claude" / "settings.json"
    merged, _ = merge(load_json(target), desired("/v", permissions=False))
    write_json(target, merged, backup_dir(tmp_path), home=tmp_path)
    again, changes = merge(load_json(target), desired("/v", permissions=False))
    assert changes == []  # caller skips write_json, so no backup is made
```

Run: `cd setup && uv run pytest -q 2>&1 | tail -3`
Expected: collection errors (`ModuleNotFoundError: planner_setup.settings`).

- [ ] **Step 3: Implement `setup/src/planner_setup/settings.py`**

```python
"""Pure functions over settings dicts: what setup wants, and merging it in."""
from __future__ import annotations

import copy

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


def merge(current: dict, wanted: dict) -> tuple[dict, list[str]]:
    """Merge `wanted` into a copy of `current`. Change lines name keys, never values."""
    out = copy.deepcopy(current)
    changes: list[str] = []

    configs = out.setdefault("pluginConfigs", {})
    for plugin_id, block in wanted.get("pluginConfigs", {}).items():
        options = configs.setdefault(plugin_id, {}).setdefault("options", {})
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
        have = out.setdefault("permissions", {})
        for key, values in perms.items():
            current_list = have.setdefault(key, [])
            for v in values:
                if v not in current_list:
                    current_list.append(v)
                    # The vault path is a value too: name the key, not the path.
                    changes.append(f"permissions.{key}: add {v}" if key == "allow" else f"permissions.{key}: add vault")
    return out, changes
```

- [ ] **Step 4: Implement `setup/src/planner_setup/files.py`**

```python
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
    return home / ".claude" / "backups" / time.strftime("%Y%m%d%H%M%S")


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
```

- [ ] **Step 5: Run the tests**

Run: `cd setup && uv run pytest -q 2>&1 | tail -3`
Expected: `12 passed`.

- [ ] **Step 6: Commit**

```bash
git add setup/pyproject.toml setup/uv.lock setup/src/planner_setup/__init__.py setup/src/planner_setup/settings.py setup/src/planner_setup/files.py setup/tests/test_settings.py setup/tests/test_files.py
git commit -m "feat(setup): planner-setup package with settings merge and safe writes"
```

---

### Task 6: Setup actions — paths, `claude` wrapper, the six actions

**Files:**
- Create: `setup/src/planner_setup/paths.py`, `setup/src/planner_setup/claude_cli.py`, `setup/src/planner_setup/actions.py`, `setup/tests/conftest.py`, `setup/tests/test_actions.py`
- Modify: `setup/pyproject.toml` (bundle `examples/`)

**Interfaces:**
- Consumes: Task 5's `settings.*` and `files.*`.
- Produces:
  - `paths.vault(env: Mapping[str, str], home: Path) -> Path` — `$VAULT` else `home/vault`, `~` expanded
  - `paths.examples() -> Path` — bundled `examples/` dir (installed) or repo `examples/` (checkout)
  - `paths.marketplace_source(cwd: Path) -> str` — `str(cwd)` if `cwd/.claude-plugin/marketplace.json` has name `adhd-planner`, else `"thetonymaster/adhd_planner"`
  - `claude_cli.Result(code: int, out: str, err: str)`; `claude_cli.run(*args: str) -> Result`; `claude_cli.available() -> bool`
  - `actions.Ctx(home: Path, cwd: Path, env: Mapping[str, str], yes: bool, dry_run: bool, confirm: Callable[[str], bool], say: Callable[[str], None])`
  - `actions.status(ctx) -> int`, `actions.install(ctx, plugins: Sequence[str]) -> int`, `actions.configure(ctx, vault: Path, permissions: bool) -> int`, `actions.seed_vault(ctx, vault: Path) -> int`, `actions.claude_md(ctx) -> int`, `actions.cowork(ctx) -> int` — return a process exit code

- [ ] **Step 1: Bundle `examples/` into the wheel**

Append to `setup/pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"../examples" = "planner_setup/examples"
"../docs/setup.md" = "planner_setup/examples/setup.md"
```

`docs/setup.md` is written in Task 7. Create a one-line stub now so the build works:
`printf '# Setup\n' > docs/setup.md`.

Run: `cd setup && rm -rf dist && uv build --wheel -q && unzip -l dist/*.whl | grep -E 'examples/(CLAUDE.md|vault-starter/Tasks/set-up-vault.md|setup.md)'`
Expected: three lines. If hatchling refuses `../`, **stop and report**; do not copy
`examples/` into `setup/` (two copies would drift).

- [ ] **Step 2: Write the shared fixture and failing tests**

`setup/tests/conftest.py` creates a fake `claude` that records its argv and replies from
files the test writes:

```python
import json
import os
import stat
from pathlib import Path

import pytest

from planner_setup.actions import Ctx

FAKE = """#!/usr/bin/env python3
import json, os, sys, pathlib
d = pathlib.Path(os.environ["FAKE_CLAUDE_DIR"])
with open(d / "calls.jsonl", "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
key = "_".join(a for a in sys.argv[1:] if not a.startswith("-")).replace("/", "_")[:60]
reply = d / f"{key}.json"
if reply.exists():
    r = json.loads(reply.read_text())
    sys.stdout.write(r.get("out", "")); sys.stderr.write(r.get("err", "")); sys.exit(r.get("code", 0))
sys.stdout.write("[]" if "--json" in sys.argv else "")
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    d = tmp_path / "fakebin"
    d.mkdir()
    exe = d / "claude"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_DIR", str(d))

    class Fake:
        dir = d
        def reply(self, key, out="", err="", code=0):
            (d / f"{key}.json").write_text(json.dumps({"out": out, "err": err, "code": code}))
        def calls(self):
            p = d / "calls.jsonl"
            return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    return Fake()


@pytest.fixture
def ctx(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    lines: list[str] = []
    c = Ctx(home=home, cwd=tmp_path, env={}, yes=True, dry_run=False,
            confirm=lambda _q: True, say=lines.append)
    c.lines = lines  # type: ignore[attr-defined]
    return c
```

`setup/tests/test_actions.py`:

```python
import json
from dataclasses import replace

from planner_setup import actions, paths


def text(ctx):
    return "\n".join(ctx.lines)


def test_vault_path_resolution(tmp_path):
    assert paths.vault({}, tmp_path) == tmp_path / "vault"
    assert paths.vault({"VAULT": "~/notes"}, tmp_path) == tmp_path / "notes"


def test_marketplace_source_prefers_checkout(tmp_path):
    assert paths.marketplace_source(tmp_path) == "thetonymaster/adhd_planner"
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text('{"name": "adhd-planner"}')
    assert paths.marketplace_source(tmp_path) == str(tmp_path)


def test_examples_dir_has_the_starter():
    assert (paths.examples() / "vault-starter" / "Tasks" / "set-up-vault.md").is_file()


def test_status_reports_everything_missing(ctx, fake_claude):
    assert actions.status(ctx) == 0
    out = text(ctx)
    assert "marketplace adhd-planner: not added" in out
    for p in ("planner", "tasks", "task-track"):
        assert f"{p}: not installed" in out
    assert "vault: " in out and "missing" in out


def test_status_reads_installed_state(ctx, fake_claude):
    fake_claude.reply("plugin_marketplace_list", out=json.dumps([{"name": "adhd-planner"}]))
    fake_claude.reply("plugin_list", out=json.dumps([
        {"id": "tasks@adhd-planner", "enabled": True},
        {"id": "planner@adhd-planner", "enabled": False}]))
    actions.status(ctx)
    out = text(ctx)
    assert "marketplace adhd-planner: added" in out
    assert "tasks: enabled" in out and "planner: installed, disabled" in out


def test_install_adds_marketplace_then_plugins(ctx, fake_claude):
    assert actions.install(ctx, ["planner", "tasks"]) == 0
    calls = fake_claude.calls()
    assert ["plugin", "marketplace", "add", "thetonymaster/adhd_planner"] in calls
    assert ["plugin", "install", "planner@adhd-planner"] in calls
    assert ["plugin", "install", "tasks@adhd-planner"] in calls
    assert ["plugin", "install", "task-track@adhd-planner"] not in calls


def test_install_skips_what_is_already_there(ctx, fake_claude):
    fake_claude.reply("plugin_marketplace_list", out=json.dumps([{"name": "adhd-planner"}]))
    fake_claude.reply("plugin_list", out=json.dumps([{"id": "tasks@adhd-planner", "enabled": True}]))
    actions.install(ctx, ["tasks"])
    assert not any(c[:2] == ["plugin", "install"] or c[:3] == ["plugin", "marketplace", "add"]
                   for c in fake_claude.calls())


def test_install_surfaces_claude_stderr_and_stops(ctx, fake_claude):
    fake_claude.reply("plugin_marketplace_add_thetonymaster_adhd_planner", err="auth required", code=1)
    assert actions.install(ctx, ["planner"]) == 1
    assert "auth required" in text(ctx)
    assert ["plugin", "install", "planner@adhd-planner"] not in fake_claude.calls()


def test_install_without_claude_says_so(ctx, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert actions.install(ctx, ["planner"]) == 1
    assert "claude: not found on PATH" in text(ctx)


def test_configure_writes_settings_with_backup(ctx):
    settings = ctx.home / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"model": "opus"}')
    assert actions.configure(ctx, ctx.home / "vault", permissions=True) == 0
    data = json.loads(settings.read_text())
    assert data["model"] == "opus"
    assert data["pluginConfigs"]["tasks@adhd-planner"]["options"]["vaultPath"] == str(ctx.home / "vault")
    assert list((ctx.home / ".claude" / "backups").glob("*/.claude/settings.json"))


def test_configure_dry_run_writes_nothing(ctx):
    c = replace(ctx, dry_run=True)
    c.lines = ctx.lines
    actions.configure(c, ctx.home / "vault", permissions=False)
    assert not (ctx.home / ".claude" / "settings.json").exists()
    assert "would change" in text(ctx).lower()


def test_configure_declined_writes_nothing(ctx):
    c = replace(ctx, yes=False, confirm=lambda _q: False)
    c.lines = ctx.lines
    assert actions.configure(c, ctx.home / "vault", permissions=False) == 1
    assert not (ctx.home / ".claude" / "settings.json").exists()


def test_configure_twice_makes_one_backup_at_most(ctx):
    actions.configure(ctx, ctx.home / "vault", permissions=False)
    actions.configure(ctx, ctx.home / "vault", permissions=False)
    assert "nothing to change" in text(ctx).lower()
    assert not (ctx.home / ".claude" / "backups").exists()  # first write had no file to back up


def test_seed_vault_copies_once(ctx):
    v = ctx.home / "vault"
    assert actions.seed_vault(ctx, v) == 0
    assert (v / "Tasks" / "set-up-vault.md").is_file()
    assert (v / ".claude" / "CLAUDE.md").is_file() and not (v / "_claude").exists()
    (v / "Tasks" / "set-up-vault.md").write_text("mine")
    assert actions.seed_vault(ctx, v) == 0
    assert (v / "Tasks" / "set-up-vault.md").read_text() == "mine"
    assert "already exists" in text(ctx)


def test_claude_md_never_overwrites(ctx):
    target = ctx.home / ".claude" / "CLAUDE.md"
    assert actions.claude_md(ctx) == 0 and target.read_text().startswith("> Example")
    target.write_text("Q's own")
    actions.claude_md(ctx)
    assert target.read_text() == "Q's own"
    assert "kept your" in text(ctx)


def test_cowork_prints_the_steps(ctx):
    actions.cowork(ctx)
    assert "thetonymaster/adhd_planner" in text(ctx)
```

Run: `cd setup && uv run pytest -q 2>&1 | tail -3`
Expected: collection error `ModuleNotFoundError: planner_setup.actions`.

- [ ] **Step 3: Implement `paths.py` and `claude_cli.py`**

`setup/src/planner_setup/paths.py`:

```python
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
```

`setup/src/planner_setup/claude_cli.py`:

```python
"""The `claude` CLI, as a function returning what it printed."""
from __future__ import annotations

import shutil
import subprocess
from typing import NamedTuple


class Result(NamedTuple):
    code: int
    out: str
    err: str


def available() -> bool:
    return shutil.which("claude") is not None


def run(*args: str) -> Result:
    p = subprocess.run(["claude", *args], capture_output=True, text=True, timeout=300)
    return Result(p.returncode, p.stdout, p.stderr)
```

- [ ] **Step 4: Implement `actions.py`**

```python
"""The six things setup can do. Each returns an exit code and talks through ctx.say."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import claude_cli, files, paths, settings


@dataclass
class Ctx:
    home: Path
    cwd: Path
    env: Mapping[str, str]
    yes: bool
    dry_run: bool
    confirm: Callable[[str], bool]
    say: Callable[[str], None]

    @property
    def settings_path(self) -> Path:
        return self.home / ".claude" / "settings.json"


def _json(ctx: Ctx, *args: str) -> list | None:
    r = claude_cli.run(*args, "--json")
    if r.code != 0:
        ctx.say(f"`claude {' '.join(args)} --json` failed (exit {r.code}): {r.err.strip()}")
        return None
    try:
        return json.loads(r.out or "[]")
    except ValueError as err:
        ctx.say(f"`claude {' '.join(args)} --json` printed non-JSON ({err}): {r.out[:200]!r}")
        return None


def _state(ctx: Ctx) -> tuple[bool, dict[str, bool]] | None:
    """(marketplace added, {plugin: enabled}) or None if claude could not be asked."""
    markets = _json(ctx, "plugin", "marketplace", "list")
    plugins = _json(ctx, "plugin", "list")
    if markets is None or plugins is None:
        return None
    added = any(m.get("name") == settings.MARKETPLACE for m in markets)
    suffix = "@" + settings.MARKETPLACE
    installed = {p["id"][: -len(suffix)]: bool(p.get("enabled")) for p in plugins if p.get("id", "").endswith(suffix)}
    return added, installed


def status(ctx: Ctx) -> int:
    if not claude_cli.available():
        ctx.say("claude: not found on PATH (plugin state unknown)")
    else:
        state = _state(ctx)
        if state is not None:
            added, installed = state
            ctx.say(f"marketplace {settings.MARKETPLACE}: {'added' if added else 'not added'}")
            for p in settings.PLUGINS:
                ctx.say(f"  {p}: " + ("not installed" if p not in installed
                                      else "enabled" if installed[p] else "installed, disabled"))
    current = files.load_json(ctx.settings_path)
    configured = current.get("pluginConfigs", {}).get(f"tasks@{settings.MARKETPLACE}", {}).get("options", {}).get("vaultPath")
    vault = Path(configured) if configured else paths.vault(ctx.env, ctx.home)
    ctx.say(f"vault: {vault} ({'exists' if vault.is_dir() else 'missing'}; {'from settings' if configured else 'default'})")
    dirs = current.get("permissions", {}).get("additionalDirectories", [])
    ctx.say(f"vault in additionalDirectories: {'yes' if str(vault) in dirs else 'no (the tasks hook approves vault access per session)'}")
    return 0


def install(ctx: Ctx, plugins: Sequence[str]) -> int:
    if not claude_cli.available():
        ctx.say("claude: not found on PATH. Install Claude Code, then rerun.")
        return 1
    state = _state(ctx)
    if state is None:
        return 1
    added, installed = state
    steps: list[tuple[str, ...]] = []
    if not added:
        steps.append(("plugin", "marketplace", "add", paths.marketplace_source(ctx.cwd)))
    steps += [("plugin", "install", f"{p}@{settings.MARKETPLACE}") for p in plugins if p not in installed]
    if not steps:
        ctx.say("Nothing to install: marketplace and plugins are already there.")
        return 0
    for s in steps:
        ctx.say(("would run: " if ctx.dry_run else "run: ") + "claude " + " ".join(s))
    if ctx.dry_run or not (ctx.yes or ctx.confirm("Run these?")):
        return 0 if ctx.dry_run else 1
    for s in steps:
        r = claude_cli.run(*s)
        if r.code != 0:
            ctx.say(f"`claude {' '.join(s)}` failed (exit {r.code}):\n{r.err.strip() or r.out.strip()}")
            return 1
    ctx.say("Done. Start a new `claude` session to load the plugins.")
    return 0


def configure(ctx: Ctx, vault: Path, permissions: bool) -> int:
    current = files.load_json(ctx.settings_path)
    merged, changes = settings.merge(current, settings.desired(str(vault), permissions=permissions))
    if not changes:
        ctx.say(f"Nothing to change in {ctx.settings_path}.")
        return 0
    ctx.say(("Would change " if ctx.dry_run else "Will change ") + f"{ctx.settings_path}:")
    for c in changes:
        ctx.say(f"  - {c}")
    if ctx.dry_run:
        return 0
    if not (ctx.yes or ctx.confirm("Write these changes?")):
        ctx.say("Nothing written.")
        return 1
    saved = files.write_json(ctx.settings_path, merged, files.backup_dir(ctx.home), home=ctx.home)
    if saved:
        ctx.say(f"Backup: {saved}")
    ctx.say("Done. Running sessions pick this up after a restart.")
    return 0


def seed_vault(ctx: Ctx, vault: Path) -> int:
    if vault.exists():
        ctx.say(f"{vault} already exists; left as is.")
        return 0
    ctx.say(("Would create " if ctx.dry_run else "Create ") + f"a starter vault at {vault}")
    if ctx.dry_run or not (ctx.yes or ctx.confirm("Create it?")):
        return 0 if ctx.dry_run else 1
    shutil.copytree(paths.examples() / "vault-starter", vault)
    (vault / "_claude").rename(vault / ".claude")
    ctx.say(f"Vault created at {vault}. Open it in Obsidian: Open folder as vault.")
    return 0


def claude_md(ctx: Ctx) -> int:
    example = paths.examples() / "CLAUDE.md"
    target = ctx.home / ".claude" / "CLAUDE.md"
    if target.exists():
        ctx.say(f"{target} exists; kept your file. Compare with: diff {target} {example}")
        return 0
    ctx.say(("Would copy " if ctx.dry_run else "Copy ") + f"{example} → {target}")
    if ctx.dry_run or not (ctx.yes or ctx.confirm("Copy it?")):
        return 0 if ctx.dry_run else 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(example, target)
    ctx.say("Copied. Edit it: it is written for one person (Q).")
    return 0


def cowork(ctx: Ctx) -> int:
    ctx.say("\n".join([
        "In Claude Desktop → Cowork:",
        f"  1. Customize → Plugins → Add marketplace → {paths.GITHUB}",
        "  2. Install `planner` and `tasks` (task-track is Claude Code only).",
        "  3. Connect your vault folder to the session.",
        '  4. Try: "add a note to <task>: test".',
        "If adding the marketplace fails (private repo), see setup.md → Cowork fallback.",
    ]))
    return 0
```

- [ ] **Step 5: Run the tests**

Run: `cd setup && uv run pytest -q 2>&1 | tail -3`
Expected: `28 passed` (12 from Task 5 + 16 here).

- [ ] **Step 6: Commit**

```bash
git add setup/pyproject.toml setup/src/planner_setup/paths.py setup/src/planner_setup/claude_cli.py setup/src/planner_setup/actions.py setup/tests/conftest.py setup/tests/test_actions.py docs/setup.md
git commit -m "feat(setup): status, install, settings, vault, CLAUDE.md and Cowork actions"
```

---

### Task 7: Menu, docs, remove the old installer

**Files:**
- Create: `setup/src/planner_setup/cli.py`, `setup/tests/test_cli.py`, `examples/settings.example.json`
- Modify: `docs/setup.md` (full content), `plugins/planner/README.md` (install section)
- Delete: `claude-config/install.sh`, `claude-config/merge-settings.py`, `claude-config/settings.snippet.json` (then `claude-config/` is gone)

**Interfaces:**
- Consumes: `actions.*`, `paths.*`, `settings.PLUGINS`.
- Produces: `cli.main(argv: list[str] | None = None) -> int`. Subcommands: `status`, `install [--plugins …]`, `settings [--vault PATH] [--permissions]`, `vault [--vault PATH]`, `claude-md`, `cowork`. Global flags: `--yes`, `--dry-run`. No subcommand → menu.

- [ ] **Step 1: Write the failing tests** — `setup/tests/test_cli.py`

```python
import json

from planner_setup import cli


def test_status_subcommand_runs(tmp_path, monkeypatch, fake_claude, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["status"]) == 0
    assert "marketplace adhd-planner" in capsys.readouterr().out


def test_settings_subcommand_with_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["--yes", "settings", "--vault", str(tmp_path / "v"), "--permissions"]) == 0
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert data["permissions"]["additionalDirectories"] == [str(tmp_path / "v")]


def test_install_defaults_to_all_plugins(tmp_path, monkeypatch, fake_claude):
    monkeypatch.setenv("HOME", str(tmp_path))
    cli.main(["--yes", "install"])
    installs = [c[2] for c in fake_claude.calls() if c[:2] == ["plugin", "install"]]
    assert installs == ["planner@adhd-planner", "tasks@adhd-planner", "task-track@adhd-planner"]


def test_unknown_plugin_is_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    try:
        cli.main(["install", "--plugins", "nope"])
    except SystemExit as e:
        assert e.code == 2
    assert "invalid choice: 'nope'" in capsys.readouterr().err


def test_invalid_settings_json_aborts_with_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{bad")
    try:
        cli.main(["--yes", "settings", "--vault", "/v"])
        raise AssertionError("expected SystemExit")
    except SystemExit as e:
        assert "settings.json is not valid JSON" in str(e.code)
```

Run: `cd setup && uv run pytest tests/test_cli.py -q 2>&1 | tail -3`
Expected: `ModuleNotFoundError: planner_setup.cli`.

- [ ] **Step 2: Implement `setup/src/planner_setup/cli.py`**

```python
"""planner-setup: a menu (no arguments) or subcommands over the same actions."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import actions, paths, settings

MENU = ("Status", "Install plugins (Claude Code)", "Settings (vault path, permissions)",
        "Vault starter", "Example CLAUDE.md", "Cowork steps", "Quit")


def _ctx(args: argparse.Namespace, confirm=None) -> actions.Ctx:
    return actions.Ctx(home=Path.home(), cwd=Path.cwd(), env=os.environ, yes=args.yes, dry_run=args.dry_run,
                       confirm=confirm or (lambda q: input(f"{q} [y/N] ").strip().lower() == "y"), say=print)


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="planner-setup", description=__doc__)
    ap.add_argument("--yes", action="store_true", help="do not ask before writing")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    p = sub.add_parser("install")
    p.add_argument("--plugins", nargs="+", choices=settings.PLUGINS, default=list(settings.PLUGINS))
    p = sub.add_parser("settings")
    p.add_argument("--vault", type=Path)
    p.add_argument("--permissions", action="store_true", help="also add the vault to additionalDirectories and allow Bash(obsidian:*)")
    p = sub.add_parser("vault")
    p.add_argument("--vault", type=Path)
    sub.add_parser("claude-md")
    sub.add_parser("cowork")
    return ap


def _menu(args: argparse.Namespace) -> int:
    import questionary  # only the menu needs it

    ctx = _ctx(args, confirm=lambda q: bool(questionary.confirm(q, default=False).ask()))
    default_vault = str(paths.vault(os.environ, Path.home()))
    while True:
        choice = questionary.select("planner-setup", choices=list(MENU)).ask()
        if choice in (None, "Quit"):
            return 0
        if choice == "Status":
            actions.status(ctx)
        elif choice.startswith("Install"):
            picked = questionary.checkbox("Plugins", choices=[
                questionary.Choice(p, checked=True) for p in settings.PLUGINS]).ask() or []
            actions.install(ctx, picked)
        elif choice.startswith("Settings"):
            vault = questionary.path("Vault path", default=default_vault, only_directories=True).ask()
            if vault:
                perms = bool(questionary.confirm("Also add it to additionalDirectories and allow Bash(obsidian:*)?",
                                                 default=False).ask())
                actions.configure(ctx, Path(os.path.expanduser(vault)), perms)
        elif choice == "Vault starter":
            vault = questionary.path("Create the starter vault at", default=default_vault).ask()
            if vault:
                actions.seed_vault(ctx, Path(os.path.expanduser(vault)))
        elif choice == "Example CLAUDE.md":
            actions.claude_md(ctx)
        elif choice == "Cowork steps":
            actions.cowork(ctx)
        print()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd is None:
        if not sys.stdin.isatty():
            print("planner-setup: no terminal for the menu; pass a subcommand (see --help).", file=sys.stderr)
            return 2
        return _menu(args)
    ctx = _ctx(args)
    vault = getattr(args, "vault", None) or paths.vault(os.environ, ctx.home)
    vault = Path(os.path.expanduser(str(vault)))
    return {
        "status": lambda: actions.status(ctx),
        "install": lambda: actions.install(ctx, args.plugins),
        "settings": lambda: actions.configure(ctx, vault, args.permissions),
        "vault": lambda: actions.seed_vault(ctx, vault),
        "claude-md": lambda: actions.claude_md(ctx),
        "cowork": lambda: actions.cowork(ctx),
    }[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run all setup tests**

Run: `cd setup && uv run pytest -q 2>&1 | tail -3`
Expected: `33 passed`.

- [ ] **Step 4: Run via uvx from the checkout against a temp HOME**

```bash
T=$(mktemp -d); HOME=$T uvx --from ./setup planner-setup status; HOME=$T uvx --from ./setup planner-setup --dry-run settings --permissions; echo "exit $?"; rm -rf "$T"
```

Expected:
- `status` lists the marketplace and the 3 plugins.
- The vault line ends `missing; default)`.
- `--dry-run settings` prints `Would change …settings.json:` and 4 change lines.
- The last line is `exit 0`.

The `claude` used here is your real binary, but only for read-only `list --json` calls.

- [ ] **Step 5: Write `docs/setup.md`**

Its sections must contain:

1. **Claude Code, with the menu.**
   - `uvx --from "git+ssh://git@github.com/thetonymaster/adhd_planner#subdirectory=setup" planner-setup`
   - From a checkout: `uvx --from ./setup planner-setup`
   - One line per menu item.
2. **Claude Code, by hand.**
   - `claude plugin marketplace add thetonymaster/adhd_planner`
   - `claude plugin install planner@adhd-planner`, then the same for `tasks` and `task-track`
   - Set `vaultPath` in `/config`, or in `pluginConfigs` (show the JSON).
3. **Settings plugins can't carry.**
   - Point to `examples/settings.example.json`.
   - Say the PermissionRequest hook approves vault access per session, and
     `additionalDirectories` makes it permanent.
4. **Cowork.**
   - The four steps from `actions.cowork`.
   - **Cowork fallback:** if the private repo can't be added, run `bash scripts/build-plugin.sh`
     and upload `planner.plugin` (Customize → Plugins → Upload).
5. **What each plugin needs.**
   - planner: python3 + reportlab for printing, Google Calendar connector.
   - tasks: python3 for the hooks; without it, they degrade to the time only.
   - task-track: Claude Code only.

- [ ] **Step 6: Write `examples/settings.example.json`**

```json
{
  "//": "Copy the parts you want into ~/.claude/settings.json. planner-setup's Settings item writes the same keys.",
  "permissions": {
    "additionalDirectories": ["~/vault"],
    "allow": ["Bash(obsidian:*)"]
  },
  "pluginConfigs": {
    "tasks@adhd-planner": { "options": { "vaultPath": "~/vault" } },
    "task-track@adhd-planner": { "options": { "vaultPath": "~/vault" } }
  }
}
```

- [ ] **Step 7: Remove the old installer; point the planner README at setup.md**

```bash
git rm -q claude-config/install.sh claude-config/merge-settings.py claude-config/settings.snippet.json
test ! -e claude-config && echo "claude-config gone"
```

In `plugins/planner/README.md`, add after the intro paragraph:
`Install: see [docs/setup.md](../../docs/setup.md) (Claude Code: \`claude plugin install planner@adhd-planner\`; Cowork: add the marketplace \`thetonymaster/adhd_planner\`).`

- [ ] **Step 8: Full repo check**

```bash
claude plugin validate . && for p in planner tasks task-track; do claude plugin validate plugins/$p || exit 1; done
python3 -m unittest discover -s tests 2>&1 | tail -1
(cd plugins/task-track && claude plugin test . 2>&1 | grep -E '^ *[0-9]+ (pass|fail)')
(cd setup && uv run pytest -q 2>&1 | tail -1)
(cd setup && rm -rf dist && uv build --wheel -q && unzip -l dist/*.whl | grep -c 'planner_setup/examples/')
git grep -n -E 'claude-config|merge-settings|install\.sh' -- ':!docs/superpowers'
```

Expected:
- 4× `✔ Validation passed`
- unittest `OK`
- task-track `98 pass` / `0 fail`
- setup `33 passed`
- examples count > 20
- the final grep prints nothing

- [ ] **Step 9: Commit**

```bash
git add setup/src/planner_setup/cli.py setup/tests/test_cli.py docs/setup.md examples/settings.example.json plugins/planner/README.md
git commit -m "feat(setup): planner-setup menu and docs; retire install.sh and merge-settings.py"
```

---

### Task 8: Rollout on Q's machine (needs Q)

Touches real state: `~/.claude`. **Each deletion waits for Q's explicit yes on the exact list.**

- [ ] **Step 1: Show the old install**

```bash
jq '{env: .env.CLAUDE_CODE_PLUGIN_DIRS, SessionStart: .hooks.SessionStart, UserPromptSubmit: .hooks.UserPromptSubmit}' ~/.claude/settings.json
ls -d ~/.claude/hooks/load-task.sh ~/.claude/skills/{task-start,task-park,task-switch,obsidian-vault} 2>&1
```

Show Q the output and the removal list:
- the `load-task.sh` and `date` hook entries
- the task-track path in `CLAUDE_CODE_PLUGIN_DIRS` (the key goes if nothing else remains)
- the hook file and the 4 skill dirs

Ask Q to confirm. Stop until Q says yes.

- [ ] **Step 2: Back up and remove (after Q's yes)**

```bash
B=~/.claude/backups/$(date +%Y%m%d%H%M%S)-pre-marketplace; mkdir -p "$B/skills" "$B/hooks"
cp ~/.claude/settings.json "$B/settings.json"
mv ~/.claude/hooks/load-task.sh "$B/hooks/"
for s in task-start task-park task-switch obsidian-vault; do mv ~/.claude/skills/$s "$B/skills/"; done
python3 - <<'PY'
import json, os, pathlib
p = pathlib.Path.home() / ".claude" / "settings.json"
s = json.loads(p.read_text())
drop = lambda c: c.endswith("hooks/load-task.sh") or c == "date '+Now: %H:%M'"
for ev in ("SessionStart", "UserPromptSubmit"):
    groups = [{**g, "hooks": [h for h in g["hooks"] if not drop(h.get("command", ""))]} for g in s.get("hooks", {}).get(ev, [])]
    groups = [g for g in groups if g["hooks"]]
    if groups: s["hooks"][ev] = groups
    else: s.get("hooks", {}).pop(ev, None)
dirs = [d for d in s.get("env", {}).get("CLAUDE_CODE_PLUGIN_DIRS", "").split(os.pathsep) if d and not d.rstrip("/").endswith("task-track")]
if dirs: s["env"]["CLAUDE_CODE_PLUGIN_DIRS"] = os.pathsep.join(dirs)
else: s.get("env", {}).pop("CLAUDE_CODE_PLUGIN_DIRS", None)
tmp = p.with_suffix(".json.tmp"); tmp.write_text(json.dumps(s, indent=2) + "\n"); json.loads(tmp.read_text()); tmp.replace(p)
PY
echo "backup: $B"; jq '{env, hooks: (.hooks|keys)}' ~/.claude/settings.json
```

Expected: `hooks` keys no longer include `SessionStart`/`UserPromptSubmit` (unless Q has
other hooks there), and `env` has no task-track path.

- [ ] **Step 3: Install with uvx**

The branch is not pushed. Install from the checkout:

```bash
cd ~/personal/adhd_planner && uvx --from ./setup planner-setup --yes install
uvx --from ./setup planner-setup --yes settings --vault ~/vault --permissions
uvx --from ./setup planner-setup status
```

Expected: the marketplace is added (source = this checkout) and all 3 plugins are enabled.
The `--permissions` keys may already exist in Q's settings, in which case they're reported
as no change.

- [ ] **Step 4: Live check in a new session** (Q starts `claude` in this repo)

Check each of these:
- [ ] SessionStart shows `Active task: …` **once**.
- [ ] Each prompt shows `Now: HH:MM` **once**.
- [ ] `/tasks:task-park` appears in `/` completion.
- [ ] The task-track band shows; its Park button submits `/tasks:task-park` and it runs.
- [ ] "add a note to <active task>: marketplace test" → task-note appends the Log line.
- [ ] Remove `~/vault` from `additionalDirectories` temporarily (or use a fresh project
      without it). Then ask Claude to read a vault note: no prompt appears, and
      `/permissions` shows the vault as a session directory. If a prompt still appears,
      stop and report the raw hook output from `claude --debug` (the `updatedPermissions`
      shape is inferred from the docs table).

- [ ] **Step 5: Update the task note**

Following the `obsidian-vault` skill, write the result to the active task note's `## Log`.

---

### Task 9: Cowork check and `build-plugin.sh` decision (needs Q)

- [ ] **Step 1: Push the branch**

Only after Q says to push. Cowork pulls from GitHub, so it can't see an unpushed branch.
Cowork reads the default branch, so either merge first or check whether Add marketplace
accepts a ref. Ask Q which.

- [ ] **Step 2: Q runs the Cowork steps** (`uvx --from ./setup planner-setup cowork` prints them)

Record each of these as PASS or FAIL with the exact message:
- marketplace added
- `planner` + `tasks` installed
- a session with the vault connected shows no hook error
- "add a note to set-up-vault: test" lands in the note

- [ ] **Step 3: Decide**

- **Private marketplace worked:** `git rm scripts/build-plugin.sh planner.plugin`, remove the
  fallback paragraph from `docs/setup.md` and the last line of `actions.cowork`
  (plus its test assertion if any), run the Task 7 Step 8 checks, then commit:
  `chore(planner): drop the zip build now that Cowork installs from the marketplace`.
- **It failed:** keep both, and add the failure message to `docs/setup.md`'s fallback
  section. Then ask Q whether to extend `build-plugin.sh` to zip `plugins/tasks` too
  (a separate change).
