# Pomodoro Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start, pause, resume and stop the one shared Pomodoro from `/pomo` and band buttons, show its state in the band, and summarize each block in the break notification (from the notes, plus an opt-in Haiku line).

**Architecture:** All timer rules are pure functions over `PomoFile` in `hooks/pomo.ts`; the block summary is pure in a new `hooks/summary.ts`; `hooks/register.tsx` only does IO (reads notes, writes `.pomo.json` through `changePomo`, toasts, the model call) and wires commands, buttons and hooks to the pure functions.

**Tech Stack:** TypeScript Claude Code plugin (mod), tests in `claude-config/task-track/tests/task-track.test.ts` via `claude plugin test .`, checked by `claude plugin validate .`.

**Spec:** `docs/superpowers/specs/2026-10-13-pomodoro-controls-design.md`

## Global Constraints

- Run every command from `claude-config/task-track/`: `claude plugin test .` (all tests) and `claude plugin validate .`.
- Baseline before Task 1: 53 tests pass. Every task ends with all tests passing and validate passing.
- Hybrid model: activity still starts a block; pause and stop override that until start/resume.
- Stop lasts until `/pomo start` or the day rolls over. Pause freezes whatever is running, a block or a break.
- New `PomoFile` fields default through `emptyPomo` so older files parse unchanged: `pausedAt: 0`, `isStopped: false`, `blockOpenedAt: 0`, `blockSnapshot: {}`, `blockActivity: []`.
- Timer text, exactly: `🍅 ●●○○ 12/25m` · `⏸ ●●○○ 12/25m paused` · `⏸ ●○○○ break 4m left paused` · `☕ ●○○○ break 4m left` · `☕ ●●●● long break 29m left` · `⏹ off` · `○ ●●○○ idle`.
- Band buttons: running/break → ⏸ Pause, ⏹ Stop; paused → ▶ Resume, ⏹ Stop; stopped/idle → ▶ Start.
- `/pomo` replies with its text like `/note` does (command output); band presses toast the same text.
- AI line: model `claude-haiku-5-5`, `maxTokens: 120`, `effort: 'low'`, `timeoutMs: 10000`, setting `breakSummaryAI` default `false`. Nothing is recorded while it is off.
- No silent fallbacks or empty catches (Q's rule): a failure is shown, named, or propagates.
- Commits: only when Q says so. Add files one by one (no `git add .`), no AI attribution lines.

## Review Focus

1. A pause that spans the end of a block (paused at 24/25m, resumed 20 min later) must not announce the break at resume time; the block finishes 1 minute after resume. → test in Task 1.
2. `/pomo stop` while paused must not credit the paused minutes as focus. → test in Task 1.
3. Two sessions: B presses pause after A already paused → `Already paused (…)`, file unchanged. → test in Task 3.
4. A file written by the current code (no new fields) with a block running keeps running after the upgrade, and its break summary still lists Log lines (filtered from `blockStartedAt`). → tests in Tasks 1 and 4.
5. A note that vanished or is unreadable at announcement never stops the break from starting or the toast from showing. → plugin test through the real tick in Task 4.

---

### Task 0: Branch and commit the timed-break baseline

The timed breaks, `isRunning`, the break reminder and the status-line removal are uncommitted on `main`. This plan builds on them.

- [ ] **Step 1: Ask Q** whether to commit that work first. On yes:

```bash
cd "$(git rev-parse --show-toplevel)"
git checkout -b feat/pomo-controls
git add claude-config/task-track/hooks/pomo.ts
git add claude-config/task-track/hooks/register.tsx
git add claude-config/task-track/types/index.d.ts
git add claude-config/task-track/tests/task-track.test.ts
git add claude-config/task-track/README.md
git commit -m "feat(task-track): timed breaks; Claude's tool calls only keep a block alive; drop the status line"
git add docs/superpowers/specs/2026-10-13-pomodoro-controls-design.md
git add docs/superpowers/plans/2026-10-13-pomodoro-controls.md
git commit -m "docs(task-track): pomodoro controls spec and plan"
```

- [ ] **Step 2: Baseline**

Run: `cd claude-config/task-track && claude plugin test . 2>&1 | grep -E '^ *[0-9]+ (pass|fail)'`
Expected: `53 pass`, `0 fail`.

---

### Task 1: Pause, resume, stop, start, toggle (pure)

**Files:**
- Modify: `claude-config/task-track/types/index.d.ts` (`PomoFile`)
- Modify: `claude-config/task-track/hooks/pomo.ts`
- Test: `claude-config/task-track/tests/task-track.test.ts` (new `describe('controls')`)

**Interfaces:**
- Consumes: existing `touch`, `advance`, `credit` (private), `onBreak`, `isRunning`, `shouldTouch`, `rollDay`, `emptyPomo`, `PomoConfig`.
- Produces (exported from `hooks/pomo.ts`):
  - `type PomoState = 'running' | 'break' | 'paused' | 'stopped' | 'idle'`
  - `pomoState(f: PomoFile, now: number, cfg: PomoConfig): PomoState`
  - `type Transition = { file: PomoFile } | { error: string }`
  - `pause(f, now, cfg): Transition`, `resume(f, now, cfg): Transition`, `stop(f, now, cfg): Transition`
  - `start(f, now, slug: string, cfg): Transition`, `toggle(f, now, slug: string, cfg): Transition`
  - `PomoEvent` break variant gains `openedAt: number; snapshot: Record<string, string[]>; activity: string[]`

- [ ] **Step 1: Add the fields to `PomoFile`** (`types/index.d.ts`, after `isLongBreak`):

```ts
  /** Epoch ms the timer was paused; 0 = not paused. Pause freezes a block or a break. */
  pausedAt: number
  /** Q stopped the timer: activity starts no block until /pomo start or the next day. */
  isStopped: boolean
  /** Wall-clock start of the running block (pause does not shift it); 0 = no block. For the break summary. */
  blockOpenedAt: number
  /** Checked Next item titles per task when the block reached it, to tell what got checked during the block. */
  blockSnapshot: Record<string, string[]>
  /** What happened during the block, for the opt-in AI summary (breakSummaryAI). Last 60 entries. */
  blockActivity: string[]
```

And in `emptyPomo` (`hooks/pomo.ts`), after `isLongBreak: false,`:

```ts
    pausedAt: 0,
    isStopped: false,
    blockOpenedAt: 0,
    blockSnapshot: {},
    blockActivity: [],
```

- [ ] **Step 2: Write the failing tests** (append before `/** An in-memory vault beneath the plugin's $.fs calls. */`; add `pause, pomoState, resume, start, stop, toggle` to the `../hooks/pomo` import):

```ts
describe('controls', () => {
  const running = () => {
    let f = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    for (let m = 1; m <= 10; m++) f = sessionMinute(f, T0 + m * MIN, true, 'a').file
    return f
  }
  const ok = (t: { file: PomoFile } | { error: string }) => {
    if ('error' in t) throw new Error(`expected a file, got: ${t.error}`)
    return t.file
  }
  const err = (t: { file: PomoFile } | { error: string }) => ('error' in t ? t.error : `no error, state ${JSON.stringify(t.file)}`)

  test('pause freezes the block and its credit; resume continues at the same minute', () => {
    const paused = ok(pause(running(), T0 + 10 * MIN, CFG))
    expect(pomoState(paused, T0 + 30 * MIN, CFG)).toBe('paused')
    const later = advance(paused, T0 + 30 * MIN, CFG)
    expect(later.event.kind).toBe('none')
    expect(later.file.dayMs.a).toBe(paused.dayMs.a)
    const back = ok(resume(later.file, T0 + 30 * MIN, CFG))
    expect(blockMinutes(back, T0 + 30 * MIN)).toBe(10)
    expect(pomoState(back, T0 + 30 * MIN, CFG)).toBe('running')
  })

  test('a pause across the end of a block finishes the block after resume, not at it', () => {
    let f = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    for (let m = 1; m <= 24; m++) f = sessionMinute(f, T0 + m * MIN, true, 'a').file
    f = ok(pause(f, T0 + 24 * MIN, CFG))
    f = ok(resume(f, T0 + 44 * MIN, CFG))
    expect(advance(f, T0 + 44 * MIN, CFG).event.kind).toBe('none')
    expect(sessionMinute(f, T0 + 45 * MIN, true, 'a').event.kind).toBe('break')
  })

  test('pause during a break freezes the countdown', () => {
    let f = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    for (let m = 1; m <= 25; m++) f = sessionMinute(f, T0 + m * MIN, true, 'a').file
    expect(pomoState(f, T0 + 27 * MIN, CFG)).toBe('break')
    f = ok(pause(f, T0 + 27 * MIN, CFG))
    f = ok(resume(f, T0 + 47 * MIN, CFG))
    expect(onBreak(f, T0 + 47 * MIN)).toEqual({ minutesLeft: 3, isLong: false })
  })

  test('activity while paused or stopped changes nothing', () => {
    const paused = ok(pause(running(), T0 + 10 * MIN, CFG))
    expect(touch(paused, T0 + 12 * MIN, 'a', CFG)).toBe(paused)
    expect(shouldTouch(paused, T0 + 12 * MIN, 'a')).toBe(false)
    const stopped = ok(stop(running(), T0 + 10 * MIN, CFG))
    expect(touch(stopped, T0 + 12 * MIN, 'a', CFG)).toBe(stopped)
    expect(isRunning(stopped, T0 + 12 * MIN, CFG)).toBe(false)
  })

  test('stop credits the time so far and ends the block; start begins a fresh one; a new day clears stop', () => {
    const stopped = ok(stop(running(), T0 + 10 * MIN, CFG))
    expect(Math.round((stopped.dayMs.a ?? 0) / MIN)).toBe(10)
    expect(stopped.blockStartedAt).toBe(0)
    expect(pomoState(stopped, T0 + 11 * MIN, CFG)).toBe('stopped')
    const started = ok(start(stopped, T0 + 20 * MIN, 'a', CFG))
    expect(started.blockStartedAt).toBe(T0 + 20 * MIN)
    expect(started.isStopped).toBe(false)
    expect(rollDay(stopped, '2026-10-14').file.isStopped).toBe(false)
  })

  test('stop while paused does not credit the paused minutes', () => {
    const paused = ok(pause(running(), T0 + 10 * MIN, CFG))
    const stopped = ok(stop(paused, T0 + 40 * MIN, CFG))
    expect(stopped.dayMs.a).toBe(paused.dayMs.a)
  })

  test('start skips a break; start while running or paused names the state', () => {
    let f = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    for (let m = 1; m <= 25; m++) f = sessionMinute(f, T0 + m * MIN, true, 'a').file
    const skipped = ok(start(f, T0 + 26 * MIN, 'a', CFG))
    expect(skipped.breakUntil).toBe(0)
    expect(skipped.blockStartedAt).toBe(T0 + 26 * MIN)
    expect(err(start(running(), T0 + 10 * MIN, 'a', CFG))).toBe('Already running (🍅 ○○○○ 10/25m). Use /pomo pause or /pomo stop.')
    expect(err(start(ok(pause(running(), T0 + 10 * MIN, CFG)), T0 + 11 * MIN, 'a', CFG))).toBe('Paused (⏸ ○○○○ 10/25m paused). Use /pomo resume.')
  })

  test('transitions that do not fit the state say so', () => {
    const paused = ok(pause(running(), T0 + 10 * MIN, CFG))
    expect(err(pause(paused, T0 + 11 * MIN, CFG))).toBe('Already paused (⏸ ○○○○ 10/25m paused).')
    expect(err(resume(running(), T0 + 10 * MIN, CFG))).toBe('Not paused (🍅 ○○○○ 10/25m).')
    const stopped = ok(stop(running(), T0 + 10 * MIN, CFG))
    expect(err(stop(stopped, T0 + 11 * MIN, CFG))).toBe('Already stopped. /pomo start to begin.')
    expect(err(pause(stopped, T0 + 11 * MIN, CFG))).toBe('Stopped. /pomo start to begin.')
    expect(err(pause(emptyPomo('2026-10-13'), T0, CFG))).toBe('Nothing running. /pomo start to begin.')
  })

  test('toggle pauses, resumes and starts by state', () => {
    const paused = ok(toggle(running(), T0 + 10 * MIN, 'a', CFG))
    expect(pomoState(paused, T0 + 10 * MIN, CFG)).toBe('paused')
    expect(pomoState(ok(toggle(paused, T0 + 12 * MIN, 'a', CFG)), T0 + 12 * MIN, CFG)).toBe('running')
    const stopped = ok(stop(running(), T0 + 10 * MIN, CFG))
    expect(pomoState(ok(toggle(stopped, T0 + 12 * MIN, 'a', CFG)), T0 + 12 * MIN, CFG)).toBe('running')
    expect(pomoState(ok(toggle(emptyPomo('2026-10-13'), T0, 'a', CFG)), T0, CFG)).toBe('running')
  })

  test('a file written before controls existed reads as not paused, not stopped', () => {
    const old = JSON.parse(serializePomo(running())) as Record<string, unknown>
    for (const k of ['pausedAt', 'isStopped', 'blockOpenedAt', 'blockSnapshot', 'blockActivity']) delete old[k]
    const f = parsePomo(JSON.stringify(old)) as PomoFile
    expect(pomoState(f, T0 + 10 * MIN, CFG)).toBe('running')
    expect(f.blockActivity).toEqual([])
  })
})
```

Also add `blockMinutes, isRunning` to the import if not there yet.

- [ ] **Step 3: Run to see them fail**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `(fail) the file did not load` (`pause` is not exported).

- [ ] **Step 4: Implement in `hooks/pomo.ts`**

Guards in the existing functions (add as the first line of each body):

```ts
// touch
  if (f.isStopped || f.pausedAt) return f
// advance (inside, before `const none` is used, after it is declared)
  if (f.isStopped || f.pausedAt) return { file: f, event: none }
// shouldTouch
  if (f.isStopped || f.pausedAt) return false
// isRunning
  if (f.isStopped || f.pausedAt) return false
```

`rollDay`: in the returned `file`, add `isStopped: false, pausedAt: 0`.

`touch`, the idle branch (a new block): also set `blockOpenedAt: now, blockSnapshot: {}, blockActivity: []`.

`advance`, the idle-end return: `{ ...credited, blockStartedAt: 0, creditedUntil: now, blockOpenedAt: 0, blockSnapshot: {}, blockActivity: [] }`.

`advance`, the block-complete branch: keep what the finished block saw for the event, then clear it:

```ts
  const finished = { openedAt: next.blockOpenedAt || next.blockStartedAt, snapshot: next.blockSnapshot, activity: next.blockActivity }
  // … existing blocksDone / isLong / next = { … } …, and add to that object:
  //   blockOpenedAt: 0, blockSnapshot: {}, blockActivity: [],
  // the returned event:
  event: { kind: 'break', slug: next.slug, blocks: blocksDone, isLong, minutes: isLong ? cfg.longBreakMinutes : cfg.breakMinutes, ...finished },
```

`PomoEvent`:

```ts
export type PomoEvent =
  | { kind: 'none' }
  | {
      kind: 'break'
      slug: string
      blocks: number
      isLong: boolean
      minutes: number
      /** Wall-clock start of the finished block (or its blockStartedAt in a file from before controls). */
      openedAt: number
      snapshot: Record<string, string[]>
      activity: string[]
    }
```

New exports (after `isRunning`):

```ts
export type PomoState = 'running' | 'break' | 'paused' | 'stopped' | 'idle'
export type Transition = { file: PomoFile } | { error: string }

export function pomoState(f: PomoFile, now: number, cfg: PomoConfig): PomoState {
  if (f.isStopped) return 'stopped'
  if (f.pausedAt) return 'paused'
  if (onBreak(f, now)) return 'break'
  return f.blockStartedAt !== 0 && now - f.lastActiveAt < cfg.breakMinutes * MINUTE ? 'running' : 'idle'
}

const BEGIN = '/pomo start to begin.'

export function pause(f: PomoFile, now: number, cfg: PomoConfig): Transition {
  const state = pomoState(f, now, cfg)
  if (state === 'paused') return { error: `Already paused (${pomoDots(f, now, cfg)}).` }
  if (state === 'stopped') return { error: `Stopped. ${BEGIN}` }
  if (state === 'idle') return { error: `Nothing running. ${BEGIN}` }
  const credited = state === 'running' ? { ...credit(f, now), creditedUntil: now } : f
  return { file: { ...credited, pausedAt: now } }
}

export function resume(f: PomoFile, now: number, cfg: PomoConfig): Transition {
  if (!f.pausedAt) return { error: `Not paused (${pomoDots(f, now, cfg)}).` }
  const shift = now - f.pausedAt
  return {
    file: {
      ...f,
      blockStartedAt: f.blockStartedAt && f.blockStartedAt + shift,
      breakUntil: f.breakUntil && f.breakUntil + shift,
      creditedUntil: now,
      lastActiveAt: now,
      pausedAt: 0,
    },
  }
}

export function stop(f: PomoFile, now: number, cfg: PomoConfig): Transition {
  const state = pomoState(f, now, cfg)
  if (state === 'stopped') return { error: `Already stopped. ${BEGIN}` }
  // A running block is credited to now; an idle one the way touch settles it; paused time never.
  const credited =
    state === 'running' ? credit(f, now)
    : state === 'idle' && f.slug && f.blockStartedAt !== 0 ? credit(f, Math.min(now, f.lastActiveAt + cfg.breakMinutes * MINUTE))
    : f
  return {
    file: { ...credited, blockStartedAt: 0, breakUntil: 0, pausedAt: 0, isStopped: true, creditedUntil: now, blockOpenedAt: 0, blockSnapshot: {}, blockActivity: [] },
  }
}

export function start(f: PomoFile, now: number, slug: string, cfg: PomoConfig): Transition {
  const state = pomoState(f, now, cfg)
  if (state === 'running') return { error: `Already running (${pomoDots(f, now, cfg)}). Use /pomo pause or /pomo stop.` }
  if (state === 'paused') return { error: `Paused (${pomoDots(f, now, cfg)}). Use /pomo resume.` }
  // An idle block left running is settled the way touch settles one.
  const settled = state === 'idle' && f.slug && f.blockStartedAt !== 0 ? credit(f, Math.min(now, f.lastActiveAt + cfg.breakMinutes * MINUTE)) : f
  return {
    file: {
      ...settled,
      slug,
      blockStartedAt: now,
      blockOpenedAt: now,
      breakUntil: 0,
      pausedAt: 0,
      isStopped: false,
      creditedUntil: now,
      lastActiveAt: now,
      blockSnapshot: {},
      blockActivity: [],
    },
  }
}

export function toggle(f: PomoFile, now: number, slug: string, cfg: PomoConfig): Transition {
  const state = pomoState(f, now, cfg)
  if (state === 'running' || state === 'break') return pause(f, now, cfg)
  if (state === 'paused') return resume(f, now, cfg)
  return start(f, now, slug, cfg)
}
```

The error texts call `pomoDots`, which Task 2 rewrites. For this task, make `pomoDots` produce the new strings now (Task 2 adds its own tests for every state). Replace its body with:

```ts
export function pomoDots(f: PomoFile, now: number, cfg: PomoConfig): string {
  const every = Math.max(1, cfg.longBreakEvery)
  if (f.isStopped) return '⏹ off'
  // Paused: everything reads at the moment it froze.
  const at = f.pausedAt || now
  const brk = onBreak(f, at)
  const filled = brk?.isLong ? every : f.blocksDone % every
  const dots = `${'●'.repeat(filled)}${'○'.repeat(every - filled)}`
  const paused = f.pausedAt ? ' paused' : ''
  if (brk) return `${f.pausedAt ? '⏸' : '☕'} ${dots} ${brk.isLong ? 'long break' : 'break'} ${brk.minutesLeft}m left${paused}`
  if (f.blockStartedAt !== 0) return `${f.pausedAt ? '⏸' : '🍅'} ${dots} ${blockMinutes(f, at)}/${cfg.focusMinutes}m${paused}`
  return `○ ${dots} idle`
}
```

- [ ] **Step 5: Fix the existing tests the new strings and event fields change**

- `'○○○○ 12/25m'` → `'🍅 ○○○○ 12/25m'` (restart test).
- `'○○○○ break'` → `'○ ○○○○ idle'` (idle test).
- `'●○○○ break 5m left'` → `'☕ ●○○○ break 5m left'`; `'●●●● long break 29m left'` → `'☕ ●●●● long break 29m left'`; `'●○○○ break'` (after the break ended) → `'○ ●○○○ idle'`.
- The three `expect(last.event).toEqual({ kind: 'break', … })` → `toMatchObject` (the event now also carries `openedAt`, `snapshot`, `activity`).
- The band test regex `/●○○○ 12\/25m/` still matches; leave it.

- [ ] **Step 6: Run all tests**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `63 pass`, `0 fail`. Then `claude plugin validate .` → `✔ Validation passed`.

- [ ] **Step 7: Commit (on Q's go)**

```bash
git add claude-config/task-track/types/index.d.ts
git add claude-config/task-track/hooks/pomo.ts
git add claude-config/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): pause, resume, stop and start the shared pomodoro"
```

---

### Task 2: Timer text for every state

**Files:**
- Test: `claude-config/task-track/tests/task-track.test.ts` (in `describe('controls')`)
- Modify: `claude-config/task-track/hooks/pomo.ts` only if a case fails

**Interfaces:**
- Consumes: `pomoDots`, `pause`, `stop`, `start` from Task 1.
- Produces: nothing new; pins the strings the band, the pane and every error message use.

- [ ] **Step 1: Write the test**

```ts
  test('the timer reads the state at a glance', () => {
    const f = running()
    expect(pomoDots(f, T0 + 10 * MIN, CFG)).toBe('🍅 ○○○○ 10/25m')
    const paused = ok(pause(f, T0 + 10 * MIN, CFG))
    expect(pomoDots(paused, T0 + 50 * MIN, CFG)).toBe('⏸ ○○○○ 10/25m paused')
    let b = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    for (let m = 1; m <= 25; m++) b = sessionMinute(b, T0 + m * MIN, true, 'a').file
    expect(pomoDots(b, T0 + 26 * MIN, CFG)).toBe('☕ ●○○○ break 4m left')
    expect(pomoDots(ok(pause(b, T0 + 26 * MIN, CFG)), T0 + 40 * MIN, CFG)).toBe('⏸ ●○○○ break 4m left paused')
    expect(pomoDots(ok(stop(f, T0 + 10 * MIN, CFG)), T0 + 11 * MIN, CFG)).toBe('⏹ off')
    expect(pomoDots(emptyPomo('2026-10-13'), T0, CFG)).toBe('○ ○○○○ idle')
  })
```

- [ ] **Step 2: Run**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `64 pass`. If a line fails, fix `pomoDots` to the exact string in Global Constraints, not the test.

- [ ] **Step 3: Commit (on Q's go)**

```bash
git add claude-config/task-track/tests/task-track.test.ts
git commit -m "test(task-track): pin the timer text for every state"
```

---

### Task 3: `/pomo` and the band buttons

**Files:**
- Modify: `claude-config/task-track/hooks/register.tsx` (imports, `COMMANDS`, a `runPomo` helper after `markActive`, the `command.run` handlers, the `AbovePrompt` render)
- Test: `claude-config/task-track/tests/task-track.test.ts` (new `describe('/pomo and the band controls')`)

**Interfaces:**
- Consumes: `pause`, `resume`, `stop`, `start`, `toggle`, `pomoState`, `pomoDots`, `Transition` from Task 1; existing `changePomo`, `flushFocus`, `pomoPath`, `load`, `read($, task)`.
- Produces: `type PomoAction = 'toggle' | 'start' | 'pause' | 'resume' | 'stop'`, `runPomo($, action): Promise<string>` (register-local), band buttons keyed `pomo-pause`, `pomo-resume`, `pomo-stop`, `pomo-start`.

- [ ] **Step 1: Write the failing tests** (before `describe('throttling'`; `On` and `PomoFile` are already imported):

```ts
describe('/pomo and the band controls', () => {
  const NOW = T0 + 10 * MIN
  const POMO = '/v/Tasks/.pomo.json'
  const running = (): PomoFile => ({
    ...touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG),
    lastActiveAt: NOW - MIN,
    creditedUntil: NOW - MIN,
    dayMs: { 'set-up-vault': 9 * MIN },
  })
  const fileOf = (t: { file: PomoFile } | { error: string }) => {
    if ('error' in t) throw new Error(t.error)
    return t.file
  }
  function setup(on: On, timer: PomoFile | string) {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: NOW })
    return fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE, [POMO]: typeof timer === 'string' ? timer : serializePomo(timer) })
  }
  const shared = (files: Record<string, string>) => parsePomo(files[POMO] ?? '') as PomoFile

  test('/pomo pauses, /pomo again resumes', async ($, on) => {
    const files = setup(on, running())
    expect((await run($, 'pomo', '')).text).toBe('⏸ ○○○○ 10/25m paused · set-up-vault')
    expect(shared(files).pausedAt).toBe(NOW)
    expect((await run($, 'pomo', '')).text).toBe('🍅 ○○○○ 10/25m · set-up-vault')
  })

  test('a transition that does not fit, or an unknown word, changes nothing', async ($, on) => {
    const files = setup(on, running())
    const before = files[POMO]
    expect((await run($, 'pomo', 'resume')).text).toBe('Not paused (🍅 ○○○○ 10/25m).')
    expect((await run($, 'pomo', 'foo')).text).toBe('Unknown: /pomo foo. Use start|pause|resume|stop')
    expect(files[POMO]).toBe(before)
  })

  test('a pause pressed after another session paused says so', async ($, on) => {
    setup(on, fileOf(pause(running(), NOW, CFG)))
    expect((await run($, 'pomo', 'pause')).text).toBe('Already paused (⏸ ○○○○ 10/25m paused).')
  })

  test('/pomo stop logs the focus so far to the task Log', async ($, on) => {
    const files = setup(on, running())
    expect((await run($, 'pomo', 'stop')).text).toBe('⏹ off · set-up-vault')
    expect(files[PATH]).toContain('— focus 10m')
    expect(shared(files).isStopped).toBe(true)
  })

  test('an unreadable timer file is named and left alone', async ($, on) => {
    const files = setup(on, '{"version":1,"slug":"x"')
    expect((await run($, 'pomo', 'pause')).text).toBe("Can't read /v/Tasks/.pomo.json: not a timer file. Nothing changed.")
    expect(files[POMO]).toBe('{"version":1,"slug":"x"')
  })

  test('the band shows the buttons for the state, and ⏸ pauses the shared file', async ($, on) => {
    const files = setup(on, running())
    const toasts: string[] = []
    on('ui.toast', ($, e) => {
      toasts.push(e.text)
      return { value: undefined }
    })
    await run($, 'openloop', 'load the task')
    const band = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
    expect(await band.find({ type: 'Button', key: 'pomo-pause' })).toBeDefined()
    expect(await band.find({ type: 'Button', key: 'pomo-stop' })).toBeDefined()
    expect(await band.find({ type: 'Button', key: 'pomo-start' })).toBeUndefined()
    await band.press({ key: 'pomo-pause' })
    expect(shared(files).pausedAt).toBe(NOW)
    expect(toasts).toContain('⏸ ○○○○ 10/25m paused · set-up-vault')
  })

  test('a stopped timer shows only ▶ Start', async ($, on) => {
    setup(on, fileOf(stop(running(), NOW, CFG)))
    await run($, 'openloop', 'load the task')
    const band = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
    expect(await band.find({ type: 'Button', key: 'pomo-start' })).toBeDefined()
    expect(await band.find({ type: 'Button', key: 'pomo-pause' })).toBeUndefined()
    expect(await band.find({ type: 'Text', text: /⏹ off/ })).toBeDefined()
  })
})
```

Add `pause, stop` to the `../hooks/pomo` import if Task 1 didn't already.

Note on `openloop`: it calls `markActive`, which touches the running file at `NOW` (1 minute since `lastActiveAt`). The timer stays running at 10/25m. With a stopped file the touch is a no-op (Task 1 guard).

- [ ] **Step 2: Run to see them fail**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: 7 failures. The `/pomo` tests fail with the engine's unknown-command answer, the band tests on the missing `pomo-pause` button.

- [ ] **Step 3: Implement in `hooks/register.tsx`**

Imports from `./pomo`: add `pause, pomoState, resume, start, stop, toggle`; from the types: `import type { DayTotals, PomoConfig, PomoEvent, Transition } from './pomo'`.

`COMMANDS`, add:

```ts
  { name: 'pomo', description: 'Pomodoro: /pomo pauses or resumes; /pomo start|pause|resume|stop', argumentHint: '[start|pause|resume|stop]', immediate: true },
```

After `markActive`:

```ts
type PomoAction = 'toggle' | 'start' | 'pause' | 'resume' | 'stop'
const POMO_ACTIONS: readonly string[] = ['start', 'pause', 'resume', 'stop']

/**
 * One control of the shared timer, from /pomo or a band button. It does not mark activity:
 * a touch first would start a block and turn `/pomo start` into "already running".
 * Returns what to tell Q.
 */
async function runPomo($: EngineInterface, action: PomoAction): Promise<string> {
  const view = (await read($, task)) ?? (await load($))
  if (!view) return 'No active task. /task-start <name>'
  const now = await $.clock.now()
  const out: { t?: Transition } = {}
  const f = await changePomo($, file => {
    const t =
      action === 'toggle' ? toggle(file, now, view.slug, settings)
      : action === 'start' ? start(file, now, view.slug, settings)
      : action === 'pause' ? pause(file, now, settings)
      : action === 'resume' ? resume(file, now, settings)
      : stop(file, now, settings)
    out.t = t
    return 'error' in t ? file : t.file
  })
  if (!f) return `Can't read ${await pomoPath($)}: not a timer file. Nothing changed.`
  const t = out.t
  if (!t) throw new Error(`runPomo(${action}): changePomo returned a file without running the change`)
  if ('error' in t) return t.error
  if (action === 'stop') await flushFocus($, view.slug, view.path)
  return `${pomoDots(f, now, settings)} · ${view.slug}`
}

async function pressPomo($: EngineInterface, action: PomoAction): Promise<void> {
  $.ui.toast(await runPomo($, action))
}
```

The command handler, next to `openloop`:

```ts
  on('command.run', { command: 'pomo' }, async ($, e) => {
    const arg = e.args.trim()
    if (arg && !POMO_ACTIONS.includes(arg)) return { text: `Unknown: /pomo ${arg}. Use start|pause|resume|stop` }
    return { text: await runPomo($, (arg || 'toggle') as PomoAction) }
  })
```

The `AbovePrompt` render: compute `const now = await $.clock.now()` once, use it for `pomoDots(p, now, settings)`, add `const state = pomoState(p, now, settings)`, and after the timer `<Box>` add:

```tsx
        <Box flexShrink={0} gap={1}>
          {(state === 'running' || state === 'break') && <Button key="pomo-pause" label="⏸ Pause" onPress={() => pressPomo($, 'pause')} />}
          {state === 'paused' && <Button key="pomo-resume" label="▶ Resume" onPress={() => pressPomo($, 'resume')} />}
          {state !== 'stopped' && state !== 'idle' && <Button key="pomo-stop" label="⏹ Stop" onPress={() => pressPomo($, 'stop')} />}
          {(state === 'stopped' || state === 'idle') && <Button key="pomo-start" label="▶ Start" onPress={() => pressPomo($, 'start')} />}
        </Box>
```

The pane header already calls `pomoDots`, so it shows the new text with no change.

- [ ] **Step 4: Run all tests**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `71 pass`, `0 fail`.
If the ⏸ press test fails because the toast never arrives, read the failure first: the `ui.toast` stub's return shape may be wrong. The answer types are under `'ui.toast'` in `.claude-plugin/types/claude-code/index.d.ts`. Then `claude plugin validate .`.

- [ ] **Step 5: Manual check in a live session** (the tests run `$.command.run` directly, so they can't show whether typing `/pomo` first fires `prompt.submit`, which would mark activity and start a block):

With the timer idle (`○ … idle`), type `/pomo start`. Expected reply: `🍅 ●●○○ 0/25m · <slug>`, not `Already running`. If it says `Already running`, stop and report to Q (RULE 0). The fix would be to skip `markActive` for prompts that start with `/pomo`.

- [ ] **Step 6: Commit (on Q's go)**

```bash
git add claude-config/task-track/hooks/register.tsx
git add claude-config/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): /pomo and band buttons to start, pause, resume and stop the timer"
```

---

### Task 4: Break summary from the notes

**Files:**
- Create: `claude-config/task-track/hooks/summary.ts`
- Modify: `claude-config/task-track/hooks/pomo.ts` (`snapshotTask`)
- Modify: `claude-config/task-track/hooks/register.tsx` (`markActive`, `runPomo`, `tick`)
- Test: `claude-config/task-track/tests/task-track.test.ts` (new `describe('break summary')`, plus one existing tick assertion)

**Interfaces:**
- Consumes: `parseNote`, `sectionRange`, `splitEstimate`, `stamp`, `truncate` from `hooks/note.ts`; `PomoEvent` with `openedAt`, `snapshot`, `activity` (Task 1); `runPomo` (Task 3).
- Produces:
  - `hooks/summary.ts`: `type NoteRead = { slug: string; text: string } | { slug: string; error: string }`, `checkedTitles(next: readonly NextItem[]): string[]`, `logSince(text: string, openedAt: number): string[]`, `blockSummary(notes: readonly NoteRead[], snapshot: Record<string, string[]>, openedAt: number): string`
  - `hooks/pomo.ts`: `snapshotTask(f: PomoFile, slug: string, checked: string[]): PomoFile`

- [ ] **Step 1: Write the failing tests** (add `import { blockSummary, checkedTitles, logSince } from '../hooks/summary'` and `snapshotTask` to the pomo import):

```ts
describe('break summary', () => {
  const OPENED = new Date(2026, 9, 13, 9, 0).getTime()
  const note = (next: string, log: string) => `---\nstatus: active\n---\n# T\n\n## Next\n${next}\n\n## Log\n${log}\n`

  test('lists items checked during the block, not before it', () => {
    const text = note('- [x] Old one\n- [x] Rewrite plan tasks 1–6 (~2 h)\n- [ ] Later', '')
    expect(blockSummary([{ slug: 'a', text }], { a: ['Old one'] }, OPENED)).toBe('✓ Rewrite plan tasks 1–6')
  })

  test('a task switched to mid-block is compared with its snapshot at the switch', () => {
    const f = { ...touch(emptyPomo('2026-10-13'), T0, 'a', CFG) }
    const withA = snapshotTask(f, 'a', ['Old one'])
    const withB = snapshotTask(withA, 'b', ['B done before'])
    expect(snapshotTask(withB, 'a', ['changed'])).toBe(withB)
    expect(withB.blockSnapshot).toEqual({ a: ['Old one'], b: ['B done before'] })
    expect(snapshotTask(emptyPomo('2026-10-13'), 'a', ['x']).blockSnapshot).toEqual({})
  })

  test('Log lines from before the block and focus lines are left out', () => {
    const text = note(
      '- [ ] x',
      '- [[2026-10-13]] 08:59 — before\n- [[2026-10-13]] 09:00 — D1 targeted plan ok\n- [[2026-10-13]] 09:20 — focus 25m (1 pomodoro)\n- [[2026-10-13]] 09:21 — key v1 added',
    )
    expect(logSince(text, OPENED)).toEqual(['D1 targeted plan ok', 'key v1 added'])
    expect(blockSummary([{ slug: 'a', text }], { a: [] }, OPENED)).toBe('📝 2 notes: "D1 targeted plan ok", "key v1 added"')
  })

  test('resume keeps the block\'s wall-clock start, so a pause drops no Log lines', () => {
    const f = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    const p = pause(f, T0 + 5 * MIN, CFG)
    if ('error' in p) throw new Error(p.error)
    const r = resume(p.file, T0 + 30 * MIN, CFG)
    if ('error' in r) throw new Error(r.error)
    expect(r.file.blockOpenedAt).toBe(T0)
  })

  test('nothing checked or logged is a nudge; long lists are cut', () => {
    expect(blockSummary([{ slug: 'a', text: note('- [ ] x', '') }], { a: [] }, OPENED)).toBe('Nothing checked or logged this block.')
    const many = note(['one', 'two', 'three', 'four', 'a title that is far longer than forty characters in total'].map(t => `- [x] ${t}`).join('\n'), '')
    expect(blockSummary([{ slug: 'a', text: many }], { a: [] }, OPENED)).toBe('✓ one · ✓ two · ✓ three +2 more')
    const long = note('- [x] a title that is far longer than forty characters in total', '')
    expect(blockSummary([{ slug: 'a', text: long }], { a: [] }, OPENED)).toBe('✓ a title that is far longer than forty c…')
  })

  test('an unreadable note is named; the others still count', () => {
    const text = note('- [x] done', '')
    expect(blockSummary([{ slug: 'a', text }, { slug: 'b', error: 'ENOENT' }], { a: [], b: [] }, OPENED)).toBe("✓ done (couldn't read b)")
  })

  test('a file from before snapshots lists only Log lines', () => {
    const text = note('- [x] done long ago', '- [[2026-10-13]] 09:05 — fresh')
    expect(blockSummary([{ slug: 'a', text }], {}, OPENED)).toBe('📝 1 note: "fresh"')
  })

  test('checkedTitles drops estimates and backticks', () => {
    expect(checkedTitles([{ text: 'Run `plan` (~10 min)', isDone: true }, { text: 'open', isDone: false }])).toEqual(['Run plan'])
  })

  test('a block whose note is gone still announces its break and names the note', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    const clock = mock.clock(on, { now: T0 + 24 * MIN + 30_000 })
    const held = { ...touch(emptyPomo('2026-10-13'), T0, 'gone', CFG), lastActiveAt: T0 + 24 * MIN }
    const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE, '/v/Tasks/.pomo.json': serializePomo(held) })
    on('session.start', ($, e) => ({ cwd: e.cwd }))
    on('command.register', ($, e) => ({ value: { command: e.name } }))
    const notified: string[] = []
    on('ui.notify', ($, e) => {
      notified.push(e.text)
      return { value: { isSent: true as const, channel: 'terminal_bell' as const } }
    })
    await $.session.start({ cwd: '/elsewhere', surface: 'terminal', isInteractive: true })
    await clock.advance(MIN)
    expect(parsePomo(files['/v/Tasks/.pomo.json'] ?? '')?.breakUntil).toBeGreaterThan(0)
    expect(notified).toEqual(["Pomodoro 1 done on gone. Break: 5 min.\nNothing checked or logged this block. (couldn't read gone)"])
  })
})
```

In the existing test `the minute tick moves the one timer even when another task holds it`, replace
`expect(notified).toEqual(['Pomodoro 1 done on other. Break: 5 min.'])` with
`expect(notified[0]?.split('\n')[0]).toBe('Pomodoro 1 done on other. Break: 5 min.')`.

- [ ] **Step 2: Run to see them fail**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `(fail) the file did not load` (`../hooks/summary` does not exist).

- [ ] **Step 3: Create `hooks/summary.ts`**

```ts
// What a finished block got done, from the task notes. Pure: register.tsx reads the notes.
import type { NextItem } from '../types'
import { parseNote, sectionRange, splitEstimate, stamp, truncate } from './note'

