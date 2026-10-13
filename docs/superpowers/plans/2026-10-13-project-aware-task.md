# Project-aware `/task` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each Claude Code session shows its own task: per-session override, else the task note bound to the session's repo, else the global `Tasks/.active`; the Pomodoro stays one timer for the person.

**Architecture:** One pure resolver (`pickTask`) in the task-track mod and a Python twin embedded in `load-task.sh`, both run against the same case list. The mod gathers IO (session id, project root, `Tasks/` listing, override file) at the edge and passes plain values in. `touch()` in `pomo.ts` stops resetting the block on a task switch. Skills write `Tasks/.session/<session-id>` next to `.active`.

**Tech Stack:** Claude Code mod API (TypeScript/TSX, `claude plugin test`, `tsc`), bash + embedded `python3` for the hook, stdlib `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-13-project-aware-task-design.md`

## Global Constraints

- Resolution order: session override → repo binding → global `.active`. First match wins.
- Override file: `Tasks/.session/<session-id>`, content = slug. Ignored when `Tasks/<slug>.md` does not exist.
- Repo binding: frontmatter `repo: <path>` (`~` expands to `$HOME`), `status` not `done`, path equals the session's directory or is an ancestor of it.
- Tie-break: deepest `repo` path, then `status: active` over anything else, then most recent note mtime.
- `.active` keeps meaning "the task the person last chose"; the planner plugin is not changed.
- `.pomo.json` format unchanged (no new fields).
- Hook prunes `Tasks/.session/*` older than 14 days; a broken or missing stdin never blocks session start.
- No silent fallbacks in mod code: a failure reading `Tasks/` propagates; only "file does not exist" is treated as empty.
- Commits: conventional commits, files added individually, no AI attribution lines.

## Review Focus

1. **`repo:` written with a trailing slash or `~`** (`repo: ~/work/infra-app/`) — must still bind sessions under that folder. Pinned in Task 1 (`normalize`) and Task 4.
2. **A prefix that isn't a parent** (`repo: ~/work/infra` vs session in `~/work/infra-app`) — must NOT bind. Pinned in Task 1 and Task 4.
3. **Override naming a deleted note** — falls through to repo, never shows "no note at …". Pinned in Task 1, Task 3 and Task 4.
4. **Hook run by hand with no stdin** (`bash load-task.sh` in a terminal) — must not hang waiting on stdin; falls back to the current directory. Pinned in Task 4 (`stdin=DEVNULL` case) and the `[ -t 0 ]` guard.
5. **A frontmatter value in quotes** (`status: "active"`, `repo: "~/x"`) — parsed the same as unquoted. Pinned in Task 1 and Task 4.

---

## File map

| File | Change | Responsibility |
| --- | --- | --- |
| `claude-config/task-track/hooks/resolve.ts` | Create | Pure: frontmatter fields, path normalization, `pickTask`. |
| `claude-config/task-track/hooks/pomo.ts` | Modify `touch()` | One timer for the person. |
| `claude-config/task-track/hooks/register.tsx` | Modify `load()`, pane header, band timer | IO edge: gather inputs, call `pickTask`, show the source. |
| `claude-config/task-track/types/index.d.ts` | Add `source` state | Contract for the new atom. |
| `claude-config/task-track/tests/task-track.test.ts` | Extend | Resolver, Pomodoro and wiring tests; `fakeVault` answers `fs.list`, `session.id`, `session.root`. |
| `claude-config/hooks/load-task.sh` | Rewrite resolution | Same rule in Python; source label; pruning. |
| `tests/test_load_task.py` | Create | Hook tests against a scratch vault. |
| `claude-config/skills/task-start/SKILL.md`, `task-switch/SKILL.md` | Modify | Write `repo:` and the override file. |
| `claude-config/CLAUDE.md`, `skills/obsidian-vault/SKILL.md`, `vault-starter/Templates/Task.md`, `vault-starter/.gitignore`, `vault-starter/Notes/How this vault works.md`, `task-track/README.md` | Modify | Docs. |

---

### Task 1: Pure resolver (`resolve.ts`)

**Files:**
- Create: `claude-config/task-track/hooks/resolve.ts`
- Test: `claude-config/task-track/tests/task-track.test.ts`

