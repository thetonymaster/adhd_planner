// Which task a session shows. Pure: register.tsx gathers the inputs (IO at the edge).

export type Candidate = { slug: string; repo: string; status: string; mtimeMs: number }
export type Source = 'session' | 'repo' | 'global'

const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---/

function field(block: string, name: string): string {
  const m = new RegExp(`^${name}:\\s*"?([^"\\r\\n]*?)"?\\s*$`, 'm').exec(block)
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
