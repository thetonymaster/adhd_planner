# vault-allow hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `tasks` PermissionRequest hook auto-approves only note reads/writes inside a sane vault, and no task slug from a vault file can name a path outside `Tasks/`.

**Architecture:** `vault-allow.py` keeps its shape (stdin JSON → optional allow JSON) but gains two pure rule functions (`may_read`, `may_write`) over the path's parts relative to the vault root, and a stricter `vault_roots()` that fails closed. Slug validation is one rule (`^[a-z0-9][a-z0-9-]*$`) applied where `.active`, `.session/<id>` and `.pomo.json` slugs are read, in Python (`vaults.py`, `session_task.py`, `load-task.sh`) and TypeScript (`resolve.ts`, used by `register.tsx`).

**Tech Stack:** Python 3 stdlib + `unittest`; bash; TypeScript Claude Code mod tested with `claude plugin test`; `setup/` is a uv project tested with pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-public-launch-design.md`, section "1. vault-allow hardening".

## Global Constraints

- Slug rule, identical everywhere: `^[a-z0-9][a-z0-9-]*$` (the existing `vaults.NAME` / `VAULT_NAME` regex).
- Approved writes: `*.md` and `*.canvas`, no path segment under the root starting with `.`, file name not `CLAUDE.md`; or exactly `Tasks/.active`, `Tasks/.pomo.json`, `Tasks/.session/<one segment>`.
- Approved reads (Read/Glob/Grep): no path segment under the root starting with `.`.
- The allow decision carries **no** `updatedPermissions`.
- Untrusted root: relative, `/`, `$HOME` or an ancestor of it, or inside/equal to `~/.claude` (or `$CLAUDE_CONFIG_DIR`).
- `vaults.json` with an error, or the config file lying inside a candidate root → no root is trusted.
- The hook always exits 0 and prints nothing when it does not approve.
- Bump `tasks` 0.1.0 → 0.2.0 and `task-track` 0.1.2 → 0.2.0 (behaviour change).
- Do not edit `planner.plugin` or `setup/uv.lock`. Run `claude plugin validate plugins/<name>` after touching a plugin.
- Commits: one per task, conventional prefix, `git add` files individually, no AI attribution lines.

**Deviation from the spec (flag to Q at review):** the spec says a slug must also "name an existing note". The existing behaviour already reports a safe-but-missing slug as `Active task 'x' has no note at …` without reading anything, which is more useful than silently showing "No active task". The plan therefore validates the **pattern** only (that alone stops traversal) and keeps the "has no note" message.

**Addition to the spec:** a root inside `~/.claude` is refused too. Otherwise `VAULT=~/.claude` would let the model write `skills/*/SKILL.md` and `rules/*.md` unprompted.

## Review Focus

1. **A vault on iCloud through a symlink**: `~/vault` → `~/Library/Mobile Documents/…/vault`. Reads and writes of notes must still be approved, because every path is `realpath`ed before the rules run. Pinned in Task 1.
2. **Root itself as the path**: `Glob` or `Grep` with `path` = the vault root has no relative parts. It must be approved for search and never treated as a write target. Pinned in Task 1.
3. **A note in a folder with a dot in its middle**, like `Projects/v1.2/plan.md`: only segments that *start* with `.` are hidden, so this one is approved. Pinned in Task 1.
4. **`$HOME` reached through a symlink**, as when macOS `/tmp` resolves to `/private/tmp`, or a home on a symlinked volume. The unsafe-root check compares realpaths on both sides. Pinned in Task 2.
5. **A pre-existing `.active` holding a slug with a trailing newline or spaces**: it is still valid after `strip()`. Pinned in Task 3 by the existing tests that write `"g\n"`.

---

### Task 1: Note-only approval rules, no addDirectories

**Files:**
- Modify: `plugins/tasks/hooks/vault-allow.py` (docstring, `main()`, new `may_read`, `may_write`, `parts_under`)
- Test: `tests/test_vault_allow.py`

**Interfaces:**
- Produces: `parts_under(path: str, root: str) -> tuple[str, ...]`, `may_read(parts) -> bool`, `may_write(parts) -> bool`, `WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}`. Task 2 reuses `inside()` and `main()` unchanged except for `vault_roots()`.

- [ ] **Step 1: Update the shared assertion and the tests whose expectations change**

In `tests/test_vault_allow.py`, replace `assertAllowed` with:

```python
    def assertAllowed(self, result):
        self.assertIsNotNone(result)
        out = result["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PermissionRequest")
        self.assertEqual(out["decision"], {"behavior": "allow"})
```

Replace `test_edit_write_notebook_grep_inside_are_allowed` with:

```python
    def test_edit_write_grep_inside_are_allowed(self):
        self.assertAllowed(self.ask("Edit", {"file_path": str(self.vault / "x.md")}))
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "new" / "y.md")}))
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "board.canvas")}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": str(self.vault)}))
```

In `test_symlinked_vault_and_tilde_option`, `test_a_path_in_the_second_vault_adds_that_vault`, `test_symlinked_second_vault_is_resolved` and `test_a_vault_nested_in_another_approves_and_adds_the_inner_one`, replace each `self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [...])` line with `self.assertAllowed(result)`. Rename the last three to `test_a_path_in_the_second_vault_is_allowed`, `test_a_symlinked_second_vault_is_resolved`, `test_a_vault_nested_in_another_is_allowed`.

- [ ] **Step 2: Add the failing rule tests**

Append to `VaultAllowTest`:

```python
    def test_writes_that_can_run_code_or_steer_claude_are_left_to_the_user(self):
        for rel in (".git/config", ".git/hooks/pre-commit", ".claude/settings.json",
                    ".obsidian/plugins/p/main.js", "CLAUDE.md", "Projects/CLAUDE.md",
                    "scripts/x.sh", "n.ipynb", ".obsidian/notes.md"):
            with self.subTest(rel):
                self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / rel)}))
                self.assertIsNone(self.ask("Edit", {"file_path": str(self.vault / rel)}))
        self.assertIsNone(self.ask("NotebookEdit", {"notebook_path": str(self.vault / "n.ipynb")}))

    def test_task_state_files_are_writable(self):
        for rel in ("Tasks/.active", "Tasks/.pomo.json", "Tasks/.session/abc-123"):
            with self.subTest(rel):
                self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / rel)}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "Tasks" / ".session" / "a" / "b")}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "Tasks" / ".other")}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "Notes" / ".active")}))

    def test_reads_skip_dot_paths(self):
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "Notes" / "a.md")}))
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "attachments" / "x.png")}))
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / ".obsidian" / "plugins" / "p" / "data.json")}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault / ".git")}))

    def test_a_dot_inside_a_segment_is_not_hidden(self):
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "Projects" / "v1.2" / "plan.md")}))

    def test_the_vault_root_itself_is_searchable_not_writable(self):
        self.assertAllowed(self.ask("Glob", {"pattern": "**/*.md", "path": str(self.vault)}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault)}))

    def test_notes_in_a_symlinked_vault_are_writable(self):
        real = self.home / "icloud" / "vault"
        real.mkdir(parents=True)
        os.symlink(real, self.home / "v")
        env = {"CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/v"}
        self.assertAllowed(self.ask("Write", {"file_path": str(self.home / "v" / "a.md")}, env_extra=env))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.home / "v" / ".git" / "config")}, env_extra=env))
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_vault_allow -v`
Expected: FAIL. `assertAllowed` sees `updatedPermissions` in the decision, and `.git/config`, `CLAUDE.md` and `scripts/x.sh` writes are allowed.

- [ ] **Step 4: Implement the rules**

In `plugins/tasks/hooks/vault-allow.py`, add `import pathlib`. Then add after `pattern_escapes`:

```python
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
NOTE_SUFFIXES = (".md", ".canvas")
# Dot-files the tasks skills and the task-track mod write.
STATE_FILES = {("Tasks", ".active"), ("Tasks", ".pomo.json")}


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
    return bool(parts) and not hidden(parts) and parts[-1].endswith(NOTE_SUFFIXES) and parts[-1] != "CLAUDE.md"