**Interfaces:**
- Produces:
  - `type Candidate = { slug: string; repo: string; status: string; mtimeMs: number }`
  - `type Source = 'session' | 'repo' | 'global'`
  - `function frontmatter(text: string): { repo: string; status: string }`
  - `function normalize(path: string, home: string): string` — expands a leading `~`, drops trailing `/`.
  - `function pickTask(input: { override: string; dir: string; home: string; candidates: readonly Candidate[]; global: string }): { slug: string; source: Source } | null`

- [ ] **Step 1: Write the failing tests** — append to `tests/task-track.test.ts`, and add `import { frontmatter, normalize, pickTask } from '../hooks/resolve'` and `import type { Candidate } from '../hooks/resolve'` to the imports at the top:

```ts
describe('which task a session shows', () => {
  const HOME = '/home/q'
  const c = (slug: string, repo: string, status = 'active', mtimeMs = 1): Candidate => ({ slug, repo, status, mtimeMs })
  const pick = (over: Partial<Parameters<typeof pickTask>[0]>) =>
    pickTask({ override: '', dir: '/elsewhere', home: HOME, candidates: [], global: '', ...over })

  test('frontmatter reads repo and status, quoted or not', () => {
    expect(frontmatter('---\nstatus: "active"\nrepo: "~/x"\n---\n# T\n')).toEqual({ repo: '~/x', status: 'active' })
    expect(frontmatter('---\nstatus: parked\n---\nrepo: not frontmatter\n')).toEqual({ repo: '', status: 'parked' })
    expect(frontmatter('# no frontmatter\n')).toEqual({ repo: '', status: '' })
  })

  test('normalize expands ~ and drops a trailing slash', () => {
    expect(normalize('~/work/infra-app/', HOME)).toBe('/home/q/work/infra-app')
    expect(normalize('/abs/path', HOME)).toBe('/abs/path')
  })

  test('a session override wins when its note exists', () => {
    const candidates = [c('a', '~/repo'), c('b', '')]
    expect(pick({ override: 'b', dir: '/home/q/repo', candidates, global: 'a' })).toEqual({ slug: 'b', source: 'session' })
  })

  test('an override naming a deleted note falls through to the repo binding', () => {
    expect(pick({ override: 'gone', dir: '/home/q/repo', candidates: [c('a', '~/repo')] })).toEqual({ slug: 'a', source: 'repo' })
  })

  test('repo binding matches the folder or a parent, never a sibling prefix', () => {
    const candidates = [c('iac', '~/work/infra-app/'), c('sre', '~/work/infra')]
    expect(pick({ dir: '/home/q/work/infra-app/docker', candidates })).toEqual({ slug: 'iac', source: 'repo' })
    expect(pick({ dir: '/home/q/work/infra-app', candidates })).toEqual({ slug: 'iac', source: 'repo' })
    expect(pick({ dir: '/home/q/work/infra-appX', candidates })).toBeNull()
  })

  test('deepest repo wins, then active over parked, then newest; done never binds', () => {
    expect(pick({ dir: '/home/q/r/sub', candidates: [c('outer', '~/r'), c('inner', '~/r/sub')] })?.slug).toBe('inner')
    expect(pick({ dir: '/home/q/r', candidates: [c('p', '~/r', 'parked', 9), c('a', '~/r', 'active', 1)] })?.slug).toBe('a')
    expect(pick({ dir: '/home/q/r', candidates: [c('old', '~/r', 'active', 1), c('new', '~/r', 'active', 2)] })?.slug).toBe('new')
    expect(pick({ dir: '/home/q/r', candidates: [c('d', '~/r', 'done')], global: 'g' })).toEqual({ slug: 'g', source: 'global' })
  })

  test('nothing bound and no global: null', () => {
    expect(pick({})).toBeNull()
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd claude-config/task-track && claude plugin test .`
Expected: FAIL — `the file did not load` (module `../hooks/resolve` not found).

- [ ] **Step 3: Write `hooks/resolve.ts`**

```ts
// Which task a session shows. Pure: register.tsx gathers the inputs (IO at the edge).

export type Candidate = { slug: string; repo: string; status: string; mtimeMs: number }
export type Source = 'session' | 'repo' | 'global'

const FRONTMATTER = /^---\n([\s\S]*?)\n---/

function field(block: string, name: string): string {
  const m = new RegExp(`^${name}:\\s*"?([^"\\n]*?)"?\\s*$`, 'm').exec(block)
  return m?.[1] ?? ''
}

