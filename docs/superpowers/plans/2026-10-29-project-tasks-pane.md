# Project Tasks Pane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `project-tasks` pane in the task-track mod that lists this repo's active and parked task notes by title. A click fills the chat box with the switch or start command and closes the pane, without ever sending it.

**Architecture:** A pure module `hooks/project.ts` turns the `Candidate[]` that `load()` already collects into a per-repo list. `load()` stores that list in a new atom on every poll. A second `ui.render` Pane hook draws it, and its buttons call `$.prompt.read` / `$.prompt.fill` / `$.ui.close`.

**Tech Stack:** TypeScript Claude Code mod (`claude-code` API 2.1.309), tests with `claude-code/testing` run by `claude plugin test .`.

**Spec:** `docs/superpowers/specs/2026-10-29-project-tasks-pane-design.md`

## Global Constraints

- Work in `plugins/task-track/`. Commands run from there unless noted.
- Command name: `project-tasks` (`/project-tasks`). Pane id constant: `PROJECT_PANE = 'task-track-project'`.
- Pane title and header: `Tasks · <vault> · <repo>`. The `<vault> · ` part only when the `vaultName` atom is non-empty.
- Group labels: `ACTIVE (<n>)`, `PARKED (<n>)`. Collapsed Parked shows 5 rows, then `… <n> more`. Expanded ends with `Show less`. Every Active row is always shown.
- Fills: `/tasks:task-switch <slug>` and `/tasks:task-start ` (trailing space). With 2+ vaults: `/tasks:task-switch <vault>:<slug>` and `/tasks:task-start <vault>:`.
- Toasts, verbatim: `Chat box has a draft: clear it, then click again.` · `Close the dialog, then click again.` · `No chat box in this session.` · `Couldn't fill the chat box.`
- Empty state body: `No tasks for <cwd basename> in <vault path's last segment>.`
- Never `$.prompt.submit` from this pane.
- The Python resolver (`plugins/tasks/hooks/vaults.py`, `session_task.py`) and `tests/fixtures/vault-cases.ts` stay unchanged. `Candidate.title` is optional.
- Bump `plugins/task-track/.claude-plugin/plugin.json` `version` 0.4.0 → 0.5.0.
- After each edit under `plugins/task-track/`, run `claude plugin validate plugins/task-track` (from the repo root).

## Review Focus

1. **A title with backticks or `[[links]]`.** Show it as written, but cut to the pane's `bodyColumns` (truncate-end). It must not wrap into the next row. Test in Task 2.
2. **A note whose `repo:` has a trailing slash or `~`.** It still matches, through `normalize()`. Test in Task 1.
3. **The session's task is `done` or belongs to another repo.** It is simply absent from the list: no `▸`, no crash. Test in Task 2.
4. **A draft that is only whitespace.** It counts as empty, so the fill goes ahead. Test in Task 3.
5. **The poll runs while the list is expanded.** It stays expanded (the atom survives `load()`). Covered by the Task 2 expand test, which calls `load` through `/project-tasks` again.

---

### Task 1: Pure project list + titles in candidates

**Files:**
- Create: `hooks/project.ts`
- Modify: `hooks/note.ts:24` (extract heading), `hooks/resolve.ts:3` (Candidate), `hooks/register.tsx:~140` (`candidates()` stores title)
- Test: `tests/task-track.test.ts` (new `describe('project list')`)

**Interfaces:**
- Produces, in `hooks/note.ts`: `export function heading(text: string): string`, the first `# ` line trimmed, or `''`. `parseNote` uses it (`heading(text) || slug`).
- Produces, in `hooks/resolve.ts`: `Candidate = { slug; repo; status; mtimeMs; title?: string }`.
- Produces, in `hooks/project.ts`:
  - `export type ProjectTask = { slug: string; title: string; status: 'active' | 'parked'; mtimeMs: number }`. Title falls back to the slug. Any non-`active`, non-`done` status maps to `'parked'`.
  - `export type ProjectList = { repo: string; tasks: ProjectTask[] }`, where `repo` is the last segment of the matched root, or `''` when nothing matched.
  - `export function projectTasks(candidates: readonly Candidate[], dir: string, home: string): ProjectList`. It drops `done` and empty-`repo` notes, keeps notes whose normalized root holds `normalize(dir)`, keeps only the deepest root, and sorts active first, then mtime descending.
  - `export function visibleParked(tasks: readonly ProjectTask[], isOpen: boolean): { shown: ProjectTask[]; hidden: number }`, with a cap of 5.

- [ ] **Step 1: Write failing tests**

