"""Undo park_on_end.py's SessionEnd park, which fires on every `claude -p` exit.

Used by run_case.sh between turns (an interactive session does not end between a question and
its answer) and by check.py when grading. Usage: session_end.py <Tasks dir>  (undoes in place).
"""
import pathlib, re, sys

END_LINE = re.compile(r"^- \[\[[\d-]+\]\] [\d:]+ — parked: session ended$")


def ended_last(text: str) -> bool:
    """The note's last Log line is a SessionEnd park: that park was its final transition."""
    logs = [l for l in text.splitlines() if l.startswith("- [[")]
    return bool(logs) and bool(END_LINE.match(logs[-1]))


def undo(text: str) -> str:
    """Drop the final SessionEnd Log line and restore the status it flipped."""
    lines = text.splitlines(keepends=True)
    i = max(n for n, l in enumerate(lines) if l.startswith("- [["))
    return "".join(lines[:i] + lines[i + 1:]).replace("status: parked", "status: active", 1)


if __name__ == "__main__":
    for note in pathlib.Path(sys.argv[1]).glob("*.md"):
        text = note.read_text()
        if ended_last(text):
            note.write_text(undo(text))
