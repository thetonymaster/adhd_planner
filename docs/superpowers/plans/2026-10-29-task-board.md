# Task Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a task note's `status:` mean Parked / Doing / Done, and show it as a board in Claude Code (`/board` pane) and in Obsidian (Bases board view installed by `planner-setup`).

**Architecture:** The note's frontmatter (`status`, `finished`) is the only state. Skills and a new SessionEnd hook write it; task-track reads it into a pure `board.ts` model rendered in a pane; Obsidian reads it through a Bases board view from a community plugin that setup installs and merges into `Tasks.base`.

**Tech Stack:** Python 3 stdlib (hooks, setup), TypeScript mod API (`claude-code`, `claude-code/testing`), Markdown skills, Obsidian Bases YAML, uv + pytest, `python3 -m unittest`.

**Spec:** `docs/superpowers/specs/2026-10-29-task-board-design.md`

## Global Constraints

- Statuses are exactly `parked` (Parked column, also the backlog), `active` (Doing), `done` (Done). No `todo` value.
- New field `finished: YYYY-MM-DD`, set only by the finish skill (and the one-time cleanup).
- Done column = `status: done` and `finished` within the last 7 days including today, in the zone task-track/`vaults.py` already use. Done notes with empty or unparseable `finished` are not shown.
- Card text = the note's first `# ` heading; fall back to the slug.
- Log lines use the existing format: `- [[YYYY-MM-DD]] HH:MM — <text>`.
- `/board` is read-only.
- Python and TypeScript resolution stay in sync (`vaults.py` ↔ `resolve.ts`, shared `vault-cases.ts`).
- Never edit `planner.plugin` or `setup/uv.lock` by hand. No new setup dependency (Tasks.base merge is text-level, not a YAML library).
- `claude plugin validate plugins/<name>` after every plugin edit. Bump `tasks` 0.5.0 → 0.6.0, `task-track` 0.4.0 → 0.5.0.
- Commits: add files individually, no `git add .`.

## Review Focus

1. A note with no `# ` heading, or `# ` followed by nothing → card shows the slug. (Task 4 test)
2. `up:` written as `"[[Name|alias]]"`, `"[[Projects/Name]]"`, `"[[]]"` (template default) or missing → project `Name`, `Name`, `No project`, `No project`. (Task 4 test)
3. SessionEnd with `reason: "clear"` → no write (the task just started stays active); other reasons park. SessionEnd when the session file names a missing note, a note already `parked`/`done`, or there is no `.session/<id>` in any vault → no write, exit 0, never blocks session end. (Task 2 test)
4. `Tasks.base` that already contains the board view, or uses CRLF line endings → running update twice changes nothing the second time; no duplicate view. (Task 7 test)
5. A note with `status: active` text inside its body (not frontmatter) → only the frontmatter line is rewritten. (Task 2 test)

---

### Task 1: Resolution no longer ranks repo notes by status

**Files:**
- Modify: `plugins/tasks/hooks/vaults.py:236-260` (`pick`)
- Modify: `plugins/task-track/hooks/resolve.ts:33-58` (`pickTask`), `:182-205` (`pickVault`)
- Modify: `plugins/task-track/tests/fixtures/vault-cases.ts`
- Modify: prose order in `plugins/tasks/skills/{task-start,task-park,task-switch,obsidian-vault}/SKILL.md` only where it says "then active"
- Modify: `AGENTS.md` "Vault resolution" if it mentions active ranking
- Test: `tests/test_vaults.py`, `plugins/task-track/tests/task-track.test.ts` (both run the shared cases)

**Interfaces:**
- Consumes: nothing new.
- Produces: unchanged signatures. Repo-match order becomes: deepest `repo` root → newest mtime → slug (TS tie-break as today). `done` still never binds.

- [ ] **Step 1: Add the shared case**

In `vault-cases.ts`, a case named `"repo notes: a newer parked note beats an older active one"`: one vault, notes `old` (`repo: ~/code/x`, status `active`, older mtime) and `new` (`repo: ~/code/x`, status `parked`, newer mtime), `cwd: ~/code/x`, expect slug `new`, reason `project: x`. Follow how existing cases express status and mtime; if the fixture shape has no status/mtime fields yet, add them to `vault-case.ts` and to both runners.