export type NoteRead = { slug: string; text: string } | { slug: string; error: string }

const BULLET = /^\s*- (.*\S)\s*$/
const LOG_LINE = /^\[\[(\d{4}-\d{2}-\d{2})\]\]\s*(\d{2}:\d{2})\s+—\s+(.*)$/
const MAX_ITEMS = 3
const MAX_CHARS = 40

/** Checked Next items as titles: no estimate, no backticks. The snapshot and the diff both use this form. */
export function checkedTitles(next: readonly NextItem[]): string[] {
  return next.filter(n => n.isDone).map(n => splitEstimate(n.text).text.replaceAll('`', ''))
}

/** The text of `## Log` lines stamped at or after `openedAt` (local time), without the plugin's own focus lines. */
export function logSince(text: string, openedAt: number): string[] {
  const lines = text.split('\n')
  const range = sectionRange(lines, 'Log')
  if (!range) return []
  const { date, time } = stamp(new Date(openedAt))
  const from = `${date} ${time}`
  return lines.slice(range[0] + 1, range[1]).flatMap(line => {
    const bullet = BULLET.exec(line)?.[1] ?? ''
    const m = LOG_LINE.exec(bullet)
    if (!m || `${m[1]} ${m[2]}` < from || (m[3] ?? '').startsWith('focus ')) return []
    return [m[3] ?? '']
  })
}

