"""bot._repaired: a failing deck goes back to the builder before anyone sees it."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

import bot


class RepairTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(bot, "log", return_value=Mock())
        p.start()
        self.addCleanup(p.stop)
        self.first = bot.harness.Turn("Built **AmyRose-Equipment**.", "s1", "out1")

    def run_with(self, problems, answers):
        turns = [bot.harness.Turn(a, "s1", f"fix{i}") for i, a in enumerate(answers)]
        with patch.object(bot, "_deck_problems", side_effect=problems), \
                patch.object(bot, "_turn", side_effect=turns) as turn:
            return bot._repaired(Path("/x"), self.first, "s1", "chan", 0.0), turn

    def test_a_passing_deck_replies_as_is(self):
        result, turn = self.run_with([""], [])
        self.assertIs(result, self.first)
        turn.assert_not_called()

    def test_a_failure_is_sent_back_and_the_fixed_answer_used(self):
        problems = "FAIL  digitalstealth/Bracket3/AmyRose-Equipment.txt\n!! unresolved names: Kellan, the Fae-Clothed"
        result, turn = self.run_with([problems, ""], ["Built **AmyRose-Equipment** (fixed)."])
        prompt = turn.call_args.args[1]
        self.assertIn("Kellan, the Fae-Clothed", prompt)
        self.assertEqual(turn.call_args.args[2], "s1")          # same session
        self.assertEqual(result.answer, "Built **AmyRose-Equipment** (fixed).")
        self.assertIn("out1", result.output)                    # tool log sees every turn
        self.assertNotIn("still fails", result.answer)

    def test_still_failing_after_the_limit_says_so(self):
        bad = "FAIL  x.txt\n!! card count is 99, expected 100"
        result, turn = self.run_with([bad] * (bot.MAX_REPAIRS + 1), ["try"] * bot.MAX_REPAIRS)
        self.assertEqual(turn.call_count, bot.MAX_REPAIRS)
        self.assertIn("still fails the deck check", result.answer)
        self.assertIn("card count is 99", result.answer)


if __name__ == "__main__":
    unittest.main()