```

In `main()`, replace everything from `root = next(...)` to the end of the function with:

```python
    root = next((r for r in roots if paths and all(inside(p, r) for p in paths)), None)
    if root is None:
        return
    rule = may_write if tool in WRITE_TOOLS else may_read
    if not all(rule(parts_under(p, root)) for p in paths):
        return
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PermissionRequest",
        "decision": {"behavior": "allow"},
    }}, sys.stdout)
```

Replace the module docstring with:

```python
"""tasks plugin PermissionRequest hook: approve note reads and writes inside one vault.

Vaults: the ones registered in vaults.json (see vaults.py), else CLAUDE_PLUGIN_OPTION_VAULTPATH,
$VAULT or ~/vault; symlinks resolved. Reads and searches are approved unless a path segment under
the vault starts with '.'. Writes are approved only for *.md / *.canvas outside dot-folders (never
CLAUDE.md) and for Tasks/.active, Tasks/.pomo.json, Tasks/.session/<id>. Each call is decided on
its own: no working directory is added. Anything else prints nothing, so the normal permission
prompt appears. Always exits 0.
"""
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `python3 -m unittest tests.test_vault_allow -v`
Expected: all PASS.

- [ ] **Step 6: Run the whole Python suite**

Run: `python3 -m unittest discover -s tests`
Expected: `OK`. That is 53 tests plus the 6 new ones (the renamed tests keep the count otherwise).

