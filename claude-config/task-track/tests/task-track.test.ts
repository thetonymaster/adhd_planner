import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import type { Engine } from 'claude-code/testing'

import { codeSpans, insertInSection, logEntry, logOrder, parseNote, splitEstimate, toggleNext } from '../hooks/note'
import { advance, emptyPomo, markLogged, parsePomo, pomoDots, rollDay, serializePomo, touch, unlogged } from '../hooks/pomo'
import type { PomoFile } from '../types'

const NOTE = `---
status: active
up: "[[ADHD Planner]]"
---
# Set up vault

## Goal
Vault + task loop working.

## Next
- [x] Enable CLI (~2 min)
- [ ] Copy hooks (~10 min)
- [ ]

## Open loops
- iCloud or local?
- ~~resolved one~~ yes

## Parked

## Log
- [[2026-10-12]] 18:25 — vault scaffold created
`

const CFG = { focusMinutes: 25, breakMinutes: 5, longBreakEvery: 4, longBreakMinutes: 30 }

describe('note parsing', () => {
  test('reads title, up, goal, next, loops, log', () => {
    const v = parseNote('set-up-vault', '/v/Tasks/set-up-vault.md', NOTE, 1)
    expect(v.title).toBe('Set up vault')
    expect(v.up).toBe('ADHD Planner')
    expect(v.goal).toBe('Vault + task loop working.')
    expect(v.next).toEqual([
      { text: 'Enable CLI (~2 min)', isDone: true },
      { text: 'Copy hooks (~10 min)', isDone: false },
    ])
    expect(v.openLoops).toEqual(['iCloud or local?'])
    expect(v.log).toEqual(['[[2026-10-12]] 18:25 — vault scaffold created'])
  })

  test('toggleNext flips only the chosen item and keeps everything else', () => {
    const after = toggleNext(NOTE, 1)
    expect(after).toContain('- [x] Copy hooks (~10 min)')
    expect(after).toContain('- [x] Enable CLI (~2 min)')
    expect(after.replace('- [x] Copy hooks', '- [ ] Copy hooks')).toBe(NOTE)
    expect(toggleNext(NOTE, 9)).toBe(NOTE)
  })

  test('insertInSection appends inside the section, before the next heading', () => {
    const after = insertInSection(NOTE, 'Open loops', '- new loop')
    expect(after).toContain('- ~~resolved one~~ yes\n- new loop\n\n## Parked')
    const logged = insertInSection(NOTE, 'Log', '- [[2026-10-13]] 09:30 — note')
    expect(logged.trimEnd().endsWith('- [[2026-10-13]] 09:30 — note')).toBe(true)
  })

  test('insertInSection replaces an empty template bullet and creates a missing section', () => {
    expect(insertInSection('## Log\n- \n', 'Log', '- first')).toBe('## Log\n- first\n')
    expect(insertInSection('# T\n', 'Log', '- first')).toBe('# T\n\n## Log\n- first\n')
  })
})

const MIN = 60_000
const T0 = new Date(2026, 9, 13, 9, 0).getTime()

/** One session's minute: maybe some activity, then its tick against the shared file. */
function sessionMinute(shared: PomoFile, now: number, isActive: boolean, slug = 'set-up-vault') {
  const touched = isActive ? touch(shared, now, slug, CFG) : shared
  return advance(touched, now, CFG)
}

