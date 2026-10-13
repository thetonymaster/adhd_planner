import { atom, read, update } from 'claude-code'
import type { EngineInterface, PluginOptions, Register } from 'claude-code'

import type { PomoFile, TaskView } from '../types'
import { codeSpans, elapsed, firstOpen, insertInSection, logEntry, logOrder, parseNote, progress, splitEstimate, stamp, toggleNext, truncate } from './note'
import {
  advance,
  emptyPomo,
  markLogged,
  parsePomo,
  pomoDots,
  rollDay,
  serializePomo,
  shouldTouch,
  touch,
  unlogged,
} from './pomo'
import type { DayTotals, PomoConfig, PomoEvent } from './pomo'
import { frontmatter, normalize, pickTask } from './resolve'
import type { Candidate } from './resolve'

const task = atom({ plugin: 'task-track', key: 'task' } as const, null)
const problem = atom({ plugin: 'task-track', key: 'problem' } as const, '')
const pomo = atom({ plugin: 'task-track', key: 'pomo' } as const, emptyPomo(''))
const isBandHidden = atom({ plugin: 'task-track', key: 'isBandHidden' } as const, false)
const isLoopsOpen = atom({ plugin: 'task-track', key: 'isLoopsOpen' } as const, false)
const isLogOpen = atom({ plugin: 'task-track', key: 'isLogOpen' } as const, false)
const source = atom({ plugin: 'task-track', key: 'source' } as const, 'global')

const PANE = 'task-track'
const POLL_MS = 15_000
const TICK_MS = 60_000
/** Less focus than this waits for the next flush instead of writing a line of its own. */
const MIN_LOGGED_MS = 5 * 60_000
/** This session, for telling which one announced a break. New on every load. */
const SESSION = Math.random().toString(36).slice(2, 10)

type Settings = PomoConfig & { vaultPath: string; staleEdits: number; notesToClaude: boolean }

// Module-local: set by register, reset on reload (state that must survive lives in atoms).
let settings: Settings = {
  vaultPath: '',
  focusMinutes: 25,
  breakMinutes: 5,
  longBreakEvery: 4,
  longBreakMinutes: 30,
  staleEdits: 10,
  notesToClaude: true,
}
let vault = ''
let editsSinceLog = 0
let logSize = -1
let isStaleNudged = false
/** Frontmatter of each task note by slug, re-read only when the note's mtime moves. */
const noteCache = new Map<string, Candidate>()

function readSettings(options: PluginOptions): Settings {
  return {
    vaultPath: String(options.vaultPath ?? '').trim(),
    focusMinutes: Number(options.focusMinutes ?? 25),
    breakMinutes: Number(options.breakMinutes ?? 5),
    longBreakEvery: Number(options.longBreakEvery ?? 4),
    longBreakMinutes: Number(options.longBreakMinutes ?? 30),
    staleEdits: Number(options.staleEdits ?? 10),
    notesToClaude: options.notesToClaude !== false,
  }
}

async function resolveVault($: EngineInterface): Promise<string> {
  if (vault) return vault
  const fromEnv = await $.env.get('VAULT')
  const home = (await $.env.get('HOME')) ?? ''
  vault = (settings.vaultPath || fromEnv || `${home}/vault`).replace(/^~(?=\/)/, home).replace(/\/$/, '')
  return vault
}

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
      const path = `${dir}/${entry.name}`
      // Deleted between the listing and the read: not a candidate. Any other read error propagates.
      const text = await $.fs.read(path).catch(async (err: unknown) => {
        if (await $.fs.exists(path)) throw err
        return undefined
      })
      if (text === undefined) continue
      const fm = frontmatter(text)
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

