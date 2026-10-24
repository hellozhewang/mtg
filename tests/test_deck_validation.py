from __future__ import annotations

import copy
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

from deckfile import Deck, Entry
from validate_deck import average_mana_value, check, commanders, land_counts, partners, report


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
            ROOT / "public" / "x" / "Bracket3" / "Validation-Rats.txt",
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
            ROOT / "public" / "x" / "Bracket3" / "Validation-Lands.txt",
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


def legend(name: str, oracle: str, colours: str, kind: str = "Creature — Human") -> dict:
    return {**card(name, 3, f"Legendary {kind}", oracle), "color_identity": list(colours)}


TYMNA = legend("Tymna the Weaver", "Lifelink\nPartner (You can have two commanders if both have partner.)", "WB")
THRASIOS = legend("Thrasios, Triton Hero", "{4}: Scry 1.\nPartner", "GU")
PIR = legend("Pir, Imaginative Rascal", "Partner with Toothy, Imaginary Friend (When this creature enters, ...)", "G")
TOOTHY = legend("Toothy, Imaginary Friend", "Partner with Pir, Imaginative Rascal (When this creature enters, ...)", "U")
CECILY = legend("Cecily, Haunted Mage", "Partner—Friends forever (You can have two commanders if both have this ability.)", "UBR")
ELMAR = legend("Elmar, Ulvenwald Informant", "Partner—Friends forever (You can have two commanders ...)", "G")
KRATOS = legend("Kratos, Stoic Father", "Partner—Father & son (You can have two commanders if both have this ability.)", "R")
WILSON = legend("Wilson, Refined Grizzly", "Choose a Background (You can have a Background as a second commander.)", "G")
GIANTS = legend("Raised by Giants", "Commander creatures you own have base power and toughness 10/10 ...", "G",
                kind="Enchantment — Background")
ROSE = legend("Rose Tyler", "Doctor's companion (You can have two commanders if the other is the Doctor.)", "W")
DOCTOR = legend("The Fourteenth Doctor", "When you cast this spell, ...", "R", kind="Creature — Time Lord Doctor")
# Mentions partner, but only as a keyword it rewards: not a partner itself.
AKROMA_LIKE = legend("Akroma-ish", "Flying\nEach other creature you control gets +1/+1 if it has partner.", "W")


class PartnerTests(unittest.TestCase):
    def test_legal_pairs(self):
        for a, b in [(TYMNA, THRASIOS), (PIR, TOOTHY), (CECILY, ELMAR),
                     (WILSON, GIANTS), (ROSE, DOCTOR)]:
            with self.subTest(a=a["name"], b=b["name"]):
                self.assertTrue(partners(a, b))
                self.assertTrue(partners(b, a))

    def test_illegal_pairs(self):
        for a, b in [(TYMNA, PIR),               # plain Partner and "Partner with" do not mix
                     (PIR, THRASIOS),            # Pir pairs with Toothy and nothing else
                     (CECILY, KRATOS),           # different "Partner—" qualities
                     (TYMNA, CECILY),            # plain Partner vs a quality
                     (WILSON, TYMNA),            # Choose a Background needs a Background
                     (ROSE, TYMNA),              # Doctor's companion needs a Doctor
                     (AKROMA_LIKE, TYMNA)]:      # mentioning partner is not having it
            with self.subTest(a=a["name"], b=b["name"]):
                self.assertFalse(partners(a, b))

    def deck(self, *names: str) -> Deck:
        filler = 100 - len(names)
        return Deck(ROOT / "public" / "x" / "Bracket3" / "Pair-Deck.txt",
                    [Entry(1, n) for n in names] + [Entry(filler, "Swamp")], [])

    def cards(self, *pool: dict) -> dict:
        return {c["name"]: c for c in pool} | {"Swamp": {**card("Swamp", 0, "Basic Land — Swamp"),
                                                        "color_identity": []}}

    def test_line_two_is_a_commander_only_when_it_partners_line_one(self):
        self.assertEqual(commanders(self.deck("Tymna the Weaver", "Thrasios, Triton Hero"),
                                    self.cards(TYMNA, THRASIOS)),
                         ["Tymna the Weaver", "Thrasios, Triton Hero"])
        self.assertEqual(commanders(self.deck("Tymna the Weaver", "Pir, Imaginative Rascal"),
                                    self.cards(TYMNA, PIR)), ["Tymna the Weaver"])

    def test_a_pair_shares_its_colour_identity(self):
        deck = self.deck("Tymna the Weaver", "Thrasios, Triton Hero")
        problems, identity, _ = check(deck, self.cards(TYMNA, THRASIOS), [], 3)
        self.assertEqual(identity, {"W", "U", "B", "G"})
        self.assertEqual(problems, [])

    def test_a_partner_left_among_the_98_gets_a_hint(self):
        # Alphabetised in with the rest, as these decks were before 2026-10-18.
        deck = Deck(ROOT / "public" / "x" / "Bracket3" / "Pair-Deck.txt",
                    [Entry(1, "Tymna the Weaver"), Entry(98, "Swamp"),
                     Entry(1, "Thrasios, Triton Hero")], [])
        problems, identity, _ = check(deck, self.cards(TYMNA, THRASIOS), [], 3)
        self.assertEqual(identity, {"W", "B"})
        self.assertIn("Thrasios, Triton Hero can partner Tymna the Weaver: if it is the "
                      "second commander, put it on line 2", problems)


class PartnerCatalogTests(unittest.TestCase):
    def test_both_commanders_head_the_page_with_their_shared_colours(self):
        import tempfile
        import build_site
        pool = {c["name"]: c for c in (TYMNA, THRASIOS)}
        pool["Swamp"] = {**card("Swamp", 0, "Basic Land — Swamp"), "color_identity": []}

        class Query:
            def cards(self, names):
                return {n: pool[n] for n in names}, []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = root / "alice" / "Bracket3" / "TymnaThrasios-Value.txt"
            path.parent.mkdir(parents=True)
            path.write_text("1 Tymna the Weaver\n1 Thrasios, Triton Hero\n98 Swamp\n")
            info = build_site.DeckInfo(path, root, Query())
        self.assertEqual(info.commander, "Tymna the Weaver & Thrasios, Triton Hero")
        self.assertEqual(info.colours, ["W", "U", "B", "G"])
        commander_rows = dict(info.sections())["Commander"]
        self.assertEqual(sorted(name for _, name, _ in commander_rows),
                         ["Thrasios, Triton Hero", "Tymna the Weaver"])


if __name__ == "__main__":
    unittest.main()
