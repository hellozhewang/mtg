from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site
import frontend


class FakeMana:
    def pips(self, _colours: list[str], _up: str) -> str:
        return ""


class FakeDeck:
    created_label = ""
    modified = 0
    modified_label = ""
    bracket = "Bracket3"
    label = "Bracket 3"
    stem = "Test-Deck"
    themes = ("value",)
    tier = None
    commander = "Test Commander"
    href = "alice/Bracket3/Test-Deck.html"
    key = "alice/Test-Deck"
    art_url = ""
    art_card: dict = {}
    author = "alice"
    colours: list[str] = []
    total = 100
    lands = 36
    avg_mv = 2.5
    gcs: list[str] = []
    cap = 3


class DeckAuthorTests(unittest.TestCase):
    """The folder a deck is in is its owner; nothing else records authorship."""

    def test_the_owner_folder_is_the_byline_and_the_map_key(self) -> None:
        class Query:
            def cards(self, names):
                return {n: {"name": n, "type_line": "Creature", "cmc": 1} for n in names}, []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = root / "ratdos" / "Bracket3" / "Obeka-Upkeep.txt"
            path.parent.mkdir(parents=True)
            path.write_text("1 Obeka, Splitter of Seconds\n99 Island\n")
            info = build_site.DeckInfo(path, root, Query(),
                                       tier_assignments={"ratdos/Obeka-Upkeep": "A",
                                                         "Obeka-Upkeep": "D"})
            self.assertEqual(info.author, "ratdos")
            self.assertEqual(info.bracket, "Bracket3")
            self.assertEqual(info.key, "ratdos/Obeka-Upkeep")
            self.assertEqual(info.tier, "A")
            self.assertEqual(info.href, "ratdos/Bracket3/Obeka-Upkeep.html")

    def test_index_displays_author_and_includes_it_in_search(self) -> None:
        templates = frontend.load(ROOT / "frontend")
        page = build_site.render_index(
            templates, [FakeDeck()], "https://example.test/repo", FakeMana()
        )
        self.assertIn('<span class="tile-author">by alice</span>', page)
        self.assertIn(
            'data-search="Test-Deck Test Commander Bracket 3 alice Value &amp; Ramp ramp big mana lands '
            'landfall artifacts enchantress counters proliferate blink superfriends toolbox unrated"', page
        )

    def test_index_does_not_reference_an_unavailable_art_file(self) -> None:
        templates = frontend.load(ROOT / "frontend")
        deck = FakeDeck()
        deck.art_url = "https://cards.scryfall.io/art/front/a/b/card.webp"
        deck.art_card = {"oracle_id": "cloud-oracle"}
        art_name = build_site.image_file(
            deck.art_card, 0, build_site.ART, deck.art_url
        )

        missing = build_site.render_index(
            templates, [deck], "https://example.test/repo", FakeMana(), set()
        )
        self.assertIn('<span class="art-blank"></span>', missing)
        self.assertNotIn(f'src="img/{art_name}"', missing)

        available = build_site.render_index(
            templates, [deck], "https://example.test/repo", FakeMana(), {art_name}
        )
        self.assertIn(f'src="img/{art_name}"', available)


if __name__ == "__main__":
    unittest.main()