describe('shared pomodoro', () => {
  test('two sessions on one file fill one block in 25 minutes and announce it once', () => {
    let shared = touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG)
    const events: string[] = []
    for (let m = 1; m <= 25; m++) {
      // Session A ticks, then session B ticks 10 s later, each against what the other wrote.
      for (const offset of [0, 10_000]) {
        const r = sessionMinute(shared, T0 + m * MIN + offset, true)
        shared = r.file
        if (r.event.kind === 'break') events.push(`${offset === 0 ? 'A' : 'B'}:${r.event.blocks}`)
      }
    }
    expect(events).toEqual(['A:1'])
    expect(shared.blocksDone).toBe(1)
    // Credited once: ~25 minutes of focus, not 50.
    const minutes = Math.round((shared.dayMs['set-up-vault'] ?? 0) / MIN)
    expect(minutes).toBe(25)
  })

  test('a restart resumes mid-block from the file', () => {
    let shared = touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG)
    for (let m = 1; m <= 12; m++) shared = sessionMinute(shared, T0 + m * MIN, true).file
    const reread = parsePomo(serializePomo(shared))
    expect(reread).not.toBeNull()
    expect(pomoDots(reread as PomoFile, T0 + 12 * MIN, CFG)).toBe('○○○○ 12/25m')
  })

  test('idle for the break length ends the block; the next activity starts a fresh one', () => {
    let shared = touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG)
    for (let m = 1; m <= 10; m++) shared = sessionMinute(shared, T0 + m * MIN, true).file
    const idle = advance(shared, T0 + 16 * MIN, CFG)
    expect(idle.file.blockStartedAt).toBe(0)
    expect(pomoDots(idle.file, T0 + 16 * MIN, CFG)).toBe('○○○○ break')
    const back = touch(idle.file, T0 + 20 * MIN, 'set-up-vault', CFG)
    expect(back.blockStartedAt).toBe(T0 + 20 * MIN)
  })

  test('every 4th block asks for the long break', () => {
    let shared = { ...touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG), blocksDone: 3, lastNotifiedBlock: 3 }
    let last = advance(shared, T0, CFG)
    for (let m = 1; m <= 25; m++) {
      last = sessionMinute(shared, T0 + m * MIN, true)
      shared = last.file
    }
    expect(last.event).toEqual({ kind: 'break', slug: 'set-up-vault', blocks: 4, isLong: true, minutes: 30 })
  })

  test('focus is logged once: unlogged drops to zero after markLogged', () => {
    let shared = touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG)
    for (let m = 1; m <= 30; m++) shared = sessionMinute(shared, T0 + m * MIN, true).file
    expect(Math.round(unlogged(shared, 'set-up-vault').ms / MIN)).toBe(30)
    expect(unlogged(shared, 'set-up-vault').blocks).toBe(1)
    shared = markLogged(shared, 'set-up-vault')
    expect(unlogged(shared, 'set-up-vault')).toEqual({ ms: 0, blocks: 0 })
  })

  test('a new day hands back the finished totals once and starts clean', () => {
    const yesterday = { ...emptyPomo('2026-10-12'), slug: 'set-up-vault', dayMs: { 'set-up-vault': 47 * MIN }, dayBlocks: { 'set-up-vault': 1 } }
    const rolled = rollDay(yesterday, '2026-10-13')
    expect(rolled.finished).toEqual({ day: '2026-10-12', dayMs: { 'set-up-vault': 47 * MIN }, dayBlocks: { 'set-up-vault': 1 }, logged: {} })
    expect(rolled.file.dayMs).toEqual({})
    expect(rollDay(rolled.file, '2026-10-13').finished).toBeUndefined()
  })

  test('a half-written or foreign file reads as null, never as an empty timer', () => {
    expect(parsePomo('{"version":1,"slug":"x"')).toBeNull()
    expect(parsePomo('{"version":2}')).toBeNull()
  })
})

/** An in-memory vault beneath the plugin's $.fs calls. */
function fakeVault(on: On, files: Record<string, string>) {
  let mtime = 1000
  const mtimes: Record<string, number> = Object.fromEntries(Object.keys(files).map(k => [k, mtime]))
  const missing = (path: string) => ({ deny: `ENOENT: ${path}` })
  on('fs.read', ($, e) => {
    const text = files[e.path]
    return text === undefined ? missing(e.path) : { value: text }
  })
  on('fs.write', ($, e) => {
    files[e.path] = e.text
    mtimes[e.path] = ++mtime
    return { value: undefined }
  })
  on('fs.exists', ($, e) => ({
    value: e.path in files || Object.keys(files).some(k => k.startsWith(`${e.path}/`)),
  }))
  on('fs.stat', ($, e) => {
    const text = files[e.path]
    if (text === undefined) return missing(e.path)
    return { value: { kind: 'file' as const, size: text.length, mtimeMs: mtimes[e.path] ?? 0, isLink: false } }
  })
  return files
}

/** Runs a slash command as the person typing it. */
function run($: Engine, command: string, args: string) {
  return $.command.run({ command, args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } })
}

const PATH = '/v/Tasks/set-up-vault.md'