function capped(items: readonly string[], show: (t: string) => string, sep: string): string {
  const shown = items.slice(0, MAX_ITEMS).map(t => show(truncate(t, MAX_CHARS))).join(sep)
  return items.length > MAX_ITEMS ? `${shown} +${items.length - MAX_ITEMS} more` : shown
}

/**
 * One line for the break notification. Items count when checked now and not in the task's
 * snapshot; a task without a snapshot (a file from before snapshots) adds only its Log lines.
 */
export function blockSummary(notes: readonly NoteRead[], snapshot: Record<string, string[]>, openedAt: number): string {
  const checked: string[] = []
  const logged: string[] = []
  const unread: string[] = []
  for (const n of notes) {
    if ('error' in n) {
      unread.push(n.slug)
      continue
    }
    const before = snapshot[n.slug]
    if (before) {
      const was = new Set(before)
      checked.push(...checkedTitles(parseNote(n.slug, '', n.text, 0).next).filter(t => !was.has(t)))
    }
    logged.push(...logSince(n.text, openedAt))
  }
  const parts: string[] = []
  if (checked.length) parts.push(`✓ ${capped(checked, t => t, ' · ✓ ')}`)
  if (logged.length) parts.push(`📝 ${logged.length === 1 ? '1 note' : `${logged.length} notes`}: ${capped(logged, t => `"${t}"`, ', ')}`)
  const body = parts.length ? parts.join(' · ') : 'Nothing checked or logged this block.'
  return unread.length ? `${body} (couldn't read ${unread.join(', ')})` : body
}
```

In `hooks/pomo.ts`, after `toggle`:

```ts
/** Records a task's checked items the first time the running block reaches it; no-op without a block. */
export function snapshotTask(f: PomoFile, slug: string, checked: string[]): PomoFile {
  if (f.blockOpenedAt === 0 || slug in f.blockSnapshot) return f
  return { ...f, blockSnapshot: { ...f.blockSnapshot, [slug]: checked } }
}
```

- [ ] **Step 4: Run the pure tests**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `79 pass`, `1 fail`: the gone-note tick test needs the wiring in Step 5. The tick assertion change passes before the wiring too.

- [ ] **Step 5: Wire it in `hooks/register.tsx`**

Import `snapshotTask` from `./pomo`, and `blockSummary, checkedTitles` plus `type NoteRead` from `./summary`.

`markActive`, the last line becomes:

```ts
  await changePomo($, f => snapshotTask(touch(f, now, view.slug, settings), view.slug, checkedTitles(view.next)))