- [ ] **Step 7: Commit**

```bash
git add plugins/tasks/hooks/vault-allow.py
git add tests/test_vault_allow.py
git commit -m "fix(tasks): vault-allow approves note reads/writes only, no addDirectories"
```

---

### Task 2: Trusted roots fail closed

**Files:**
- Modify: `plugins/tasks/hooks/vault-allow.py` (`vault_roots()`, new `unsafe_root()`, `main()` input check, `pattern_escapes()`)
- Test: `tests/test_vault_allow.py`

**Interfaces:**
- Consumes: `inside(path, root)` and `main()` from Task 1; `vaults.load_config(env, home) -> Config` (with `.error: str` and `.vaults[].path`) and `vaults.config_path(env, home) -> str`.
- Produces: `vault_roots(env, home) -> list[str]` (it now takes its inputs) and `unsafe_root(root: str, guarded: list[str]) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `VaultAllowTest`:

```python
    def test_home_root_and_ancestors_are_never_a_vault(self):
        (self.home / ".ssh").mkdir()
        for vault in (str(self.home), "/", str(self.home.parent)):
            with self.subTest(vault):
                self.assertIsNone(self.ask("Write", {"file_path": str(self.home / "notes.md")},
                                           env_extra={"VAULT": vault}))
                self.assertIsNone(self.ask("Read", {"file_path": str(self.home / ".ssh" / "id_rsa")},
                                           env_extra={"VAULT": vault}))

    def test_claude_config_is_never_a_vault(self):
        skills = self.home / ".claude" / "skills" / "x"
        skills.mkdir(parents=True)
        for vault in (str(self.home / ".claude"), str(self.home / ".claude" / "skills")):
            with self.subTest(vault):
                self.assertIsNone(self.ask("Write", {"file_path": str(skills / "SKILL.md")},
                                           env_extra={"VAULT": vault}))
        custom = self.home / "cfg"
        (custom / "rules").mkdir(parents=True)
        self.assertIsNone(self.ask("Write", {"file_path": str(custom / "rules" / "r.md")},
                                   env_extra={"VAULT": str(custom), "CLAUDE_CONFIG_DIR": str(custom)}))

    def test_a_relative_implicit_vault_approves_nothing(self):
        project = self.home / "project"
        project.mkdir()
        self.assertIsNone(self.ask_from(project, "Write", {"file_path": str(project / "a.md")}, {"VAULT": "."}))

    def test_a_vaults_json_inside_a_vault_approves_nothing(self):
        cfg = self.vault / "vaults.json"
        cfg.write_text(json.dumps({"vaults": {"personal": {"path": str(self.vault)}}}))
        env = {"ADHD_PLANNER_VAULTS": str(cfg)}
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "a.md")}, env_extra=env))
        self.assertIsNone(self.ask("Read", {"file_path": str(cfg)}, env_extra=env))

    def test_a_broken_config_approves_nothing(self):
        cfg = self.home / "vaults.json"
        cfg.write_text("{not json")
        env = {"ADHD_PLANNER_VAULTS": str(cfg)}
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / "a.md")}, env_extra=env))

    def test_json_that_is_not_an_object_exits_cleanly(self):
        for raw in (b"[1]", b"42", b'"x"', b"null"):
            with self.subTest(raw):
                self.assertIsNone(self.ask("Read", {}, raw=raw))

    def test_brace_or_dot_glob_patterns_are_left_to_the_user(self):
        self.assertIsNone(self.ask("Glob", {"pattern": "{..,x}/**", "path": str(self.vault)}))
        self.assertIsNone(self.ask("Glob", {"pattern": ".obsidian/**", "path": str(self.vault)}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault), "glob": "{a,../b}"}))
        self.assertAllowed(self.ask("Glob", {"pattern": "Projects/**/*.md", "path": str(self.vault)}))
