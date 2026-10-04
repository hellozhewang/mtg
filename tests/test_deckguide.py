from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deckguide


class PiecesTests(unittest.TestCase):
    def test_single_card(self):
        self.assertEqual(deckguide.pieces("Sol Ring"), [("", "Sol Ring")])

    def test_combo_keeps_commas_inside_names(self):
        self.assertEqual(
            deckguide.pieces("Kiki-Jiki, Mirror Breaker + Zealous Conscripts"),
            [("", "Kiki-Jiki, Mirror Breaker"), ("+", "Zealous Conscripts")])

    def test_chain_then_combo(self):
        self.assertEqual(
            deckguide.pieces("Goblin Recruiter -> Kiki-Jiki, Mirror Breaker + Conspicuous Snoop"),
            [("", "Goblin Recruiter"), ("->", "Kiki-Jiki, Mirror Breaker"),
             ("+", "Conspicuous Snoop")])

    def test_unicode_arrow_is_normalised(self):
        self.assertEqual(deckguide.pieces("Goblin Matron → Krenko, Mob Boss"),
                         [("", "Goblin Matron"), ("->", "Krenko, Mob Boss")])

    def test_joiner_needs_spaces(self):
        # A name that starts with "+" must not split.
        self.assertEqual(deckguide.pieces("+2 Mace"), [("", "+2 Mace")])


class CardNamesTests(unittest.TestCase):
    def test_combo_rows_contribute_every_card_once(self):
        sections = deckguide.parse(
            "# Combos\n"
            "Kiki-Jiki, Mirror Breaker + Zealous Conscripts :: loop\n"
            "Goblin Matron -> Kiki-Jiki, Mirror Breaker :: find it\n"
            "Prose line with no card.\n")
        self.assertEqual(deckguide.card_names(sections),
                         ["Kiki-Jiki, Mirror Breaker", "Zealous Conscripts", "Goblin Matron"])


if __name__ == "__main__":
    unittest.main()
