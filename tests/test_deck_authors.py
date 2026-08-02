from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site
from deckmeta import DeckAuthorStore, created_paths
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
    def test_changed_birth_timestamp_means_same_path_was_recreated(self) -> None:
        self.assertEqual(
            created_paths(
                {"Bracket3/Same-Deck.txt": 100},
                {"Bracket3/Same-Deck.txt": 200},
            ),
            ["Bracket3/Same-Deck.txt"],
        )
        self.assertEqual(
            created_paths(
                {"Bracket3/Same-Deck.txt": 100},
                {"Bracket3/Same-Deck.txt": 100},
            ),
            [],
        )

    def test_old_schema_migrates_and_backfills_birth_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.db"
            with sqlite3.connect(path) as conn:
                conn.execute(
                    "CREATE TABLE deck_authors ("
                    "deck TEXT PRIMARY KEY, author TEXT NOT NULL, "
                    "attributed_at REAL NOT NULL)"
                )
                conn.execute(
                    "INSERT INTO deck_authors VALUES (?,?,?)",
                    ("Bracket3/Old-Deck.txt", "alice", 1.0),
                )
            with DeckAuthorStore(path) as store:
                self.assertEqual(
                    store.timestamps(), {"Bracket3/Old-Deck.txt": None}
                )
                store.sync({"Bracket3/Old-Deck.txt": 123}, [], "unused")
                self.assertEqual(
                    store.timestamps(), {"Bracket3/Old-Deck.txt": 123}
                )

    def test_store_round_trip_and_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.db"
            with DeckAuthorStore(path) as store:
                store.set("Bracket3/Test-Deck.txt", "alice", 100)
                self.assertEqual(store.get("Bracket3/Test-Deck.txt"), "alice")
                store.set("Bracket3/Test-Deck.txt", "bob", 200)
                self.assertEqual(
                    store.all(), {"Bracket3/Test-Deck.txt": "bob"}
                )
                self.assertEqual(
                    store.timestamps(), {"Bracket3/Test-Deck.txt": 200}
                )
                store.set("Bracket4/Keep-Deck.txt", "carol")
                removed = store.sync(
                    {"Bracket4/Keep-Deck.txt": 300}, [], "unused"
                )
                self.assertEqual(removed, ["Bracket3/Test-Deck.txt"])
                self.assertEqual(
                    store.all(), {"Bracket4/Keep-Deck.txt": "carol"}
                )
                self.assertEqual(
                    store.timestamps(), {"Bracket4/Keep-Deck.txt": 300}
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
