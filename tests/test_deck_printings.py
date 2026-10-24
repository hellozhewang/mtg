from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _paths  # noqa: E402,F401  (scripts/<area>/ on sys.path)

import build_site
import deckfile
import ttsimport
import validate_deck
from deckfile import Deck, Entry, Printing

SOL, VAULT, CRYPT = "id-sol-sld-249", "id-vault", "id-crypt"
CARDS = {
    "Sol Ring": {"name": "Sol Ring", "oracle_id": "o-sol"},
    "Mana Vault": {"name": "Mana Vault", "oracle_id": "o-vault"},
    "Malakir Rebirth": {"name": "Malakir Rebirth // Malakir Mire", "oracle_id": "o-malakir"},
}


def face(scryfall_id: str) -> dict:
    return {"FaceURL": f"https://img.example/display/front/a/b/{scryfall_id}.webp"}


def importer_reply(*cards: tuple[str, str], extra: list[dict] | None = None) -> str:
    """The backend's ndjson for a deck: one sheet per card, then any extra lines."""
    deck = {
        "Name": "DeckCustom", "Nickname": "Deck",
        "CustomDeck": {str(i + 1): face(sid) for i, (_, sid) in enumerate(cards)},
        "ContainedObjects": [{"Name": "Card", "CardID": (i + 1) * 100,
                              "Nickname": f"{name}\nArtifact 1CMC"}
                             for i, (name, _) in enumerate(cards)],
    }
    return "\n".join(json.dumps(o) for o in [deck, *(extra or [])]) + "\n"


class ParseTests(unittest.TestCase):
    def test_printing_suffix_is_split_from_the_name(self):
        cases = {
            "Sol Ring (SLD) 249": ("Sol Ring", Printing("SLD", "249")),
            "Sol Ring (cmm)": ("Sol Ring", Printing("CMM", None)),
            "Mana Vault (SLD) 796★": ("Mana Vault", Printing("SLD", "796★")),
            "Black Cat, Cunning Thief (SPM) 52": ("Black Cat, Cunning Thief", Printing("SPM", "52")),
            "Sol Ring": ("Sol Ring", None),
            "Wear // Tear": ("Wear // Tear", None),
            # Not a set code: too short, so the parentheses stay part of the name.
            "Erase (X)": ("Erase (X)", None),
        }
        for text, expected in cases.items():
            self.assertEqual(deckfile.split_printing(text), expected, text)

    def test_names_stay_clean_and_the_file_keeps_its_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Test-Deck.txt"
            path.write_text("1 Marchesa, the Black Rose (2X2) 248\n1 Sol Ring (SLD) 249\n98 Swamp\n")
            deck = deckfile.parse(path)
        self.assertEqual(deck.names, ["Marchesa, the Black Rose", "Sol Ring", "Swamp"])
        self.assertEqual(deck.commander, "Marchesa, the Black Rose")
        self.assertEqual(deck.total, 100)
        self.assertEqual(deck.printings, {"Marchesa, the Black Rose": Printing("2X2", "248"),
                                          "Sol Ring": Printing("SLD", "249")})
        self.assertEqual(Entry(1, "Sol Ring"), Entry(1, "Sol Ring", None))
        self.assertEqual(str(Printing("SLD", "249")), "(SLD) 249")


class ImporterReplyTests(unittest.TestCase):
    def test_counts_cards_and_reads_each_printing(self):
        tokens = {"Name": "DeckCustom", "Nickname": "Tokens", "CustomDeck": {"9": face("tok")},
                  "ContainedObjects": [{"Name": "Card", "CardID": 900, "Nickname": "Bird\nToken"}]}
        result = ttsimport.parse(importer_reply(
            ("Sol Ring", SOL), ("Malakir Rebirth // Malakir Mire", "id-malakir"), extra=[tokens]))
        self.assertEqual((result.count, result.tokens, result.errors), (2, 1, []))
        self.assertEqual(result.printing_of("Sol Ring"), [SOL])
        # The decklist names a double-faced card by its front face only.
        self.assertEqual(result.printing_of("Malakir Rebirth"), ["id-malakir"])
        self.assertEqual(result.printing_of("Not There"), [])

    def test_a_lone_token_is_a_loose_card_and_not_part_of_the_deck(self):
        # Measured: a deck that makes exactly one token gets it back as a bare
        # Card after the pile, which once read as "101 of 100 cards".
        token = {"Name": "Card", "CardID": 900, "CustomDeck": {"9": face("tok")},
                 "Nickname": "Warrior\nToken Creature — Warrior 0CMC"}
        result = ttsimport.parse(importer_reply(("Sol Ring", SOL), ("Mana Vault", VAULT), extra=[token]))
        self.assertEqual((result.count, result.tokens), (2, 1))
        self.assertNotIn("Warrior", result.faces)

    def test_an_empty_pile_is_not_a_card(self):
        self.assertEqual(ttsimport.parse(importer_reply()).count, 0)

    def test_error_lines_and_a_single_bare_card(self):
        card = {"Name": "Card", "CardID": 100, "Nickname": "Sol Ring\nArtifact 1CMC",
                "CustomDeck": {"1": face(SOL)}}
        text = json.dumps(card) + '\n{"error":"failed to find card \\"Sol Rnig\\""}\n'
        result = ttsimport.parse(text)
        self.assertEqual(result.count, 1)
        self.assertEqual(result.printing_of("Sol Ring"), [SOL])
        self.assertEqual(result.errors, ['failed to find card "Sol Rnig"'])


