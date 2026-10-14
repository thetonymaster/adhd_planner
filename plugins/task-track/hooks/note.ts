// Pure functions over a task note's markdown. No IO: register.tsx reads and writes.
import type { NextItem, TaskView } from '../types'

const HEADING = /^## (.+?)\s*$/
const CHECKBOX = /^\s*- \[([ xX])\] (.*\S)\s*$/
const BULLET = /^\s*- (.*\S)\s*$/

/** [index of the `## name` line, index one past the section's last line], or null. */
export function sectionRange(lines: readonly string[], name: string): [number, number] | null {
  const start = lines.findIndex(l => HEADING.exec(l)?.[1] === name)
  if (start === -1) return null
  let end = start + 1
  while (end < lines.length && !HEADING.test(lines[end] ?? '')) end++
  return [start, end]
}

function sectionLines(lines: readonly string[], name: string): string[] {
  const range = sectionRange(lines, name)
  return range ? lines.slice(range[0] + 1, range[1]) : []
}

export function parseNote(slug: string, path: string, text: string, mtimeMs: number): TaskView {
  const lines = text.split('\n')
  const title = lines.find(l => l.startsWith('# '))?.slice(2).trim() || slug
  const up = /^up:\s*"?\[\[([^\]|]+)/m.exec(text)?.[1] ?? ''
  const goal = sectionLines(lines, 'Goal').map(l => l.trim()).filter(Boolean).join(' ')
  const next: NextItem[] = sectionLines(lines, 'Next').flatMap(l => {
    const m = CHECKBOX.exec(l)
    return m ? [{ text: m[2] ?? '', isDone: m[1] !== ' ' }] : []
  })
  const bullets = (name: string) =>
    sectionLines(lines, name).flatMap(l => {
      const m = BULLET.exec(l)
      return m && !CHECKBOX.test(l) ? [m[1] ?? ''] : []
    })
  const openLoops = bullets('Open loops').filter(l => !l.startsWith('~~'))
  const allLog = bullets('Log')
  return { slug, path, title, up, goal, next, openLoops, log: allLog.slice(-5), logCount: allLog.length, mtimeMs }
}

/** Flips the checkbox of the `index`th non-empty Next item (0-based). Unchanged text when out of range. */
export function toggleNext(text: string, index: number): string {
  const lines = text.split('\n')
  const range = sectionRange(lines, 'Next')
  if (!range) return text
  let seen = -1
  for (let i = range[0] + 1; i < range[1]; i++) {
    const line = lines[i] ?? ''
    const m = CHECKBOX.exec(line)
    if (!m) continue
    seen++
    if (seen === index) {
      lines[i] = line.replace(/\[([ xX])\]/, m[1] === ' ' ? '[x]' : '[ ]')
      return lines.join('\n')
    }
  }
  return text
}

/** Index of the first unchecked Next item, or -1. */
export function firstOpen(next: readonly NextItem[]): number {
  return next.findIndex(n => !n.isDone)
}

/** Inserts `line` after the last non-blank line of `## name`; creates the section at the end if missing. */
export function insertInSection(text: string, name: string, line: string): string {
  const lines = text.split('\n')
  const range = sectionRange(lines, name)
  if (!range) {
    const body = text.replace(/\s*$/, '')
    return `${body}\n\n## ${name}\n${line}\n`
  }
  let at = range[1]
  while (at > range[0] + 1 && (lines[at - 1] ?? '').trim() === '') at--
  // Drop an empty placeholder bullet ("- ") the template left behind.
  if (at > range[0] + 1 && /^\s*-\s*$/.test(lines[at - 1] ?? '')) {
    lines.splice(at - 1, 1)
    at--
  }
  lines.splice(at, 0, line)
  return lines.join('\n')
}

export function progress(next: readonly NextItem[]): { done: number; total: number } {
  return { done: next.filter(n => n.isDone).length, total: next.length }
}

export function elapsed(ms: number): string {
  const minutes = Math.max(0, Math.floor(ms / 60000))
  if (minutes < 60) return `${minutes}m`
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`
}

export function stamp(d: Date): { date: string; time: string } {
  const p = (n: number) => String(n).padStart(2, '0')
  return {
    date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
    time: `${p(d.getHours())}:${p(d.getMinutes())}`,
  }
}

export function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}

const ESTIMATE = /\s*\(~\s*(\d+)\s*(min|m|hours?|h|days?|d)\b[^)]*\)\s*$/
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** `Copy hooks (~10 min)` → `{ text: 'Copy hooks', est: '~10m' }`; no trailing estimate → est ''. */
export function splitEstimate(text: string): { text: string; est: string } {
  const m = ESTIMATE.exec(text)
  if (!m) return { text, est: '' }
  const n = Number(m[1])
  const unit = (m[2] ?? '').charAt(0)
  const est = unit === 'm' && n >= 60 && n % 60 === 0 ? `~${n / 60}h` : `~${n}${unit}`
  return { text: text.slice(0, m.index), est }
}

/** A Log line for the pane: `[[2026-10-13]] 13:41 — x` → `{ when: '13:41', text: 'x' }`, `Oct 12` on other days. */
export function logEntry(line: string, today: string): { when: string; text: string } {
  const m = /^\[\[(\d{4})-(\d{2})-(\d{2})\]\]\s*(.*?)\s+—\s+(.*)$/.exec(line)
  if (!m) return { when: '', text: line }
  const [, y, mo, d, time, text] = m
  const isToday = `${y}-${mo}-${d}` === today
  const when = isToday && /^\d{2}:\d{2}$/.test(time ?? '') ? (time ?? '') : `${MONTHS[Number(mo) - 1]} ${Number(d)}`
  return { when, text: text ?? '' }
}

/** `a `b` c` → plain and code runs, backticks dropped; an unclosed backtick runs to the end. */
export function codeSpans(text: string): { text: string; isCode: boolean }[] {
  return text
    .split('`')
    .map((part, i) => ({ text: part, isCode: i % 2 === 1 }))
    .filter(s => s.text !== '')
}

/** Log lines newest first by their `[[date]] HH:MM`; a line with no time sorts after its day's timed ones, undated last. */
export function logOrder(lines: readonly string[]): string[] {
  const key = (line: string) => {
    const m = /^\[\[(\d{4}-\d{2}-\d{2})\]\]\s*(\d{2}:\d{2})?/.exec(line)
    return m ? `${m[1]} ${m[2] ?? '00:00'}` : ''
  }
  return lines
    .map((line, i) => ({ line, i, k: key(line) }))
    .sort((a, b) => (a.k === b.k ? b.i - a.i : a.k < b.k ? 1 : -1))
    .map(x => x.line)
}
