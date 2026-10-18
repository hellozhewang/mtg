"""Every deck lives in its owner's folder, public/<user>/<Bracket>/, and the
folder is the owner: on the catalog, in the Discord commands and in the maps."""
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
    """Two owners' folders in a temp dir, with the env pointed at them."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.public, self.frontend = base / "public", base / "frontend"
        write(self.public / "alice" / "Bracket3" / "Zur-Voltron.txt", "1 Zur the Enchanter\n99 Island\n")
        write(self.public / "alice" / "Bracket3" / "Shared-Deck.txt", "1 Alice Commander\n99 Island\n")
        write(self.public / "bob" / "Bracket4" / "Wort-Goblins.txt", "1 Wort, Boggart Auntie\n99 Mountain\n")
        write(self.public / "bob" / "Bracket3" / "Shared-Deck.txt", "1 Bob Commander\n99 Swamp\n")
        # Not decks: a list outside any bracket folder, and the builder's instructions.
        write(self.public / "alice" / "notes.txt", "1 Not A Deck\n")
        write(self.public / "alice" / "AGENTS.md", "instructions\n")
        write(self.frontend / "deck-tiers.json", json.dumps(
            {"alice/Zur-Voltron": "B", "alice/Shared-Deck": "C",
             "bob/Wort-Goblins": "S", "bob/Shared-Deck": "A"}))
        write(self.frontend / "deck-themes.json", json.dumps(
            {"alice/Zur-Voltron": ["aggro", "goblins"], "bob/Wort-Goblins": ["gowide", "combo"]}))
        self.env = mock.patch.dict(os.environ, {
            "MTG_DECKS": str(self.public), "MTG_FRONTEND": str(self.frontend)})
        self.env.start()
        return self

    def __exit__(self, *exc):
        self.env.stop()
        self.tmp.cleanup()


class FolderTests(unittest.TestCase):
    def test_only_owner_bracket_folders_hold_decks(self):
        with Collection() as c:
            found = deckfile.discover_collection(c.public)
            self.assertEqual([p.relative_to(c.public).as_posix() for p in found],
                             ["alice/Bracket3/Shared-Deck.txt", "alice/Bracket3/Zur-Voltron.txt",
                              "bob/Bracket3/Shared-Deck.txt", "bob/Bracket4/Wort-Goblins.txt"])

    def test_a_decks_page_starts_with_its_owner(self):
        with Collection() as c:
            self.assertEqual(workspace.site_url(c.public / "bob" / "Bracket3" / "Shared-Deck.txt"),
                             workspace.site_url() + "bob/Bracket3/Shared-Deck.html")
            self.assertEqual(workspace.owner_of(c.public / "bob" / "Bracket3" / "Shared-Deck.txt"), "bob")

    def test_usernames_that_cannot_be_folders(self):
        self.assertEqual(workspace.owner_name("RatDos"), "ratdos")
        self.assertEqual(workspace.owner_name("em0k1ller"), "em0k1ller")
        for name in ("", "../x", "a/b", ".hidden", "img", "mana", "tts", "private",
                     "Bracket3", "bracket4", "x" * 33, "two words"):
            with self.subTest(name=name):
                self.assertIsNone(workspace.owner_name(name))


class CommandTests(unittest.TestCase):
    def test_deck_list_names_each_owner(self):
        with Collection():
            listing = "\n".join(commands.handle("!decks"))
            self.assertIn("  Wort, Boggart Auntie (bob)", listing)
            self.assertIn("  Zur the Enchanter (alice)", listing)
            self.assertNotIn("Not A Deck", listing)

    def test_a_shared_name_prefers_the_askers_own_deck(self):
        with Collection():
            self.assertEqual(commands.handle("!deck shared deck", "bob"),
                             ["1 Bob Commander\n99 Swamp\n"])
            self.assertEqual(commands.handle("!deck shared deck", "alice"),
                             ["1 Alice Commander\n99 Island\n"])

    def test_owner_slash_name_picks_one_owners_deck(self):
        with Collection():
            self.assertEqual(commands.handle("!deck bob/shared", "alice"),
                             ["1 Bob Commander\n99 Swamp\n"])

    def test_otherwise_a_shared_name_lists_owner_and_stem(self):
        with Collection():
            reply = commands.handle("!deck shareddeck", "carol")[0]
            self.assertIn("alice/Shared-Deck — Alice Commander", reply)
            self.assertIn("bob/Shared-Deck — Bob Commander", reply)

    def test_random_filters_by_owner_and_reads_the_owners_tier(self):
        with Collection():
            for _ in range(10):
                header, _ = commands.handle("!random bob")
                self.assertIn("by bob)", header)
                self.assertIn("/bob/Bracket", header)
            header, _ = commands.handle("!random wort")
            self.assertIn("Bracket 4, S tier, by bob", header)

    def test_a_local_only_category_is_not_a_filter(self):
        # Zur-Voltron is tagged goblins; only Wort-Goblins matches, by its name.
        with Collection():
            for _ in range(10):
                self.assertIn("**Wort-Goblins**", commands.handle("!random goblins")[0])


class PageTests(unittest.TestCase):
    def test_a_deck_links_to_its_file_in_its_owners_folder(self):
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
            path = c.public / "bob" / "Bracket4" / "Wort-Goblins.txt"
            info = build_site.DeckInfo(path, c.public, Query())
            page = build_site.render_deck(frontend.load(ROOT / "frontend"), info, [info],
                                          "https://github.com/owner/repo", Mana())
            self.assertIn("https://raw.githubusercontent.com/owner/repo/main/public/bob/"
                          "Bracket4/Wort-Goblins.txt", page)
            self.assertIn("../../style.css", page)

    def test_old_urls_redirect_to_the_owner_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, mapping = Path(tmp) / "docs", Path(tmp) / "redirects.json"
            mapping.write_text(json.dumps({
                "Bracket3/Zur-Voltron.html": "alice/Bracket3/Zur-Voltron.html",
                "private/Bracket4/Gone.html": "alice/Bracket4/Gone.html",
                "alice/Bracket3/Taken.html": "alice/Bracket3/Zur-Voltron.html"}))
            live = [type("D", (), {"href": "alice/Bracket3/Zur-Voltron.html", "stem": "Zur-Voltron"})]
            taken = {out / "alice/Bracket3/Taken.html": "a real page"}
            pages = build_site.redirect_pages(frontend.load(ROOT / "frontend"), live, out,
                                              mapping, taken)
            self.assertEqual(list(pages), [out / "Bracket3/Zur-Voltron.html"])
            self.assertIn('url=../alice/Bracket3/Zur-Voltron.html"',
                          pages[out / "Bracket3/Zur-Voltron.html"])


class GitignoreTests(unittest.TestCase):
    def ignored(self, path: str) -> bool:
        return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", path],
                              capture_output=True).returncode == 0

    def test_decks_are_tracked(self):
        for path in ("public/alice/Bracket3/Foo.txt", "public/alice/Bracket4/Foo.guide",
                     "frontend/deck-themes.json", "frontend/redirects.json"):
            with self.subTest(path=path):
                self.assertFalse(self.ignored(path))

    def test_generated_and_personal_files_stay_out(self):
        for path in ("public/alice/AGENTS.md", "docs/index.local.html",
                     "private/cardsearch/search.py", "private/showcards/input.txt"):
            with self.subTest(path=path):
                self.assertTrue(self.ignored(path))


class LocalServerTests(unittest.TestCase):
    def test_the_home_page_is_the_local_index_and_everything_else_is_docs(self):
        import start_private_server as server
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            write(site / "index.html", "published")
            write(site / server.LOCAL_INDEX, "local")
            handler = object.__new__(server.CatalogHandler)
            handler.directory = str(site)
            for path in ("/", "/index.html", "/index.html?random=copied"):
                with self.subTest(path=path):
                    self.assertEqual(Path(handler.translate_path(path)).name, server.LOCAL_INDEX)
            self.assertEqual(Path(handler.translate_path("/zz/Bracket3/X.html")).name, "X.html")
            (site / server.LOCAL_INDEX).unlink()
            self.assertEqual(Path(handler.translate_path("/")).name, site.name)   # plain docs/


if __name__ == "__main__":
    unittest.main()
