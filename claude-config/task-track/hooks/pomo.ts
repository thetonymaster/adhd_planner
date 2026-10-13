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
  | { kind: 'break'; slug: string; blocks: number; isLong: boolean; minutes: number }

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
  return { file: { ...f, day, dayMs: {}, dayBlocks: {}, logged: {}, blocksDone: 0, lastNotifiedBlock: 0 }, finished }
}

/** Whether an activity at `now` needs writing: a new task, no block running, or a minute since the last. */
export function shouldTouch(f: PomoFile, now: number, slug: string): boolean {
  return f.slug !== slug || f.blockStartedAt === 0 || now - f.lastActiveAt >= TOUCH_EVERY_MS
}

/**
 * Records activity on `slug`. A new task starts its own block count. After a break
 * (no activity for breakMinutes, from any session) the next activity starts a fresh block.
 */
export function touch(f: PomoFile, now: number, slug: string, cfg: PomoConfig): PomoFile {
  if (f.slug !== slug) {
    return { ...f, slug, blockStartedAt: now, lastActiveAt: now, creditedUntil: now, blocksDone: f.dayBlocks[slug] ?? 0, lastNotifiedBlock: f.dayBlocks[slug] ?? 0 }
  }
  const isFresh = f.blockStartedAt === 0 || now - f.lastActiveAt >= cfg.breakMinutes * MINUTE
  return isFresh ? { ...f, blockStartedAt: now, creditedUntil: now, lastActiveAt: now } : { ...f, lastActiveAt: now }
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
  if (!f.slug || f.blockStartedAt === 0) return { file: f, event: none }
  if (now - f.lastActiveAt >= cfg.breakMinutes * MINUTE) {
    const credited = credit(f, Math.min(now, f.lastActiveAt + cfg.breakMinutes * MINUTE))
    return { file: { ...credited, blockStartedAt: 0, creditedUntil: now }, event: none }
  }
  let next = { ...credit(f, now), creditedUntil: now }
  if (now - next.blockStartedAt < cfg.focusMinutes * MINUTE) return { file: next, event: none }

  const blocksDone = next.blocksDone + 1
  next = {
    ...next,
    blocksDone,
    blockStartedAt: now,
    dayBlocks: { ...next.dayBlocks, [next.slug]: (next.dayBlocks[next.slug] ?? 0) + 1 },
  }
  if (blocksDone <= next.lastNotifiedBlock) return { file: next, event: none }
  const isLong = cfg.longBreakEvery > 0 && blocksDone % cfg.longBreakEvery === 0
  return {
    file: { ...next, lastNotifiedBlock: blocksDone },
    event: { kind: 'break', slug: next.slug, blocks: blocksDone, isLong, minutes: isLong ? cfg.longBreakMinutes : cfg.breakMinutes },
  }
}

/** Minutes into the running block (0 between blocks). */
export function blockMinutes(f: PomoFile, now: number): number {
  return f.blockStartedAt === 0 ? 0 : Math.max(0, Math.floor((now - f.blockStartedAt) / MINUTE))
}

/** `●●○○ 12/25m` for the band and the status line. */
export function pomoDots(f: PomoFile, now: number, cfg: PomoConfig): string {
  const every = Math.max(1, cfg.longBreakEvery)
  const filled = f.blocksDone % every
  const label = f.blockStartedAt === 0 ? 'break' : `${blockMinutes(f, now)}/${cfg.focusMinutes}m`
  return `${'●'.repeat(filled)}${'○'.repeat(every - filled)} ${label}`
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
