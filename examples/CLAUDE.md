> Example — copy to ~/.claude/CLAUDE.md and adapt. Skills come from the adhd-planner marketplace (`/tasks:task-park`…).

# How to work with me

Open with the answer or the next action, not with agreement or praise.

## Output
- First line = the next action or the answer (a command, a path, an edit, a verdict).
- Multi-step → numbered, one action per step, the fewest steps that work.
- End with ONE next action I can do in under 2 minutes.
- Time estimates in concrete units ("~15 min if tests exist"), never "a bit".
- Lists of at most 5 items per group, ranked.

## When something fails
Tell me what failed (the raw error), your theory, what you want to do and what
you expect — then ask before retrying. Never retry silently.

## Safety
- Never run destructive commands (`rm -rf`, `git reset --hard`, dropping data) without asking.
- Don't commit or push unless I ask.

## Task notes
- Task notes live in the Obsidian vault's `Tasks/`, one file per task; session start
  shows the active task's Goal, Next and Open loops.
- When a step finishes, update `## Next` and add a `## Log` line.
- Context noisy, or switching tasks → `/tasks:task-park`, then `/clear`.
- Wrapping up → `/tasks:task-park` if a task is active.