```

Delete `test_a_broken_config_uses_only_the_single_vault`, which is replaced by `test_a_broken_config_approves_nothing`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_vault_allow -v`
Expected: FAIL in the home, `.claude`, vaults.json-inside, broken-config, non-object (`AttributeError`, exit 1) and brace-glob tests.

- [ ] **Step 3: Implement**

Replace `vault_roots()` and `pattern_escapes()` in `vault-allow.py` with:

```python
def unsafe_root(root, guarded):
    """A root that would expose home, the filesystem, or Claude's own config."""
    return root == "/" or any(inside(g, root) or inside(root, g) for g in guarded[1:]) or inside(guarded[0], root)


def vault_roots(env, home):
    """Trusted vault roots, symlinks resolved, deepest first. Empty when the config is broken,
    lives inside a vault, or a root is relative, `/`, home or an ancestor, or Claude's config."""
    config = vaults.load_config(env, home)
    if config.error:
        return []
    claude_dirs = [os.path.join(home, ".claude")] + ([env["CLAUDE_CONFIG_DIR"]] if env.get("CLAUDE_CONFIG_DIR") else [])
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


def pattern_escapes(pattern):
    """Absolute, home-relative, brace-expanding, or reaching a dot-segment (`..`, `.obsidian`)."""
    if pattern.startswith(("/", "~")) or "{" in pattern:
        return True
    return any(seg.startswith(".") for seg in pattern.replace("\\", "/").split("/"))
```

`unsafe_root` reads `guarded[0]` as home: a root is unsafe if home is inside it (home or an ancestor). `guarded[1:]` are Claude config dirs: unsafe if either contains the other.

In `main()`, change the input handling and the roots call:

```python
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
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python3 -m unittest tests.test_vault_allow -v`
Expected: all PASS. `test_a_relative_vault_path_does_not_approve_the_cwd` still passes (a relative path in vaults.json is a config error, which now approves nothing).

- [ ] **Step 5: Run the whole Python suite**

Run: `python3 -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add plugins/tasks/hooks/vault-allow.py
git add tests/test_vault_allow.py
git commit -m "fix(tasks): vault-allow trusts no root that is home, /, Claude config, or misconfigured"
```

---

### Task 3: Slug validation in the Python and bash resolvers

**Files:**
- Modify: `plugins/tasks/hooks/vaults.py` (new `slug_or_empty`, used in `read_state`)
- Modify: `plugins/tasks/hooks/session_task.py` (`fallback()`)
- Modify: `plugins/tasks/hooks/load-task.sh` (no-python path)
- Modify: `plugins/task-track/tests/fixtures/vault-cases.ts` (two shared cases)
- Test: `tests/test_vaults.py`, `tests/test_load_task.py`

**Interfaces:**
- Consumes: `vaults.NAME` (existing compiled regex `^[a-z0-9][a-z0-9-]*$`).
- Produces: `vaults.slug_or_empty(text: str) -> str`, which returns the stripped text if it matches `NAME`, else `''`. Task 4 mirrors it as `isSlug` in TS, and the shared cases added here run against both.

- [ ] **Step 1: Write the failing tests**

In `tests/test_vaults.py`, add to the existing test class (find it with `grep -n "^class" tests/test_vaults.py`):