class FakeQuery:
    """Stands in for CardQuery: knows two printings and one set."""

    PRINTS = {
        ("SLD", "249"): {"id": SOL, "name": "Sol Ring", "oracle_ids": ["o-sol"]},
        ("2XM", "270"): {"id": CRYPT, "name": "Mana Crypt", "oracle_ids": ["o-crypt"]},
    }

    def __init__(self):
        self.api = self
        self.searches = []

    def printings(self, pairs):
        return {pair: self.PRINTS.get(pair) for pair in pairs}

    def search(self, query, unique="cards", limit=None):
        self.searches.append(query)
        return ([{"name": "Sol Ring"}] if "set:cmm" in query else []), 0


def deck_of(*entries: Entry) -> Deck:
    return Deck(Path("Bracket3/Test-Deck.txt"), list(entries), [])


class PinnedPrintingTests(unittest.TestCase):
    def test_a_real_printing_of_the_right_card_passes_and_yields_its_id(self):
        problems, ids = validate_deck.printing_problems(
            deck_of(Entry(1, "Sol Ring", Printing("SLD", "249")), Entry(1, "Mana Vault")),
            CARDS, FakeQuery())
        self.assertEqual((problems, ids), ([], {"Sol Ring": SOL}))

    def test_unknown_and_wrong_card_printings_are_errors(self):
        problems, ids = validate_deck.printing_problems(
            deck_of(Entry(1, "Sol Ring", Printing("CMM", "99999")),
                    Entry(1, "Mana Vault", Printing("2XM", "270"))),
            CARDS, FakeQuery())
        self.assertEqual(problems, [
            "unknown printing: Sol Ring (CMM) 99999",
            "printing is a different card: Mana Vault (2XM) 270 is Mana Crypt"])
        self.assertEqual(ids, {})

    def test_set_only_pins_are_checked_against_the_set(self):
        q = FakeQuery()
        problems, ids = validate_deck.printing_problems(
            deck_of(Entry(1, "Sol Ring", Printing("CMM", None)),
                    Entry(1, "Malakir Rebirth", Printing("ZZZ", None))),
            CARDS, q)
        self.assertEqual(problems, ["unknown printing: Malakir Rebirth (ZZZ)"])
        self.assertEqual(ids, {})
        self.assertEqual(q.searches, ['!"Sol Ring" set:cmm', '!"Malakir Rebirth" set:zzz'])


