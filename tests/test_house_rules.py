"""The house rules: the only hard rules are the ones a script can check every
time. Below Bracket 4 that is 0-3 Game Changers and no named mass land denial;
two-card combos and extra turns are not deckbuilding restrictions."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site
import deckfile
import frontend
from validate_deck import check, gc_cap


def card(name: str, gc: bool = False) -> dict:
    return {"name": name, "cmc": 1, "type_line": "Artifact",
            "color_identity": [], "legalities": {"commander": "legal"},
            "game_changer": gc}


class HouseRuleTests(unittest.TestCase):
    def test_the_cap_comes_from_the_bracket_folder_and_the_cli_can_override_it(self):
        for folder, expected in [("Bracket3", 3), ("Bracket4", None), ("Bracket5", None)]:
            with self.subTest(folder=folder):
                self.assertEqual(gc_cap(Path(folder) / "Test-Deck.txt", None), expected)
        self.assertEqual(gc_cap(Path("Bracket4/Test-Deck.txt"), 2), 2)

    def deck(self, folder: str, *extra: str):
        cards = {n: card(n, True) for n in ["Engine", "Threat A", "Threat B"]}
        cards["Wastes"] = {**card("Wastes"), "type_line": "Basic Land", "cmc": 0}
        cards.update({n: card(n, n.startswith("GC ")) for n in extra})
        names = [n for n in cards if n != "Wastes"]
        path = Path(folder) / "Test-Deck.txt"
        deck = deckfile.Deck(path, [deckfile.Entry(1, n) for n in names]
                             + [deckfile.Entry(100 - len(names), "Wastes")], [])
        return check(deck, cards, [], gc_cap(path, None))[0]

    def test_three_game_changers_pass_and_a_fourth_fails(self):
        self.assertEqual(self.deck("Bracket3"), [])
        self.assertIn("4 Game Changers exceeds cap of 3", self.deck("Bracket3", "GC Fourth"))

    def test_named_mass_land_denial_fails_below_bracket_4_only(self):
        self.assertTrue(any("Winter Orb" in p for p in self.deck("Bracket3", "Winter Orb")))
        self.assertEqual(self.deck("Bracket4", "Winter Orb"), [])

    def test_two_card_combos_are_not_a_deckbuilding_rule(self):
        # Isochron Scepter + Dramatic Reversal goes infinite; the only expectation
        # is that nobody uses it before turn 6, which no list can show.
        self.assertEqual(self.deck("Bracket3", "Isochron Scepter", "Dramatic Reversal"), [])

    def test_the_catalog_shows_the_same_cap(self):
        cards = {n: card(n, True) for n in ["Engine", "Threat A", "Threat B"]}
        cards["Wastes"] = {**card("Wastes"), "type_line": "Basic Land", "cmc": 0}

        class Query:
            def cards(self, names):
                return {name: cards[name] for name in names}, []

        class Mana:
            def pips(self, colours, up):
                return ""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = root / "alice" / "Bracket3" / "Test-Deck.txt"
            path.parent.mkdir(parents=True)
            path.write_text("1 Engine\n1 Threat A\n1 Threat B\n97 Wastes\n")
            info = build_site.DeckInfo(path, root, Query())
            self.assertEqual(info.gc_label, "3/3")
            page = build_site.render_index(frontend.load(ROOT / "frontend"), [info],
                                           "https://example.test/repo", Mana())
            self.assertIn("GC 3/3", page)
            self.assertIn("Bracket 3", page)


if __name__ == "__main__":
    unittest.main()