describe('commands write to the note without a model turn', () => {
  test('/note logs a line and tells Claude', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: new Date(2026, 9, 13, 9, 30).getTime() })
    const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE })
    const out = await run($, 'note', 'CLI enabled, unresolved=0')
    expect(out.text).toBe('Logged to set-up-vault.')
    expect(out.context?.[0]).toContain('CLI enabled, unresolved=0')
    expect(files[PATH]).toContain('- [[2026-10-13]] 09:30 — CLI enabled, unresolved=0')
  })

  test('/done checks the first open item; /done 1 reopens item 1', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE })
    const first = await run($, 'done', '')
    expect(first.text).toBe('Done: Copy hooks (~10 min) · 0 left')
    expect(files[PATH]).toContain('- [x] Copy hooks (~10 min)')
    const again = await run($, 'done', '1')
    expect(again.text).toBe('Reopened: Enable CLI (~2 min) · 1 left')
    expect(files[PATH]).toContain('- [ ] Enable CLI (~2 min)')
  })

  test('/openloop adds an open loop; notes stay out of context when turned off', { options: { notesToClaude: false } }, async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE })
    const out = await run($, 'openloop', 'wire eod-shutdown to Daily/')
    expect(out.text).toBe('Open loop added to set-up-vault.')
    expect(out.context).toBeUndefined()
    expect(files[PATH]).toContain('- wire eod-shutdown to Daily/\n\n## Parked')
  })

  test('no active task: commands say how to start one', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    fakeVault(on, { '/v/Tasks/.active': '' })
    const out = await run($, 'note', 'x')
    expect(out.text).toBe('No active task. /task-start <name>')
  })
})

// The band reads only hasSurvey; the rest is what a surface measures.
const BAND_PROPS = { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 120 } as never

describe('band above the prompt', () => {
  for (const surface of ['terminal', 'desktop'] as const) {
    test(`${surface}: shows the task and its next step; Done checks it off`, async ($, on) => {
      mock.env(on, { VAULT: '/v', HOME: '/home/q' })
      mock.clock(on)
      const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE })
      await run($, 'openloop', 'load the task')
      const band = await $.ui.mount({
        plugin: 'task-track',
        surface,
        component: 'AbovePrompt',
        props: BAND_PROPS,
      })
      expect(await band.find({ type: 'Text', text: /set-up-vault/ })).toBeDefined()
      expect(await band.find({ type: 'Text', text: /Next: Copy hooks/ })).toBeDefined()
      await band.press({ key: 'done' })
      expect(files[PATH]).toContain('- [x] Copy hooks (~10 min)')
    })
  }

  test('shows the timer another session wrote, and this session\'s activity writes to the same file', async ($, on) => {
    const now = T0 + 12 * MIN
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now })
    const other = { ...touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG), lastActiveAt: now - 2 * MIN, blocksDone: 1, lastNotifiedBlock: 1 }
    const files = fakeVault(on, {
      '/v/Tasks/.active': 'set-up-vault\n',
      [PATH]: NOTE,
      '/v/Tasks/.pomo.json': serializePomo(other),
    })
    await run($, 'openloop', 'load the task')
    const band = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
    expect(await band.find({ type: 'Text', text: /●○○○ 12\/25m/ })).toBeDefined()
    await run($, 'note', 'activity')
    const shared = parsePomo(files['/v/Tasks/.pomo.json'] ?? '')
    expect(shared?.blockStartedAt).toBe(T0)
    expect(shared?.lastActiveAt).toBe(now)
  })

  test('draws nothing of its own while no task is active', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    fakeVault(on, { '/v/Tasks/.active': '' })
    on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
      const { Text } = $.ui.resolve(e)
      return h(Text, {}, 'engine band') as never
    })
    await run($, 'note', 'x')
    const band = await $.ui.mount({
      plugin: 'task-track',
      surface: 'terminal',
      component: 'AbovePrompt',
      props: BAND_PROPS,
    })
    expect(await band.find({ type: 'Text', text: 'engine band' })).toBeDefined()
    expect(await band.find({ type: 'Button', key: 'done' })).toBeUndefined()
  })
})

describe('throttling', () => {
  test('activity within a minute of the last write does not write again', async ($, on) => {
    const now = T0 + 12 * MIN
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now })
    const recent = serializePomo({ ...touch(emptyPomo('2026-10-13'), T0, 'set-up-vault', CFG), lastActiveAt: now - 30_000 })
    const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE, '/v/Tasks/.pomo.json': recent })
    await run($, 'openloop', 'load the task')
    await run($, 'note', 'activity')
    expect(files['/v/Tasks/.pomo.json']).toBe(recent)
  })
})