class ImportCheckTests(unittest.TestCase):
    DECK = deck_of(Entry(1, "Sol Ring", Printing("SLD", "249")), Entry(1, "Mana Vault"))

    def run_check(self, reply=None, error=None, pinned=None):
        side = {"side_effect": error} if error else {"return_value": ttsimport.parse(reply)}
        with mock.patch.object(ttsimport, "check", **side):
            return validate_deck.import_check(
                self.DECK, "ignored", {"Sol Ring": SOL} if pinned is None else pinned)

    def test_whole_deck_with_the_pinned_art(self):
        problems, note = self.run_check(importer_reply(("Sol Ring", SOL), ("Mana Vault", VAULT)))
        self.assertEqual(problems, [])
        self.assertEqual(note, "TTS import 2/2 cards, 1/1 pinned printings load")

    def test_a_silently_swapped_printing_is_a_problem(self):
        problems, note = self.run_check(importer_reply(("Sol Ring", "other-art"), ("Mana Vault", VAULT)))
        self.assertEqual(problems, ["TTS importer loads a different printing for: Sol Ring"])
        self.assertEqual(note, "TTS import 2/2 cards, 0/1 pinned printings load")

    def test_missing_cards_and_importer_errors(self):
        problems, _ = self.run_check(importer_reply(("Sol Ring", SOL)), pinned={})
        self.assertEqual(problems, ["TTS importer returned 1 of 2 cards"])
        reply = importer_reply(("Sol Ring", SOL), extra=[{"error": 'failed to find card "Mana Vualt"'}])
        problems, _ = self.run_check(reply, pinned={})
        self.assertEqual(problems, ['TTS importer: failed to find card "Mana Vualt"'])

    def test_an_unreachable_importer_is_a_note_not_a_failure(self):
        problems, note = self.run_check(error=ttsimport.ImporterUnavailable("timed out"))
        self.assertEqual(problems, [])
        self.assertEqual(note, "TTS import not checked: importer unavailable (timed out)")


class FakeImporter:
    """Answers `ttsimport.fetch` from a table of what each card loads as, and
    records exactly which lines it was asked about."""

    def __init__(self, loads: dict[str, str], unknown: tuple[str, ...] = ()):
        self.loads, self.unknown, self.asked = loads, unknown, []

    def __call__(self, text: str) -> ttsimport.Result:
        lines = [l for l in text.splitlines() if l.strip()]
        self.asked.append(lines)
        cards, errors = [], []
        for line in lines:
            qty, rest = line.split(" ", 1)
            name, _pin = deckfile.split_printing(rest)
            if name in self.unknown:
                errors.append({"error": f'failed to find card "{rest}"'})
            else:
                cards += [(name, self.loads[rest])] * int(qty)
        if not cards:                                    # nothing loaded: only the complaints
            return ttsimport.parse("\n".join(json.dumps(e) for e in errors))
        return ttsimport.parse(importer_reply(*cards, extra=errors))


