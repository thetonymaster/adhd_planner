---
up: "[[Home]]"
status: active
tags: [project]
---
# Northwind

## Why

## Done looks like

## Key notes

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