- [ ] **Step 2: Run both suites, see the new case fail**

Run: `python3 -m unittest tests.test_vaults -v` and `cd plugins/task-track && claude plugin test .`
Expected: the new case FAILS (picks `old`) in both.

- [ ] **Step 3: Drop the status term**

`vaults.py`: tuple becomes `(len(root), n.mtime, n.slug, s.vault, root)` and `max(..., key=lambda b: b[:3])`. `resolve.ts`: remove the `Number(b.c.status === 'active') - …` line in both sorts. Update the docstrings/comments that say "then active".

- [ ] **Step 4: Run both suites**

Expected: all PASS, including existing cases. If an existing case relied on active-over-parked, report it before changing the case (it encodes old behaviour Q asked to drop).

- [ ] **Step 5: Validate and commit**

Run: `claude plugin validate plugins/tasks && claude plugin validate plugins/task-track`
```bash
git add plugins/tasks/hooks/vaults.py plugins/task-track/hooks/resolve.ts plugins/task-track/tests/fixtures/vault-cases.ts <skill files touched> 
git commit -m "fix(tasks,task-track): repo match no longer prefers active over parked"
```

---

### Task 2: SessionEnd hook parks the session's task

**Files:**
- Create: `plugins/tasks/hooks/park_on_end.py`
- Modify: `plugins/tasks/hooks/hooks.json` (add `SessionEnd`)
- Test: `tests/test_park_on_end.py`