/** Resolves the session's task and re-reads its note when it changed; returns the current view. */
async function load($: EngineInterface): Promise<TaskView | null> {
  const root = await resolveVault($)
  const home = (await $.env.get('HOME')) ?? ''
  const sessionId = await $.session.id()
  const [found, override, dir, global] = await Promise.all([
    candidates($, root),
    readIfExists($, `${root}/Tasks/.session/${sessionId}`),
    $.session.root(),
    readIfExists($, `${root}/Tasks/.active`),
  ])
  const picked = pickTask({ override, dir, home, candidates: found, global })
  const slug = picked?.slug ?? ''
  const repo = found.find(c => c.slug === slug)?.repo ?? ''
  const label = picked?.source === 'session' ? 'this session' : picked?.source === 'repo' ? `project: ${normalize(repo, home).split('/').pop()}` : 'global'
  await update($, source, () => label)
  const prev = await read($, task)
  await refreshPomo($)
  if (!slug) {
    if (prev) await flushFocus($, prev.slug, prev.path)
    const hasVault = await $.fs.exists(root)
    await update($, task, () => null)
    await update($, problem, () => (hasVault ? '' : `No vault at ${root}`))
    $.ui.status(undefined)
    return null
  }
  const path = `${root}/Tasks/${slug}.md`
  const stat = await $.fs.stat(path).catch(() => undefined)
  if (!stat) {
    await update($, problem, () => `Active task "${slug}" has no note at ${path}`)
    return prev
  }
  if (prev && prev.path === path && prev.mtimeMs === stat.mtimeMs) return prev
  const view = parseNote(slug, path, await $.fs.read(path), stat.mtimeMs)
  if (prev && prev.slug !== slug) await flushFocus($, prev.slug, prev.path)
  if (view.logCount !== logSize || prev?.slug !== slug) {
    logSize = view.logCount
    editsSinceLog = 0
    isStaleNudged = false
  }
  await update($, task, () => view)
  await update($, problem, () => '')
  await showStatus($)
  return view
}

async function showStatus($: EngineInterface): Promise<void> {
  const view = await read($, task)
  if (!view) {
    $.ui.status(undefined)
    return
  }
  const { done, total } = progress(view.next)
  const p = await read($, pomo)
  const timer = pomoDots(p, await $.clock.now(), settings)
  $.ui.status(`▶ ${view.slug} ${done}/${total} · ${timer}`)
}

/** Read fresh, change, write back: the note is the source of truth. */
async function edit($: EngineInterface, change: (text: string) => string): Promise<TaskView | null> {
  const view = await load($)
  if (!view) return null
  const before = await $.fs.read(view.path)
  const after = change(before)
  if (after === before) return view
  await $.fs.write(view.path, after)
  const stat = await $.fs.stat(view.path)
  const fresh = parseNote(view.slug, view.path, after, stat.mtimeMs)
  logSize = fresh.logCount
  editsSinceLog = 0
  isStaleNudged = false
  await update($, task, () => fresh)
  await showStatus($)
  return fresh
}

async function addLog($: EngineInterface, text: string): Promise<TaskView | null> {
  const { date, time } = stamp(new Date(await $.clock.now()))
  return edit($, t => insertInSection(t, 'Log', `- [[${date}]] ${time} — ${text}`))
}

async function toggle($: EngineInterface, index: number): Promise<TaskView | null> {
  return edit($, t => toggleNext(t, index))
}

async function addLoop($: EngineInterface, text: string): Promise<TaskView | null> {
  return edit($, t => insertInSection(t, 'Open loops', `- ${text}`))
}

// ── the shared Pomodoro file ──────────────────────────────────────────────

async function pomoPath($: EngineInterface): Promise<string> {
  return `${await resolveVault($)}/Tasks/.pomo.json`
}

async function today($: EngineInterface): Promise<string> {
  return stamp(new Date(await $.clock.now())).date
}

/** The shared file; a fresh one when missing; null when unreadable this round (half-written). */
async function readPomo($: EngineInterface): Promise<PomoFile | null> {
  const text = await $.fs.read(await pomoPath($)).catch(() => undefined)
  if (text === undefined) return emptyPomo(await today($))
  return parsePomo(text)
}

