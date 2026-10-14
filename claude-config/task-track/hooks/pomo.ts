// The shared Pomodoro: one JSON file every session reads and writes (vault/Tasks/.pomo.json).
// Timestamps, not counters: each session derives the same block progress from the same
// numbers, so two sessions never double-count, and a restart resumes mid-block. Pure: no IO.
import type { PomoFile } from '../types'

export type PomoConfig = {
  focusMinutes: number
  breakMinutes: number
  longBreakEvery: number
  longBreakMinutes: number
}

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

/** A finished day's totals, handed back once by whichever session rolls the day over. */
export type DayTotals = Pick<PomoFile, 'day' | 'dayMs' | 'dayBlocks' | 'logged'>

const MINUTE = 60_000
/** Activity closer than this to the last recorded one is not written again. */
export const TOUCH_EVERY_MS = MINUTE

export function emptyPomo(day: string): PomoFile {
  return {
    version: 1,
    slug: '',
    blockStartedAt: 0,
    breakUntil: 0,
    isLongBreak: false,
    pausedAt: 0,
    isStopped: false,
    blockOpenedAt: 0,
    blockSnapshot: {},
    blockActivity: [],
    lastActiveAt: 0,
    creditedUntil: 0,
    blocksDone: 0,
    lastNotifiedBlock: 0,
    notifiedBy: '',
    day,
    dayMs: {},
    dayBlocks: {},
    logged: {},
  }
}

/** The file's text as a PomoFile, or null when it is not one (half-written, another version). */
export function parsePomo(text: string): PomoFile | null {
  try {
    const value = JSON.parse(text) as Partial<PomoFile> | null
    if (!value || value.version !== 1 || typeof value.slug !== 'string') return null
    return { ...emptyPomo(String(value.day ?? '')), ...value } as PomoFile
  } catch {
    return null
  }
}

export function serializePomo(f: PomoFile): string {
  return `${JSON.stringify(f, null, 2)}\n`
}

/** Starts a new day's totals when `day` moved on; the finished day comes back once. */
export function rollDay(f: PomoFile, day: string): { file: PomoFile; finished?: DayTotals } {
  if (f.day === day) return { file: f }
  const hadTime = Object.values(f.dayMs).some(ms => ms > 0)
  const finished = hadTime && f.day ? { day: f.day, dayMs: f.dayMs, dayBlocks: f.dayBlocks, logged: f.logged } : undefined
  // A pause left over the rollover ends its block or break: resuming would credit the night.
  const unpaused = f.pausedAt
    ? { blockStartedAt: 0, breakUntil: 0, creditedUntil: f.lastActiveAt, blockOpenedAt: 0, blockSnapshot: {}, blockActivity: [] }
    : {}
  return { file: { ...f, ...unpaused, day, dayMs: {}, dayBlocks: {}, logged: {}, blocksDone: 0, lastNotifiedBlock: 0, isStopped: false, pausedAt: 0 }, finished }
}

/** The break running at `now`, or null: none, or it is over. */
export function onBreak(f: PomoFile, now: number): { minutesLeft: number; isLong: boolean } | null {
  if (f.breakUntil <= now) return null
  return { minutesLeft: Math.ceil((f.breakUntil - now) / MINUTE), isLong: f.isLongBreak }
}

/** A block is running and not yet idle: Claude's work may keep it alive, never start one. */
export function isRunning(f: PomoFile, now: number, cfg: PomoConfig): boolean {
  if (f.isStopped || f.pausedAt) return false
  return f.blockStartedAt !== 0 && now - f.lastActiveAt < cfg.breakMinutes * MINUTE
}

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

/** Records a task's checked items the first time the running block reaches it; no-op without a block. */
export function snapshotTask(f: PomoFile, slug: string, checked: string[]): PomoFile {
  if (f.blockOpenedAt === 0 || slug in f.blockSnapshot) return f
  return { ...f, blockSnapshot: { ...f.blockSnapshot, [slug]: checked } }
}

/** Entries kept for the AI summary: enough for 25 minutes, small enough for one short Haiku call. */
export const MAX_ACTIVITY = 60

/** Appends one activity entry unless it repeats the last one; keeps the newest MAX_ACTIVITY. */
export function recordActivity(f: PomoFile, entry: string): PomoFile {
  if (f.blockActivity.at(-1) === entry) return f
  return { ...f, blockActivity: [...f.blockActivity, entry].slice(-MAX_ACTIVITY) }
}

/** Whether an activity at `now` needs writing: a new task, a block to start, or a minute since the last. */
export function shouldTouch(f: PomoFile, now: number, slug: string): boolean {
  if (f.isStopped || f.pausedAt) return false
  const canStart = f.blockStartedAt === 0 && !onBreak(f, now)
  return f.slug !== slug || canStart || now - f.lastActiveAt >= TOUCH_EVERY_MS
}

/**
 * Records activity on `slug`. One timer for the person: a different task keeps the running
 * block, with the time so far credited to the task it was on. After a break (no activity for
 * breakMinutes, from any session) the next activity starts a fresh block.
 */
