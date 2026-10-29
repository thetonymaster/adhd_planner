// The tasks of the repo a session runs in, for the project-tasks pane. Pure: register.tsx gathers the candidates.
import type { ProjectList, ProjectTask } from '../types'
import { normalize } from './resolve'
import type { Candidate } from './resolve'

/** Parked rows shown before `… N more`. */
export const PARKED_CAP = 5

function isWithin(dir: string, root: string): boolean {
  return dir === root || dir.startsWith(`${root}/`)
}

/**
 * Non-done notes whose `repo:` is `dir` or a parent, the deepest such root only; active first,
 * then newest. Any status but `active` (empty, a typo) lists as parked, so no task goes missing.
 */
export function projectTasks(candidates: readonly Candidate[], dir: string, home: string): ProjectList {
  const here = normalize(dir, home)
  const bound = candidates
    .filter(c => c.repo !== '' && c.status !== 'done')
    .map(c => ({ c, root: normalize(c.repo, home) }))
    .filter(x => isWithin(here, x.root))
  const deepest = bound.reduce((longest, x) => (x.root.length > longest.length ? x.root : longest), '')
  if (!deepest) return { repo: '', tasks: [] }
  const tasks: ProjectTask[] = bound
    .filter(x => x.root === deepest)
    .map(({ c }) => ({ slug: c.slug, title: c.title || c.slug, status: c.status === 'active' ? 'active' : 'parked', mtimeMs: c.mtimeMs }))
    .sort((a, b) => Number(b.status === 'active') - Number(a.status === 'active') || b.mtimeMs - a.mtimeMs)
  return { repo: deepest.slice(deepest.lastIndexOf('/') + 1), tasks }
}

/** The parked rows to draw: the first PARKED_CAP unless the list is open, and how many that hides. */
export function visibleParked(tasks: readonly ProjectTask[], isOpen: boolean): { shown: ProjectTask[]; hidden: number } {
  const shown = isOpen ? [...tasks] : tasks.slice(0, PARKED_CAP)
  return { shown, hidden: tasks.length - shown.length }
}
