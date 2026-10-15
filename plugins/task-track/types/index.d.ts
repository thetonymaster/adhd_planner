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
  /** Epoch ms the break after a finished block ends; until then no block starts. 0 = none. */
  breakUntil: number
  /** The break at breakUntil is the long one (every longBreakEvery-th block). */
  isLongBreak: boolean
  /** Epoch ms the timer was paused; 0 = not paused. Pause freezes a block or a break. */
  pausedAt: number
  /** The user stopped the timer: activity starts no block until /pomo start or the next day. */
  isStopped: boolean
  /** Wall-clock start of the running block (pause does not shift it); 0 = no block. For the break summary. */
  blockOpenedAt: number
  /** Checked Next item titles per task when the block reached it, to tell what got checked during the block. */
  blockSnapshot: Record<string, string[]>
  /** What happened during the block, for the opt-in AI summary (breakSummaryAI). Last 60 entries. */
  blockActivity: string[]
  /** Epoch ms of the user's last prompt, press or command in any session (Claude's tool calls don't count). */
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
      /** Why the session shows its task, as the pane says it: `this session`, `project: <folder>`, `folder <path>`, `default` or `global`. */
      source: string
      /** The session's vault name while 2+ vaults are registered; '' with one, so nothing is prefixed. */
      vaultName: string
      /** Why vaults.json was ignored (shown in the pane); '' when it was used or absent. */
      configError: string
      /** breakUntil of the break this session already reminded the user of on a prompt. */
      toldBreakUntil: number
      /** This session already said that mv onto .pomo.json failed. */
      toldMvFailed: boolean
    }
  }
}