```

`runPomo`, inside the `changePomo` callback, `return 'error' in t ? file : snapshotTask(t.file, view.slug, checkedTitles(view.next))`.

`tick`, replace the `const text = …` lines with:

```ts
  const root = await resolveVault($)
  const slugs = [...new Set([event.slug, ...Object.keys(event.snapshot)])]
  // A note that can't be read is named in the summary; the break has already started.
  const notes: NoteRead[] = await Promise.all(
    slugs.map(slug =>
      $.fs.read(`${root}/Tasks/${slug}.md`).then(
        text => ({ slug, text }),
        (err: unknown) => ({ slug, error: err instanceof Error ? err.message : String(err) }),
      ),
    ),
  )
  const header = event.isLong
    ? `${event.blocks} pomodoros on ${event.slug}. Long break: ${event.minutes} min.`
    : `Pomodoro ${event.blocks} done on ${event.slug}. Break: ${event.minutes} min.`
  const text = `${header}\n${blockSummary(notes, event.snapshot, event.openedAt)}`
```

(the `$.ui.toast(text)` and `$.ui.notify(...)` lines after it stay).

- [ ] **Step 6: Run all tests**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `80 pass`, `0 fail`. Then `claude plugin validate .`.

- [ ] **Step 7: Commit (on Q's go)**

```bash
git add claude-config/task-track/hooks/summary.ts
git add claude-config/task-track/hooks/pomo.ts
git add claude-config/task-track/hooks/register.tsx
git add claude-config/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): the break notification says what the block got done"
```

---

### Task 5: Opt-in AI line (`breakSummaryAI`)

**Files:**
- Modify: `claude-config/task-track/.claude-plugin/plugin.json` (new option)
- Modify: `claude-config/task-track/hooks/pomo.ts` (`recordActivity`, `MAX_ACTIVITY`)
- Modify: `claude-config/task-track/hooks/summary.ts` (`SUMMARY_SYSTEM`, `summaryPrompt`)
- Modify: `claude-config/task-track/hooks/register.tsx` (`Settings`, `readSettings`, `noteActivity`, `aiLine`, `prompt.submit`, `tool.call`, `tick`)
- Test: `claude-config/task-track/tests/task-track.test.ts` (new `describe('AI line')`)

**Interfaces:**
- Consumes: `pomoState`, the break event's `activity` (Task 1), `blockSummary` (Task 4), `truncate` from `hooks/note.ts`.
- Produces: `recordActivity(f: PomoFile, entry: string): PomoFile`, `MAX_ACTIVITY = 60`, `SUMMARY_SYSTEM: string`, `summaryPrompt(slug: string, noteSummary: string, activity: readonly string[]): string`, setting `breakSummaryAI: boolean`.

- [ ] **Step 1: Write the failing tests** (add `recordActivity` to the pomo import and `summaryPrompt` to the summary import):

```ts
describe('AI line', () => {
  const POMO = '/v/Tasks/.pomo.json'
  const NOW = T0 + 10 * MIN
  const running = (): PomoFile => ({ ...touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG), lastActiveAt: NOW - MIN, creditedUntil: NOW - MIN })
  function setup(on: On, timer: PomoFile, now = NOW) {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    const clock = mock.clock(on, { now })
    on('prompt.submit', ($, e) => ({ text: e.text }))
    const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE, [POMO]: serializePomo(timer) })
    return { files, clock }
  }
  const activity = (files: Record<string, string>) => (parsePomo(files[POMO] ?? '') as PomoFile).blockActivity

  test('nothing is recorded while the setting is off', async ($, on) => {
    const { files } = setup(on, running())
    await run($, 'openloop', 'load the task')
    await $.prompt.submit({ text: 'hello' })
    expect(activity(files)).toEqual([])
  })

  test('with the setting on, prompts are recorded only while a block runs', { options: { breakSummaryAI: true } }, async ($, on) => {
    const p = pause(running(), NOW, CFG)
    if ('error' in p) throw new Error(p.error)
    const { files } = setup(on, p.file)
    await run($, 'openloop', 'load the task')
    await $.prompt.submit({ text: 'while paused' })
    expect(activity(files)).toEqual([])
    await run($, 'pomo', 'resume')
    await $.prompt.submit({ text: 'write the scrub' })
    expect(activity(files)).toEqual(['prompt: write the scrub'])
  })

  test('repeats are dropped, the list keeps the last 60, a new block clears it', () => {
    let f = touch(emptyPomo('2026-10-13'), T0, 'a', CFG)
    f = recordActivity(recordActivity(f, 'ran: ls'), 'ran: ls')
    expect(f.blockActivity).toEqual(['ran: ls'])
    for (let i = 0; i < 70; i++) f = recordActivity(f, `edit: f${i}`)
    expect(f.blockActivity.length).toBe(60)
    expect(f.blockActivity[59]).toBe('edit: f69')
    expect(touch(f, T0 + 60 * MIN, 'a', CFG).blockActivity).toEqual([])
  })

  test('summaryPrompt holds the task, the note summary and the log', () => {
    expect(summaryPrompt('a', '✓ done', ['prompt: x', 'edit: hooks/pomo.ts'])).toBe(
      'Task: a\nFrom the task note: ✓ done\nActivity during the block, oldest first:\n- prompt: x\n- edit: hooks/pomo.ts',
    )
    expect(summaryPrompt('a', 'Nothing checked or logged this block.', [])).toContain('- (none recorded)')
  })

  /** Starts the session, lets the minute tick finish a block, returns the toasts in order. */
  async function finishBlock($: Engine, on: On, answer: unknown) {
    const held = { ...touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG), lastActiveAt: T0 + 24 * MIN }
    const { clock } = setup(on, held, T0 + 24 * MIN + 30_000)
    on('session.start', ($, e) => ({ cwd: e.cwd }))
    on('command.register', ($, e) => ({ value: { command: e.name } }))
    on('ui.notify', () => ({ value: { isSent: true as const, channel: 'terminal_bell' as const } }))
    const toasts: string[] = []
    on('ui.toast', ($, e) => {
      toasts.push(e.text)
      return { value: undefined }
    })
    on('model.complete', () => ({ value: answer }) as never)
    await $.session.start({ cwd: '/elsewhere', surface: 'terminal', isInteractive: true })
    await clock.advance(MIN)
    return toasts
  }

  test('the AI line follows the note summary', { options: { breakSummaryAI: true } }, async ($, on) => {
    const toasts = await finishBlock($, on, { isAnswered: true, text: 'Wrote the archive scrub.\n', usage: {} })
    expect(toasts).toEqual(['Pomodoro 1 done on set-up-vault. Break: 5 min.\nNothing checked or logged this block.', 'Wrote the archive scrub.'])
  })

  test('a failed call says why; the note summary was already shown', { options: { breakSummaryAI: true } }, async ($, on) => {
    const toasts = await finishBlock($, on, { isAnswered: false, reason: 'api-error', status: 529, error: 'overloaded_error' })
    expect(toasts[1]).toBe('(AI summary failed: api-error)')
  })
})
```

`Engine` and `On` are already imported at the top of the test file.

- [ ] **Step 2: Run to see them fail**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `(fail) the file did not load` (`recordActivity` is not exported).
If, after Step 4, the `model.complete` stub is reported as answering wrongly ("returned neither…"), read the `'model.complete'` entries under `declare module 'claude-code/testing'` in `.claude-plugin/types/claude-code/index.d.ts` and fix the stub's shape, not the code.

- [ ] **Step 3: Pure parts**

`hooks/pomo.ts`:

```ts
/** Entries kept for the AI summary: enough for 25 minutes, small enough for one short Haiku call. */
export const MAX_ACTIVITY = 60