/** Writes beside the file, then renames over it, so no session reads half a file. */
async function writePomo($: EngineInterface, f: PomoFile): Promise<void> {
  const path = await pomoPath($)
  const tmp = `${path}.${SESSION}.tmp`
  const text = serializePomo(f)
  await $.fs.write(tmp, text)
  const isMoved = await $.process
    .run(['mv', '-f', tmp, path])
    .then(r => r.exitCode === 0)
    .catch(() => false)
  if (!isMoved) await $.fs.write(path, text)
  await update($, pomo, () => f)
}

async function refreshPomo($: EngineInterface): Promise<void> {
  const f = await readPomo($)
  if (f) await update($, pomo, () => f)
}

async function saveDay($: EngineInterface, d: DayTotals): Promise<void> {
  await $.store.set(`focus:${d.day}`, { ms: d.dayMs, blocks: d.dayBlocks })
}

function focusText(pending: { ms: number; blocks: number }): string {
  if (pending.blocks <= 0) return `focus ${elapsed(pending.ms)}`
  const blocks = pending.blocks === 1 ? '1 pomodoro' : `${pending.blocks} pomodoros`
  return `focus ${elapsed(pending.ms)} (${blocks})`
}

/**
 * The daily note's text: the file when it exists, else Templates/Daily.md filled in, else
 * a minimal note. A note that exists but can't be read throws: writing a stub over it
 * would wipe the day.
 */
async function dailyText($: EngineInterface, path: string, date: string): Promise<string> {
  if (await $.fs.exists(path)) return $.fs.read(path)
  const template = `${await resolveVault($)}/Templates/Daily.md`
  if (await $.fs.exists(template)) {
    return (await $.fs.read(template)).replaceAll('{{date}}', date).replaceAll('{{title}}', date)
  }
  return `---\ndate: ${date}\ntags: [daily]\n---\n# ${date}\n\n## Log\n`
}

/** Appends one focus line to the task's Log (when its note exists) and to that day's daily note. */
async function writeFocus($: EngineInterface, slug: string, taskPath: string, date: string, time: string, spent: string): Promise<void> {
  if (await $.fs.exists(taskPath)) {
    const taskText = await $.fs.read(taskPath)
    await $.fs.write(taskPath, insertInSection(taskText, 'Log', `- [[${date}]] ${time} — ${spent}`))
  }
  const daily = `${await resolveVault($)}/Daily/${date}.md`
  await $.fs.write(daily, insertInSection(await dailyText($, daily, date), 'Log', `- ${time} [[${slug}]] ${spent}`))
}

/** A finished day's focus that no session wrote (it ran past midnight, or crashed): written to that day's notes. */
async function flushDay($: EngineInterface, d: DayTotals): Promise<void> {
  const root = await resolveVault($)
  for (const slug of Object.keys(d.dayMs)) {
    const logged = d.logged[slug] ?? { ms: 0, blocks: 0 }
    const pending = { ms: (d.dayMs[slug] ?? 0) - logged.ms, blocks: (d.dayBlocks[slug] ?? 0) - logged.blocks }
    if (pending.ms < MIN_LOGGED_MS) continue
    await writeFocus($, slug, `${root}/Tasks/${slug}.md`, d.day, 'end of day', focusText(pending))
  }
}

/**
 * Read fresh, roll the day, change, write back. Skips the round when the file is unreadable.
 * A finished day's unwritten focus goes to the notes before the rolled file replaces it:
 * a failed write then repeats on the next round instead of losing the time.
 */
async function changePomo($: EngineInterface, change: (f: PomoFile) => PomoFile): Promise<PomoFile | null> {
  const current = await readPomo($)
  if (!current) return null
  const { file, finished } = rollDay(current, await today($))
  if (finished) {
    await flushDay($, finished)
    await saveDay($, finished)
  }
  const next = change(file)
  if (next === current) {
    await update($, pomo, () => current)
    return current
  }
  await writePomo($, next)
  return next
}

/** Activity in this session: written to the shared file at most once a minute. */
async function markActive($: EngineInterface): Promise<void> {
  const view = await read($, task)
  if (!view) return
  const now = await $.clock.now()
  if (!shouldTouch(await read($, pomo), now, view.slug)) return
  await changePomo($, f => touch(f, now, view.slug, settings))
}