export function touch(f: PomoFile, now: number, slug: string, cfg: PomoConfig): PomoFile {
  if (f.isStopped || f.pausedAt) return f
  // A break runs to its end: activity is recorded, but no block starts and no time is credited.
  if (onBreak(f, now)) return { ...f, slug, creditedUntil: now, lastActiveAt: now }
  const isIdle = f.blockStartedAt === 0 || now - f.lastActiveAt >= cfg.breakMinutes * MINUTE
  if (isIdle) {
    const settled = f.slug && f.blockStartedAt !== 0 ? credit(f, Math.min(now, f.lastActiveAt + cfg.breakMinutes * MINUTE)) : f
    return { ...settled, slug, blockStartedAt: now, breakUntil: 0, creditedUntil: now, lastActiveAt: now, blockOpenedAt: now, blockSnapshot: {}, blockActivity: [] }
  }
  if (f.slug === slug) return { ...f, lastActiveAt: now }
  return { ...credit(f, now), slug, creditedUntil: now, lastActiveAt: now }
}

function credit(f: PomoFile, until: number): PomoFile {
  const ms = until - f.creditedUntil
  if (!f.slug || ms <= 0) return f
  return { ...f, dayMs: { ...f.dayMs, [f.slug]: (f.dayMs[f.slug] ?? 0) + ms } }
}

/**
 * Moves the shared clock to `now`. Active time (activity within breakMinutes) is credited
 * once, up to `creditedUntil`, whichever session ticks. A full block bumps the count and
 * returns a break event only while that block has not been announced yet.
 */
export function advance(f: PomoFile, now: number, cfg: PomoConfig): { file: PomoFile; event: PomoEvent } {
  const none = { kind: 'none' } as const
  if (f.isStopped || f.pausedAt) return { file: f, event: none }
  if (!f.slug || f.blockStartedAt === 0) return { file: f, event: none }
  if (now - f.lastActiveAt >= cfg.breakMinutes * MINUTE) {
    const credited = credit(f, Math.min(now, f.lastActiveAt + cfg.breakMinutes * MINUTE))
    return { file: { ...credited, blockStartedAt: 0, creditedUntil: now, blockOpenedAt: 0, blockSnapshot: {}, blockActivity: [] }, event: none }
  }
  let next = { ...credit(f, now), creditedUntil: now }
  if (now - next.blockStartedAt < cfg.focusMinutes * MINUTE) return { file: next, event: none }

  const finished = { openedAt: next.blockOpenedAt || next.blockStartedAt, snapshot: next.blockSnapshot, activity: next.blockActivity }
  const blocksDone = next.blocksDone + 1
  const isLong = cfg.longBreakEvery > 0 && blocksDone % cfg.longBreakEvery === 0
  next = {
    ...next,
    blocksDone,
    blockStartedAt: 0,
    breakUntil: now + (isLong ? cfg.longBreakMinutes : cfg.breakMinutes) * MINUTE,
    isLongBreak: isLong,
    blockOpenedAt: 0,
    blockSnapshot: {},
    blockActivity: [],
    dayBlocks: { ...next.dayBlocks, [next.slug]: (next.dayBlocks[next.slug] ?? 0) + 1 },
  }
  if (blocksDone <= next.lastNotifiedBlock) return { file: next, event: none }
  return {
    file: { ...next, lastNotifiedBlock: blocksDone },
    event: { kind: 'break', slug: next.slug, blocks: blocksDone, isLong, minutes: isLong ? cfg.longBreakMinutes : cfg.breakMinutes, ...finished },
  }
}

/** Minutes into the running block (0 between blocks). */
export function blockMinutes(f: PomoFile, now: number): number {
  return f.blockStartedAt === 0 ? 0 : Math.max(0, Math.floor((now - f.blockStartedAt) / MINUTE))
}

/** The timer for the band and the pane: `🍅 ●●○○ 12/25m`, `⏸ … paused`, `☕ … break 4m left`, `⏹ off`, `○ … idle`. */
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
  // A block idle past breakMinutes reads idle at once, not at the next tick that ends it.
  if (f.blockStartedAt !== 0 && pomoState(f, now, cfg) !== 'idle') return `${f.pausedAt ? '⏸' : '🍅'} ${dots} ${blockMinutes(f, at)}/${cfg.focusMinutes}m${paused}`
  return `○ ${dots} idle`
}

/** Focus on `slug` today not yet written to the notes. */
export function unlogged(f: PomoFile, slug: string): { ms: number; blocks: number } {
  const logged = f.logged[slug] ?? { ms: 0, blocks: 0 }
  return { ms: (f.dayMs[slug] ?? 0) - logged.ms, blocks: (f.dayBlocks[slug] ?? 0) - logged.blocks }
}

/** Marks all of today's focus on `slug` as written, so no session writes it twice. */
export function markLogged(f: PomoFile, slug: string): PomoFile {
  return { ...f, logged: { ...f.logged, [slug]: { ms: f.dayMs[slug] ?? 0, blocks: f.dayBlocks[slug] ?? 0 } } }
}