/** `repo` and `status` from a note's frontmatter; '' when absent. */
export function frontmatter(text: string): { repo: string; status: string } {
  const block = FRONTMATTER.exec(text)?.[1] ?? ''
  return { repo: field(block, 'repo'), status: field(block, 'status') }
}

/** `~/x/` → `<home>/x`. */
export function normalize(path: string, home: string): string {
  const expanded = path.startsWith('~/') || path === '~' ? home + path.slice(1) : path
  return expanded.length > 1 ? expanded.replace(/\/+$/, '') : expanded
}

function isWithin(dir: string, root: string): boolean {
  return dir === root || dir.startsWith(`${root}/`)
}

/**
 * Session override (when its note exists) → the task bound to `dir` or a parent
 * (deepest path, then active, then newest) → the global `.active` → null.
 */
export function pickTask(input: {
  override: string
  dir: string
  home: string
  candidates: readonly Candidate[]
  global: string
}): { slug: string; source: Source } | null {
  const { override, home, candidates, global } = input
  if (override && candidates.some(c => c.slug === override)) return { slug: override, source: 'session' }
  const dir = normalize(input.dir, home)
  const bound = candidates
    .filter(c => c.repo !== '' && c.status !== 'done')
    .map(c => ({ c, root: normalize(c.repo, home) }))
    .filter(x => isWithin(dir, x.root))
    .sort(
      (a, b) =>
        b.root.length - a.root.length ||
        Number(b.c.status === 'active') - Number(a.c.status === 'active') ||
        b.c.mtimeMs - a.c.mtimeMs,
    )
  const best = bound[0]
  if (best) return { slug: best.c.slug, source: 'repo' }
  return global ? { slug: global, source: 'global' } : null
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd claude-config/task-track && tsc -p . && claude plugin test .`
Expected: `tsc` silent; all tests pass (31 existing + 7 new = 38).

- [ ] **Step 5: Commit**

```bash
git add claude-config/task-track/hooks/resolve.ts claude-config/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): add the pure task resolver"
```

---

### Task 2: One Pomodoro for the person (`touch()`)

**Files:**
- Modify: `claude-config/task-track/hooks/pomo.ts` (`touch`, lines 69-79)
- Test: `claude-config/task-track/tests/task-track.test.ts` (`describe('shared pomodoro')`)

**Interfaces:**
- Consumes: `credit(f, until)` (private, same file), `PomoConfig`, `MINUTE`.
- Produces: `touch(f: PomoFile, now: number, slug: string, cfg: PomoConfig): PomoFile` — same signature, new behaviour.

- [ ] **Step 1: Write the failing tests** — add inside `describe('shared pomodoro', ...)`:

```ts
  test('switching task keeps the block; minutes go to the task you were on', () => {
    let shared = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    for (let m = 1; m <= 10; m++) shared = sessionMinute(shared, T0 + m * MIN, true, 'a').file
    let last = sessionMinute(shared, T0 + 11 * MIN, true, 'b')
    shared = last.file
    expect(shared.blockStartedAt).toBe(T0)
    for (let m = 12; m <= 25; m++) {
      last = sessionMinute(shared, T0 + m * MIN, true, 'b')
      shared = last.file
    }
    expect(last.event).toEqual({ kind: 'break', slug: 'b', blocks: 1, isLong: false, minutes: 5 })
    expect(Math.round((shared.dayMs.a ?? 0) / MIN)).toBe(11)
    expect(Math.round((shared.dayMs.b ?? 0) / MIN)).toBe(14)
    expect(shared.dayBlocks).toEqual({ b: 1 })
  })

  test('the 4th block of the day asks for the long break across tasks', () => {
    let shared = { ...touch(emptyPomo('2026-10-13'), T0, 'a', CFG), blocksDone: 3, lastNotifiedBlock: 3 }
    let last = advance(shared, T0, CFG)
    for (let m = 1; m <= 25; m++) {
      last = sessionMinute(shared, T0 + m * MIN, true, m <= 12 ? 'a' : 'b')
      shared = last.file
    }
    expect(last.event).toEqual({ kind: 'break', slug: 'b', blocks: 4, isLong: true, minutes: 30 })
  })
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd claude-config/task-track && claude plugin test .`
Expected: FAIL in "switching task keeps the block" — `blockStartedAt` is `T0 + 11*MIN` (old `touch` restarts the block on a new slug).

- [ ] **Step 3: Replace `touch` in `hooks/pomo.ts`** (the doc comment and body, lines 69-79):

```ts
/**
 * Records activity on `slug`. One timer for the person: a different task keeps the running
 * block, with the time so far credited to the task it was on. After a break (no activity for
 * breakMinutes, from any session) the next activity starts a fresh block.
 */
