from __future__ import annotations

import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site
import deckthemes
import frontend


class Catalog(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.stack = []
        self.sections = []
        self.tiles = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("section", "details"):
            self.stack.append(attrs)
            self.sections.append(tuple(self.stack))
        if tag == "a" and attrs.get("class") == "tile":
            self.tiles.append((tuple(self.stack), attrs))

    def handle_endtag(self, tag):
        if tag in ("section", "details"):
            self.stack.pop()


def deck(stem, themes, private=False, bracket="Bracket3.5", tier=None):
    return SimpleNamespace(
        stem=stem, themes=themes, private=private, created_label="", tier=tier,
        bracket=bracket, label=build_site.bracket_label(bracket), commander="Test Commander",
        href=("private/" if private else "") + f"{bracket}/{stem}.html",
        art_url="", art_card={}, author="zzwang", colours=[], total=100,
        lands=35, avg_mv=2.4, gcs=[], cap=3,
    )


class Mana:
    def pips(self, colours, up):
        return ""


class DeckThemeTests(unittest.TestCase):
    def test_seven_fixed_categories_plus_a_catch_all(self):
        self.assertEqual(tuple(deckthemes.THEMES), ("aggro", "gowide", "combo", "control",
                                                    "graveyard", "spells", "value", "other"))

    def test_curated_plans(self):
        assignments = deckthemes.load(ROOT / "frontend/deck-themes.json")
        self.assertEqual(deckthemes.classify("Cloud-Equipment", assignments)[0], "aggro")
        self.assertEqual(deckthemes.classify("Kinnan-Infinite", assignments)[0], "combo")
        self.assertEqual(deckthemes.classify("Krenko-Combo", assignments), ("combo", "gowide"))

    def test_every_private_deck_has_an_explicit_entry(self):
        # Published like the public ones, so held to the same rule, in their own map.
        assignments = deckthemes.load(ROOT / "private/deck-themes.json")
        import deckfile
        stems = {p.stem for p in deckfile.discover_private(ROOT / "private")}
        self.assertEqual(sorted(stems - set(assignments)), [], "add these to private/deck-themes.json")
        self.assertEqual(sorted(set(assignments) - stems), [], "these decks no longer exist")

    def test_every_public_deck_has_an_explicit_entry(self):
        assignments = deckthemes.load(ROOT / "frontend/deck-themes.json")
        import deckfile
        stems = {p.stem for p in deckfile.discover(sorted((ROOT / "public").glob("Bracket*")))}
        self.assertEqual(sorted(stems - set(assignments)), [], "add these to deck-themes.json")
        self.assertEqual(sorted(set(assignments) - stems), [], "these decks no longer exist")

    def test_new_decks_have_safe_fallbacks(self):
        self.assertEqual(deckthemes.classify("NewCommander-Prison", {}), ("control",))
        self.assertEqual(deckthemes.classify("NewCommander-Goblins", {}), ("gowide",))
        self.assertEqual(deckthemes.classify("NewCommander-NewPlan", {}), ("other",))

    def test_anything_outside_the_fixed_set_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "themes.json"
            self.assertEqual(deckthemes.load(path), {})
            for value in [[], ["typo"], ["control", "control"], "control",
                          ["tribal"], ["stax"], ["goblins", "gowide"]]:
                path.write_text(json.dumps({"Test-Deck": value}))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    deckthemes.load(path)

    def test_one_tile_per_deck_with_secondary_theme_filters(self):
        decks = [deck("Goblins-Combo", ("combo", "gowide")),
                 deck("Machine-Combo", ("combo", "value"))]
        page = build_site.render_index(frontend.load(ROOT / "frontend"), decks,
                                       "https://example.test/repo", Mana())
        catalog = Catalog(page)
        self.assertEqual(len(catalog.tiles), 2)
        self.assertEqual([attrs["data-themes"] for _, attrs in catalog.tiles],
                         ["combo gowide", "combo value"])
        self.assertIn('value="gowide">Tokens &amp; Aristocrats</option>', page)
        self.assertIn('value="combo">Combo</option>', page)
        self.assertIn("Tokens & Aristocrats", catalog.tiles[0][1]["data-search"])

    def test_private_decks_share_the_one_catalog_with_a_badge(self):
        public = deck("Krenko-Combo", ("combo", "gowide"))
        private = deck("Wort-Goblins", ("gowide", "combo"), private=True)
        page = build_site.render_index(frontend.load(ROOT / "frontend"), [public, private],
                                       "https://example.test", Mana())
        catalog = Catalog(page)
        self.assertEqual(len(catalog.tiles), 2)
        hrefs = {attrs["href"]: attrs for _, attrs in catalog.tiles}
        self.assertIn("Bracket3.5/Krenko-Combo.html", hrefs)
        self.assertIn("private/Bracket3.5/Wort-Goblins.html", hrefs)
        # One badge, on the owner's deck, and the search box finds it by the word.
        self.assertEqual(page.count('class="chip private"'), 1)
        self.assertIn("private", hrefs["private/Bracket3.5/Wort-Goblins.html"]["data-search"])
        self.assertNotIn("private", hrefs["Bracket3.5/Krenko-Combo.html"]["data-search"])
        self.assertNotIn("goblins", page.lower().replace("wort-goblins", ""))

    def test_default_bracket_list_and_collapsible_category_destinations(self):
        decks = [deck("Fast-Combo", ("combo",), bracket="Bracket5"),
                 deck("Goblin-Swarm", ("gowide",), bracket="Bracket3.5"),
                 deck("Engine-Combo", ("combo",), bracket="Bracket3"),
                 deck("Other-Combo", ("combo",), bracket="Bracket3")]
        page = build_site.render_index(frontend.load(ROOT / "frontend"), decks,
                                       "https://example.test/repo", Mana())
        catalog = Catalog(page)
        self.assertIn('data-grouping="list" data-view="list"', page)
        self.assertIn('data-grouping="list" aria-pressed="true">List</button>', page)
        self.assertIn('class="catalog-categories" hidden', page)
        category_groups = [groups for groups in catalog.sections
                           if groups[0]["class"] == "strategy-group"]
        self.assertEqual([groups[0]["data-theme"] for groups in category_groups
                          if len(groups) == 1], ["gowide", "combo"])
        self.assertTrue(all("open" in groups[0] for groups in category_groups))
        self.assertEqual([(groups[0]["data-theme"], groups[1]["data-bracket"])
                          for groups in category_groups if len(groups) == 2],
                         [("gowide", "Bracket3.5"), ("combo", "Bracket3"),
                          ("combo", "Bracket5")])
        placements = []
        for groups, attrs in catalog.tiles:
            self.assertEqual([group["class"] for group in groups], ["bracket-group"])
            self.assertIn("open", groups[0])
            self.assertEqual(groups[0]["data-bracket"], attrs["data-bracket"])
            placements.append((attrs["data-themes"].split()[0], groups[0]["data-bracket"],
                               attrs["href"]))
        self.assertEqual(placements, [
            ("combo", "Bracket3", "Bracket3/Engine-Combo.html"),
            ("combo", "Bracket3", "Bracket3/Other-Combo.html"),
            ("gowide", "Bracket3.5", "Bracket3.5/Goblin-Swarm.html"),
            ("combo", "Bracket5", "Bracket5/Fast-Combo.html"),
        ])
        # three list brackets, five category sections, one Unrated tier section
        self.assertEqual(len(catalog.sections), 9)
        self.assertEqual(page.count('<summary class="bracket-heading">'), 3)

    def test_a_public_and_a_private_deck_can_share_a_name(self):
        public = deck("Shared-Deck", ("aggro",))
        private = deck("Shared-Deck", ("control",), private=True)
        page = build_site.render_index(frontend.load(ROOT / "frontend"), [public, private],
                                       "https://example.test", Mana())
        tiles = {attrs["href"]: attrs["data-themes"] for _, attrs in Catalog(page).tiles}
        self.assertEqual(tiles, {"Bracket3.5/Shared-Deck.html": "aggro",
                                 "private/Bracket3.5/Shared-Deck.html": "control"})


if __name__ == "__main__":
    unittest.main()