describe('focus reaches the notes', () => {
  const TEMPLATE = '---\ndate: {{date}}\n---\n# {{title}}\n\n## Top 3\n- [ ] \n\n## Brain dump\n\n## Log\n'
  const today = (ms: number) => ({ ...emptyPomo('2026-10-13'), slug: 'set-up-vault', dayMs: { 'set-up-vault': ms }, dayBlocks: { 'set-up-vault': 1 } })
  const end = { reason: 'other', sessionId: 's', resume: {} } as never
  /** The engine's own session.end, beneath the plugin's hook. */
  const coreEnd = (on: On) => on('session.end', ($, e) => ({ sessionId: e.sessionId }))

  test('session end writes unlogged focus to the task Log and a daily note made from the template', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: T0 + 40 * MIN })
    const files = fakeVault(on, {
      '/v/Tasks/.active': 'set-up-vault\n',
      [PATH]: NOTE,
      '/v/Templates/Daily.md': TEMPLATE,
      '/v/Tasks/.pomo.json': serializePomo(today(30 * MIN)),
    })
    coreEnd(on)
    await run($, 'openloop', 'load the task')
    await $.session.end(end)
    expect(files[PATH]).toContain('— focus 30m (1 pomodoro)')
    const daily = files['/v/Daily/2026-10-13.md'] ?? ''
    expect(daily).toContain('# 2026-10-13\n\n## Top 3')
    expect(daily).toContain('## Log\n- 09:40 [[set-up-vault]] focus 30m (1 pomodoro)')
  })

  test('a daily note that exists but cannot be read is left alone', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: T0 + 40 * MIN })
    const DAILY = '/v/Daily/2026-10-13.md'
    on('fs.read', { path: DAILY }, ($, e) => ({ deny: `EACCES: ${e.path}` }))
    const files = fakeVault(on, {
      '/v/Tasks/.active': 'set-up-vault\n',
      [PATH]: NOTE,
      [DAILY]: '# my real day\n\n## Top 3\n- [x] shipped\n\n## Log\n',
      '/v/Tasks/.pomo.json': serializePomo(today(30 * MIN)),
    })
    coreEnd(on)
    await run($, 'openloop', 'load the task')
    await $.session.end(end)
    expect(files[DAILY]).toBe('# my real day\n\n## Top 3\n- [x] shipped\n\n## Log\n')
  })

  test('focus left from a finished day goes to that day\'s notes when the day rolls over', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: T0 })
    const yesterday = { ...today(47 * MIN), day: '2026-10-12' }
    const files = fakeVault(on, {
      '/v/Tasks/.active': 'set-up-vault\n',
      [PATH]: NOTE,
      '/v/Tasks/.pomo.json': serializePomo(yesterday),
    })
    const stored: Record<string, unknown> = {}
    on('store.set', ($, e) => {
      stored[e.key] = e.value
      return { value: undefined }
    })
    await run($, 'openloop', 'load the task')
    await run($, 'note', 'morning')
    expect(files['/v/Daily/2026-10-12.md']).toContain('- end of day [[set-up-vault]] focus 47m (1 pomodoro)')
    expect(files[PATH]).toContain('- [[2026-10-12]] end of day — focus 47m (1 pomodoro)')
    expect(parsePomo(files['/v/Tasks/.pomo.json'] ?? '')?.day).toBe('2026-10-13')
    expect(stored['focus:2026-10-12']).toEqual({ ms: { 'set-up-vault': 47 * MIN }, blocks: { 'set-up-vault': 1 } })
  })

  test('the Log count keeps moving after the 5th line', () => {
    const long = NOTE + Array.from({ length: 6 }, (_, i) => `- [[2026-10-13]] 10:0${i} — l${i}\n`).join('')
    const v = parseNote('set-up-vault', PATH, long, 1)
    expect(v.log).toHaveLength(5)
    expect(v.logCount).toBe(7)
  })
})