```ts
describe('project list', () => {
  const c = (slug: string, repo: string, status: string, mtimeMs: number, title?: string): Candidate => ({ slug, repo, status, mtimeMs, title })
  test('lists this repo\'s non-done notes, active first, newest first, titles with slug fallback', () => {
    const list = projectTasks([
      c('a', '~/w', 'parked', 1, 'Old parked'), c('b', '~/w/', 'active', 2, 'Active one'),
      c('d', '~/w', 'done', 9, 'Done'), c('e', '~/other', 'active', 9), c('f', '~/w', '', 5), c('g', '', 'active', 9),
    ], '/home/q/w/lib', '/home/q')
    expect(list.repo).toBe('w')
    expect(list.tasks.map(t => [t.slug, t.title, t.status])).toEqual([['b', 'Active one', 'active'], ['f', 'f', 'parked'], ['a', 'Old parked', 'parked']])
  })
  test('only the deepest matching root counts', () => {
    const list = projectTasks([c('outer', '~/p', 'active', 1), c('inner', '~/p/w', 'parked', 1)], '/home/q/p/w', '/home/q')
    expect(list).toEqual({ repo: 'w', tasks: [expect.objectContaining({ slug: 'inner' })] })
  })
  test('no match → empty repo and list', () => {
    expect(projectTasks([c('x', '~/w', 'active', 1)], '/tmp', '/home/q')).toEqual({ repo: '', tasks: [] })
  })
  test('visibleParked caps at 5 unless open', () => {
    const seven = Array.from({ length: 7 }, (_, i) => ({ slug: `p${i}`, title: `p${i}`, status: 'parked' as const, mtimeMs: 7 - i }))
    expect(visibleParked(seven, false)).toEqual({ shown: seven.slice(0, 5), hidden: 2 })
    expect(visibleParked(seven, true)).toEqual({ shown: seven, hidden: 0 })
  })
  test('heading reads the first # line', () => {
    expect(heading('---\nx: 1\n---\n# Decide: encrypt google_tokens\n## Goal')).toBe('Decide: encrypt google_tokens')
    expect(heading('no heading')).toBe('')
  })
})
```

- [ ] **Step 2: Run, expect FAIL** (`projectTasks` / `heading` not exported). Run: `claude plugin test .`
- [ ] **Step 3: Implement** `heading`, the `Candidate.title`, `hooks/project.ts`, and make `candidates()` set `title: heading(text)`. It already reads the text when the mtime moves, so this adds no extra reads.
- [ ] **Step 4: Run `claude plugin test .`.** Expected: all pass, including the existing vault-case fixtures.
- [ ] **Step 5: Commit**

```bash
git add plugins/task-track/hooks/project.ts plugins/task-track/hooks/note.ts plugins/task-track/hooks/resolve.ts plugins/task-track/hooks/register.tsx plugins/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): per-repo task list from note frontmatter"
```

---

### Task 2: The pane, `/project-tasks` and the band button

**Files:**
- Modify: `hooks/register.tsx` (atoms, `load()`, `COMMANDS`, command hook, band, new Pane render), `types/index.d.ts` (PluginState)
- Test: `tests/task-track.test.ts` (new `describe('project tasks pane')`)

**Interfaces:**
- Consumes: `projectTasks`, `visibleParked`, `ProjectList` (Task 1).
- Produces, in the atoms: `projectList: ProjectList` (initial `{ repo: '', tasks: [] }`) and `isProjectMoreOpen: boolean` (initial `false`). Both are declared in `PluginState['task-track']` with doc comments; `ProjectList` / `ProjectTask` types are re-declared or imported into `types/index.d.ts` the way `TaskView` is.
- Produces, in `register.tsx`: `async function openProjectPane($): Promise<void>`. It opens `PROJECT_PANE` with `focus: true` and the title from Global Constraints. Task 3 needs `PROJECT_PANE`.
- Button keys (Task 3 attaches handlers to these): `proj-<slug>` per row, `proj-more` (`… N more` / `Show less`), `proj-new`.

`load()`: right after `vault = root`, before any early return, set `projectList` from `projectTasks(states.find(s => s.vault.path === root)?.candidates ?? [], dir, home)`.

