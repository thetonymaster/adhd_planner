// Which task a session shows. Pure: register.tsx gathers the inputs (IO at the edge).

export type Candidate = { slug: string; repo: string; status: string; mtimeMs: number }
export type Source = 'session' | 'repo' | 'global'

const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---/

function field(block: string, name: string): string {
  const m = new RegExp(`^${name}:[ \\t]*"?([^"\\r\\n]*?)"?\\s*$`, 'm').exec(block)
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

// ── several vaults: mirrors plugins/tasks/hooks/vaults.py; both run tests/fixtures/vault-cases.ts ──

export type VaultSpec = { name: string; path: string; folders: readonly { written: string; root: string }[] }
/** timezone: IANA zone for stamps ('' = the runtime's local zone); warning: why vaults.json's timezone was ignored. */
export type VaultConfig = { default: string; vaults: readonly VaultSpec[]; isImplicit: boolean; error: string; timezone: string; warning: string }
export type VaultState = { vault: VaultSpec; candidates: readonly Candidate[]; override: string; overrideMtimeMs: number; global: string }
export type VaultPick = { vault: VaultSpec; slug: string; reason: string }

const VAULT_NAME = /^[a-z0-9][a-z0-9-]*$/

/** A task slug read from a vault file. Mirrors vaults.slug_or_empty: anything else could name a path outside Tasks/. */
export function isSlug(s: string): boolean {
  return VAULT_NAME.test(s)
}

/** `<root>/Tasks/<slug>.md`; throws for a non-slug instead of building a path that leaves Tasks/. */
export function taskNotePath(root: string, slug: string): string {
  if (!isSlug(slug)) throw new Error(`task slug '${slug}' is not kebab-case; refusing to build a path from it`)
  return `${root}/Tasks/${slug}.md`
}

/** No vaults.json, or a broken one: the single vault from the plugin option, $VAULT or ~/vault. */
export function implicitVault(fallback: string, home: string, error = ''): VaultConfig {
  return { default: 'default', vaults: [{ name: 'default', path: normalize(fallback, home), folders: [] }], isImplicit: true, error, timezone: '', warning: '' }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** vaults.json text → config; any problem → the implicit vault, with `error` naming the file and what is wrong. */
export function parseVaults(text: string, where: string, fallback: string, home: string): VaultConfig {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch (err) {
    return implicitVault(fallback, home, `${where}: not valid JSON (${err instanceof Error ? err.message : String(err)})`)
  }
  const parsed = vaultsFrom(data, home)
  if (typeof parsed === 'string') return implicitVault(fallback, home, `${where}: ${parsed}`)
  const zone = zoneFrom(isRecord(data) ? data.timezone : undefined)
  return { ...parsed, timezone: zone.timezone, warning: zone.warning ? `${where}: ${zone.warning}` : '' }
}

/** True when the runtime knows `name` as a time zone. */
export function isZone(name: string): boolean {
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: name })
    return true
  } catch (err) {
    if (err instanceof RangeError) return false
    throw err
  }
}

/** The zone stamps use: vaults.json's, else a valid $TZ, else '' (the runtime's local zone). */
export function zoneFor(config: VaultConfig, envTZ: string): string {
  if (config.timezone) return config.timezone
  return envTZ && isZone(envTZ) ? envTZ : ''
}

/** vaults.json `timezone` → the zone, or '' and why it was ignored (same words as vaults.py). A bad zone must not cost the vaults. */
function zoneFrom(raw: unknown): { timezone: string; warning: string } {
  if (raw === undefined || raw === null || raw === '') return { timezone: '', warning: '' }
  if (typeof raw !== 'string') {
    return { timezone: '', warning: `"timezone" must be a string like 'America/Mexico_City', got ${JSON.stringify(raw)}; using $TZ or the system clock` }
  }
  if (!isZone(raw.trim())) return { timezone: '', warning: `timezone '${raw}' is not an IANA zone; using $TZ or the system clock` }
  return { timezone: raw.trim(), warning: '' }
}