**Interfaces:**
- Consumes: `vaults.load_config(env, home) -> Config`, `vaults.slug_or_empty(text) -> str`, `vaults.zone_for(config, env) -> str`, `vaults.now(zone) -> datetime`.
- Produces:
  - `park(text: str, stamp: str) -> str | None` — returns the note with frontmatter `status: active` → `status: parked` and `- <stamp> — parked: session ended` appended as the last line of `## Log` (section created at end of note if missing); `None` when frontmatter status is not `active`.
  - `main(stdin: str, env: Mapping[str, str], home: str) -> int` — reads `session_id` and `reason` from the hook JSON (`reason == "clear"` → nothing is touched; `stdin` may also be a stream, read inside the catch-all); for each vault in config, reads `<vault>/Tasks/.session/<session_id>`; parks the named note if `park` returns text. Always returns 0. Errors go to stderr as `park_on_end: <what failed>: <path>: <error>`.
  - `stamp` format: `[[YYYY-MM-DD]] HH:MM`.
  - Parks even if another session also names the task (spec leaves this to the builder; simplest rule, the other session's next `task-switch`/`task-start` re-activates it).

- [ ] **Step 1: Write the failing tests** (`tests/test_park_on_end.py`, import the module like `test_load_task.py` imports `vaults`)

```python
def test_active_note_is_parked_and_logged(self):
    out = park_on_end.park(NOTE.format(status="active"), "[[2026-10-29]] 16:40")
    self.assertIn("\nstatus: parked\n", out)
    self.assertTrue(out.rstrip().endswith("- [[2026-10-29]] 16:40 — parked: session ended"))

def test_parked_and_done_notes_are_left(self):
    for s in ("parked", "done"):
        self.assertIsNone(park_on_end.park(NOTE.format(status=s), "[[2026-10-29]] 16:40"))

def test_body_text_status_line_is_not_touched(self):
    text = NOTE.format(status="parked") + "status: active\n"
    self.assertIsNone(park_on_end.park(text, "[[2026-10-29]] 16:40"))

def test_main_parks_the_note_named_by_this_session(self):  # temp home, vaults.json with two vaults, .session/<sid> in the second
    ...assert second vault's note now has status: parked; first vault untouched; returns 0

def test_main_without_session_file_or_with_missing_note_writes_nothing(self):
    ...both cases: return 0, no file mtime changes, stderr empty for no-session, names the path for missing note
```
`NOTE` = a task note with frontmatter `status: {status}` and a `## Log` section holding one line.

- [ ] **Step 2: Run, see failures**

Run: `python3 -m unittest tests.test_park_on_end -v`
Expected: FAIL / ImportError.

- [ ] **Step 3: Implement `park` and `main`**

Rewrite the status line only inside the first `---` … `---` block. Write via temp file + `os.replace` in the same directory. `if __name__ == "__main__": sys.exit(main(sys.stdin.read() if not sys.stdin.isatty() else "", os.environ, os.path.expanduser("~")))`.

- [ ] **Step 4: Register the hook**

`hooks.json` gains:
```json
"SessionEnd": [{ "hooks": [{ "type": "command", "command": "if command -v python3 >/dev/null; then python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/park_on_end.py\"; fi", "timeout": 5 }] }]
```

- [ ] **Step 5: Run tests and validate**

Run: `python3 -m unittest discover -s tests` and `claude plugin validate plugins/tasks`
Expected: all PASS, validate clean.

- [ ] **Step 6: Commit**

```bash
git add plugins/tasks/hooks/park_on_end.py plugins/tasks/hooks/hooks.json tests/test_park_on_end.py
git commit -m "feat(tasks): park the session's task when the session ends"
```

---

### Task 3: Lifecycle skills and template

**Files:**
- Modify: `examples/vault-starter/Templates/Task.md` (`status: parked`, add `finished:` after `started:`)
- Modify: `plugins/tasks/skills/task-start/SKILL.md` step 4: set `status: active` explicitly
- Modify: `plugins/tasks/skills/task-park/SKILL.md` step 5: always set `parked`; remove its "or `done` if finished" branch and say "finished → /tasks:task-finish" instead
- Create: `plugins/tasks/skills/create-task/SKILL.md`
- Create: `plugins/tasks/skills/task-finish/SKILL.md`
- Modify: `plugins/tasks/skills/task-list/SKILL.md` (new-task pointer → `create-task`; remove any active-first ordering), `plugins/tasks/skills/obsidian-vault/SKILL.md` (task notes are created via `create-task`)
- Modify: `plugins/tasks/.claude-plugin/plugin.json` version `0.6.0`; `docs/setup.md` skill list if it enumerates skills
- Modify: `.gitignore` add `.superpowers/brainstorm/`
- Test: `tests/test_skill_files.py`

**Interfaces:**
- Produces (skill contracts later tasks and users rely on):
  - `create-task`: one task or many (a batch from a plan/review) → notes from `Templates/Task.md`, `status: parked`, `up`, `started`, `aliases`, Goal, Next; `repo:` only when the user says it belongs to the current repo. Never writes `.active` or `.session/`. Vault-resolution preamble copied from `task-start`. Existing slug → skip it and say so. Log line `created` (with source, e.g. "from <plan>") per note.
  - `task-finish`: resolves the session's task (same order as task-park) or a named `[vault:]slug`; asks for outcome details in one message (skip what the user already said); sets `status: done`, `finished: <today>`; appends Log `finished: <outcome>`; deletes every `Tasks/.session/*` file whose content is the slug, and clears `.active` when it is the slug; appends `- [[slug]] finished` to today's daily note Log like task-start does; verifies per obsidian-vault.
  - Descriptions carry routing: create-task "not start working on it (task-start)"; task-finish "finish/close/complete a task, not check off a Next item (task-note or /done)".

- [ ] **Step 1: Write failing skill-file tests** in `tests/test_skill_files.py`, matching its style:

```python
class TaskLifecycleTest(unittest.TestCase):
    def test_template_defaults_to_parked_with_finished_field(self):  # Task.md has 'status: parked' and a 'finished:' line
    def test_task_start_sets_active_explicitly(self):                # task-start SKILL.md mentions 'status: active'
    def test_task_park_always_parks(self):                           # no 'If the user is switching or stopping' condition before 'status: parked'
    def test_create_task_never_binds_the_session(self):              # create-task SKILL.md has 'status: parked' and says it does not write .active / .session
    def test_task_finish_sets_done_and_finished_and_clears_sessions(self):  # 'status: done', 'finished:', '.session/'
```

- [ ] **Step 2: Run, see failures**

Run: `python3 -m unittest tests.test_skill_files -v` → new tests FAIL.

- [ ] **Step 3: Edit template and existing skills, write the two new skills** per the contracts above.

- [ ] **Step 4: Run tests, validate, review triggers**

Run: `python3 -m unittest discover -s tests`, `claude plugin validate plugins/tasks`, then dispatch the `planner-dev:skill-trigger-reviewer` agent on the tasks skills. Fix overlaps it reports.

- [ ] **Step 5: Commit**

```bash
git add examples/vault-starter/Templates/Task.md plugins/tasks/skills/create-task/SKILL.md plugins/tasks/skills/task-finish/SKILL.md plugins/tasks/skills/task-start/SKILL.md plugins/tasks/skills/task-park/SKILL.md plugins/tasks/skills/task-list/SKILL.md plugins/tasks/skills/obsidian-vault/SKILL.md plugins/tasks/.claude-plugin/plugin.json tests/test_skill_files.py .gitignore
git commit -m "feat(tasks): create-task and task-finish; new tasks start parked; park always parks"
```

---

### Task 4: Board model (pure)

**Files:**
- Create: `plugins/task-track/hooks/board.ts`
- Test: `plugins/task-track/tests/task-track.test.ts` (new `describe('board')`)

**Interfaces:**
- Consumes: the frontmatter regex style of `resolve.ts` (reuse its `field` by exporting it, or a local copy — implementer's call).
- Produces:
```ts
export type BoardNote = { slug: string; title: string; project: string; status: string; finished: string }
export type BoardColumn = { name: 'Doing' | 'Parked' | 'Done'; count: number; groups: { project: string; cards: { slug: string; title: string }[] }[] }
export function boardNote(slug: string, text: string): BoardNote
export function buildBoard(notes: readonly BoardNote[], today: string, days?: number): BoardColumn[]  // days default 7; order Doing, Parked, Done
```
  - `project`: target of `up:` with path and alias stripped; `'No project'` when empty or `[[]]`.
  - Groups sorted by project name, `No project` last; cards by title (case-insensitive).
  - Status other than the three → not on the board.

- [ ] **Step 1: Write failing tests**

```ts
test('title falls back to slug', () => {
  expect(boardNote('a-b', '---\nstatus: parked\n---\nbody').title).toBe('a-b')
  expect(boardNote('a-b', '---\nstatus: parked\n---\n# \n').title).toBe('a-b')
  expect(boardNote('a-b', '---\nstatus: parked\n---\n# Fix card href XSS\n').title).toBe('Fix card href XSS')
})
test('project from up: forms', () => {
  for (const [up, want] of [['"[[Name|alias]]"', 'Name'], ['"[[Projects/Name]]"', 'Name'], ['"[[]]"', 'No project'], ['', 'No project']])
    expect(boardNote('s', `---\nstatus: active\nup: ${up}\n---\n# T\n`).project).toBe(want)
})
test('done shows only finished within 7 days including today', () => {
  const n = (slug: string, finished: string) => ({ slug, title: slug, project: 'P', status: 'done', finished })
  const done = buildBoard([n('today', '2026-10-29'), n('edge', '2026-10-23'), n('old', '2026-10-22'), n('none', ''), n('bad', '29/10')], '2026-10-29')[2]
  expect(done.groups.flatMap(g => g.cards.map(c => c.slug))).toEqual(['edge', 'today'])
  expect(done.count).toBe(2)
})
test('columns in order with counts, unknown status ignored', () => { /* Doing, Parked, Done names; a 'todo' note appears nowhere */ })
```

- [ ] **Step 2: Run, see failures** — `cd plugins/task-track && claude plugin test .` → import error / FAIL.

- [ ] **Step 3: Implement** `board.ts`. Date window via `Date.UTC` on the `YYYY-MM-DD` parts; reject strings not matching `^\d{4}-\d{2}-\d{2}$`.

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/task-track/hooks/board.ts plugins/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): board model from task note frontmatter"
```

