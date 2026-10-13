from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cardlib import CardQuery

KNOWN = {
    "wear": {"name": "Wear // Tear", "oracle_id": "o-wear"},
    "unholy annex": {"name": "Unholy Annex // Ritual Chamber", "oracle_id": "o-annex"},
    "sol ring": {"name": "Sol Ring", "oracle_id": "o-sol"},
}


class BulkLookup:
    """Scryfall's bulk endpoint as measured: a card is found by its front face
    (or its whole name when it has one face), never by both halves."""

    def __init__(self):
        self.asked: list[list[str]] = []

    def collection(self, names):
        self.asked.append(list(names))
        found = [KNOWN[n.lower()] for n in names if n.lower() in KNOWN]
        return found, [n for n in names if n.lower() not in KNOWN]


class EmptyStore:
    """A cache with nothing fresh in it, as after the 30-day entry ages out."""

    def __init__(self):
        self.saved: dict[str, str] = {}

    def get_many(self, names):
        return {}, list(names)

    def put(self, card, query=None):
        self.saved[query] = card["name"]

    def commit(self):
        pass


class SplitNameTests(unittest.TestCase):
    def lookup(self, names):
        api, store = BulkLookup(), EmptyStore()
        found, missing = CardQuery(store=store, api=api).cards(names)
        return found, missing, api, store

    def test_both_halves_resolve_with_a_cold_cache(self):
        found, missing, api, store = self.lookup(
            ["Wear // Tear", "Unholy Annex // Ritual Chamber", "Sol Ring"])
        self.assertEqual(missing, [])
        self.assertEqual(found["Wear // Tear"]["name"], "Wear // Tear")
        self.assertEqual(found["Unholy Annex // Ritual Chamber"]["oracle_id"], "o-annex")
        self.assertEqual(api.asked, [["Wear", "Unholy Annex", "Sol Ring"]])
        # Cached under the spelling the list used, so the next run is a hit.
        self.assertEqual(store.saved["Wear // Tear"], "Wear // Tear")

    def test_front_face_spelling_still_resolves(self):
        found, missing, _, _ = self.lookup(["Wear", "Unholy Annex"])
        self.assertEqual((sorted(found), missing), (["Unholy Annex", "Wear"], []))

    def test_a_made_up_second_half_does_not_resolve_to_the_front_card(self):
        found, missing, _, _ = self.lookup(["Sol Ring // Nonsense", "Wear // Tera"])
        self.assertEqual((found, missing), ({}, ["Sol Ring // Nonsense", "Wear // Tera"]))


if __name__ == "__main__":
    unittest.main()
