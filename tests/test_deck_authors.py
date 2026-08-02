from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site
from deckmeta import DeckAuthorStore
import frontend


class FakeMana:
    def pips(self, _colours: list[str], _up: str) -> str:
        return ""


class FakeDeck:
    bracket = "Bracket3"
    label = "Bracket 3"
    stem = "Test-Deck"
    commander = "Test Commander"
    href = "Bracket3/Test-Deck.html"
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
    def test_store_round_trip_and_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.db"
            with DeckAuthorStore(path) as store:
                store.set("Bracket3/Test-Deck.txt", "alice")
                self.assertEqual(store.get("Bracket3/Test-Deck.txt"), "alice")
                store.set("Bracket3/Test-Deck.txt", "bob")
                self.assertEqual(
                    store.all(), {"Bracket3/Test-Deck.txt": "bob"}
                )

    def test_index_displays_author_and_includes_it_in_search(self) -> None:
        templates = frontend.load(ROOT / "frontend")
        page = build_site.render_index(
            templates, [FakeDeck()], "https://example.test/repo", FakeMana()
        )
        self.assertIn('<span class="tile-author">by alice</span>', page)
        self.assertIn(
            'data-search="Test-Deck Test Commander Bracket 3 alice"', page
        )


if __name__ == "__main__":
    unittest.main()
