import type { Register } from 'claude-code'

// Files of this repo that only change through their build: planner.plugin via scripts/build-plugin.sh, uv.lock via uv.
const BUILT = ['planner.plugin', 'setup/uv.lock']

// Resolves `.`, `..` and repeated slashes of an absolute path, so `/repo/setup/../planner.plugin` is `/repo/planner.plugin`.
// Symlinks are not followed.
export const normalize = (path: string): string => {
  const parts: string[] = []
  for (const p of path.split('/')) {
    if (p === '' || p === '.') continue
    if (p === '..') parts.pop()
    else parts.push(p)
  }
  return `/${parts.join('/')}`
}

export const guardReason = (root: string, path: string): string | undefined =>
  BUILT.some(f => normalize(path) === `${normalize(root)}/${f}`)
    ? `${path} is a build output: rebuild it (bash scripts/build-plugin.sh / uv lock), don't edit it.`
    : undefined

// The plugin folder an edited file belongs to, when it is under <root>/plugins/<name>/.
export const pluginDir = (root: string, path: string): string | undefined => {
  const prefix = `${normalize(root)}/plugins/`
  path = normalize(path)
  if (!path.startsWith(prefix)) return undefined
  const name = path.slice(prefix.length).split('/')[0]
  return name && path.length > prefix.length + name.length ? prefix + name : undefined
}

export const register: Register = on => {
  for (const tool of ['Edit', 'Write'] as const) {
    on('tool.call', { tool }, async ($, e, next) => {
      const reason = guardReason(await $.session.root(), e.file_path)
      return reason ? { deny: `${$.plugin.name}: ${reason}` } : next(e)
    }).catch(($, e, next) => (next.called ? next(e) : { deny: `${$.plugin.name}: its guard failed.` }))

    // After an edit inside plugins/<name>/, validate that plugin and hand the model any failure.
    on('tool.call', { tool }, async ($, e, next) => {
      const ran = await next(e)
      if (ran.deny !== undefined || ran.isError) return ran
      const dir = pluginDir(await $.session.root(), e.file_path)
      if (!dir) return ran
      const { exitCode, stdout, stderr } = await $.process.run(['claude', 'plugin', 'validate', dir])
      if (exitCode === 0) return ran
      return { ...ran, context: [...(ran.context ?? []), `claude plugin validate ${dir} failed (exit ${exitCode}) after this edit:\n${stdout}${stderr}`] }
    }).catch(($, e, next) => next(e))
  }
}
