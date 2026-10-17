"""The owner's decks in private/: published and listed like any other, never
writable by the Discord builder (its sandbox only writes public/)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bot"))

import build_site
import commands
import deckfile
import frontend
import workspace


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class Collection:
    """A public/ and a private/ tree in a temp dir, with the env pointed at them."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.public, self.private = base / "public", base / "private"
        self.frontend = base / "frontend"
        write(self.public / "Bracket3" / "Zur-Voltron.txt", "1 Zur the Enchanter\n99 Island\n")
        write(self.public / "Bracket3" / "Shared-Deck.txt", "1 Public Commander\n99 Island\n")
        write(self.private / "Bracket3.5" / "Wort-Goblins.txt", "1 Wort, Boggart Auntie\n99 Mountain\n")
        write(self.private / "Bracket3" / "Shared-Deck.txt", "1 Private Commander\n99 Swamp\n")
        # The owner's tools live beside the decks and are not decks.
        write(self.private / "showcards" / "input.txt", "1 Not A Deck\n")
        write(self.frontend / "deck-tiers.json", json.dumps({"Zur-Voltron": "B", "Shared-Deck": "C"}))
        write(self.frontend / "deck-themes.json", json.dumps({"Zur-Voltron": ["aggro"]}))
        write(self.private / "deck-tiers.json", json.dumps({"Wort-Goblins": "S", "Shared-Deck": "A"}))
        write(self.private / "deck-themes.json", json.dumps({"Wort-Goblins": ["gowide", "combo"]}))
        self.env = mock.patch.dict(os.environ, {
            "MTG_DECKS": str(self.public), "MTG_PRIVATE": str(self.private),
            "MTG_FRONTEND": str(self.frontend)})
        self.env.start()
        return self

    def __exit__(self, *exc):
        self.env.stop()
        self.tmp.cleanup()


class DiscoveryTests(unittest.TestCase):
    def test_only_bracket_folders_hold_private_decks(self):
        with Collection() as c:
            found = deckfile.discover_private(c.private)
            self.assertEqual([p.relative_to(c.private).as_posix() for p in found],
                             ["Bracket3/Shared-Deck.txt", "Bracket3.5/Wort-Goblins.txt"])

    def test_no_private_folder_means_no_private_decks(self):
        self.assertEqual(deckfile.discover_private(Path("/nonexistent/private")), [])

    def test_a_private_deck_has_its_own_page_url(self):
        with Collection() as c:
            base = workspace.site_url()
            self.assertEqual(workspace.site_url(c.private / "Bracket3" / "Shared-Deck.txt"),
                             base + "private/Bracket3/Shared-Deck.html")
            self.assertEqual(workspace.site_url(c.public / "Bracket3" / "Shared-Deck.txt"),
                             base + "Bracket3/Shared-Deck.html")


class CommandTests(unittest.TestCase):
    def test_deck_list_marks_private_decks(self):
        with Collection():
            listing = "\n".join(commands.handle("!decks"))
            self.assertIn("  Wort, Boggart Auntie (private)", listing)
            self.assertIn("  Zur the Enchanter\n", listing)
            self.assertNotIn("Not A Deck", listing)

    def test_deck_print_returns_a_private_list_exactly(self):
        with Collection():
            self.assertEqual(commands.handle("!deck wort"),
                             ["1 Wort, Boggart Auntie\n99 Mountain\n"])

    def test_a_shared_stem_asks_which_and_says_which_is_private(self):
        with Collection():
            reply = commands.handle("!deck shareddeck")[0]
            self.assertIn("Shared-Deck — Public Commander\n", reply + "\n")
            self.assertIn("Shared-Deck — Private Commander (private)", reply)

    def test_random_can_draw_only_private_decks_and_reads_their_own_tier(self):
        with Collection():
            for _ in range(10):
                header, _ = commands.handle("!random private")
                self.assertIn(", private)", header)
                self.assertIn("/private/Bracket", header)
            # Wort is S in the private map; Shared-Deck is A there, C in the public one.
            header, _ = commands.handle("!random wort")
            self.assertIn("Bracket 3.5, S tier, private", header)
            header, _ = commands.handle("!random private commander")
            self.assertIn("A tier, private", header)


class PageTests(unittest.TestCase):
    def test_a_private_deck_links_to_its_file_on_github(self):
        class Query:
            def cards(self, names):
                return {n: {"name": n, "type_line": "Legendary Creature", "cmc": 2,
                            "color_identity": ["R"]} for n in names}, []

        class Mana:
            def pips(self, colours, up):
                return ""

            def render(self, cost, up):
                return ""

        with Collection() as c:
            path = c.private / "Bracket3.5" / "Wort-Goblins.txt"
            info = build_site.DeckInfo(path, c.private, Query(), {}, private=True)
            page = build_site.render_deck(frontend.load(ROOT / "frontend"), info, [info],
                                          "https://github.com/owner/repo", Mana())
            self.assertIn("https://raw.githubusercontent.com/owner/repo/main/private/"
                          "Bracket3.5/Wort-Goblins.txt", page)
            self.assertIn("https://github.com/owner/repo/blob/main/private/"
                          "Bracket3.5/Wort-Goblins.txt", page)
            self.assertIn('class="chip private"', page)


class GitignoreTests(unittest.TestCase):
    """private/ used to be wholly ignored. Now its decks are source, and the
    owner's tools beside them are not."""

    def ignored(self, path: str) -> bool:
        return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", path],
                              capture_output=True).returncode == 0

    def test_decks_and_maps_are_tracked(self):
        for path in ("private/Bracket3/Foo.txt", "private/Bracket3.5/Foo.guide",
                     "private/deck-themes.json", "private/deck-tiers.json",
                     "docs/private/Bracket3/Foo.html"):
            with self.subTest(path=path):
                self.assertFalse(self.ignored(path))

    def test_the_owners_tools_stay_out(self):
        for path in ("private/cardsearch/search.py", "private/showcards/input.txt",
                     "private/notes.txt"):
            with self.subTest(path=path):
                self.assertTrue(self.ignored(path))


if __name__ == "__main__":
    unittest.main()