---

### Task 5: `/board` pane

**Files:**
- Modify: `plugins/task-track/hooks/register.tsx` (command list ~585, a `command.run` handler next to `task` ~670, a second `ui.render` Pane handler next to the task pane ~774, a `BOARD_PANE` id next to `PANE` :46)
- Modify: `plugins/task-track/.claude-plugin/plugin.json` version `0.5.0`, description mentions `/board`
- Modify: `docs/setup.md` where task-track commands are listed
- Test: `plugins/task-track/tests/task-track.test.ts`

**Interfaces:**
- Consumes: `boardNote`, `buildBoard`, `BoardColumn` (Task 4); existing vault resolution (`vaultName`, the session task slug from the `task` state), `stamp(date, zone).date` for today, `parseVaults`/registered vaults for the `<vault>` argument.
- Produces: command `{ name: 'board', description: 'Show the task board (Doing / Parked / Done) for this vault or <vault>', argumentHint: '[vault]', immediate: true }`.

Behaviour:
- No argument → session's vault. `<vault>` → that vault from `vaults.json`; unknown name → `{ text: 'No vault "<name>" in vaults.json (have: a, b)' }`, pane not opened.
- Pane title `Board · <vault>`; header line `<vault> · Doing N · Parked N · Done N`.
- Three columns side by side (`Box flexDirection="row"`, each `flexGrow={1}`), project headings in `subtle`, the session's task card prefixed `▸` in `suggestion` color.
- Columns truncate to what fits; last row `… N more` (implementer picks the height rule).
- Reads notes fresh each render (reuse the `noteCache` mtime pattern from `candidates`).