describe('pane formatting', () => {
  test('splitEstimate moves a trailing (~N min) estimate out of the title', () => {
    expect(splitEstimate('Copy hooks (~10 min)')).toEqual({ text: 'Copy hooks', est: '~10m' })
    expect(splitEstimate('Rewrite plan (~120 min)')).toEqual({ text: 'Rewrite plan', est: '~2h' })
    expect(splitEstimate('Rewrite plan (~2 h)')).toEqual({ text: 'Rewrite plan', est: '~2h' })
    expect(splitEstimate('Ship it (~1 day of work across PRs)')).toEqual({ text: 'Ship it', est: '~1d' })
    expect(splitEstimate('Pair (~3 hours)')).toEqual({ text: 'Pair', est: '~3h' })
    expect(splitEstimate('Odd (~soon)')).toEqual({ text: 'Odd (~soon)', est: '' })
    expect(splitEstimate('No estimate')).toEqual({ text: 'No estimate', est: '' })
  })

  test('codeSpans splits `code` out without the backticks', () => {
    expect(codeSpans('spec `a.md` in `wt`')).toEqual([
      { text: 'spec ', isCode: false },
      { text: 'a.md', isCode: true },
      { text: ' in ', isCode: false },
      { text: 'wt', isCode: true },
    ])
    expect(codeSpans('plain')).toEqual([{ text: 'plain', isCode: false }])
    expect(codeSpans('cut `off')).toEqual([{ text: 'cut ', isCode: false }, { text: 'off', isCode: true }])
  })

  test('logOrder puts the newest first by date and time, whatever the file order', () => {
    const lines = ['[[2026-10-13]] 11:12 — a', '[[2026-10-13]] 13:45 — c', '[[2026-10-13]] 13:41 — b', '[[2026-10-12]] end of day — z', 'loose']
    expect(logOrder(lines)).toEqual(['[[2026-10-13]] 13:45 — c', '[[2026-10-13]] 13:41 — b', '[[2026-10-13]] 11:12 — a', '[[2026-10-12]] end of day — z', 'loose'])
  })

  test('logEntry shows the time for today, the date otherwise, and drops the [[link]]', () => {
    expect(logEntry('[[2026-10-13]] 13:41 — focus 1h 19m', '2026-10-13')).toEqual({ when: '13:41', text: 'focus 1h 19m' })
    expect(logEntry('[[2026-10-12]] 18:25 — vault scaffold created', '2026-10-13')).toEqual({ when: 'Oct 12', text: 'vault scaffold created' })
    expect(logEntry('[[2026-10-12]] end of day — focus 47m', '2026-10-13')).toEqual({ when: 'Oct 12', text: 'focus 47m' })
    expect(logEntry('free text line', '2026-10-13')).toEqual({ when: '', text: 'free text line' })
  })
})

describe('task pane', () => {
  const BUSY = NOTE.replace('- ~~resolved one~~ yes\n', '- ~~resolved one~~ yes\n- loop three\n- loop four\n')
    + '- [[2026-10-13]] 09:10 — first today\n- [[2026-10-13]] 09:20 — second today\n- [[2026-10-13]] 09:30 — third today\n'

  test('leads with the current step, folds loops and log, and drops [[date]] links', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on, { now: new Date(2026, 9, 13, 9, 40).getTime() })
    fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: BUSY })
    await run($, 'openloop', 'load the task')
    const pane = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'Pane', requestId: 'task-track', props: {} as never })
    expect(await pane.find({ type: 'Text', text: 'Copy hooks' })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: /~10m/ })).toBeDefined()
    expect(await pane.find({ type: 'Button', key: 'loops' })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: 'loop four' })).toBeUndefined()
    expect(await pane.find({ type: 'Text', text: 'third today' })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: /\[\[2026/ })).toBeUndefined()
    expect(await pane.find({ type: 'Text', text: 'vault scaffold created' })).toBeUndefined()

    await pane.press({ key: 'loops' })
    await pane.press({ key: 'log' })
    expect(await pane.find({ type: 'Text', text: 'loop four' })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: 'vault scaffold created' })).toBeDefined()
  })

  test('a narrow pane cuts Next rows to its width and drops backticks from code', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    const LONG = NOTE.replace('- [ ]\n', '- [ ] Rewrite plan tasks 1-6 for rev 2 with a very long tail of detail (~2 h)\n- [ ] read `docs/spec.md` first\n')
    fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: LONG })
    await run($, 'openloop', 'load the task')
    const pane = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'Pane', requestId: 'task-track', props: {} as never, viewport: { columns: 40, rows: 40 } })
    // The terminal cuts the row to the pane's width; the tree holds the whole title.
    expect(await pane.find({ type: 'Text', text: /^Rewrite plan tasks 1-6/ })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: 'docs/spec.md' })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: /`/ })).toBeUndefined()
  })

  test('pressing the current step checks it off', async ($, on) => {
    mock.env(on, { VAULT: '/v', HOME: '/home/q' })
    mock.clock(on)
    const files = fakeVault(on, { '/v/Tasks/.active': 'set-up-vault\n', [PATH]: NOTE })
    await run($, 'openloop', 'load the task')
    const pane = await $.ui.mount({ plugin: 'task-track', surface: 'terminal', component: 'Pane', requestId: 'task-track', props: {} as never })
    await pane.press({ key: 'next-1' })
    expect(files[PATH]).toContain('- [x] Copy hooks (~10 min)')
  })
})