/** Appends one activity entry unless it repeats the last one; keeps the newest MAX_ACTIVITY. */
export function recordActivity(f: PomoFile, entry: string): PomoFile {
  if (f.blockActivity.at(-1) === entry) return f
  return { ...f, blockActivity: [...f.blockActivity, entry].slice(-MAX_ACTIVITY) }
}
```

`hooks/summary.ts`:

```ts
export const SUMMARY_SYSTEM =
  'You summarize one 25-minute work block for the person who did it. Reply with one line under 120 characters saying what got done, in plain words. No preamble, no quotes.'

export function summaryPrompt(slug: string, noteSummary: string, activity: readonly string[]): string {
  const lines = activity.length ? activity.map(a => `- ${a}`) : ['- (none recorded)']
  return [`Task: ${slug}`, `From the task note: ${noteSummary}`, 'Activity during the block, oldest first:', ...lines].join('\n')
}
```

- [ ] **Step 4: Setting and wiring**

`.claude-plugin/plugin.json`, in `options` after `notesToClaude`:

```json
    "breakSummaryAI": {
      "type": "boolean",
      "title": "AI line in the break notification",
      "description": "Off by default. While on, each block records your prompts (first 80 characters), files Claude edits and commands it runs in vault/Tasks/.pomo.json, a file in your synced vault, and asks Claude Haiku for one line on what got done (about $0.0005 a break).",
      "default": false
    }