export function touch(f: PomoFile, now: number, slug: string, cfg: PomoConfig): PomoFile {
  const isIdle = f.blockStartedAt === 0 || now - f.lastActiveAt >= cfg.breakMinutes * MINUTE
  if (isIdle) {
    const settled = f.slug && f.blockStartedAt !== 0 ? credit(f, Math.min(now, f.lastActiveAt + cfg.breakMinutes * MINUTE)) : f
    return { ...settled, slug, blockStartedAt: now, creditedUntil: now, lastActiveAt: now }
  }
  if (f.slug === slug) return { ...f, lastActiveAt: now }
  return { ...credit(f, now), slug, creditedUntil: now, lastActiveAt: now }
}
```

Note: the idle branch now credits the stretch between `creditedUntil` and the end of the active window when no tick noticed the idle first; the old code dropped it.

- [ ] **Step 4: Run all tests**

Run: `cd claude-config/task-track && tsc -p . && claude plugin test .`
Expected: all pass (40). If an existing test fails, read its assertion: only a test that asserted "a new task restarts the block" may change, and only to the new rule; stop and report any other failure.

- [ ] **Step 5: Commit**

```bash
git add claude-config/task-track/hooks/pomo.ts claude-config/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): keep one pomodoro across task switches"
```

---

### Task 3: Wire the resolver into the mod

**Files:**
- Modify: `claude-config/task-track/hooks/register.tsx` (`load()` lines 72-104; atoms near line 20; pane header; band `timer`)
- Modify: `claude-config/task-track/types/index.d.ts` (`PluginState`)
- Test: `claude-config/task-track/tests/task-track.test.ts` (`fakeVault`, new describe)

**Interfaces:**
- Consumes: `frontmatter`, `pickTask`, `Candidate`, `Source` from Task 1.
- Uses `$.session.root()` (the project root, which a shell `cd` does not move) where the spec says `cwd`; at session start they are the same folder.
- Produces: atom `source: Source` (state key `'task-track'.source`).

- [ ] **Step 1: Give `fakeVault` the new nouns.** Replace its signature and add three hooks before `return files`:

```ts
function fakeVault(on: On, files: Record<string, string>, session: { id?: string; root?: string } = {}) {
```

```ts
  on('fs.list', ($, e) => {
    const prefix = `${e.path}/`
    const names = Object.keys(files)
      .filter(k => k.startsWith(prefix) && !k.slice(prefix.length).includes('/'))
      .map(k => k.slice(prefix.length))
    if (names.length === 0 && !(e.path in files)) return missing(e.path)
    return { value: names.map(name => ({ name, kind: 'file' as const, size: (files[prefix + name] ?? '').length, mtimeMs: mtimes[prefix + name] ?? 0, isLink: false })) }
  })
  on('session.id', () => ({ value: session.id ?? 'sess-test' }))
  on('session.root', () => ({ value: session.root ?? '/elsewhere' }))
```

Run `claude plugin test .` — expected: still all pass (no behaviour uses them yet).

- [ ] **Step 2: Write the failing wiring tests** — append:

```ts
describe('the session\'s own task', () => {
  const BOUND = NOTE.replace('status: active\n', 'status: active\nrepo: ~/work/infra-app\n')
  const OTHER = '---\nstatus: parked\n---\n# Other\n\n## Next\n- [ ] other step\n\n## Log\n'
  const vault = {
    '/v/Tasks/.active': 'other\n',
    '/v/Tasks/other.md': OTHER,
    [PATH]: BOUND,
  }

  test('a session in a bound repo shows that task and says so', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    fakeVault(on, { ...vault }, { root: '/home/q/work/infra-app/docker' })
    await run($, 'openloop', 'load')
    const pane = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'Pane', requestId: 'task-track', props: {} as never })
    expect(await pane.find({ type: 'Text', text: 'Set up vault' })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: /repo/ })).toBeDefined()
  })

  test('a session elsewhere shows the global task', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    fakeVault(on, { ...vault }, { root: '/home/q/personal' })
    const out = await run($, 'note', 'x')
    expect(out.text).toBe('Logged to other.')
  })

  test('a session override beats the repo binding; a dangling one falls through', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    const files = fakeVault(on, { ...vault, '/v/Tasks/.session/s1': 'other\n' }, { id: 's1', root: '/home/q/work/infra-app' })
    expect((await run($, 'note', 'x')).text).toBe('Logged to other.')
    delete files['/v/Tasks/other.md']
    files['/v/Tasks/.active'] = ''
    expect((await run($, 'note', 'y')).text).toBe('Logged to set-up-vault.')
  })
})
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd claude-config/task-track && claude plugin test .`
Expected: FAIL — the bound-repo test shows `other` (old `load()` reads only `.active`).

- [ ] **Step 4: Add the contract entry** in `types/index.d.ts`, inside `'task-track': { ... }`:

```ts
      /** Why the session shows its task: an override, its repo, or the global .active. */
      source: import('../hooks/resolve').Source
