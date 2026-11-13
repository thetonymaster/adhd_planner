# ADHD Planner

Plugins that keep a person's work in an Obsidian vault as task notes, so any Claude session can pick up where the last one stopped.

## Tasks

**Task note**:
One vault note per piece of work, holding its goal, next steps, open loops and log.
_Avoid_: ticket, todo

**Current task**:
The task note a session is working on, resolved from the session's own choice, else the repo, else the last task chosen anywhere. It can be Parked.
_Avoid_: active task, session task

**Next item**:
One concrete step listed under a task note's Next.
_Avoid_: backlog item, subtask

**Next work**:
The open Next items of one task note, scheduled together as one row of a plan.

**Pool**:
The to-dos and task notes' next work a day or week plan is built from.
_Avoid_: backlog

**Priority**:
How soon a task note should be worked on, `p0` (first) to `p5` (someday); a missing value means `p3`.

**Due date**:
A hard limit on when a task note's next work may be placed.

**Open loop**:
An unresolved question or dependency recorded on a task note so it isn't held in the head.

## Status

**Parked**:
A task note's status when nobody is working on it, whether never started or paused.
_Avoid_: todo, paused, inactive

**Doing**:
A task note's status (`active`) while a session is working on it. "Active" names only this status.
_Avoid_: in progress, active task

**Done**:
A task note's status once the whole task is finished.
_Avoid_: closed, complete

**Backlog**:
All Parked task notes.
_Avoid_: using it for Next items

## Hubs

**Hub**:
The note a task note links up to: either a Project or an Area.
_Avoid_: calling every hub a project

**Project**:
A Hub for work that has an end.

**Area**:
A Hub for an ongoing responsibility with no end.
