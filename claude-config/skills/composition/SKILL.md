---
name: composition
description: Use when reaching for an abstraction, designing how components fit together, or reviewing whether an existing abstraction earns its keep. Covers IO at the edges, the second-implementation test, ordering as a compile error, and the symmetric risk of over-abstraction.
---

# Composition

The summary lives in CLAUDE.md. This is the reasoning, the tests to apply, and
worked examples in both directions.

## The one test that decides most cases

**Does a second implementation exist right now, or in a plan already committed
to?**

- Yes → the abstraction is earned. Build it.
- No → it is speculative generality. Write the concrete thing.

"I can imagine a second one" does not count. Neither does "we might need to
swap this later." Both are how ceremony enters a codebase and never leaves.

## IO at the edges

Push every side effect to the outermost layer:

- Reads take a filesystem abstraction (Go: `io/fs.FS`; elsewhere: an injected
  reader). Never a root path string plus direct `os` calls.
- Writes take a writer. The command layer decides where bytes land.
- Time, randomness and the network are injected, not called.

You get three things at once, and the third is the one people forget:

1. A second source works with no code change — a tarball, a remote fetch, an
   archive — because it is the same interface.
2. Tests run against an in-memory filesystem: no disk, no network, no fixtures
   to clean up. The suite passes on a plane.
3. **A security property.** `io/fs.FS` rejects absolute paths and `..`, so
   user-supplied paths cannot escape the tree. That is enforcement, not
   convention.

Read-only abstractions do not cover writes. Decide the write story at the same
time, or the "no direct IO" rule gets quietly broken the first time someone
needs to create a file — and an absolute rule that has to be broken teaches
contributors to ignore the rules.

## Make ordering a compile error

If stage B requires stage A to have run, B should take A's **return type**.

The failure this prevents is specific and nasty: a method that mutates hidden
state, and accessors that return a valid-looking empty answer when it hasn't
run yet.

```go
// Before: compiles, silently returns zero cycles on an unresolved catalog.
cat.Resolve(scope, collector)
cycles := cat.Cycles()

// After: Cycles is on the value Resolve returns, so the wrong order
// does not compile.
g := cat.Resolve(scope, collector)
cycles := g.Cycles()
```

A silently wrong answer is worse than a crash. If a claim like "ordering bugs
are compile errors" appears in a design doc, verify it for the one constraint
that is not obvious — that is exactly where it tends to be false.

## No package-level mutable state

No singletons, no `init()` self-registration, no `sync.Once` hiding
initialisation. Things that need configuring are values you construct and pass.

The cost of a singleton is not style. It is that two configurations cannot
coexist — so a migration where old and new formats must both be readable
becomes impossible without a rewrite — and that the failure path of
initialisation cannot be tested.

An exported slice or map is still mutable by any importer. If the rule matters,
say what is actually true rather than overclaiming.

## The other direction: over-abstraction

Under-abstraction is not the only failure, and it is not always the one you
have. Signals that an abstraction is not paying rent:

- One implementation, and no committed plan for a second.
- Its only consumer is a test that invents its own subject to justify it.
- A registry, factory or plugin layer where a map literal or a switch would do.
- A stated benefit that is not actually delivered — e.g. "adding one requires
  editing no existing file" when adding one requires editing the registry.

When you catch the last case, fix the claim as well as the code. A criterion
that cannot be met teaches contributors either to believe something false about
the codebase, or to break another rule to satisfy it.

**Worked example.** In one review three abstractions survived attack and one
did not. An `fs.FS` seam survived: three implementations already existed in the
same plan. A validator-as-a-value survived: six lines more than a package
function, and it made a real failure path testable. Four small formatter types
survived: four real implementations, clearly better than a sixty-line switch.
The registry *holding* those four types did not: one instance, ever, and its
only consumer was a test written to justify it. Keep the interface, delete the
registry, use a map.

## Checklist

1. Name the second implementation. Cannot? Stop.
2. Does this unit do IO? Push it outward.
3. Is there an ordering constraint? Make it a type.
4. Any hidden global? Make it a constructed value.
5. Does every stated benefit actually hold? Test the claim, not the intention.
