---
name: obsidian-vault
description: Rules for reading and writing Q's Obsidian vault at ~/vault — folder placement, templates, frontmatter, wikilink rules that keep the graph accurate, and the Obsidian CLI checks to run after writing. Use before creating, editing, linking, moving or renaming any note in ~/vault, including task notes and daily notes.
---

# Obsidian vault (~/vault)

The vault is the path on the session-start `Vault:` line; without that line, the `default` vault in `~/.config/adhd-planner/vaults.json` (or `$ADHD_PLANNER_VAULTS`) when that file loads; otherwise the plugin's vault path option `${user_config.vaultPath}` (skip it when empty), else `$VAULT`, else `~/vault`, the session-start hook's order. Every `~/vault` path in these skills means that root. With several vaults, read and write only that one; never link across vaults (a `[[link]]` resolves only inside its own vault).

The graph is built only from `[[wikilinks]]` (body and frontmatter). Every link
Claude writes is an edge Q will see. Wrong links = wrong graph.

## Where notes go

| Folder | What | Template |
|---|---|---|
| `00 Inbox/` | Unsorted captures. Only place a note may sit without an `up` link. | — |
| `Daily/` | `YYYY-MM-DD.md`, one per day | `Templates/Daily.md` |
| `Tasks/` | One note per task, kebab-case slug filename. `repo:` binds a task to a repo folder. `.active` holds the last chosen slug; `.session/<id>` a session's own. | `Templates/Task.md` |
| `Projects/` | Hub per project with an end (Northwind, ADHD Planner) | `Templates/Project.md` |
| `Areas/` | Hub per ongoing responsibility with no end (Acme SRE, Health) | `Templates/Project.md` |
| `Notes/` | Evergreen knowledge: concepts, runbooks, decisions, references | `Templates/Note.md` |
| `People/` | One note per person Q works with | `Templates/Person.md` |
| `Meetings/` | One note per meeting, created by the Meetings Plus plugin from the calendar. Set `up:` to the project/area it served; action items that are real work become task notes (`/tasks:task-start`). | `Templates/Meeting.md` |
| `Attachments/` | Images, PDFs | — |

Create notes from the template file: copy its content, then fill the fields.
Don't invent new top-level folders; ask Q.

## Link rules

1. **Links are relationships; tags are categories.** `status`, `type`, `#daily` go in
   frontmatter/tags. Never link to a status or type.
2. **Every note links up once** via the `up:` property (`up: "[[Northwind]]"`).
   Task → project/area. Note → project, area, or a parent note. Person → area.
3. **No unresolved links from Claude.** Before writing `[[X]]`, confirm X exists
   (`ls ~/vault/**/X.md`, or `obsidian search query="X"` for aliases). If it doesn't:
   create it from a template (and give it an `up`), or write plain text. Never guess.
4. **Link the first mention only,** and only things that have or deserve a note.
   Not every noun.
5. **Attendees stay plain text** in meeting notes unless a `People/` note exists for them — no ghost nodes per attendee.
6. **Filenames are unique across the vault.** Links use the shortest form `[[Name]]`.
   Human titles for Projects/Areas/Notes/People; kebab slugs + `aliases:` for Tasks.
7. **Daily ↔ task:** task Log lines start with `[[YYYY-MM-DD]]`; daily Log lines
   reference `[[task-slug]]`.
8. **Never move or rename with `mv`.** Use the CLI (from the vault root) so links update:
   `obsidian rename file=X name=Y`, `obsidian move file=X to=Folder`.
9. **Never delete lines** in Log / Open loops sections; strike through `~~text~~` and say why.

## After writing — verify (Obsidian CLI, needs the app; the first call launches it)

The CLI acts on the vault the shell is in, else on whichever vault Obsidian last had
active, which can be a different one. So every CLI call runs from the vault root:
`cd "<vault root>" && obsidian ...`. Never call it from a repo or other folder.

```bash
cd "<vault root>" && obsidian unresolved verbose format=json   # must not contain links Claude wrote
cd "<vault root>" && obsidian deadends                          # notes with no outgoing links; only Inbox may appear
cd "<vault root>" && obsidian backlinks file="<note>"           # check a hub picked up the new note
```

Report what the check returned: `VERIFY: unresolved=0, deadends=Inbox only`.
If the CLI is unavailable, say so and fall back to `grep -o '\[\[[^]]*\]\]'` + `ls`.

## Reading

- Find by meaning: `cd "<vault root>" && obsidian search query="..." format=json limit=10`.
- Find relationships: same `cd` first, then `obsidian backlinks file=X`, `obsidian links file=X`.
- Read only the sections needed; don't load whole hubs into context.
