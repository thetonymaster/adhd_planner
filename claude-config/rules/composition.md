---
paths:
  - "**/*.{go,ts,tsx,js,mjs,py,rs}"
---
<!-- ~/.claude/rules/composition.md — loads only when Claude reads/edits a code file. Full reasoning: /composition -->

# Code quality

- Handle errors explicitly: wrap with context and propagate, or crash. Never swallow, never an empty catch, never a silent fallback.
- No `any` or loose type assertions in TypeScript/JavaScript unless Q asks.
- Modern, idiomatic patterns for the active language.

# Composition

- **IO at the edges.** Reads take a filesystem abstraction, writes take a
  writer. Only the outermost layer touches the real filesystem, the network or
  the clock. Everything beneath is pure and testable in memory.
- **An abstraction needs a second implementation** that exists now, or in a plan
  already committed to. Not one you can imagine.
- **No package-level mutable state.** No singletons, no `init()` registration,
  no hidden globals. Things that need configuring are values you construct.
- **Make ordering a compile error.** If B requires A, B takes A's return type.
  A silently wrong answer is worse than a crash.
- **Accept interfaces, return structs.**
- **Loose coupling:** a unit knows its input type, its output type, and nothing
  about who calls it.

Watch both directions. Under-abstraction couples things that should move
independently; over-abstraction adds ceremony that buys nothing and taxes every
future contributor. Ask which one is actually present.