class CardCacheTests(unittest.TestCase):
    """The importer is asked only about lines not known to load."""

    DECK = "1 Sol Ring (SLD) 249\n1 Mana Vault\n3 Swamp\n"
    LOADS = {"Sol Ring (SLD) 249": SOL, "Mana Vault": VAULT, "Swamp": "id-swamp",
             "Sol Ring": "id-sol-default", "Mox Opal": "id-opal", "Sol Ring (CMM) 410": "id-sol-cmm"}
    EXPECT = {"Sol Ring": SOL}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "cards.json"
        for patch in (mock.patch.object(ttsimport, "_cache_path", return_value=path),
                      mock.patch.object(ttsimport, "POLITE_DELAY", 0)):
            patch.start()
            self.addCleanup(patch.stop)

    def importer(self, **kw) -> FakeImporter:
        fake = FakeImporter(self.LOADS, **kw)
        patch = mock.patch.object(ttsimport, "fetch", fake)
        patch.start()
        self.addCleanup(patch.stop)
        return fake

    def test_an_unchanged_deck_is_not_sent_again(self):
        fake = self.importer()
        first = ttsimport.check(self.DECK, expect=self.EXPECT)
        self.assertEqual((first.count, first.sent, first.cached), (5, 5, False))
        again = ttsimport.check(self.DECK, expect=self.EXPECT)
        self.assertEqual(len(fake.asked), 1)
        self.assertEqual((again.count, again.sent, again.cached, again.errors), (5, 0, True, []))
        # The remembered answer still says which printing each card is.
        self.assertEqual(again.printing_of("Sol Ring"), [SOL])
        self.assertEqual(again.printing_of("Swamp"), ["id-swamp"] * 3)

    def test_only_the_changed_line_is_asked_about(self):
        fake = self.importer()
        ttsimport.check(self.DECK, expect=self.EXPECT)
        result = ttsimport.check(self.DECK.replace("1 Mana Vault", "1 Mox Opal"), expect=self.EXPECT)
        self.assertEqual(fake.asked[1], ["1 Mox Opal"])
        self.assertEqual((result.count, result.sent, result.cached), (5, 1, False))

    def test_a_different_pin_on_a_known_card_is_a_new_question(self):
        fake = self.importer()
        ttsimport.check(self.DECK, expect=self.EXPECT)
        ttsimport.check(self.DECK.replace("(SLD) 249", "(CMM) 410"), expect={"Sol Ring": "id-sol-cmm"})
        self.assertEqual(fake.asked[1], ["1 Sol Ring (CMM) 410"])

    def test_a_pin_is_learned_only_when_it_loaded_as_the_expected_printing(self):
        fake = self.importer()
        ttsimport.check(self.DECK)                               # nobody said which printing is right
        ttsimport.check(self.DECK, expect={"Sol Ring": "other"})  # the importer returned a different one
        ttsimport.check(self.DECK, expect=self.EXPECT)            # verified: remembered from here on
        ttsimport.check(self.DECK, expect=self.EXPECT)
        self.assertEqual(fake.asked, [["1 Sol Ring (SLD) 249", "1 Mana Vault", "3 Swamp"],
                                      ["1 Sol Ring (SLD) 249"], ["1 Sol Ring (SLD) 249"]])
        # A remembered pin is not trusted for a different expected printing.
        ttsimport.check(self.DECK, expect={"Sol Ring": "other"})
        self.assertEqual(fake.asked[-1], ["1 Sol Ring (SLD) 249"])

    def test_lines_that_fail_are_asked_again_and_the_rest_remembered(self):
        fake = self.importer(unknown=("Mana Vault",))
        first = ttsimport.check(self.DECK, expect=self.EXPECT)
        self.assertEqual((first.count, first.errors), (4, ['failed to find card "Mana Vault"']))
        second = ttsimport.check(self.DECK, expect=self.EXPECT)
        self.assertEqual(fake.asked[1], ["1 Mana Vault"])
        self.assertEqual((second.count, second.errors), (4, ['failed to find card "Mana Vault"']))

    def test_remembered_lines_expire_and_refresh_asks_everything(self):
        fake = self.importer()
        ttsimport.check(self.DECK, expect=self.EXPECT)
        later = ttsimport.time.time() + (ttsimport.CACHE_DAYS + 1) * 86400
        with mock.patch.object(ttsimport.time, "time", return_value=later):
            ttsimport.check(self.DECK, expect=self.EXPECT)
        self.assertEqual(len(fake.asked[1]), 3)
        ttsimport.check(self.DECK, expect=self.EXPECT, refresh=True)
        self.assertEqual(len(fake.asked[2]), 3)

    def test_a_known_deck_validates_while_the_importer_is_down(self):
        self.importer()
        ttsimport.check(self.DECK, expect=self.EXPECT)
        down = mock.patch.object(ttsimport, "fetch", side_effect=ttsimport.ImporterUnavailable("timed out"))
        down.start()
        self.addCleanup(down.stop)
        self.assertEqual(ttsimport.check(self.DECK, expect=self.EXPECT).count, 5)
        with self.assertRaises(ttsimport.ImporterUnavailable):
            ttsimport.check(self.DECK + "1 Mox Opal\n", expect=self.EXPECT)

    def test_the_validator_note_says_how_much_was_asked(self):
        self.importer()
        deck = deck_of(Entry(1, "Sol Ring", Printing("SLD", "249")), Entry(1, "Mana Vault"), Entry(3, "Swamp"))
        _, note = validate_deck.import_check(deck, self.DECK, self.EXPECT)
        self.assertEqual(note, "TTS import 5/5 cards, 1/1 pinned printings load")
        _, note = validate_deck.import_check(deck, self.DECK, self.EXPECT)
        self.assertEqual(note, "TTS import 5/5 cards, 1/1 pinned printings load (all known good, importer not asked)")
        changed = deck_of(Entry(1, "Sol Ring", Printing("SLD", "249")), Entry(1, "Mox Opal"), Entry(3, "Swamp"))
        _, note = validate_deck.import_check(changed, self.DECK.replace("Mana Vault", "Mox Opal"), self.EXPECT)
        self.assertEqual(note, "TTS import 5/5 cards, 1/1 pinned printings load (asked the importer about 1)")


def uris(tag: str) -> dict:
    return {"thumb": f"https://img.example/thumb/{tag}.webp",
            "normal": f"https://img.example/normal/{tag}.jpg"}


class ArtQuery:
    """Stands in for CardQuery.printings with pictures attached."""

    def __init__(self, prints=None, error=None):
        self.prints, self.error = prints or {}, error

    def printings(self, pairs):
        if self.error:
            raise self.error
        return {pair: self.prints.get(pair) for pair in pairs}


