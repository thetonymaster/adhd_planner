import { atom, read, update } from 'claude-code'
import type { EngineInterface, PluginOptions, Register } from 'claude-code'

import type { PomoFile, TaskView } from '../types'
import { codeSpans, elapsed, firstOpen, insertInSection, logEntry, logOrder, parseNote, progress, splitEstimate, stamp, toggleNext, truncate } from './note'
import {
  advance,
  isRunning,
  onBreak,
  emptyPomo,
  markLogged,
  parsePomo,
  pause,
  pomoDots,
  pomoState,
  recordActivity,
  resume,
  rollDay,
  serializePomo,
  shouldTouch,
  snapshotTask,
  start,
  stop,
  toggle as togglePomo,
  touch,
  unlogged,
} from './pomo'
import type { DayTotals, PomoConfig, PomoEvent, Transition } from './pomo'
import { defaultVault, frontmatter, implicitVault, normalize, parseVaults, pickVault } from './resolve'
import { blockSummary, checkedTitles, SUMMARY_SYSTEM, summaryPrompt } from './summary'
import type { NoteRead } from './summary'
import type { Candidate, VaultConfig, VaultSpec, VaultState } from './resolve'

const task = atom({ plugin: 'task-track', key: 'task' } as const, null)
const problem = atom({ plugin: 'task-track', key: 'problem' } as const, '')
const pomo = atom({ plugin: 'task-track', key: 'pomo' } as const, emptyPomo(''))
const isBandHidden = atom({ plugin: 'task-track', key: 'isBandHidden' } as const, false)
const isLoopsOpen = atom({ plugin: 'task-track', key: 'isLoopsOpen' } as const, false)
const isLogOpen = atom({ plugin: 'task-track', key: 'isLogOpen' } as const, false)
const source = atom({ plugin: 'task-track', key: 'source' } as const, 'global')
const vaultName = atom({ plugin: 'task-track', key: 'vaultName' } as const, '')
const configError = atom({ plugin: 'task-track', key: 'configError' } as const, '')
const toldBreakUntil = atom({ plugin: 'task-track', key: 'toldBreakUntil' } as const, 0)
const toldMvFailed = atom({ plugin: 'task-track', key: 'toldMvFailed' } as const, false)

const PANE = 'task-track'
const POLL_MS = 15_000
const TICK_MS = 60_000
/** Less focus than this waits for the next flush instead of writing a line of its own. */
const MIN_LOGGED_MS = 5 * 60_000
/** This session, for telling which one announced a break. New on every load. */
const SESSION = Math.random().toString(36).slice(2, 10)

type Settings = PomoConfig & { vaultPath: string; staleEdits: number; notesToClaude: boolean; breakSummaryAI: boolean }

// Module-local: set by register, reset on reload (state that must survive lives in atoms).
let settings: Settings = {
  vaultPath: '',
  focusMinutes: 25,
  breakMinutes: 5,
  longBreakEvery: 4,
  longBreakMinutes: 30,
  staleEdits: 10,
  notesToClaude: true,
  breakSummaryAI: false,
}
/** The vault this session resolved to on its last load; '' until the first load. */
let vault = ''
let editsSinceLog = 0
let logSize = -1
let isStaleNudged = false
/** Frontmatter of each task note by note path, re-read only when the note's mtime moves. */
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
    breakSummaryAI: options.breakSummaryAI === true,
  }
}

/** vaults.json, read on every load so an edit applies without a restart; the implicit vault without one. */
async function vaultConfig($: EngineInterface, home: string): Promise<VaultConfig> {
  const fallback = settings.vaultPath || (await $.env.get('VAULT')) || `${home}/vault`
  // `~` expanded here: settings.json `env` does not expand it. Same rule as vaults.py config_path.
  const raw = (await $.env.get('ADHD_PLANNER_VAULTS')) ?? ''
  const path = raw ? normalize(raw, home) : `${home}/.config/adhd-planner/vaults.json`
  if (!path.startsWith('/')) return implicitVault(fallback, home, `$ADHD_PLANNER_VAULTS must be an absolute path or start with ~/, got '${raw}'`)
  if (!(await $.fs.exists(path))) return implicitVault(fallback, home)
  const text = await $.fs.read(path).catch((err: unknown) => new Error(err instanceof Error ? err.message : String(err)))
  return text instanceof Error ? implicitVault(fallback, home, `${path}: ${text.message}`) : parseVaults(text, path, fallback, home)
}

