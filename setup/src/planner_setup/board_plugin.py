"""The community Obsidian plugin that renders the task board, and the Tasks.base views that use it.

Kanban Bases View (xiwcx/obsidian-bases-kanban, MIT): registers the Bases view type
`kanban-view`; view options `groupByProperty`, `cardTitleProperty` (default: file name) and
`columnOrders` ({propertyId: [values]}) are read from the view's entry in the .base file.
Dragging a card rewrites the grouped property in the note's frontmatter.
"""

PLUGIN_ID = "kanban-bases-view"
PLUGIN_VERSION = "0.10.6"
PLUGIN_REPO = "xiwcx/obsidian-bases-kanban"
PLUGIN_FILES = ("manifest.json", "main.js", "styles.css")

# 7 days including today, matching /board in task-track.
DONE_WINDOW = 'finished >= today() - "6 days"'

BOARD_VIEW = f"""\
  - type: kanban-view
    name: Board
    filters:
      or:
        - status != "done"
        - {DONE_WINDOW}
    groupByProperty: note.status
    columnOrders:
      note.status:
        - parked
        - active
        - done
    order:
      - up
      - started
"""

DONE_VIEW_NAME = "Done (7 days)"

DONE_VIEW = f"""\
  - type: table
    name: {DONE_VIEW_NAME}
    filters:
      and:
        - status == "done"
        - {DONE_WINDOW}
    order:
      - file.name
      - up
      - finished
    sort:
      - property: finished
        direction: DESC
"""
