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
```base
filters:
  and:
    - file.inFolder("Tasks")
    - up == this.file.asLink()
    - status != "done"
formulas:
  prio: if(["p0", "p1", "p2", "p3", "p4", "p5"].contains(priority), priority, "p3")
  first: priority == "p0"
  soon: if(due, due <= today() + "7 days", false)
  dueKey: if(formula.soon, due, date("9999-12-31"))
views:
  - type: table
    name: Open tasks
    order: [file.name, formula.prio, due, status]
    sort:
      - {property: formula.first, direction: DESC}
      - {property: formula.soon, direction: DESC}
      - {property: formula.dueKey, direction: ASC}
      - {property: formula.prio, direction: ASC}
```
