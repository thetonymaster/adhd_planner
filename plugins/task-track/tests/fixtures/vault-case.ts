/** One shared vault-resolution case. Run by tests/task-track.test.ts and by tests/test_load_task.py. */
export type NoteSpec = { status?: string; repo?: string; mtime?: number }
export type VaultDir = { notes?: Record<string, NoteSpec>; active?: string; session?: { slug: string; mtime?: number } }
export type VaultCase = {
  name: string
  /** vaults.json: an object is written as JSON, a string as raw text, null means no file. */
  config: Record<string, unknown> | string | null
  /** Folders under home that exist with a Tasks/ inside, keyed like "vault" or "work". Session id is always s1. */
  vaults: Record<string, VaultDir>
  cwd: string
  /** vault null: nothing usable. nameLine and skipped are checked by Python only (the mod prints neither).
   *  timezone: the zone read from vaults.json ('' when absent or rejected); warning: why it was rejected. */
  expect: { vault: string | null; slug?: string; reason?: string; error?: string; skipped?: string; nameLine?: string; timezone?: string; warning?: string }
}
