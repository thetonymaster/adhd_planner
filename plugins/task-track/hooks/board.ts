// The task board: task notes' frontmatter → Doing / Parked / Done columns grouped by project. Pure: the pane gathers the notes.

import { field, FRONTMATTER } from './resolve'

export type BoardNote = { slug: string; title: string; project: string; status: string; finished: string }
export type BoardColumn = {
  name: 'Doing' | 'Parked' | 'Done'
  count: number
  groups: { project: string; cards: { slug: string; title: string }[] }[]
}

const NO_PROJECT = 'No project'
const DATE = /^\d{4}-\d{2}-\d{2}$/
const DAY_MS = 86_400_000

/** `[[Projects/Name|alias]]` → `Name`; empty or `[[]]` → 'No project'. */
function projectName(up: string): string {
  const target = up.replace(/^\[\[|\]\]$/g, '').split('|')[0]?.split('/').pop()?.trim() ?? ''
  return target === '' ? NO_PROJECT : target
}

/** A note's board fields. The title is the first `# ` line after the frontmatter, else the slug. */
export function boardNote(slug: string, text: string): BoardNote {
  const block = FRONTMATTER.exec(text)?.[1] ?? ''
  const body = text.replace(FRONTMATTER, '')
  const title = /^# (.*)$/m.exec(body)?.[1]?.trim() ?? ''
  return {
    slug,
    title: title === '' ? slug : title,
    project: projectName(field(block, 'up')),
    status: field(block, 'status'),
    finished: field(block, 'finished'),
  }
}

function dayNumber(date: string): number {
  const [y = 0, m = 1, d = 1] = date.split('-').map(Number)
  return Date.UTC(y, m - 1, d) / DAY_MS
}

/** Finished within the last `days` days, today included; a missing, malformed or future date is out. */
function isRecent(finished: string, today: string, days: number): boolean {
  if (!DATE.test(finished) || !DATE.test(today)) return false
  const age = dayNumber(today) - dayNumber(finished)
  return age >= 0 && age < days
}

function column(name: BoardColumn['name'], notes: readonly BoardNote[]): BoardColumn {
  const byProject = new Map<string, { slug: string; title: string }[]>()
  for (const n of notes) byProject.set(n.project, [...(byProject.get(n.project) ?? []), { slug: n.slug, title: n.title }])
  const groups = [...byProject]
    .map(([project, cards]) => ({ project, cards: cards.sort((a, b) => a.title.toLowerCase().localeCompare(b.title.toLowerCase())) }))
    .sort((a, b) => Number(a.project === NO_PROJECT) - Number(b.project === NO_PROJECT) || a.project.localeCompare(b.project))
  return { name, count: notes.length, groups }
}

/** Doing (active), Parked (parked), Done (done and finished in the last `days` days); other statuses are not on the board. */
export function buildBoard(notes: readonly BoardNote[], today: string, days = 7): BoardColumn[] {
  return [
    column('Doing', notes.filter(n => n.status === 'active')),
    column('Parked', notes.filter(n => n.status === 'parked')),
    column('Done', notes.filter(n => n.status === 'done' && isRecent(n.finished, today, days))),
  ]
}

/** `<vault> · Doing N · Parked N · Done N`, the board's header and /board's reply. */
export function boardHeader(vault: string, columns: readonly BoardColumn[]): string {
  return [vault, ...columns.map(c => `${c.name} ${c.count}`)].join(' · ')
}

export type BoardLine ={ kind: 'project' | 'card'; slug: string; text: string }

/**
 * A column's project headings and cards in `rows` lines. When they don't all fit, the last line is left for
 * "… N more" (N = the cards cut), and a heading whose cards were all cut goes too.
 */
export function fitColumn(column: BoardColumn, rows: number): { lines: BoardLine[]; more: number } {
  const all: BoardLine[] = column.groups.flatMap(g => [
    { kind: 'project' as const, slug: '', text: g.project },
    ...g.cards.map(c => ({ kind: 'card' as const, slug: c.slug, text: c.title })),
  ])
  if (all.length <= rows) return { lines: all, more: 0 }
  const lines = all.slice(0, Math.max(0, rows - 1))
  while (lines.at(-1)?.kind === 'project') lines.pop()
  return { lines, more: column.count - lines.filter(l => l.kind === 'card').length }
}
