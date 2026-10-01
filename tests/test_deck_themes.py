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
        self.tiles = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.stack.append(attrs)
        if tag == "a" and attrs.get("class") == "tile":
            self.tiles.append((self.stack[-1].get("data-theme"), attrs))

    def handle_endtag(self, tag):
        if tag == "section":
            self.stack.pop()


def deck(stem, themes, private=False):
    return SimpleNamespace(
        stem=stem, themes=themes, private=private, created_label="",
        bracket="Bracket3.5", label="Bracket 3.5", commander="Test Commander",
        href=("private/" if private else "") + f"Bracket3.5/{stem}.html",
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
        self.assertTrue({"tribal", "tokens", "combo"}.issubset(
            deckthemes.classify("Krenko-Combo", assignments)))

    def test_new_decks_have_safe_fallbacks(self):
        self.assertEqual(deckthemes.classify("NewCommander-Prison", {}), ("stax",))
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
        decks = [deck("Goblins-Combo", ("tribal", "tokens", "combo")),
                 deck("Machine-Combo", ("combo", "artifacts"))]
        page = build_site.render_index(frontend.load(ROOT / "frontend"), decks,
                                       "https://example.test/repo", Mana())
        catalog = Catalog(page)
        self.assertEqual(len(catalog.tiles), 2)
        self.assertEqual([group for group, _ in catalog.tiles], ["tribal", "combo"])
        self.assertIn('value="combo">Combo (2)</option>', page)
        goblins = catalog.tiles[0][1]
        self.assertEqual(goblins["data-themes"], "tribal tokens combo")
        self.assertIn("Tokens / Go-wide", goblins["data-search"])
        self.assertIn("Combo", goblins["data-search"])

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
