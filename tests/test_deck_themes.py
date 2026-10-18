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


def deck(stem, themes, owner="alice", bracket="Bracket4", tier=None):
    return SimpleNamespace(
        stem=stem, themes=themes, created_label="", tier=tier,
        modified=0, modified_label="", key=f"{owner}/{stem}",
        bracket=bracket, label=build_site.bracket_label(bracket), commander="Test Commander", commanders=["Test Commander"],
        href=f"{owner}/{bracket}/{stem}.html",
        art_url="", art_card={}, author=owner, colours=[], total=100,
        lands=35, avg_mv=2.4, gcs=[], cap=3,
    )


def collection_keys():
    """`<owner>/<Deck>` for every deck in the repo."""
    import deckfile
    return {f"{p.parent.parent.name}/{p.stem}"
            for p in deckfile.discover_collection(ROOT / "public")}


class Mana:
    def pips(self, colours, up):
        return ""


class DeckThemeTests(unittest.TestCase):
    def test_seven_fixed_categories_plus_a_catch_all_and_local_goblins(self):
        self.assertEqual(deckthemes.CANONICAL, ("aggro", "gowide", "combo", "control",
                                                "graveyard", "spells", "value", "other"))
        self.assertEqual([k for k, t in deckthemes.THEMES.items() if t.local_only], ["goblins"])

    def test_curated_plans(self):
        assignments = deckthemes.load(ROOT / "frontend/deck-themes.json")
        self.assertEqual(deckthemes.classify("zzwang/Kinnan-Infinite", assignments)[0], "combo")
        self.assertEqual(deckthemes.classify("zzwang/Krenko-Combo", assignments),
                         ("combo", "gowide", "goblins"))
        # Keyed by owner: the bare stem is not an entry.
        self.assertEqual(deckthemes.classify("Krenko-Combo", assignments), ("combo",))

    def test_every_deck_has_an_explicit_entry(self):
        assignments = deckthemes.load(ROOT / "frontend/deck-themes.json")
        keys = collection_keys()
        self.assertEqual(sorted(keys - set(assignments)), [], "add these to deck-themes.json")
        self.assertEqual(sorted(set(assignments) - keys), [], "these decks no longer exist")

    def test_new_decks_have_safe_fallbacks(self):
        self.assertEqual(deckthemes.classify("NewCommander-Prison", {}), ("control",))
        self.assertEqual(deckthemes.classify("NewCommander-Goblins", {}), ("gowide", "goblins"))
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

    def test_the_owner_is_the_byline_and_a_search_term(self):
        page = build_site.render_index(frontend.load(ROOT / "frontend"),
                                       [deck("Krenko-Combo", ("combo",), owner="ratdos")],
                                       "https://example.test", Mana())
        (_, attrs), = Catalog(page).tiles
        self.assertEqual(attrs["href"], "ratdos/Bracket4/Krenko-Combo.html")
        self.assertIn("ratdos", attrs["data-search"])
        self.assertIn('<span class="tile-author">by ratdos</span>', page)
        self.assertNotIn("private", page.lower())

    def test_default_bracket_list_and_collapsible_category_destinations(self):
        decks = [deck("Fast-Combo", ("combo",), bracket="Bracket5"),
                 deck("Goblin-Swarm", ("gowide",), bracket="Bracket4"),
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
                         [("gowide", "Bracket4"), ("combo", "Bracket3"),
                          ("combo", "Bracket5")])
        placements = []
        for groups, attrs in catalog.tiles:
            self.assertEqual([group["class"] for group in groups], ["bracket-group"])
            self.assertIn("open", groups[0])
            self.assertEqual(groups[0]["data-bracket"], attrs["data-bracket"])
            placements.append((attrs["data-themes"].split()[0], groups[0]["data-bracket"],
                               attrs["href"]))
        self.assertEqual(placements, [
            ("combo", "Bracket3", "alice/Bracket3/Engine-Combo.html"),
            ("combo", "Bracket3", "alice/Bracket3/Other-Combo.html"),
            ("gowide", "Bracket4", "alice/Bracket4/Goblin-Swarm.html"),
            ("combo", "Bracket5", "alice/Bracket5/Fast-Combo.html"),
        ])
        # three list brackets, five category sections, one Unrated tier section
        self.assertEqual(len(catalog.sections), 9)
        self.assertEqual(page.count('<summary class="bracket-heading">'), 3)

    def test_goblins_only_on_the_local_index(self):
        krenko = deck("Krenko-Combo", ("combo", "gowide", "goblins"))
        wort = deck("Wort-Goblins", ("gowide", "combo", "goblins"), owner="zzwang")
        other = deck("Fair-Deck", ("aggro",), bracket="Bracket3")
        templates = frontend.load(ROOT / "frontend")
        decks = [krenko, wort, other]
        published = build_site.render_index(templates, decks, "https://example.test", Mana())
        self.assertNotIn('data-theme="goblins"', published)
        self.assertNotIn(">Goblins<", published)
        self.assertNotIn("tile mirror", published)
        local = build_site.render_index(templates, decks, "https://example.test", Mana(),
                                        local=True)
        catalog = Catalog(local)
        self.assertEqual(len(catalog.tiles), 3)            # one real tile per deck
        self.assertIn('value="goblins">Goblins (local)</option>', local)
        self.assertIn('<span class="theme-tag local">Goblins</span>', local)
        self.assertEqual(local.count('class="chip local"'), 1)
        self.assertEqual(local.count('class="tile mirror"'), 2)
        self.assertTrue([g for g in catalog.sections if g[0].get("data-theme") == "goblins"])
        # The goblin decks keep their canonical homes as well.
        primaries = sorted(attrs["data-themes"].split()[0] for _, attrs in catalog.tiles)
        self.assertEqual(primaries, ["aggro", "combo", "gowide"])

    def test_two_owners_can_each_have_a_deck_of_the_same_name(self):
        mine = deck("Shared-Deck", ("aggro",), owner="alice")
        theirs = deck("Shared-Deck", ("control",), owner="bob")
        page = build_site.render_index(frontend.load(ROOT / "frontend"), [mine, theirs],
                                       "https://example.test", Mana())
        tiles = {attrs["href"]: attrs["data-themes"] for _, attrs in Catalog(page).tiles}
        self.assertEqual(tiles, {"alice/Bracket4/Shared-Deck.html": "aggro",
                                 "bob/Bracket4/Shared-Deck.html": "control"})


if __name__ == "__main__":
    unittest.main()
