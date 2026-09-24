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


class GameChangerExceptionTests(unittest.TestCase):
    def test_exception_is_scoped_and_cli_override_still_wins(self):
        for folder, expected in [("Bracket3", 3), ("Bracket3.5", 3),
                                 ("Bracket3.5+4GC", 4), ("Bracket4", None),
                                 ("Bracket5", None), ("Bracket3.5+40GC", 3)]:
            with self.subTest(folder=folder):
                self.assertEqual(gc_cap(Path(folder) / "Test-Deck.txt", None), expected)
        self.assertEqual(gc_cap(Path("Bracket3.5+4GC/Test-Deck.txt"), 3), 3)

    def test_four_pass_but_five_and_land_denial_still_fail(self):
        cards = {n: card(n, True) for n in ["Engine", "Threat A", "Threat B", "Threat C"]}
        cards["Wastes"] = {**card("Wastes"), "type_line": "Basic Land", "cmc": 0}
        entries = [deckfile.Entry(1, n) for n in cards if n != "Wastes"]
        path = Path("Bracket3.5+4GC/Test-Deck.txt")
        deck = deckfile.Deck(path, entries + [deckfile.Entry(96, "Wastes")], [])
        self.assertEqual(check(deck, cards, [], gc_cap(path, None))[0], [])
        self.assertIn("4 Game Changers exceeds cap of 3", check(deck, cards, [], 3)[0])
        for name, gc, expected in [("Threat D", True, "5 Game Changers exceeds cap of 4"),
                                   ("Winter Orb", False, "Winter Orb")]:
            with self.subTest(name=name):
                trial = deckfile.Deck(path, entries + [deckfile.Entry(1, name),
                                                        deckfile.Entry(95, "Wastes")], [])
                errors = check(trial, {**cards, name: card(name, gc)}, [], gc_cap(path, None))[0]
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_private_catalog_uses_the_same_cap(self):
        cards = {n: card(n, True) for n in ["Engine", "Threat A", "Threat B", "Threat C"]}
        cards["Wastes"] = {**card("Wastes"), "type_line": "Basic Land", "cmc": 0}

        class Query:
            def cards(self, names):
                return {name: cards[name] for name in names}, []

        class Mana:
            def pips(self, colours, up):
                return ""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = root / "Bracket3.5+4GC" / "Test-Deck.txt"
            path.parent.mkdir()
            path.write_text("1 Engine\n1 Threat A\n1 Threat B\n1 Threat C\n96 Wastes\n")
            info = build_site.DeckInfo(path, root, Query(), {}, private=True)
            self.assertEqual(info.gc_label, "4/4")
            self.assertEqual(info.label, "Bracket 3.5 + 4 GC")
            page = build_site.render_index(frontend.load(ROOT / "frontend"), [info],
                                           "https://example.test/repo", Mana())
            self.assertIn("GC 4/4", page)
            self.assertIn("Bracket 3.5 + 4 GC", page)
            self.assertIn("private/Bracket3.5+4GC/Test-Deck.html", page)


if __name__ == "__main__":
    unittest.main()