```

`hooks/register.tsx`:

- `Settings` gains `breakSummaryAI: boolean`; the default object gets `breakSummaryAI: false`; `readSettings` gets `breakSummaryAI: options.breakSummaryAI === true,`.
- Imports: `recordActivity` from `./pomo`; `SUMMARY_SYSTEM, summaryPrompt` from `./summary`.
- After `markActive`:

```ts
/** One entry for the AI summary, only while it is on and a block runs (not paused, stopped or on break). */
async function noteActivity($: EngineInterface, entry: string): Promise<void> {
  if (!settings.breakSummaryAI) return
  const now = await $.clock.now()
  if (pomoState(await read($, pomo), now, settings) !== 'running') return
  await changePomo($, f => (pomoState(f, now, settings) === 'running' ? recordActivity(f, entry) : f))
}

/** The opt-in AI line, after the note summary is on screen. A failed call says why. */
async function aiLine($: EngineInterface, slug: string, noteSummary: string, activity: readonly string[]): Promise<void> {
  const r = await $.model
    .complete({ model: 'claude-haiku-5-5', system: SUMMARY_SYSTEM, prompt: summaryPrompt(slug, noteSummary, activity), maxTokens: 120, effort: 'low', timeoutMs: 10_000 })
    .catch((err: unknown) => ({ isAnswered: false as const, reason: err instanceof Error ? err.message : String(err) }))
  if (!r.isAnswered) {
    $.ui.toast(`(AI summary failed: ${r.reason})`)
    return
  }
  const text = r.text.trim()
  $.ui.toast(text)
  void $.ui.notify(text, { title: 'task-track' })
}
```

- `prompt.submit` handler, after `await remindBreak($)`:

```ts
    await noteActivity($, `prompt: ${truncate(e.text.trim().replaceAll('\n', ' '), 80)}`)
