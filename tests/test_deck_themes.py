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


def deck(stem, themes, private=False, bracket="Bracket3.5"):
    return SimpleNamespace(
        stem=stem, themes=themes, private=private, created_label="",
        bracket=bracket, label=build_site.bracket_label(bracket), commander="Test Commander",
        href=("private/" if private else "") + f"{bracket}/{stem}.html",
        art_url="", art_card={}, author="zzwang", colours=[], total=100,
        lands=35, avg_mv=2.4, gcs=[], cap=3,
    )


class Mana:
    def pips(self, colours, up):
        return ""


class DeckThemeTests(unittest.TestCase):
    def test_curated_plans_distinguish_similar_commanders(self):
        assignments = deckthemes.load(ROOT / "frontend/deck-themes.json")
        self.assertEqual(deckthemes.classify("Cloud-Equipment", assignments)[0], "voltron")
        self.assertNotIn("voltron", deckthemes.classify("Cloud-Attacks", assignments))
        self.assertEqual(deckthemes.classify("Krenko-Combo", assignments)[0], "goblins")
        self.assertTrue({"tribal", "tokens", "combo"}.issubset(
            deckthemes.classify("Krenko-Combo", assignments)))

    def test_new_decks_have_safe_fallbacks(self):
        self.assertEqual(deckthemes.classify("NewCommander-Prison", {}), ("stax",))
        self.assertEqual(deckthemes.classify("NewCommander-Goblins", {}), ("goblins",))
        self.assertEqual(deckthemes.classify("NewCommander-NewPlan", {}), ("other",))

    def test_invalid_assignments_fail_instead_of_hiding_decks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "themes.json"
            self.assertEqual(deckthemes.load(path), {})
            for value in [[], ["typo"], ["tribal", "tribal"], "tribal"]:
                path.write_text(json.dumps({"Test-Deck": value}))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    deckthemes.load(path)

    def test_one_tile_per_deck_with_secondary_theme_filters(self):
        decks = [deck("Goblins-Combo", ("goblins", "tribal", "tokens", "combo")),
                 deck("Machine-Combo", ("combo", "artifacts"))]
        page = build_site.render_index(frontend.load(ROOT / "frontend"), decks,
                                       "https://example.test/repo", Mana())
        catalog = Catalog(page)
        self.assertEqual(len(catalog.tiles), 2)
        self.assertEqual([attrs["data-themes"].split()[0] for _, attrs in catalog.tiles],
                         ["goblins", "combo"])
        self.assertIn('value="goblins">Goblins</option>', page)
        self.assertIn('value="tribal">Tribal / Kindred</option>', page)
        self.assertIn('value="combo">Combo</option>', page)
        goblins = catalog.tiles[0][1]
        self.assertEqual(goblins["data-themes"], "goblins tribal tokens combo")
        self.assertIn("Tokens / Go-wide", goblins["data-search"])
        self.assertIn("Combo", goblins["data-search"])

    def test_default_bracket_list_and_collapsible_category_destinations(self):
        decks = [deck("Fast-Combo", ("combo",), bracket="Bracket5"),
                 deck("Goblins", ("goblins", "tribal", "combo"), bracket="Bracket3.5"),
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
                          if len(groups) == 1], ["goblins", "combo"])
        self.assertTrue(all("open" in groups[0] for groups in category_groups))
        self.assertEqual([(groups[0]["data-theme"], groups[1]["data-bracket"])
                          for groups in category_groups if len(groups) == 2],
                         [("goblins", "Bracket3.5"), ("combo", "Bracket3"),
                          ("combo", "Bracket5")])
        placements = []
        for groups, attrs in catalog.tiles:
            self.assertEqual([group["class"] for group in groups],
                             ["bracket-group"])
            self.assertIn("open", groups[0])
            self.assertEqual(groups[0]["data-bracket"], attrs["data-bracket"])
            placements.append((attrs["data-themes"].split()[0], groups[0]["data-bracket"],
                               attrs["href"]))
        self.assertEqual(placements, [
            ("combo", "Bracket3", "Bracket3/Engine-Combo.html"),
            ("combo", "Bracket3", "Bracket3/Other-Combo.html"),
            ("goblins", "Bracket3.5", "Bracket3.5/Goblins.html"),
            ("combo", "Bracket5", "Bracket5/Fast-Combo.html"),
        ])
        self.assertEqual(len(catalog.sections), 8)  # three list brackets plus five category sections
        self.assertEqual(page.count('<summary class="bracket-heading">'), 3)

    def test_private_names_and_assignments_never_enter_public_catalog(self):
        public = deck("Shared-Deck", ("voltron",))
        private = deck("Shared-Deck", ("goad",), private=True)
        templates = frontend.load(ROOT / "frontend")
        published = build_site.render_index(templates, [public], "https://example.test", Mana())
        local = build_site.render_index(templates, [public, private], "https://example.test", Mana())
        self.assertNotIn('value="goad"', published)
        self.assertNotIn("private/Bracket", published)
        self.assertIn('value="goad"', local)
        self.assertIn("private/Bracket3.5/Shared-Deck.html", local)
        self.assertEqual(len(Catalog(local).tiles), 2)


if __name__ == "__main__":
    unittest.main()