```python
    def test_slug_or_empty_accepts_only_kebab_slugs(self):
        self.assertEqual(vaults.slug_or_empty("set-up-vault\n"), "set-up-vault")
        for bad in ("../../outside/secret", "a/b", ".hidden", "-x", "Up", "a b", "", "x.md"):
            with self.subTest(bad):
                self.assertEqual(vaults.slug_or_empty(bad), "")
```

In `tests/test_load_task.py`, add to the class holding `test_no_task_hint_uses_prefixed_skill` (it has `self.tasks` and `run_hook`):

```python
    def test_an_active_slug_that_escapes_tasks_is_ignored(self):
        outside = self.tasks.parent.parent / "outside"
        outside.mkdir()
        (outside / "secret.md").write_text("## Next\n- AWS_SECRET=abc123\n")
        (self.tasks / ".active").write_text("../../outside/secret\n")
        out = self.run_hook()
        self.assertIn("No active task", out)
        self.assertNotIn("AWS_SECRET", out)

    def test_without_python_an_escaping_active_slug_is_ignored(self):
        outside = self.tasks.parent.parent / "outside"
        outside.mkdir()
        (outside / "secret.md").write_text("## Next\n- AWS_SECRET=abc123\n")
        (self.tasks / ".active").write_text("../../outside/secret\n")
        bin_dir = self.tasks.parent.parent / "bin"
        bin_dir.mkdir()
        for tool in ("bash", "date", "tr", "awk", "head", "cat", "dirname"):
            os.symlink(shutil.which(tool), bin_dir / tool)
        out = self.run_hook(env_extra={"PATH": str(bin_dir)})
        self.assertIn("No active task", out)
        self.assertNotIn("AWS_SECRET", out)
```

Before writing these, run `grep -n 'python3 missing' tests/test_load_task.py`: if an existing test already hides python3, reuse its PATH setup instead of the `bin_dir` above. Read `setUp` and `run_hook` (lines 16–36) and adapt the two tests to their actual names: where `self.tasks` lives, how `run_hook` returns stdout, whether `env_extra` replaces or merges `PATH`. If `run_hook` merges `env_extra` over a dict that sets `PATH`, the override above works as written. Add `import shutil` if it is missing.

