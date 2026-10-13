---
name: handoff
description: Use when finishing a work session, pausing at a gate, or handing work to another session or person. Produces a handoff that lets the next reader resume without re-deriving context.
---

# Handoff

Leave the campsite clean. The next reader may be a person, another session, or
you with none of this context.

## The five sections

**1. State of work.** Done / in progress / untouched. Say which explicitly —
"mostly done" is not a state. If something is done, say it plainly; if a test
fails, say so with the output.

**2. Blockers.** What is stopping progress right now, and what would unblock
it. "Waiting on Q to decide X" is a blocker; name it.

**3. Open questions and competing theories.** Anything unresolved, with the
theories still live. This is what stops the next session re-deriving what you
already ruled out.

**4. Recommendations and why.** What you would do next, with the reasoning. The
reasoning matters more than the recommendation — it is what lets the reader
disagree productively.

**5. Files touched.** Created, modified, deleted. Exact paths.

## Also state

- **Verification status.** What you actually ran, and what it printed. "Tests
  pass" is worth nothing without the command. If you did not run it, say you
  did not run it.
- **Anything unverified.** Assumptions you made, claims you did not check,
  network calls you could not make. Unverified is not the same as false, but it
  is not the same as true either.
- **What you deliberately left out**, and why. Scope you dropped is the reader's
  decision to revisit, and they can only revisit what they know about.

## Tone

Report outcomes faithfully. No hedging on things you verified, no confidence on
things you did not. If part of the work is blocked or problematic, finish
everything else in full and say plainly what you left and why — scaling the work
down is Q's call, not yours.