- [ ] **Step 1: Write failing tests.** Use `fakeVault` with `session.root = '/home/q/w'`, `HOME=/home/q` and `VAULT=/v`, plus three notes with `repo: "~/w"` (one active and the session's via `.active`, two parked) and one `done`. Then `run($, 'project-tasks', '')` and mount `{ component: 'Pane', requestId: 'task-track-project' }`, on both `terminal` and `desktop`.
  - `out.text` is `Project tasks: w`. The pane has `Text` `ACTIVE (1)` and `PARKED (2)`, plus each title. The done title is absent.
  - The session's row text starts with `▸`. Pressing `proj-<that slug>` with a `prompt.fill` hook spy records no call.
  - 7 parked: `… 2 more` is shown. Pressing `proj-more` shows all 7 and `Show less`. Running `/project-tasks` again keeps 7 rows.
  - A long title (80 chars) with `bodyColumns` 40: its `Text` has `wrap="truncate-end"`.
  - The session's task is `done`: there is no `▸` row and no throw.
  - `session.root` is `/tmp/x`: the body is `No tasks for x in v.` and `proj-new` exists.
  - Band: `band.find({ type: 'Button', key: 'project' })` is defined, and pressing it raises `ui.open` with id `task-track-project` (spy with `on('ui.open', …)`, then `next(e)`).
- [ ] **Step 2: Run `claude plugin test .`.** Expected: FAIL (no command / pane).
- [ ] **Step 3: Implement** the atoms, the `load()` line, the `COMMANDS` entry `{ name: 'project-tasks', description: 'Show this repo\'s active and parked tasks; a click fills the switch command', immediate: true }`, the command hook (calls `load`, `openProjectPane`, returns the text above or the empty-state line), the band `Button key="project" label="Tasks"` after `pane`, and the Pane render. Follow the existing Pane render's `Box`/`Text`/`Button` use and its `bodyColumns` width handling.
- [ ] **Step 4: Run `claude plugin test .`, then `claude plugin validate plugins/task-track` and `tsc -p plugins/task-track`** (from the repo root, if `.claude-plugin/types` exists). Expected: all pass, no type errors.
- [ ] **Step 5: Commit**

```bash
git add plugins/task-track/hooks/register.tsx plugins/task-track/types/index.d.ts plugins/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): /project-tasks pane lists this repo's tasks"
```

---

### Task 3: Click fills the chat box and closes the pane

**Files:**
- Modify: `hooks/register.tsx`
- Test: `tests/task-track.test.ts` (same describe)

**Interfaces:**
- Consumes: `PROJECT_PANE` and the button keys (Task 2), the `vaultName` atom.
- Produces: `async function fillFromPane($: EngineInterface, text: string): Promise<void>`, the only path the row and `proj-new` buttons use.

Behaviour, in order:
1. `markActive($)`.
2. If `(await $.prompt.read()).text.trim()` is non-empty, toast the draft message and return.
3. Run `$.prompt.fill({ text, mode: 'replace' })`. If `!isFilled`, toast by `refusal` (`dialog` / `no_composer` / absent) and return, leaving the pane open.
4. `await $.ui.close({ id: PROJECT_PANE })`.

The text is built from the slug and the `vaultName` prefix (Global Constraints).

- [ ] **Step 1: Write failing tests.** Spy `prompt.read` → `{ value: { text: draft, cursor: 0 } }`, `prompt.fill` → record `e`, return `{ value: { isFilled: true, text: e.text, cursor: e.text.length } }`, `ui.close` → record `e.id`, `ui.toast` → record text, `prompt.submit` → record (must stay empty).
  - Draft `''`: pressing `proj-boundary-error-tuples` fills `{ text: '/tasks:task-switch boundary-error-tuples', mode: 'replace' }`. Close is recorded with `task-track-project`. No submit, no toast.
  - Draft `'   \n'` (whitespace): same as empty.
  - Draft `'half typed'`: no fill, no close, and the toast is `Chat box has a draft: clear it, then click again.`
  - `proj-new`: fills `/tasks:task-start `.
  - The fill returns `{ isFilled: false, refusal: 'dialog' }`: the toast is `Close the dialog, then click again.` and there is no close. Same for `no_composer` → `No chat box in this session.` and no refusal → `Couldn't fill the chat box.`
  - Two vaults via `ADHD_PLANNER_VAULTS` pointing at a fake `vaults.json` with `personal` (the session's) and `work`. Copy the setup from the existing multi-vault tests: the fills are `/tasks:task-switch personal:<slug>` and `/tasks:task-start personal:`.
- [ ] **Step 2: Run `claude plugin test .`.** Expected: FAIL (no handlers).
- [ ] **Step 3: Implement `fillFromPane`** and wire `onPress` for `proj-<slug>` (except the session's own) and `proj-new`.
- [ ] **Step 4: Run `claude plugin test .` and `claude plugin validate plugins/task-track`.** Expected: PASS.
- [ ] **Step 5: Check the keyboard by hand.** Load the mod with `CLAUDE_CODE_PLUGIN_DIRS=plugins/task-track` in a terminal `claude` session in a repo with task notes. Run `/project-tasks`, click or press a row, then press Enter once. Expected: the switch command is sent. Repeat in the desktop app. If a surface leaves the keys elsewhere, write that down in the PR description; do not add a submit.
- [ ] **Step 6: Commit**

```bash
git add plugins/task-track/hooks/register.tsx plugins/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): project-tasks click fills switch/start and closes the pane"
```

---

### Task 4: Version, docs, gitignore, full check

**Files:**
- Modify: `plugins/task-track/.claude-plugin/plugin.json` (version 0.5.0, mention the pane in `description`), `plugins/task-track/README.md` (feature bullet plus a `/project-tasks` row in the command table), `.gitignore` (add `.superpowers/brainstorm/`), and `docs/setup.md` only if it lists task-track commands (`grep -n "/pomo\|/task" docs/setup.md`).

- [ ] **Step 1: Make the edits above.**
- [ ] **Step 2: Verify from the repo root:** `claude plugin validate plugins/task-track` → passes; `cd plugins/task-track && claude plugin test .` → all pass; `python3 -m unittest discover -s tests` → OK (resolver untouched, guards against fixture drift).
- [ ] **Step 3: Commit**

```bash
git add plugins/task-track/.claude-plugin/plugin.json plugins/task-track/README.md .gitignore
git commit -m "docs(task-track): document /project-tasks, bump to 0.5.0"
```
