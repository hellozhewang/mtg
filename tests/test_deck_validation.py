from __future__ import annotations

import copy
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deckfile import Deck, Entry
from validate_deck import average_mana_value, check, land_counts, report


def card(name: str, mana: int, type_line: str, oracle: str = "") -> dict:
    return {
        "name": name, "cmc": mana, "type_line": type_line,
        "oracle_text": oracle, "color_identity": ["B"],
        "legalities": {"commander": "legal"}, "game_changer": False,
    }


class DeckValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cards = {
            "Marrow-Gnawer": card("Marrow-Gnawer", 5, "Legendary Creature — Rat Rogue"),
            "Swamp": card("Swamp", 0, "Basic Land — Swamp"),
            "Sol Ring": card("Sol Ring", 1, "Artifact"),
        }
        for name, mana in (("Rat Colony", 2), ("Relentless Rats", 3)):
            self.cards[name] = card(
                name, mana, "Creature — Rat",
                f"A deck can have any number of cards named {name}.",
            )

    def deck(self, *entries: Entry) -> Deck:
        return Deck(
            ROOT / "private" / "Bracket3.5" / "Validation-Rats.txt",
            [Entry(1, "Marrow-Gnawer"), *entries,
             Entry(99 - sum(e.count for e in entries), "Swamp")],
            [],
        )

    def problems(self, deck: Deck, cards: dict | None = None) -> list[str]:
        used = {n: (cards or self.cards)[n] for n in deck.names}
        return check(deck, used, [], 3)[0]

    def test_unlimited_rat_copies_are_legal(self) -> None:
        for name in ("Rat Colony", "Relentless Rats"):
            with self.subTest(name=name):
                self.assertEqual(self.problems(self.deck(Entry(25, name))), [])

    def test_ordinary_duplicates_still_fail(self) -> None:
        problems = self.problems(self.deck(Entry(25, "Rat Colony"), Entry(2, "Sol Ring")))
        self.assertIn("illegal duplicates: 2x Sol Ring", problems)

    def test_exception_must_name_the_card_itself(self) -> None:
        cards = copy.deepcopy(self.cards)
        cards["Sol Ring"]["oracle_text"] = self.cards["Rat Colony"]["oracle_text"]
        self.assertIn(
            "illegal duplicates: 2x Sol Ring",
            self.problems(self.deck(Entry(2, "Sol Ring")), cards),
        )

    def test_repeat_lines_are_not_a_quantity_line(self) -> None:
        problems = self.problems(self.deck(Entry(12, "Rat Colony"), Entry(13, "Rat Colony")))
        self.assertIn("repeated lines: Rat Colony", problems)

    def test_copy_permission_does_not_override_color_or_legality(self) -> None:
        cards = copy.deepcopy(self.cards)
        cards["Rat Colony"]["color_identity"] = ["U"]
        cards["Rat Colony"]["legalities"]["commander"] = "banned"
        problems = self.problems(self.deck(Entry(25, "Rat Colony")), cards)
        self.assertIn("off-colour: Rat Colony[U]", problems)
        self.assertIn("NOT LEGAL in Commander: Rat Colony [banned]", problems)

    def test_mana_average_weights_copies_and_excludes_lands(self) -> None:
        deck = self.deck(Entry(25, "Rat Colony"))
        self.assertAlmostEqual(average_mana_value(deck, self.cards), 55 / 26)
        output = io.StringIO()
        with redirect_stdout(output):
            report(deck, self.cards, [], {"B"}, [], 3)
        self.assertIn("avg MV 2.12", output.getvalue())

    def test_land_options_exclude_transforming_backs(self) -> None:
        cards = {
            "Swamp": self.cards["Swamp"],
            "Blightstep Pathway": {
                **card("Blightstep Pathway", 0, "Land // Land"),
                "layout": "modal_dfc",
            },
            "Malakir Rebirth": {
                **card("Malakir Rebirth", 1, "Instant // Land"),
                "layout": "modal_dfc",
            },
            "Ojer Axonil, Deepest Might": {
                **card("Ojer Axonil, Deepest Might", 4,
                       "Legendary Creature — God // Land"),
                "layout": "transform",
            },
            "Treasure Map": {
                **card("Treasure Map", 2, "Artifact // Land"),
                "layout": "transform",
            },
        }
        deck = Deck(
            ROOT / "private" / "Bracket3.5" / "Validation-Lands.txt",
            [Entry(1, "Ojer Axonil, Deepest Might"), Entry(2, "Swamp"),
             Entry(1, "Blightstep Pathway"), Entry(1, "Malakir Rebirth"),
             Entry(1, "Treasure Map")],
            [],
        )
        self.assertEqual(land_counts(deck, cards), (3, 1))
        output = io.StringIO()
        with redirect_stdout(output):
            report(deck, cards, [], {"B", "R"}, [], 3)
        self.assertIn("3 lands (+1 MDFC)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