/** The vault this session resolved to on its last load; loads once if nothing has yet. */
async function currentVault($: EngineInterface): Promise<string> {
  if (!vault) await load($)
  return vault
}

/** One vault's notes and pointer files; null when it has no Tasks/ (not mounted, not a vault). */
async function vaultState($: EngineInterface, v: VaultSpec, sessionId: string): Promise<VaultState | null> {
  if (!(await $.fs.exists(`${v.path}/Tasks`))) return null
  const sessionFile = `${v.path}/Tasks/.session/${sessionId}`
  const [found, override, global] = await Promise.all([
    candidates($, v.path),
    readIfExists($, sessionFile),
    readIfExists($, `${v.path}/Tasks/.active`),
  ])
  const overrideMtimeMs = override ? (await $.fs.stat(sessionFile)).mtimeMs : 0
  return { vault: v, candidates: found, override, overrideMtimeMs, global }
}

/** Every task note's slug, repo, status and mtime; [] when there is no Tasks/ folder. */
async function candidates($: EngineInterface, root: string): Promise<Candidate[]> {
  const dir = `${root}/Tasks`
  if (!(await $.fs.exists(dir))) return []
  const out: Candidate[] = []
  for (const entry of await $.fs.list(dir)) {
    if (entry.kind !== 'file' || !entry.name.endsWith('.md')) continue
    const slug = entry.name.slice(0, -3)
    const path = `${dir}/${entry.name}`
    let c = noteCache.get(path)
    if (!c || c.mtimeMs !== entry.mtimeMs) {
      // Deleted between the listing and the read: not a candidate. Any other read error propagates.
      const text = await $.fs.read(path).catch(async (err: unknown) => {
        if (await $.fs.exists(path)) throw err
        return undefined
      })
      if (text === undefined) continue
      const fm = frontmatter(text)
      c = { slug, repo: fm.repo, status: fm.status, mtimeMs: entry.mtimeMs }
      noteCache.set(path, c)
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
  const home = (await $.env.get('HOME')) ?? ''
  const config = await vaultConfig($, home)
  const [sessionId, dir] = await Promise.all([$.session.id(), $.session.root()])
  // A vault that can't be read is left out and named, so it can't stop the others from loading.
  const loaded = await Promise.all(
    config.vaults.map(v =>
      vaultState($, v, sessionId).catch((err: unknown) => new Error(`vault ${v.name} (${v.path}) skipped: ${err instanceof Error ? err.message : String(err)}`)),
    ),
  )
  const states = loaded.filter((s): s is VaultState => s !== null && !(s instanceof Error))
  const unreadable = loaded.flatMap(s => (s instanceof Error ? [s.message] : []))
  const picked = pickVault({ config, states, dir, home })
  const root = picked?.vault.path ?? defaultVault(config).path
  const prev = await read($, task)
  // Credit the old task on the old vault's timer before this session moves to the new vault's.
  const isVaultChange = vault !== '' && root !== vault
  if (prev && isVaultChange) await flushFocus($, prev.slug, prev.path)
  vault = root
  await update($, source, () => picked?.reason ?? 'global')
  await update($, vaultName, () => (config.vaults.length > 1 && picked ? picked.vault.name : ''))
  await update($, configError, () => [config.error, ...unreadable].filter(Boolean).join('; '))
  await refreshPomo($)
  const slug = picked?.slug ?? ''
  if (!slug) {
    if (prev && !isVaultChange) await flushFocus($, prev.slug, prev.path)
    const hasVault = await $.fs.exists(root)
    await update($, task, () => null)
    await update($, problem, () => (hasVault ? '' : `No vault at ${root}`))
    return null
  }
  const path = `${root}/Tasks/${slug}.md`
  const stat = await $.fs.stat(path).catch(() => undefined)
  if (!stat) {
    await update($, problem, () => `Active task "${slug}" has no note at ${path}`)
    if (!isVaultChange) return prev
    // prev is the old vault's note: keeping it would edit that note on this vault's timer.
    await update($, task, () => null)
    return null
  }
  if (prev && prev.path === path && prev.mtimeMs === stat.mtimeMs) return prev
  const view = parseNote(slug, path, await $.fs.read(path), stat.mtimeMs)
  if (prev && prev.path !== path && !isVaultChange) await flushFocus($, prev.slug, prev.path)
  if (view.logCount !== logSize || prev?.path !== path) {
    logSize = view.logCount
    editsSinceLog = 0
    isStaleNudged = false
  }
  await update($, task, () => view)
  await update($, problem, () => '')
  return view
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
  return `${await currentVault($)}/Tasks/.pomo.json`
}

async function today($: EngineInterface): Promise<string> {
  return stamp(new Date(await $.clock.now())).date
}

/**
 * The shared file; a fresh one only when it does not exist. Null when it exists but can't be read
 * or parsed this round (half-written, permissions, sync): never replace a file we couldn't read.
 */
async function readPomo($: EngineInterface): Promise<PomoFile | null> {
  const path = await pomoPath($)
  const text = await $.fs.read(path).catch(() => undefined)
  if (text === undefined) return (await $.fs.exists(path)) ? null : emptyPomo(await today($))
  return parsePomo(text)
}

/** Writes beside the file, then renames over it, so no session reads half a file. */
async function writePomo($: EngineInterface, f: PomoFile): Promise<void> {
  const path = await pomoPath($)
  const tmp = `${path}.${SESSION}.tmp`
  const text = serializePomo(f)
  await $.fs.write(tmp, text)
  const why = await $.process
    .run(['mv', '-f', tmp, path])
    .then(r => (r.exitCode === 0 ? '' : `exit ${r.exitCode}: ${r.stderr.trim()}`))
    .catch((err: unknown) => (err instanceof Error ? err.message : String(err)))
  if (why) {
    // Still written, but not atomically: say so once per session instead of falling back in silence.
    if (!(await read($, toldMvFailed))) {
      await update($, toldMvFailed, () => true)
      $.ui.log(`task-track: mv onto ${path} failed (${why}); writing it directly, so another session may read half a file.`)
    }
    await $.fs.write(path, text)
  }
  await update($, pomo, () => f)
}

async function refreshPomo($: EngineInterface): Promise<void> {
  const f = await readPomo($)
  if (f) await update($, pomo, () => f)
}

/**
 * With several vaults the key names the vault whose timer this is, so two vaults' totals for one day
 * don't overwrite each other. Taken from the config, not the band's vaultName, which is '' when no task is picked.
 */
async function saveDay($: EngineInterface, d: DayTotals): Promise<void> {
  const config = await vaultConfig($, (await $.env.get('HOME')) ?? '')
  const owner = config.vaults.length > 1 ? config.vaults.find(v => v.path === vault) : undefined
  await $.store.set(owner ? `focus:${owner.name}:${d.day}` : `focus:${d.day}`, { ms: d.dayMs, blocks: d.dayBlocks })
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
  const template = `${await currentVault($)}/Templates/Daily.md`
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
  const daily = `${await currentVault($)}/Daily/${date}.md`
  await $.fs.write(daily, insertInSection(await dailyText($, daily, date), 'Log', `- ${time} [[${slug}]] ${spent}`))
}

/** A finished day's focus that no session wrote (it ran past midnight, or crashed): written to that day's notes. */
async function flushDay($: EngineInterface, d: DayTotals): Promise<void> {
  const root = await currentVault($)
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

/**
 * Activity in this session: written to the shared file at most once a minute. Q's own
 * actions can start a block; Claude's tool calls (`byClaude`) only keep a running one alive.
 */
async function markActive($: EngineInterface, byClaude = false): Promise<void> {
  const view = await read($, task)
  if (!view) return
  const now = await $.clock.now()
  const p = await read($, pomo)
  if (byClaude && !isRunning(p, now, settings)) return
  if (!shouldTouch(p, now, view.slug)) return
  await changePomo($, f => snapshotTask(touch(f, now, view.slug, settings), view.slug, checkedTitles(view.next)))
}

/** One entry for the AI summary, only while it is on and a block runs (not paused, stopped or on break). */
async function noteActivity($: EngineInterface, entry: string): Promise<void> {
  if (!settings.breakSummaryAI) {
    // Turned off mid-block: what was already recorded leaves the synced file now, not at the block's end.
    if ((await read($, pomo)).blockActivity.length > 0) await changePomo($, f => ({ ...f, blockActivity: [] }))
    return
  }
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
  if (!text) {
    $.ui.toast('(AI summary failed: empty reply)')
    return
  }
  $.ui.toast(text)
  void $.ui.notify(text, { title: 'task-track' })
}

type PomoAction = 'toggle' | 'start' | 'pause' | 'resume' | 'stop'
const POMO_ACTIONS: readonly string[] = ['start', 'pause', 'resume', 'stop']
const isPomoAction = (s: string): s is PomoAction => s === 'toggle' || POMO_ACTIONS.includes(s)

/**
 * One control of the shared timer, from /pomo or a band button. It does not mark activity:
 * a touch first would start a block and turn `/pomo start` into "already running".
 * Returns what to tell Q.
 */
async function runPomo($: EngineInterface, action: PomoAction): Promise<string> {
  const view = (await read($, task)) ?? (await load($))
  if (!view) return 'No active task. /tasks:task-start <name>'
  const now = await $.clock.now()
  const out: { t?: Transition; held?: string } = {}
  const f = await changePomo($, file => {
    out.held = file.slug
    const t =
      action === 'toggle' ? togglePomo(file, now, view.slug, settings)
      : action === 'start' ? start(file, now, view.slug, settings)
      : action === 'pause' ? pause(file, now, settings)
      : action === 'resume' ? resume(file, now, settings)
      : stop(file, now, settings)
    out.t = t
    return 'error' in t ? file : snapshotTask(t.file, view.slug, checkedTitles(view.next))
  })
  if (!f) return `Can't read ${await pomoPath($)}: unreadable or not a timer file. Nothing changed.`
  const t = out.t
  if (!t) throw new Error(`runPomo(${action}): changePomo returned a file without running the change`)
  if ('error' in t) return t.error
  // No compare-and-set on the file: read back, so a change another session overwrote isn't reported as done.
  const check = await readPomo($)
  if (!check) return `Wrote ${await pomoPath($)} but can't read it back. Check the band before relying on it.`
  if (pomoState(check, now, settings) !== pomoState(f, now, settings)) {
    return `Didn't stick: another session wrote the timer at the same moment (${pomoDots(check, now, settings)}). Try again.`
  }
  if (action === 'stop') {
    // stop credits the task holding the timer, which may be another session's.
    const held = out.held || view.slug
    await flushFocus($, held, held === view.slug ? view.path : `${await currentVault($)}/Tasks/${held}.md`)
  }
  return `${pomoDots(f, now, settings)} · ${view.slug}`
}

async function pressPomo($: EngineInterface, action: PomoAction): Promise<void> {
  $.ui.toast(await runPomo($, action))
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
  const event = out.event
  if (!f || event.kind !== 'break') return
  const check = await readPomo($)
  if (!check || check.notifiedBy !== SESSION || check.lastNotifiedBlock !== event.blocks) return
  const root = await currentVault($)
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
  const summary = blockSummary(notes, event.snapshot, event.openedAt)
  const text = `${header}\n${summary}`
  $.ui.toast(text)
  void $.ui.notify(text, { title: 'task-track' })
  if (settings.breakSummaryAI) await aiLine($, event.slug, summary, event.activity)
}

/** A prompt during a break: say once per break how long is left, since no block runs until it ends. */
async function remindBreak($: EngineInterface): Promise<void> {
  const p = await read($, pomo)
  const brk = onBreak(p, await $.clock.now())
  // A paused break has no countdown, and the next block won't start on its own after it.
  if (!brk || p.pausedAt || (await read($, toldBreakUntil)) === p.breakUntil) return
  await update($, toldBreakUntil, () => p.breakUntil)
  $.ui.toast(`On a ${brk.isLong ? 'long ' : ''}break: ${brk.minutesLeft} min left. The next block starts after it.`)
}

async function openPane($: EngineInterface): Promise<void> {
  const view = await read($, task)
  const prefix = await read($, vaultName)
  await $.ui.open({ id: PANE, title: view ? `Task · ${prefix ? `${prefix} · ` : ''}${view.slug}` : 'Task', focus: true })
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
  await $.prompt.submit({ text: '/tasks:task-park' })
}

async function openInObsidian($: EngineInterface, path: string): Promise<void> {
  await $.process.run(['open', `obsidian://open?path=${encodeURIComponent(path)}`])
}

const COMMANDS = [
  { name: 'task', description: 'Show the active task pane (/task hide|show toggles the band)', argumentHint: '[hide|show]' },
  { name: 'note', description: 'Add a line to the active task Log (no model turn)', argumentHint: '<text>', immediate: true },
  { name: 'done', description: 'Check off a Next item (default: the first open one)', argumentHint: '[n]', immediate: true },
  { name: 'openloop', description: 'Add an Open loop to the active task', argumentHint: '<text>', immediate: true },
  { name: 'pomo', description: 'Pomodoro: /pomo pauses or resumes; /pomo start|pause|resume|stop', argumentHint: '[start|pause|resume|stop]', immediate: true },
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
    // /pomo controls the timer; counting its keystroke as activity would start a block first.
    if (/^\/pomo\b/.test(e.text.trimStart())) return next(e)
    await markActive($)
    await remindBreak($)
    await noteActivity($, `prompt: ${truncate(e.text.trim().replaceAll('\n', ' '), 80)}`)
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    const isEdit = e.tool === 'Edit' || e.tool === 'Write' || e.tool === 'NotebookEdit'
    const path = 'file_path' in e && typeof e.file_path === 'string' ? e.file_path : undefined
    await markActive($, true)
    if (isEdit && path) {
      const root = await $.session.root()
      await noteActivity($, `edit: ${path.startsWith(`${root}/`) ? path.slice(root.length + 1) : path}`)
    }
    if (e.tool === 'Bash' && 'command' in e && typeof e.command === 'string') await noteActivity($, `ran: ${truncate(e.command, 80)}`)
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
    return { text: view ? `Task pane: ${view.slug}` : (await read($, problem)) || 'No active task. /tasks:task-start <name>' }
  })

  on('command.run', { command: 'note' }, async ($, e) => {
    await markActive($)
    const text = e.args.trim()
    if (!text) return { text: 'Usage: /note <text>' }
    const view = await addLog($, text)
    if (!view) return { text: 'No active task. /tasks:task-start <name>' }
    return { text: `Logged to ${view.slug}.`, ...told(`Q added a note to the active task (${view.slug}): ${text}`) }
  })

  on('command.run', { command: 'done' }, async ($, e) => {
    await markActive($)
    const view = await load($)
    if (!view) return { text: 'No active task. /tasks:task-start <name>' }
    const arg = e.args.trim()
    const index = arg ? Number(arg) - 1 : firstOpen(view.next)
    const item = view.next[index]
    if (!item) {
      return { text: arg ? `No Next item ${arg} (1–${view.next.length}).` : 'All Next items are done. Add the next step, or /tasks:task-park.' }
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
    if (!view) return { text: 'No active task. /tasks:task-start <name>' }
    return { text: `Open loop added to ${view.slug}.`, ...told(`Q added an open loop to ${view.slug}: ${text}`) }
  })

  on('command.run', { command: 'pomo' }, async ($, e) => {
    const action = e.args.trim() || 'toggle'
    if (!isPomoAction(action)) return { text: `Unknown: /pomo ${action}. Use start|pause|resume|stop` }
    return { text: await runPomo($, action) }
  })

  // ── band above the prompt: only while a task is active ──────────────────

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const view = await read($, task)
    if (!view || e.props.hasSurvey || (await read($, isBandHidden))) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const p = await read($, pomo)
    const now = await $.clock.now()
    const timer = pomoDots(p, now, settings)
    const state = pomoState(p, now, settings)
    const { done, total } = progress(view.next)
    const open = view.next[firstOpen(view.next)]
    const step = open ? splitEstimate(open.text) : undefined
    // Two rows: the slug, counts, timer and buttons on the first; the Next step on its own row,
    // wrapped so the whole step reads at a glance. The width is bodyColumns, which every surface
    // sends (the desktop app sends no viewport) and which already leaves out the engine's `[-]`;
    // without a width the row grows past the edge and the surface clips it.
    const prefix = await read($, vaultName)
    return (
      <Box flexDirection="column" width={Math.max(20, e.props.bodyColumns)} marginTop={1}>
        <Box gap={1}>
          <Box flexShrink={0}>
            <Text bold color="claude">▶ {prefix ? `${prefix} · ` : ''}{view.slug}</Text>
          </Box>
          <Box flexShrink={0}>
            <Text color="subtle">
              {done}/{total} · {timer}
            </Text>
          </Box>
          <Box flexShrink={0} gap={1}>
            {(state === 'running' || state === 'break') && <Button key="pomo-pause" label="⏸" onPress={() => pressPomo($, 'pause')} />}
            {state === 'paused' && <Button key="pomo-resume" label="▶" onPress={() => pressPomo($, 'resume')} />}
            {state !== 'stopped' && state !== 'idle' && <Button key="pomo-stop" label="⏹" onPress={() => pressPomo($, 'stop')} />}
            {(state === 'stopped' || state === 'idle') && <Button key="pomo-start" label="▶" onPress={() => pressPomo($, 'start')} />}
          </Box>
          <Box flexShrink={0} gap={1}>
            {open && <Button key="done" label="Done" onPress={() => pressDoneFirst($)} />}
            <Button key="pane" label="Task" onPress={() => openPane($)} />
            <Button key="hide" label="Hide" onPress={() => hideBand($)} />
          </Box>
        </Box>
        <Text wrap="wrap">
          {step ? `Next: ${step.text.replaceAll('`', '')}` : 'All Next done'}
          {step?.est ? <Text color="subtle">  {step.est}</Text> : null}
        </Text>
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
      const configErr = await read($, configError)
      return (
        <Box flexDirection="column">
          <Text>{why || 'No active task.'}</Text>
          {configErr ? <Text color="subtle" wrap="truncate-end">Vault config error: {configErr}</Text> : null}
          <Text dimColor>Start one with /tasks:task-start &lt;name&gt;</Text>
        </Box>
      )
    }
    const p = await read($, pomo)
    const now = await $.clock.now()
    const timer = pomoDots(p, now, settings)
    const why = await read($, source)
    const vaultLabel = await read($, vaultName)
    const configErr = await read($, configError)
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
            <Text color="subtle"> · {vaultLabel ? `${vaultLabel} · ` : ''}{why}</Text>
          </Text>
          {configErr ? <Text color="subtle" wrap="truncate-end">Vault config error: {configErr}</Text> : null}
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
          <Button key="park" label="Park (/tasks:task-park)" onPress={() => park($)} />
          <Button key="obsidian" label="Open in Obsidian" onPress={() => openInObsidian($, view.path)} />
        </Box>
      </Box>
    )
  })
}