class PinnedArtTests(unittest.TestCase):
    SOL_DEFAULT = {"name": "Sol Ring", "oracle_id": "o-sol", "id": "id-default",
                   "mana_cost": "{1}", "image_uris": uris("default")}
    REBIRTH = {"name": "Malakir Rebirth // Malakir Mire", "oracle_id": "o-malakir",
               "card_faces": [{"name": "Malakir Rebirth", "mana_cost": "{B}", "image_uris": uris("f0")},
                              {"name": "Malakir Mire", "image_uris": uris("b0")}]}
    PRINTS = {
        ("SLD", "249"): {"id": SOL, "oracle_ids": ["o-sol"], "image_uris": uris("gold"),
                         "face_images": []},
        ("ZNR", "111"): {"id": "id-znr", "oracle_ids": ["o-malakir"], "image_uris": None,
                         "face_images": [uris("f1"), uris("b1")]},
        ("2XM", "270"): {"id": CRYPT, "oracle_ids": ["o-crypt"], "image_uris": uris("crypt"),
                         "face_images": []},
    }

    def cards(self):
        return {"Sol Ring": self.SOL_DEFAULT, "Malakir Rebirth": self.REBIRTH}

    def test_pinned_cards_show_that_printing_and_keep_their_rules(self):
        deck = deck_of(Entry(1, "Sol Ring", Printing("SLD", "249")),
                       Entry(1, "Malakir Rebirth", Printing("ZNR", "111")))
        cards = self.cards()
        shown = build_site.pinned_art(deck, cards, ArtQuery(self.PRINTS))
        sol = shown["Sol Ring"]
        self.assertEqual(sol["image_uris"], uris("gold"))
        self.assertEqual((sol["mana_cost"], sol["oracle_id"]), ("{1}", "o-sol"))
        # Filed under the printing, so it cannot overwrite the default thumbnail
        # that every other deck's Sol Ring uses.
        self.assertEqual(build_site.image_file(sol, 0, "thumb", sol["image_uris"]["thumb"]),
                         f"{SOL}-front-thumb.webp")
        self.assertEqual(build_site.image_file(self.SOL_DEFAULT, 0, "thumb", "x.webp"),
                         "o-sol-front-thumb.webp")
        faces = shown["Malakir Rebirth"]["card_faces"]
        self.assertEqual([f["image_uris"] for f in faces], [uris("f1"), uris("b1")])
        self.assertEqual(faces[0]["mana_cost"], "{B}")
        # The shared objects other decks render were not modified.
        self.assertEqual(cards["Sol Ring"]["image_uris"], uris("default"))
        self.assertEqual(self.REBIRTH["card_faces"][0]["image_uris"], uris("f0"))

    def test_a_pin_that_is_already_the_default_printing_changes_nothing(self):
        # Measured on the first build: 17 of 52 pins were the printing the site
        # already showed, and each page pointed at a thumbnail nobody wrote.
        cards = {"Sol Ring": {**self.SOL_DEFAULT, "id": SOL}}
        deck = deck_of(Entry(1, "Sol Ring", Printing("SLD", "249")))
        shown = build_site.pinned_art(deck, cards, ArtQuery(self.PRINTS))
        self.assertIs(shown["Sol Ring"], cards["Sol Ring"])
        self.assertEqual(build_site.image_file(shown["Sol Ring"], 0, "thumb", "x.webp"),
                         "o-sol-front-thumb.webp")

    def test_bad_pins_and_an_unreachable_scryfall_fall_back_to_default_art(self):
        cards = self.cards()
        wrong = deck_of(Entry(1, "Sol Ring", Printing("2XM", "270")),        # Mana Crypt
                        Entry(1, "Malakir Rebirth", Printing("ZNR", "999")))  # no such number
        self.assertEqual(build_site.pinned_art(wrong, cards, ArtQuery(self.PRINTS)), cards)
        set_only = deck_of(Entry(1, "Sol Ring", Printing("CMM", None)))
        self.assertIs(build_site.pinned_art(set_only, cards, ArtQuery(self.PRINTS)), cards)
        pinned = deck_of(Entry(1, "Sol Ring", Printing("SLD", "249")))
        down = ArtQuery(error=build_site.ScryfallError("HTTP 503"))
        with mock.patch("sys.stderr"):
            self.assertIs(build_site.pinned_art(pinned, cards, down), cards)


if __name__ == "__main__":
    unittest.main()