```

- [ ] **Step 5: Change `register.tsx`.**

Imports — add:

```ts
import { frontmatter, pickTask } from './resolve'
import type { Candidate } from './resolve'
```

Atoms — add after `isLogOpen`:

```ts
const source = atom({ plugin: 'task-track', key: 'source' } as const, 'global')
```

Module-local cache — add after `let isStaleNudged = false`:

```ts
/** Frontmatter of each task note by slug, re-read only when the note's mtime moves. */
const noteCache = new Map<string, Candidate>()
```

Add above `load()`:

```ts
/** Every task note's slug, repo, status and mtime; [] when there is no Tasks/ folder. */
async function candidates($: EngineInterface, root: string): Promise<Candidate[]> {
  const dir = `${root}/Tasks`
  if (!(await $.fs.exists(dir))) return []
  const out: Candidate[] = []
  for (const entry of await $.fs.list(dir)) {
    if (entry.kind !== 'file' || !entry.name.endsWith('.md')) continue
    const slug = entry.name.slice(0, -3)
    let c = noteCache.get(slug)
    if (!c || c.mtimeMs !== entry.mtimeMs) {
      const fm = frontmatter(await $.fs.read(`${dir}/${entry.name}`))
      c = { slug, repo: fm.repo, status: fm.status, mtimeMs: entry.mtimeMs }
      noteCache.set(slug, c)
    }
    out.push(c)
  }
  return out
}

/** A file's trimmed text, '' when it does not exist; other read errors propagate. */
async function readIfExists($: EngineInterface, path: string): Promise<string> {
  return (await $.fs.exists(path)) ? (await $.fs.read(path)).trim() : ''
}
```

In `load()`, replace the first line that reads `.active`:

```ts
  const slug = (await $.fs.read(`${root}/Tasks/.active`).catch(() => '')).trim()
```

with:

```ts
  const home = (await $.env.get('HOME')) ?? ''
  const sessionId = await $.session.id()
  const picked = pickTask({
    override: await readIfExists($, `${root}/Tasks/.session/${sessionId}`),
    dir: await $.session.root(),
    home,
    candidates: await candidates($, root),
    global: await readIfExists($, `${root}/Tasks/.active`),
  })
  const slug = picked?.slug ?? ''
  await update($, source, () => picked?.source ?? 'global')
```

Band — one timer for the person; replace in the `AbovePrompt` hook:

```ts
    const timer = p.slug === view.slug ? pomoDots(p, await $.clock.now(), settings) : 'idle'
```

with:

```ts
    const timer = pomoDots(p, await $.clock.now(), settings)
```

Commands act on the session's task as it is now, not as the last 15 s poll saw it. In
`edit()` and in the `done` command, replace

```ts
  const view = (await read($, task)) ?? (await load($))
```

with

```ts
  const view = await load($)
```

(`load()` returns the cached view when nothing changed, so this costs one listing.)

Do the same timer replacement in `showStatus()` and in the `Pane` hook (`const timer = p.slug === view.slug ? pomoDots(p, now, settings) : 'idle'` → `const timer = pomoDots(p, now, settings)`).

Pane header — after the `{view.up ? ... : null}` Text in the status line, add:

```tsx
            <Text color="subtle"> · {SOURCE_LABEL[await read($, source)]}</Text>