```

- `tool.call` handler, right after `await markActive($, true)`:

```ts
    if (isEdit && path) {
      const root = await $.session.root()
      await noteActivity($, `edit: ${path.startsWith(`${root}/`) ? path.slice(root.length + 1) : path}`)
    }
    if (e.tool === 'Bash' && 'command' in e && typeof e.command === 'string') await noteActivity($, `ran: ${truncate(e.command, 80)}`)
```

(move the existing `isEdit` / `path` declarations above this block).

- `tick`: keep the summary in a variable and await the AI line last:

```ts
  const summary = blockSummary(notes, event.snapshot, event.openedAt)
  const text = `${header}\n${summary}`
  $.ui.toast(text)
  void $.ui.notify(text, { title: 'task-track' })
  if (settings.breakSummaryAI) await aiLine($, event.slug, summary, event.activity)
```

- [ ] **Step 5: Run all tests**

Run: `claude plugin test . 2>&1 | grep -E '^\(fail\)|^ *[0-9]+ (pass|fail)'`
Expected: `86 pass`, `0 fail`. Then `claude plugin validate .` → passes with the new option.

- [ ] **Step 6: Commit (on Q's go)**

```bash
git add claude-config/task-track/.claude-plugin/plugin.json
git add claude-config/task-track/hooks/pomo.ts
git add claude-config/task-track/hooks/summary.ts
git add claude-config/task-track/hooks/register.tsx
git add claude-config/task-track/tests/task-track.test.ts
git commit -m "feat(task-track): opt-in Haiku line in the break notification"
```

---

### Task 6: Docs

**Files:**
- Modify: `claude-config/task-track/README.md`
- Modify: `claude-config/task-track/.claude-plugin/plugin.json` (`description`)

- [ ] **Step 1: `plugin.json` description** becomes:

```json
  "description": "Keeps the active Obsidian task note in view (band, pane), runs one shared Pomodoro you can /pomo start, pause, resume and stop, and lets /note, /done, /openloop write to the note without a model turn.",
