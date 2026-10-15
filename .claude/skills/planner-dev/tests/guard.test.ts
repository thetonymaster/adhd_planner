import { expect, test } from 'claude-code/testing'

import { guardReason, normalize, pluginDir } from '../hooks/register'

test('built files of this repo are named; sources and other repos are not', () => {
  expect(guardReason('/repo', '/repo/planner.plugin')).toBeDefined()
  expect(guardReason('/repo/', '/repo/setup/uv.lock')).toBeDefined()
  expect(guardReason('/repo', '/repo/plugins/planner/skills/plan-day/SKILL.md')).toBeUndefined()
  expect(guardReason('/repo', '/repo/planner.plugin.md')).toBeUndefined()
  expect(guardReason('/repo', '/other-project/setup/uv.lock')).toBeUndefined()
  expect(guardReason('/repo', '/repo/setup/../planner.plugin')).toBeDefined()
  expect(guardReason('/repo', '/repo/./setup//uv.lock')).toBeDefined()
  expect(guardReason('/repo', '/repo/../other/planner.plugin')).toBeUndefined()
})

test('normalize resolves . and .. and repeated slashes', () => {
  expect(normalize('/repo/setup/../planner.plugin')).toBe('/repo/planner.plugin')
  expect(normalize('/repo/./a//b/')).toBe('/repo/a/b')
  expect(normalize('/../repo')).toBe('/repo')
})

test('an Edit of planner.plugin is denied', async ($, on) => {
  on('session.root', () => ({ value: '/repo' }))
  on('tool.call', () => ({ deny: 'reached the tool' }))
  const r = await $.tool.call({ tool: 'Edit', file_path: '/repo/planner.plugin', old_string: 'a', new_string: 'b' })
  expect(r.deny).toContain('build output')
})

test('a Write elsewhere goes through', async ($, on) => {
  // The test's hook stands for the tool; reaching it means the guard passed the call on.
  on('session.root', () => ({ value: '/repo' }))
  on('tool.call', () => ({ deny: 'reached the tool' }))
  const r = await $.tool.call({ tool: 'Write', file_path: '/repo/README.md', content: 'x' })
  expect(r.deny).toBe('reached the tool')
})

test('pluginDir finds the plugin folder of a file under <root>/plugins/', () => {
  expect(pluginDir('/repo', '/repo/plugins/tasks/skills/task-note/SKILL.md')).toBe('/repo/plugins/tasks')
  expect(pluginDir('/repo/', '/repo/plugins/planner/.claude-plugin/plugin.json')).toBe('/repo/plugins/planner')
  expect(pluginDir('/repo', '/repo/plugins/README.md')).toBeUndefined()
  expect(pluginDir('/repo', '/repo/CLAUDE.md')).toBeUndefined()
  expect(pluginDir('/repo', '/other/plugins/tasks/x.md')).toBeUndefined()
  expect(pluginDir('/repo', '/repo/setup/../plugins/tasks/x.md')).toBe('/repo/plugins/tasks')
})

test("an Edit of another repo's setup/uv.lock goes through", async ($, on) => {
  on('session.root', () => ({ value: '/repo' }))
  on('tool.call', () => ({ deny: 'reached the tool' }))
  const r = await $.tool.call({ tool: 'Edit', file_path: '/other-project/setup/uv.lock', old_string: 'a', new_string: 'b' })
  expect(r.deny).toBe('reached the tool')
})
