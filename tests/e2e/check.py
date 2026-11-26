"""Deterministic graders: assert vault state after each e2e case. Usage: check.py <out-dir>"""
import os, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import session_end  # noqa: E402

E2E = pathlib.Path(sys.argv[1])


def state(case):
    root = E2E / f"run-{case}"
    t = root / "vault" / "Tasks"
    rd = lambda p: p.read_text().strip() if p.is_file() else None
    # SessionEnd (park_on_end.py) parks the session's active task when `claude -p` exits. When its
    # line is a note's LAST Log line, that park was the final transition: undo it to see what the
    # skill left behind (run_case.sh already undid turn 1's before the reply).
    ended_last, undo_end = session_end.ended_last, session_end.undo

    def status_of(text):
        return re.search(r"(?m)^status: *(\S*)", (undo_end(text) if ended_last(text) else text)).group(1)
    status = {p.stem: status_of(p.read_text()) for p in t.glob("*.md")}  # for "active" checks
    raw = {p.stem: re.search(r"(?m)^status: *(\S*)", p.read_text()).group(1) for p in t.glob("*.md")}  # for "parked" checks

    def unchanged(n):  # equal, after undoing only the SessionEnd park (active -> parked + its Log line)
        before, after = (root / "Tasks.before" / n).read_text(), (t / n).read_text()
        return before == (undo_end(after) if ended_last(after) else after)
    return dict(status=status, raw=raw, active=rd(t / ".active"), session=rd(t / ".session" / rd(root / "sid")),
                unchanged=unchanged,
                said=(root / "turn1.txt").read_text(),  # assistant's turn-1 output only
                repo_is_work=lambda slug: bool(re.search(r"(?m)^repo: *(\S.*)$", (t / f"{slug}.md").read_text()))
                    and os.path.realpath(os.path.expanduser(re.search(r"(?m)^repo: *(.*)$", (t / f"{slug}.md").read_text()).group(1).strip()))
                    == os.path.realpath(root / "work"),
                repo=lambda slug: re.search(r"(?m)^repo: *(.*)$", (t / f"{slug}.md").read_text()).group(1).strip(),
                # Log lines turn 2 added (diffed against the post-turn-1 snapshot, so turn 1's
                # SessionEnd park can't count), minus turn 2's own SessionEnd line
                turn2_log=lambda n: [l for l in (t / n).read_text().splitlines()
                                     if l.startswith("- [[") and "parked: session ended" not in l
                                     and l not in (root / "Tasks.turn1" / n).read_text().splitlines()],
                # turn 2 left the note as the snapshot had it, apart from turn 2's own SessionEnd park
                turn2_untouched=lambda n: (root / "Tasks.turn1" / n).read_text()
                    == (undo_end((t / n).read_text()) if ended_last((t / n).read_text()) else (t / n).read_text()),
                was_active_after_turn1=lambda n: re.search(r"(?m)^status: *active", (root / "Tasks.turn1" / n).read_text()) is not None,
                parked_by_skill=lambda n: re.search(r"(?m)^status: *parked", (t / n).read_text()) is not None
                    and not ended_last((t / n).read_text()),
                # Log lines added by the skill itself (not the SessionEnd park)
                skill_log=lambda n: [l for l in (t / n).read_text().splitlines()
                                     if l.startswith("- [[") and "parked: session ended" not in l
                                     and l not in (root / "Tasks.before" / n).read_text().splitlines()])


EXPECT = {
    "s-yes": lambda s: [("asked park-or-stop", "Park" in s["said"] and "old-work" in s["said"]),
                        ("old-work active when 'yes' arrived", s["was_active_after_turn1"]("old-work.md")),
                        ("old-work parked by task-park in turn 2 (not SessionEnd)",
                         s["parked_by_skill"]("old-work.md") and bool(s["turn2_log"]("old-work.md"))),
                        ("fix-bug active", s["status"]["fix-bug"] == "active"),
                        (".active=fix-bug", s["active"] == "fix-bug"),
                        (".session=fix-bug", s["session"] == "fix-bug")],
    "s-no": lambda s: [("old-work untouched", s["unchanged"]("old-work.md")),
                       ("turn 2 ('no') wrote nothing to old-work", s["turn2_untouched"]("old-work.md")),
                       ("fix-bug untouched", s["unchanged"]("fix-bug.md")),
                       (".active=old-work", s["active"] == "old-work"),
                       (".session=old-work", s["session"] == "old-work")],
    "g-leave": lambda s: [("fix-bug not bound to repo", s["repo"]("fix-bug") == ""),("asked park-or-leave", "leave it as is" in s["said"].lower()),
                          ("old-work untouched", s["unchanged"]("old-work.md")),
                          (".active=old-work", s["active"] == "old-work"),
                          ("fix-bug active", s["status"]["fix-bug"] == "active"),
                          (".session=fix-bug", s["session"] == "fix-bug")],
    "g-park": lambda s: [("fix-bug bound to this repo", s["repo_is_work"]("fix-bug")),("old-work parked", s["raw"]["old-work"] == "parked"),
                         ("fix-bug active", s["status"]["fix-bug"] == "active"),
                         (".active=fix-bug", s["active"] == "fix-bug"),
                         (".session=fix-bug", s["session"] == "fix-bug")],
    "new": lambda s: [("note created active", s["status"].get("new-thing") == "active"),
                      (".active=new-thing", s["active"] == "new-thing"),
                      (".session=new-thing", s["session"] == "new-thing")],
    "done": lambda s: [("says finished", "finish" in s["said"].lower()),
                       ("fix-bug untouched", s["unchanged"]("fix-bug.md")),
                       ("no .active", s["active"] is None)],
    "sw-done": lambda s: [("says finished", "finish" in s["said"].lower()),
                          ("fix-bug untouched", s["unchanged"]("fix-bug.md")),
                          ("no .active", s["active"] is None)],
    "sw-leave": lambda s: [("fix-bug not bound to repo", s["repo"]("fix-bug") == ""),("asked park-or-leave", "leave it as is" in s["said"].lower()),
                           ("old-work untouched", s["unchanged"]("old-work.md")),
                           (".active=old-work", s["active"] == "old-work"),
                           ("fix-bug active", s["status"]["fix-bug"] == "active"),
                           (".session=fix-bug", s["session"] == "fix-bug")],
}

fails = 0
for case, expect in EXPECT.items():
    for label, ok in expect(state(case)):
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {case:9} {label}")
sys.exit(1 if fails else 0)