- [ ] **Step 1: Write failing tests** using the existing Engine test pattern in `task-track.test.ts`: (a) `/board` with a fixture vault of one active, one parked, one done-today note returns text and opens pane id `BOARD_PANE`; rendered output contains each title and `Doing 1 · Parked 1 · Done 1`; (b) `/board nope` returns the "No vault" text and opens nothing; (c) the session's task renders with `▸`.

- [ ] **Step 2: Run, see failures.**

- [ ] **Step 3: Implement** command, handler and pane render.

- [ ] **Step 4: Run tests, validate**

Run: `cd plugins/task-track && claude plugin test .` and `claude plugin validate plugins/task-track` → PASS / clean.

- [ ] **Step 5: Live check** — `CLAUDE_CODE_PLUGIN_DIRS=plugins/task-track claude`, run `/board` in this repo; confirm titles and counts match `~/vaults/personal/Tasks`. Record what was seen.

- [ ] **Step 6: Commit**

```bash
git add plugins/task-track/hooks/register.tsx plugins/task-track/.claude-plugin/plugin.json plugins/task-track/tests/task-track.test.ts docs/setup.md
git commit -m "feat(task-track): /board pane with Doing, Parked and Done"
```

---

### Task 6: Pick the Obsidian board plugin and the starter `Tasks.base`

**Files:**
- Modify: `examples/vault-starter/Tasks.base`
- Create: `setup/src/planner_setup/board_plugin.py` (constants only in this task)
- Test: `setup/tests/test_board_plugin.py`

**Interfaces:**
- Produces:
```python
PLUGIN_ID: str          # e.g. the manifest "id"
PLUGIN_VERSION: str     # pinned release tag
PLUGIN_REPO: str        # "owner/name" on GitHub
PLUGIN_FILES: tuple[str, ...]  # ("manifest.json", "main.js") + ("styles.css",) if the release ships it
BOARD_VIEW: str         # the exact YAML text of the board view entry, indented as a list item under views:
DONE_VIEW_NAME = "Done (7 days)"
```

- [ ] **Step 1: Choose the plugin** against the spec criteria (Obsidian 1.11.7 in use; groups by a text property; drag rewrites it; shows note title; release within 6 months; MIT-like). Check each candidate's GitHub releases and README for its Bases view `type:` id and group-by config. Write the pick, version and why into this plan under this step before continuing.
  - Decision (Q, 2026-10-29): keep the community plugin kanban-bases-view 0.10.6 even though Obsidian 1.14 ships a native Bases kanban layout.

  **Pick: Kanban Bases View** — id `kanban-bases-view`, repo `xiwcx/obsidian-bases-kanban`, pinned `0.10.6` (released 2026-09-27; assets `manifest.json`, `main.js`, `styles.css`; `minAppVersion` 1.10.2; MIT). It is the plugin the spec calls "Kanban Bases View"; the community list maps that id to xiwcx, not zenobi-us (zenobi-us/obsidian-bases-kanban-view is a separate 0.0.1 from 2025-11, unmaintained). Why: most used (156 stars), released within the month; view type `kanban-view` with `groupByProperty` (any non-`file.` property), drag rewrites it via `processFrontMatter`, card title defaults to the file name, and column order is stored in the view entry (`columnOrders: {note.status: [...]}`), so the starter can pin parked → active → done (without it the plugin sorts columns alphabetically). Card order is kept in the base config, not in notes. Rejected: Base Board (mderazon, 2.6.1, MIT) writes a `kanban_order` property into every note; Bases Kanban (kotserge, 0BSD, last release 2026-06) and Kanban Base (jaidetree, 2 stars) are less used. Note: Obsidian 1.14 (2026-09) ships a native Bases `kanban` view; on 1.11.7 the plugin is still needed, and its `kanban-view` id does not clash with the native one.

