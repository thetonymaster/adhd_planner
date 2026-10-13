---
name: investigation
description: Use when you do not understand something and are tempted to start changing code to find out. Structures the inquiry into facts, competing theories and tests, so debugging produces knowledge instead of thrash.
---

# Investigation

Reach for this the moment you notice you are guessing.

## Set it up

Create `investigations/<topic>.md`. Writing it down is the point: your context
degrades, and an investigation you cannot reconstruct restarts from zero.

```markdown
# <topic>

## FACTS — verified, with evidence
- [what you observed, and the command or log line that shows it]

## THEORIES — plausible, unverified
1. ...
2. ...
3. ...
4. ...
5. ...

## TESTS
### [what you are testing]
- Why: which theories this distinguishes
- Found: the actual output
- Means: which theories survive, which are dead
```

## Rules

**Separate FACTS from THEORIES ruthlessly.** A fact has evidence attached. If
you cannot point at the log line, it is a theory. "Probably" belongs in the
theory section.

**Maintain 5+ competing theories.** One theory is not an investigation, it is a
commitment. The discipline of writing a fifth forces you past the obvious
candidates, and the real cause is often there.

**Design each test to kill theories, not to confirm one.** A test that can only
confirm what you already believe tells you nothing. Ask: which theories does
this distinguish? If the answer is "none", pick a different test.

**Always include a control.** A method that reports the answer you expect on
the input you are studying, but also reports it on an input you *know* differs,
is broken. Two examples worth internalising: a lookup tool that reported every
domain as registered because it never followed a referral, and a second that
reported `google.com` as available because the endpoint 404s for everything.
Both were caught only by checking a known-good and a known-bad case.

**When two methods disagree, stop.** Do not average them and do not pick the
convenient one. One of them is wrong and finding out which *is* the
investigation.

## Exit

You are done when the FACTS section alone explains the behaviour, and you can
state which theory survived and why the others are dead. Then, before fixing:
ask why five times. "Why did this break?" is the wrong question. **"Why was
this breakable?"** is the right one.
