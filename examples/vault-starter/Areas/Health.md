---
up: "[[Home]]"
status: active
tags: [area]
---
# Health

## Responsibilities

## Key notes
<!-- routines, appointments, references -->

## Meetings
```base
filters:
  and:
    - file.inFolder("Meetings")
    - file.hasLink(this.file)
views:
  - type: table
    name: Meetings
    order:
      - file.name
      - date
      - start
```

## Tasks
Tasks link here via `up:` — see the backlinks pane, or [[Tasks.base]].