- [ ] **Step 2: Write the failing test**: `BOARD_VIEW` parses as part of the starter `Tasks.base` (assert the starter contains `BOARD_VIEW` verbatim and a view named `DONE_VIEW_NAME` filtering on `finished`), and `PLUGIN_FILES` includes `manifest.json` and `main.js`.

- [ ] **Step 3: Add constants and update the starter `Tasks.base`**: append the board view (group by `status`, column order parked → active → done, title = `file.name` or the title property the plugin supports) and a `Done (7 days)` table view filtering `status == "done"` and `finished >= today() - "6 days"` (7 days including today) (use the Bases date syntax the docs specify; verify in Obsidian). Keep existing views; add `sort: started DESC` to Active as personal has.

- [ ] **Step 4: Run** `cd setup && uv run pytest tests/test_board_plugin.py` → PASS.

- [ ] **Step 5: Manual check** — copy the starter `Tasks.base` into a throwaway vault with the plugin installed by hand, open in Obsidian, confirm the board renders and a drag rewrites `status`. Record result.

- [ ] **Step 6: Commit**

```bash
git add examples/vault-starter/Tasks.base setup/src/planner_setup/board_plugin.py setup/tests/test_board_plugin.py docs/superpowers/plans/2026-10-29-task-board.md
git commit -m "feat(setup): pick the Obsidian board plugin; starter Tasks.base gets a board view"
```

---

### Task 7: Setup installs the board in new and existing vaults

**Files:**
- Modify: `setup/src/planner_setup/board_plugin.py` (functions)
- Modify: `setup/src/planner_setup/actions.py` (new `update_vaults`), `setup/src/planner_setup/cli.py` (subcommand `update-vaults` + menu entry; `seed_vault` calls the plugin install after copying)
- Modify: `docs/setup.md`
- Test: `setup/tests/test_board_plugin.py`, `setup/tests/test_actions.py`, `setup/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 6 constants; `files.backup(path, backups, home=)`, `files.write_json`, `files.load_json`, `Ctx.say/confirm/yes/dry_run`.
- Produces:
```python
def merge_base(text: str) -> tuple[str, str]   # (new_text, outcome) outcome in {"unchanged", "added", "conflict"}
def install_plugin(vault: Path, fetch: Callable[[str], bytes], backups: Path, *, home: Path) -> str  # "installed" | "present" | "failed: <why>"
def update_vaults(ctx: Ctx, fetch: Callable[[str], bytes] = <urllib GET>) -> int     # in actions.py
```
  - `merge_base`: text-level. Normalises CRLF for matching but writes back with the file's original line ending. `unchanged` when a view with the board's `name:` already exists with identical text; `conflict` when the name exists with different text or there is no top-level `views:`; else `added` (board view and Done (7 days) view appended at the end of `views:`).
  - `install_plugin`: URLs `https://github.com/{PLUGIN_REPO}/releases/download/{PLUGIN_VERSION}/{file}`; downloads every file into a temp dir first, moves into `.obsidian/plugins/{PLUGIN_ID}/` only when all succeed; adds `PLUGIN_ID` to `community-plugins.json` keeping existing entries (backup first). `present` when the manifest there already has `PLUGIN_VERSION`.
  - `update_vaults`: for each vault in `vaults.json` (or the single configured vault): merge `Tasks.base` (backup before write; on `conflict` ask "Replace Tasks.base in <vault>? (backup kept)"); ask "Download <PLUGIN_REPO>@<PLUGIN_VERSION> into <vault>?" before `install_plugin`; then say "Reload Obsidian; allow community plugins (Settings → Community plugins) if restricted mode is on." Dry-run prints what it would do and writes nothing.