In `plugins/task-track/tests/fixtures/vault-cases.ts`, add two cases before the closing `]` (keep the file's JSON-like style; the Python runner parses it as JSON, so no trailing commas or comments):

```
  {"name": "an .active that is not a slug is ignored",
   "config": null, "vaults": {"vault": {"notes": {"g": {}}, "active": "../../outside/secret"}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "", "reason": "global"}},
  {"name": "a session override that is not a slug falls through to the default .active",
   "config": null, "vaults": {"vault": {"notes": {"g": {}}, "active": "g", "session": {"slug": "../g"}}}, "cwd": "~/x",
   "expect": {"vault": "~/vault", "slug": "g", "reason": "global"}}
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python3 -m unittest tests.test_vaults tests.test_load_task -v`
Expected: FAIL. `slug_or_empty` is not defined, the escaping `.active` injects `AWS_SECRET`, and the shared case "an .active that is not a slug is ignored" reports `Active task: ../../outside/secret`. The second shared case (session override `../g`) already passes, because the override must be an existing stem; it pins that behaviour.

- [ ] **Step 3: Implement in vaults.py and session_task.py**

In `plugins/tasks/hooks/vaults.py`, add after `NAME = re.compile(...)`:

```python
def slug_or_empty(text: str) -> str:
    """A task slug read from a vault file, or '' when it is not one (it would name a path outside Tasks/)."""
    slug = text.strip()
    return slug if NAME.match(slug) else ""
```

In `read_state`, change the two reads:

```python
    if sid and session.is_file():
        override, override_mtime = slug_or_empty(session.read_text()), session.stat().st_mtime
    active = tasks / ".active"
    state = State(vault, frozenset(p.stem for p in paths), tuple(notes), override, override_mtime,
                  slug_or_empty(active.read_text()) if active.is_file() else "")
```

In `plugins/tasks/hooks/session_task.py`, `fallback()`:

```python
            return vaults.Pick(v, vaults.slug_or_empty(active.read_text()) if active.is_file() else "", why)
```

- [ ] **Step 4: Implement in load-task.sh**

Replace the `slug=` line and the following test with:

```bash
slug="$(tr -d '[:space:]' < "$NOTES/.active" 2>/dev/null)"
# Same rule as vaults.slug_or_empty: anything else could name a file outside Tasks/.
case "$slug" in ""|-*|*[!a-z0-9-]*) slug="" ;; esac
[ -n "$slug" ] || { echo "No active task. Ask Q what we're working on, or suggest /tasks:task-start."; exit 0; }
```

(The "Ask Q" wording is changed in sub-project 2, not here.)

- [ ] **Step 5: Run the tests to see them pass**

Run: `python3 -m unittest discover -s tests`
Expected: `OK`, including `test_every_shared_case` with the two new cases.

- [ ] **Step 6: Commit**

```bash
git add plugins/tasks/hooks/vaults.py
git add plugins/tasks/hooks/session_task.py
git add plugins/tasks/hooks/load-task.sh
git add plugins/task-track/tests/fixtures/vault-cases.ts
git add tests/test_vaults.py
git add tests/test_load_task.py
git commit -m "fix(tasks): ignore an .active or session slug that is not kebab-case"
```

---

### Task 4: Slug validation in the task-track mod

**Files:**
- Modify: `plugins/task-track/hooks/resolve.ts` (export `isSlug`, `taskNotePath`; filter in `pickVault`)
- Modify: `plugins/task-track/hooks/register.tsx` (every `${…}/Tasks/${slug}.md`)
- Test: `plugins/task-track/tests/task-track.test.ts`

**Interfaces:**
- Consumes: the shared cases added in Task 3, which the existing `for (const k of CASES)` loop runs.
- Produces: `isSlug(s: string): boolean` and `taskNotePath(root: string, slug: string): string`. The latter throws `Error("task slug '<s>' is not kebab-case; refusing to build a path from it")` for a non-slug.

- [ ] **Step 1: Write the failing tests**

Add to `plugins/task-track/tests/task-track.test.ts`, importing `isSlug` and `taskNotePath` from `../hooks/resolve` next to the existing `pickVault` import:

```ts
describe('task slugs from vault files', () => {
  test('isSlug accepts kebab-case only', () => {
    expect(isSlug('set-up-vault')).toBe(true)
    for (const bad of ['../../outside/secret', 'a/b', '.hidden', '-x', 'Up', 'a b', '', 'x.md']) expect(isSlug(bad)).toBe(false)
  })

  test('taskNotePath refuses a non-slug', () => {
    expect(taskNotePath('/v', 'a-b')).toBe('/v/Tasks/a-b.md')
    expect(() => taskNotePath('/v', '../../x')).toThrow(/not kebab-case/)
  })

  test('/note with an escaping .active writes nothing outside the vault', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    const files = fakeVault(on, { '/v/Tasks/.active': '../../outside/secret\n', '/outside/secret.md': '# s\n' })
    await run($, 'note', 'pwned')
    expect(files['/outside/secret.md']).toBe('# s\n')
  })
})
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd plugins/task-track && claude plugin test .`
Expected: FAIL. The imports don't exist, the shared case "an .active that is not a slug is ignored" gets slug `../../outside/secret`, and `/outside/secret.md` gains a `## Log` line.

- [ ] **Step 3: Implement in resolve.ts**

Below `const VAULT_NAME = /^[a-z0-9][a-z0-9-]*$/`, add:

```ts
/** A task slug read from a vault file. Mirrors vaults.slug_or_empty: anything else could name a path outside Tasks/. */
export function isSlug(s: string): boolean {
  return VAULT_NAME.test(s)
}

/** `<root>/Tasks/<slug>.md`; throws for a non-slug instead of building a path that leaves Tasks/. */
export function taskNotePath(root: string, slug: string): string {
  if (!isSlug(slug)) throw new Error(`task slug '${slug}' is not kebab-case; refusing to build a path from it`)
  return `${root}/Tasks/${slug}.md`
}
```

In `pickVault`, make a non-slug override or `.active` count as absent. Change the `over` filter and both uses of `.global`:

```ts
  const over = states
    .filter(s => isSlug(s.override) && s.candidates.some(c => c.slug === s.override))
    .sort((a, b) => b.overrideMtimeMs - a.overrideMtimeMs)[0]
```

```ts
  if (folder) return { vault: folder.s.vault, slug: isSlug(folder.s.global) ? folder.s.global : '', reason: `folder ${folder.f.written}` }
  const byDefault = states.find(s => s.vault.name === config.default)
  return byDefault ? { vault: byDefault.vault, slug: isSlug(byDefault.global) ? byDefault.global : '', reason: config.isImplicit ? 'global' : 'default' } : null
```

(`isSlug('')` is false, which replaces the old `s.override !== ''` check.)

- [ ] **Step 4: Implement in register.tsx**

Add `isSlug` and `taskNotePath` to the existing import from `./resolve`. Replace each path built from a slug:

- In `load()`: `const path = \`${root}/Tasks/${slug}.md\`` → `const path = taskNotePath(root, slug)`. The slug comes from `pickVault`, which is now always a slug, so this cannot throw.
- In `flushDay`: `\`${root}/Tasks/${slug}.md\`` → `taskNotePath(root, slug)`. Before that call, add `if (!isSlug(slug)) throw new Error(\`.pomo.json day totals name '${slug}', which is not a task slug; fix or delete ${await pomoPath($)}\`)`. A tampered timer file should fail loudly, not be written around.
- In `runPomo` stop: change `const held = out.held || view.slug` to the following. A non-slug `held` throws inside `taskNotePath` with its message:

```ts
    const held = out.held || view.slug
    await flushFocus($, held, held === view.slug ? view.path : taskNotePath(await currentVault($), held))
```

- In the break-summary reader (`$.fs.read(\`${root}/Tasks/${slug}.md\`)`): use `$.fs.read(taskNotePath(root, slug))`. It is already inside `.then(…, err => ({ slug, error }))`, but `taskNotePath` throws synchronously. Wrap it as `Promise.resolve().then(() => $.fs.read(taskNotePath(root, slug))).then(…)` so the throw lands in the existing error branch and the summary names it.

Then confirm nothing was missed:

Run: `grep -n 'Tasks/\${' plugins/task-track/hooks/register.tsx`
Expected: no matches.

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd plugins/task-track && claude plugin test .`
Expected: all pass. That is 138 existing tests plus the 3 new ones and 2 new shared cases.

- [ ] **Step 6: Validate and commit**

Run: `claude plugin validate plugins/task-track`
Expected: exit 0.

```bash
git add plugins/task-track/hooks/resolve.ts
git add plugins/task-track/hooks/register.tsx
git add plugins/task-track/tests/task-track.test.ts
git commit -m "fix(task-track): never build a note path from a non-slug in .active, .session or .pomo.json"
```

---

### Task 5: Stop widening the vault into a working directory; docs and versions

**Files:**
- Modify: `setup/src/planner_setup/settings.py` (`desired()`), `setup/src/planner_setup/actions.py:85-90` (status line), `setup/src/planner_setup/cli.py:30,61` (help and prompt text)
- Modify: `docs/setup.md:59-61`
- Modify: `plugins/tasks/.claude-plugin/plugin.json`, `plugins/task-track/.claude-plugin/plugin.json` (versions)
- Test: `setup/tests/test_settings.py`, `setup/tests/test_cli.py`, `setup/tests/test_actions.py`

**Interfaces:**
- Consumes: nothing from Tasks 1–4 at the code level. The docs describe their behaviour.
- Produces: `settings.desired(vault, permissions=True)` now returns `permissions == {"allow": ["Bash(obsidian:*)"]}`, with no `additionalDirectories`.

- [ ] **Step 1: Check the premise before changing anything**

Ask a `claude-code-guide` subagent: "In Claude Code, for a directory listed in `permissions.additionalDirectories`: (a) in default permission mode, do Write/Edit calls there still raise a permission request (so PermissionRequest hooks run)? (b) In acceptEdits mode, are they auto-accepted without any PermissionRequest hook? (c) Are `.git/` or `.claude/` paths protected regardless? Cite the docs page."

Write down the answer. If (b) is "no, the hook still runs", additionalDirectories is not a bypass. In that case, do only the docs change in Step 5, rewording to "adds the vault so reads skip the prompt; writes are still decided by the hook", and skip Steps 2–4. Otherwise continue.

- [ ] **Step 2: Write the failing setup tests**

In `setup/tests/test_settings.py`, change the assertion at line 14 to:

```python
    assert d["permissions"] == {"allow": ["Bash(obsidian:*)"]}
```

In `setup/tests/test_cli.py`, replace the assertion at line 18 with:

```python
    assert "additionalDirectories" not in data["permissions"]
    assert data["permissions"]["allow"] == ["Bash(obsidian:*)"]
```

In `setup/tests/test_actions.py`, change the expectation at line 146 to:

```python
    assert "vault in additionalDirectories: yes (not needed; edits there may skip the tasks hook's write rules: consider removing it)" in out
```

(Use the wording Step 1 justifies. If the docs say acceptEdits auto-accepts edits there, keep this text.)

- [ ] **Step 3: Run them to see them fail**

Run: `cd setup && uv run pytest tests/test_settings.py tests/test_cli.py tests/test_actions.py -q`
Expected: 3 failures, all on `additionalDirectories`.

- [ ] **Step 4: Implement**

In `settings.py`, `desired()`:

```python
    if permissions:
        wanted["permissions"] = {"allow": [OBSIDIAN_ALLOW]}
```

Leave `merge()` untouched. Its `additionalDirectories` handling stays correct for any caller.

In `actions.py` around line 89, make the status line match the test:

```python
    ctx.say("vault in additionalDirectories: " + (
        "yes (not needed; edits there may skip the tasks hook's write rules: consider removing it)"
        if listed else "no (the tasks hook approves note reads and writes per call)"))
```

In `cli.py`, change `--permissions` help to `"also allow Bash(obsidian:*)"`, and the questionary prompt to `"Also allow Bash(obsidian:*)?"`.

Run: `cd setup && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Docs**

Replace `docs/setup.md` lines 59–61 (the "Vault access" bullet) with:

```markdown
- **Vault access.** The `tasks` plugin's PermissionRequest hook approves, per call and without a
  prompt: Read/Glob/Grep anywhere in the vault except dot-folders (`.obsidian/`, `.git/`, …), and
  Write/Edit of `*.md` / `*.canvas` notes outside dot-folders (never `CLAUDE.md`) plus
  `Tasks/.active`, `Tasks/.pomo.json` and `Tasks/.session/*`. Everything else gets the normal
  prompt. It trusts no vault that is `/`, your home folder or above it, or inside `~/.claude`,
  and approves nothing while `vaults.json` has an error. Don't add the vault to
  `permissions.additionalDirectories`. To turn the hook off, disable the `tasks` plugin's hooks
  or uninstall it.
```

- [ ] **Step 6: Bump versions and validate**

Set `"version": "0.2.0"` in `plugins/tasks/.claude-plugin/plugin.json` (was 0.1.0) and `plugins/task-track/.claude-plugin/plugin.json` (was 0.1.2).

Run: `claude plugin validate plugins/tasks && claude plugin validate plugins/task-track`
Expected: both exit 0.

- [ ] **Step 7: Full verification**

Run each and record a `VERIFY:` line with the counts:

```bash
python3 -m unittest discover -s tests
```
```bash
cd setup && uv run pytest
```
```bash
cd plugins/task-track && claude plugin test .
```
```bash
cd .claude/skills/planner-dev && claude plugin test .
```

Expected: all PASS. Python is 53 + new, setup 53, task-track 138 + new, planner-dev 6.

- [ ] **Step 8: Commit**

```bash
git add setup/src/planner_setup/settings.py
git add setup/src/planner_setup/actions.py
git add setup/src/planner_setup/cli.py
git add setup/tests/test_settings.py
git add setup/tests/test_cli.py
git add setup/tests/test_actions.py
git add docs/setup.md
git add plugins/tasks/.claude-plugin/plugin.json
git add plugins/task-track/.claude-plugin/plugin.json
git commit -m "fix(setup): stop adding the vault to additionalDirectories; document vault-allow rules"
```

Note for Q, after merging: if your own `~/.claude/settings.json` lists the vault in `additionalDirectories`, remove it by hand. `planner-setup status` will flag it.
