"""The starter Recurring.md that seeds new vaults turns week and month notes on
without creating any occurrences: it parses to no rules and no warnings.
Run: python3 -m unittest tests.test_recurring_starter
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "planner" / "tools"))
import period_note  # noqa: E402

STARTER = ROOT / "examples" / "vault-starter" / "Recurring.md"


class StarterRecurringTest(unittest.TestCase):
    def test_starter_yields_no_rules_and_no_warnings(self):
        rules, warnings = period_note.parse_recurring(STARTER.read_text(encoding="utf-8"))
        self.assertEqual(rules, [])
        self.assertEqual(warnings, [])

    def test_starter_examples_are_valid_rules_once_unfenced(self):
        # The fenced examples must be real rules, so copying one out of the block works.
        text = STARTER.read_text(encoding="utf-8")
        unfenced = "\n".join(l for l in text.splitlines() if not period_note.is_fence(l))
        rules, warnings = period_note.parse_recurring(unfenced)
        self.assertEqual(warnings, [])
        self.assertEqual(sorted(r.id for r in rules), ["rent", "weekly-review"])


if __name__ == "__main__":
    unittest.main()
