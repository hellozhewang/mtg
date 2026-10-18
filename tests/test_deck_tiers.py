from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import build_site
import deckfile
import decktiers
import frontend
from test_deck_themes import Catalog, Mana, collection_keys, deck


class DeckTierTests(unittest.TestCase):
    def test_tiers_are_ordered_strongest_first(self):
        self.assertEqual(list(decktiers.TIERS),
                         ["GOD", "SS", "S", "A", "B", "C", "D", "TRASH"])

    def test_invalid_assignments_fail_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiers.json"
            self.assertEqual(decktiers.load(path), {})
            for value in ["s", "Z", ["S"], None, "unrated"]:
                path.write_text(json.dumps({"Test-Deck": value}))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    decktiers.load(path)

    def test_unplaced_decks_are_unrated_not_guessed(self):
        self.assertIsNone(decktiers.classify("New-Deck", {"Other-Deck": "S"}))
        self.assertEqual(decktiers.info(None).title, "Unrated")
        self.assertEqual(decktiers.search_text("GOD"), "GOD-tier")

    def test_every_deck_has_a_tier(self):
        tiers = decktiers.load(ROOT / "frontend/deck-tiers.json")
        keys = collection_keys()
        self.assertEqual(sorted(keys - set(tiers)), [], "place these in deck-tiers.json")
        self.assertEqual(sorted(set(tiers) - keys), [], "these decks no longer exist")

    def test_a_local_only_tier_shows_only_on_the_local_index(self):
        local_d = decktiers.Tier("D", "D tier", "Weak.", local_only=True)
        decks = [deck("Weak-Deck", ("value",), tier="D"), deck("Good-Deck", ("value",), tier="B")]
        templates = frontend.load(ROOT / "frontend")
        with mock.patch.dict(decktiers.TIERS, {"D": local_d}):
            published = build_site.render_index(templates, decks, "https://example.test", Mana())
            local = build_site.render_index(templates, decks, "https://example.test", Mana(),
                                            local=True)
        tiles = {a["href"]: a["data-tier"] for _, a in Catalog(published).tiles}
        self.assertEqual(tiles["alice/Bracket3.5/Weak-Deck.html"], decktiers.UNRATED_ID)
        self.assertNotIn('data-tier="D"', published)
        self.assertIn('data-tier="D"', local)

    def test_tiers_view_has_one_section_per_used_tier_strongest_first(self):
        decks = [deck("Slow-Deck", ("value",), bracket="Bracket3", tier="C"),
                 deck("Fast-Combo", ("combo",), bracket="Bracket5", tier="GOD"),
                 deck("New-Deck", ("value",), bracket="Bracket3"),
                 deck("Mid-Deck", ("value",), bracket="Bracket3", tier="C")]
        page = build_site.render_index(frontend.load(ROOT / "frontend"), decks,
                                       "https://example.test/repo", Mana())
        catalog = Catalog(page)
        tier_groups = [groups[0]["data-tier"] for groups in catalog.sections
                       if groups[0]["class"] == "tier-group"]
        self.assertEqual(tier_groups, ["GOD", "C", "unrated"])
        self.assertIn('class="catalog-tiers" hidden', page)
        self.assertIn('data-grouping="tiers"', page)
        by_name = {attrs["href"]: attrs for _, attrs in catalog.tiles}
        self.assertEqual(by_name["alice/Bracket5/Fast-Combo.html"]["data-tier"], "GOD")
        self.assertEqual(by_name["alice/Bracket3/New-Deck.html"]["data-tier"], "unrated")
        self.assertTrue(by_name["alice/Bracket5/Fast-Combo.html"]["data-search"].endswith("GOD-tier"))
        self.assertIn('<span class="tier" data-tier="GOD"', page)


if __name__ == "__main__":
    unittest.main()