```

- [ ] **Step 2: README.** Under `## Pomodoro (shared across sessions)`, after the `Breaks are timed` bullet, add:

```markdown
- **Controls.** `/pomo` pauses or resumes (and starts the timer when it is stopped or idle); `/pomo start|pause|resume|stop` for the rest. The band shows ⏸ Pause / ▶ Resume / ⏹ Stop / ▶ Start for the current state. Pause freezes a block or a break; stop credits the time so far, logs it, and keeps activity from starting a block until `/pomo start` or the next day. Other sessions show a change on their next minute tick.
- **States at a glance.** `🍅 ●●○○ 12/25m` running · `⏸ … paused` · `☕ ●○○○ break 4m left` · `☕ ●●●● long break 29m left` · `⏹ off` · `○ ●●○○ idle`.
- **Break summary.** The break notification lists the Next items checked and the Log lines written during the block (`✓ … · 📝 2 notes: "…"`), or says nothing was. With `breakSummaryAI` on, a one-line Claude Haiku summary of the block follows.
```

In the settings table, add a row:

```markdown
| `breakSummaryAI` | `false` | One-line Haiku summary in the break notification. Records your prompts (first 80 chars), edited files and commands during each block in `vault/Tasks/.pomo.json`, a synced file. About $0.0005 a break. |
```

(match the table's existing columns; read its header first).

- [ ] **Step 3: Verify**

Run: `claude plugin validate . && claude plugin test . 2>&1 | grep -E '^ *[0-9]+ (pass|fail)'`
Expected: `✔ Validation passed`, `86 pass`, `0 fail`.

- [ ] **Step 4: Commit (on Q's go)**

```bash
git add claude-config/task-track/README.md
git add claude-config/task-track/.claude-plugin/plugin.json
git commit -m "docs(task-track): pomodoro controls, states and break summary"
```

---

### Final check

- [ ] `claude plugin test .` → 86 pass, 0 fail; `claude plugin validate .` → passes.
- [ ] In a live session: `/pomo` → `⏸ … paused`; band shows ▶ Resume; `/pomo` → running again; `/pomo stop` → `⏹ off` and a `focus …` line in the task Log; a keystroke does not restart it; `/pomo start` → `🍅 … 0/25m`.
- [ ] Whole-branch review by a fresh reviewer (most capable model) before the PR.
