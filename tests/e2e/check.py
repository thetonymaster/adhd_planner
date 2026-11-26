"""Deterministic graders: assert vault state after each e2e case. Usage: check.py <out-dir>"""
import pathlib, re, sys

E2E = pathlib.Path(sys.argv[1])


def state(case):
    root = E2E / f"run-{case}"
    t = root / "vault" / "Tasks"
    rd = lambda p: p.read_text().strip() if p.is_file() else None
    # SessionEnd (park_on_end.py) parks the session's active task when `claude -p` exits:
    # a note it parked counts as active, and its edits are stripped before comparing.
    END = re.compile(r"(?m)^- \[\[[\d-]+\]\] [\d:]+ — parked: session ended\n?")
    def status_of(text):
        st = re.search(r"(?m)^status: *(\S*)", text).group(1)
        return "active" if st == "parked" and END.search(text) else st
    status = {p.stem: status_of(p.read_text()) for p in t.glob("*.md")}

    def unchanged(n):  # equal, after undoing only the SessionEnd park (active -> parked + its Log line)
        before, after = (root / "Tasks.before" / n).read_text(), (t / n).read_text()
        if END.search(after):
            after = END.sub("", after).replace("status: parked", "status: active", 1)
        return before == after
    return dict(status=status, active=rd(t / ".active"), session=rd(t / ".session" / rd(root / "sid")),
                unchanged=unchanged,
                said=(root / "transcript.txt").read_text(),
                # Log lines added by the skill itself (not the SessionEnd park)
                skill_log=lambda n: [l for l in (t / n).read_text().splitlines()[len((root / "Tasks.before" / n).read_text().splitlines()):]
                                     if l.startswith("- [[") and "parked: session ended" not in l])


EXPECT = {
    "s-yes": lambda s: [("asked park-or-stop", "Park" in s["said"] and "old-work" in s["said"]),
                        ("old-work parked by task-park", bool(s["skill_log"]("old-work.md"))),
                        ("fix-bug active", s["status"]["fix-bug"] == "active"),
                        (".active=fix-bug", s["active"] == "fix-bug"),
                        (".session=fix-bug", s["session"] == "fix-bug")],
    "s-no": lambda s: [("old-work untouched", s["unchanged"]("old-work.md")),
                       ("fix-bug untouched", s["unchanged"]("fix-bug.md")),
                       (".active=old-work", s["active"] == "old-work"),
                       (".session=old-work", s["session"] == "old-work")],
    "g-leave": lambda s: [("asked park-or-leave", "leave it as is" in s["said"].lower()),
                          ("old-work untouched", s["unchanged"]("old-work.md")),
                          (".active=old-work", s["active"] == "old-work"),
                          ("fix-bug active", s["status"]["fix-bug"] == "active"),
                          (".session=fix-bug", s["session"] == "fix-bug")],
    "g-park": lambda s: [("old-work parked", s["status"]["old-work"] == "parked"),
                         ("fix-bug active", s["status"]["fix-bug"] == "active"),
                         (".active=fix-bug", s["active"] == "fix-bug"),
                         (".session=fix-bug", s["session"] == "fix-bug")],
    "new": lambda s: [("note created active", s["status"].get("new-thing") == "active"),
                      (".active=new-thing", s["active"] == "new-thing"),
                      (".session=new-thing", s["session"] == "new-thing")],
    "done": lambda s: [("says finished", "finish" in s["said"].lower()),
                       ("fix-bug untouched", s["unchanged"]("fix-bug.md")),
                       ("no .active", s["active"] is None)],
    "sw-leave": lambda s: [("asked park-or-leave", "leave it as is" in s["said"].lower()),
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