/** Writes today's not-yet-logged focus on `slug` to its task Log and the daily note, once across sessions. */
async function flushFocus($: EngineInterface, slug: string, path: string): Promise<void> {
  let pending = { ms: 0, blocks: 0 }
  const f = await changePomo($, file => {
    pending = unlogged(file, slug)
    return pending.ms >= MIN_LOGGED_MS ? markLogged(file, slug) : file
  })
  if (!f || pending.ms < MIN_LOGGED_MS) return
  const { date, time } = stamp(new Date(await $.clock.now()))
  await writeFocus($, slug, path, date, time, focusText(pending))
}

/** Every minute: move the shared clock; the session that announces a block is the one whose write stuck. */
async function tick($: EngineInterface): Promise<void> {
  const view = await read($, task)
  if (!view) return
  const now = await $.clock.now()
  const out: { event: PomoEvent } = { event: { kind: 'none' } }
  // One timer for the person: advance it whichever task holds it, or a block left by a closed
  // session would climb past focusMinutes and never announce its break.
  const f = await changePomo($, file => {
    const r = advance(file, now, settings)
    out.event = r.event
    return r.event.kind === 'break' ? { ...r.file, notifiedBy: SESSION } : r.file
  })
  await showStatus($)
  const event = out.event
  if (!f || event.kind !== 'break') return
  const check = await readPomo($)
  if (!check || check.notifiedBy !== SESSION || check.lastNotifiedBlock !== event.blocks) return
  const text = event.isLong
    ? `${event.blocks} pomodoros on ${event.slug}. Long break: ${event.minutes} min.`
    : `Pomodoro ${event.blocks} done on ${event.slug}. Break: ${event.minutes} min.`
  $.ui.toast(text)
  void $.ui.notify(text, { title: 'task-track' })
}

async function openPane($: EngineInterface): Promise<void> {
  const view = await read($, task)
  await $.ui.open({ id: PANE, title: view ? `Task · ${view.slug}` : 'Task', focus: true })
}

async function noteFromPane($: EngineInterface, slug: string, value: string): Promise<void> {
  const text = value.trim()
  if (!text) return
  await markActive($)
  await addLog($, text)
  if (!settings.notesToClaude) return
  await $.session
    .append({ message: { type: 'user', content: [{ type: 'text', text: `Q added a note to the active task (${slug}): ${text}` }] } })
    .catch(() => undefined)
}

async function pressToggle($: EngineInterface, index: number): Promise<void> {
  await markActive($)
  await toggle($, index)
}

async function pressDoneFirst($: EngineInterface): Promise<void> {
  const view = await read($, task)
  if (!view) return
  await markActive($)
  await toggle($, firstOpen(view.next))
}

async function hideBand($: EngineInterface): Promise<void> {
  await update($, isBandHidden, () => true)
}

async function park($: EngineInterface): Promise<void> {
  await $.prompt.submit({ text: '/task-park' })
}

async function openInObsidian($: EngineInterface, path: string): Promise<void> {
  await $.process.run(['open', `obsidian://open?path=${encodeURIComponent(path)}`])
}

const COMMANDS = [
  { name: 'task', description: 'Show the active task pane (/task hide|show toggles the band)', argumentHint: '[hide|show]' },
  { name: 'note', description: 'Add a line to the active task Log (no model turn)', argumentHint: '<text>', immediate: true },
  { name: 'done', description: 'Check off a Next item (default: the first open one)', argumentHint: '[n]', immediate: true },
  { name: 'openloop', description: 'Add an Open loop to the active task', argumentHint: '<text>', immediate: true },
] as const

/** Registers each command on its own: one refused name (a built-in, another plugin's) never stops the rest or the start hook. */
async function registerCommands($: EngineInterface): Promise<void> {
  const refused: string[] = []
  for (const command of COMMANDS) {
    await $.command.register(command).catch(() => {
      refused.push(`/${command.name}`)
    })
  }
  if (refused.length > 0) $.ui.log(`task-track: ${refused.join(', ')} not registered (name taken).`)
}

