"""Catalog-wide owner preference: every Snoop deck includes its full package."""
import unittest
from pathlib import Path

import _paths  # noqa: F401
import deckfile

ROOT = Path(__file__).resolve().parents[1]


class GoblinPackageTests(unittest.TestCase):
    def test_every_snoop_deck_has_the_required_support(self):
        required = {"Kiki-Jiki, Mirror Breaker", "Torch Courier",
                    "Goblin Ringleader", "Mogg Fanatic"}
        checked = []
        for path in deckfile.discover_collection(ROOT / "public"):
            deck = deckfile.parse(path)
            if "Conspicuous Snoop" not in deck.names:
                continue
            checked.append(path)
            with self.subTest(deck=str(path.relative_to(ROOT))):
                self.assertEqual(required - set(deck.names), set(),
                                 "Snoop support package is incomplete")
        self.assertTrue(checked, "No Snoop decks were discovered")


if __name__ == "__main__":
    unittest.main()