/** The config, or what is wrong with it (same words as vaults.py). */
function vaultsFrom(data: unknown, home: string): VaultConfig | string {
  if (!isRecord(data) || !isRecord(data.vaults) || Object.keys(data.vaults).length === 0) {
    return 'expected {"vaults": {"<name>": {"path": "..."}}} with at least one vault'
  }
  const vaults: VaultSpec[] = []
  const owner = new Map<string, string>()
  for (const [name, spec] of Object.entries(data.vaults)) {
    if (!VAULT_NAME.test(name)) return `vault name '${name}' must be kebab-case (a-z, 0-9, -)`
    const path = isRecord(spec) ? spec.path : undefined
    if (typeof path !== 'string' || path.trim() === '') return `vault '${name}' has no "path"`
    if (!normalize(path.trim(), home).startsWith('/')) return `vault '${name}': path '${path}' must be absolute or start with ~/`
    const folders: unknown = isRecord(spec) && 'folders' in spec ? spec.folders : []
    if (!Array.isArray(folders) || !folders.every((f): f is string => typeof f === 'string' && f.trim() !== '')) {
      return `vault '${name}': "folders" must be a list of paths`
    }
    const pairs: { written: string; root: string }[] = []
    for (const written of folders) {
      if (!normalize(written.trim(), home).startsWith('/')) return `vault '${name}': folder '${written}' must be absolute or start with ~/`
      // no symlink resolution here (vaults.py resolves them); accepted, see spec §4
      const root = normalize(written, home)
      const other = owner.get(root)
      if (other !== undefined && other !== name) return `folder '${written}' is listed by both '${other}' and '${name}'`
      owner.set(root, name)
      pairs.push({ written, root })
    }
    vaults.push({ name, path: normalize(path.trim(), home), folders: pairs })
  }
  const names = vaults.map(v => v.name)
  const chosen = data.default ?? (names.length === 1 ? names[0] : undefined)
  if (chosen === undefined) return `"default" is required with ${names.length} vaults`
  if (typeof chosen !== 'string' || !names.includes(chosen)) return `"default" is '${String(chosen)}', not one of: ${names.join(', ')}`
  return { default: chosen, vaults, isImplicit: false, error: '', timezone: '', warning: '' }
}

/** The default vault; parseVaults and implicitVault guarantee it exists. */
export function defaultVault(config: VaultConfig): VaultSpec {
  const v = config.vaults.find(x => x.name === config.default)
  if (!v) throw new Error(`vault config: default '${config.default}' is not among: ${config.vaults.map(x => x.name).join(', ')}`)
  return v
}

/**
 * Session override (newest across vaults) → a repo note in any vault (deepest, then active, then
 * newest; done never binds, nor does a note whose name is not a slug) → the deepest bound folder (its vault's .active) → the default
 * vault's .active. `states` holds only vaults that have Tasks/; null when none of them answers.
 */
export function pickVault(input: { config: VaultConfig; states: readonly VaultState[]; dir: string; home: string }): VaultPick | null {
  const { config, states, home } = input
  const dir = normalize(input.dir, home)
  // candidates are every readable note; the mod's candidates() rethrows read errors, so this matches vaults.py's all-stems check
  const over = states
    .filter(s => isSlug(s.override) && s.candidates.some(c => c.slug === s.override))
    .sort((a, b) => b.overrideMtimeMs - a.overrideMtimeMs)[0]
  if (over) return { vault: over.vault, slug: over.override, reason: 'this session' }
  const best = states
    .flatMap(s => s.candidates.filter(c => isSlug(c.slug) && c.repo !== '' && c.status !== 'done').map(c => ({ s, c, root: normalize(c.repo, home) })))
    .filter(x => isWithin(dir, x.root))
    .sort(
      (a, b) =>
        b.root.length - a.root.length ||
        Number(b.c.status === 'active') - Number(a.c.status === 'active') ||
        b.c.mtimeMs - a.c.mtimeMs ||
        (a.c.slug < b.c.slug ? 1 : a.c.slug > b.c.slug ? -1 : 0),
    )[0]
  if (best) return { vault: best.s.vault, slug: best.c.slug, reason: `project: ${best.root.split('/').pop()}` }
  const folder = states
    .flatMap(s => s.vault.folders.filter(f => isWithin(dir, f.root)).map(f => ({ s, f })))
    .sort((a, b) => b.f.root.length - a.f.root.length)[0]
  if (folder) return { vault: folder.s.vault, slug: isSlug(folder.s.global) ? folder.s.global : '', reason: `folder ${folder.f.written}` }
  const byDefault = states.find(s => s.vault.name === config.default)
  return byDefault ? { vault: byDefault.vault, slug: isSlug(byDefault.global) ? byDefault.global : '', reason: config.isImplicit ? 'global' : 'default' } : null
}