- [ ] **Step 1: Write failing tests**

```python
def test_merge_adds_board_once(): t,o = merge_base(PERSONAL_BASE); assert o=="added"; assert merge_base(t)==(t,"unchanged")
def test_merge_keeps_custom_sort(): assert "direction: DESC" in merge_base(PERSONAL_BASE)[0]
def test_merge_crlf_round_trip(): crlf = PERSONAL_BASE.replace("\n","\r\n"); t,o = merge_base(crlf); assert o=="added" and "\r\n" in t and "\n" not in t.replace("\r\n","")
def test_merge_conflict_on_same_name_other_text(): assert merge_base(BASE_WITH_OTHER_BOARD)[1]=="conflict"
def test_install_keeps_existing_plugins(tmp_path): # community-plugins.json ["meetings-plus"] → ["meetings-plus", PLUGIN_ID]
def test_install_failed_fetch_leaves_nothing(tmp_path): # fetch raises on main.js → "failed: ..." and no plugins/<id>/ dir, json unchanged
def test_update_vaults_asks_before_download(tmp_path): # confirm returns False for the download question → no fetch calls; Tasks.base still merged
def test_update_vaults_dry_run_writes_nothing(tmp_path)
```
`PERSONAL_BASE` = the current `~/vaults/personal/Tasks.base` content copied into the test file.

- [ ] **Step 2: Run, see failures** — `cd setup && uv run pytest -k "merge or install or update_vaults"`.

- [ ] **Step 3: Implement** `merge_base`, `install_plugin`, `update_vaults`, the CLI subcommand and menu entry, and the call from `seed_vault`.

- [ ] **Step 4: Run** `cd setup && uv run pytest` and `cd setup && uv build` → PASS / builds.

- [ ] **Step 5: Docs** — `docs/setup.md`: `planner-setup update-vaults`, what it changes, the two questions, the reload step.

- [ ] **Step 6: Commit**

```bash
git add setup/src/planner_setup/board_plugin.py setup/src/planner_setup/actions.py setup/src/planner_setup/cli.py setup/tests/test_board_plugin.py setup/tests/test_actions.py setup/tests/test_cli.py docs/setup.md
git commit -m "feat(setup): update-vaults merges the board into Tasks.base and installs the board plugin"
```

---

### Task 8: One-time cleanup of Q's vaults (real data, no repo code)

Runs in the session with Q, after Tasks 1–7 are merged and the plugins updated. Uses a scratch script in the session scratchpad, not committed.

- [ ] **Step 1: List** every `status: active` note across the vaults in `~/.config/adhd-planner/vaults.json`: vault, slug, title, project, started, last Log date. Show Q as a numbered table. Also list `done` notes without `finished` and the date their last Log line gives.
- [ ] **Step 2: Q picks** which active notes stay in Doing. Write nothing before Q answers.
- [ ] **Step 3: Apply**: others → `status: parked` + Log `- [[YYYY-MM-DD]] HH:MM — parked by status cleanup`; done notes get `finished:` from their last Log date (none → leave empty, report). Follow the `obsidian-vault` skill; never delete Log or Open-loop lines.
- [ ] **Step 4: Verify**: re-count statuses per vault, compare with the list Q approved; open `/board` and the Obsidian board for personal. Report counts.
- [ ] **Step 5: Run** `planner-setup update-vaults` with Q (it asks per vault). Log a line in the active task note.

---

### Task 9: Whole-branch verification

- [ ] `python3 -m unittest discover -s tests` → PASS
- [ ] `cd setup && uv run pytest && uv build` → PASS
- [ ] `cd plugins/task-track && claude plugin test .` → PASS
- [ ] `claude plugin validate plugins/tasks`, `plugins/task-track`, `plugins/planner`, and the marketplace → clean
- [ ] `git diff main --stat` shows no change under `plugins/planner/` (else rebuild `planner.plugin` with `bash scripts/build-plugin.sh`) and none to `setup/uv.lock`
- [ ] Record `VERIFY:` lines for each suite in the PR body.