function told(text: string): { context?: string[] } {
  return settings.notesToClaude ? { context: [text] } : {}
}

export const register: Register = (on, options) => {
  settings = readSettings(options)
  vault = ''

  // ── lifecycle ────────────────────────────────────────────────────────────

  on('session.start', async ($, e, next) => {
    await registerCommands($)
    await load($)
    $.clock.every(POLL_MS, () => load($))
    $.clock.every(TICK_MS, () => tick($))
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    const view = await read($, task)
    if (view) {
      await flushFocus($, view.slug, view.path).catch((err: unknown) => {
        $.ui.log(`task-track: focus for ${view.slug} not written at session end: ${String(err)}`)
      })
    }
    return next(e)
  })

  // ── activity + staleness ────────────────────────────────────────────────

  on('prompt.submit', async ($, e, next) => {
    await markActive($)
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    await markActive($)
    const isEdit = e.tool === 'Edit' || e.tool === 'Write' || e.tool === 'NotebookEdit'
    const path = 'file_path' in e && typeof e.file_path === 'string' ? e.file_path : undefined
    if (!isEdit || !path) return ran
    const view = await read($, task)
    if (view && path === view.path) {
      await load($)
      return ran
    }
    editsSinceLog += 1
    if (view && settings.staleEdits > 0 && editsSinceLog >= settings.staleEdits && !isStaleNudged) {
      isStaleNudged = true
      $.ui.toast(`${editsSinceLog} edits since ${view.slug}'s Log changed. /note what moved?`)
    }
    return ran
  }).catch(($, e, next) => next(e))

  // ── commands ────────────────────────────────────────────────────────────

  on('command.run', { command: 'task' }, async ($, e) => {
    await markActive($)
    const arg = e.args.trim()
    if (arg === 'hide' || arg === 'show') {
      await update($, isBandHidden, () => arg === 'hide')
      return { text: `Task band ${arg === 'hide' ? 'hidden' : 'shown'}.` }
    }
    const view = await load($)
    await openPane($)
    return { text: view ? `Task pane: ${view.slug}` : (await read($, problem)) || 'No active task. /task-start <name>' }
  })

  on('command.run', { command: 'note' }, async ($, e) => {
    await markActive($)
    const text = e.args.trim()
    if (!text) return { text: 'Usage: /note <text>' }
    const view = await addLog($, text)
    if (!view) return { text: 'No active task. /task-start <name>' }
    return { text: `Logged to ${view.slug}.`, ...told(`Q added a note to the active task (${view.slug}): ${text}`) }
  })

  on('command.run', { command: 'done' }, async ($, e) => {
    await markActive($)
    const view = await load($)
    if (!view) return { text: 'No active task. /task-start <name>' }
    const arg = e.args.trim()
    const index = arg ? Number(arg) - 1 : firstOpen(view.next)
    const item = view.next[index]
    if (!item) {
      return { text: arg ? `No Next item ${arg} (1–${view.next.length}).` : 'All Next items are done. Add the next step, or /task-park.' }
    }
    const after = await toggle($, index)
    const left = after ? after.next.filter(n => !n.isDone).length : 0
    const verb = item.isDone ? 'Reopened' : 'Done'
    return {
      text: `${verb}: ${item.text} · ${left} left`,
      ...told(`Q marked a Next item ${item.isDone ? 'not done' : 'done'} on ${view.slug}: ${item.text}`),
    }
  })

  on('command.run', { command: 'openloop' }, async ($, e) => {
    await markActive($)
    const text = e.args.trim()
    if (!text) return { text: 'Usage: /openloop <text>' }
    const view = await addLoop($, text)
    if (!view) return { text: 'No active task. /task-start <name>' }
    return { text: `Open loop added to ${view.slug}.`, ...told(`Q added an open loop to ${view.slug}: ${text}`) }
  })

  // ── band above the prompt: only while a task is active ──────────────────

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const view = await read($, task)
    if (!view || e.props.hasSurvey || (await read($, isBandHidden))) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const p = await read($, pomo)
    const timer = pomoDots(p, await $.clock.now(), settings)
    const { done, total } = progress(view.next)
    const open = view.next[firstOpen(view.next)]
    const step = open ? splitEstimate(open.text) : undefined
    // One row: the slug, counts and buttons keep their width; only the Next text gives way,
    // cut by the terminal so nothing wraps under the prompt. The band spans the surface, and
    // without a width the row grows past the edge instead of cutting the text. The engine draws
    // its own `[-]` control at the right end of the band, so the row leaves it 5 columns (its 3 and a gap each side).
    const columns = e.viewport?.columns === undefined ? undefined : Math.max(20, e.viewport.columns - 5)
    return (
      <Box gap={1} width={columns} marginTop={1}>
        <Box flexShrink={0}>
          <Text bold color="claude">▶ {view.slug}</Text>
        </Box>
        <Box flexShrink={1} flexGrow={1}>
          <Text wrap="truncate-end">
            {step ? `Next: ${step.text.replaceAll('`', '')}` : 'All Next done'}
            {step?.est ? <Text color="subtle">  {step.est}</Text> : null}
          </Text>
        </Box>
        <Box flexShrink={0}>
          <Text color="subtle">
            {done}/{total} · {timer}
          </Text>
        </Box>
        <Box flexShrink={0} gap={1}>
          {open && <Button key="done" label="Done" onPress={() => pressDoneFirst($)} />}
          <Button key="pane" label="Task" onPress={() => openPane($)} />
          <Button key="hide" label="Hide" onPress={() => hideBand($)} />
        </Box>
      </Box>
    )
  })

  // ── pane ────────────────────────────────────────────────────────────────

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const elements = $.ui.resolve(e)
    const { Box, Button, Text } = elements
    const Input = 'Input' in elements ? elements.Input : undefined
    const view = await read($, task)
    if (!view) {
      const why = await read($, problem)
      return (
        <Box flexDirection="column">
          <Text>{why || 'No active task.'}</Text>
          <Text dimColor>Start one with /task-start &lt;name&gt;</Text>
        </Box>
      )
    }
    const p = await read($, pomo)
    const now = await $.clock.now()
    const timer = pomoDots(p, now, settings)
    const why = await read($, source)
    const { done, total } = progress(view.next)
    const nowIndex = firstOpen(view.next)
    const open = view.next.flatMap((item, i) => (!item.isDone && i !== nowIndex ? [{ item, i }] : []))
    const loopsOpen = await read($, isLoopsOpen)
    const logOpen = await read($, isLogOpen)
    const loops = loopsOpen ? view.openLoops : view.openLoops.slice(0, 2)
    const today = stamp(new Date(now)).date
    const log = logOrder(view.log).slice(0, logOpen ? view.log.length : 3)
    const label = (text: string, count?: string) => (
      <Box marginTop={1}>
        <Text bold color="claude">{text}</Text>
        {count ? <Text color="subtle">  {count}</Text> : null}
      </Box>
    )
    /** Text with `code` runs drawn dim and without backticks. */
    const spans = (text: string, base: { color?: string; bold?: boolean; dimColor?: boolean; strikethrough?: boolean }) =>
      codeSpans(text).map((run, k) => (
        <Text key={`run-${k}`} {...base} color={run.isCode ? 'subtle' : base.color} bold={run.isCode ? false : base.bold}>{run.text}</Text>
      ))
    /**
     * One Next item: the marker is the button (a Button draws its text whole), the title a
     * Text the terminal cuts to the pane's width. NOW wraps; it is the line to act on.
     */
    const row = (i: number, text: string, est: string, isNow: boolean) => (
      <Box key={`row-${i}`}>
        <Box flexShrink={0}>
          <Button key={`next-${i}`} plain label={isNow ? '▶' : '○'} onPress={() => pressToggle($, i)} />
          <Text> </Text>
        </Box>
        <Box flexShrink={1}>
          <Text color={isNow ? 'suggestion' : undefined} bold={isNow} wrap={isNow ? 'wrap' : 'truncate-end'}>
            {spans(text, { color: isNow ? 'suggestion' : undefined, bold: isNow })}
          </Text>
        </Box>
        {est ? (
          <Box flexShrink={0}>
            <Text color="subtle">  {est}</Text>
          </Box>
        ) : null}
      </Box>
    )
    const nextRow = ({ item, i }: { item: { text: string; isDone: boolean }; i: number }, isNow = false) => {
      const { text, est } = splitEstimate(item.text)
      return row(i, text, est, isNow)
    }
    const nowItem = nowIndex === -1 ? undefined : view.next[nowIndex]
    return (
      <Box flexDirection="column">
        <Box flexDirection="column" borderStyle="round" borderColor="claude" paddingX={1}>
          <Text bold wrap="truncate-end">{view.title}</Text>
          {view.goal ? <Text color="subtle" wrap="truncate-end">{view.goal}</Text> : null}
          <Text>
            {timer} <Text color="subtle">· today {elapsed(p.dayMs[view.slug] ?? 0)} · Next {done}/{total}</Text>
            {view.up ? <Text color="subtle"> · {view.up}</Text> : null}
            <Text color="subtle"> · {why}</Text>
          </Text>
        </Box>
        {label('NOW')}
        {nowItem ? nextRow({ item: nowItem, i: nowIndex }, true) : <Text color="subtle">  Nothing open. Add a step to ## Next.</Text>}
        {open.length + done > 0 ? label('NEXT') : null}
        {open.map(o => nextRow(o))}
        {done > 0 ? <Text color="subtle">✓ {done} done</Text> : null}
        {view.openLoops.length > 0 ? label('OPEN LOOPS', String(view.openLoops.length)) : null}
        {loops.map((l, i) => (
          <Box key={`loop-${i}`} marginBottom={loopsOpen ? 1 : 0}>
            <Box flexShrink={0}>
              <Text color="warning">? </Text>
            </Box>
            <Box flexShrink={1}>
              <Text wrap={loopsOpen ? 'wrap' : 'truncate-end'}>{spans(l, {})}</Text>
            </Box>
          </Box>
        ))}
        {view.openLoops.length > 2 ? (
          <Button key="loops" plain dimColor hotkey="o" label={loopsOpen ? 'less' : `+${view.openLoops.length - 2} more`} onPress={() => update($, isLoopsOpen, v => !v)} />
        ) : null}
        {log.length > 0 ? label('LOG') : null}
        {log.map((line, i) => {
          const entry = logEntry(line, today)
          return (
            <Box key={`log-${i}`} marginBottom={logOpen ? 1 : 0}>
              <Box flexShrink={0} width={8}>
                <Text color="subtle">{entry.when}</Text>
              </Box>
              <Box flexShrink={1}>
                <Text wrap={logOpen ? 'wrap' : 'truncate-end'}>{spans(entry.text, {})}</Text>
              </Box>
            </Box>
          )
        })}
        {view.log.length > 3 ? (
          <Button key="log" plain dimColor hotkey="l" label={logOpen ? 'less' : 'more'} onPress={() => update($, isLogOpen, v => !v)} />
        ) : null}
        <Box marginTop={1} />
        {Input ? (
          <Input
            key="note"
            label="Note"
            placeholder="what changed, what you learned"
            submitLabel="log"
            autoFocus
            onSubmit={(value: string) => noteFromPane($, view.slug, value)}
          />
        ) : (
          <Text dimColor>/note &lt;text&gt; to log</Text>
        )}
        <Box gap={1}>
          <Button key="park" label="Park (/task-park)" onPress={() => park($)} />
          <Button key="obsidian" label="Open in Obsidian" onPress={() => openInObsidian($, view.path)} />
        </Box>
      </Box>
    )
  })
}