```

and, near `PANE`, add:

```ts
const SOURCE_LABEL = { session: 'this session', repo: 'repo', global: 'global' } as const
```

(Read `source` into a const before the `return` if the JSX await is refused: `const why = SOURCE_LABEL[await read($, source)]`, then `{why}`.)

- [ ] **Step 6: Run everything**

Run: `cd claude-config/task-track && tsc -p . && claude plugin validate . && claude plugin test .`
Expected: `tsc` silent, `✔ Validation passed`, all tests pass (43).

- [ ] **Step 7: Commit**

```bash
git add claude-config/task-track/hooks/register.tsx claude-config/task-track/types/index.d.ts claude-config/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): show each session's own task"
```

---

### Task 4: The SessionStart hook resolves the same way

**Files:**
- Modify: `claude-config/hooks/load-task.sh`
- Create: `tests/test_load_task.py`

The spec names `jq` for reading stdin; this plan uses the `python3` the installer already
requires (`merge-settings.py`), because the resolver also parses frontmatter and sorts.
Without `python3` the hook falls back to `.active` and says so.

**Interfaces:**
- Consumes: the hook JSON on stdin (`session_id`, `cwd`), `$VAULT`, `$HOME`.
- Produces: stdout lines `Now: …`, `Active task: <slug> (<this session|repo <path>|global>) — full note: <path>`, then Goal/Next/Open loops.

- [ ] **Step 1: Write the failing tests** — `tests/test_load_task.py`:

```python
"""Tests for claude-config/hooks/load-task.sh. Run: python3 -m unittest discover -s tests"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "claude-config" / "hooks" / "load-task.sh"
NOTE = "---\nstatus: {status}\n{repo}---\n# {slug}\n\n## Goal\ngoal {slug}\n\n## Next\n- [ ] step {slug}\n\n## Log\n"


class LoadTaskTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp())
        self.tasks = self.home / "vault" / "Tasks"
        self.tasks.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.home)

    def note(self, slug, status="active", repo="", mtime=None):
        path = self.tasks / f"{slug}.md"
        path.write_text(NOTE.format(slug=slug, status=status, repo=f"repo: {repo}\n" if repo else ""))
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    def run_hook(self, payload=None, stdin=None):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"]}
        data = json.dumps(payload).encode() if payload is not None else None
        out = subprocess.run(["bash", str(HOOK)], input=data, stdin=stdin, env=env,
                             capture_output=True, timeout=10, check=True)
        return out.stdout.decode()

    def test_override_beats_repo_and_global(self):
        self.note("bound", repo="~/code/app")
        self.note("mine")
        (self.tasks / ".active").write_text("bound\n")
        (self.tasks / ".session").mkdir()
        (self.tasks / ".session" / "s1").write_text("mine\n")
        out = self.run_hook({"session_id": "s1", "cwd": str(self.home / "code" / "app")})
        self.assertIn("Active task: mine (this session)", out)
        self.assertIn("step mine", out)

    def test_dangling_override_falls_through_to_repo(self):
        self.note("bound", repo="~/code/app/")
        (self.tasks / ".session").mkdir()
        (self.tasks / ".session" / "s1").write_text("gone\n")
        out = self.run_hook({"session_id": "s1", "cwd": str(self.home / "code" / "app" / "src")})
        self.assertIn("Active task: bound (repo ~/code/app/)", out)

    def test_deepest_then_active_then_newest_and_done_never_binds(self):
        self.note("outer", repo="~/r")
        self.note("inner", repo="~/r/sub")
        self.assertIn("Active task: inner", self.run_hook({"session_id": "x", "cwd": str(self.home / "r" / "sub")}))
        self.note("parked", status="parked", repo="~/p", mtime=time.time())
        self.note("active", status='"active"', repo='"~/p"', mtime=time.time() - 100)
        self.assertIn("Active task: active", self.run_hook({"session_id": "x", "cwd": str(self.home / "p")}))
        self.note("done", status="done", repo="~/d")
        (self.tasks / ".active").write_text("outer\n")
        self.assertIn("Active task: outer (global)", self.run_hook({"session_id": "x", "cwd": str(self.home / "d")}))

    def test_sibling_prefix_does_not_bind(self):
        self.note("sre", repo="~/work/infra")
        (self.tasks / ".active").write_text("sre\n")
        out = self.run_hook({"session_id": "x", "cwd": str(self.home / "work" / "infra-app")})
        self.assertIn("Active task: sre (global)", out)

    def test_no_stdin_or_bad_json_falls_back_without_hanging(self):
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        self.assertIn("Active task: g (global)", self.run_hook(stdin=subprocess.DEVNULL))
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"]}
        out = subprocess.run(["bash", str(HOOK)], input=b"not json", env=env, capture_output=True, timeout=10, check=True)
        self.assertIn("Active task: g (global)", out.stdout.decode())

    def test_prunes_overrides_older_than_14_days(self):
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        sessions = self.tasks / ".session"
        sessions.mkdir()
        (sessions / "old").write_text("g\n")
        (sessions / "new").write_text("g\n")
        old = time.time() - 15 * 86400
        os.utime(sessions / "old", (old, old))
        self.run_hook({"session_id": "x", "cwd": str(self.home)})
        self.assertFalse((sessions / "old").exists())
        self.assertTrue((sessions / "new").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest tests.test_load_task -v`
Expected: FAIL — output says `Active task: <global slug> —` without a `(…)` source, and the override/repo cases pick the global task.

- [ ] **Step 3: Rewrite `claude-config/hooks/load-task.sh`**

```bash
#!/usr/bin/env bash
# SessionStart (startup|resume|clear|compact): inject time + this session's task Next/Open loops.
# Which task: Tasks/.session/<session_id> → the note whose `repo:` holds the session's cwd
# (deepest, then active, then newest; never `done`) → Tasks/.active.
VAULT="${VAULT:-$HOME/vault}"
NOTES="$VAULT/Tasks"
echo "Now: $(date '+%a %Y-%m-%d %H:%M')"
# The hook's JSON arrives on stdin; run by hand in a terminal there is none, so don't wait for it.
input=""
[ -t 0 ] || input=$(cat)
picked=""
command -v python3 >/dev/null || picked="$(tr -d '[:space:]' < "$NOTES/.active" 2>/dev/null)"$'\t'"global (python3 missing)"
[ -n "$picked" ] || picked=$(HOOK_INPUT="$input" NOTES="$NOTES" python3 - <<'PY'
import json, os, pathlib, re, time

notes = pathlib.Path(os.environ["NOTES"])
home = os.path.expanduser("~")
try:
    data = json.loads(os.environ.get("HOOK_INPUT") or "{}")
except ValueError:
    data = {}
sid = str(data.get("session_id") or "")
cwd = str(data.get("cwd") or os.getcwd())

sessions = notes / ".session"
if sessions.is_dir():
    cutoff = time.time() - 14 * 86400
    for f in sessions.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()

def norm(p):
    p = home + p[1:] if p == "~" or p.startswith("~/") else p
    return p.rstrip("/") if len(p) > 1 else p

def field(block, name):
    m = re.search(rf'^{name}:\s*"?([^"\n]*?)"?\s*$', block, re.M)
    return m.group(1) if m else ""

slugs = {p.stem for p in notes.glob("*.md")} if notes.is_dir() else set()
override = (sessions / sid).read_text().strip() if sid and (sessions / sid).is_file() else ""
if override in slugs:
    print(f"{override}\tthis session")
    raise SystemExit
here = norm(cwd)
bound = []
for p in notes.glob("*.md"):
    m = re.match(r"---\n(.*?)\n---", p.read_text(), re.S)
    block = m.group(1) if m else ""
    repo, status = field(block, "repo"), field(block, "status")
    if not repo or status == "done":
        continue
    root = norm(repo)
    if here == root or here.startswith(root + "/"):
        bound.append((len(root), status == "active", p.stat().st_mtime, p.stem, repo))
if bound:
    best = max(bound)
    print(f"{best[3]}\trepo {best[4]}")
    raise SystemExit
active = notes / ".active"
slug = active.read_text().strip() if active.is_file() else ""
if slug:
    print(f"{slug}\tglobal")
PY
)
slug=${picked%%$'\t'*}
why=${picked#*$'\t'}
[ -n "$slug" ] || { echo "No active task. Ask Q what we're working on, or suggest /task-start."; exit 0; }
f="$NOTES/$slug.md"
[ -f "$f" ] || { echo "Active task '$slug' ($why) has no note at $f."; exit 0; }
echo "Active task: $slug ($why) — full note: $f"
# Struck-through lines (~~done~~) stay in the note but not in every session's context.
awk '/^## (Goal|Next|Open loops)/{p=1;print;next} /^## /{p=0} p && !/^[[:space:]]*- (\[.\] )?~~/' "$f" | head -40
```

- [ ] **Step 4: Run the hook tests and the whole suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: 11 tests pass (5 triage + 6 load-task).

- [ ] **Step 5: Commit**

```bash
git add claude-config/hooks/load-task.sh tests/test_load_task.py
git commit -m "feat(hooks): load each session's own task at session start"
```

---

### Task 5: Skills and docs

**Files:**
- Modify: `claude-config/skills/task-start/SKILL.md`, `claude-config/skills/task-switch/SKILL.md`
- Modify: `claude-config/CLAUDE.md` (Task notes section), `claude-config/skills/obsidian-vault/SKILL.md` (`Tasks/` row)
- Modify: `claude-config/vault-starter/Templates/Task.md`, `claude-config/vault-starter/.gitignore`, `claude-config/vault-starter/Notes/How this vault works.md`, `claude-config/task-track/README.md`

- [ ] **Step 1: `task-start` — replace steps 4 and 6:**

Step 4 becomes:

```markdown
4. Copy `~/vault/Templates/Task.md` to `~/vault/Tasks/<slug>.md`; fill `up`, `started`, `aliases`, Goal, Next (as `- [ ]` with a time estimate). Set `repo:` to `git rev-parse --show-toplevel` of the current directory, written with `~` for `$HOME`; leave it empty outside a git repo.
```

Step 6 becomes:

```markdown
6. Write the slug to `~/vault/Tasks/.active` and to `~/vault/Tasks/.session/$CLAUDE_CODE_SESSION_ID` (create `.session/`). If `CLAUDE_CODE_SESSION_ID` is empty, write only `.active` and say the choice applies to every session.
```

- [ ] **Step 2: `task-switch` — replace step 4:**

```markdown
4. Set target `status: active`; write its slug to `~/vault/Tasks/.active` and to `~/vault/Tasks/.session/$CLAUDE_CODE_SESSION_ID` (create `.session/`). If `CLAUDE_CODE_SESSION_ID` is empty, write only `.active` and say the choice applies to every session.
```

- [ ] **Step 3: Docs**

`claude-config/CLAUDE.md`, the first Task notes bullet becomes:

```markdown
- Notes live in the Obsidian vault at `$VAULT/Tasks/` (default `~/vault/Tasks/`), one file per task. A session's task: `Tasks/.session/<session-id>` (set by /task-start, /task-switch) → the note whose `repo:` holds the session's folder → `.active` (the task last chosen).
```

`claude-config/skills/obsidian-vault/SKILL.md`, the `Tasks/` table row:

```markdown
| `Tasks/` | One note per task, kebab-case slug filename. `repo:` binds a task to a repo folder. `.active` holds the last chosen slug; `.session/<id>` a session's own. | `Templates/Task.md` |
```

`claude-config/vault-starter/Templates/Task.md`, add after the `up:` line:

```yaml
repo:
```

`claude-config/vault-starter/.gitignore`, append:

```
Tasks/.session/
```

`claude-config/vault-starter/Notes/How this vault works.md` — in the Tasks bullet, replace the sentence about `.active` with:

```markdown
A session shows its own task: the one it switched to, else the task whose `repo:` is the folder it runs in, else `.active`.
```

`claude-config/task-track/README.md` — replace the first sentence's `(\`~/vault/Tasks/<.active>.md\`)` with `(the session's task: its /task-switch choice, else the note bound to its repo, else \`Tasks/.active\`)`.

- [ ] **Step 4: Verify**

Run:

```bash
grep -rn "\.session" claude-config/skills claude-config/CLAUDE.md claude-config/vault-starter | head
python3 -m unittest discover -s tests
cd claude-config/task-track && tsc -p . && claude plugin validate . && claude plugin test .
```

Expected: the new `.session` lines listed; 11 Python tests pass; `tsc` silent; validation passed; 43 mod tests pass.

- [ ] **Step 5: Commit**

```bash
git add claude-config/skills/task-start/SKILL.md claude-config/skills/task-switch/SKILL.md claude-config/CLAUDE.md claude-config/skills/obsidian-vault/SKILL.md claude-config/vault-starter/Templates/Task.md claude-config/vault-starter/.gitignore "claude-config/vault-starter/Notes/How this vault works.md" claude-config/task-track/README.md
git commit -m "docs(task-track): document per-session and repo-bound tasks"
```

- [ ] **Step 6: Install and try it** (Q runs; touches `~/.claude`):

```bash
bash claude-config/install.sh
```

Then add `repo: ~/work/infra-app` to `~/vault/Tasks/example-task.md`, start `claude` in `~/work/infra-app` and in `~/personal/adhd_planner`, and run `/task` in each: the first shows `example-task · repo`, the second shows the global task.
