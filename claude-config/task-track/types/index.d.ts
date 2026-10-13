export type NextItem = { text: string; isDone: boolean }

export type TaskView = {
  slug: string
  path: string
  title: string
  up: string
  goal: string
  next: NextItem[]
  openLoops: string[]
  /** The last 5 Log lines, for drawing. */
  log: string[]
  /** How many lines the Log holds, so a new one is noticed after the 5th. */
  logCount: number
  mtimeMs: number
}

/**
 * The shared Pomodoro, as stored in vault/Tasks/.pomo.json: every session reads and writes
 * the same file, so the timer is one timer across sessions, restarts and synced machines.
 */
export type PomoFile = {
  version: 1
  /** The task the running block belongs to. */
  slug: string
  /** Epoch ms the running block started; 0 = between blocks (on a break). */
  blockStartedAt: number
  /** Epoch ms of the last prompt, tool call, press or command in any session. */
  lastActiveAt: number
  /** Epoch ms up to which active time has been added to dayMs (credited once, by any session). */
  creditedUntil: number
  /** Blocks finished today on `slug`. */
  blocksDone: number
  /** Highest block already announced, so only one session notifies. */
  lastNotifiedBlock: number
  /** Session id that announced lastNotifiedBlock. */
  notifiedBy: string
  /** Local date (YYYY-MM-DD) the totals below belong to. */
  day: string
  /** Active ms per task today. */
  dayMs: Record<string, number>
  /** Finished blocks per task today. */
  dayBlocks: Record<string, number>
  /** What of dayMs/dayBlocks is already written to the task Log and daily note. */
  logged: Record<string, { ms: number; blocks: number }>
}

declare module 'claude-code' {
  interface PluginState {
    'task-track': {
      task: TaskView | null
      problem: string
      /** Last read of the shared file, for drawing. */
      pomo: PomoFile
      isBandHidden: boolean
      /** The pane's Open loops section shows every loop, not the first two. */
      isLoopsOpen: boolean
      /** The pane's Log section shows every kept line, wrapped, not three truncated. */
      isLogOpen: boolean
      /** Why the session shows its task, as the pane says it: `this session`, `project: <folder>` or `global`. */
      source: string
    }
  }
}
